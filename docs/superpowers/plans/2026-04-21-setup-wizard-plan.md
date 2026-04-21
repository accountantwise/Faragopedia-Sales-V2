# Setup Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-run setup wizard that makes the wiki company-agnostic, replacing hardcoded Farago identity with LLM-generated entity types configured at first launch.

**Architecture:** FastAPI dependency injection gates all wiki routes behind `get_wiki_manager()` which returns 503 until setup completes. A 3-step React wizard collects identity, reviews/edits LLM-generated entity types (with full field control), and writes all config files. A "Reconfigure Wiki" sidebar button re-enters the wizard with a diff layout showing existing vs new folders.

**Tech Stack:** FastAPI, Pydantic v2, LangChain PydanticOutputParser, React 18, TypeScript, Tailwind CSS

---

## File Map

### New files
- `Faragopedia-Sales/backend/agent/setup_wizard.py` — core setup functions + LLM suggestion
- `Faragopedia-Sales/backend/api/setup_routes.py` — 5 setup API endpoints + Pydantic models
- `Faragopedia-Sales/backend/tests/test_setup_wizard.py` — unit tests for setup_wizard functions
- `Faragopedia-Sales/backend/tests/test_setup_routes.py` — integration tests for setup endpoints
- `Faragopedia-Sales/frontend/src/components/SetupWizard.tsx` — full 3-step wizard component

### Modified files
- `Faragopedia-Sales/backend/agent/wiki_manager.py:201-207` — stub fallback in `_load_system_prompt()`
- `Faragopedia-Sales/backend/api/routes.py:52-62` — replace module-level singleton with DI functions; update all route signatures
- `Faragopedia-Sales/backend/main.py` — startup init + register setup router
- `Faragopedia-Sales/frontend/src/App.tsx` — setup state gating + reconfigure flow
- `Faragopedia-Sales/frontend/src/components/Sidebar.tsx` — `wikiName` prop + Reconfigure button

---

## Task 1: WikiManager stub fallback

**Files:**
- Modify: `Faragopedia-Sales/backend/agent/wiki_manager.py:201-212`
- Test: `Faragopedia-Sales/backend/tests/test_setup_wizard.py` (partial — written here, extended in Task 7)

- [ ] **Step 1: Write the failing test**

Create `Faragopedia-Sales/backend/tests/test_setup_wizard.py`:

```python
import os
import pytest
import tempfile
from agent.wiki_manager import WikiManager

def test_wiki_manager_init_without_schema_files():
    """WikiManager should not crash when SCHEMA.md and company_profile.md are absent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_dir = os.path.join(tmpdir, "wiki")
        os.makedirs(wiki_dir)
        schema_dir = os.path.join(tmpdir, "schema")
        os.makedirs(schema_dir)
        # No SCHEMA.md, no company_profile.md, no SCHEMA_TEMPLATE.md
        # Should not raise
        wm = WikiManager(
            sources_dir=os.path.join(tmpdir, "sources"),
            wiki_dir=wiki_dir,
            archive_dir=os.path.join(tmpdir, "archive"),
            snapshots_dir=os.path.join(tmpdir, "snapshots"),
            schema_dir=schema_dir,
        )
        assert wm is not None
```

- [ ] **Step 2: Run test to verify it fails**

```
cd Faragopedia-Sales/backend
pytest tests/test_setup_wizard.py::test_wiki_manager_init_without_schema_files -v
```

Expected: FAIL — `FileNotFoundError: SCHEMA.md not found`

- [ ] **Step 3: Fix `_load_system_prompt()` to return stub when files absent**

In `Faragopedia-Sales/backend/agent/wiki_manager.py`, replace lines 201-212:

```python
def _load_system_prompt(self) -> str:
    schema_path = os.path.join(self.schema_dir, "SCHEMA.md")
    profile_path = os.path.join(self.schema_dir, "company_profile.md")
    if not os.path.exists(schema_path) or not os.path.exists(profile_path):
        return "Wiki not yet configured. Setup required."
    with open(schema_path, "r", encoding="utf-8", errors="replace") as f:
        schema = f.read()
    with open(profile_path, "r", encoding="utf-8") as f:
        profile = f.read()
    return f"{schema}\n\n---\n\n{profile}"
```

- [ ] **Step 4: Run test to verify it passes**

```
cd Faragopedia-Sales/backend
pytest tests/test_setup_wizard.py::test_wiki_manager_init_without_schema_files -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/agent/wiki_manager.py Faragopedia-Sales/backend/tests/test_setup_wizard.py
git commit -m "feat: wiki_manager returns stub system prompt when schema files absent"
```

---

## Task 2: Dependency injection in routes.py

**Files:**
- Modify: `Faragopedia-Sales/backend/api/routes.py`

This is a mechanical refactor. No logic changes to any route — only how `wiki_manager` is accessed.

- [ ] **Step 1: Replace the module-level singleton (lines 52-58) with DI scaffolding**

Replace:
```python
# Instantiate WikiManager
wiki_manager = WikiManager(
    sources_dir=SOURCES_DIR,
    wiki_dir=WIKI_DIR,
    archive_dir=ARCHIVE_DIR,
    snapshots_dir=SNAPSHOTS_DIR
)
```

With:
```python
from fastapi import Depends
from typing import Annotated

_wiki_manager: WikiManager | None = None

def get_wiki_manager() -> WikiManager:
    if _wiki_manager is None:
        raise HTTPException(status_code=503, detail="Wiki setup not complete")
    return _wiki_manager

def set_wiki_manager(wm: "WikiManager | None") -> None:
    global _wiki_manager
    _wiki_manager = wm

WM = Annotated[WikiManager, Depends(get_wiki_manager)]
```

- [ ] **Step 2: Update `get_valid_entity_subdirs()` to accept wm parameter (line 60-62)**

Replace:
```python
def get_valid_entity_subdirs() -> set:
    """Get valid entity subdirectories dynamically from wiki_manager."""
    return set(wiki_manager.get_entity_types().keys())
```

With:
```python
def get_valid_entity_subdirs(wm: WikiManager) -> set:
    return set(wm.get_entity_types().keys())
```

- [ ] **Step 3: Update every route handler that uses `wiki_manager`**

Add `wm: WM` parameter to each route and replace `wiki_manager.` with `wm.`. Also replace `get_valid_entity_subdirs()` with `get_valid_entity_subdirs(wm)`. Full list of routes to update (every `@router.` decorated function):

`upload_file` — add `wm: WM`, replace `wiki_manager.ingest_source` → `wm.ingest_source`
`chat` — add `wm: WM`, replace `wiki_manager.query` → `wm.query`
`list_pages` — add `wm: WM`, pass `wm` to `get_valid_entity_subdirs(wm)`
`list_sources` — add `wm: WM`, replace `wiki_manager.list_sources` → `wm.list_sources`
`get_sources_metadata` — add `wm: WM`, replace accordingly
`ingest_source` — add `wm: WM`, replace `wiki_manager.ingest_source` → `wm.ingest_source`
`bulk_ingest_sources` — add `wm: WM`, replace accordingly
`get_backlinks` — add `wm: WM`, replace accordingly
`download_page` — no `wiki_manager` usage, skip
`get_page` — add `wm: WM`, replace accordingly
`get_source` — add `wm: WM`, replace accordingly
`create_page` — add `wm: WM`, pass `wm` to `get_valid_entity_subdirs(wm)`, replace `wiki_manager.create_new_page` → `wm.create_new_page`
`get_entity_types` — add `wm: WM`, replace accordingly
`create_folder` — add `wm: WM`, replace accordingly
`delete_folder` — add `wm: WM`, replace accordingly
`rename_folder` — add `wm: WM`, replace accordingly
`move_page` — add `wm: WM`, replace accordingly
`run_lint` — add `wm: WM`, replace accordingly
`fix_lint_findings` — add `wm: WM`, replace accordingly
`list_snapshots` — add `wm: WM`, replace accordingly
`restore_snapshot` — add `wm: WM`, replace accordingly
`delete_snapshot` — add `wm: WM`, replace accordingly
`bulk_archive_sources` — add `wm: WM`, replace accordingly
`bulk_archive_pages` — add `wm: WM`, replace accordingly
`bulk_move_pages` — add `wm: WM`, pass `wm` to `get_valid_entity_subdirs(wm)`, replace accordingly
`bulk_download_pages` — no `wiki_manager` usage, skip
`delete_page` — add `wm: WM`, replace accordingly
`delete_source` — add `wm: WM`, replace accordingly
`list_archived_pages` — add `wm: WM`, replace accordingly
`list_archived_sources` — add `wm: WM`, replace accordingly
`restore_page` — add `wm: WM`, replace accordingly
`restore_source` — add `wm: WM`, replace accordingly
`delete_archived_page_permanent` — add `wm: WM`, replace accordingly
`get_search_index` — add `wm: WM`, replace `wiki_manager._rebuild_search_index()` → `wm._rebuild_search_index()`
`get_tags` — add `wm: WM`, replace accordingly
`update_page_tags` — add `wm: WM`, replace accordingly
`update_source_tags` — add `wm: WM`, replace accordingly
`rebuild_search_index` — add `wm: WM`, replace accordingly
`update_page` — add `wm: WM`, replace accordingly
`delete_archived_source_permanent` — add `wm: WM`, replace accordingly
`download_source` — no `wiki_manager` usage, skip

