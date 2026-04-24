# Entity Type Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a `_template.md` for each entity type at setup time; use it to pre-populate new pages in the editor, hide it from the wiki sidebar, and auto-rename the file to the correct wiki slug when the user first saves.

**Architecture:** New `generate_entity_template` / `write_entity_templates` functions in `schema_builder.py` render templates from `_type.yaml` data. `complete_setup()` calls them after writing `_type.yaml` files. `list_pages()` filters `_`-prefixed filenames. `create_new_page()` reads `_template.md` if present, else falls back to the existing stub. On save, `auto_rename_if_untitled()` in `WikiManager` detects `Untitled*.md` filenames, extracts the `name` frontmatter field, slugifies it, and renames the file; the new filename is returned to the frontend which updates its state accordingly.

**Tech Stack:** Python 3.11, pytest, PyYAML, FastAPI (no new dependencies)

---

## File Map

| File | Change |
|---|---|
| `backend/agent/schema_builder.py` | Add `generate_entity_template()` and `write_entity_templates()` |
| `backend/agent/setup_wizard.py` | Import + call `write_entity_templates()` inside `complete_setup()` |
| `backend/agent/wiki_manager.py` | Filter `_`-prefixed files in `list_pages()`; read template in `create_new_page()`; add `_slugify()` + `auto_rename_if_untitled()` |
| `backend/api/routes.py` | Call `auto_rename_if_untitled()` after save; return `new_filename` in PUT response |
| `frontend/src/components/WikiView.tsx` | Handle `new_filename` in `handleSave`; update `selectedPage` and reload content |
| `backend/tests/test_schema_builder.py` | Add tests for two new functions |
| `backend/tests/test_setup_wizard.py` | Add test that `complete_setup` writes templates |
| `backend/tests/test_wiki_manager.py` | Add tests for `list_pages` filter, `create_new_page` template usage, `_slugify`, and `auto_rename_if_untitled` |

---

### Task 1: `generate_entity_template` in schema_builder.py

**Files:**
- Modify: `backend/agent/schema_builder.py` (append after line 212)
- Test: `backend/tests/test_schema_builder.py`

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/test_schema_builder.py`. Add this import at the top alongside the existing imports:

```python
from agent.schema_builder import (
    load_type_yaml,
    discover_entity_types,
    render_type_schema_section,
    build_schema_md,
    generate_entity_template,   # new
)
```

Append these tests at the bottom of the file:

```python
def test_generate_entity_template_frontmatter():
    fields = [
        {"name": "type", "type": "string", "default": "client"},
        {"name": "name", "type": "string"},
        {"name": "tier", "type": "enum", "values": ["A", "B", "C"]},
        {"name": "tags", "type": "list"},
        {"name": "status", "type": "string", "default": "active"},
    ]
    result = generate_entity_template("clients", "client", fields, [])
    assert result.startswith("---\ntype: client\n")
    assert "name: \n" in result
    assert "tier:  # options: A, B, C\n" in result
    assert "tags: []\n" in result
    assert "status: active\n" in result
    assert result.count("type: client") == 1  # not duplicated


def test_generate_entity_template_sections():
    result = generate_entity_template(
        "clients", "client", [],
        ["Overview", "Key Contacts", "Notes"],
    )
    assert "## Overview\n_Add overview here..._" in result
    assert "## Key Contacts\n_Add key contacts here..._" in result
    assert "## Notes\n_Add notes here..._" in result


def test_generate_entity_template_no_sections():
    result = generate_entity_template("contacts", "contact", [{"name": "name", "type": "string"}], [])
    assert "---\ntype: contact\nname: \n---" in result
    assert "##" not in result


