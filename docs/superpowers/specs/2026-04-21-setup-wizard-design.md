# Design: First-Run Setup Wizard

**Date:** 2026-04-21
**Status:** Approved

## Goal

Make Faragopedia company-agnostic. Currently the app is hardwired to Farago Projects via `company_profile.md`, `SCHEMA_TEMPLATE.md`, and five Farago-specific entity types. A first-run wizard collects organisation identity, generates entity types via LLM, and writes all config files before the wiki loads.

---

## Key Decisions

| Decision | Choice |
|---|---|
| Step 2 field editing depth | Full — add/remove/edit any field (name, type, required, enum values, description) |
| Re-run mechanism | "Reconfigure Wiki" button in sidebar settings |
| Data handling on reconfigure | Warn and selectively clear — per-folder Keep/Delete for orphaned folders |
| Reconfigure Step 2 layout | Fresh LLM suggestion + existing folder diff side-by-side |
| Backend init architecture | FastAPI dependency injection (not module-level None singleton) |

---

## Architecture Overview

```
Browser loads App.tsx
  └─ GET /api/setup/status
      ├─ setup_required: false  → render normal app
      └─ setup_required: true   → render <SetupWizard /> full-screen

SetupWizard (3 steps):
  Step 1 — Identity
    wiki_name, org_name, org_description
    "Generate Schema →" → POST /api/setup/suggest-schema → entity types JSON
    On 503/error → Step 2 with preset picker fallback

  Step 2 — Schema Review & Edit (full field control)
    Expandable/collapsible entity type cards:
      - display_name (editable), folder_name (read-only slug shown), description
      - Fields: add/remove, edit name/type/required/enum-values/description
      - Sections: pill-style add/remove
    Add/remove whole entity type cards
    "Review & Launch →"

  Step 3 — Confirm
    Read-only folder structure summary
    "Launch Wiki" → POST /api/setup/complete → app re-renders normally

Normal app — Sidebar shows "Reconfigure Wiki" button
  → POST /api/setup/clear → returns { existing_folders: [...] }
  → re-renders <SetupWizard reconfigureMode existingFolders />

Reconfigure Step 2 — split layout:
  Left: LLM suggestion (editable), with "matches existing" / "new" badges
  Right: Existing folders panel — matched ones show ✓, unmatched show Keep/Delete

Reconfigure Step 3 — diff summary:
  New folders · Kept folders · Deleted folders
  Confirmation before launch

POST /api/setup/complete calls complete_setup():
  1. write company_profile.md
  2. fill BASE_SCHEMA_TEMPLATE → write SCHEMA_TEMPLATE.md
  3. makedirs + write _type.yaml per entity type
  4. build_schema_md() → write SCHEMA.md
  5. write wiki_config.json
  6. instantiate WikiManager → set_wiki_manager()
```

---

## Backend

### `backend/api/routes.py` (modified)

Replace module-level singleton with FastAPI dependency injection:

```python
_wiki_manager: WikiManager | None = None

def get_wiki_manager() -> WikiManager:
    if _wiki_manager is None:
        raise HTTPException(503, "Wiki setup not complete")
    return _wiki_manager

def set_wiki_manager(wm: WikiManager | None) -> None:
    global _wiki_manager
    _wiki_manager = wm
```

All existing route signatures gain `wm: Annotated[WikiManager, Depends(get_wiki_manager)]`. This is a mechanical change — no logic changes to existing routes. Routes automatically return 503 during setup with no scattered None-checks needed.

### `backend/agent/wiki_manager.py` (modified)

`_load_system_prompt()` (line 201): return a stub fallback string instead of raising `FileNotFoundError` when SCHEMA.md or company_profile.md are absent. Prevents WikiManager from crashing when constructed in tests before setup files exist.

### `backend/agent/setup_wizard.py` (new)