Example of before/after for `chat`:
```python
# Before
@router.post("/chat")
async def chat(query: str):
    if not query or not query.strip():
        raise HTTPException(status_code=422, detail="Query parameter is required")
    try:
        response = await wiki_manager.query(query)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

# After
@router.post("/chat")
async def chat(query: str, wm: WM):
    if not query or not query.strip():
        raise HTTPException(status_code=422, detail="Query parameter is required")
    try:
        response = await wm.query(query)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
```

- [ ] **Step 4: Verify existing tests still pass**

```
cd Faragopedia-Sales/backend
pytest tests/ -v --ignore=tests/test_setup_wizard.py
```

Expected: All previously passing tests still PASS. (Tests that construct WikiManager directly are unaffected.)

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/api/routes.py
git commit -m "refactor: replace module-level WikiManager singleton with FastAPI DI"
```

---

## Task 3: setup_wizard.py — core functions + BASE_SCHEMA_TEMPLATE

**Files:**
- Create: `Faragopedia-Sales/backend/agent/setup_wizard.py`

- [ ] **Step 1: Write failing tests for core functions**

Add to `Faragopedia-Sales/backend/tests/test_setup_wizard.py`:

```python
import json
from agent.setup_wizard import is_setup_complete, get_wiki_config, migrate_existing, clear_setup

def test_is_setup_complete_false_when_no_config(tmp_path):
    assert is_setup_complete(str(tmp_path)) is False

def test_is_setup_complete_true_when_config_exists(tmp_path):
    config = {"wiki_name": "Test", "org_name": "Test Org", "setup_complete": True}
    (tmp_path / "wiki_config.json").write_text(json.dumps(config))
    assert is_setup_complete(str(tmp_path)) is True

def test_get_wiki_config_returns_none_when_missing(tmp_path):
    assert get_wiki_config(str(tmp_path)) is None

def test_get_wiki_config_returns_dict_when_present(tmp_path):
    config = {"wiki_name": "Test", "org_name": "Test Org", "setup_complete": True}
    (tmp_path / "wiki_config.json").write_text(json.dumps(config))
    result = get_wiki_config(str(tmp_path))
    assert result["wiki_name"] == "Test"

def test_migrate_existing_creates_config_when_profile_exists(tmp_path):
    (tmp_path / "company_profile.md").write_text("# Farago Projects")
    migrate_existing(str(tmp_path))
    assert (tmp_path / "wiki_config.json").exists()
    config = json.loads((tmp_path / "wiki_config.json").read_text())
    assert config["wiki_name"] == "Faragopedia"
    assert config["setup_complete"] is True

def test_migrate_existing_no_op_when_config_exists(tmp_path):
    (tmp_path / "company_profile.md").write_text("# Farago Projects")
    existing = {"wiki_name": "Custom", "org_name": "Custom Org", "setup_complete": True}
    (tmp_path / "wiki_config.json").write_text(json.dumps(existing))
    migrate_existing(str(tmp_path))
    config = json.loads((tmp_path / "wiki_config.json").read_text())
    assert config["wiki_name"] == "Custom"  # unchanged

def test_migrate_existing_no_op_when_no_profile(tmp_path):
    migrate_existing(str(tmp_path))
    assert not (tmp_path / "wiki_config.json").exists()

def test_clear_setup_removes_config_and_returns_folders(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    (wiki_dir / "clients").mkdir()
    (wiki_dir / "productions").mkdir()
    (wiki_dir / "clients" / "_type.yaml").write_text("name: Clients")
    config = {"wiki_name": "Test", "org_name": "Test Org", "setup_complete": True}
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "wiki_config.json").write_text(json.dumps(config))

    folders = clear_setup(str(schema_dir), str(wiki_dir))
    assert not (schema_dir / "wiki_config.json").exists()
    assert "clients" in folders
    assert "productions" not in folders  # no _type.yaml
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd Faragopedia-Sales/backend
pytest tests/test_setup_wizard.py -v -k "not test_wiki_manager"
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent.setup_wizard'`

- [ ] **Step 3: Create `setup_wizard.py` with Pydantic models + core functions + BASE_SCHEMA_TEMPLATE**

All Pydantic models live here (not in setup_routes.py) to avoid circular imports.

Create `Faragopedia-Sales/backend/agent/setup_wizard.py`:

```python
import json
import os
import re

import yaml
from pydantic import BaseModel, field_validator


# ── Pydantic models (shared with setup_routes.py via import) ──────────────────

class EntityTypeField(BaseModel):
    name: str
    type: str  # string | date | integer | enum | list
    default: str | None = None
    required: bool | None = None
    values: list[str] | None = None
    description: str | None = None


class EntityTypeDefinition(BaseModel):
    folder_name: str
    display_name: str
    description: str
    singular: str
    fields: list[EntityTypeField]
    sections: list[str]

    @field_validator("folder_name")
    @classmethod
    def folder_name_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9-]*$", v):
            raise ValueError("folder_name must be lowercase alphanumeric with hyphens")
        return v


class SuggestedSchema(BaseModel):
    entity_types: list[EntityTypeDefinition]


class SuggestRequest(BaseModel):
    org_name: str
    org_description: str


class SetupPayload(BaseModel):
    wiki_name: str
    org_name: str
    org_description: str
    entity_types: list[EntityTypeDefinition]


BASE_SCHEMA_TEMPLATE = """\
# SCHEMA.md — {{ORG_NAME}} LLM Wiki

This file is the operating manual for the LLM wiki agent. Read it at the start of every session before taking any action.

---

## Identity

You are the wiki agent for {{ORG_NAME}}. {{ORG_DESCRIPTION}}

Your role: maintain a persistent, compounding knowledge base. You write and maintain all wiki pages. The human curates sources and directs analysis.

Read `company_profile.md` if you need full company context.

---

## Session Start Protocol

At the start of EVERY session, before responding to any request:

1. Read `SCHEMA.md` (this file)
2. Read `index.md` to load current wiki state
3. Read the last 10 entries of `log.md` to understand recent activity

---

## Directory Structure

```
Wiki/
├── SCHEMA.md              # This file — LLM operating manual
├── index.md               # Master catalog of all wiki pages
├── log.md                 # Append-only chronological log
├── company_profile.md     # Organisation profile (IMMUTABLE — never modify)
│
{{ENTITY_TYPES_DIRECTORY}}
└── sources/               # Immutable raw source documents (human drops here — never modify)
    └── assets/            # Downloaded images