def test_generate_entity_template_h1_blank():
    result = generate_entity_template("clients", "client", [], ["Overview"])
    # Body starts with a blank H1
    assert "\n\n# \n" in result
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_schema_builder.py::test_generate_entity_template_frontmatter tests/test_schema_builder.py::test_generate_entity_template_sections -v
```

Expected: `ImportError` or `FAILED` — `generate_entity_template` not yet defined.

- [ ] **Step 3: Implement `generate_entity_template`**

Open `backend/agent/schema_builder.py`. Append this function after `build_schema_md` (after line 212):

```python
def generate_entity_template(
    folder_name: str,
    singular: str,
    fields: list,
    sections: list,
) -> str:
    """Render a _template.md for an entity type.

    fields is a list of dicts with keys: name, type, default (opt), values (opt).
    """
    fm_lines = [f"type: {singular}"]
    for field in fields:
        fname = field.get("name", "")
        if fname == "type":
            continue  # already emitted as first line
        ftype = field.get("type", "string")
        if ftype == "list":
            fm_lines.append(f"{fname}: []")
        elif ftype == "enum":
            values = field.get("values", [])
            fm_lines.append(f"{fname}:  # options: {', '.join(str(v) for v in values)}")
        elif "default" in field:
            fm_lines.append(f"{fname}: {field['default']}")
        else:
            fm_lines.append(f"{fname}: ")

    lines = ["---"] + fm_lines + ["---", "", "# ", ""]
    for section in sections:
        lines.append(f"## {section}")
        lines.append(f"_Add {section.lower()} here..._")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_schema_builder.py::test_generate_entity_template_frontmatter tests/test_schema_builder.py::test_generate_entity_template_sections tests/test_schema_builder.py::test_generate_entity_template_no_sections tests/test_schema_builder.py::test_generate_entity_template_h1_blank -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2" && git add "Faragopedia-Sales/backend/agent/schema_builder.py" "Faragopedia-Sales/backend/tests/test_schema_builder.py" && git commit -m "feat: add generate_entity_template to schema_builder"
```

---

### Task 2: `write_entity_templates` in schema_builder.py

**Files:**
- Modify: `backend/agent/schema_builder.py`
- Test: `backend/tests/test_schema_builder.py`

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/test_schema_builder.py`. Update the import to include `write_entity_templates`:

```python
from agent.schema_builder import (
    load_type_yaml,
    discover_entity_types,
    render_type_schema_section,
    build_schema_md,
    generate_entity_template,
    write_entity_templates,   # new
)
```

Append these tests:

```python
def test_write_entity_templates_creates_files(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "clients").mkdir(parents=True)
    (wiki / "contacts").mkdir()

    entity_dicts = [
        {
            "folder_name": "clients",
            "singular": "client",
            "fields": [{"name": "name", "type": "string"}],
            "sections": ["Overview"],
        },
        {
            "folder_name": "contacts",
            "singular": "contact",
            "fields": [{"name": "name", "type": "string"}],
            "sections": ["Bio"],
        },
    ]
    write_entity_templates(str(wiki), entity_dicts)

    clients_tmpl = wiki / "clients" / "_template.md"
    contacts_tmpl = wiki / "contacts" / "_template.md"
    assert clients_tmpl.exists()
    assert contacts_tmpl.exists()
    assert "type: client" in clients_tmpl.read_text()
    assert "## Overview" in clients_tmpl.read_text()
    assert "type: contact" in contacts_tmpl.read_text()
    assert "## Bio" in contacts_tmpl.read_text()


def test_write_entity_templates_creates_missing_folder(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    # Entity folder does NOT exist yet
    entity_dicts = [
        {
            "folder_name": "deals",
            "singular": "deal",
            "fields": [],
            "sections": [],
        }
    ]
    write_entity_templates(str(wiki), entity_dicts)
    assert (wiki / "deals" / "_template.md").exists()


def test_write_entity_templates_overwrites_existing(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "clients").mkdir(parents=True)
    (wiki / "clients" / "_template.md").write_text("old content")

    entity_dicts = [
        {
            "folder_name": "clients",
            "singular": "client",
            "fields": [{"name": "name", "type": "string"}],
            "sections": [],
        }
    ]
    write_entity_templates(str(wiki), entity_dicts)
    content = (wiki / "clients" / "_template.md").read_text()
    assert content != "old content"
    assert "type: client" in content
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_schema_builder.py::test_write_entity_templates_creates_files -v
```

Expected: `ImportError` — `write_entity_templates` not yet defined.

- [ ] **Step 3: Implement `write_entity_templates`**

Open `backend/agent/schema_builder.py`. Append this function after `generate_entity_template`:

```python
def write_entity_templates(wiki_dir: str, entity_type_dicts: list) -> None:
    """Write _template.md for each entity type.

    entity_type_dicts is a list of dicts with keys:
      folder_name (str), singular (str), fields (list of field dicts), sections (list of str).
    """
    for et in entity_type_dicts:
        folder_path = os.path.join(wiki_dir, et["folder_name"])
        os.makedirs(folder_path, exist_ok=True)
        content = generate_entity_template(
            folder_name=et["folder_name"],
            singular=et["singular"],
            fields=et.get("fields", []),
            sections=et.get("sections", []),
        )
        template_path = os.path.join(folder_path, "_template.md")
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(content)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_schema_builder.py::test_write_entity_templates_creates_files tests/test_schema_builder.py::test_write_entity_templates_creates_missing_folder tests/test_schema_builder.py::test_write_entity_templates_overwrites_existing -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2" && git add "Faragopedia-Sales/backend/agent/schema_builder.py" "Faragopedia-Sales/backend/tests/test_schema_builder.py" && git commit -m "feat: add write_entity_templates to schema_builder"
```

---

### Task 3: Call `write_entity_templates` in `complete_setup()`

**Files:**
- Modify: `backend/agent/setup_wizard.py:217-230` (inside the entity type loop in `complete_setup`)
- Test: `backend/tests/test_setup_wizard.py`

- [ ] **Step 1: Write the failing test**

Open `backend/tests/test_setup_wizard.py`. Append this test:

```python
def test_complete_setup_writes_entity_templates(tmp_path):
    schema_dir = tmp_path / "schema"
    wiki_dir = tmp_path / "wiki"
    schema_dir.mkdir()
    wiki_dir.mkdir()

    payload = SetupPayload(
        wiki_name="TestWiki",
        org_name="Test Org",
        org_description="A test organisation",
        entity_types=[
            EntityTypeDefinition(
                folder_name="clients",
                display_name="Clients",
                description="Client companies",
                singular="client",
                fields=[
                    EntityTypeField(name="name", type="string", required=True),
                    EntityTypeField(name="tier", type="enum", values=["A", "B", "C"]),
                    EntityTypeField(name="tags", type="list"),
                ],
                sections=["Overview", "Notes"],
            ),
        ],
    )
    complete_setup(str(schema_dir), str(wiki_dir), payload)

    template = wiki_dir / "clients" / "_template.md"
    assert template.exists(), "_template.md was not created"
    content = template.read_text()
    assert "type: client" in content
    assert "name: \n" in content
    assert "tier:  # options: A, B, C" in content
    assert "tags: []" in content
    assert "## Overview" in content
    assert "## Notes" in content
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_setup_wizard.py::test_complete_setup_writes_entity_templates -v
```

Expected: FAILED — `_template.md` not found.

- [ ] **Step 3: Update `complete_setup` to call `write_entity_templates`**

Open `backend/agent/setup_wizard.py`.

Add `write_entity_templates` to the existing import from `schema_builder` (line 7):

```python
from agent.schema_builder import build_schema_md, write_entity_templates
```

At the end of `complete_setup()`, after the `# 4. Build SCHEMA.md` block and before `# 5. Write wiki_config.json` (around line 232), add:

```python
    # 4b. Write _template.md for each entity type
    entity_type_dicts = [
        {
            "folder_name": et.folder_name,
            "singular": et.singular,
            "fields": [_field_to_dict(f) for f in et.fields],
            "sections": et.sections,
        }
        for et in payload.entity_types
    ]
    write_entity_templates(wiki_dir, entity_type_dicts)
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_setup_wizard.py::test_complete_setup_writes_entity_templates -v
```

Expected: PASSED.

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2" && git add "Faragopedia-Sales/backend/agent/setup_wizard.py" "Faragopedia-Sales/backend/tests/test_setup_wizard.py" && git commit -m "feat: generate _template.md for each entity type during setup"
```

---

### Task 4: Filter `_`-prefixed files from `list_pages()`

**Files:**
- Modify: `backend/agent/wiki_manager.py:1171` (inside `list_pages`)
- Test: `backend/tests/test_wiki_manager.py`

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/test_wiki_manager.py`. Find the existing `test_list_pages_excludes_meta` test (around line 1029) for reference on how `WikiManager` is constructed in tests. Append these new tests near it:

```python
def test_list_pages_excludes_underscore_prefixed_files(temp_dirs):
    """_template.md and any _-prefixed .md files must not appear in list_pages."""
    sources, wiki = temp_dirs
    clients = os.path.join(wiki, "clients")
    os.makedirs(clients, exist_ok=True)
    # Write _type.yaml so entity type is valid
    with open(os.path.join(clients, "_type.yaml"), "w") as f:
        f.write("name: Clients\nsingular: client\nfields: []\nsections: []\n")
    # Write a real page
    with open(os.path.join(clients, "acme.md"), "w") as f:
        f.write("---\ntype: client\nname: Acme\n---\n")
    # Write a template file that should be hidden
    with open(os.path.join(clients, "_template.md"), "w") as f:
        f.write("---\ntype: client\nname: \n---\n")

    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)

    pages = manager.list_pages()
    assert "clients/acme.md" in pages
    assert "clients/_template.md" not in pages
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_wiki_manager.py::test_list_pages_excludes_underscore_prefixed_files -v
```

Expected: FAILED — `clients/_template.md` appears in `pages`.

- [ ] **Step 3: Add filter to `list_pages()`**

Open `backend/agent/wiki_manager.py`. Find `list_pages()` at line 1165. Change line 1171 from:

```python
                if not filename.endswith(".md"):
                    continue
```

to:

```python
                if not filename.endswith(".md") or filename.startswith("_"):
                    continue
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_wiki_manager.py::test_list_pages_excludes_underscore_prefixed_files -v
```

Expected: PASSED.

- [ ] **Step 5: Confirm existing list_pages tests still pass**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_wiki_manager.py -k "list_pages" -v
```

Expected: All PASSED.

- [ ] **Step 6: Commit**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2" && git add "Faragopedia-Sales/backend/agent/wiki_manager.py" "Faragopedia-Sales/backend/tests/test_wiki_manager.py" && git commit -m "fix: hide _-prefixed files from list_pages"
```

---

### Task 5: Pre-populate new pages from `_template.md`

**Files:**
- Modify: `backend/agent/wiki_manager.py:907-910` (inside `create_new_page`)
- Test: `backend/tests/test_wiki_manager.py`

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/test_wiki_manager.py`. Append these tests near the existing `test_create_new_page_in_entity_subdir` test (around line 733):

```python
@pytest.mark.asyncio
async def test_create_new_page_uses_template_when_present(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "clients" / "_type.yaml").write_text(
        "name: Clients\nsingular: client\nfields: []\nsections: []\n"
    )
    template_content = (
        "---\ntype: client\nname: \ntier:  # options: A, B, C\n---\n\n# \n\n"
        "## Overview\n_Add overview here..._\n"
    )
    (wiki / "clients" / "_template.md").write_text(template_content)

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir),
        )

    filename = await manager.create_new_page(entity_type="clients")
    assert filename == "clients/Untitled.md"
    written = (wiki / "clients" / "Untitled.md").read_text()
    assert written == template_content


@pytest.mark.asyncio
async def test_create_new_page_falls_back_when_no_template(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "clients" / "_type.yaml").write_text(
        "name: Clients\nsingular: client\nfields: []\nsections: []\n"
    )
    # No _template.md present

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir),
        )

    filename = await manager.create_new_page(entity_type="clients")
    written = (wiki / "clients" / "Untitled.md").read_text()
    assert "type: client" in written
    assert "name: " in written
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_wiki_manager.py::test_create_new_page_uses_template_when_present tests/test_wiki_manager.py::test_create_new_page_falls_back_when_no_template -v
```

Expected: `test_create_new_page_uses_template_when_present` FAILED (content is stub, not template).
`test_create_new_page_falls_back_when_no_template` should PASS already.

- [ ] **Step 3: Update `create_new_page` to read template**

Open `backend/agent/wiki_manager.py`. Find `create_new_page` at line 888. Replace lines 907-910:

```python
            singular = entity_types[entity_type].get("singular", entity_type.rstrip("s"))
            content = f"---\ntype: {singular}\nname: \n---\n\n# Untitled\n\nNew page content here.\n"