```
is_setup_complete(schema_dir) → bool
    Checks wiki_config.json existence.

get_wiki_config(schema_dir) → dict | None
    Reads and returns wiki_config.json contents.

migrate_existing(schema_dir) → None
    If company_profile.md exists but wiki_config.json doesn't:
    write wiki_config.json with Farago defaults. Wizard never shows.

suggest_schema_llm(org_name, org_description, llm) → SuggestedSchema
    LLM call using PydanticOutputParser(SuggestedSchema).
    System prompt instructs: 3–7 entity types, folder_name plural lowercase
    hyphen-separated, every type has a required name:string field first.

complete_setup(schema_dir, wiki_dir, payload) → WikiManager
    1. write company_profile.md (org_name + org_description)
    2. fill BASE_SCHEMA_TEMPLATE tokens → write SCHEMA_TEMPLATE.md
    3. makedirs(wiki_dir/folder_name) + write _type.yaml per entity type
    4. build_schema_md(wiki_dir, schema_dir/SCHEMA_TEMPLATE.md) → write SCHEMA.md
    5. write wiki_config.json { wiki_name, org_name, setup_complete: true }
    6. instantiate WikiManager with schema_dir → return it

clear_setup(schema_dir, wiki_dir) → list[str]
    Deletes wiki_config.json.
    Returns list of existing entity folder names (for diff display).
    Does NOT delete wiki data — user decides per-folder in the wizard.
```

`BASE_SCHEMA_TEMPLATE`: string constant, identical structure to current `SCHEMA_TEMPLATE.md` but Identity section uses `{{ORG_NAME}}` / `{{ORG_DESCRIPTION}}` tokens.

### `backend/api/setup_routes.py` (new)

```
GET  /api/setup/status
     → { setup_required: bool, wiki_name?: str }

GET  /api/setup/config
     → { wiki_name: str, org_name: str }

POST /api/setup/suggest-schema
     ← { org_name: str, org_description: str }
     → { entity_types: [...] }
     → 503 { detail: "LLM unavailable" } if no provider configured or timeout

POST /api/setup/complete
     ← SetupPayload
     → { success: true, wiki_name: str }
     calls complete_setup() → set_wiki_manager()

POST /api/setup/clear
     ← {}
     → { existing_folders: [str, ...] }
     calls clear_setup() → set_wiki_manager(None)

DELETE /api/setup/folder/{name}
     → { success: true }
     Deletes wiki_dir/name and all contents (user confirmed in UI).
```

**Pydantic models:**

```python
class EntityTypeField(BaseModel):
    name: str
    type: str                        # string | date | integer | enum | list
    default: str | None = None
    required: bool | None = None
    values: list[str] | None = None  # enum only
    description: str | None = None

class EntityTypeDefinition(BaseModel):
    folder_name: str    # validated: lowercase, hyphen-separated
    display_name: str
    description: str
    singular: str
    fields: list[EntityTypeField]
    sections: list[str]

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
```

### `backend/main.py` (modified)

On startup:
1. Call `migrate_existing(schema_dir)`
2. If `is_setup_complete(schema_dir)`: instantiate WikiManager → `set_wiki_manager(wm)`
3. Register `setup_router` at `/api/setup`

---

## Frontend

### `frontend/src/App.tsx` (modified)

```tsx
type SetupState = 'loading' | 'required' | 'ready'

const [setupState, setSetupState] = useState<SetupState>('loading')
const [wikiName, setWikiName] = useState('')
const [reconfigureMode, setReconfigureMode] = useState(false)
const [existingFolders, setExistingFolders] = useState<string[]>([])

// On mount: GET /api/setup/status
// setup_required: true  → setSetupState('required')
// setup_required: false → setWikiName(data.wiki_name), setSetupState('ready')

// handleSetupComplete: fetch /api/setup/config → setWikiName, setSetupState('ready')

// handleReconfigure:
//   POST /api/setup/clear → setExistingFolders(data.existing_folders)
//   setReconfigureMode(true), setSetupState('required')

if (setupState === 'loading') return <LoadingScreen />
if (setupState === 'required') return (
  <SetupWizard
    onComplete={handleSetupComplete}
    reconfigureMode={reconfigureMode}
    existingFolders={existingFolders}
  />
)
return <NormalApp wikiName={wikiName} onReconfigure={handleReconfigure} />
```

### `frontend/src/components/SetupWizard.tsx` (new)

**Props:** `onComplete: () => void`, `reconfigureMode?: boolean`, `existingFolders?: string[]`

**Step 1 — Identity:**
- Fields: `wiki_name`, `org_name`, `org_description` (textarea)
- In reconfigure mode: prefill from `GET /api/setup/config`
- "Generate Schema →" button → `POST /api/setup/suggest-schema` with loading spinner
- On success: advance to Step 2 with entity types pre-populated
- On 503/error: advance to Step 2 with empty list + inline preset picker

**Step 2 — Schema Review & Edit:**

