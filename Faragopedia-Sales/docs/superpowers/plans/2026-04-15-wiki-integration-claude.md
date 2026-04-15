# Wiki-Concept Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the Farago Projects wiki schema into Faragopedia-Sales so that all LLM-driven ingest, query, and lint operations produce schema-compliant, entity-typed wiki pages in a subdirectory structure, accessible via the web UI.

**Architecture:** Every LLM call receives `SCHEMA.md` + `company_profile.md` as a fixed system prompt (baked into the Docker image at `backend/schema/`). A new `FaragoIngestionResult` Pydantic model replaces the generic `Entity`/`IngestionResult` — the LLM returns structured `WikiPage` objects with explicit subdirectory paths (`clients/louis-vuitton.md`). The wiki directory adopts a one-level-deep subdirectory structure (`clients/`, `prospects/`, `contacts/`, `photographers/`, `productions/`). A new LLM-powered `lint()` replaces the structural `health_check()`. The frontend gains a collapsible tree sidebar and a `LintView`.

**Tech Stack:** Python/FastAPI, LangChain (`ChatPromptTemplate`, `PydanticOutputParser`), Pydantic v2, React/TypeScript, Tailwind CSS, Docker.

**Design Spec:** `docs/superpowers/specs/2026-04-15-wiki-integration-design.md`

---

## File Map

### Created
- `backend/schema/SCHEMA.md` — Farago wiki operating manual (baked into image)
- `backend/schema/company_profile.md` — company context (baked into image)
- `wiki/clients/.gitkeep` — ensure empty subdirs are tracked
- `wiki/prospects/.gitkeep`
- `wiki/contacts/.gitkeep`
- `wiki/photographers/.gitkeep`
- `wiki/productions/.gitkeep`
- `frontend/src/components/LintView.tsx` — new lint results view

### Modified
- `backend/agent/wiki_manager.py` — new models, schema loading, recursive traversal, ingest/query/lint redesign
- `backend/api/routes.py` — new grouped pages endpoint, lint endpoint, path security, remove health endpoint
- `backend/Dockerfile` — add `COPY schema/ /app/schema/`
- `frontend/src/App.tsx` — add LintView, remove health check UI
- `frontend/src/components/Sidebar.tsx` — replace Health Check with Lint nav item
- `frontend/src/components/WikiView.tsx` — collapsible tree, path-aware routing, entity-type new-page menu

### Deleted
- `backend/tests/test_wiki_manager_health.py` — tests `health_check()` which is removed

### Tests Updated
- `backend/tests/test_wiki_manager.py` — replace old model imports and ingest tests
- `backend/tests/test_km_features.py` — update for subdirectory paths

---

## Task 1: Data Migration & Schema Files

**Files:**
- Create: `backend/schema/SCHEMA.md`
- Create: `backend/schema/company_profile.md`
- Create: `wiki/clients/.gitkeep`, `wiki/prospects/.gitkeep`, `wiki/contacts/.gitkeep`, `wiki/photographers/.gitkeep`, `wiki/productions/.gitkeep`
- Modify: `backend/Dockerfile`

- [ ] **Step 1: Create backend/schema/ directory and copy files**

```bash
mkdir -p backend/schema
cp ../Wiki-Concept/SCHEMA.md backend/schema/SCHEMA.md
cp ../Wiki-Concept/company_profile.md backend/schema/company_profile.md
```

Verify: `ls backend/schema/` should show `SCHEMA.md` and `company_profile.md`.

- [ ] **Step 2: Delete all existing wiki pages (clean slate)**

```bash
# From the repo root
find wiki/ -name "*.md" -not -name "index.md" -not -name "log.md" -delete
```

Verify: `ls wiki/` should show only `index.md` and `log.md`.

- [ ] **Step 3: Create wiki subdirectory structure**

```bash
mkdir -p wiki/clients wiki/prospects wiki/contacts wiki/photographers wiki/productions
touch wiki/clients/.gitkeep wiki/prospects/.gitkeep wiki/contacts/.gitkeep wiki/photographers/.gitkeep wiki/productions/.gitkeep
```

- [ ] **Step 4: Reset index.md to Farago schema format**

Overwrite `wiki/index.md` with:

```markdown
# Wiki Index — Farago Projects

Last updated: 2026-04-15

This is the master catalog of all wiki pages. Updated on every ingest operation.

---

## Clients

*No client pages yet.*

---

## Prospects

*No prospect pages yet.*

---

## Contacts

*No contact pages yet.*

---

## Photographers

*No photographer pages yet.*

---

## Productions

*No production pages yet.*
```

- [ ] **Step 5: Reset log.md**

Overwrite `wiki/log.md` with:

```markdown
# Wiki Log — Farago Projects

Append-only chronological record of all wiki operations.

**Format:** `## [YYYY-MM-DD] operation | title`

---

## [2026-04-15] init | Wiki migrated to Farago schema

Existing pages deleted. Subdirectory structure created. SCHEMA.md and company_profile.md baked into backend image.
```

- [ ] **Step 6: Update Dockerfile to copy schema files**

Edit `backend/Dockerfile`. After `COPY . .`, add:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY schema/ /app/schema/

EXPOSE 8300

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8300"]
```

- [ ] **Step 7: Commit**

```bash
git add backend/schema/ wiki/ backend/Dockerfile
git commit -m "chore: migrate wiki to Farago schema structure and bake schema files into image"
```

---

## Task 2: New Pydantic Models + Schema Loading

**Files:**
- Modify: `backend/agent/wiki_manager.py`
- Modify: `backend/tests/test_wiki_manager.py`

- [ ] **Step 1: Write the failing tests**

At the top of `backend/tests/test_wiki_manager.py`, replace the existing imports with:

```python
import asyncio
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from agent.wiki_manager import (
    WikiManager, WikiPage, FaragoIngestionResult, LintFinding, LintReport
)
```

Also delete these tests now (they reference the old `Entity`/`IngestionResult` models that no longer exist after Step 3):
- `test_wiki_manager_ingest_source_cycle`
- `test_concurrent_ingestion_no_corruption`
- `test_wiki_manager_query`
- `test_create_new_page`

Add these new tests (keep all other existing tests — archive/restore/metadata — for now):