```

with:

```python
            singular = entity_types[entity_type].get("singular", entity_type.rstrip("s"))
            template_path = os.path.join(sub_dir, "_template.md")
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as _tf:
                    content = _tf.read()
            else:
                content = f"---\ntype: {singular}\nname: \n---\n\n# Untitled\n\nNew page content here.\n"
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_wiki_manager.py::test_create_new_page_uses_template_when_present tests/test_wiki_manager.py::test_create_new_page_falls_back_when_no_template -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Run the full test suite**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: All previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2" && git add "Faragopedia-Sales/backend/agent/wiki_manager.py" "Faragopedia-Sales/backend/tests/test_wiki_manager.py" && git commit -m "feat: pre-populate new pages from _template.md"
```

---

### Task 6: Auto-rename Untitled pages on first save

When a user fills in the `name` field and saves an `Untitled*.md` page, the backend renames the file to the correct lowercase-hyphenated slug, and the frontend navigates to the new filename.

**Files:**
- Modify: `backend/agent/wiki_manager.py` (add `_slugify` static method + `auto_rename_if_untitled` method)
- Modify: `backend/api/routes.py:784-797` (`update_page` endpoint)
- Modify: `frontend/src/components/WikiView.tsx:296-322` (`handleSave`)
- Test: `backend/tests/test_wiki_manager.py`

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/test_wiki_manager.py`. Append these tests:

```python
def test_slugify_basic():
    from agent.wiki_manager import WikiManager
    assert WikiManager._slugify("Acme Corp") == "acme-corp"
    assert WikiManager._slugify("Jane O'Brien") == "jane-o-brien"
    assert WikiManager._slugify("  Hello  World  ") == "hello-world"
    assert WikiManager._slugify("ABC 123") == "abc-123"
    assert WikiManager._slugify("---") == "untitled"
    assert WikiManager._slugify("") == "untitled"


@pytest.mark.asyncio
async def test_auto_rename_if_untitled_renames_when_name_present(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "clients" / "_type.yaml").write_text(
        "name: Clients\nsingular: client\nfields: []\nsections: []\n"
    )
    # Simulate an Untitled page that the user has filled in
    untitled_path = wiki / "clients" / "Untitled.md"
    untitled_path.write_text("---\ntype: client\nname: Acme Corp\n---\n\n# Acme Corp\n")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir),
        )

    new_path = await manager.auto_rename_if_untitled("clients/Untitled.md")
    assert new_path == "clients/acme-corp.md"
    assert (wiki / "clients" / "acme-corp.md").exists()
    assert not (wiki / "clients" / "Untitled.md").exists()


@pytest.mark.asyncio
async def test_auto_rename_if_untitled_no_op_when_already_named(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "clients" / "_type.yaml").write_text(
        "name: Clients\nsingular: client\nfields: []\nsections: []\n"
    )
    (wiki / "clients" / "acme-corp.md").write_text("---\ntype: client\nname: Acme Corp\n---\n")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir),
        )

    result = await manager.auto_rename_if_untitled("clients/acme-corp.md")
    assert result is None


@pytest.mark.asyncio
async def test_auto_rename_if_untitled_no_op_when_name_empty(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "clients" / "_type.yaml").write_text(
        "name: Clients\nsingular: client\nfields: []\nsections: []\n"
    )
    untitled_path = wiki / "clients" / "Untitled.md"
    untitled_path.write_text("---\ntype: client\nname: \n---\n\n# \n")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir),
        )

    result = await manager.auto_rename_if_untitled("clients/Untitled.md")
    assert result is None
    assert (wiki / "clients" / "Untitled.md").exists()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_wiki_manager.py::test_slugify_basic tests/test_wiki_manager.py::test_auto_rename_if_untitled_renames_when_name_present -v
```

Expected: `AttributeError` — `_slugify` and `auto_rename_if_untitled` not yet defined.

- [ ] **Step 3: Implement `_slugify` and `auto_rename_if_untitled` in `wiki_manager.py`**

Open `backend/agent/wiki_manager.py`. Add the static `_slugify` method near the other `_parse_frontmatter` / `_render_frontmatter` helpers (around line 250):

```python
    @staticmethod
    def _slugify(name: str) -> str:
        """Convert a display name to a lowercase-hyphenated wiki filename slug."""
        slug = name.lower().strip()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        return slug or "untitled"
```