Normal mode — single column of entity type cards:
- Expandable/collapsible (collapsed shows: folder name, display name, field count, section count)
- Expanded shows:
  - `display_name` inline text input — `folder_name` is auto-slugified from display_name (lowercase, hyphens), shown read-only below the input but editable via a small "edit slug" affordance
  - `description` textarea
  - Fields list: each row shows name, type badge, required indicator, delete (×)
    - Click field row to expand inline editor: name input, type select, required toggle,
      enum values input (comma-separated, shown only for enum type), description input
  - "+ Add field" button appends blank field row
  - Sections: pill tags with (×), "+ section" pill opens inline text input
- "+ Add entity type" dashed card at end
- Entity type (×) removes the card

Reconfigure mode — split layout:
- Left panel: LLM suggestion cards (same editing controls as normal mode)
  - Each card badged: "matches existing" (green) or "new" (blue)
- Right panel: Existing folders list
  - Matched folders: show ✓ and "→ kept" — their existing `_type.yaml` is left untouched
  - Unmatched folders: show Keep / Delete buttons — "Keep" also leaves `_type.yaml` untouched; "Delete" calls `DELETE /api/setup/folder/{name}` in Step 3
- All state is local React state; no API calls until Step 3

Preset fallback (shown in Step 2 when LLM unavailable):
- Buttons: "Creative Production" | "CRM" | "Research" | "Blank"
- Each loads a frontend constant set of entity types into the editor

**Step 3 — Confirm:**

Normal mode:
- Read-only folder structure tree
- "Launch Wiki" → `POST /api/setup/complete` → `onComplete()`

Reconfigure mode:
- Diff summary: New folders · Kept folders · Deleted folders
- Per-folder `DELETE /api/setup/folder/{name}` for folders marked for deletion (sequential)
- Then `POST /api/setup/complete`
- On error: stay on Step 3 with inline error message

### `frontend/src/components/Sidebar.tsx` (modified)

- Accept `wikiName: string` prop — replaces both hardcoded `"Faragopedia"` occurrences (line 22 display name, line 46 version label area)
- Add "Reconfigure Wiki" button at bottom of sidebar, below nav links
- Calls `onReconfigure` prop (passed down from App)

---

## Key Reuse (unchanged)

- `schema_builder.build_schema_md()` — called by `complete_setup()` unchanged
- `schema_builder.discover_entity_types()` — used unchanged for post-setup operation
- `schema_builder.bootstrap_type_yamls()` — still safe; wizard creates folders + _type.yaml together so no collision
- `WikiManager._init_llm()` — extracted or duplicated into `setup_wizard.py` for the suggest-schema endpoint
- `PydanticOutputParser` (LangChain, already in requirements.txt) — parses SuggestedSchema

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Fresh install, no files | `migrate_existing` no-ops, wizard shown |
| Existing Farago install (no wiki_config.json) | `migrate_existing` writes config with Farago defaults, wizard skipped |
| `suggest-schema` — no LLM configured | 503, frontend shows preset picker in Step 2 |
| `suggest-schema` — LLM timeout | 503 `{"detail": "LLM unavailable"}`, same fallback |
| `complete_setup` — file write fails | 500, wizard stays on Step 3 with inline error |
| WikiManager reinit fails after setup | 500, wiki_config.json already written so next reload recovers |
| `DELETE /api/setup/folder/{name}` | Deletes folder + all contents (user confirmed in UI) |

---

## Testing

New test files:
- `backend/tests/test_setup_wizard.py` — unit tests for `is_setup_complete`, `migrate_existing`, `complete_setup`, `clear_setup`
- `backend/tests/test_setup_routes.py` — integration tests for all 5 setup endpoints
- `backend/tests/test_dependency_injection.py` — verify 503 when manager is None, correct operation after `set_wiki_manager()`

Existing tests unaffected — they construct WikiManager directly with explicit schema_dir pointing to real files.

**Fresh install verification sequence:**
1. Remove `wiki_config.json` + `SCHEMA.md`, clear `company_profile.md` → wizard appears
2. Fill Step 1, generate schema → LLM entity types in Step 2
3. Edit fields (add/remove/rename) → proceed to Step 3
4. Launch → all files written, wiki loads with correct wiki_name in sidebar
5. Hit "Reconfigure Wiki" → clears config, wizard reopens in reconfigure mode with diff layout
6. LLM fallback: no `AI_PROVIDER` configured → 503 → Step 2 shows preset picker
7. Farago migration: restore current files (no wiki_config.json) → `migrate_existing()` auto-creates it → wizard does not appear