```python
@pytest.fixture
def schema_dirs(tmp_path):
    """Create fake schema files for tests."""
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Test Schema\nYou are the Farago wiki agent.")
    (schema_dir / "company_profile.md").write_text("# Farago Projects\nA creative production house.")
    return str(schema_dir)


@pytest.fixture
def temp_dirs_with_schema(tmp_path, schema_dirs):
    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()
    return str(sources), str(wiki), schema_dirs


def test_wiki_page_model():
    page = WikiPage(
        path="clients/louis-vuitton.md",
        content="---\ntype: client\nname: Louis Vuitton\n---\n# Louis Vuitton\n",
        action="create"
    )
    assert page.path == "clients/louis-vuitton.md"
    assert page.action == "create"
    assert "Louis Vuitton" in page.content


def test_wiki_page_action_values():
    create_page = WikiPage(path="clients/foo.md", content="# Foo", action="create")
    update_page = WikiPage(path="clients/foo.md", content="# Foo updated", action="update")
    assert create_page.action == "create"
    assert update_page.action == "update"


def test_farago_ingestion_result_model():
    result = FaragoIngestionResult(
        pages=[
            WikiPage(path="clients/louis-vuitton.md", content="# LV", action="create"),
            WikiPage(path="contacts/jane-doe.md", content="# Jane", action="create"),
        ],
        log_entry="Ingested LV press release. Created 2 pages: clients/louis-vuitton, contacts/jane-doe."
    )
    assert len(result.pages) == 2
    assert result.pages[0].path == "clients/louis-vuitton.md"
    assert "jane-doe" in result.log_entry


def test_lint_finding_model():
    finding = LintFinding(
        severity="warning",
        page="clients/louis-vuitton.md",
        description="Missing 'last_contact' field in frontmatter."
    )
    assert finding.severity == "warning"
    assert finding.page == "clients/louis-vuitton.md"


def test_lint_report_model():
    report = LintReport(
        findings=[
            LintFinding(severity="error", page="global", description="Orphan page: photographers/unknown.md"),
            LintFinding(severity="warning", page="clients/chanel.md", description="tier field is empty"),
            LintFinding(severity="suggestion", page="global", description="Consider adding Dior as a prospect"),
        ],
        summary="1 error, 1 warning, 1 suggestion found."
    )
    assert len(report.findings) == 3
    errors = [f for f in report.findings if f.severity == "error"]
    assert len(errors) == 1


def test_system_prompt_loaded_from_schema_dir(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# SCHEMA CONTENT")
    (schema_dir / "company_profile.md").write_text("# PROFILE CONTENT")

    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(sources),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    assert "SCHEMA CONTENT" in manager.system_prompt
    assert "PROFILE CONTENT" in manager.system_prompt


def test_system_prompt_raises_if_schema_missing(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    # Only create SCHEMA.md, not company_profile.md
    (schema_dir / "SCHEMA.md").write_text("# Schema")

    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        with pytest.raises(FileNotFoundError):
            WikiManager(
                sources_dir=str(sources),
                wiki_dir=str(wiki),
                schema_dir=str(schema_dir)
            )
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_wiki_page_model tests/test_wiki_manager.py::test_farago_ingestion_result_model tests/test_wiki_manager.py::test_lint_report_model tests/test_wiki_manager.py::test_system_prompt_loaded_from_schema_dir -v
```

Expected: FAIL — `ImportError: cannot import name 'WikiPage'`

- [ ] **Step 3: Add new models and schema loading to wiki_manager.py**

At the top of `backend/agent/wiki_manager.py`, replace the existing model classes and add schema loading. Keep all existing imports and the `_init_llm` method intact. Replace `Entity` and `IngestionResult` with:

```python
# Replace old model classes with these:

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
```

Add `schema_dir` parameter and `_load_system_prompt` to the `WikiManager` class:

```python
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
```

Add to imports at the top of wiki_manager.py — keep the existing `PromptTemplate` import, it is still used by the old `ingest_source` and `query` methods until Tasks 5 and 6 replace them:

```python
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_wiki_page_model tests/test_wiki_manager.py::test_farago_ingestion_result_model tests/test_wiki_manager.py::test_lint_report_model tests/test_wiki_manager.py::test_system_prompt_loaded_from_schema_dir tests/test_wiki_manager.py::test_system_prompt_raises_if_schema_missing -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/agent/wiki_manager.py backend/tests/test_wiki_manager.py
git commit -m "feat(backend): add Farago schema models and system prompt loading"
```

---

## Task 3: Recursive File Traversal

**Files:**
- Modify: `backend/agent/wiki_manager.py`
- Modify: `backend/tests/test_wiki_manager.py`
- Modify: `backend/tests/test_km_features.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_wiki_manager.py`:

```python
def test_list_pages_returns_subdirectory_paths(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "photographers").mkdir()
    (wiki / "clients" / "louis-vuitton.md").write_text("---\ntype: client\n---\n# LV")
    (wiki / "photographers" / "jamie-hawkesworth.md").write_text("---\ntype: photographer\n---\n# JH")
    (wiki / "index.md").write_text("# Index")
    (wiki / "log.md").write_text("# Log")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    pages = manager.list_pages()
    assert "clients/louis-vuitton.md" in pages
    assert "photographers/jamie-hawkesworth.md" in pages
    assert "index.md" not in pages
    assert "log.md" not in pages


def test_update_index_groups_by_subdirectory(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    for sub in ["clients", "prospects", "contacts", "photographers", "productions"]:
        (wiki / sub).mkdir()
    (wiki / "clients" / "louis-vuitton.md").write_text("# LV")
    (wiki / "prospects" / "chanel.md").write_text("# Chanel")
    (wiki / "photographers" / "jamie-hawkesworth.md").write_text("# JH")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    manager.update_index()
    index_content = (wiki / "index.md").read_text()

    assert "## Clients" in index_content
    assert "[[clients/louis-vuitton]]" in index_content
    assert "## Prospects" in index_content
    assert "[[prospects/chanel]]" in index_content
    assert "## Photographers" in index_content
    assert "[[photographers/jamie-hawkesworth]]" in index_content


def test_get_backlinks_across_subdirectories(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "contacts").mkdir()
    (wiki / "productions").mkdir()

    (wiki / "clients" / "louis-vuitton.md").write_text(
        "# LV\n\nKey contact: [[contacts/jane-doe]]"
    )
    (wiki / "productions" / "2026-02-lv-editorial.md").write_text(
        "# LV Editorial\n\nClient: [[clients/louis-vuitton]]"
    )
    (wiki / "contacts" / "jane-doe.md").write_text("# Jane Doe\n\nWorks at [[clients/louis-vuitton]]")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    backlinks = manager.get_backlinks("clients/louis-vuitton.md")
    assert "productions/2026-02-lv-editorial.md" in backlinks
    assert "contacts/jane-doe.md" in backlinks
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_list_pages_returns_subdirectory_paths tests/test_wiki_manager.py::test_update_index_groups_by_subdirectory tests/test_wiki_manager.py::test_get_backlinks_across_subdirectories -v
```

Expected: FAIL

- [ ] **Step 3: Rewrite list_pages(), update_index(), get_backlinks() in wiki_manager.py**

Replace the three methods with these implementations:

```python
ENTITY_SUBDIRS = ["clients", "prospects", "contacts", "photographers", "productions"]

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

def update_index(self):
    """Regenerate index.md grouped by entity subdirectory."""
    index_path = os.path.join(self.wiki_dir, "index.md")
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    sections = {}
    for sub in ENTITY_SUBDIRS:
        sub_dir = os.path.join(self.wiki_dir, sub)
        if not os.path.exists(sub_dir):
            continue
        files = sorted(f for f in os.listdir(sub_dir) if f.endswith(".md"))
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

    for sub in ENTITY_SUBDIRS:
        heading = sub.capitalize()
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
```

Also add `ENTITY_SUBDIRS` as a module-level constant before the `WikiManager` class.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_list_pages_returns_subdirectory_paths tests/test_wiki_manager.py::test_update_index_groups_by_subdirectory tests/test_wiki_manager.py::test_get_backlinks_across_subdirectories -v
```

Expected: 3 PASSED

- [ ] **Step 5: Update test_km_features.py for subdirectory paths**

Replace the entire `temp_wiki` fixture and tests in `backend/tests/test_km_features.py`:

```python
import os
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from agent.wiki_manager import WikiManager