Then add `auto_rename_if_untitled` as an async method on `WikiManager`, near `create_new_page` (around line 916):

```python
    async def auto_rename_if_untitled(self, rel_path: str) -> str | None:
        """If rel_path is an Untitled*.md file with a non-empty name frontmatter field,
        rename it to the correct wiki slug and return the new relative path.
        Returns None if no rename was performed.
        """
        basename = os.path.basename(rel_path)
        if not re.match(r'^Untitled(_\d+)?\.md$', basename):
            return None

        abs_path = os.path.join(self.wiki_dir, rel_path.replace("/", os.sep))
        if not os.path.exists(abs_path):
            return None

        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()

        fm, _ = self._parse_frontmatter(content)
        name = str(fm.get("name", "")).strip()
        if not name:
            return None

        entity_type = rel_path.split("/")[0]
        sub_dir = os.path.join(self.wiki_dir, entity_type)
        slug = self._slugify(name)
        new_rel_path = f"{entity_type}/{slug}.md"
        new_abs_path = os.path.join(sub_dir, f"{slug}.md")

        # Collision handling: append -2, -3, etc.
        counter = 2
        while os.path.exists(new_abs_path):
            new_rel_path = f"{entity_type}/{slug}-{counter}.md"
            new_abs_path = os.path.join(sub_dir, f"{slug}-{counter}.md")
            counter += 1

        async with self._write_lock:
            os.rename(abs_path, new_abs_path)
            self.update_index()
        self._rebuild_search_index()
        return new_rel_path
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/test_wiki_manager.py::test_slugify_basic tests/test_wiki_manager.py::test_auto_rename_if_untitled_renames_when_name_present tests/test_wiki_manager.py::test_auto_rename_if_untitled_no_op_when_already_named tests/test_wiki_manager.py::test_auto_rename_if_untitled_no_op_when_name_empty -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Update the `update_page` route to call `auto_rename_if_untitled`**

Open `backend/api/routes.py`. Replace the `update_page` function (lines 784–797):

```python
@router.put("/pages/{path:path}")
async def update_page(wm: WM, path: str, payload: dict):
    try:
        safe_path = safe_wiki_filename(path, wm)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    content = payload.get("content")
    if content is None:
        raise HTTPException(status_code=422, detail="Content is required")
    try:
        suggested_tags = await wm.save_page_content(safe_path, content)
        new_filename = await wm.auto_rename_if_untitled(safe_path)
        return {
            "message": "Page updated successfully",
            "suggested_tags": suggested_tags,
            "new_filename": new_filename,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating page: {str(e)}")
```

- [ ] **Step 6: Run the full backend test suite to check for regressions**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2/Faragopedia-Sales/backend" && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All previously passing tests still pass.

- [ ] **Step 7: Update `handleSave` in `WikiView.tsx` to handle the new filename**

Open `frontend/src/components/WikiView.tsx`. Replace `handleSave` (lines 296–322):

```typescript
  const handleSave = async () => {
    if (!selectedPage) return;
    try {
      setIsSaving(true);
      const response = await fetch(`${API_BASE}/pages/${encodeURIComponent(selectedPage)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editedContent }),
      });

      if (!response.ok) throw new Error('Failed to save page');

      const saveData = await response.json();
      if (saveData.suggested_tags && saveData.suggested_tags.length > 0) {
        setSuggestedTags(saveData.suggested_tags);
      }

      setContent(editedContent);
      setIsEditing(false);

      if (saveData.new_filename) {
        // File was renamed from Untitled — navigate to the new path
        await fetchPages();
        setSelectedPage(saveData.new_filename);
        await fetchPageContent(saveData.new_filename);
      } else {
        fetchPages();
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };
```

- [ ] **Step 8: Commit**

```bash
cd "/home/colacho/Nextcloud/AI/VS Code/Faragopedia-V2" && git add "Faragopedia-Sales/backend/agent/wiki_manager.py" "Faragopedia-Sales/backend/api/routes.py" "Faragopedia-Sales/frontend/src/components/WikiView.tsx" "Faragopedia-Sales/backend/tests/test_wiki_manager.py" && git commit -m "feat: auto-rename Untitled pages to wiki slug on first save"
```
