# Settings Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Settings slide-out drawer (theme toggle, reconfigure, export), a backend export/import API, and a SetupWizard import-from-backup flow.

**Architecture:** Theme state + `settingsOpen` flag live in `App.tsx`, applied via Tailwind's `dark:` class strategy. A new `SettingsDrawer` component overlays from the right. Three new backend endpoints handle bundle export, import staging, and import finalization. The SetupWizard gains a step-0 "Getting Started" screen offering fresh start vs import.

**Tech Stack:** React 18 + TypeScript + Tailwind CSS (frontend); FastAPI + Python stdlib `zipfile` (backend). `python-multipart` already in requirements.txt.

**Implementation split:** Backend tasks (1–5) → Claude. Frontend tasks (6–13) → Gemini per this plan.

---

## Spec reference
`docs/superpowers/specs/2026-04-22-settings-design.md`

---

## File map

### Backend (new/modified)
| File | Action | Responsibility |
|---|---|---|
| `backend/agent/setup_wizard.py` | Modify | Add `finalize_import()` function |
| `backend/api/export_routes.py` | Create | `GET /bundle`, `POST /import`, `POST /import/finalize` |
| `backend/main.py` | Modify | Register `export_router` under `/api/export` |
| `backend/tests/test_export_routes.py` | Create | Tests for all three endpoints |

### Frontend (new/modified)
| File | Action | Responsibility |
|---|---|---|
| `frontend/tailwind.config.js` | Modify | Add `darkMode: 'class'` |
| `frontend/src/App.tsx` | Modify | Theme state, `settingsOpen`, `useEffect`, render `SettingsDrawer` |
| `frontend/src/components/Sidebar.tsx` | Modify | Remove reconfigure button, add gear icon + `onOpenSettings` prop |
| `frontend/src/components/SettingsDrawer.tsx` | Create | Slide-out settings panel |
| `frontend/src/components/SetupWizard.tsx` | Modify | Add step-0 getting-started screen + import flow |
| `frontend/src/components/WikiView.tsx` | Modify | Dark mode `dark:` variants |
| `frontend/src/components/SourcesView.tsx` | Modify | Dark mode `dark:` variants |
| `frontend/src/components/ArchiveView.tsx` | Modify | Dark mode `dark:` variants |
| `frontend/src/components/LintView.tsx` | Modify | Dark mode `dark:` variants |

---

## Backend Tasks

---

### Task 1: Add `finalize_import` to setup_wizard.py

**Files:**
- Modify: `Faragopedia-Sales/backend/agent/setup_wizard.py`
- Test: `Faragopedia-Sales/backend/tests/test_export_routes.py` (written in Task 2)

**Context:** `complete_setup()` generates `SCHEMA.md` from entity types — that would overwrite the imported version. `finalize_import` does everything `complete_setup` does *except* writing `SCHEMA.md`, `SCHEMA_TEMPLATE.md`, and `company_profile.md` (already staged by the import endpoint).

- [ ] **Step 1: Add `finalize_import` to setup_wizard.py**

Open `Faragopedia-Sales/backend/agent/setup_wizard.py`. After the `complete_setup` function (line ~244), add:

```python
def finalize_import(schema_dir: str, wiki_dir: str, payload) -> None:
    """Finalise an import: create entity folders and write wiki_config.json.
    Does NOT touch SCHEMA.md or company_profile.md — import step already placed them.
    """
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

    config = {
        "wiki_name": payload.wiki_name,
        "org_name": payload.org_name,
        "setup_complete": True,
    }
    with open(os.path.join(schema_dir, "wiki_config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
```

- [ ] **Step 2: Verify `_field_to_dict` exists in the file**

Run:
```bash
grep -n "_field_to_dict" Faragopedia-Sales/backend/agent/setup_wizard.py
```
Expected: at least two hits (definition + call in `complete_setup`). If zero hits, it is inlined — check `complete_setup` and copy the serialisation logic into `finalize_import` directly.

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/backend/agent/setup_wizard.py
git commit -m "feat: add finalize_import to setup_wizard"
```

---

### Task 2: GET /api/export/bundle

**Files:**
- Create: `Faragopedia-Sales/backend/api/export_routes.py`
- Create: `Faragopedia-Sales/backend/tests/test_export_routes.py`

- [ ] **Step 1: Write the failing test**

Create `Faragopedia-Sales/backend/tests/test_export_routes.py`:

```python
import io
import json
import zipfile
import pytest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def dirs(tmp_path):
    schema_dir = tmp_path / "schema"
    wiki_dir = tmp_path / "wiki"
    schema_dir.mkdir()
    wiki_dir.mkdir()

    (schema_dir / "SCHEMA.md").write_text("# Schema content")
    (schema_dir / "company_profile.md").write_text("# Org Profile")
    (schema_dir / "wiki_config.json").write_text(
        json.dumps({"wiki_name": "TestWiki", "org_name": "TestOrg", "setup_complete": True})
    )
    (wiki_dir / "index.md").write_text("# Index")
    (wiki_dir / "log.md").write_text("# Log")
    return str(schema_dir), str(wiki_dir)


