# Workspace Feature Plan

## Context

Faragopedia-Sales currently supports a single wiki instance. The user wants to support multiple independent "workspaces" — each with its own wiki, sources, entity schema, company profile, and LLM identity — switchable from within the running app. Creating a new workspace goes through the same setup wizard that already exists on the `setup-wizard` branch (not yet merged to main or the feature branch).

Key user decisions:
- Existing wiki data → migrated automatically as the "default" workspace
- Workspace switcher → lives in the sidebar header (where wiki name currently is)
- Setup wizard → already implemented on `setup-wizard` branch; reuse it
- Workspaces are completely isolated from each other

---

## Architecture Overview

```
workspaces/
├── registry.json              ← { active_workspace_id, workspaces: [{id, name, created_at}] }
├── default/
│   ├── wiki/                  ← wiki pages
│   ├── sources/               ← raw source files
│   ├── archive/               ← archived pages/sources
│   ├── snapshots/             ← lint snapshots
│   └── schema/                ← SCHEMA.md, company_profile.md, wiki_config.json
└── my-new-wiki/
    ├── wiki/
    ├── sources/
    ├── archive/
    ├── snapshots/
    └── schema/
```

### Data flow — workspace switch

```
User clicks workspace    POST /api/workspaces/{id}/switch
  └─ workspace_manager.set_active_workspace(id)
      ├─ updates _active_dirs (in-memory)
      ├─ writes registry.json
      └─ rebuilds WikiManager with new dirs → set_wiki_manager(wm)

Frontend detects switch:
  ├─ GET /api/setup/status  → setup_required?
  │   ├─ false → normal app (new workspace is ready)
  │   └─ true  → show SetupWizard for this workspace
  └─ remount WikiView/SourcesView via key={activeWorkspaceId}
```

### New workspace creation flow

```
"+ New Workspace" clicked
  └─ POST /api/workspaces   (auto-generates ID from name slug)
      └─ creates dirs, registry entry, switches active → { id, setup_required: true }
Frontend:
  └─ shows SetupWizard (wizard runs against active workspace's dirs via getters)
      └─ POST /api/setup/complete → writes schema files, builds WikiManager
          └─ also calls workspace_manager.update_workspace_name(id, wiki_name)
```

---

## Critical Design: Making Workspace Dirs Dynamic

`routes.py` and `setup_routes.py` currently use hardcoded module-level constants (`WIKI_DIR`, `SOURCES_DIR`, etc.). These must become dynamic calls because they change when the active workspace changes.

**Solution:** Add per-directory getter functions to `workspace_manager.py`. Both `routes.py` and `setup_routes.py` import and call these instead of using constants.

```python
# workspace_manager.py
_active_dirs: dict = {}

def get_wiki_dir() -> str:     return _active_dirs.get("wiki_dir", "")
def get_sources_dir() -> str:  return _active_dirs.get("sources_dir", "")
def get_archive_dir() -> str:  return _active_dirs.get("archive_dir", "")
def get_snapshots_dir() -> str: return _active_dirs.get("snapshots_dir", "")
def get_schema_dir() -> str:   return _active_dirs.get("schema_dir", "")
```

In `routes.py`: replace ~20 usages of `WIKI_DIR` / `SOURCES_DIR` etc. with `get_wiki_dir()` / `get_sources_dir()` etc. (also pass wiki_dir as a parameter to `rewrite_wikilinks()`).

In `setup_routes.py`: remove `SCHEMA_DIR` constant and the `from api.routes import WIKI_DIR, SOURCES_DIR, ...` import; replace with getters.

---

## Step 0: Merge setup-wizard into feature branch

```bash
git fetch origin setup-wizard
git merge origin/setup-wizard --no-edit
# resolve any conflicts (setup-wizard is 58 commits ahead of main)
```

This brings in: `setup_wizard.py`, `setup_routes.py`, `SetupWizard.tsx`, `SettingsDrawer.tsx`, updated `App.tsx`, `Sidebar.tsx`, `routes.py` (with DI), `main.py`.