```

---

## Immutable Files

NEVER modify these files under any circumstances:
- `sources/` — all files and subdirectories
- `company_profile.md`

---

## Page Schemas

All wiki pages use YAML frontmatter for Obsidian Dataview compatibility. Use wikilink syntax (`[[page-name]]`) for all cross-references.

{{ENTITY_TYPES_SCHEMAS}}

## Operations

### Ingest
**Trigger:** User says "ingest [source]" or "ingest [filename]"

1. Read the source file from `sources/`
2. Discuss key takeaways with the user
3. Create or update all touched entity pages — check the Directory Structure above for available folders
4. Update `index.md` — add any new pages, update summaries of changed pages
5. Append to `log.md`: `## [YYYY-MM-DD] ingest | [source title]` followed by a 2–3 line summary of what was updated

A single source may touch 5–15 wiki pages. Update all of them.

---

### Query
**Trigger:** Any question about any entity in the wiki

1. Read `index.md` to identify the most relevant pages
2. Read those pages in full
3. Synthesize a clear answer with inline wikilink citations (`[[page-name]]`)
4. If the answer is valuable enough to keep, offer to file it as a new wiki page
5. Append to `log.md`: `## [YYYY-MM-DD] query | [topic]`

---

### Lint
**Trigger:** User says "lint"

1. Read all pages listed in `index.md`
2. Scan for orphan pages, contradictions, missing entities, data gaps
3. Append to `log.md`: `## [YYYY-MM-DD] lint | [brief summary of findings]`

---

## General Rules