def _client(schema_dir, wiki_dir):
    with patch("api.export_routes.SCHEMA_DIR", schema_dir), \
         patch("api.export_routes.WIKI_DIR", wiki_dir):
        from api import export_routes
        import importlib
        importlib.reload(export_routes)
        app = FastAPI()
        app.include_router(export_routes.export_router)
        return TestClient(app)


def test_bundle_returns_zip_with_all_files(dirs):
    schema_dir, wiki_dir = dirs
    client = _client(schema_dir, wiki_dir)

    response = client.get("/bundle")

    assert response.status_code == 200
    assert "application/zip" in response.headers["content-type"]
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    names = zf.namelist()
    assert "SCHEMA.md" in names
    assert "company_profile.md" in names
    assert "wiki_config.json" in names
    assert "index.md" in names
    assert "log.md" in names


def test_bundle_skips_missing_files(dirs):
    schema_dir, wiki_dir = dirs
    import os
    os.remove(os.path.join(wiki_dir, "log.md"))
    client = _client(schema_dir, wiki_dir)

    response = client.get("/bundle")

    assert response.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    names = zf.namelist()
    assert "log.md" not in names
    assert "index.md" in names
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd Faragopedia-Sales && python -m pytest backend/tests/test_export_routes.py::test_bundle_returns_zip_with_all_files -v
```
Expected: `ModuleNotFoundError` or `ImportError` — `export_routes` doesn't exist yet.

- [ ] **Step 3: Create export_routes.py with GET /bundle**

Create `Faragopedia-Sales/backend/api/export_routes.py`:

```python
import io
import json
import os
import zipfile

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from api.routes import WIKI_DIR

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
SCHEMA_DIR = os.path.join(_BACKEND_DIR, "schema")

export_router = APIRouter()

_BUNDLE_FILES = [
    # (source_dir_attr, filename)
    ("schema", "SCHEMA.md"),
    ("schema", "company_profile.md"),
    ("schema", "wiki_config.json"),
    ("wiki", "index.md"),
    ("wiki", "log.md"),
]


@export_router.get("/bundle")
def export_bundle():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for source, filename in _BUNDLE_FILES:
            dir_path = SCHEMA_DIR if source == "schema" else WIKI_DIR
            full_path = os.path.join(dir_path, filename)
            if os.path.exists(full_path):
                zf.write(full_path, arcname=filename)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="wiki-bundle.zip"'},
    )
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd Faragopedia-Sales && python -m pytest backend/tests/test_export_routes.py::test_bundle_returns_zip_with_all_files backend/tests/test_export_routes.py::test_bundle_skips_missing_files -v
```
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/api/export_routes.py Faragopedia-Sales/backend/tests/test_export_routes.py
git commit -m "feat: add GET /api/export/bundle endpoint"
```

---

### Task 3: POST /api/export/import

**Files:**
- Modify: `Faragopedia-Sales/backend/api/export_routes.py`
- Modify: `Faragopedia-Sales/backend/tests/test_export_routes.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_export_routes.py`:

```python
def _make_zip(include_schema=True, include_profile=True, include_config=True, config_data=None):
    if config_data is None:
        config_data = {
            "wiki_name": "ImportedWiki",
            "org_name": "ImportedOrg",
            "org_description": "An imported org",
            "entity_types": [
                {
                    "folder_name": "clients",
                    "display_name": "Clients",
                    "description": "Client orgs",
                    "singular": "client",
                    "fields": [{"name": "name", "type": "string", "required": True}],
                    "sections": ["Overview"],
                }
            ],
        }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if include_schema:
            zf.writestr("SCHEMA.md", "# Imported Schema")
        if include_profile:
            zf.writestr("company_profile.md", "# Imported Org")
        if include_config:
            zf.writestr("wiki_config.json", json.dumps(config_data))
    buf.seek(0)
    return buf.read()


def test_import_stages_files_and_returns_config(dirs):
    schema_dir, wiki_dir = dirs
    client = _client(schema_dir, wiki_dir)
    zip_bytes = _make_zip()

    response = client.post(
        "/import",
        files={"file": ("wiki-bundle.zip", zip_bytes, "application/zip")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["wiki_name"] == "ImportedWiki"
    assert data["org_name"] == "ImportedOrg"
    assert len(data["entity_types"]) == 1
    assert os.path.exists(os.path.join(schema_dir, "SCHEMA.md"))
    assert open(os.path.join(schema_dir, "SCHEMA.md")).read() == "# Imported Schema"
    assert os.path.exists(os.path.join(schema_dir, "company_profile.md"))
    # wiki_config.json must NOT be written by import (finalize does that)
    config_on_disk = json.loads(open(os.path.join(schema_dir, "wiki_config.json")).read())
    assert config_on_disk.get("wiki_name") != "ImportedWiki"


def test_import_rejects_invalid_zip(dirs):
    schema_dir, wiki_dir = dirs
    client = _client(schema_dir, wiki_dir)

    response = client.post(
        "/import",
        files={"file": ("bad.zip", b"not a zip", "application/zip")},
    )
    assert response.status_code == 422


def test_import_rejects_missing_schema(dirs):
    schema_dir, wiki_dir = dirs
    client = _client(schema_dir, wiki_dir)
    zip_bytes = _make_zip(include_schema=False)

    response = client.post(
        "/import",
        files={"file": ("bundle.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 422


def test_import_rejects_missing_config(dirs):
    schema_dir, wiki_dir = dirs
    client = _client(schema_dir, wiki_dir)
    zip_bytes = _make_zip(include_config=False)

    response = client.post(
        "/import",
        files={"file": ("bundle.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run — verify failure**

```bash
cd Faragopedia-Sales && python -m pytest backend/tests/test_export_routes.py::test_import_stages_files_and_returns_config -v
```
Expected: FAIL — `/import` route doesn't exist yet.

- [ ] **Step 3: Add POST /import to export_routes.py**

Add this import at the top of `export_routes.py`:
```python
from fastapi import APIRouter, HTTPException, UploadFile, File
```
(replace the existing import line — `File` is the new addition)

Then append to `export_routes.py`:

```python
@export_router.post("/import")
async def import_bundle(file: UploadFile = File(...)):
    raw = await file.read()

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="Not a valid zip file")

    names = zf.namelist()

    if "SCHEMA.md" not in names:
        raise HTTPException(status_code=422, detail="zip must contain SCHEMA.md")
    if "wiki_config.json" not in names:
        raise HTTPException(status_code=422, detail="zip must contain wiki_config.json")

    try:
        config = json.loads(zf.read("wiki_config.json"))
    except (json.JSONDecodeError, KeyError) as exc:
        raise HTTPException(status_code=422, detail="wiki_config.json is not valid JSON") from exc

    os.makedirs(SCHEMA_DIR, exist_ok=True)
    zf.extract("SCHEMA.md", SCHEMA_DIR)
    if "company_profile.md" in names:
        zf.extract("company_profile.md", SCHEMA_DIR)

    return {
        "wiki_name": config.get("wiki_name", ""),
        "org_name": config.get("org_name", ""),
        "org_description": config.get("org_description", ""),
        "entity_types": config.get("entity_types", []),
    }
```

- [ ] **Step 4: Run all import tests — verify they pass**

```bash
cd Faragopedia-Sales && python -m pytest backend/tests/test_export_routes.py -k "import" -v
```
Expected: all 4 import tests PASS.

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/api/export_routes.py Faragopedia-Sales/backend/tests/test_export_routes.py
git commit -m "feat: add POST /api/export/import endpoint"
```

---

### Task 4: POST /api/export/import/finalize

**Files:**
- Modify: `Faragopedia-Sales/backend/api/export_routes.py`
- Modify: `Faragopedia-Sales/backend/tests/test_export_routes.py`

- [ ] **Step 1: Write the failing test**

Append to `test_export_routes.py`:

```python
def test_finalize_creates_folders_and_config(dirs):
    schema_dir, wiki_dir = dirs
    # Pre-stage SCHEMA.md as import step would
    import os
    with open(os.path.join(schema_dir, "SCHEMA.md"), "w") as f:
        f.write("# Imported Schema")
    with open(os.path.join(schema_dir, "company_profile.md"), "w") as f:
        f.write("# Imported Org")

    client = _client(schema_dir, wiki_dir)
    payload = {
        "wiki_name": "ImportedWiki",
        "org_name": "ImportedOrg",
        "org_description": "An org",
        "entity_types": [
            {
                "folder_name": "clients",
                "display_name": "Clients",
                "description": "Client orgs",
                "singular": "client",
                "fields": [{"name": "name", "type": "string", "required": True}],
                "sections": ["Overview"],
            }
        ],
    }

    response = client.post("/import/finalize", json=payload)

    assert response.status_code == 200
    assert response.json()["success"] is True
    config_path = os.path.join(schema_dir, "wiki_config.json")
    assert os.path.exists(config_path)
    config = json.loads(open(config_path).read())
    assert config["setup_complete"] is True
    assert config["wiki_name"] == "ImportedWiki"
    assert os.path.isdir(os.path.join(wiki_dir, "clients"))
    assert os.path.exists(os.path.join(wiki_dir, "clients", "_type.yaml"))
    # Must NOT overwrite SCHEMA.md
    assert open(os.path.join(schema_dir, "SCHEMA.md")).read() == "# Imported Schema"
```

- [ ] **Step 2: Run — verify failure**

```bash
cd Faragopedia-Sales && python -m pytest backend/tests/test_export_routes.py::test_finalize_creates_folders_and_config -v
```
Expected: FAIL — `/import/finalize` doesn't exist.

- [ ] **Step 3: Add the finalize endpoint to export_routes.py**

Add this import to the top of `export_routes.py` (update the import block):
```python
from agent.setup_wizard import SetupPayload, finalize_import
from api.routes import ARCHIVE_DIR, SNAPSHOTS_DIR, SOURCES_DIR, WIKI_DIR, set_wiki_manager
```

Then append the endpoint:

```python
@export_router.post("/import/finalize")
def import_finalize(payload: SetupPayload):
    try:
        finalize_import(SCHEMA_DIR, WIKI_DIR, payload)
        from agent.wiki_manager import WikiManager
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
```

- [ ] **Step 4: Run all export tests**

```bash
cd Faragopedia-Sales && python -m pytest backend/tests/test_export_routes.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/api/export_routes.py Faragopedia-Sales/backend/tests/test_export_routes.py
git commit -m "feat: add POST /api/export/import/finalize endpoint"
```

---

### Task 5: Register export_router in main.py

**Files:**
- Modify: `Faragopedia-Sales/backend/main.py`

- [ ] **Step 1: Add the router**

In `main.py`, add after the existing `from api.setup_routes import ...` line:
```python
from api.export_routes import export_router
```

And after the existing `app.include_router(setup_router, prefix="/api/setup")` line:
```python
app.include_router(export_router, prefix="/api/export")
```

- [ ] **Step 2: Verify server starts without errors**

```bash
cd Faragopedia-Sales/backend && python -m uvicorn main:app --port 8300 --reload &
sleep 2 && curl -s http://localhost:8300/ && kill %1
```
Expected: `{"message":"Hello World from FastAPI"}`

- [ ] **Step 3: Run full backend test suite**

```bash
cd Faragopedia-Sales && python -m pytest backend/tests/ -v --tb=short
```
Expected: all tests PASS (no regressions).

- [ ] **Step 4: Commit**

```bash
git add Faragopedia-Sales/backend/main.py
git commit -m "feat: register export_router in main.py"
```

---

## Frontend Tasks

> **For Gemini:** The backend is already complete by this point. Read each section fully before implementing — the code shown is the exact target. Follow the existing code style throughout: Tailwind CSS classes, TypeScript interfaces, React functional components. All API calls use `API_BASE` from `../config` (resolves to `http://localhost:8300/api`).

---

### Task 6: Enable Tailwind dark mode

**Files:**
- Modify: `Faragopedia-Sales/frontend/tailwind.config.js`

- [ ] **Step 1: Add `darkMode: 'class'`**

Replace the contents of `tailwind.config.js` with:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
```

- [ ] **Step 2: Verify Vite picks up the change**

```bash
cd Faragopedia-Sales/frontend && npm run build 2>&1 | tail -5
```
Expected: build completes without errors.

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/tailwind.config.js
git commit -m "feat: enable Tailwind dark mode class strategy"
```

---