---

## Step 1: `backend/agent/workspace_manager.py` (new file, ~160 lines)

```python
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))  # backend/agent/
BACKEND_DIR = os.path.dirname(_THIS_DIR)                # backend/
BASE_DIR = os.path.dirname(BACKEND_DIR)                 # project root

LEGACY_DIRS = {
    "wiki_dir":      os.path.join(BASE_DIR, "wiki"),
    "sources_dir":   os.path.join(BASE_DIR, "sources"),
    "archive_dir":   os.path.join(BASE_DIR, "archive"),
    "snapshots_dir": os.path.join(BASE_DIR, "snapshots"),
    "schema_dir":    os.path.join(BACKEND_DIR, "schema"),
}

WORKSPACES_BASE = os.path.join(BASE_DIR, "workspaces")
REGISTRY_PATH   = os.path.join(WORKSPACES_BASE, "registry.json")

_active_workspace_id: str | None = None
_active_dirs: dict = {}
```

Key functions:

| Function | Purpose |
|---|---|
| `initialize_workspaces()` | Called at startup. If no registry: detect legacy data, migrate to `default/`. If empty install: write empty registry. |
| `list_workspaces() → list[dict]` | Read registry["workspaces"] |
| `get_active_workspace_id() → str \| None` | Return `_active_workspace_id` |
| `get_active_workspace_info() → dict \| None` | Return matching registry entry |
| `set_active_workspace(id)` | Update `_active_dirs` + registry |
| `create_workspace(name) → dict` | Slugify name → id, create dirs, registry entry, set active |
| `update_workspace_name(id, name)` | Update registry entry name |
| `delete_workspace(id)` | rmtree dirs, remove registry entry |
| `workspace_dirs(id) → dict` | Return path dict for given id |
| `get_wiki_dir() / get_sources_dir() / get_archive_dir() / get_snapshots_dir() / get_schema_dir()` | Return from `_active_dirs` |

**Migration logic** inside `initialize_workspaces()`:
1. If `registry.json` exists → load, update `_active_dirs`, done.
2. If `backend/schema/wiki_config.json` exists → copy legacy dirs into `workspaces/default/`, read wiki_name from config, write registry with "default" as active.
3. Otherwise → write empty registry `{ active_workspace_id: null, workspaces: [] }`.

Migration copy: use `shutil.copytree` with `dirs_exist_ok=True` for each legacy dir.

---

## Step 2: Update `backend/api/routes.py`

**Remove:** `BASE_DIR`, `SOURCES_DIR`, `WIKI_DIR`, `ARCHIVE_DIR`, `SNAPSHOTS_DIR` module-level constants (~lines 41–50).

**Add import:**
```python
from agent.workspace_manager import (
    get_wiki_dir, get_sources_dir, get_archive_dir, get_snapshots_dir
)
```

**Replace all usages** (find & replace, ~20 occurrences):
- `WIKI_DIR` → `get_wiki_dir()`
- `SOURCES_DIR` → `get_sources_dir()`
- `ARCHIVE_DIR` → `get_archive_dir()`
- `SNAPSHOTS_DIR` → `get_snapshots_dir()`

**`rewrite_wikilinks` function:** Add `wiki_dir: str` parameter; replace internal `WIKI_DIR` with it. Update all call sites to pass `get_wiki_dir()`.

Keep `set_wiki_manager` / `get_wiki_manager` / `_wiki_manager` DI scaffolding as-is.

---

## Step 3: Update `backend/api/setup_routes.py`

**Remove:**
```python
from api.routes import (ARCHIVE_DIR, SNAPSHOTS_DIR, SOURCES_DIR, WIKI_DIR, set_wiki_manager)
_THIS_DIR / _BACKEND_DIR / SCHEMA_DIR constants
```

