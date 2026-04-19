import os
import asyncio
import datetime
import re
import json
import shutil
import yaml
from pydantic import BaseModel, Field
from typing import List, Dict
from agent.schema_builder import discover_entity_types, build_schema_md, bootstrap_type_yamls
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable

class _LLMProxy(Runnable):
    """Thin ``Runnable`` wrapper around a LangChain LLM.

    Inheriting from ``Runnable`` (not from Pydantic's ``BaseModel``) means
    instance attributes like ``ainvoke`` can be freely replaced in tests
    via simple assignment while still being recognised by LangChain chains
    (``prompt | self.llm | parser``).

    Attribute access falls through to the wrapped LLM so that callers can
    read provider-specific attributes (e.g. ``model_name``) transparently.
    """

    def __init__(self, llm):
        self._llm = llm

    # ── Runnable interface ────────────────────────────────────────────────

    def invoke(self, input, config=None, **kwargs):
        return self._llm.invoke(input, config, **kwargs)

    async def ainvoke(self, input, config=None, **kwargs):
        return await self._llm.ainvoke(input, config, **kwargs)

    # ── Transparent attribute delegation ─────────────────────────────────

    def __getattr__(self, name):
        # Called only when the attribute is NOT found on the proxy itself,
        # so instance-level overrides (e.g. mock replacements) take priority.
        return getattr(self._llm, name)


class WikiPage(BaseModel):
    path: str = Field(description="Relative path for the wiki page, e.g. 'clients/louis-vuitton.md'")
    content: str = Field(description="Full markdown content including YAML frontmatter and all sections")
    action: str = Field(description="'create' for new pages, 'update' for existing pages")

class FaragoIngestionResult(BaseModel):
    pages: List[WikiPage] = Field(description="All wiki pages to create or update")
    log_entry: str = Field(description="2-3 line summary of what was ingested, for log.md")

class LintFinding(BaseModel):
    severity: str = Field(description="'error', 'warning', or 'suggestion'")
    page: str = Field(description="Affected page path (e.g. 'clients/louis-vuitton.md') or 'global'")
    description: str = Field(description="Description of the issue or suggestion")

class LintReport(BaseModel):
    findings: List[LintFinding] = Field(description="All findings from the lint operation")
    summary: str = Field(description="One-line summary of findings count by severity")


INGEST_HUMAN_TEMPLATE = """You are ingesting a new source document into the Farago Projects wiki.

Current wiki index:
{index_content}

Existing pages that may need updating:
{existing_pages}

Source document filename: {filename}
Source document content:
{source_content}

Instructions:
1. Identify all entities in the source that match the Farago schema: clients, prospects, contacts, photographers, productions.
2. For each entity, produce a complete wiki page with valid YAML frontmatter matching the schema for that entity type.
3. Use the exact file path format: "clients/brand-name.md", "photographers/first-last.md", "productions/YYYY-MM-client-description.md", etc.
4. File names must be lowercase and hyphen-separated.
5. For existing pages (action="update"), produce the full merged content.
6. For new pages (action="create"), produce the full page with all schema sections.
7. Always use [[subdir/page-name]] wikilink syntax for cross-references.
8. Write a 2-3 line log_entry summarising what was ingested.

{format_instructions}"""

RELEVANCE_HUMAN_TEMPLATE = """Given the wiki index below, list the 3-5 most relevant page paths to answer the user query.
Return ONLY a comma-separated list of relative page paths (e.g. 'clients/louis-vuitton.md, contacts/jane-doe.md').
If nothing is relevant, return 'None'.

Wiki index:
{index}

Query: {query}"""

ANSWER_HUMAN_TEMPLATE = """Answer the user query using the provided wiki context.
Cite sources using [[subdir/page-name]] wikilink syntax.
If the context doesn't contain the answer, say so.

Context:
{context}

Query: {query}"""

LINT_HUMAN_TEMPLATE = """Perform a lint operation on the Farago Projects wiki.

All current wiki pages:
{wiki_content}

Instructions (per SCHEMA.md lint operation):
1. Find orphan pages — pages with no inbound wikilinks from other pages.
2. Flag contradictions between pages (conflicting dates, roles, statuses).
3. Identify entities mentioned in page text that lack their own page.
4. Suggest data gaps that could be filled with a new source or web search.

Return findings grouped by severity: 'error' (structural problems), 'warning' (data quality), 'suggestion' (gaps to fill).
Use page='global' for findings that are not specific to one page.

{format_instructions}"""