### Task 7: Theme state and SettingsDrawer wiring in App.tsx

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/App.tsx`

- [ ] **Step 1: Add theme state and settingsOpen state**

In `App.tsx`, after the existing state declarations (around line 18), add:

```tsx
const [theme, setTheme] = useState<'light' | 'dark' | 'system'>(() => {
  return (localStorage.getItem('faragopedia-theme') as 'light' | 'dark' | 'system') ?? 'system';
});
const [settingsOpen, setSettingsOpen] = useState(false);
```

- [ ] **Step 2: Add theme useEffect**

After the existing `useEffect` blocks, add:

```tsx
useEffect(() => {
  localStorage.setItem('faragopedia-theme', theme);
  const root = document.documentElement;
  if (theme === 'dark') {
    root.classList.add('dark');
  } else if (theme === 'light') {
    root.classList.remove('dark');
  } else {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    root.classList.toggle('dark', mq.matches);
    const handler = (e: MediaQueryListEvent) => root.classList.toggle('dark', e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }
}, [theme]);
```

- [ ] **Step 3: Add SettingsDrawer import**

At the top of `App.tsx`, add:
```tsx
import SettingsDrawer from './components/SettingsDrawer';
```

- [ ] **Step 4: Update Sidebar render to remove onReconfigure and add onOpenSettings**

Find the `<Sidebar` JSX in the return statement (inside the sidebar container div). Replace:
```tsx
<Sidebar
  currentView={currentView}
  onViewChange={(v) => { setCurrentView(v); setMobileMenuOpen(false); }}
  wikiName={wikiName}
  onReconfigure={handleReconfigure}
/>
```
With:
```tsx
<Sidebar
  currentView={currentView}
  onViewChange={(v) => { setCurrentView(v); setMobileMenuOpen(false); }}
  wikiName={wikiName}
  onOpenSettings={() => setSettingsOpen(true)}
/>
```

- [ ] **Step 5: Render SettingsDrawer**

Immediately before the closing `</div>` of the outermost return div (after `<ToastContainer />`), add:

```tsx
<SettingsDrawer
  open={settingsOpen}
  onClose={() => setSettingsOpen(false)}
  theme={theme}
  onThemeChange={setTheme}
  onReconfigure={() => { setSettingsOpen(false); handleReconfigure(); }}
/>
```

- [ ] **Step 6: Commit**

```bash
git add Faragopedia-Sales/frontend/src/App.tsx
git commit -m "feat: add theme state, settingsOpen, and SettingsDrawer wiring to App.tsx"
```

---

### Task 8: Update Sidebar.tsx

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Replace Sidebar contents entirely**

Replace the full contents of `Sidebar.tsx` with:

```tsx
import React from 'react';
import { Book, MessageSquare, Layers, Archive, Activity, Settings } from 'lucide-react';

interface SidebarProps {
  currentView: string;
  onViewChange: (view: string) => void;
  wikiName: string;
  onOpenSettings: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ currentView, onViewChange, wikiName, onOpenSettings }) => {
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

      <div className="p-4 border-t border-gray-700 flex items-center justify-between">
        <p className="text-xs text-gray-500 uppercase tracking-wider">{wikiName} v0.2.0</p>
        <button
          onClick={onOpenSettings}
          title="Settings"
          className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
        >
          <Settings className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
};

export default Sidebar;
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd Faragopedia-Sales/frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors about `Sidebar`.

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/Sidebar.tsx
git commit -m "feat: update Sidebar — replace reconfigure button with settings gear icon"
```

---

### Task 9: Create SettingsDrawer.tsx

**Files:**
- Create: `Faragopedia-Sales/frontend/src/components/SettingsDrawer.tsx`

- [ ] **Step 1: Create the component**

Create `Faragopedia-Sales/frontend/src/components/SettingsDrawer.tsx`:

```tsx
import React, { useEffect, useState } from 'react';
import { X, RefreshCw, Download, Settings } from 'lucide-react';
import { API_BASE } from '../config';

interface SettingsDrawerProps {
  open: boolean;
  onClose: () => void;
  theme: 'light' | 'dark' | 'system';
  onThemeChange: (t: 'light' | 'dark' | 'system') => void;
  onReconfigure: () => void;
}

const THEMES: { value: 'light' | 'dark' | 'system'; label: string }[] = [
  { value: 'light', label: '☀ Light' },
  { value: 'system', label: '◑ System' },
  { value: 'dark', label: '● Dark' },
];

