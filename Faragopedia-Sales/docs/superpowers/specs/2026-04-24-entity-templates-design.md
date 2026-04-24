# Entity Type Templates — Design Spec

**Date:** 2026-04-24
**Status:** Approved

---

## Overview

When the wiki setup wizard completes, generate a `_template.md` file for each entity type. When a user creates a new page, pre-populate the editor with that template so they know which fields and sections to fill out.

---

## Template Format

Each `_template.md` contains YAML frontmatter with all defined fields, followed by markdown sections with inline hints.

Example for a `clients` entity type with fields `name` (string, required), `industry` (enum: Tech/Finance/Other), `website` (string) and sections `Overview`, `Contacts`, `Notes`:

```markdown
---
type: client
name: 
industry:  # options: Tech, Finance, Other
website: 
---

# 

## Overview
_Add an overview here..._

## Contacts
_Add contacts here..._

## Notes
_Add notes here..._
```

**Frontmatter rendering rules:**
- All fields included with empty values (`field: `)
- `name` always appears first
- `list` type fields render as `field: []`
- Enum fields include an inline comment: `# options: Val1, Val2, Val3`
- `type` (singular form) always included as the first field

**Section hints:** `_Add {section name} here..._` (generic, lowercase section name)

---

## Storage

Templates live co-located with `_type.yaml` inside each entity type folder:

```
wiki/
├── clients/
│   ├── _type.yaml
│   ├── _template.md   ← generated
│   └── acme-corp.md
├── contacts/
│   ├── _type.yaml
│   ├── _template.md   ← generated
│   └── jane-doe.md
```

Templates are per-workspace — each workspace's wiki directory contains its own set of templates derived from that workspace's entity type definitions.

---

## Generation Triggers

Templates are generated:
1. **At setup completion** — `complete_setup()` in `setup_wizard.py` generates all templates after writing `_type.yaml` files
2. **On setup re-run** — `complete_setup()` overwrites existing templates when setup is cleared and re-run

If a post-setup entity type editor is added in the future, it should call `write_entity_templates()` after writing updated `_type.yaml` files.

---

## Backend Changes

### `backend/agent/schema_builder.py`

Add two new functions:

**`generate_entity_template(folder_name: str, singular: str, fields: list, sections: list[str]) -> str`**
- Renders the full `_template.md` content string from entity type data
- `fields` is a list of dicts (matching the `_type.yaml` field schema: `name`, `type`, `values`, etc.)
- Accepts plain dicts rather than Pydantic models so it can also be called when reading from `_type.yaml` post-setup

**`write_entity_templates(wiki_dir: str, entity_types: list[EntityTypeDefinition])`**
- Iterates over entity types, unpacks each `EntityTypeDefinition` into plain values, calls `generate_entity_template()`
- Writes `{wiki_dir}/{entity_type.folder_name}/_template.md`
- Creates the entity type folder if it doesn't exist (mirrors existing `_type.yaml` write logic)

### `backend/agent/setup_wizard.py` — `complete_setup()`

After the existing loop that writes `_type.yaml` files, call:
```python
write_entity_templates(wiki_dir, payload.entity_types)
```

Import `write_entity_templates` from `schema_builder`.

### `backend/agent/wiki_manager.py` — `list_pages()`

Add `not filename.startswith("_")` to the file filter so `_template.md` (and any future `_`-prefixed metadata files) are excluded from the page list returned to the frontend.

Current:
```python
if not filename.endswith(".md"):
    continue
```

Updated:
```python
if not filename.endswith(".md") or filename.startswith("_"):
    continue
```

### `backend/agent/wiki_manager.py` — `create_new_page()`

After determining the new file path, attempt to read the entity type's `_template.md`:

```python
template_path = os.path.join(sub_dir, "_template.md")
if os.path.exists(template_path):
    with open(template_path, "r") as f:
        content = f.read()
else:
    # existing fallback stub
    content = f"---\ntype: {singular}\nname: \n---\n\n# Untitled\n\nNew page content here.\n"
```

---

## Frontend Changes

None. The `GET /pages` response is already filtered by the backend `list_pages()` change, so `_template.md` files never reach the sidebar. The new file pre-population happens entirely in `create_new_page()`, so `handleNewPage()` in `WikiView.tsx` is unchanged.

---

## Out of Scope

- Manual template editing UI (templates are files and can be edited directly if needed)
- Per-field hints derived from field descriptions (generic section hints are sufficient)
- Template preview in the setup wizard