class WikiManager:
    def __init__(self, sources_dir="sources", wiki_dir="wiki", archive_dir="archive", llm=None, schema_dir=None):
        self.sources_dir = sources_dir
        self.wiki_dir = wiki_dir
        self.archive_dir = archive_dir
        self.archive_wiki_dir = os.path.join(archive_dir, "wiki")
        self.archive_sources_dir = os.path.join(archive_dir, "sources")
        self.metadata_path = os.path.join(sources_dir, ".metadata.json")
        self.schema_dir = schema_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "schema"
        )
        self.system_prompt = self._load_system_prompt()
        self.llm = llm if llm else self._init_llm()
        self._write_lock = asyncio.Lock()

        for d in [self.sources_dir, self.wiki_dir, self.archive_dir,
                  self.archive_wiki_dir, self.archive_sources_dir]:
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)

        bootstrap_type_yamls(self.wiki_dir)

        # Build search index on startup if missing
        index_path = os.path.join(self.wiki_dir, "search-index.json")
        if not os.path.exists(index_path):
            self._rebuild_search_index()

    def _load_system_prompt(self) -> str:
        schema_path = os.path.join(self.schema_dir, "SCHEMA.md")
        profile_path = os.path.join(self.schema_dir, "company_profile.md")
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"SCHEMA.md not found at {schema_path}")
        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"company_profile.md not found at {profile_path}")
        with open(schema_path, "r", encoding="utf-8", errors="replace") as f:
            schema = f.read()
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = f.read()
        return f"{schema}\n\n---\n\n{profile}"

    def _init_llm(self):
        provider = os.getenv("AI_PROVIDER", "openai").lower()
        model = os.getenv("AI_MODEL", "gpt-4o-mini")

        if provider == "openai":
            llm = ChatOpenAI(model=model)
        elif provider == "anthropic":
            llm = ChatAnthropic(model=model)
        elif provider == "google":
            llm = ChatGoogleGenerativeAI(model=model)
        elif provider == "openrouter":
            llm = ChatOpenAI(
                model=model,
                openai_api_base="https://openrouter.ai/api/v1",
                openai_api_key=os.getenv("OPENROUTER_API_KEY")
            )
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")
        return _LLMProxy(llm)

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        match = re.match(r'^---\n(.*?)\n---\n?(.*)', content, re.DOTALL)
        if match:
            try:
                fm = yaml.safe_load(match.group(1))
                if not isinstance(fm, dict):
                    fm = {}
            except yaml.YAMLError:
                fm = {}
            return fm, match.group(2)
        return {}, content

    def _render_frontmatter(self, frontmatter: dict, body: str) -> str:
        fm_str = yaml.dump(frontmatter, default_flow_style=False,
                           allow_unicode=True, sort_keys=False).rstrip()
        return f"---\n{fm_str}\n---\n{body}"

    def _strip_markdown(self, text: str) -> str:
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'[*_`~]', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _rebuild_search_index(self) -> None:
        pages = []
        for rel_path in self.list_pages():
            try:
                content = self.get_page_content(rel_path)
                fm, body = self._parse_frontmatter(content)
                entity_type = rel_path.split("/")[0]
                title = fm.get("name") or fm.get("title") or \
                    rel_path.split("/")[-1].replace("-", " ").replace("_", " ").title()
                tags = fm.get("tags", [])
                if not isinstance(tags, list):
                    tags = []
                pages.append({
                    "path": rel_path,
                    "title": str(title),
                    "entity_type": entity_type,
                    "tags": [str(t) for t in tags],
                    "frontmatter": {k: v for k, v in fm.items() if k != "tags"},
                    "content_preview": self._strip_markdown(body)[:500],
                })
            except Exception:
                continue

        raw_meta = self._load_metadata()
        sources = []
        for filename in self.list_sources():
            m = raw_meta.get(filename, {})
            tags = m.get("tags", [])
            if not isinstance(tags, list):
                tags = []
            sources.append({
                "filename": filename,
                "display_name": filename,
                "tags": [str(t) for t in tags],
                "metadata": {
                    "ingested": m.get("ingested", False),
                    "upload_date": m.get("ingested_at"),
                },
            })

        index = {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "pages": pages,
            "sources": sources,
        }
        import tempfile
        index_path = os.path.join(self.wiki_dir, "search-index.json")
        tmp_fd, tmp_path = tempfile.mkstemp(dir=self.wiki_dir)
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, index_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    async def update_page_tags(self, page_path: str, tags: list[str], _rebuild: bool = True) -> None:
        """Replace the tags list on a wiki page's YAML frontmatter and rebuild index."""
        path = os.path.join(self.wiki_dir, page_path.replace("/", os.sep))
        if not os.path.exists(path):
            raise FileNotFoundError(f"Page not found: {page_path}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        fm, body = self._parse_frontmatter(content)
        fm["tags"] = [str(t).lower().strip() for t in tags]
        new_content = self._render_frontmatter(fm, body)
        async with self._write_lock:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
        if _rebuild:
            self._rebuild_search_index()

    def update_source_tags(self, filename: str, tags: list[str], _rebuild: bool = True) -> None:
        """Replace the tags list on a source's metadata entry and rebuild index."""
        metadata = self._load_metadata()
        entry = metadata.get(filename, {"ingested": False, "ingested_at": None})
        entry["tags"] = [str(t).lower().strip() for t in tags]
        metadata[filename] = entry
        self._save_metadata(metadata)
        if _rebuild:
            self._rebuild_search_index()

    async def _suggest_tags(self, content: str, entity_type: str) -> list[str]:
        """Ask the LLM for 3-5 tags. Returns empty list on any failure."""
        prompt = ChatPromptTemplate.from_messages([
            ("human", (
                "Suggest 3-5 short, lowercase tags for this {entity_type} page. "
                "Return ONLY a JSON array of strings, e.g. [\"tag1\", \"tag2\"]. "
                "Content:\n{content}"
            ))
        ])
        chain = prompt | self.llm
        try:
            response = await chain.ainvoke({
                "entity_type": entity_type,
                "content": content[:2000],
            })
            text = response.content if hasattr(response, "content") else str(response)
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                tags = json.loads(match.group())
                return [str(t).lower().strip() for t in tags if isinstance(t, str)][:5]
        except Exception:
            pass
        return []

    def _load_metadata(self) -> Dict:
        if not os.path.exists(self.metadata_path):
            return {}
        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_metadata(self, metadata: Dict):
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def get_sources_metadata(self) -> Dict:
        """Return metadata for all current sources."""
        metadata = self._load_metadata()
        current_sources = self.list_sources()
        result = {}
        for s in current_sources:
            stored = metadata.get(s, {})
            result[s] = {
                "ingested": stored.get("ingested", False),
                "ingested_at": stored.get("ingested_at", None),
                "tags": stored.get("tags", []),
            }
        return result

    def mark_source_ingested(self, file_name: str, status: bool = True):
        """Mark a source as ingested in the metadata."""
        metadata = self._load_metadata()
        existing = metadata.get(file_name, {})
        if status:
            existing["ingested"] = True
            existing["ingested_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            existing["ingested"] = False
            existing["ingested_at"] = None
        metadata[file_name] = existing
        self._save_metadata(metadata)

    def _get_page_path(self, title: str) -> str:
        # Sanitize title for filename
        safe_title = title.replace("/", "_").replace("\\", "_").replace(" ", "_")
        return os.path.join(self.wiki_dir, f"{safe_title}.md")

    def _write_page(self, title: str, content: str):
        path = self._get_page_path(title)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _append_to_log(self, action: str, details: str):
        log_path = os.path.join(self.wiki_dir, "log.md")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"## [{timestamp}] {action} | {details}\n")

    def get_entity_types(self) -> Dict[str, Dict]:
        """Discover entity types dynamically from _type.yaml files."""
        return discover_entity_types(self.wiki_dir)

    def update_index(self):
        """Regenerate index.md grouped by entity subdirectory (dynamic)."""
        index_path = os.path.join(self.wiki_dir, "index.md")
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        entity_types = self.get_entity_types()
        sections = {}
        for sub in entity_types:
            sub_dir = os.path.join(self.wiki_dir, sub)
            if not os.path.exists(sub_dir):
                continue
            files = sorted(
                f for f in os.listdir(sub_dir)
                if f.endswith(".md") and not f.startswith("_")
            )
            if files:
                sections[sub] = files

        lines = [
            "# Wiki Index — Farago Projects",
            "",
            f"Last updated: {today}",
            "",
            "---",
            "",
        ]

        for sub, type_data in entity_types.items():
            heading = type_data.get("name", sub.capitalize())
            lines.append(f"## {heading}")
            lines.append("")
            if sub in sections:
                for filename in sections[sub]:
                    page_ref = f"{sub}/{filename[:-3]}"  # strip .md
                    lines.append(f"- [[{page_ref}]] | last updated: {today}")
            else:
                lines.append(f"*No {sub} pages yet.*")
            lines.append("")

        with open(index_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    async def _run_ingest_llm(
        self, filename: str, source_content: str, index_content: str, existing_pages: str
    ) -> FaragoIngestionResult:
        """Run the LLM ingest call. Extracted for testability."""
        parser = PydanticOutputParser(pydantic_object=FaragoIngestionResult)
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template("{system_prompt}"),
            HumanMessagePromptTemplate.from_template(INGEST_HUMAN_TEMPLATE),
        ])
        chain = prompt | self.llm | parser
        return await chain.ainvoke({
            "system_prompt": self.system_prompt,
            "index_content": index_content,
            "existing_pages": existing_pages,
            "filename": filename,
            "source_content": source_content,
            "format_instructions": parser.get_format_instructions(),
        })

    async def ingest_source(self, file_name: str):
        """Phase 1: Read file and call LLM (concurrent). Phase 2: Write files (serialized)."""
        file_path = os.path.join(self.sources_dir, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file not found: {file_path}")

        # Read source content
        ext = os.path.splitext(file_name)[1].lower()
        content = ""
        try:
            if ext == ".pdf":
                from langchain_community.document_loaders import PyPDFLoader
                loader = PyPDFLoader(file_path)
                docs = await asyncio.to_thread(loader.load)
                content = "\n\n".join([doc.page_content for doc in docs])
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
        except Exception as e:
            print(f"ERROR: Failed to read {file_name}: {e}")
            self._append_to_log("error", f"Failed to read {file_name}: {e}")
            return

        if not content.strip():
            print(f"WARNING: No content extracted from {file_name}")
            return

        # Load current index
        index_path = os.path.join(self.wiki_dir, "index.md")
        index_content = ""
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                index_content = f.read()

        # Load existing pages that may be updated (all current pages as context)
        existing_pages_str = ""
        for rel_path in self.list_pages():
            full_path = os.path.join(self.wiki_dir, rel_path.replace("/", os.sep))
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    existing_pages_str += f"\n--- {rel_path} ---\n{f.read()}\n"

        # LLM call with retry (max 2 retries)
        result = None
        last_error = None
        for attempt in range(3):
            try:
                ingest_content = content
                if attempt > 0 and last_error:
                    ingest_content = f"{content}\n\n[Previous attempt failed with: {last_error}. Please fix and retry.]"
                result = await self._run_ingest_llm(file_name, ingest_content, index_content, existing_pages_str)
                break
            except Exception as e:
                last_error = str(e)
                print(f"WARNING: Ingest attempt {attempt + 1} failed: {e}")

        if result is None:
            msg = f"Ingest failed after 3 attempts for {file_name}: {last_error}"
            print(f"ERROR: {msg}")
            self._append_to_log("error", msg)
            self.mark_source_ingested(file_name, False)
            return

        # Phase 2: Write files (serialized)
        async with self._write_lock:
            for page in result.pages:
                page_full_path = os.path.join(self.wiki_dir, page.path.replace("/", os.sep))
                os.makedirs(os.path.dirname(page_full_path), exist_ok=True)
                with open(page_full_path, "w", encoding="utf-8") as f:
                    f.write(page.content)

            self.update_index()
            self.mark_source_ingested(file_name, True)
            self._append_to_log("ingest", result.log_entry)

        # Phase 3: Auto-apply AI tags (outside lock — async LLM calls)
        for page in result.pages:
            try:
                entity_type = page.path.split("/")[0]
                tags = await self._suggest_tags(page.content, entity_type)
                if tags:
                    await self.update_page_tags(page.path, tags, _rebuild=False)
            except Exception:
                pass
        try:
            source_tags = await self._suggest_tags(content[:2000], "source")
            if source_tags:
                self.update_source_tags(file_name, source_tags, _rebuild=False)
        except Exception:
            pass
        self._rebuild_search_index()

        return result

    async def _run_query_llm(self, user_query: str, index_content: str, context: str) -> str:
        """Run the answer LLM call. Extracted for testability."""
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template("{system_prompt}"),
            HumanMessagePromptTemplate.from_template(ANSWER_HUMAN_TEMPLATE),
        ])
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "system_prompt": self.system_prompt,
            "context": context,
            "query": user_query,
        })
        return response.content

    async def query(self, user_query: str) -> str:
        index_path = os.path.join(self.wiki_dir, "index.md")
        if not os.path.exists(index_path):
            return "No wiki content available yet. Please ingest some sources first."

        with open(index_path, "r", encoding="utf-8") as f:
            index_content = f.read()

        # Step 1: Find relevant pages using the LLM
        relevance_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template("{system_prompt}"),
            HumanMessagePromptTemplate.from_template(RELEVANCE_HUMAN_TEMPLATE),
        ])
        relevance_chain = relevance_prompt | self.llm
        relevance_resp = await relevance_chain.ainvoke({
            "system_prompt": self.system_prompt,
            "index": index_content,
            "query": user_query,
        })

        raw_content = relevance_resp.content
        page_names_str = raw_content if isinstance(raw_content, str) else ""
        page_names_str = page_names_str.strip()

        if page_names_str.lower() == "none":
            return "I couldn't find relevant information in the wiki to answer your question."

        page_paths = [p.strip() for p in page_names_str.split(",") if p.strip()]

        # If LLM returned no usable paths, fall back to all pages listed in the index
        if not page_paths:
            wikilink_pattern_idx = re.compile(r"\[\[([^\]]+)\]\]")
            page_paths = [
                f"{m}.md" for m in wikilink_pattern_idx.findall(index_content)
            ]

        # Step 2: Read relevant pages
        context = ""
        for path in page_paths:
            clean_path = path.replace("[[", "").replace("]]", "").strip()
            if not clean_path.endswith(".md"):
                clean_path = f"{clean_path}.md"
            full_path = os.path.join(self.wiki_dir, clean_path.replace("/", os.sep))
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    context += f"\n--- {clean_path} ---\n{f.read()}\n"

        if not context:
            return "I found relevant page names but the pages appear to be missing."

        # Step 3: Synthesize answer
        answer = await self._run_query_llm(user_query, index_content, context)
        self._append_to_log("query", f"Answered: {user_query}")
        return answer

    async def _run_lint_llm(self, wiki_content: str) -> LintReport:
        """Run the LLM lint call. Extracted for testability."""
        parser = PydanticOutputParser(pydantic_object=LintReport)
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template("{system_prompt}"),
            HumanMessagePromptTemplate.from_template(LINT_HUMAN_TEMPLATE),
        ])
        chain = prompt | self.llm | parser
        return await chain.ainvoke({
            "system_prompt": self.system_prompt,
            "wiki_content": wiki_content,
            "format_instructions": parser.get_format_instructions(),
        })

    async def lint(self) -> LintReport:
        """LLM-powered wiki lint. Read-only — returns a LintReport, writes only to log.md."""
        # Gather all wiki content
        wiki_content = ""
        for rel_path in self.list_pages():
            full_path = os.path.join(self.wiki_dir, rel_path.replace("/", os.sep))
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    wiki_content += f"\n=== {rel_path} ===\n{f.read()}\n"

        if not wiki_content.strip():
            return LintReport(findings=[], summary="Wiki is empty — nothing to lint.")

        report = await self._run_lint_llm(wiki_content)
        self._append_to_log("lint", report.summary)
        return report

    async def create_new_page(self, entity_type: str = "clients") -> str:
        """Create a new Untitled page in the given entity subdirectory.
        Returns the relative path, e.g. 'clients/Untitled.md'.
        """
        entity_types = self.get_entity_types()
        if entity_type not in entity_types:
            raise ValueError(f"Invalid entity type: {entity_type!r}. Must be one of {list(entity_types.keys())}")

        async with self._write_lock:
            sub_dir = os.path.join(self.wiki_dir, entity_type)
            os.makedirs(sub_dir, exist_ok=True)

            base_name = "Untitled"
            rel_path = f"{entity_type}/{base_name}.md"
            count = 1
            while os.path.exists(os.path.join(self.wiki_dir, rel_path.replace("/", os.sep))):
                rel_path = f"{entity_type}/{base_name}_{count}.md"
                count += 1

            singular = entity_types[entity_type].get("singular", entity_type.rstrip("s"))
            content = f"---\ntype: {singular}\nname: \n---\n\n# Untitled\n\nNew page content here.\n"
            with open(os.path.join(self.wiki_dir, rel_path.replace("/", os.sep)), "w", encoding="utf-8") as f:
                f.write(content)

            self.update_index()
            self._append_to_log("create", f"Created {rel_path}")
        self._rebuild_search_index()
        return rel_path

    def rebuild_schema(self):
        """Regenerate SCHEMA.md from SCHEMA_TEMPLATE.md and _type.yaml files."""
        template_path = os.path.join(self.schema_dir, "SCHEMA_TEMPLATE.md")
        if not os.path.exists(template_path):
            return  # No template yet, skip
        schema_content = build_schema_md(self.wiki_dir, template_path)
        schema_path = os.path.join(self.schema_dir, "SCHEMA.md")
        with open(schema_path, "w", encoding="utf-8") as f:
            f.write(schema_content)
        # Reload system prompt so next LLM call sees updated schema
        self.system_prompt = self._load_system_prompt()

    def _rewrite_wikilinks(self, old_folder: str, new_folder: str):
        """Rewrite all [[old_folder/...]] wikilinks to [[new_folder/...]] across all pages."""
        pattern = re.compile(r"\[\[" + re.escape(old_folder) + r"/([^\]]+)\]\]")
        replacement = f"[[{new_folder}/\\1]]"
        for root, _dirs, files in os.walk(self.wiki_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                new_content = pattern.sub(replacement, content)
                if new_content != content:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(new_content)

    def _rewrite_wikilinks_specific(self, old_ref: str, new_ref: str):
        """Rewrite a specific [[old_ref]] wikilink to [[new_ref]] across all pages."""
        for root, _dirs, files in os.walk(self.wiki_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                new_content = content.replace(f"[[{old_ref}]]", f"[[{new_ref}]]")
                if new_content != content:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(new_content)

    async def create_folder(self, folder_name: str, display_name: str, description: str = ""):
        """Create a new entity folder with a _type.yaml file."""
        folder_path = os.path.join(self.wiki_dir, folder_name)
        if os.path.exists(folder_path):
            raise ValueError(f"Folder '{folder_name}' already exists")

        async with self._write_lock:
            os.makedirs(folder_path)
            type_data = {
                "name": display_name,
                "description": description,
                "singular": folder_name.rstrip("s"),
                "fields": [
                    {"name": "type", "type": "string", "default": folder_name.rstrip("s")},
                    {"name": "name", "type": "string", "required": True},
                ],
                "sections": ["Overview", "Notes"],
            }
            with open(os.path.join(folder_path, "_type.yaml"), "w", encoding="utf-8") as f:
                yaml.dump(type_data, f, default_flow_style=False, sort_keys=False)

            self.rebuild_schema()
            self.update_index()
            self._append_to_log("create_folder", f"Created folder '{folder_name}' ({display_name})")

    async def delete_folder(self, folder_name: str):
        """Delete an empty entity folder."""
        folder_path = os.path.join(self.wiki_dir, folder_name)
        if not os.path.exists(folder_path):
            raise ValueError(f"Folder '{folder_name}' does not exist")

        # Check for pages (anything except _type.yaml and .gitkeep)
        contents = [f for f in os.listdir(folder_path) if f not in ("_type.yaml", ".gitkeep")]
        if contents:
            raise ValueError(f"Folder '{folder_name}' is not empty — archive or move pages first")

        async with self._write_lock:
            shutil.rmtree(folder_path)
            self.rebuild_schema()
            self.update_index()
            self._append_to_log("delete_folder", f"Deleted folder '{folder_name}'")

    async def rename_folder(self, old_name: str, new_name: str):
        """Rename an entity folder and update all wikilinks across the wiki."""
        old_path = os.path.join(self.wiki_dir, old_name)
        new_path = os.path.join(self.wiki_dir, new_name)
        if not os.path.exists(old_path):
            raise ValueError(f"Folder '{old_name}' does not exist")
        if os.path.exists(new_path):
            raise ValueError(f"Folder '{new_name}' already exists")

        async with self._write_lock:
            os.rename(old_path, new_path)
            self._rewrite_wikilinks(old_name, new_name)
            self.rebuild_schema()
            self.update_index()
            self._append_to_log("rename_folder", f"Renamed '{old_name}' → '{new_name}'")

    async def move_page(self, page_path: str, target_folder: str) -> str:
        """Move a wiki page to a different entity folder. Updates wikilinks.
        Returns the new page path.
        """
        target_dir = os.path.join(self.wiki_dir, target_folder)
        if not os.path.exists(target_dir) or not os.path.exists(os.path.join(target_dir, "_type.yaml")):
            raise ValueError(f"Target folder '{target_folder}' does not exist or has no _type.yaml")

        src = os.path.join(self.wiki_dir, page_path.replace("/", os.sep))
        if not os.path.exists(src):
            raise FileNotFoundError(f"Page not found: {page_path}")

        filename = os.path.basename(page_path)
        new_rel_path = f"{target_folder}/{filename}"
        dest = os.path.join(self.wiki_dir, new_rel_path.replace("/", os.sep))

        old_ref = page_path[:-3] if page_path.endswith(".md") else page_path
        new_ref = new_rel_path[:-3] if new_rel_path.endswith(".md") else new_rel_path

        async with self._write_lock:
            shutil.move(src, dest)
            self._rewrite_wikilinks_specific(old_ref, new_ref)
            self.update_index()
            self._append_to_log("move", f"Moved {page_path} → {new_rel_path}")

        return new_rel_path

    async def archive_page(self, page_path: str):
        """Move a wiki page to the archive."""
        src = os.path.join(self.wiki_dir, page_path.replace("/", os.sep))
        dest = os.path.join(self.archive_wiki_dir, page_path.replace("/", os.sep))
        async with self._write_lock:
            if not os.path.exists(src):
                raise FileNotFoundError(f"Page not found: {page_path}")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.exists(dest):
                base, ext = os.path.splitext(dest)
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                dest = f"{base}_{timestamp}{ext}"
            shutil.move(src, dest)
            self.update_index()
            self._append_to_log("archive", f"Archived {page_path}")
        self._rebuild_search_index()

    async def archive_source(self, filename: str):
        """Move a source file to the archive."""
        src = os.path.join(self.sources_dir, filename)
        dest = os.path.join(self.archive_sources_dir, filename)
        
        async with self._write_lock:
            if not os.path.exists(src):
                raise FileNotFoundError(f"Source not found: {filename}")
            
            # Handle collision in archive
            if os.path.exists(dest):
                base, ext = os.path.splitext(filename)
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                dest = os.path.join(self.archive_sources_dir, f"{base}_{timestamp}{ext}")
                
            shutil.move(src, dest)
            self._append_to_log("archive", f"Archived source {filename}")

    async def restore_page(self, filename: str):
        """Move an archived wiki page back to the main wiki directory."""
        src = os.path.join(self.archive_wiki_dir, filename)
        dest = os.path.join(self.wiki_dir, filename)
        
        async with self._write_lock:
            if not os.path.exists(src):
                raise FileNotFoundError(f"Archived page not found: {filename}")

            # Handle collision in wiki_dir
            if os.path.exists(dest):
                base, ext = os.path.splitext(filename)
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                dest = os.path.join(self.wiki_dir, f"{base}_{timestamp}{ext}")

            shutil.move(src, dest)
            self.update_index()
            self._append_to_log("restore", f"Restored {filename}")
        self._rebuild_search_index()

    async def restore_source(self, filename: str):
        """Move an archived source file back to the main sources directory."""
        src = os.path.join(self.archive_sources_dir, filename)
        dest = os.path.join(self.sources_dir, filename)
        
        async with self._write_lock:
            if not os.path.exists(src):
                raise FileNotFoundError(f"Archived source not found: {filename}")
            
            # Handle collision in sources_dir
            if os.path.exists(dest):
                base, ext = os.path.splitext(filename)
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                dest = os.path.join(self.sources_dir, f"{base}_{timestamp}{ext}")
                
            shutil.move(src, dest)
            self._append_to_log("restore", f"Restored source {filename}")

    async def delete_archived_page(self, filename: str):
        """Permanently delete a wiki page from the archive."""
        path = os.path.join(self.archive_wiki_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Archived page not found: {filename}")
        os.remove(path)
        self._append_to_log("delete_permanent", f"Permanently deleted archived {filename}")

    async def delete_archived_source(self, filename: str):
        """Permanently delete a source file from the archive."""
        path = os.path.join(self.archive_sources_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Archived source not found: {filename}")
        os.remove(path)
        self._append_to_log("delete_permanent", f"Permanently deleted archived source {filename}")

    def list_archived_pages(self) -> List[str]:
        """List all markdown files in the archive wiki directory (recursive)."""
        pages = []
        for root, _dirs, files in os.walk(self.archive_wiki_dir):
            for f in files:
                if f.endswith(".md"):
                    rel = os.path.relpath(os.path.join(root, f), self.archive_wiki_dir)
                    pages.append(rel.replace(os.sep, "/"))
        return pages

    def list_archived_sources(self) -> List[str]:
        """List all files in the archive sources directory."""
        return [f for f in os.listdir(self.archive_sources_dir) if os.path.isfile(os.path.join(self.archive_sources_dir, f)) and not f.startswith(".")]

    def get_archived_page_content(self, filename: str) -> str:
        """Read and return the content of an archived wiki page."""
        path = os.path.join(self.archive_wiki_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Archived page not found: {filename}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    async def get_archived_source_content(self, filename: str) -> str:
        """Read and return the content of an archived source file."""
        # Use existing logic by passing the archive path
        old_sources_dir = self.sources_dir
        self.sources_dir = self.archive_sources_dir
        try:
            return await self.get_source_content(filename)
        finally:
            self.sources_dir = old_sources_dir

    def list_pages(self) -> List[str]:
        """List all entity pages as relative paths (e.g. 'clients/louis-vuitton.md').
        Excludes index.md and log.md."""
        pages = []
        for root, _dirs, files in os.walk(self.wiki_dir):
            for filename in sorted(files):
                if not filename.endswith(".md"):
                    continue
                rel_path = os.path.relpath(os.path.join(root, filename), self.wiki_dir)
                # Normalize to forward slashes
                rel_path = rel_path.replace(os.sep, "/")
                if rel_path in ("index.md", "log.md"):
                    continue
                pages.append(rel_path)
        return pages

    def list_sources(self) -> List[str]:
        """List all files in the sources directory."""
        return [f for f in os.listdir(self.sources_dir) if os.path.isfile(os.path.join(self.sources_dir, f)) and f != ".gitkeep" and not f.startswith(".")]

    def get_page_content(self, page_path: str) -> str:
        """Read and return the content of a wiki page."""
        path = os.path.join(self.wiki_dir, page_path.replace("/", os.sep))
        if not os.path.exists(path):
            raise FileNotFoundError(f"Page not found: {page_path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    async def get_source_content(self, filename: str) -> str:
        """Read and return the content of a source file."""
        path = os.path.join(self.sources_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Source file not found: {filename}")
        
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            try:
                from langchain_community.document_loaders import PyPDFLoader
                loader = PyPDFLoader(path)
                docs = await asyncio.to_thread(loader.load)
                return "\n\n".join([doc.page_content for doc in docs])
            except Exception as e:
                return f"Error extracting PDF content: {str(e)}"
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Fallback for non-utf8 files
            with open(path, "r", encoding="latin-1") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def get_backlinks(self, page_path: str) -> List[str]:
        """Find all pages that contain a wikilink to page_path.
        page_path is a relative path like 'clients/louis-vuitton.md'.
        Searches for [[clients/louis-vuitton]] style links.
        """
        # Build the link target string (without .md)
        target_ref = page_path[:-3] if page_path.endswith(".md") else page_path

        wiki_link_pattern = re.compile(r"\[\[(.*?)\]\]")
        backlinks = []

        for root, _dirs, files in os.walk(self.wiki_dir):
            for filename in sorted(files):
                if not filename.endswith(".md"):
                    continue
                rel = os.path.relpath(os.path.join(root, filename), self.wiki_dir).replace(os.sep, "/")
                if rel == page_path or rel in ("index.md", "log.md"):
                    continue
                full_path = os.path.join(root, filename)
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                for link in wiki_link_pattern.findall(content):
                    if link == target_ref:
                        backlinks.append(rel)
                        break

        return sorted(backlinks)

    async def save_page_content(self, page_path: str, content: str) -> list[str]:
        """
        Save content to a wiki page and log the action.
        Returns AI-suggested tags not already present on the page.
        """
        path = os.path.join(self.wiki_dir, page_path.replace("/", os.sep))
        async with self._write_lock:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.update_index()
            self._append_to_log("edit", f"Updated {page_path}")
        self._rebuild_search_index()

        entity_type = page_path.split("/")[0]
        fm, _ = self._parse_frontmatter(content)
        existing_tags = [str(t).lower() for t in fm.get("tags", []) if isinstance(t, str)]
        all_suggestions = await self._suggest_tags(content, entity_type)
        return [t for t in all_suggestions if t not in existing_tags]