const SettingsDrawer: React.FC<SettingsDrawerProps> = ({
  open,
  onClose,
  theme,
  onThemeChange,
  onReconfigure,
}) => {
  const [wikiName, setWikiName] = useState('');
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (open && !wikiName) {
      fetch(`${API_BASE}/setup/config`)
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data?.wiki_name) setWikiName(data.wiki_name); })
        .catch(() => {});
    }
  }, [open]);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const res = await fetch(`${API_BASE}/export/bundle`);
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'wiki-bundle.zip';
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/40 z-40"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={`fixed inset-y-0 right-0 z-50 w-80 bg-white dark:bg-gray-900 shadow-2xl flex flex-col transform transition-transform duration-300 ease-in-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 font-semibold text-gray-900 dark:text-gray-100">
            <Settings className="w-4 h-4" />
            Settings
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">

          {/* Appearance */}
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-3">
              Appearance
            </p>
            <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-4">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Theme</p>
              <div className="flex bg-gray-200 dark:bg-gray-700 rounded-lg p-1 gap-1">
                {THEMES.map(t => (
                  <button
                    key={t.value}
                    onClick={() => onThemeChange(t.value)}
                    className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-all ${
                      theme === t.value
                        ? 'bg-blue-600 text-white shadow'
                        : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Wiki */}
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-3">
              Wiki
            </p>
            <button
              onClick={onReconfigure}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors text-sm"
            >
              <RefreshCw className="w-4 h-4" />
              Reconfigure Wiki
            </button>
          </div>

          {/* Export */}
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-3">
              Export
            </p>
            <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-4">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Wiki infrastructure files
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mb-4">
                SCHEMA.md · index.md · log.md · company_profile.md · wiki_config.json
              </p>
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors text-sm font-medium"
              >
                <Download className="w-4 h-4" />
                {downloading ? 'Downloading…' : 'Download as .zip'}
              </button>
            </div>
          </div>

        </div>

        {/* Footer */}
        {wikiName && (
          <div className="px-5 py-3 border-t border-gray-100 dark:border-gray-800">
            <p className="text-xs text-gray-400 dark:text-gray-600">{wikiName}</p>
          </div>
        )}
      </div>
    </>
  );
};

export default SettingsDrawer;
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd Faragopedia-Sales/frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/SettingsDrawer.tsx
git commit -m "feat: add SettingsDrawer component"
```

---

### Task 10: SetupWizard — Step 0 (Getting Started)

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/SetupWizard.tsx`

**Context:** The wizard currently starts with step `1` (Identity). We insert step `0` before it. In `reconfigureMode` this step is skipped entirely. The import path calls `POST /api/export/import` then shows a pre-filled step 3 (Confirm) before calling `POST /api/export/import/finalize`.

- [ ] **Step 1: Add import state and the step-0 UI**

Open `SetupWizard.tsx`. Find the `SetupWizardProps` interface and add the import-related state inside the component. These changes need to be made in context with the existing code:

**a) Inside the component function, after the existing `useState` declarations, add:**

```tsx
const [importLoading, setImportLoading] = useState(false);
const [importError, setImportError] = useState('');
const [importedConfig, setImportedConfig] = useState<{
  wiki_name: string;
  org_name: string;
  org_description: string;
  entity_types: EntityType[];
} | null>(null);
```

**b) Locate `const [step, setStep] = useState(1);` and change it to:**

```tsx
const [step, setStep] = useState(reconfigureMode ? 1 : 0);
```

**c) Add the import handler function inside the component (after other handler functions):**