@pytest.fixture
def temp_wiki(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    sources_dir = tmp_path / "sources"
    wiki_dir = tmp_path / "wiki"
    sources_dir.mkdir()
    wiki_dir.mkdir()

    # Create subdirectory structure
    for sub in ["clients", "contacts", "productions"]:
        (wiki_dir / sub).mkdir()

    # Create pages with cross-links
    (wiki_dir / "clients" / "brand-a.md").write_text(
        "# Brand A\n\nLinks to [[contacts/person-b]] and [[contacts/person-c]].",
        encoding="utf-8"
    )
    (wiki_dir / "contacts" / "person-b.md").write_text(
        "# Person B\n\nWorks at [[clients/brand-a]].", encoding="utf-8"
    )
    (wiki_dir / "contacts" / "person-c.md").write_text(
        "# Person C\n\nNo links here.", encoding="utf-8"
    )
    (wiki_dir / "productions" / "2026-01-brand-a-shoot.md").write_text(
        "# Brand A Shoot\n\nClient: [[clients/brand-a]].", encoding="utf-8"
    )

    manager = WikiManager(
        sources_dir=str(sources_dir),
        wiki_dir=str(wiki_dir),
        schema_dir=str(schema_dir),
        llm=MagicMock()
    )
    return manager, wiki_dir


def test_get_backlinks(temp_wiki):
    manager, wiki_dir = temp_wiki

    backlinks_brand_a = manager.get_backlinks("clients/brand-a.md")
    assert "contacts/person-b.md" in backlinks_brand_a
    assert "productions/2026-01-brand-a-shoot.md" in backlinks_brand_a
    assert len(backlinks_brand_a) == 2

    backlinks_person_b = manager.get_backlinks("contacts/person-b.md")
    assert "clients/brand-a.md" in backlinks_person_b
    assert len(backlinks_person_b) == 1

    backlinks_person_c = manager.get_backlinks("contacts/person-c.md")
    assert "clients/brand-a.md" in backlinks_person_c
    assert len(backlinks_person_c) == 1


@pytest.mark.asyncio
async def test_save_page_content(temp_wiki):
    manager, wiki_dir = temp_wiki

    new_content = "# Person C Updated\n\nNow links to [[clients/brand-a]]."
    await manager.save_page_content("contacts/person-c.md", new_content)

    saved = (wiki_dir / "contacts" / "person-c.md").read_text(encoding="utf-8")
    assert saved == new_content

    log_path = wiki_dir / "log.md"
    assert log_path.exists()
    assert "edit | Updated contacts/person-c.md" in log_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_sources_features(temp_wiki):
    manager, _ = temp_wiki
    sources_dir = manager.sources_dir

    with open(os.path.join(sources_dir, "test1.txt"), "w", encoding="utf-8") as f:
        f.write("Hello from test1")

    sources = manager.list_sources()
    assert "test1.txt" in sources

    content = await manager.get_source_content("test1.txt")
    assert content == "Hello from test1"

    with pytest.raises(FileNotFoundError):
        await manager.get_source_content("nonexistent.txt")
```

- [ ] **Step 6: Run updated test_km_features.py**

```bash
cd backend && pytest tests/test_km_features.py -v
```

Expected: all PASSED

- [ ] **Step 7: Commit**

```bash
git add backend/agent/wiki_manager.py backend/tests/test_wiki_manager.py backend/tests/test_km_features.py
git commit -m "feat(backend): recursive file traversal and grouped index for subdirectory structure"
```

---

## Task 4: Path Security Update

**Files:**
- Modify: `backend/api/routes.py`
- Modify: `backend/tests/test_wiki_manager.py` (add path security tests)

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_wiki_manager.py` (these test the updated `safe_wiki_filename` from routes.py — import it directly):

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api.routes import safe_wiki_filename


def test_safe_wiki_filename_allows_known_subdirs():
    for sub in ["clients", "prospects", "contacts", "photographers", "productions"]:
        result = safe_wiki_filename(f"{sub}/some-page.md")
        assert result == f"{sub}/some-page.md"


def test_safe_wiki_filename_rejects_unknown_subdir():
    with pytest.raises(ValueError, match="Invalid entity subdirectory"):
        safe_wiki_filename("evil/foo.md")


def test_safe_wiki_filename_rejects_flat_path():
    with pytest.raises(ValueError, match="Invalid entity subdirectory"):
        safe_wiki_filename("louis-vuitton.md")


def test_safe_wiki_filename_rejects_traversal():
    with pytest.raises(ValueError):
        safe_wiki_filename("../etc/passwd.md")
    with pytest.raises(ValueError):
        safe_wiki_filename("clients/../secrets.md")


def test_safe_wiki_filename_rejects_non_md():
    with pytest.raises(ValueError, match=".md"):
        safe_wiki_filename("clients/foo.txt")
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_safe_wiki_filename_allows_known_subdirs tests/test_wiki_manager.py::test_safe_wiki_filename_rejects_unknown_subdir tests/test_wiki_manager.py::test_safe_wiki_filename_rejects_traversal -v
```

Expected: FAIL

- [ ] **Step 3: Replace safe_wiki_filename in routes.py**

In `backend/api/routes.py`, replace the existing `safe_wiki_filename` function:

```python
VALID_ENTITY_SUBDIRS = {"clients", "prospects", "contacts", "photographers", "productions"}

def safe_wiki_filename(path: str) -> str:
    """Validate a wiki page path of the form 'subdir/page-name.md'.
    Accepts exactly one level of subdirectory from VALID_ENTITY_SUBDIRS.
    Rejects path traversal, unknown subdirectories, and non-.md files.
    """
    # Normalize separators
    normalized = path.replace("\\", "/")

    # Must end with .md
    if not normalized.endswith(".md"):
        raise ValueError(f"Invalid page path: {path!r} — must end with .md")

    parts = normalized.split("/")

    # Must be exactly subdir/filename.md (2 parts)
    if len(parts) != 2:
        raise ValueError(f"Invalid entity subdirectory in path: {path!r}")

    subdir, filename = parts

    # Subdir must be a known entity type
    if subdir not in VALID_ENTITY_SUBDIRS:
        raise ValueError(f"Invalid entity subdirectory '{subdir}' in path: {path!r}")

    # No path traversal components
    if ".." in filename or ".." in subdir:
        raise ValueError(f"Path traversal detected in: {path!r}")

    # Validate the full resolved path stays within wiki dir
    wiki_real = os.path.realpath(WIKI_DIR)
    resolved = os.path.realpath(os.path.join(wiki_real, subdir, filename))

    if os.name == "nt":
        if not resolved.lower().startswith(wiki_real.lower() + os.sep):
            raise ValueError(f"Path traversal detected in: {path!r}")
    else:
        if not resolved.startswith(wiki_real + os.sep):
            raise ValueError(f"Path traversal detected in: {path!r}")

    return normalized
```

Also add `VALID_ENTITY_SUBDIRS` constant near the top of `routes.py`, after `WIKI_DIR` is defined.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_safe_wiki_filename_allows_known_subdirs tests/test_wiki_manager.py::test_safe_wiki_filename_rejects_unknown_subdir tests/test_wiki_manager.py::test_safe_wiki_filename_rejects_flat_path tests/test_wiki_manager.py::test_safe_wiki_filename_rejects_traversal tests/test_wiki_manager.py::test_safe_wiki_filename_rejects_non_md -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes.py backend/tests/test_wiki_manager.py
git commit -m "feat(backend): update path security to require known entity subdirectory"
```

---

## Task 5: Ingest Redesign

**Files:**
- Modify: `backend/agent/wiki_manager.py`
- Modify: `backend/tests/test_wiki_manager.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_wiki_manager.py`:

```python
@pytest.mark.asyncio
async def test_ingest_writes_pages_to_correct_subdirectory(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()
    for sub in ["clients", "contacts", "prospects", "photographers", "productions"]:
        (wiki / sub).mkdir()
    (wiki / "index.md").write_text("# Index\n\n## Clients\n\n*No clients yet.*\n")

    source_file = sources / "lv-brief.txt"
    source_file.write_text("Louis Vuitton is an A-tier client. Contact: Sophie Martin.")

    mock_result = FaragoIngestionResult(
        pages=[
            WikiPage(
                path="clients/louis-vuitton.md",
                content="---\ntype: client\nname: Louis Vuitton\ntier: A\nstatus: active\n---\n# Louis Vuitton\n\n## Overview\n\nLuxury fashion house.\n",
                action="create"
            ),
            WikiPage(
                path="contacts/sophie-martin.md",
                content="---\ntype: contact\nname: Sophie Martin\norg: Louis Vuitton\n---\n# Sophie Martin\n\n## Role & Responsibilities\n\nKey contact at [[clients/louis-vuitton]].\n",
                action="create"
            ),
        ],
        log_entry="Ingested lv-brief.txt. Created 2 pages: clients/louis-vuitton, contacts/sophie-martin."
    )

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(sources),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    with patch.object(manager, '_run_ingest_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_result
        await manager.ingest_source("lv-brief.txt")

    assert (wiki / "clients" / "louis-vuitton.md").exists()
    lv_content = (wiki / "clients" / "louis-vuitton.md").read_text()
    assert "tier: A" in lv_content

    assert (wiki / "contacts" / "sophie-martin.md").exists()
    sophie_content = (wiki / "contacts" / "sophie-martin.md").read_text()
    assert "[[clients/louis-vuitton]]" in sophie_content

    index_content = (wiki / "index.md").read_text()
    assert "[[clients/louis-vuitton]]" in index_content

    log_content = (wiki / "log.md").read_text()
    assert "lv-brief.txt" in log_content

    metadata = manager.get_sources_metadata()
    assert metadata["lv-brief.txt"]["ingested"] is True


@pytest.mark.asyncio
async def test_ingest_source_not_found(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(tmp_path / "wiki"),
            schema_dir=str(schema_dir)
        )

    with pytest.raises(FileNotFoundError):
        await manager.ingest_source("nonexistent.txt")


@pytest.mark.asyncio
async def test_ingest_retries_on_llm_failure(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()
    (wiki / "index.md").write_text("# Index")
    (sources / "test.txt").write_text("Test content")

    success_result = FaragoIngestionResult(
        pages=[WikiPage(path="clients/test.md", content="# Test", action="create")],
        log_entry="Ingested test.txt"
    )

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(sources),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    # Fail once, succeed on second attempt
    (wiki / "clients").mkdir()
    call_count = [0]
    async def flaky_llm(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise ValueError("LLM output validation failed")
        return success_result

    with patch.object(manager, '_run_ingest_llm', side_effect=flaky_llm):
        await manager.ingest_source("test.txt")

    assert call_count[0] == 2
    assert (wiki / "clients" / "test.md").exists()
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_ingest_writes_pages_to_correct_subdirectory tests/test_wiki_manager.py::test_ingest_source_not_found -v
```

Expected: FAIL — `_run_ingest_llm` does not exist yet

- [ ] **Step 3: Rewrite ingest_source() in wiki_manager.py**

Replace the existing `ingest_source` method with:

```python
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

    return result
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_ingest_writes_pages_to_correct_subdirectory tests/test_wiki_manager.py::test_ingest_source_not_found tests/test_wiki_manager.py::test_ingest_retries_on_llm_failure -v
```

Expected: 3 PASSED

- [ ] **Step 5: Remove old Entity and IngestionResult models from wiki_manager.py**

Delete the `Entity` and `IngestionResult` class definitions from `wiki_manager.py`. Also remove `PromptTemplate` from imports if it is no longer referenced anywhere in the file (it won't be after this task if query was already updated — otherwise remove it after Task 6).

- [ ] **Step 6: Commit**

```bash
git add backend/agent/wiki_manager.py backend/tests/test_wiki_manager.py
git commit -m "feat(backend): schema-aware ingest using FaragoIngestionResult with retry logic"
```

---

## Task 6: Query Update

**Files:**
- Modify: `backend/agent/wiki_manager.py`
- Modify: `backend/tests/test_wiki_manager.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_wiki_manager.py`:

```python
@pytest.mark.asyncio
async def test_query_uses_system_prompt(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema — you are the Farago wiki agent")
    (schema_dir / "company_profile.md").write_text("# Farago Projects profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "clients" / "louis-vuitton.md").write_text(
        "---\ntype: client\nname: Louis Vuitton\ntier: A\n---\n# Louis Vuitton\n\n## Overview\n\nA luxury fashion house."
    )
    (wiki / "index.md").write_text(
        "# Index\n\n## Clients\n\n- [[clients/louis-vuitton]] | last updated: 2026-04-15\n"
    )

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    captured_calls = []

    async def mock_run_query(user_query, index_content, context):
        captured_calls.append({
            "query": user_query,
            "index": index_content,
            "context": context,
        })
        return "Louis Vuitton is an A-tier client. [[clients/louis-vuitton]]"

    with patch.object(manager, '_run_query_llm', side_effect=mock_run_query):
        response = await manager.query("Who are our top clients?")

    assert response == "Louis Vuitton is an A-tier client. [[clients/louis-vuitton]]"
    assert len(captured_calls) == 1
    assert "louis-vuitton" in captured_calls[0]["context"].lower()

    log_content = (wiki / "log.md").read_text()
    assert "query" in log_content
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_query_uses_system_prompt -v
```

Expected: FAIL — `_run_query_llm` does not exist

- [ ] **Step 3: Rewrite query() in wiki_manager.py**

Replace the existing `query` method with:

```python
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

    page_names_str = relevance_resp.content.strip()
    if page_names_str.lower() == "none":
        return "I couldn't find relevant information in the wiki to answer your question."

    page_paths = [p.strip() for p in page_names_str.split(",")]

    # Step 2: Read relevant pages
    context = ""
    for path in page_paths:
        clean_path = path.replace("[[", "").replace("]]", "").strip()
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_query_uses_system_prompt -v
```

Expected: PASSED

- [ ] **Step 5: Remove old query test that uses PromptTemplate mock**

Delete `test_wiki_manager_query` from `test_wiki_manager.py` (it patches `PromptTemplate` which is no longer used in `query`).

- [ ] **Step 6: Commit**

```bash
git add backend/agent/wiki_manager.py backend/tests/test_wiki_manager.py
git commit -m "feat(backend): inject system prompt into query and use recursive page lookup"
```

---

## Task 7: Lint Operation (replaces health_check)

**Files:**
- Modify: `backend/agent/wiki_manager.py`
- Delete: `backend/tests/test_wiki_manager_health.py`
- Modify: `backend/tests/test_wiki_manager.py`

- [ ] **Step 1: Delete the old health check test file**

```bash
rm backend/tests/test_wiki_manager_health.py
```

- [ ] **Step 2: Write failing tests**

Add to `backend/tests/test_wiki_manager.py`:

```python
@pytest.mark.asyncio
async def test_lint_returns_report(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "clients" / "louis-vuitton.md").write_text(
        "---\ntype: client\nname: Louis Vuitton\ntier: A\n---\n# Louis Vuitton\n"
    )
    (wiki / "index.md").write_text("# Index\n\n## Clients\n\n- [[clients/louis-vuitton]]\n")

    mock_report = LintReport(
        findings=[
            LintFinding(
                severity="warning",
                page="clients/louis-vuitton.md",
                description="Missing 'last_contact' field in frontmatter."
            )
        ],
        summary="1 warning found."
    )

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    with patch.object(manager, '_run_lint_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_report
        report = await manager.lint()

    assert isinstance(report, LintReport)
    assert len(report.findings) == 1
    assert report.findings[0].severity == "warning"
    assert report.summary == "1 warning found."

    # Lint is read-only — no files written except log
    log_content = (wiki / "log.md").read_text()
    assert "lint" in log_content


def test_health_check_no_longer_exists(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(tmp_path / "wiki"),
            schema_dir=str(schema_dir)
        )

    assert not hasattr(manager, 'health_check'), \
        "health_check() should be removed — use lint() instead"
```

- [ ] **Step 3: Run to confirm failure**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_lint_returns_report tests/test_wiki_manager.py::test_health_check_no_longer_exists -v
```

Expected: FAIL

- [ ] **Step 4: Add lint() and remove health_check() from wiki_manager.py**

Remove the entire `health_check` method.

Add these to `wiki_manager.py`:

```python
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
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_lint_returns_report tests/test_wiki_manager.py::test_health_check_no_longer_exists -v
```

Expected: 2 PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/agent/wiki_manager.py backend/tests/test_wiki_manager.py
git rm backend/tests/test_wiki_manager_health.py
git commit -m "feat(backend): add LLM-powered lint() operation, remove health_check()"
```

---

## Task 8: create_new_page Update

**Files:**
- Modify: `backend/agent/wiki_manager.py`
- Modify: `backend/tests/test_wiki_manager.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_wiki_manager.py`:

```python
@pytest.mark.asyncio
async def test_create_new_page_in_entity_subdir(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    for sub in ["clients", "prospects", "contacts", "photographers", "productions"]:
        (wiki / sub).mkdir()

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    filename = await manager.create_new_page(entity_type="clients")
    assert filename == "clients/Untitled.md"
    assert (wiki / "clients" / "Untitled.md").exists()

    # Second creation → collision handling
    filename2 = await manager.create_new_page(entity_type="clients")
    assert filename2 == "clients/Untitled_1.md"

    # Photographers subdir
    filename3 = await manager.create_new_page(entity_type="photographers")
    assert filename3 == "photographers/Untitled.md"


@pytest.mark.asyncio
async def test_create_new_page_rejects_invalid_type(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(tmp_path / "wiki"),
            schema_dir=str(schema_dir)
        )

    with pytest.raises(ValueError, match="Invalid entity type"):
        await manager.create_new_page(entity_type="invoices")
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_create_new_page_in_entity_subdir tests/test_wiki_manager.py::test_create_new_page_rejects_invalid_type -v
```

Expected: FAIL

- [ ] **Step 3: Replace create_new_page() in wiki_manager.py**

```python
async def create_new_page(self, entity_type: str = "clients") -> str:
    """Create a new Untitled page in the given entity subdirectory.
    Returns the relative path, e.g. 'clients/Untitled.md'.
    """
    if entity_type not in ENTITY_SUBDIRS:
        raise ValueError(f"Invalid entity type: {entity_type!r}. Must be one of {ENTITY_SUBDIRS}")

    async with self._write_lock:
        sub_dir = os.path.join(self.wiki_dir, entity_type)
        os.makedirs(sub_dir, exist_ok=True)

        base_name = "Untitled"
        rel_path = f"{entity_type}/{base_name}.md"
        count = 1
        while os.path.exists(os.path.join(self.wiki_dir, rel_path.replace("/", os.sep))):
            rel_path = f"{entity_type}/{base_name}_{count}.md"
            count += 1

        # Write with minimal frontmatter for the entity type
        singular = entity_type.rstrip("s")  # "clients" → "client", etc.
        content = f"---\ntype: {singular}\nname: \n---\n\n# Untitled\n\nNew page content here.\n"
        with open(os.path.join(self.wiki_dir, rel_path.replace("/", os.sep)), "w", encoding="utf-8") as f:
            f.write(content)

        self.update_index()
        self._append_to_log("create", f"Created {rel_path}")
        return rel_path
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && pytest tests/test_wiki_manager.py::test_create_new_page_in_entity_subdir tests/test_wiki_manager.py::test_create_new_page_rejects_invalid_type -v
```

Expected: 2 PASSED

- [ ] **Step 5: Remove old create_new_page test**

Delete `test_create_new_page` from `test_wiki_manager.py` (it tests the old flat-path behaviour).

- [ ] **Step 6: Commit**

```bash
git add backend/agent/wiki_manager.py backend/tests/test_wiki_manager.py
git commit -m "feat(backend): create_new_page accepts entity_type and writes to correct subdirectory"
```

---

## Task 9: API Routes Update

**Files:**
- Modify: `backend/api/routes.py`
- Modify: `backend/tests/test_sources.py`

- [ ] **Step 1: Run existing test suite to establish baseline**

```bash
cd backend && pytest tests/ -v 2>&1 | tail -20
```

Note any currently failing tests before making changes.

- [ ] **Step 2: Update routes.py — grouped pages endpoint**

Replace the existing `list_pages` route:

```python
@router.get("/pages")
async def list_pages():
    """Return wiki pages grouped by entity subdirectory."""
    try:
        all_pages = wiki_manager.list_pages()
        grouped: Dict[str, List[str]] = {sub: [] for sub in VALID_ENTITY_SUBDIRS}
        for page_path in all_pages:
            parts = page_path.split("/")
            if len(parts) == 2 and parts[0] in VALID_ENTITY_SUBDIRS:
                grouped[parts[0]].append(page_path)
        return grouped
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing pages: {str(e)}")
```

- [ ] **Step 3: Update routes.py — add lint endpoint, remove health endpoint**

Remove the entire `health_check` route.

Add after the sources routes:

```python
@router.post("/lint")
async def run_lint():
    try:
        report = await wiki_manager.lint()
        return report.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running lint: {str(e)}")
```

- [ ] **Step 4: Update routes.py — page routes to accept subdirectory paths**

The `get_page`, `update_page`, `delete_page`, `get_backlinks`, `download_page` routes use `path: str` as the parameter. Update them to use the full path:

```python
@router.get("/pages/{path:path}")
async def get_page(path: str):
    try:
        safe_path = safe_wiki_filename(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        return {"content": wiki_manager.get_page_content(safe_path)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading page: {str(e)}")


@router.get("/pages/{path:path}/backlinks")
async def get_backlinks(path: str):
    try:
        safe_path = safe_wiki_filename(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        return wiki_manager.get_backlinks(safe_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching backlinks: {str(e)}")


@router.put("/pages/{path:path}")
async def update_page(path: str, payload: dict):
    try:
        safe_path = safe_wiki_filename(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    content = payload.get("content")
    if content is None:
        raise HTTPException(status_code=422, detail="Content is required")
    try:
        await wiki_manager.save_page_content(safe_path, content)
        return {"message": "Page updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating page: {str(e)}")


@router.delete("/pages/{path:path}")
async def delete_page(path: str):
    try:
        safe_path = safe_wiki_filename(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await wiki_manager.archive_page(safe_path)
        return {"message": "Page moved to archive"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error archiving page: {str(e)}")


@router.get("/pages/{path:path}/download")
async def download_page(path: str):
    try:
        safe_path = safe_wiki_filename(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    full_path = os.path.join(WIKI_DIR, safe_path.replace("/", os.sep))
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Page not found")
    filename = safe_path.split("/")[-1]
    return FileResponse(full_path, filename=filename, media_type="text/markdown")
```

- [ ] **Step 5: Update routes.py — create_page to accept entity_type**

```python
@router.post("/pages")
async def create_page(entity_type: str = Query("clients")):
    if entity_type not in VALID_ENTITY_SUBDIRS:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")
    try:
        filename = await wiki_manager.create_new_page(entity_type=entity_type)
        return {"filename": filename, "message": "New page created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating page: {str(e)}")
```

- [ ] **Step 6: Update save_page_content and archive_page in wiki_manager.py to use subdirectory paths**

Ensure `get_page_content` and `save_page_content` use `os.sep` when building paths:

```python
def get_page_content(self, page_path: str) -> str:
    path = os.path.join(self.wiki_dir, page_path.replace("/", os.sep))
    if not os.path.exists(path):
        raise FileNotFoundError(f"Page not found: {page_path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

async def save_page_content(self, page_path: str, content: str):
    path = os.path.join(self.wiki_dir, page_path.replace("/", os.sep))
    async with self._write_lock:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        self.update_index()
        self._append_to_log("edit", f"Updated {page_path}")

async def archive_page(self, page_path: str):
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
```

- [ ] **Step 7: Run full test suite**

```bash
cd backend && pytest tests/ -v
```

Expected: all tests PASS (or at most unrelated pre-existing failures)

- [ ] **Step 8: Commit**

```bash
git add backend/api/routes.py backend/agent/wiki_manager.py
git commit -m "feat(backend): update routes for grouped pages, lint endpoint, and subdirectory path support"
```

---

## Task 10: Frontend — WikiView Tree

**Files:**
- Modify: `frontend/src/components/WikiView.tsx`

- [ ] **Step 1: Update the PageTree type and state in WikiView.tsx**

Replace the `pages` state and `fetchPages` function at the top of `WikiView.tsx`:

```typescript
type PageTree = Record<string, string[]>;

// Replace:  const [pages, setPages] = useState<string[]>([]);
const [pageTree, setPageTree] = useState<PageTree>({});
const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
  clients: true,
  prospects: true,
  contacts: true,
  photographers: true,
  productions: true,
});

// Replace fetchPages:
const fetchPages = async () => {
  try {
    setLoading(true);
    const response = await fetch(`${API_BASE}/pages`);
    if (!response.ok) throw new Error('Failed to fetch pages');
    const data: PageTree = await response.json();
    setPageTree(data);
  } catch (err: any) {
    setError(err.message);
  } finally {
    setLoading(false);
  }
};

const toggleSection = (section: string) => {
  setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
};

const totalPageCount = Object.values(pageTree).reduce((acc, pages) => acc + pages.length, 0);
```

- [ ] **Step 2: Add entity type selector state for new page**

Add alongside existing state declarations:

```typescript
const [showNewPageMenu, setShowNewPageMenu] = useState(false);
const ENTITY_TYPES = ['clients', 'prospects', 'contacts', 'photographers', 'productions'];
```

Replace the existing `handleNewPage` function:

```typescript
const handleNewPage = async (entityType: string) => {
  try {
    setIsCreating(true);
    setShowNewPageMenu(false);
    const response = await fetch(`${API_BASE}/pages?entity_type=${entityType}`, { method: 'POST' });
    if (!response.ok) throw new Error('Failed to create new page');
    const data = await response.json();
    await fetchPages();
    await fetchPageContent(data.filename);
    setIsEditing(true);
  } catch (err: any) {
    setError(err.message);
  } finally {
    setIsCreating(false);
  }
};
```

- [ ] **Step 3: Replace the flat page list JSX with the collapsible tree**

In the left sidebar `<div className="w-64 border-r ...">`, replace the entire `<ul>` and its empty state with:

```tsx
{/* Header with New Page menu */}
<div className="flex items-center justify-between mb-4">
  <h2 className="text-lg font-semibold">Pages</h2>
  <div className="relative">
    <button
      onClick={() => setShowNewPageMenu(prev => !prev)}
      disabled={isCreating}
      className="p-1.5 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors disabled:opacity-50"
      title="New Page"
    >
      {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
    </button>
    {showNewPageMenu && (
      <div className="absolute right-0 mt-1 w-44 bg-white rounded-lg shadow-lg border border-gray-100 z-20 overflow-hidden">
        {ENTITY_TYPES.map(type => (
          <button
            key={type}
            onClick={() => handleNewPage(type)}
            className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-blue-50 hover:text-blue-700 capitalize transition-colors"
          >
            {type}
          </button>
        ))}
      </div>
    )}
  </div>
</div>

{/* Collapsible tree */}
{totalPageCount === 0 ? (
  <p className="text-gray-500 text-sm">No pages found. Ingest some data first!</p>
) : (
  <div className="space-y-1">
    {ENTITY_TYPES.map(section => {
      const sectionPages = pageTree[section] || [];
      return (
        <div key={section}>
          <button
            onClick={() => toggleSection(section)}
            className="w-full text-left px-2 py-1.5 flex items-center justify-between text-xs font-semibold text-gray-400 uppercase tracking-wider hover:bg-gray-50 rounded-md transition-colors"
          >
            <span>{section}</span>
            <ChevronRight className={`w-3 h-3 transition-transform duration-150 ${expandedSections[section] ? 'rotate-90' : ''}`} />
          </button>
          {expandedSections[section] && sectionPages.length > 0 && (
            <ul className="ml-1 space-y-0.5 mb-1">
              {sectionPages.map(pagePath => (
                <li key={pagePath}>
                  <button
                    onClick={() => fetchPageContent(pagePath)}
                    className={`w-full text-left px-3 py-1.5 rounded-md text-sm transition-colors flex items-center ${
                      selectedPage === pagePath
                        ? 'bg-blue-50 text-blue-700 font-medium'
                        : 'hover:bg-gray-100 text-gray-700'
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5 mr-2 flex-shrink-0 opacity-50" />
                    <span className="truncate">
                      {pagePath.split('/').pop()?.replace('.md', '').replace(/-/g, ' ')}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      );
    })}
  </div>
)}
```

Add `ChevronRight` to the existing lucide-react import at the top.

- [ ] **Step 4: Update processWikiLinks to resolve subdirectory paths**

Replace the existing `processWikiLinks` function:

```typescript
const processWikiLinks = (text: string, tree: PageTree) => {
  return text.replace(/\[\[(.*?)\]\]/g, (match, p1) => {
    const trimmed = p1.trim();

    // If it already contains a slash, it's a full path reference
    if (trimmed.includes('/')) {
      return `[${trimmed.split('/').pop()?.replace(/-/g, ' ')}](#${trimmed.replace('/', '__')})`;
    }

    // Otherwise, look up which subdirectory contains this page
    const slug = trimmed.toLowerCase().replace(/\s+/g, '-');
    for (const [section, pages] of Object.entries(tree)) {
      const match = pages.find(p => p.endsWith(`/${slug}.md`));
      if (match) {
        const ref = match.replace('/', '__').replace('.md', '');
        return `[${trimmed}](#${ref})`;
      }
    }

    // Fallback: render as plain anchor
    return `[${trimmed}](#${slug})`;
  });
};
```

Update the call site in the `<ReactMarkdown>` block:

```tsx
{processWikiLinks(content || '', pageTree)}
```

Update the internal link click handler in `ReactMarkdown` to resolve paths:

```tsx
a: ({ node, ...props }) => {
  const isInternal = props.href?.startsWith('#');
  if (isInternal) {
    const ref = props.href?.slice(1); // e.g. "clients__louis-vuitton"
    const pagePath = ref?.replace('__', '/') + '.md'; // "clients/louis-vuitton.md"
    return (
      <a
        {...props}
        onClick={(e) => {
          e.preventDefault();
          if (pagePath) fetchPageContent(pagePath);
        }}
        className="text-blue-600 hover:underline cursor-pointer font-medium"
      >
        {props.children}
      </a>
    );
  }
  return <a {...props} className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer" />;
}
```

- [ ] **Step 5: Update page display name in header to strip subdirectory**

Find the breadcrumb span in the navigation header:

```tsx
{selectedPage && (
  <span className="ml-4 text-sm font-medium text-gray-500 truncate max-w-xs">
    {selectedPage.split('/').pop()?.replace('.md', '').replace(/-/g, ' ')}
  </span>
)}
```

And the delete confirm dialog:

```tsx
if (!window.confirm(`Move '${selectedPage.split('/').pop()?.replace('.md', '').replace(/-/g, ' ')}' to archive?`)) return;
```

- [ ] **Step 6: Close new-page menu on outside click**

Add a `useEffect` that closes the menu when clicking outside:

```typescript
useEffect(() => {
  const handleOutsideClick = (e: MouseEvent) => {
    setShowNewPageMenu(false);
  };
  if (showNewPageMenu) {
    document.addEventListener('click', handleOutsideClick);
  }
  return () => document.removeEventListener('click', handleOutsideClick);
}, [showNewPageMenu]);
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/WikiView.tsx
git commit -m "feat(frontend): collapsible tree view in WikiView, entity-type new page menu, path-aware wikilinks"
```

---

## Task 11: Frontend — Sidebar, LintView, App

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/LintView.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create LintView.tsx**

Create `frontend/src/components/LintView.tsx`:

```tsx
import React, { useState } from 'react';
import { Activity, Loader2, AlertCircle, AlertTriangle, Lightbulb } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || `http://${window.location.hostname}:8300/api`;

