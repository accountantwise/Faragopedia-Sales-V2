# Dynamic Frontmatter Editing Design

**Date:** 2026-04-27  
**Status:** Approved

## Overview

Make frontmatter fields in the wiki view editable inline. Fields with preset options (enum type in `_type.yaml`) render as dropdowns; free-text fields become inputs on click. Each field saves independently via a new PATCH endpoint. No "save all" button — changes persist immediately on selection/blur.

## Source of Truth for Field Options

Entity type schemas are already defined in `_type.yaml` files inside each wiki entity folder (e.g. `wiki/contacts/_type.yaml`). These files use `{"type": "enum", "values": [...]}` for fields with preset options. The backend reads these via `load_type_yaml()` in `schema_builder.py`. No template-comment parsing is needed.

## Backend Changes

### New function: `get_field_schema(entity_type)`

In `wiki_manager.py`, add a method that:
1. Calls `load_type_yaml` for the given entity type folder
2. Returns a dict mapping field names to their option lists for enum fields only
3. Example output: `{"seniority": ["Director","Manager","Executive","C-Suite","Freelance"], "status": ["Active","Dormant","Converted","Lost"]}`
4. Returns `{}` if the entity type has no `_type.yaml` or no enum fields

### New route: `GET /entity-types/{type}/field-schema`

- Reads the entity type's `_type.yaml` via `get_field_schema()`
- Returns `{"schema": {"field_name": ["opt1","opt2",...], ...}}`
- 404 if entity type doesn't exist
- Used by the frontend on page load

### New route: `PATCH /pages/{path}/frontmatter`

- Request body: `{"field": "relationship", "value": "Hot"}`
- Reads the page, parses frontmatter with `_parse_frontmatter()`
- Updates the single field, writes back with `_render_frontmatter()`
- Triggers `_rebuild_search_index()`
- Returns `{"ok": true}`
- Validates the path using existing `validate_page_path()` helper

## Frontend Changes

### Entity type detection

The page path (e.g. `contacts/alexandra-cernanova.md`) gives the entity type as the first path segment. Extract it when the page loads.

### Schema fetch

When a page loads in view mode, fetch `GET /entity-types/{type}/field-schema` and store the result in a `fieldSchema` state variable (`Record<string, string[]>`). Skip the fetch if no entity type can be determined.

### Frontmatter badge interaction

Replace the static value `<span>` in the frontmatter display block (around line 1329 in `WikiView.tsx`) with a `FrontmatterValue` component. Behaviour:

- **Enum field** (field name in `fieldSchema`): renders a `<select>` styled to match the existing blue badge text. The current value is the selected option. On `onChange`, PATCH the field and update local display state. A brief checkmark appears on the badge after save.
- **Free-text field**: renders a `<span>` by default. On click, replaces with an `<input>`. On blur or Enter, if the value changed, PATCH the field. Escape cancels.
- **List fields** (`industries`, `role_tags`, etc.): remain read-only for now — the raw editor handles these. The badge displays as before.
- **System fields** (`type`, `name`): remain read-only in this component. `name` changes trigger auto-rename which requires the full save flow.

### Saving state

Track a per-field saving state (`savingField: string | null`) to show a loading indicator. On error, show a red indicator and revert the local value.

### Styling

The `<select>` and `<input>` elements inherit the badge's font and colour so the UI feels seamless — no visible box borders, just the value becomes interactive. A subtle underline or pencil cursor signals editability.

## Data Flow

```
User clicks value badge
  → if enum: <select> appears with options
  → user picks option
  → PATCH /pages/{path}/frontmatter {field, value}
  → backend updates file + rebuilds search index
  → frontend updates local display state
  → checkmark shown briefly
```

## What Is Not Changing

- The raw markdown editor remains unchanged for full content edits
- List fields (`industries`, `role_tags`) are still edited via the raw editor
- The `name` field is still edited via the raw editor (auto-rename logic lives there)
- The tag system (separate from frontmatter) is unchanged

## Prerequisite: Contacts `_type.yaml`

The default contacts schema in `schema_builder.py` has minimal fields (`role`, `org`, `linked_orgs`). The real contact pages (e.g. `alexandra-cernanova.md`) use a richer field set: `seniority`, `email`, `phone`, `linkedin`, `source`, `relationship`, `farago_contact`, `industries`, `role_tags`, `internal_or_freelance`, `first_contacted`, `last_contacted`, `last_meeting`, `next_follow_up`, `status`, `notes`.

The implementation plan must update the default contacts `_type.yaml` definition in `schema_builder.py` (and any live `contacts/_type.yaml`) to include these fields with their correct types and enum values before the frontend field-schema fetch will return useful data.

## Files to Change

| File | Change |
|------|--------|
| `backend/agent/wiki_manager.py` | Add `get_field_schema(entity_type)` and `patch_frontmatter_field(path, field, value)` |
| `backend/api/routes.py` | Add `GET /entity-types/{type}/field-schema` and `PATCH /pages/{path}/frontmatter` |
| `frontend/src/components/WikiView.tsx` | Add schema fetch, replace static value span with interactive `FrontmatterValue` component |