```tsx
const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;
  setImportError('');
  setImportLoading(true);
  try {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/export/import`, { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      setImportError(err.detail ?? 'Upload failed');
      return;
    }
    const data = await res.json();
    setImportedConfig(data);
    setWikiName(data.wiki_name);
    setOrgName(data.org_name);
    setOrgDescription(data.org_description);
    setEntityTypes(data.entity_types ?? []);
    setStep(3);
  } catch {
    setImportError('Failed to read zip file.');
  } finally {
    setImportLoading(false);
  }
};
```

Note: `setWikiName`, `setOrgName`, `setOrgDescription`, `setEntityTypes` are the existing state setters in the wizard — check their names against the actual code.

**d) In the main render, before the existing `if (step === 1)` block, add:**

```tsx
if (step === 0) {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center p-6">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl p-8 w-full max-w-md">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Get Started</h1>
        <p className="text-gray-500 dark:text-gray-400 mb-8">Set up your wiki from scratch or restore from a backup.</p>

        <div className="space-y-3">
          <button
            onClick={() => setStep(1)}
            className="w-full flex flex-col items-start gap-1 px-5 py-4 rounded-xl border-2 border-blue-500 bg-blue-50 dark:bg-blue-950/30 hover:bg-blue-100 dark:hover:bg-blue-950/50 transition-colors"
          >
            <span className="font-semibold text-blue-700 dark:text-blue-400">Start fresh</span>
            <span className="text-sm text-blue-500 dark:text-blue-500">Design your wiki schema from scratch or use a preset.</span>
          </button>

          <label className="w-full flex flex-col items-start gap-1 px-5 py-4 rounded-xl border-2 border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors cursor-pointer">
            <span className="font-semibold text-gray-700 dark:text-gray-300">
              {importLoading ? 'Importing…' : 'Import from backup'}
            </span>
            <span className="text-sm text-gray-400">Restore schema and settings from a wiki-bundle.zip file.</span>
            <input
              type="file"
              accept=".zip"
              className="hidden"
              onChange={handleImportFile}
              disabled={importLoading}
            />
          </label>
        </div>

        {importError && (
          <p className="mt-4 text-sm text-red-600 dark:text-red-400">{importError}</p>
        )}
      </div>
    </div>
  );
}
```

**e) Find the existing `step === 3` (Confirm) render block. Wrap the confirm button's `onClick` handler so it calls the right endpoint depending on whether this is an import flow:**

Find the confirm/complete button (it calls `handleComplete` or similar). Change it so that if `importedConfig !== null`, it calls the finalize endpoint instead:

```tsx
const handleConfirm = async () => {
  if (importedConfig) {
    // Import flow — call finalize
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/export/import/finalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wiki_name: wikiName,
          org_name: orgName,
          org_description: orgDescription,
          entity_types: entityTypes,
        }),
      });
      if (!res.ok) throw new Error('Finalize failed');
      onComplete();
    } catch (err) {
      setError('Failed to finalize import.');
    } finally {
      setLoading(false);
    }
  } else {
    // Normal flow
    handleComplete(); // call whatever the existing complete function is named
  }
};
```

Replace the confirm button's `onClick` with `handleConfirm`. Check the actual variable names (`setLoading`, `setError`, `handleComplete`) against the existing code before applying.

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd Faragopedia-Sales/frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/SetupWizard.tsx
git commit -m "feat: add step-0 getting-started screen and import-from-backup flow to SetupWizard"
```

---

### Task 11: Dark mode — color mapping reference

> **Read this before Tasks 12–13.** No code changes in this task — it defines the patterns to apply.

The app currently uses hardcoded light-mode Tailwind classes. Dark mode is applied by adding `dark:` variants alongside existing classes. The sidebar (`bg-gray-800`) is already dark; it needs no changes.

**Color mapping table — apply to all components:**

| Light class | Add dark variant |
|---|---|
| `bg-white` | `dark:bg-gray-900` |
| `bg-gray-50` | `dark:bg-gray-950` |
| `bg-gray-100` | `dark:bg-gray-800` |
| `bg-gray-200` | `dark:bg-gray-700` |
| `text-gray-900` | `dark:text-gray-100` |
| `text-gray-800` | `dark:text-gray-200` |
| `text-gray-700` | `dark:text-gray-300` |
| `text-gray-600` | `dark:text-gray-400` |
| `text-gray-500` | `dark:text-gray-400` |
| `text-gray-400` | `dark:text-gray-500` |
| `border-gray-200` | `dark:border-gray-700` |
| `border-gray-100` | `dark:border-gray-800` |
| `shadow-sm` | (no change needed) |
| `prose-slate` | `dark:prose-invert` |
| `ring-blue-500` | (no change needed) |

**Example transformation:**
```tsx
// Before
<div className="bg-white border border-gray-200 text-gray-900">

// After
<div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100">
```

**Approach:** Work through each component file top to bottom. Search for each class in the left column, add the corresponding `dark:` variant after it (space-separated, within the same string).

---