1. **Never modify** `sources/` or `company_profile.md`
2. **Always use wikilinks** — cite cross-references as `[[page-name]]` not plain text
3. **Prefer updating over creating** — update an existing page before creating a new one
4. **Keep index.md current** — update it on every ingest operation
5. **Keep log.md current** — append an entry on every ingest, query, and lint operation
6. **Frontmatter always** — every wiki page must have valid YAML frontmatter matching its schema
7. **File naming** — lowercase, hyphen-separated: `acme-corp.md`, `jane-smith.md`
"""


def is_setup_complete(schema_dir: str) -> bool:
    return os.path.exists(os.path.join(schema_dir, "wiki_config.json"))


def get_wiki_config(schema_dir: str) -> dict | None:
    path = os.path.join(schema_dir, "wiki_config.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def migrate_existing(schema_dir: str) -> None:
    config_path = os.path.join(schema_dir, "wiki_config.json")
    profile_path = os.path.join(schema_dir, "company_profile.md")
    if os.path.exists(profile_path) and not os.path.exists(config_path):
        config = {
            "wiki_name": "Faragopedia",
            "org_name": "Farago Projects",
            "setup_complete": True,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)


def clear_setup(schema_dir: str, wiki_dir: str) -> list[str]:
    config_path = os.path.join(schema_dir, "wiki_config.json")
    if os.path.exists(config_path):
        os.remove(config_path)
    folders = []
    if os.path.isdir(wiki_dir):
        for entry in sorted(os.listdir(wiki_dir)):
            full = os.path.join(wiki_dir, entry)
            if os.path.isdir(full) and os.path.exists(os.path.join(full, "_type.yaml")):
                folders.append(entry)
    return folders
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd Faragopedia-Sales/backend
pytest tests/test_setup_wizard.py -v -k "not test_wiki_manager"
```

Expected: All 7 core-function tests PASS

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/agent/setup_wizard.py Faragopedia-Sales/backend/tests/test_setup_wizard.py
git commit -m "feat: add setup_wizard core functions and BASE_SCHEMA_TEMPLATE"
```

---

## Task 4: setup_wizard.py — complete_setup()

**Files:**
- Modify: `Faragopedia-Sales/backend/agent/setup_wizard.py`
- Modify: `Faragopedia-Sales/backend/tests/test_setup_wizard.py`

- [ ] **Step 1: Write failing test for complete_setup()**

Add to `Faragopedia-Sales/backend/tests/test_setup_wizard.py`:

```python
from agent.setup_wizard import (
    complete_setup,
    EntityTypeDefinition,
    EntityTypeField,
    SetupPayload,
)

def _make_payload(**kwargs):
    defaults = dict(
        wiki_name="TestWiki",
        org_name="Test Org",
        org_description="A test organisation.",
        entity_types=[
            EntityTypeDefinition(
                folder_name="clients",
                display_name="Clients",
                description="Client organisations",
                singular="client",
                fields=[
                    EntityTypeField(name="name", type="string", required=True),
                    EntityTypeField(name="status", type="enum", values=["active", "inactive"]),
                ],
                sections=["Overview", "Notes"],
            )
        ],
    )
    defaults.update(kwargs)
    return SetupPayload(**defaults)

def test_complete_setup_writes_all_files(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    payload = _make_payload()

    complete_setup(str(schema_dir), str(wiki_dir), payload)

    assert (schema_dir / "wiki_config.json").exists()
    assert (schema_dir / "company_profile.md").exists()
    assert (schema_dir / "SCHEMA_TEMPLATE.md").exists()
    assert (schema_dir / "SCHEMA.md").exists()
    assert (wiki_dir / "clients" / "_type.yaml").exists()

def test_complete_setup_config_contents(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    complete_setup(str(schema_dir), str(wiki_dir), _make_payload())
    config = json.loads((schema_dir / "wiki_config.json").read_text())
    assert config["wiki_name"] == "TestWiki"
    assert config["org_name"] == "Test Org"
    assert config["setup_complete"] is True

def test_complete_setup_schema_template_substitution(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    complete_setup(str(schema_dir), str(wiki_dir), _make_payload())
    template = (schema_dir / "SCHEMA_TEMPLATE.md").read_text()
    assert "Test Org" in template
    assert "A test organisation." in template
    assert "{{ORG_NAME}}" not in template

def test_complete_setup_type_yaml_contents(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    complete_setup(str(schema_dir), str(wiki_dir), _make_payload())
    type_data = yaml.safe_load((wiki_dir / "clients" / "_type.yaml").read_text())
    assert type_data["name"] == "Clients"
    assert type_data["singular"] == "client"
    assert any(f["name"] == "name" for f in type_data["fields"])
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd Faragopedia-Sales/backend
pytest tests/test_setup_wizard.py -v -k "complete_setup"
```

Expected: FAIL — `ImportError` or `AttributeError: module has no attribute 'complete_setup'`

- [ ] **Step 3: Implement complete_setup() in setup_wizard.py**

Add these imports at the top of `setup_wizard.py`:

```python
from agent.schema_builder import build_schema_md
```

Add the function to `setup_wizard.py` (after `clear_setup`):

```python
def complete_setup(schema_dir: str, wiki_dir: str, payload) -> None:
    """Write all config files from a validated SetupPayload. Returns None; caller builds WikiManager."""
    # 1. Write company_profile.md
    profile_path = os.path.join(schema_dir, "company_profile.md")
    with open(profile_path, "w", encoding="utf-8") as f:
        f.write(f"# {payload.org_name}\n\n{payload.org_description}\n")

    # 2. Write SCHEMA_TEMPLATE.md from BASE_SCHEMA_TEMPLATE
    template_content = (
        BASE_SCHEMA_TEMPLATE
        .replace("{{ORG_NAME}}", payload.org_name)
        .replace("{{ORG_DESCRIPTION}}", payload.org_description)
    )
    template_path = os.path.join(schema_dir, "SCHEMA_TEMPLATE.md")
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(template_content)

    # 3. Create entity folders and write _type.yaml per entity type
    for et in payload.entity_types:
        folder_path = os.path.join(wiki_dir, et.folder_name)
        os.makedirs(folder_path, exist_ok=True)
        type_data = {
            "name": et.display_name,
            "description": et.description,
            "singular": et.singular,
            "fields": [_field_to_dict(f) for f in et.fields],
            "sections": et.sections,
        }
        yaml_path = os.path.join(folder_path, "_type.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(type_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # 4. Build SCHEMA.md
    schema_md = build_schema_md(wiki_dir, template_path)
    with open(os.path.join(schema_dir, "SCHEMA.md"), "w", encoding="utf-8") as f:
        f.write(schema_md)

    # 5. Write wiki_config.json
    config = {
        "wiki_name": payload.wiki_name,
        "org_name": payload.org_name,
        "setup_complete": True,
    }
    with open(os.path.join(schema_dir, "wiki_config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _field_to_dict(field) -> dict:
    d: dict = {"name": field.name, "type": field.type}
    if field.required is not None:
        d["required"] = field.required
    if field.values is not None:
        d["values"] = field.values
    if field.default is not None:
        d["default"] = field.default
    if field.description is not None:
        d["description"] = field.description
    return d
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd Faragopedia-Sales/backend
pytest tests/test_setup_wizard.py -v -k "complete_setup"
```

Expected: All 4 `complete_setup` tests PASS

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/agent/setup_wizard.py Faragopedia-Sales/backend/tests/test_setup_wizard.py
git commit -m "feat: implement complete_setup() orchestrator"
```

---

## Task 5: setup_routes.py — Pydantic models + all endpoints

**Files:**
- Create: `Faragopedia-Sales/backend/api/setup_routes.py`

- [ ] **Step 1: Create setup_routes.py with all models and endpoints**

Create `Faragopedia-Sales/backend/api/setup_routes.py`:

```python
import os
import shutil

from fastapi import APIRouter, HTTPException

from agent.setup_wizard import (
    EntityTypeDefinition,
    EntityTypeField,
    SetupPayload,
    SuggestRequest,
    SuggestedSchema,
    clear_setup,
    complete_setup,
    get_wiki_config,
    is_setup_complete,
    suggest_schema_llm,
)
from api.routes import (
    ARCHIVE_DIR,
    SNAPSHOTS_DIR,
    SOURCES_DIR,
    WIKI_DIR,
    set_wiki_manager,
)

setup_router = APIRouter()

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))   # backend/api/
_BACKEND_DIR = os.path.dirname(_THIS_DIR)                 # backend/
SCHEMA_DIR = os.path.join(_BACKEND_DIR, "schema")


@setup_router.get("/status")
def setup_status():
    config = get_wiki_config(SCHEMA_DIR)
    if config and config.get("setup_complete"):
        return {"setup_required": False, "wiki_name": config.get("wiki_name", "")}
    return {"setup_required": True}


@setup_router.get("/config")
def setup_config():
    config = get_wiki_config(SCHEMA_DIR)
    if not config:
        raise HTTPException(status_code=404, detail="Wiki not configured")
    return {"wiki_name": config.get("wiki_name", ""), "org_name": config.get("org_name", "")}


@setup_router.post("/suggest-schema")
def suggest_schema(req: SuggestRequest):
    try:
        from agent.wiki_manager import WikiManager
        # Build a temporary WikiManager just to get the LLM initialised
        import tempfile, os as _os
        with tempfile.TemporaryDirectory() as tmpdir:
            wm = WikiManager(
                sources_dir=tmpdir,
                wiki_dir=tmpdir,
                archive_dir=tmpdir,
                snapshots_dir=tmpdir,
                schema_dir=tmpdir,
            )
            llm = wm._init_llm()
        result = suggest_schema_llm(req.org_name, req.org_description, llm)
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="LLM unavailable") from exc


@setup_router.post("/complete")
def setup_complete(payload: SetupPayload):
    try:
        from agent.wiki_manager import WikiManager
        complete_setup(SCHEMA_DIR, WIKI_DIR, payload)
        wm = WikiManager(
            sources_dir=SOURCES_DIR,
            wiki_dir=WIKI_DIR,
            archive_dir=ARCHIVE_DIR,
            snapshots_dir=SNAPSHOTS_DIR,
            schema_dir=SCHEMA_DIR,
        )
        set_wiki_manager(wm)
        return {"success": True, "wiki_name": payload.wiki_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@setup_router.post("/clear")
def setup_clear():
    set_wiki_manager(None)
    folders = clear_setup(SCHEMA_DIR, WIKI_DIR)
    return {"existing_folders": folders}


@setup_router.delete("/folder/{folder_name}")
def delete_setup_folder(folder_name: str):
    import re
    if not re.match(r"^[a-z][a-z0-9-]*$", folder_name):
        raise HTTPException(status_code=400, detail="Invalid folder name")
    folder_path = os.path.join(WIKI_DIR, folder_name)
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail="Folder not found")
    shutil.rmtree(folder_path)
    return {"success": True}
```

- [ ] **Step 2: Add suggest_schema_llm() to setup_wizard.py**

Add to `Faragopedia-Sales/backend/agent/setup_wizard.py`:

```python
def suggest_schema_llm(org_name: str, org_description: str, llm) -> SuggestedSchema:
    from langchain.output_parsers import PydanticOutputParser
    from langchain.prompts import ChatPromptTemplate

    parser = PydanticOutputParser(pydantic_object=SuggestedSchema)

    system = (
        "You are a wiki schema designer. Given a description of an organisation, "
        "design the entity types that the wiki should track. Each entity type becomes a folder.\n\n"
        "Rules:\n"
        "- 3–7 entity types; fewer is better\n"
        "- Each field must have name and type (string | date | integer | enum | list)\n"
        "- Enum fields must have a values list\n"
        "- folder_name must be plural, lowercase, hyphen-separated (e.g. 'project-clients')\n"
        "- singular is the lowercase singular form\n"
        "- Every entity type must have a 'name' field (type: string, required: true) as the first field\n"
        "- Sections are markdown heading names for the page template\n"
    )
    human = (
        "Organisation: {org_name}\nDescription: {org_description}\n\n"
        "Design the wiki entity types for this organisation.\n{format_instructions}"
    )

    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", human)])
    chain = prompt | llm | parser
    return chain.invoke({
        "org_name": org_name,
        "org_description": org_description,
        "format_instructions": parser.get_format_instructions(),
    })
```

- [ ] **Step 3: Write integration tests for setup endpoints**

Create `Faragopedia-Sales/backend/tests/test_setup_routes.py`:

```python
import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

_tmp = tempfile.mkdtemp()
_schema_dir = os.path.join(_tmp, "schema")
_wiki_dir = os.path.join(_tmp, "wiki")
os.makedirs(_schema_dir, exist_ok=True)
os.makedirs(_wiki_dir, exist_ok=True)

# Patch module-level path constants BEFORE importing main
import api.setup_routes as sr
import api.routes as ar
sr.SCHEMA_DIR = _schema_dir
sr.WIKI_DIR = _wiki_dir
ar.WIKI_DIR = _wiki_dir

from main import app  # noqa: E402

client = TestClient(app)


def _clear_state():
    config = os.path.join(_schema_dir, "wiki_config.json")
    if os.path.exists(config):
        os.remove(config)
    import api.routes
    api.routes.set_wiki_manager(None)


def test_setup_status_required_when_no_config():
    _clear_state()
    r = client.get("/api/setup/status")
    assert r.status_code == 200
    assert r.json()["setup_required"] is True


def test_setup_status_not_required_when_config_present():
    _clear_state()
    config = {"wiki_name": "TestWiki", "org_name": "Test Org", "setup_complete": True}
    with open(os.path.join(_schema_dir, "wiki_config.json"), "w") as f:
        json.dump(config, f)
    r = client.get("/api/setup/status")
    assert r.status_code == 200
    assert r.json()["setup_required"] is False
    assert r.json()["wiki_name"] == "TestWiki"


def test_setup_config_returns_404_when_missing():
    _clear_state()
    r = client.get("/api/setup/config")
    assert r.status_code == 404


def test_wiki_routes_return_503_when_not_setup():
    _clear_state()
    r = client.get("/api/pages")
    assert r.status_code == 503


def test_setup_clear_returns_existing_folders():
    _clear_state()
    folder = os.path.join(_wiki_dir, "clients")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "_type.yaml"), "w") as f:
        f.write("name: Clients\n")
    r = client.post("/api/setup/clear")
    assert r.status_code == 200
    assert "clients" in r.json()["existing_folders"]


def test_delete_setup_folder():
    folder = os.path.join(_wiki_dir, "to-delete")
    os.makedirs(folder, exist_ok=True)
    r = client.delete("/api/setup/folder/to-delete")
    assert r.status_code == 200
    assert not os.path.exists(folder)


def test_delete_setup_folder_invalid_name():
    r = client.delete("/api/setup/folder/../etc")
    assert r.status_code in (400, 404)
```

- [ ] **Step 4: Run endpoint tests**

```
cd Faragopedia-Sales/backend
pytest tests/test_setup_routes.py -v
```

Expected: All tests PASS (suggest-schema test is omitted here as it requires a live LLM)

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/api/setup_routes.py Faragopedia-Sales/backend/agent/setup_wizard.py Faragopedia-Sales/backend/tests/test_setup_routes.py
git commit -m "feat: add setup_routes endpoints and suggest_schema_llm"
```

---

## Task 6: main.py — startup initialization + router registration

**Files:**
- Modify: `Faragopedia-Sales/backend/main.py`

- [ ] **Step 1: Update main.py**

Replace the entire file:

```python
import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router, set_wiki_manager, WIKI_DIR, SOURCES_DIR, ARCHIVE_DIR, SNAPSHOTS_DIR
from api.setup_routes import setup_router, SCHEMA_DIR
from agent.setup_wizard import migrate_existing, is_setup_complete

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(setup_router, prefix="/api/setup")

# On startup: migrate existing Farago install, then init WikiManager if setup complete
migrate_existing(SCHEMA_DIR)
if is_setup_complete(SCHEMA_DIR):
    from agent.wiki_manager import WikiManager
    wm = WikiManager(
        sources_dir=SOURCES_DIR,
        wiki_dir=WIKI_DIR,
        archive_dir=ARCHIVE_DIR,
        snapshots_dir=SNAPSHOTS_DIR,
        schema_dir=SCHEMA_DIR,
    )
    set_wiki_manager(wm)

@app.get("/")
def read_root():
    return {"message": "Hello World from FastAPI"}
```

- [ ] **Step 2: Verify the app starts without errors on a configured install**

```
cd Faragopedia-Sales/backend
uvicorn main:app --reload --port 8000
```

Expected: Server starts. `GET /api/setup/status` returns `{"setup_required": false, "wiki_name": "Faragopedia"}` (for existing Farago installs after migration). Ctrl-C to stop.

- [ ] **Step 3: Verify 503 on fresh install**

```bash
# Temporarily rename wiki_config.json
mv Faragopedia-Sales/backend/schema/wiki_config.json /tmp/wiki_config.json.bak
```

Restart uvicorn. `GET /api/setup/status` returns `{"setup_required": true}`. `GET /api/pages` returns 503. Restore the backup.

- [ ] **Step 4: Run full test suite**

```
cd Faragopedia-Sales/backend
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/main.py
git commit -m "feat: startup migration and WikiManager init in main.py"
```

---

## Task 7: Sidebar.tsx — wikiName prop + Reconfigure button

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Update Sidebar to accept wikiName prop and add Reconfigure button**

Replace the full file:

```tsx
import React from 'react';
import { Book, MessageSquare, Layers, Archive, Activity, Settings } from 'lucide-react';

interface SidebarProps {
  currentView: string;
  onViewChange: (view: string) => void;
  wikiName: string;
  onReconfigure: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ currentView, onViewChange, wikiName, onReconfigure }) => {
  const menuItems = [
    { name: 'Wiki', icon: <Book className="w-5 h-5" /> },
    { name: 'Sources', icon: <Layers className="w-5 h-5" /> },
    { name: 'Chat', icon: <MessageSquare className="w-5 h-5" /> },
    { name: 'Archive', icon: <Archive className="w-5 h-5" /> },
    { name: 'Lint', icon: <Activity className="w-5 h-5" /> },
  ];

  return (
    <div className="flex flex-col h-screen w-64 bg-gray-800 text-white shadow-xl">
      <div className="p-6 text-2xl font-bold border-b border-gray-700 flex items-center">
        <div className="w-8 h-8 bg-blue-600 rounded-lg mr-3 flex items-center justify-center text-sm">
          {wikiName.slice(0, 2).toUpperCase()}
        </div>
        {wikiName}
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

      <div className="p-4 border-t border-gray-700 space-y-2">
        <button
          onClick={onReconfigure}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700 text-sm transition-colors"
        >
          <Settings className="w-4 h-4" />
          Reconfigure Wiki
        </button>
        <p className="text-xs text-gray-500 text-center uppercase tracking-wider">
          {wikiName} v0.2.0
        </p>
      </div>
    </div>
  );
};

export default Sidebar;
```

- [ ] **Step 2: Verify TypeScript compiles**

```
cd Faragopedia-Sales/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/Sidebar.tsx
git commit -m "feat: Sidebar accepts wikiName prop and adds Reconfigure button"
```

---

## Task 8: App.tsx — setup state gating

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/App.tsx`

- [ ] **Step 1: Add setup state + reconfigure flow to App.tsx**

At the top of `App.tsx`, add the import:
```tsx
import SetupWizard from './components/SetupWizard';
```

Replace the `const App: React.FC = () => {` block's state declarations and opening `useEffect` with:

```tsx
const App: React.FC = () => {
  const [setupState, setSetupState] = useState<'loading' | 'required' | 'ready'>('loading');
  const [wikiName, setWikiName] = useState('Wiki');
  const [reconfigureMode, setReconfigureMode] = useState(false);
  const [existingFolders, setExistingFolders] = useState<string[]>([]);
  const [currentView, setCurrentView] = useState('Wiki');
  // ... rest of existing state unchanged
```

Add these handlers before `handleChat`:

```tsx
  const handleSetupComplete = async () => {
    const res = await fetch(`${API_BASE}/setup/config`);
    if (res.ok) {
      const data = await res.json();
      setWikiName(data.wiki_name);
    }
    setReconfigureMode(false);
    setSetupState('ready');
  };

  const handleReconfigure = async () => {
    const res = await fetch(`${API_BASE}/setup/clear`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      setExistingFolders(data.existing_folders);
    }
    setReconfigureMode(true);
    setSetupState('required');
  };
```

Add a startup `useEffect` as the FIRST useEffect in the component:

```tsx
  useEffect(() => {
    fetch(`${API_BASE}/setup/status`)
      .then(r => r.json())
      .then(data => {
        if (data.setup_required) {
          setSetupState('required');
        } else {
          setWikiName(data.wiki_name || 'Wiki');
          setSetupState('ready');
        }
      })
      .catch(() => setSetupState('required'));
  }, []);
```

Replace the main return block:

```tsx
  if (setupState === 'loading') {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (setupState === 'required') {
    return (
      <SetupWizard
        onComplete={handleSetupComplete}
        reconfigureMode={reconfigureMode}
        existingFolders={existingFolders}
      />
    );
  }

  return (
    <div className="flex h-screen bg-gray-50 font-sans antialiased text-gray-900 overflow-hidden">
      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}
      <div
        className={`fixed inset-y-0 left-0 z-50 flex-shrink-0 h-screen bg-gray-800 overflow-hidden transition-all duration-300 ease-in-out transform ${
          mobileMenuOpen ? 'translate-x-0 w-64' : '-translate-x-full w-64'
        } md:relative md:translate-x-0 ${sidebarOpen ? 'md:w-64' : 'md:w-0'}`}
      >
        <div className="w-64 h-full relative">
          <Sidebar
            currentView={currentView}
            onViewChange={(v) => { setCurrentView(v); setMobileMenuOpen(false); }}
            wikiName={wikiName}
            onReconfigure={handleReconfigure}
          />
          <button
            className="md:hidden absolute top-4 right-4 text-gray-400 hover:text-white p-2 rounded-lg bg-gray-800/80"
            onClick={() => setMobileMenuOpen(false)}
          >
            <X className="w-6 h-6" />
          </button>
        </div>
      </div>
      <main className="flex-grow flex flex-col overflow-hidden relative w-full">
        <div className="bg-white border-b px-4 py-4 flex items-center shrink-0 z-30 relative shadow-sm">
          <button
            onClick={() => {
              if (window.innerWidth < 768) setMobileMenuOpen(true);
              else setSidebarOpen(prev => !prev);
            }}
            className="p-2 -ml-2 text-gray-600 hover:bg-gray-100 rounded-lg flex items-center justify-center transition-colors focus:ring-2 focus:ring-blue-500 outline-none"
            aria-label="Toggle Navigation"
          >
            <Menu className="w-6 h-6" />
          </button>
          {!sidebarOpen && (
            <span className="hidden md:ml-4 font-bold text-gray-800 md:inline-block">{wikiName}</span>
          )}
          <span className="ml-4 font-bold text-gray-800 md:hidden">{wikiName}</span>
        </div>
        <div className="flex-grow overflow-hidden relative h-full">
          {renderContent()}
        </div>
        <ToastContainer toasts={toasts} />
      </main>
    </div>
  );
```

- [ ] **Step 2: Verify TypeScript compiles**

```
cd Faragopedia-Sales/frontend
npx tsc --noEmit
```

Expected: No errors (SetupWizard not yet created — add `// @ts-ignore` above the import temporarily if needed)

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/App.tsx
git commit -m "feat: App.tsx setup state gating and reconfigure flow"
```

---

## Task 9: SetupWizard.tsx

**Files:**
- Create: `Faragopedia-Sales/frontend/src/components/SetupWizard.tsx`

This is a large component — built in one task since all steps are tightly coupled via shared state.

- [ ] **Step 1: Create SetupWizard.tsx**

Create `Faragopedia-Sales/frontend/src/components/SetupWizard.tsx`:

```tsx
import React, { useEffect, useState } from 'react';
import { Loader2, Plus, Trash2, ChevronDown, ChevronRight } from 'lucide-react';
import { API_BASE } from '../config';

// ── Types ────────────────────────────────────────────────────────────────────

interface EntityField {
  name: string;
  type: 'string' | 'date' | 'integer' | 'enum' | 'list';
  required?: boolean;
  values?: string[];
  default?: string;
  description?: string;
}

interface EntityType {
  folder_name: string;
  display_name: string;
  description: string;
  singular: string;
  fields: EntityField[];
  sections: string[];
}

interface SetupWizardProps {
  onComplete: () => void;
  reconfigureMode?: boolean;
  existingFolders?: string[];
}

// ── Preset fallback schemas ───────────────────────────────────────────────────

const PRESETS: Record<string, EntityType[]> = {
  'Creative Production': [
    { folder_name: 'clients', display_name: 'Clients', description: 'Client organisations', singular: 'client', fields: [{ name: 'name', type: 'string', required: true }, { name: 'status', type: 'enum', values: ['active', 'inactive'] }], sections: ['Overview', 'Notes'] },
    { folder_name: 'contacts', display_name: 'Contacts', description: 'Individual people', singular: 'contact', fields: [{ name: 'name', type: 'string', required: true }, { name: 'role', type: 'string' }], sections: ['Bio', 'Notes'] },
    { folder_name: 'photographers', display_name: 'Photographers', description: 'Photographer roster', singular: 'photographer', fields: [{ name: 'name', type: 'string', required: true }], sections: ['Bio', 'Style Notes'] },
    { folder_name: 'productions', display_name: 'Productions', description: 'Shoots and projects', singular: 'production', fields: [{ name: 'name', type: 'string', required: true }, { name: 'date', type: 'date' }], sections: ['Brief', 'Team', 'Notes'] },
    { folder_name: 'prospects', display_name: 'Prospects', description: 'Pipeline prospects', singular: 'prospect', fields: [{ name: 'name', type: 'string', required: true }], sections: ['Overview', 'Outreach'] },
  ],
  'CRM': [
    { folder_name: 'organisations', display_name: 'Organisations', description: 'Companies and orgs', singular: 'organisation', fields: [{ name: 'name', type: 'string', required: true }], sections: ['Overview', 'Contacts', 'Notes'] },
    { folder_name: 'contacts', display_name: 'Contacts', description: 'Individual contacts', singular: 'contact', fields: [{ name: 'name', type: 'string', required: true }, { name: 'email', type: 'string' }], sections: ['Bio', 'Notes'] },
    { folder_name: 'deals', display_name: 'Deals', description: 'Sales opportunities', singular: 'deal', fields: [{ name: 'name', type: 'string', required: true }, { name: 'stage', type: 'enum', values: ['prospect', 'qualified', 'closed-won', 'closed-lost'] }], sections: ['Overview', 'Notes'] },
    { folder_name: 'notes', display_name: 'Notes', description: 'Meeting and call notes', singular: 'note', fields: [{ name: 'name', type: 'string', required: true }, { name: 'date', type: 'date' }], sections: ['Content'] },
  ],
  'Research': [
    { folder_name: 'topics', display_name: 'Topics', description: 'Research topics', singular: 'topic', fields: [{ name: 'name', type: 'string', required: true }], sections: ['Overview', 'Notes'] },
    { folder_name: 'papers', display_name: 'Papers', description: 'Academic papers', singular: 'paper', fields: [{ name: 'name', type: 'string', required: true }, { name: 'year', type: 'integer' }], sections: ['Abstract', 'Notes'] },
    { folder_name: 'authors', display_name: 'Authors', description: 'Researchers and authors', singular: 'author', fields: [{ name: 'name', type: 'string', required: true }], sections: ['Bio', 'Works'] },
    { folder_name: 'notes', display_name: 'Notes', description: 'Research notes', singular: 'note', fields: [{ name: 'name', type: 'string', required: true }], sections: ['Content'] },
  ],
  'Blank': [],
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function slugify(str: string): string {
  return str.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '').replace(/-+/g, '-');
}

function blankField(): EntityField {
  return { name: '', type: 'string' };
}

function blankEntityType(): EntityType {
  return {
    folder_name: '',
    display_name: '',
    description: '',
    singular: '',
    fields: [{ name: 'name', type: 'string', required: true }],
    sections: [],
  };
}

// ── Field editor sub-component ────────────────────────────────────────────────

const FieldEditor: React.FC<{
  field: EntityField;
  onChange: (f: EntityField) => void;
  onDelete: () => void;
}> = ({ field, onChange, onDelete }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border border-gray-200 rounded-lg mb-1">
      <div
        className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-gray-50"
        onClick={() => setExpanded(e => !e)}
      >
        {expanded ? <ChevronDown className="w-3 h-3 text-gray-400" /> : <ChevronRight className="w-3 h-3 text-gray-400" />}
        <span className="text-sm flex-1 font-mono">{field.name || <span className="text-gray-400 italic">unnamed</span>}</span>
        <span className="text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-600">{field.type}</span>
        {field.required && <span className="text-xs text-green-600">required</span>}
        <button onClick={(e) => { e.stopPropagation(); onDelete(); }} className="text-red-400 hover:text-red-600 ml-1"><Trash2 className="w-3 h-3" /></button>
      </div>
      {expanded && (
        <div className="px-3 pb-3 pt-1 grid grid-cols-2 gap-2 border-t border-gray-100">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Name</label>
            <input className="w-full border rounded px-2 py-1 text-sm" value={field.name} onChange={e => onChange({ ...field, name: e.target.value })} />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Type</label>
            <select className="w-full border rounded px-2 py-1 text-sm" value={field.type} onChange={e => onChange({ ...field, type: e.target.value as EntityField['type'] })}>
              {(['string', 'date', 'integer', 'enum', 'list'] as const).map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          {field.type === 'enum' && (
            <div className="col-span-2">
              <label className="text-xs text-gray-500 block mb-1">Enum values (comma-separated)</label>
              <input className="w-full border rounded px-2 py-1 text-sm" value={(field.values || []).join(', ')} onChange={e => onChange({ ...field, values: e.target.value.split(',').map(v => v.trim()).filter(Boolean) })} />
            </div>
          )}
          <div className="col-span-2 flex items-center gap-2">
            <input type="checkbox" id={`req-${field.name}`} checked={!!field.required} onChange={e => onChange({ ...field, required: e.target.checked })} />
            <label htmlFor={`req-${field.name}`} className="text-xs text-gray-500">Required</label>
          </div>
          <div className="col-span-2">
            <label className="text-xs text-gray-500 block mb-1">Description (optional)</label>
            <input className="w-full border rounded px-2 py-1 text-sm" value={field.description || ''} onChange={e => onChange({ ...field, description: e.target.value })} />
          </div>
        </div>
      )}
    </div>
  );
};

// ── Entity card sub-component ─────────────────────────────────────────────────

const EntityCard: React.FC<{
  et: EntityType;
  badge?: string;
  onChange: (et: EntityType) => void;
  onDelete: () => void;
}> = ({ et, badge, onChange, onDelete }) => {
  const [expanded, setExpanded] = useState(true);
  const [newSection, setNewSection] = useState('');

  return (
    <div className="border border-gray-200 rounded-xl bg-white shadow-sm mb-3">
      <div className="flex items-center gap-3 px-4 py-3 cursor-pointer" onClick={() => setExpanded(e => !e)}>
        {expanded ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
        <div className="flex-1">
          <div className="text-xs text-gray-400 font-mono">folder: {et.folder_name || '—'}</div>
          <div className="font-semibold text-gray-800">{et.display_name || <span className="text-gray-400 italic">Unnamed</span>}</div>
        </div>
        {badge && <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">{badge}</span>}
        {!expanded && <span className="text-xs text-gray-400">{et.fields.length} fields · {et.sections.length} sections</span>}
        <button onClick={(e) => { e.stopPropagation(); onDelete(); }} className="text-red-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-3 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 block mb-1">Display Name</label>
              <input
                className="w-full border rounded px-2 py-1.5 text-sm"
                value={et.display_name}
                onChange={e => {
                  const display_name = e.target.value;
                  onChange({ ...et, display_name, folder_name: slugify(display_name), singular: slugify(display_name).replace(/-?s$/, '') });
                }}
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Folder slug (editable)</label>
              <input className="w-full border rounded px-2 py-1.5 text-sm font-mono" value={et.folder_name} onChange={e => onChange({ ...et, folder_name: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Description</label>
            <textarea className="w-full border rounded px-2 py-1.5 text-sm resize-none" rows={2} value={et.description} onChange={e => onChange({ ...et, description: e.target.value })} />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-2 uppercase tracking-wide">Fields</div>
            {et.fields.map((f, i) => (
              <FieldEditor
                key={i}
                field={f}
                onChange={updated => { const fields = [...et.fields]; fields[i] = updated; onChange({ ...et, fields }); }}
                onDelete={() => { const fields = et.fields.filter((_, idx) => idx !== i); onChange({ ...et, fields }); }}
              />
            ))}
            <button
              className="w-full mt-1 border border-dashed border-gray-300 rounded-lg py-1.5 text-sm text-gray-400 hover:text-gray-600 hover:border-gray-400 flex items-center justify-center gap-1"
              onClick={() => onChange({ ...et, fields: [...et.fields, blankField()] })}
            >
              <Plus className="w-3 h-3" /> Add field
            </button>
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-2 uppercase tracking-wide">Sections</div>
            <div className="flex flex-wrap gap-2">
              {et.sections.map((s, i) => (
                <span key={i} className="inline-flex items-center gap-1 bg-gray-100 rounded-full px-3 py-1 text-sm">
                  {s}
                  <button onClick={() => onChange({ ...et, sections: et.sections.filter((_, idx) => idx !== i) })} className="text-gray-400 hover:text-red-500">×</button>
                </span>
              ))}
              <form onSubmit={e => { e.preventDefault(); if (newSection.trim()) { onChange({ ...et, sections: [...et.sections, newSection.trim()] }); setNewSection(''); } }}>
                <input
                  className="border border-dashed border-gray-300 rounded-full px-3 py-1 text-sm w-28"
                  placeholder="+ section"
                  value={newSection}
                  onChange={e => setNewSection(e.target.value)}
                />
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Main SetupWizard component ────────────────────────────────────────────────

const SetupWizard: React.FC<SetupWizardProps> = ({ onComplete, reconfigureMode = false, existingFolders = [] }) => {
  const [step, setStep] = useState(1);
  const [wikiName, setWikiName] = useState('');
  const [orgName, setOrgName] = useState('');
  const [orgDescription, setOrgDescription] = useState('');
  const [entityTypes, setEntityTypes] = useState<EntityType[]>([]);
  const [folderActions, setFolderActions] = useState<Record<string, 'keep' | 'delete'>>({});
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmFailed, setLlmFailed] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState('');

  // Prefill in reconfigure mode
  useEffect(() => {
    if (reconfigureMode) {
      fetch(`${API_BASE}/setup/config`)
        .then(r => r.json())
        .then(d => { setWikiName(d.wiki_name || ''); setOrgName(d.org_name || ''); })
        .catch(() => {});
      const initial: Record<string, 'keep' | 'delete'> = {};
      existingFolders.forEach(f => { initial[f] = 'keep'; });
      setFolderActions(initial);
    }
  }, [reconfigureMode, existingFolders]);

  const handleGenerateSchema = async () => {
    setLlmLoading(true);
    setLlmFailed(false);
    try {
      const res = await fetch(`${API_BASE}/setup/suggest-schema`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ org_name: orgName, org_description: orgDescription }),
      });
      if (!res.ok) throw new Error('LLM unavailable');
      const data = await res.json();
      setEntityTypes(data.entity_types || []);
    } catch {
      setLlmFailed(true);
      setEntityTypes([]);
    } finally {
      setLlmLoading(false);
      setStep(2);
    }
  };

  const handleLaunch = async () => {
    setLaunching(true);
    setError('');
    try {
      // Delete folders marked for deletion (reconfigure mode)
      for (const [folder, action] of Object.entries(folderActions)) {
        if (action === 'delete') {
          await fetch(`${API_BASE}/setup/folder/${folder}`, { method: 'DELETE' });
        }
      }
      const res = await fetch(`${API_BASE}/setup/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wiki_name: wikiName,
          org_name: orgName,
          org_description: orgDescription,
          entity_types: entityTypes,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Setup failed');
      }
      onComplete();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Setup failed');
    } finally {
      setLaunching(false);
    }
  };

  // ── Step 1: Identity ──────────────────────────────────────────────────────

  if (step === 1) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-8">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 w-full max-w-lg p-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">{reconfigureMode ? 'Reconfigure Wiki' : 'Welcome — Set up your wiki'}</h1>
          <p className="text-gray-500 mb-6 text-sm">Tell us about your organisation. We'll generate a schema tailored to what you track.</p>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Wiki name</label>
              <input className="w-full border rounded-lg px-3 py-2" placeholder="e.g. Acme Wiki" value={wikiName} onChange={e => setWikiName(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Organisation name</label>
              <input className="w-full border rounded-lg px-3 py-2" placeholder="e.g. Acme Corp" value={orgName} onChange={e => setOrgName(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">What does your organisation do?</label>
              <textarea className="w-full border rounded-lg px-3 py-2 resize-none" rows={4} placeholder="Describe your organisation and what kind of information you track..." value={orgDescription} onChange={e => setOrgDescription(e.target.value)} />
            </div>
          </div>

          <button
            onClick={handleGenerateSchema}
            disabled={!wikiName.trim() || !orgName.trim() || !orgDescription.trim() || llmLoading}
            className="mt-6 w-full bg-blue-600 text-white rounded-lg py-2.5 font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {llmLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating schema...</> : 'Generate Schema →'}
          </button>
        </div>
      </div>
    );
  }

  // ── Step 2: Schema Review ──────────────────────────────────────────────────

  if (step === 2) {
    const matchedFolders = new Set(entityTypes.map(et => et.folder_name));

    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-2xl font-bold text-gray-900 mb-1">Review your schema</h1>
          <p className="text-gray-500 text-sm mb-6">Edit entity types, fields, and sections. Add or remove types as needed.</p>

          {llmFailed && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
              <p className="text-sm text-yellow-800 mb-3">LLM unavailable — choose a preset to get started:</p>
              <div className="flex flex-wrap gap-2">
                {Object.keys(PRESETS).map(k => (
                  <button key={k} onClick={() => setEntityTypes(PRESETS[k])} className="px-3 py-1.5 rounded-lg border border-yellow-300 text-sm text-yellow-800 hover:bg-yellow-100">{k}</button>
                ))}
              </div>
            </div>
          )}

          <div className={reconfigureMode ? 'flex gap-6' : ''}>
            <div className={reconfigureMode ? 'flex-1' : ''}>
              {reconfigureMode && <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">New Schema</div>}
              {entityTypes.map((et, i) => {
                const badge = reconfigureMode
                  ? existingFolders.includes(et.folder_name) ? 'matches existing' : 'new'
                  : undefined;
                return (
                  <EntityCard
                    key={i}
                    et={et}
                    badge={badge}
                    onChange={updated => { const arr = [...entityTypes]; arr[i] = updated; setEntityTypes(arr); }}
                    onDelete={() => setEntityTypes(entityTypes.filter((_, idx) => idx !== i))}
                  />
                );
              })}
              <button
                onClick={() => setEntityTypes([...entityTypes, blankEntityType()])}
                className="w-full border-2 border-dashed border-gray-300 rounded-xl py-4 text-gray-400 hover:text-gray-600 hover:border-gray-400 flex items-center justify-center gap-2"
              >
                <Plus className="w-4 h-4" /> Add entity type
              </button>
            </div>

            {reconfigureMode && (
              <div className="w-56 flex-shrink-0">
                <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">Existing Folders</div>
                {existingFolders.map(folder => {
                  const matched = matchedFolders.has(folder);
                  return (
                    <div key={folder} className={`border rounded-lg p-3 mb-2 ${matched ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
                      <div className="font-mono text-sm mb-1">{folder}</div>
                      {matched ? (
                        <div className="text-xs text-green-600">→ kept (matched)</div>
                      ) : (
                        <div className="flex gap-1 mt-1">
                          <button
                            onClick={() => setFolderActions(a => ({ ...a, [folder]: 'keep' }))}
                            className={`flex-1 text-xs py-1 rounded ${folderActions[folder] === 'keep' ? 'bg-green-600 text-white' : 'border border-green-400 text-green-700'}`}
                          >Keep</button>
                          <button
                            onClick={() => setFolderActions(a => ({ ...a, [folder]: 'delete' }))}
                            className={`flex-1 text-xs py-1 rounded ${folderActions[folder] === 'delete' ? 'bg-red-600 text-white' : 'border border-red-400 text-red-700'}`}
                          >Delete</button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex justify-between mt-6">
            <button onClick={() => setStep(1)} className="px-4 py-2 border rounded-lg text-gray-600 hover:bg-gray-50">← Back</button>
            <button
              onClick={() => setStep(3)}
              disabled={entityTypes.length === 0}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              Review & Launch →
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Step 3: Confirm ────────────────────────────────────────────────────────

  const toDelete = Object.entries(folderActions).filter(([, a]) => a === 'delete').map(([f]) => f);
  const toKeep = existingFolders.filter(f => folderActions[f] === 'keep' && !entityTypes.find(et => et.folder_name === f));

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-8">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 w-full max-w-lg p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Ready to launch</h1>
        <p className="text-gray-500 text-sm mb-6">Review what will be created, then click Launch Wiki.</p>

        <div className="bg-gray-50 rounded-xl p-4 font-mono text-sm space-y-1 mb-4">
          <div className="font-bold text-gray-700 mb-2">{wikiName}</div>
          <div className="text-gray-500">wiki/</div>
          {entityTypes.map(et => (
            <div key={et.folder_name} className="text-green-700 pl-2">+ {et.folder_name}/ <span className="text-gray-400">({et.fields.length} fields)</span></div>
          ))}
          {toKeep.map(f => <div key={f} className="text-blue-600 pl-2">~ {f}/ <span className="text-gray-400">(kept)</span></div>)}
          {toDelete.map(f => <div key={f} className="text-red-500 pl-2">- {f}/ <span className="text-gray-400">(deleted)</span></div>)}
        </div>

        {error && <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm mb-4">{error}</div>}

        <div className="flex gap-3">
          <button onClick={() => setStep(2)} className="px-4 py-2 border rounded-lg text-gray-600 hover:bg-gray-50">← Back</button>
          <button
            onClick={handleLaunch}
            disabled={launching}
            className="flex-1 bg-blue-600 text-white rounded-lg py-2.5 font-medium hover:bg-blue-700 disabled:bg-gray-300 flex items-center justify-center gap-2"
          >
            {launching ? <><Loader2 className="w-4 h-4 animate-spin" /> Launching...</> : 'Launch Wiki'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SetupWizard;
```

- [ ] **Step 2: Verify TypeScript compiles**

```
cd Faragopedia-Sales/frontend
npx tsc --noEmit
```

Expected: No errors. Remove any `// @ts-ignore` added in Task 8.

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/SetupWizard.tsx
git commit -m "feat: add SetupWizard component with 3-step wizard and full field editing"
```

---

## Task 10: End-to-end verification

- [ ] **Step 1: Run all backend tests**

```
cd Faragopedia-Sales/backend
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 2: Fresh install test — wizard appears**

```bash
# Temporarily move config and SCHEMA.md out
mv Faragopedia-Sales/backend/schema/wiki_config.json /tmp/wiki_config.json.bak
mv Faragopedia-Sales/backend/schema/SCHEMA.md /tmp/SCHEMA.md.bak
```

Start backend and frontend:
```bash
cd Faragopedia-Sales/backend && uvicorn main:app --reload --port 8000
cd Faragopedia-Sales/frontend && npm run dev
```

Open browser → wizard appears full-screen. Restore files after test:
```bash
mv /tmp/wiki_config.json.bak Faragopedia-Sales/backend/schema/wiki_config.json
mv /tmp/SCHEMA.md.bak Faragopedia-Sales/backend/schema/SCHEMA.md
```

- [ ] **Step 3: Complete wizard flow**

With fresh state (Step 2 above): fill Step 1 with org name + description → click "Generate Schema" → verify Step 2 shows LLM entity types → edit a field → proceed to Step 3 → click "Launch Wiki" → verify normal app loads with org name in sidebar.

- [ ] **Step 4: Reconfigure flow**

In normal app, click "Reconfigure Wiki" in sidebar → wizard re-opens in reconfigure mode → Step 2 shows split layout with existing folders on right → complete wizard → app returns to normal state.

- [ ] **Step 5: LLM fallback test**

Set `AI_PROVIDER=invalid` in env. Repeat Step 3 → on "Generate Schema", verify Step 2 shows preset picker buttons instead of LLM output. Restore env.

- [ ] **Step 6: Farago migration test**

Confirm existing Farago installs (with `company_profile.md` but no `wiki_config.json`) auto-migrate: remove `wiki_config.json` only, restart backend → `migrate_existing()` creates it → `GET /api/setup/status` returns `setup_required: false`.

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat: complete first-run setup wizard implementation"
```