**Add:**
```python
from agent.workspace_manager import (
    get_wiki_dir, get_sources_dir, get_archive_dir, get_snapshots_dir, get_schema_dir,
    update_workspace_name, get_active_workspace_id
)
from api.routes import set_wiki_manager
```

**Replace** `SCHEMA_DIR` → `get_schema_dir()`, `WIKI_DIR` → `get_wiki_dir()`, etc. everywhere in the file.

**`setup_complete` endpoint**: after `complete_setup()` and `set_wiki_manager(wm)`, also call:
```python
update_workspace_name(get_active_workspace_id(), payload.wiki_name)
```

---

## Step 4: `backend/api/workspace_routes.py` (new file, ~100 lines)

```python
workspace_router = APIRouter()

GET  /workspaces         → { workspaces: [...], active_workspace_id: str }
POST /workspaces         ← { name: str }
                         → creates workspace, switches active
                         → { id, name, setup_required: true }
POST /workspaces/{id}/switch
                         → set_active_workspace(id)
                         → rebuild WikiManager if setup complete
                         → { id, wiki_name, setup_required: bool }
DELETE /workspaces/{id}  → cannot delete active workspace
                         → delete_workspace(id) → { success: true }
```

`POST /workspaces/{id}/switch` logic:
```python
workspace_manager.set_active_workspace(id)
if is_setup_complete(get_schema_dir()):
    wm = WikiManager(sources_dir=get_sources_dir(), wiki_dir=get_wiki_dir(), ...)
    set_wiki_manager(wm)
    return {"id": id, "setup_required": False, "wiki_name": ...}
else:
    set_wiki_manager(None)
    return {"id": id, "setup_required": True}
```

---

## Step 5: Update `backend/main.py`

```python
from agent.workspace_manager import initialize_workspaces, get_active_workspace_id, \
    get_wiki_dir, get_sources_dir, get_archive_dir, get_snapshots_dir, get_schema_dir, \
    is_setup_complete  # re-export from setup_wizard
from api.workspace_routes import workspace_router

app.include_router(workspace_router, prefix="/api/workspaces")

# Replace migrate_existing + is_setup_complete + WikiManager init block:
initialize_workspaces()
active_id = get_active_workspace_id()
if active_id:
    from agent.setup_wizard import is_setup_complete
    if is_setup_complete(get_schema_dir()):
        from agent.wiki_manager import WikiManager
        wm = WikiManager(
            sources_dir=get_sources_dir(), wiki_dir=get_wiki_dir(),
            archive_dir=get_archive_dir(), snapshots_dir=get_snapshots_dir(),
            schema_dir=get_schema_dir()
        )
        set_wiki_manager(wm)
```

Remove the old `migrate_existing(SCHEMA_DIR)` call and the old `WIKI_DIR / SOURCES_DIR / ARCHIVE_DIR / SNAPSHOTS_DIR / SCHEMA_DIR` imports.

---

## Step 6: `frontend/src/components/WorkspaceSwitcher.tsx` (new, ~90 lines)

```tsx
interface Workspace { id: string; name: string; }
interface Props {
  workspaces: Workspace[];
  activeWorkspaceId: string;
  onSwitch: (id: string) => void;
  onNewWorkspace: () => void;
}
```

UI: a button showing `[WS] {name} ▾` that opens a dropdown panel with:
- Each workspace as a clickable row (active one has a check mark)
- A `+ New Workspace` button at the bottom of the list

Dropdown closes on outside click (use `useRef` + `useEffect` listener).

---

## Step 7: Update `frontend/src/components/Sidebar.tsx`

- Add `WorkspaceSwitcher` import
- Add props: `workspaces`, `activeWorkspaceId`, `onSwitchWorkspace`, `onNewWorkspace`
- Replace the static wiki-name `<div>` at the top with `<WorkspaceSwitcher ...>`
- Keep existing settings button and nav items unchanged

---

## Step 8: Update `frontend/src/App.tsx`