### Task 12: Dark mode — App.tsx inline chat and layout

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/App.tsx`

- [ ] **Step 1: Apply dark mode to App.tsx**

Using the color mapping table from Task 11, update these specific sections in `App.tsx`:

**Main layout wrapper** (the `flex h-screen` div):
```tsx
// Before
<div className="flex h-screen bg-gray-50 font-sans antialiased text-gray-900 overflow-hidden">
// After
<div className="flex h-screen bg-gray-50 dark:bg-gray-950 font-sans antialiased text-gray-900 dark:text-gray-100 overflow-hidden">
```

**Top bar** (the `bg-white border-b` div):
```tsx
// Before
<div className="bg-white border-b px-4 py-4 flex items-center ...">
// After
<div className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-4 py-4 flex items-center ...">
```

**Chat container** (the `bg-white rounded-2xl` div):
```tsx
// Before
<div className="bg-white rounded-2xl shadow-sm border border-gray-200 flex-grow flex flex-col overflow-hidden mb-8">
// After
<div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 flex-grow flex flex-col overflow-hidden mb-8">
```

**Chat assistant bubble**:
```tsx
// Before
'bg-gray-100 text-gray-800 rounded-tl-none prose prose-sm prose-slate max-w-none'
// After
'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-tl-none prose prose-sm prose-slate dark:prose-invert max-w-none'
```

**Chat input area** (`bg-gray-50 border-t`):
```tsx
// Before
<div className="p-4 bg-gray-50 border-t">
// After
<div className="p-4 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
```

**Chat input field**:
```tsx
// Before
className="w-full px-6 py-4 bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all pr-16"
// After
className="w-full px-6 py-4 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all pr-16 placeholder:text-gray-400 dark:placeholder:text-gray-500"
```

**Chat empty state text**:
```tsx
// Before
<div className="h-full flex flex-col items-center justify-center text-gray-400 space-y-4">
// After
<div className="h-full flex flex-col items-center justify-center text-gray-400 dark:text-gray-600 space-y-4">
```

- [ ] **Step 2: Commit**

```bash
git add Faragopedia-Sales/frontend/src/App.tsx
git commit -m "feat: dark mode variants for App.tsx layout and chat UI"
```

---

### Task 13: Dark mode — view components

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/WikiView.tsx`
- Modify: `Faragopedia-Sales/frontend/src/components/SourcesView.tsx`
- Modify: `Faragopedia-Sales/frontend/src/components/ArchiveView.tsx`
- Modify: `Faragopedia-Sales/frontend/src/components/LintView.tsx`

- [ ] **Step 1: Apply dark mode to WikiView.tsx**

Read `WikiView.tsx` in full. Apply the color mapping table from Task 11 to every `className` string in the file. Key patterns to find:
- All `bg-white`, `bg-gray-50`, `bg-gray-100` divs — add `dark:` equivalents
- All `text-gray-*` — add `dark:` equivalents  
- All `border-gray-*` — add `dark:` equivalents
- Any `prose` classes — add `dark:prose-invert`
- Inputs (`<input>`, `<textarea>`) with `bg-white border-gray-*` — add dark variants + `dark:text-gray-100`

Commit when done:
```bash
git add Faragopedia-Sales/frontend/src/components/WikiView.tsx
git commit -m "feat: dark mode variants for WikiView"
```

- [ ] **Step 2: Apply dark mode to SourcesView.tsx**

Read `SourcesView.tsx` in full. Apply the same mapping. Pay attention to status badges (ingested/pending) which may use `bg-green-100 text-green-700` — add `dark:bg-green-900/30 dark:text-green-400` equivalents.

Commit:
```bash
git add Faragopedia-Sales/frontend/src/components/SourcesView.tsx
git commit -m "feat: dark mode variants for SourcesView"
```

- [ ] **Step 3: Apply dark mode to ArchiveView.tsx**

Read `ArchiveView.tsx` in full. Apply the mapping.

Commit:
```bash
git add Faragopedia-Sales/frontend/src/components/ArchiveView.tsx
git commit -m "feat: dark mode variants for ArchiveView"
```

- [ ] **Step 4: Apply dark mode to LintView.tsx**

Read `LintView.tsx` in full. Apply the mapping.

Commit:
```bash
git add Faragopedia-Sales/frontend/src/components/LintView.tsx
git commit -m "feat: dark mode variants for LintView"
```

- [ ] **Step 5: Build check**

```bash
cd Faragopedia-Sales/frontend && npm run build 2>&1 | tail -10
```
Expected: build completes with no errors.

---

## Completion checklist

- [ ] All backend tests pass: `cd Faragopedia-Sales && python -m pytest backend/tests/ -v`
- [ ] Frontend builds without errors: `cd Faragopedia-Sales/frontend && npm run build`
- [ ] TypeScript clean: `cd Faragopedia-Sales/frontend && npx tsc --noEmit`
- [ ] Settings gear icon opens drawer from sidebar
- [ ] Theme toggle persists across page reloads
- [ ] Download .zip contains all 5 files
- [ ] SetupWizard step 0 shows on fresh install (not in reconfigureMode)
- [ ] Import from backup uploads zip, pre-fills wizard, skips to confirm
- [ ] Import finalize creates entity folders + wiki_config.json without overwriting SCHEMA.md