interface LintFinding {
  severity: 'error' | 'warning' | 'suggestion';
  page: string;
  description: string;
}

interface LintReport {
  findings: LintFinding[];
  summary: string;
}

const SEVERITY_CONFIG = {
  error: {
    label: 'Errors',
    icon: <AlertCircle className="w-4 h-4 text-red-500" />,
    cardClass: 'bg-red-50 border-red-200',
    badgeClass: 'bg-red-100 text-red-700',
  },
  warning: {
    label: 'Warnings',
    icon: <AlertTriangle className="w-4 h-4 text-amber-500" />,
    cardClass: 'bg-amber-50 border-amber-200',
    badgeClass: 'bg-amber-100 text-amber-700',
  },
  suggestion: {
    label: 'Suggestions',
    icon: <Lightbulb className="w-4 h-4 text-blue-500" />,
    cardClass: 'bg-blue-50 border-blue-200',
    badgeClass: 'bg-blue-100 text-blue-700',
  },
};

const LintView: React.FC = () => {
  const [report, setReport] = useState<LintReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runLint = async () => {
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const response = await fetch(`${API_BASE}/lint`, { method: 'POST' });
      if (!response.ok) throw new Error('Lint request failed');
      const data: LintReport = await response.json();
      setReport(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-12 max-w-4xl mx-auto">
      <h1 className="text-4xl font-extrabold text-gray-900 mb-6 tracking-tight">Wiki Lint</h1>
      <p className="text-xl text-gray-500 mb-8 leading-relaxed">
        Deep AI analysis — orphan pages, contradictions, missing entities, and data gaps.
      </p>

      <button
        onClick={runLint}
        disabled={loading}
        className="flex items-center px-6 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50 mb-8 shadow-sm"
      >
        {loading
          ? <Loader2 className="w-5 h-5 animate-spin mr-2" />
          : <Activity className="w-5 h-5 mr-2" />
        }
        Lint
      </button>

      {loading && (
        <div className="flex items-center space-x-3 text-gray-500">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Analysing wiki — this may take a moment...</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          {error}
        </div>
      )}

      {report && (
        <div className="space-y-6">
          <p className="text-gray-600 font-medium">{report.summary}</p>

          {(['error', 'warning', 'suggestion'] as const).map(severity => {
            const findings = report.findings.filter(f => f.severity === severity);
            if (findings.length === 0) return null;
            const config = SEVERITY_CONFIG[severity];
            return (
              <div key={severity}>
                <h3 className="flex items-center space-x-2 text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
                  {config.icon}
                  <span>{config.label} ({findings.length})</span>
                </h3>
                <ul className="space-y-2">
                  {findings.map((finding, i) => (
                    <li key={i} className={`p-4 rounded-xl border ${config.cardClass}`}>
                      <span className={`inline-block text-xs font-mono px-2 py-0.5 rounded-md mb-1 ${config.badgeClass}`}>
                        {finding.page}
                      </span>
                      <p className="text-sm text-gray-700">{finding.description}</p>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}

          {report.findings.length === 0 && (
            <p className="text-green-600 font-medium">Wiki is clean — no issues found.</p>
          )}
        </div>
      )}
    </div>
  );
};

export default LintView;
```

- [ ] **Step 2: Update Sidebar.tsx — replace Health Check with Lint nav item**

Replace the entire `Sidebar.tsx` file:

```tsx
import React from 'react';
import { Book, Upload, MessageSquare, Layers, Archive, Activity } from 'lucide-react';

interface SidebarProps {
  currentView: string;
  onViewChange: (view: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ currentView, onViewChange }) => {
  const menuItems = [
    { name: 'Wiki', icon: <Book className="w-5 h-5" /> },
    { name: 'Sources', icon: <Layers className="w-5 h-5" /> },
    { name: 'Upload', icon: <Upload className="w-5 h-5" /> },
    { name: 'Chat', icon: <MessageSquare className="w-5 h-5" /> },
    { name: 'Archive', icon: <Archive className="w-5 h-5" /> },
    { name: 'Lint', icon: <Activity className="w-5 h-5" /> },
  ];

  return (
    <div className="flex flex-col h-screen w-64 bg-gray-800 text-white shadow-xl">
      <div className="p-6 text-2xl font-bold border-b border-gray-700 flex items-center">
        <div className="w-8 h-8 bg-blue-600 rounded-lg mr-3 flex items-center justify-center text-sm">FP</div>
        Faragopedia
      </div>

      <nav className="flex-grow p-4">
        <ul className="space-y-2">
          {menuItems.map((item) => (
            <li key={item.name}>
              <button
                onClick={() => onViewChange(item.name)}
                className={`w-full text-left px-4 py-3 rounded-lg transition-all duration-200 flex items-center space-x-3 ${
                  currentView === item.name
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
                    : 'hover:bg-gray-700 text-gray-300 hover:text-white'
                }`}
              >
                {item.icon}
                <span className="font-medium">{item.name}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="p-4 text-xs text-gray-500 border-t border-gray-700 text-center uppercase tracking-wider">
        Faragopedia v0.2.0
      </div>
    </div>
  );
};

export default Sidebar;
```

- [ ] **Step 3: Update App.tsx — add LintView, remove all health check code**

Replace the entire `App.tsx` with:

```tsx
import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import WikiView from './components/WikiView';
import SourcesView from './components/SourcesView';
import ArchiveView from './components/ArchiveView';
import LintView from './components/LintView';
import { Loader2, Upload, MessageSquare, Activity } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || `http://${window.location.hostname}:8300/api`;

const App: React.FC = () => {
  const [currentView, setCurrentView] = useState('Wiki');
  const [uploading, setUploading] = useState(false);
  const [chatQuery, setChatQuery] = useState('');
  const [chatHistory, setChatHistory] = useState<{ role: 'user' | 'assistant', content: string }[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    setUploading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/upload`, { method: 'POST', body: formData });
      if (!response.ok) throw new Error('Upload failed');
      const data = await response.json();
      alert(`Success: ${data.message}`);
    } catch (err) {
      alert('Error uploading file');
    } finally {
      setUploading(false);
      if (event.target) event.target.value = '';
    }
  };

  const handleChat = async () => {
    if (!chatQuery.trim()) return;
    const userMessage = chatQuery;
    setChatQuery('');
    setChatHistory(prev => [...prev, { role: 'user', content: userMessage }]);
    setChatLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/chat?query=${encodeURIComponent(userMessage)}`, { method: 'POST' });
      if (!response.ok) throw new Error('Chat failed');
      const data = await response.json();
      setChatHistory(prev => [...prev, { role: 'assistant', content: data.response }]);
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  const renderContent = () => {
    switch (currentView) {
      case 'Wiki':
        return <WikiView />;
      case 'Sources':
        return <SourcesView />;
      case 'Upload':
        return (
          <div className="p-12 max-w-4xl mx-auto">
            <h1 className="text-4xl font-extrabold text-gray-900 mb-6 tracking-tight">Upload Sources</h1>
            <p className="text-xl text-gray-500 mb-8 leading-relaxed">
              Add documents, PDFs, or text files. The AI will ingest and create Farago schema pages automatically.
            </p>
            <label className="bg-white rounded-2xl shadow-sm border border-gray-200 p-12 flex flex-col items-center border-dashed border-2 hover:border-blue-400 transition-colors cursor-pointer group relative">
              <input type="file" className="hidden" onChange={handleFileUpload} disabled={uploading} />
              <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mb-6 group-hover:bg-blue-100 transition-colors">
                {uploading ? <Loader2 className="w-8 h-8 text-blue-600 animate-spin" /> : <Upload className="w-8 h-8 text-blue-600" />}
              </div>
              <p className="text-lg font-medium text-gray-700">
                {uploading ? 'Uploading and ingesting...' : 'Click to select a file to upload'}
              </p>
              <p className="text-sm text-gray-400 mt-2">PDF, TXT, and Markdown supported</p>
            </label>
          </div>
        );
      case 'Chat':
        return (
          <div className="p-12 max-w-4xl mx-auto h-full flex flex-col">
            <h1 className="text-4xl font-extrabold text-gray-900 mb-6 tracking-tight">AI Assistant</h1>
            <p className="text-xl text-gray-500 mb-8 leading-relaxed">
              Ask questions about your data. The AI synthesises answers from wiki pages and cites sources.
            </p>
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 flex-grow flex flex-col overflow-hidden mb-8">
              <div className="flex-grow overflow-y-auto p-6 space-y-4">
                {chatHistory.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-gray-400 space-y-4">
                    <MessageSquare className="w-12 h-12 opacity-20" />
                    <p>Start a conversation with your Wiki</p>
                  </div>
                ) : (
                  chatHistory.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] px-4 py-3 rounded-2xl ${
                        msg.role === 'user'
                          ? 'bg-blue-600 text-white rounded-tr-none'
                          : 'bg-gray-100 text-gray-800 rounded-tl-none'
                      }`}>
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                      </div>
                    </div>
                  ))
                )}
                {chatLoading && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-tl-none flex items-center space-x-2">
                      <Loader2 className="w-4 h-4 animate-spin text-gray-500" />
                      <span className="text-sm text-gray-500">AI is thinking...</span>
                    </div>
                  </div>
                )}
              </div>
              <div className="p-4 bg-gray-50 border-t">
                <div className="relative">
                  <input
                    type="text"
                    value={chatQuery}
                    onChange={(e) => setChatQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleChat()}
                    placeholder="Ask a question..."
                    disabled={chatLoading}
                    className="w-full px-6 py-4 bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all pr-16"
                  />
                  <button
                    onClick={handleChat}
                    disabled={chatLoading || !chatQuery.trim()}
                    className="absolute right-3 top-3 bg-blue-600 text-white p-2 rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
                  >
                    <Activity className="w-5 h-5 transform rotate-90" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      case 'Archive':
        return <ArchiveView />;
      case 'Lint':
        return <LintView />;
      default:
        return <div className="p-8">Select a view</div>;
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 font-sans antialiased text-gray-900">
      <Sidebar currentView={currentView} onViewChange={setCurrentView} />
      <main className="flex-grow overflow-hidden relative">
        {renderContent()}
      </main>
    </div>
  );
};

export default App;
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/LintView.tsx frontend/src/components/Sidebar.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add LintView, replace Health Check with Lint nav, remove health check modal"
```

---

## Task 12: Final Integration Test

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 2: Start backend locally and verify routes**

```bash
cd backend && uvicorn main:app --host 0.0.0.0 --port 8300 --reload
```

In a second terminal:

```bash
# Grouped pages
curl http://localhost:8300/api/pages

# Should return: {"clients":[],"prospects":[],"contacts":[],"photographers":[],"productions":[]}

# Lint endpoint exists
curl -X POST http://localhost:8300/api/lint

# Health endpoint is gone
curl http://localhost:8300/api/health
# Expected: 404
```

- [ ] **Step 3: Start frontend and verify UI**

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173` and verify:
- Sidebar shows Wiki, Sources, Upload, Chat, Archive, Lint — no Health Check
- Wiki view shows collapsible tree (all sections collapsed if empty)
- Plus button opens entity type dropdown (clients, prospects, contacts, photographers, productions)
- Lint view renders with "Lint" button
- Clicking Lint fires `POST /api/lint` (check Network tab)

- [ ] **Step 4: Upload a source and verify schema-compliant pages are created**

Upload any text file through the Upload view. After ingestion:
- Check that pages appear under the correct entity type section in the tree
- Open a created page and verify YAML frontmatter is present
- Verify the page lives at e.g. `wiki/clients/brand-name.md` (check container volume or local `wiki/` directory)

- [ ] **Step 5: Build Docker image**

```bash
docker-compose build
docker-compose up
```

Navigate to `http://localhost:5173`. Verify the same steps as Step 3 work inside Docker.

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "chore: final integration verification — Wiki-Concept schema fully integrated"
```

---

## Known Limitations (follow-up work)

**Archive view with subdirectory paths:** `list_archived_pages()` uses `os.listdir()` on a flat directory. If a user archives a page after this migration, it will be stored at `archive/wiki/clients/louis-vuitton.md` but the archive listing won't recurse into subdirectories. The `ArchiveView.tsx` will not display it. This should be addressed in a follow-up by making `list_archived_pages()` and `restore_page()` recursive (same `os.walk` pattern as `list_pages()`).

**Context window size for large wikis:** `ingest_source()` passes all existing pages as context. As the wiki grows beyond ~50 pages this will exceed typical context windows. A future improvement would be a semantic pre-filter (embedding-based lookup) to pass only the most relevant existing pages.