**Add state:**
```tsx
const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
const [activeWorkspaceId, setActiveWorkspaceId] = useState('');
```

**`fetchWorkspaces()`**: `GET /api/workspaces` → update both state values.

Call `fetchWorkspaces()` inside the existing setup-status `useEffect` after `setSetupState('ready')`.

**`handleSwitchWorkspace(id)`**:
```tsx
const res = await fetch(`${API_BASE}/workspaces/${id}/switch`, { method: 'POST' });
const data = await res.json();
setActiveWorkspaceId(id);
setChatHistory([]);
setCurrentView('Wiki');
setSourcesMetadata({});
if (data.setup_required) {
  setSetupState('required');
} else {
  setWikiName(data.wiki_name || 'Wiki');
  setSetupState('ready');
}
fetchWorkspaces();
```

**`handleNewWorkspace()`**:
```tsx
const res = await fetch(`${API_BASE}/workspaces`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ name: 'New Workspace' }),
});
const data = await res.json();
setActiveWorkspaceId(data.id);
setChatHistory([]);
setCurrentView('Wiki');
setSourcesMetadata({});
setSetupState('required');
setReconfigureMode(false);
setExistingFolders([]);
fetchWorkspaces();
```

**Force remount on workspace switch** — add `key={activeWorkspaceId}` to `<WikiView>`, `<SourcesView>`, `<LintView>`, `<ArchiveView>` in `renderContent()`. This clears all internal state automatically.

**Pass to Sidebar:** `workspaces`, `activeWorkspaceId`, `onSwitchWorkspace`, `onNewWorkspace`.

---

## Step 9: Update `docker-compose.yml`

Add volume and mount:
```yaml
volumes:
  workspaces_data:

services:
  backend:
    volumes:
      - workspaces_data:/app/workspaces
      # keep old volumes for backwards-compat (legacy data still on disk during migration)
      - wiki_data:/app/wiki
      - sources_data:/app/sources
      - snapshots_data:/app/snapshots
```

---

## Files Changed / Created

| File | Change |
|---|---|
| `backend/agent/workspace_manager.py` | **NEW** |
| `backend/api/workspace_routes.py` | **NEW** |
| `frontend/src/components/WorkspaceSwitcher.tsx` | **NEW** |
| `backend/agent/wiki_manager.py` | setup-wizard branch version (already updated) |
| `backend/agent/setup_wizard.py` | setup-wizard branch version; add `update_workspace_name` call in `complete_setup` |
| `backend/api/routes.py` | remove hardcoded dirs, import getters, replace ~20 usages |
| `backend/api/setup_routes.py` | replace SCHEMA_DIR + dir imports; add workspace name update on complete |
| `backend/main.py` | replace init block, register workspace_router |
| `frontend/src/App.tsx` | add workspace state + handlers + pass to Sidebar + key={activeWorkspaceId} |
| `frontend/src/components/Sidebar.tsx` | embed WorkspaceSwitcher, add props |
| `docker-compose.yml` | add `workspaces_data` volume |

---

## Verification

1. **Migration test**: Start app with existing `schema/wiki_config.json` (Farago Projects data). Confirm `workspaces/registry.json` is created, `workspaces/default/` contains copied data, sidebar shows "Faragopedia" workspace.

2. **Workspace switcher**: Confirm the sidebar header shows current workspace name + chevron. Dropdown lists all workspaces.

3. **New workspace**: Click "+ New Workspace" → wizard appears → complete it → new workspace appears in switcher, switching to it loads the new (empty) wiki.

4. **Isolation**: Create two workspaces, add different pages to each, switch back and forth — confirm each shows only its own content (WikiView remounts via `key` prop).

5. **Docker**: `docker-compose up` — confirm `workspaces_data` volume is created, migration runs on first boot.

6. **Tests**: `cd backend && pytest tests/ -v` — all tests must pass (routes.py refactor is mechanical; existing tests create their own temp dirs so no paths break).