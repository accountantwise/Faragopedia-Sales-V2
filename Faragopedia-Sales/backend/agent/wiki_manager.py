import os
import asyncio
import datetime
import re
import json
import shutil
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

class Entity(BaseModel):
    name: str = Field(description="Name of the entity or concept")
    summary: str = Field(description="One-sentence summary of the entity or concept")
    details: str = Field(description="Detailed information about the entity or concept")

class IngestionResult(BaseModel):
    source_summary: str = Field(description="A concise summary of the source document")
    entities: List[Entity] = Field(description="Key entities and concepts extracted from the document")

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

    def _load_system_prompt(self) -> str:
        schema_path = os.path.join(self.schema_dir, "SCHEMA.md")
        profile_path = os.path.join(self.schema_dir, "company_profile.md")
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"SCHEMA.md not found at {schema_path}")
        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"company_profile.md not found at {profile_path}")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = f.read()
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = f.read()
        return f"{schema}\n\n---\n\n{profile}"

    def _init_llm(self):
        provider = os.getenv("AI_PROVIDER", "openai").lower()
        model = os.getenv("AI_MODEL", "gpt-4o-mini")
        
        if provider == "openai":
            return ChatOpenAI(model=model)
        elif provider == "anthropic":
            return ChatAnthropic(model=model)
        elif provider == "google":
            return ChatGoogleGenerativeAI(model=model)
        elif provider == "openrouter":
            return ChatOpenAI(
                model=model,
                openai_api_base="https://openrouter.ai/api/v1",
                openai_api_key=os.getenv("OPENROUTER_API_KEY")
            )
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

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
        # Filter metadata to only include current sources and add defaults
        result = {}
        for s in current_sources:
            result[s] = metadata.get(s, {"ingested": False, "ingested_at": None})
        return result

    def mark_source_ingested(self, file_name: str, status: bool = True):
        """Mark a source as ingested in the metadata."""
        metadata = self._load_metadata()
        if status:
            metadata[file_name] = {
                "ingested": True,
                "ingested_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            metadata[file_name] = {"ingested": False, "ingested_at": None}
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

    def update_index(self):
        index_path = os.path.join(self.wiki_dir, "index.md")
        # List all markdown files except index and log
        files = [f for f in os.listdir(self.wiki_dir) if f.endswith(".md") and f not in ["index.md", "log.md"]]
        
        index_content = "# Wiki Index\n\n"
        index_content += "A content-oriented catalog of all pages in the wiki.\n\n"
        for f_name in files:
            title = f_name[:-3]
            # Simple heuristic: we could read the first few lines for a summary,
            # but for now, we'll just link it.
            index_content += f"- [[{title}]]: Wiki page for {title}\n"
        
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_content)

    async def ingest_source(self, file_name: str):
        # Phase 1 — Read and LLM inference (runs concurrently across uploads)
        file_path = os.path.join(self.sources_dir, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file not found: {file_path}")

        ext = os.path.splitext(file_name)[1].lower()
        content = ""

        try:
            if ext == ".pdf":
                from langchain_community.document_loaders import PyPDFLoader
                loader = PyPDFLoader(file_path)
                docs = await asyncio.to_thread(loader.load)
                content = "\n\n".join([doc.page_content for doc in docs])
            elif ext in [".txt", ".md"]:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                # Basic fallback: attempt text read for everything else
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
        except Exception as e:
            # For background tasks, we log but don't want to crash the whole task loop
            print(f"ERROR: Failed to read file {file_name}: {str(e)}")
            self._append_to_log("error", f"Failed to read {file_name}: {str(e)}")
            return

        if not content.strip():
            print(f"WARNING: No content extracted from {file_name}")
            return

        parser = PydanticOutputParser(pydantic_object=IngestionResult)

        prompt = PromptTemplate(
            template="Extract key information from the following document.\n{format_instructions}\nDocument:\n{content}\n",
            input_variables=["content"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        chain = prompt | self.llm | parser
        result = await chain.ainvoke({"content": content})

        # Phase 2 — File writes (serialized: one ingestion at a time)
        async with self._write_lock:
            # 1. Write Source Summary Page
            source_title = f"Summary_{file_name}"
            source_content = f"# Summary of {file_name}\n\n{result.source_summary}\n\n## Extracted Entities\n"
            for entity in result.entities:
                source_content += f"- [[{entity.name}]]\n"
            self._write_page(source_title, source_content)

            # 2. Update/Create Entity Pages
            for entity in result.entities:
                entity_path = self._get_page_path(entity.name)
                if os.path.exists(entity_path):
                    with open(entity_path, "a", encoding="utf-8") as f:
                        f.write(f"\n\n### Updated from {file_name}\n\n{entity.details}\n")
                else:
                    self._write_page(entity.name, f"# {entity.name}\n\n{entity.summary}\n\n## Details\n\n{entity.details}\n")

            # 3. Maintain wiki structure
            self.update_index()
            self.mark_source_ingested(file_name, True)
            self._append_to_log("ingest", f"Processed {file_name}")

        return result

    async def query(self, user_query: str):
        # 1. Read index to find relevant pages (simplified version)
        index_path = os.path.join(self.wiki_dir, "index.md")
        if not os.path.exists(index_path):
            return "No wiki content available yet. Please ingest some sources first."

        with open(index_path, "r", encoding="utf-8") as f:
            index_content = f.read()

        # 2. Ask LLM which pages are relevant
        relevance_prompt = PromptTemplate(
            template="Given the following wiki index and a user query, list the names of the 3 most relevant wiki pages to answer the query. Return ONLY a comma-separated list of page names. If no pages are relevant, return 'None'.\n\nIndex:\n{index}\n\nQuery: {query}\n",
            input_variables=["index", "query"]
        )
        
        relevance_chain = relevance_prompt | self.llm
        relevant_pages_resp = await relevance_chain.ainvoke({"index": index_content, "query": user_query})
        
        page_names_str = relevant_pages_resp.content.strip()
        if page_names_str.lower() == "none":
            return "I couldn't find any relevant information in the wiki to answer your question."
            
        page_names = [p.strip() for p in page_names_str.split(",")]

        # 3. Read relevant pages
        context = ""
        for name in page_names:
            # Clean up potential markdown links from LLM output
            clean_name = name.replace("[[", "").replace("]]", "")
            path = self._get_page_path(clean_name)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    context += f"\n--- Page: {clean_name} ---\n{f.read()}\n"

        if not context:
            return "I found some relevant page names, but the pages themselves seem to be missing."

        # 4. Synthesize answer
        answer_prompt = PromptTemplate(
            template="You are a wiki assistant. Answer the user query using the provided context from the wiki. Cite your sources using [[Page Name]] syntax. If the context doesn't contain the answer, say you don't know.\n\nContext:\n{context}\n\nQuery: {query}\n",
            input_variables=["context", "query"]
        )
        
        answer_chain = answer_prompt | self.llm
        answer = await answer_chain.ainvoke({"context": context, "query": user_query})
        
        self._append_to_log("query", f"Answered: {user_query}")
        return answer.content

    async def create_new_page(self) -> str:
        """Create a new 'Untitled.md' page and return its filename.
        Handles duplicates by adding a numeric suffix.
        """
        async with self._write_lock:
            base_name = "Untitled"
            filename = f"{base_name}.md"
            count = 1
            while os.path.exists(os.path.join(self.wiki_dir, filename)):
                filename = f"{base_name}_{count}.md"
                count += 1
            
            with open(os.path.join(self.wiki_dir, filename), "w", encoding="utf-8") as f:
                f.write(f"# {filename[:-3]}\n\nNew wiki page content here.")
            
            self.update_index()
            self._append_to_log("create", f"Created {filename}")
            return filename

    async def archive_page(self, filename: str):
        """Move a wiki page to the archive."""
        src = os.path.join(self.wiki_dir, filename)
        dest = os.path.join(self.archive_wiki_dir, filename)
        
        async with self._write_lock:
            if not os.path.exists(src):
                raise FileNotFoundError(f"Page not found: {filename}")
            
            # Handle collision in archive
            if os.path.exists(dest):
                base, ext = os.path.splitext(filename)
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                dest = os.path.join(self.archive_wiki_dir, f"{base}_{timestamp}{ext}")
                
            shutil.move(src, dest)
            self.update_index()
            self._append_to_log("archive", f"Archived {filename}")

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
        """List all markdown files in the archive wiki directory."""
        return [f for f in os.listdir(self.archive_wiki_dir) if f.endswith(".md")]

    def list_archived_sources(self) -> List[str]:
        """List all files in the archive sources directory."""
        return [f for f in os.listdir(self.archive_sources_dir) if os.path.isfile(os.path.join(self.archive_sources_dir, f))]

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
        """List all markdown files in the wiki directory, excluding log.md and index.md."""
        return [f for f in os.listdir(self.wiki_dir) if f.endswith(".md") and f not in ["log.md", "index.md"]]

    def list_sources(self) -> List[str]:
        """List all files in the sources directory."""
        return [f for f in os.listdir(self.sources_dir) if os.path.isfile(os.path.join(self.sources_dir, f)) and f != ".gitkeep"]

    def get_page_content(self, filename: str) -> str:
        """Read and return the content of a wiki page."""
        path = os.path.join(self.wiki_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Page not found: {filename}")
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

    def get_backlinks(self, filename: str) -> List[str]:
        """
        Find all pages that link to the given filename.
        """
        target_title = filename[:-3] if filename.endswith(".md") else filename
        backlinks = []
        
        all_files = [f for f in os.listdir(self.wiki_dir) if f.endswith(".md")]
        
        # Patterns for links
        wiki_link_pattern = re.compile(r"\[\[(.*?)\]\]")
        md_link_pattern = re.compile(r"\[.*?\]\((.*?)\.md\)")
        
        for f in all_files:
            if f == filename:
                continue
                
            content = self.get_page_content(f)
            
            # Check wiki links [[...]]
            found = False
            wiki_links = wiki_link_pattern.findall(content)
            for link in wiki_links:
                safe_link = link.replace("/", "_").replace("\\", "_").replace(" ", "_")
                if safe_link == target_title:
                    backlinks.append(f)
                    found = True
                    break
            
            if found:
                continue
                
            # Check markdown links [...](...)
            md_links = md_link_pattern.findall(content)
            for link in md_links:
                safe_link = link.replace("/", "_").replace("\\", "_").replace(" ", "_")
                if safe_link == target_title:
                    backlinks.append(f)
                    break
                    
        return sorted(backlinks)

    async def save_page_content(self, filename: str, content: str):
        """
        Save content to a wiki page and log the action.
        """
        path = os.path.join(self.wiki_dir, filename)
        
        async with self._write_lock:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            
            # Update index just in case this is a new file (though usually it's an edit)
            self.update_index()
            self._append_to_log("edit", f"Updated {filename}")

    def health_check(self) -> Dict:
        """
        Scan wiki for orphan pages and missing pages.
        Returns a summary of issues found.
        """
        all_files = [f for f in os.listdir(self.wiki_dir) if f.endswith(".md")]
        pages_to_check = [f for f in all_files if f not in ["log.md"]]
        
        # 1. Find all links in all pages
        all_links = set()
        index_links = set()
        
        # Pattern for [[Page Name]]
        wiki_link_pattern = re.compile(r"\[\[(.*?)\]\]")
        # Pattern for [Link Text](Page_Name.md)
        md_link_pattern = re.compile(r"\[.*?\]\((.*?)\.md\)")
        
        for filename in all_files:
            content = self.get_page_content(filename)
            # Find [[...]] links
            wiki_links = wiki_link_pattern.findall(content)
            for link in wiki_links:
                # Sanitize the link to match how files are named
                safe_link = link.replace("/", "_").replace("\\", "_").replace(" ", "_")
                all_links.add(safe_link)
                if filename == "index.md":
                    index_links.add(safe_link)
            
            # Find [...](...) links
            md_links = md_link_pattern.findall(content)
            for link in md_links:
                # md links often already have underscores, but let's be safe
                safe_link = link.replace("/", "_").replace("\\", "_").replace(" ", "_")
                all_links.add(safe_link)
                if filename == "index.md":
                    index_links.add(safe_link)
        
        # 2. Check for missing pages (listed in any page but file doesn't exist)
        missing_pages = []
        for link in all_links:
            page_path = os.path.join(self.wiki_dir, f"{link}.md")
            if not os.path.exists(page_path):
                missing_pages.append(link)
        
        # 3. Check for orphan pages (file exists but no inbound links from ANY other page)
        orphan_pages = []
        for filename in pages_to_check:
            if filename == "index.md":
                continue
            
            title = filename[:-3] # Remove .md
            
            # Check if title is linked from any other file
            is_linked = False
            for other_file in all_files:
                if other_file == filename:
                    continue
                other_content = self.get_page_content(other_file)
                # Check for both formats
                if f"[[{title}]]" in other_content or f"({title}.md)" in other_content:
                    is_linked = True
                    break
            
            if not is_linked:
                orphan_pages.append(filename)
                
        return {
            "total_pages": len(pages_to_check),
            "orphan_pages": orphan_pages,
            "missing_pages": sorted(list(set(missing_pages))), # Unique and sorted
            "status": "healthy" if not orphan_pages and not missing_pages else "issues_found"
        }
