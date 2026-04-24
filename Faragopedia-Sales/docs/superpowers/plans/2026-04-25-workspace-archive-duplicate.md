# Workspace Archive & Duplicate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add archive (soft-hide + restore) and duplicate (full copy or template copy) actions to the workspace switcher, accessible via a `...` context menu on each workspace row.

**Architecture:** Three new `workspace_manager` functions handle business logic; three new route endpoints expose them via HTTP. The frontend gains a `DuplicateWorkspaceModal` component and a redesigned `WorkspaceSwitcher` with per-row context menus and a collapsed archived section.

**Tech Stack:** Python/FastAPI, pytest, React/TypeScript, Tailwind CSS, Lucide icons.

---

## File Map

| File | Change |
|------|--------|
| `backend/agent/workspace_manager.py` | Add `archive_workspace`, `unarchive_workspace`, `duplicate_workspace` |
| `backend/api/workspace_routes.py` | Add `DuplicateWorkspaceRequest`, 3 new endpoints |
| `backend/tests/test_workspace_archive_duplicate.py` | Create — all new backend tests |
| `frontend/src/components/WorkspaceSwitcher.tsx` | Overhaul — context menus, archived section, new props |
| `frontend/src/components/DuplicateWorkspaceModal.tsx` | Create — new modal component |
| `frontend/src/components/Sidebar.tsx` | Add 3 new prop types, thread through |
| `frontend/src/App.tsx` | Add `archived?` to Workspace type, add 3 handlers, pass new props |

---

## Task 1: archive_workspace and unarchive_workspace (workspace_manager + tests)

**Files:**
- Create: `backend/tests/test_workspace_archive_duplicate.py`
- Modify: `backend/agent/workspace_manager.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_workspace_archive_duplicate.py`:

```python
import json
import os
import pytest
import agent.workspace_manager as wm


@pytest.fixture
def ws_env(tmp_path, monkeypatch):
    monkeypatch.setattr(wm, "REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setattr(wm, "WORKSPACES_BASE", str(tmp_path))
    monkeypatch.setattr(wm, "_active_workspace_id", "ws-a")

    for ws_id in ("ws-a", "ws-b"):
        for sub in ("wiki", "sources", "archive", "snapshots", "schema"):
            os.makedirs(tmp_path / ws_id / sub, exist_ok=True)

    registry = {
        "active_workspace_id": "ws-a",
        "workspaces": [
            {"id": "ws-a", "name": "Workspace A", "created_at": "2026-01-01T00:00:00"},
            {"id": "ws-b", "name": "Workspace B", "created_at": "2026-01-01T00:00:00"},
        ],
    }
    (tmp_path / "registry.json").write_text(json.dumps(registry))
    return tmp_path


def test_archive_workspace_sets_flag(ws_env):
    result = wm.archive_workspace("ws-b")
    assert result["archived"] is True
    registry = json.loads((ws_env / "registry.json").read_text())
    ws_b = next(ws for ws in registry["workspaces"] if ws["id"] == "ws-b")
    assert ws_b["archived"] is True


def test_archive_active_workspace_raises(ws_env):
    with pytest.raises(ValueError, match="active"):
        wm.archive_workspace("ws-a")


def test_archive_nonexistent_raises(ws_env):
    with pytest.raises(ValueError, match="not found"):
        wm.archive_workspace("no-such-ws")


def test_unarchive_workspace_clears_flag(ws_env):
    # Manually archive first
    reg = json.loads((ws_env / "registry.json").read_text())
    for ws in reg["workspaces"]:
        if ws["id"] == "ws-b":
            ws["archived"] = True
    (ws_env / "registry.json").write_text(json.dumps(reg))

    result = wm.unarchive_workspace("ws-b")
    assert result["archived"] is False
    registry = json.loads((ws_env / "registry.json").read_text())
    ws_b = next(ws for ws in registry["workspaces"] if ws["id"] == "ws-b")
    assert ws_b["archived"] is False


def test_unarchive_nonexistent_raises(ws_env):
    with pytest.raises(ValueError, match="not found"):
        wm.unarchive_workspace("no-such-ws")
```

- [ ] **Step 2: Run to verify failures**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_workspace_archive_duplicate.py -v 2>&1 | head -30
```

Expected: 5 failures with `AttributeError: module ... has no attribute 'archive_workspace'`

- [ ] **Step 3: Implement archive_workspace and unarchive_workspace**

In `backend/agent/workspace_manager.py`, add after `delete_workspace` (after line 232):

```python
def archive_workspace(workspace_id: str) -> dict:
    """Set archived=True on a workspace registry entry."""
    if workspace_id == _active_workspace_id:
        raise ValueError("Cannot archive the active workspace.")
    registry = _read_registry()
    for ws in registry.get("workspaces", []):
        if ws["id"] == workspace_id:
            ws["archived"] = True
            _write_registry(registry)
            return ws
    raise ValueError(f"Workspace '{workspace_id}' not found.")


def unarchive_workspace(workspace_id: str) -> dict:
    """Set archived=False on a workspace registry entry."""
    registry = _read_registry()
    for ws in registry.get("workspaces", []):
        if ws["id"] == workspace_id:
            ws["archived"] = False
            _write_registry(registry)
            return ws
    raise ValueError(f"Workspace '{workspace_id}' not found.")
```

- [ ] **Step 4: Run to verify they pass**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_workspace_archive_duplicate.py -v 2>&1 | head -30
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/agent/workspace_manager.py \
        Faragopedia-Sales/backend/tests/test_workspace_archive_duplicate.py
git commit -m "feat: add archive_workspace and unarchive_workspace to workspace_manager"
```

---

## Task 2: duplicate_workspace (workspace_manager + tests)

**Files:**
- Modify: `backend/tests/test_workspace_archive_duplicate.py`
- Modify: `backend/agent/workspace_manager.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_workspace_archive_duplicate.py`:

```python
@pytest.fixture
def ws_with_content(tmp_path, monkeypatch):
    """ws_env with content files in ws-a for copy testing."""
    monkeypatch.setattr(wm, "REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setattr(wm, "WORKSPACES_BASE", str(tmp_path))
    monkeypatch.setattr(wm, "_active_workspace_id", "ws-a")
    monkeypatch.setattr(wm, "_active_dirs", {
        "wiki_dir":      str(tmp_path / "ws-a" / "wiki"),
        "sources_dir":   str(tmp_path / "ws-a" / "sources"),
        "archive_dir":   str(tmp_path / "ws-a" / "archive"),
        "snapshots_dir": str(tmp_path / "ws-a" / "snapshots"),
        "schema_dir":    str(tmp_path / "ws-a" / "schema"),
    })

    # Create ws-a with content
    schema = tmp_path / "ws-a" / "schema"
    wiki = tmp_path / "ws-a" / "wiki"
    for sub in ("wiki", "sources", "archive", "snapshots", "schema"):
        os.makedirs(tmp_path / "ws-a" / sub, exist_ok=True)

    (schema / "wiki_config.json").write_text(json.dumps({"setup_complete": True, "wiki_name": "A"}))
    (schema / "SCHEMA.md").write_text("# Schema A")

    clients = wiki / "clients"
    clients.mkdir()
    (clients / "_type.yaml").write_text("name: Clients\n")
    (clients / "_template.md").write_text("# Template\n")
    (clients / "acme.md").write_text("# Acme\n")
    (wiki / "index.md").write_text("# Index\n")

    registry = {
        "active_workspace_id": "ws-a",
        "workspaces": [
            {"id": "ws-a", "name": "Workspace A", "created_at": "2026-01-01T00:00:00"},
        ],
    }
    (tmp_path / "registry.json").write_text(json.dumps(registry))
    return tmp_path


def test_duplicate_full_copies_all_content(ws_with_content):
    result = wm.duplicate_workspace("ws-a", "Copy of A", "full")
    new_id = result["id"]
    assert result["setup_required"] is False

    new_wiki = ws_with_content / new_id / "wiki"
    assert (new_wiki / "clients" / "_type.yaml").exists()
    assert (new_wiki / "clients" / "acme.md").exists()
    assert (new_wiki / "index.md").exists()

    new_schema = ws_with_content / new_id / "schema"
    assert (new_schema / "wiki_config.json").exists()
    assert (new_schema / "SCHEMA.md").exists()


def test_duplicate_full_registers_new_workspace(ws_with_content):
    result = wm.duplicate_workspace("ws-a", "Copy of A", "full")
    registry = json.loads((ws_with_content / "registry.json").read_text())
    ids = [ws["id"] for ws in registry["workspaces"]]
    assert result["id"] in ids
    new_entry = next(ws for ws in registry["workspaces"] if ws["id"] == result["id"])
    assert new_entry.get("archived") is False


def test_duplicate_template_copies_only_structure(ws_with_content):
    result = wm.duplicate_workspace("ws-a", "Template Copy", "template")
    new_id = result["id"]
    assert result["setup_required"] is True

    new_wiki = ws_with_content / new_id / "wiki"
    assert (new_wiki / "clients" / "_type.yaml").exists()
    assert (new_wiki / "clients" / "_template.md").exists()
    assert not (new_wiki / "clients" / "acme.md").exists()

    new_schema = ws_with_content / new_id / "schema"
    assert (new_schema / "SCHEMA.md").exists()
    assert not (new_schema / "wiki_config.json").exists()


def test_duplicate_nonexistent_raises(ws_with_content):
    with pytest.raises(ValueError, match="not found"):
        wm.duplicate_workspace("no-such", "Name", "full")


def test_duplicate_invalid_mode_raises(ws_with_content):
    with pytest.raises(ValueError, match="Invalid mode"):
        wm.duplicate_workspace("ws-a", "Name", "invalid")


def test_duplicate_slug_uniqueness(ws_with_content):
    result1 = wm.duplicate_workspace("ws-a", "Copy", "full")
    # Re-patch active to the original after first duplicate switched it
    import agent.workspace_manager as wm2
    wm2._active_workspace_id = result1["id"]
    result2 = wm.duplicate_workspace("ws-a", "Copy", "full")
    assert result1["id"] != result2["id"]
```

- [ ] **Step 2: Run to verify failures**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_workspace_archive_duplicate.py::test_duplicate_full_copies_all_content -v 2>&1 | head -20
```

Expected: FAIL with `AttributeError: module ... has no attribute 'duplicate_workspace'`

- [ ] **Step 3: Implement duplicate_workspace**

In `backend/agent/workspace_manager.py`, add after `unarchive_workspace`:

```python
def duplicate_workspace(source_id: str, name: str, mode: str) -> dict:
    """Duplicate a workspace. mode must be 'full' or 'template'."""
    if mode not in ("full", "template"):
        raise ValueError(f"Invalid mode: {mode!r}. Must be 'full' or 'template'.")

    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    slug = slug[:50]
    if not slug:
        slug = "workspace"

    registry = _read_registry()
    existing_ids = {ws["id"] for ws in registry.get("workspaces", [])}

    source_entry = next((ws for ws in registry.get("workspaces", []) if ws["id"] == source_id), None)
    if source_entry is None:
        raise ValueError(f"Workspace '{source_id}' not found.")

    if slug in existing_ids:
        counter = 2
        while f"{slug}-{counter}" in existing_ids:
            counter += 1
        slug = f"{slug}-{counter}"

    source_dirs = workspace_dirs(source_id)
    new_dirs = workspace_dirs(slug)

    if mode == "full":
        for key in ("wiki_dir", "sources_dir", "archive_dir", "snapshots_dir", "schema_dir"):
            src = source_dirs[key]
            dst = new_dirs[key]
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                os.makedirs(dst, exist_ok=True)
        setup_required = False
    else:  # template
        for path in new_dirs.values():
            os.makedirs(path, exist_ok=True)
        src_schema = source_dirs["schema_dir"]
        dst_schema = new_dirs["schema_dir"]
        if os.path.isdir(src_schema):
            shutil.copytree(src_schema, dst_schema, dirs_exist_ok=True)
        wiki_config_path = os.path.join(dst_schema, "wiki_config.json")
        if os.path.isfile(wiki_config_path):
            os.remove(wiki_config_path)
        src_wiki = source_dirs["wiki_dir"]
        dst_wiki = new_dirs["wiki_dir"]
        if os.path.isdir(src_wiki):
            for item in os.listdir(src_wiki):
                src_folder = os.path.join(src_wiki, item)
                if os.path.isdir(src_folder):
                    dst_folder = os.path.join(dst_wiki, item)
                    os.makedirs(dst_folder, exist_ok=True)
                    for fname in ("_type.yaml", "_template.md"):
                        src_file = os.path.join(src_folder, fname)
                        if os.path.isfile(src_file):
                            shutil.copy2(src_file, os.path.join(dst_folder, fname))
        setup_required = True

    entry = {
        "id": slug,
        "name": name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "archived": False,
    }
    registry.setdefault("workspaces", []).append(entry)
    _write_registry(registry)
    set_active_workspace(slug)

    return {"id": slug, "name": name, "setup_required": setup_required}
```

- [ ] **Step 4: Run to verify all duplicate tests pass**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_workspace_archive_duplicate.py -v 2>&1 | tail -20
```

Expected: All tests PASSED

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/agent/workspace_manager.py \
        Faragopedia-Sales/backend/tests/test_workspace_archive_duplicate.py
git commit -m "feat: add duplicate_workspace to workspace_manager"
```

---

## Task 3: API endpoints (workspace_routes + tests)

**Files:**
- Modify: `backend/api/workspace_routes.py`
- Modify: `backend/tests/test_workspace_archive_duplicate.py`

- [ ] **Step 1: Write failing API tests**

Append to `backend/tests/test_workspace_archive_duplicate.py`:

```python
# ── API route tests ────────────────────────────────────────────────────────────

import json as _json
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def api_env(tmp_path, monkeypatch):
    import agent.workspace_manager as wm_module
    import api.workspace_routes as wr

    registry_path = tmp_path / "registry.json"
    monkeypatch.setattr(wm_module, "REGISTRY_PATH", str(registry_path))
    monkeypatch.setattr(wm_module, "WORKSPACES_BASE", str(tmp_path))
    monkeypatch.setattr(wm_module, "_active_workspace_id", "ws-a")
    monkeypatch.setattr(wm_module, "_active_dirs", {
        "wiki_dir":      str(tmp_path / "ws-a" / "wiki"),
        "sources_dir":   str(tmp_path / "ws-a" / "sources"),
        "archive_dir":   str(tmp_path / "ws-a" / "archive"),
        "snapshots_dir": str(tmp_path / "ws-a" / "snapshots"),
        "schema_dir":    str(tmp_path / "ws-a" / "schema"),
    })
    # Stub set_wiki_manager so duplicate doesn't try to init WikiManager
    monkeypatch.setattr(wr, "set_wiki_manager", lambda wm: None)

    for ws_id in ("ws-a", "ws-b"):
        schema = tmp_path / ws_id / "schema"
        wiki = tmp_path / ws_id / "wiki"
        for sub in ("wiki", "sources", "archive", "snapshots", "schema"):
            os.makedirs(tmp_path / ws_id / sub, exist_ok=True)
        (schema / "wiki_config.json").write_text(_json.dumps({"setup_complete": True, "wiki_name": ws_id}))
        (schema / "SCHEMA.md").write_text("# Schema")
        clients = wiki / "clients"
        clients.mkdir(exist_ok=True)
        (clients / "_type.yaml").write_text("name: Clients\n")
        (clients / "page.md").write_text("# Page\n")

    registry = {
        "active_workspace_id": "ws-a",
        "workspaces": [
            {"id": "ws-a", "name": "Workspace A", "created_at": "2026-01-01T00:00:00"},
            {"id": "ws-b", "name": "Workspace B", "created_at": "2026-01-01T00:00:00"},
        ],
    }
    registry_path.write_text(_json.dumps(registry))

    app = FastAPI()
    app.include_router(wr.workspace_router)
    return TestClient(app)


def test_archive_endpoint_returns_archived_workspace(api_env):
    r = api_env.post("/ws-b/archive")
    assert r.status_code == 200
    assert r.json()["archived"] is True


def test_archive_active_workspace_returns_400(api_env):
    r = api_env.post("/ws-a/archive")
    assert r.status_code == 400


def test_archive_nonexistent_returns_404(api_env):
    r = api_env.post("/no-such/archive")
    assert r.status_code == 404


def test_unarchive_endpoint_clears_flag(api_env, tmp_path):
    # Archive ws-b first via the API
    api_env.post("/ws-b/archive")
    r = api_env.post("/ws-b/unarchive")
    assert r.status_code == 200
    assert r.json()["archived"] is False


def test_unarchive_nonexistent_returns_404(api_env):
    r = api_env.post("/no-such/unarchive")
    assert r.status_code == 404


def test_duplicate_full_endpoint(api_env):
    r = api_env.post("/ws-a/duplicate", json={"name": "Copy of A", "mode": "full"})
    assert r.status_code == 200
    data = r.json()
    assert data["setup_required"] is False
    assert "id" in data


def test_duplicate_template_endpoint(api_env):
    r = api_env.post("/ws-a/duplicate", json={"name": "Template Copy", "mode": "template"})
    assert r.status_code == 200
    assert r.json()["setup_required"] is True


def test_duplicate_empty_name_returns_422(api_env):
    r = api_env.post("/ws-a/duplicate", json={"name": "  ", "mode": "full"})
    assert r.status_code == 422


def test_duplicate_invalid_mode_returns_422(api_env):
    r = api_env.post("/ws-a/duplicate", json={"name": "Copy", "mode": "bad"})
    assert r.status_code == 422


def test_duplicate_nonexistent_source_returns_404(api_env):
    r = api_env.post("/no-such/duplicate", json={"name": "Copy", "mode": "full"})
    assert r.status_code == 404
```

- [ ] **Step 2: Run to verify failures**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_workspace_archive_duplicate.py::test_archive_endpoint_returns_archived_workspace -v 2>&1 | head -20
```

Expected: FAIL — endpoint doesn't exist yet

- [ ] **Step 3: Implement the 3 new endpoints**

In `backend/api/workspace_routes.py`, add after the existing `delete_workspace_endpoint`:

```python
class DuplicateWorkspaceRequest(BaseModel):
    name: str
    mode: str  # "full" or "template"


@workspace_router.post("/{workspace_id}/archive")
def archive_workspace_endpoint(workspace_id: str):
    if workspace_id == workspace_manager.get_active_workspace_id():
        raise HTTPException(status_code=400, detail="Cannot archive the active workspace")
    try:
        workspace = workspace_manager.archive_workspace(workspace_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found")
    return workspace


@workspace_router.post("/{workspace_id}/unarchive")
def unarchive_workspace_endpoint(workspace_id: str):
    try:
        workspace = workspace_manager.unarchive_workspace(workspace_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found")
    return workspace


@workspace_router.post("/{workspace_id}/duplicate")
def duplicate_workspace_endpoint(workspace_id: str, payload: DuplicateWorkspaceRequest):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    if payload.mode not in ("full", "template"):
        raise HTTPException(status_code=422, detail="mode must be 'full' or 'template'")
    try:
        result = workspace_manager.duplicate_workspace(workspace_id, name, payload.mode)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not result["setup_required"]:
        from agent.setup_wizard import is_setup_complete
        schema_dir = workspace_manager.get_schema_dir()
        if is_setup_complete(schema_dir):
            from agent.wiki_manager import WikiManager
            from agent.setup_wizard import get_wiki_config
            try:
                wm = WikiManager(
                    sources_dir=workspace_manager.get_sources_dir(),
                    wiki_dir=workspace_manager.get_wiki_dir(),
                    archive_dir=workspace_manager.get_archive_dir(),
                    snapshots_dir=workspace_manager.get_snapshots_dir(),
                    schema_dir=schema_dir,
                )
                set_wiki_manager(wm)
            except Exception:
                set_wiki_manager(None)
        else:
            set_wiki_manager(None)
    else:
        set_wiki_manager(None)

    return result
```

- [ ] **Step 4: Run all tests to verify**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_workspace_archive_duplicate.py -v 2>&1 | tail -25
```

Expected: All tests PASSED

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd Faragopedia-Sales/backend
python -m pytest --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add Faragopedia-Sales/backend/api/workspace_routes.py \
        Faragopedia-Sales/backend/tests/test_workspace_archive_duplicate.py
git commit -m "feat: add archive, unarchive, and duplicate workspace endpoints"
```

---

## Task 4: DuplicateWorkspaceModal component

**Files:**
- Create: `frontend/src/components/DuplicateWorkspaceModal.tsx`

- [ ] **Step 1: Create the modal component**

Create `frontend/src/components/DuplicateWorkspaceModal.tsx`:

```tsx
import React, { useState } from 'react';
import { Copy, X } from 'lucide-react';

interface DuplicateWorkspaceModalProps {
  sourceName: string;
  onClose: () => void;
  onConfirm: (name: string, mode: 'full' | 'template') => Promise<void>;
}

const DuplicateWorkspaceModal: React.FC<DuplicateWorkspaceModalProps> = ({
  sourceName,
  onClose,
  onConfirm,
}) => {
  const [name, setName] = useState(`Copy of ${sourceName}`);
  const [mode, setMode] = useState<'full' | 'template'>('full');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('Name is required.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await onConfirm(name.trim(), mode);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Something went wrong.');
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Copy className="w-5 h-5 text-blue-400" />
            Duplicate Workspace
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="mb-4">
          <label className="block text-sm text-gray-300 mb-1">Name</label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            autoFocus
          />
        </div>

        <div className="mb-5 grid grid-cols-2 gap-3">
          <button
            onClick={() => setMode('full')}
            className={`p-4 rounded-lg border text-left transition-colors ${
              mode === 'full'
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-gray-600 hover:border-gray-500'
            }`}
          >
            <div className="font-medium text-sm mb-1">Full Copy</div>
            <div className="text-xs text-gray-400">Copies all pages, sources, and content.</div>
          </button>
          <button
            onClick={() => setMode('template')}
            className={`p-4 rounded-lg border text-left transition-colors ${
              mode === 'template'
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-gray-600 hover:border-gray-500'
            }`}
          >
            <div className="font-medium text-sm mb-1">Empty Wiki</div>
            <div className="text-xs text-gray-400">Copies schema structure only. Setup wizard to configure.</div>
          </button>
        </div>

        {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-300 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg transition-colors"
          >
            {loading ? 'Duplicating…' : 'Duplicate'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DuplicateWorkspaceModal;
```

- [ ] **Step 2: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/DuplicateWorkspaceModal.tsx
git commit -m "feat: add DuplicateWorkspaceModal component"
```

---

## Task 5: WorkspaceSwitcher overhaul

**Files:**
- Modify: `frontend/src/components/WorkspaceSwitcher.tsx`

The existing component (`WorkspaceSwitcher.tsx`) has a simple dropdown with workspace rows and a "New Workspace" button. This task replaces it entirely.

- [ ] **Step 1: Rewrite WorkspaceSwitcher.tsx**

Replace the entire contents of `frontend/src/components/WorkspaceSwitcher.tsx` with:

```tsx
import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check, Plus, MoreHorizontal, Copy, Archive, RotateCcw, ChevronRight } from 'lucide-react';
import DuplicateWorkspaceModal from './DuplicateWorkspaceModal';

interface Workspace {
  id: string;
  name: string;
  archived?: boolean;
}

interface WorkspaceSwitcherProps {
  workspaces: Workspace[];
  activeWorkspaceId: string;
  onSwitch: (id: string) => void;
  onNewWorkspace: () => void;
  onArchive: (id: string) => void;
  onUnarchive: (id: string) => void;
  onDuplicate: (id: string, name: string, mode: 'full' | 'template') => Promise<void>;
}

const WorkspaceSwitcher: React.FC<WorkspaceSwitcherProps> = ({
  workspaces,
  activeWorkspaceId,
  onSwitch,
  onNewWorkspace,
  onArchive,
  onUnarchive,
  onDuplicate,
}) => {
  const [open, setOpen] = useState(false);
  const [contextMenuId, setContextMenuId] = useState<string | null>(null);
  const [archivedExpanded, setArchivedExpanded] = useState(false);
  const [duplicateSource, setDuplicateSource] = useState<Workspace | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setContextMenuId(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const activeWs = workspaces.find(ws => ws.id === activeWorkspaceId);
  const displayName = activeWs?.name ?? 'Workspace';
  const activeWorkspaces = workspaces.filter(ws => !ws.archived);
  const archivedWorkspaces = workspaces.filter(ws => ws.archived);

  const handleContextMenu = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setContextMenuId(prev => (prev === id ? null : id));
  };

  return (
    <>
      <div ref={ref} className="relative">
        {/* Trigger button */}
        <button
          onClick={() => { setOpen(prev => !prev); setContextMenuId(null); }}
          className="w-full flex items-center gap-3 px-6 py-4 text-left hover:bg-gray-700 transition-colors border-b border-gray-700"
        >
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-sm font-bold shrink-0">
            {displayName.slice(0, 2).toUpperCase()}
          </div>
          <span className="flex-grow font-bold text-xl truncate">{displayName}</span>
          <ChevronDown
            className={`w-4 h-4 text-gray-400 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
          />
        </button>

        {/* Dropdown */}
        {open && (
          <div className="absolute left-0 right-0 bg-gray-700 border border-gray-600 rounded-b-lg shadow-xl z-50 overflow-hidden">

            {/* Active workspaces */}
            {activeWorkspaces.map(ws => (
              <div key={ws.id} className="relative group flex items-center">
                <button
                  onClick={() => { onSwitch(ws.id); setOpen(false); }}
                  className="flex-grow flex items-center justify-between px-4 py-3 text-left text-sm hover:bg-gray-600 transition-colors min-w-0"
                >
                  <span className="truncate">{ws.name}</span>
                  {ws.id === activeWorkspaceId && (
                    <Check className="w-4 h-4 text-blue-400 shrink-0 ml-2" />
                  )}
                </button>

                {/* Context menu trigger */}
                <button
                  onClick={e => handleContextMenu(e, ws.id)}
                  className="px-2 py-3 text-gray-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                  title="More options"
                >
                  <MoreHorizontal className="w-4 h-4" />
                </button>

                {/* Context menu popover */}
                {contextMenuId === ws.id && (
                  <div className="absolute right-0 top-full mt-1 bg-gray-800 border border-gray-600 rounded-lg shadow-xl z-10 w-40 py-1">
                    <button
                      onClick={e => {
                        e.stopPropagation();
                        setDuplicateSource(ws);
                        setContextMenuId(null);
                        setOpen(false);
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-700 transition-colors"
                    >
                      <Copy className="w-4 h-4" />
                      Duplicate
                    </button>
                    {ws.id === activeWorkspaceId ? (
                      <button
                        disabled
                        title="Switch to another workspace first"
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-500 cursor-not-allowed"
                      >
                        <Archive className="w-4 h-4" />
                        Archive
                      </button>
                    ) : (
                      <button
                        onClick={e => {
                          e.stopPropagation();
                          onArchive(ws.id);
                          setContextMenuId(null);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-700 transition-colors"
                      >
                        <Archive className="w-4 h-4" />
                        Archive
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* Archived section */}
            {archivedWorkspaces.length > 0 && (
              <div className="border-t border-gray-600">
                <button
                  onClick={() => setArchivedExpanded(prev => !prev)}
                  className="w-full flex items-center justify-between px-4 py-2 text-xs text-gray-400 hover:bg-gray-600 transition-colors"
                >
                  <span>Archived · {archivedWorkspaces.length}</span>
                  <ChevronRight className={`w-3 h-3 transition-transform ${archivedExpanded ? 'rotate-90' : ''}`} />
                </button>

                {archivedExpanded && archivedWorkspaces.map(ws => (
                  <div key={ws.id} className="relative group flex items-center bg-gray-750">
                    <span className="flex-grow px-4 py-2 text-sm text-gray-400 truncate">{ws.name}</span>
                    <button
                      onClick={e => handleContextMenu(e, ws.id)}
                      className="px-2 py-2 text-gray-500 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                    >
                      <MoreHorizontal className="w-4 h-4" />
                    </button>
                    {contextMenuId === ws.id && (
                      <div className="absolute right-0 top-full mt-1 bg-gray-800 border border-gray-600 rounded-lg shadow-xl z-10 w-40 py-1">
                        <button
                          onClick={e => {
                            e.stopPropagation();
                            onUnarchive(ws.id);
                            setContextMenuId(null);
                          }}
                          className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-700 transition-colors"
                        >
                          <RotateCcw className="w-4 h-4" />
                          Restore
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* New workspace */}
            <div className="border-t border-gray-600">
              <button
                onClick={() => { onNewWorkspace(); setOpen(false); }}
                className="w-full flex items-center gap-2 px-4 py-3 text-sm text-blue-400 hover:bg-gray-600 transition-colors"
              >
                <Plus className="w-4 h-4" />
                New Workspace
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Duplicate modal — rendered outside the dropdown div so it's not clipped */}
      {duplicateSource && (
        <DuplicateWorkspaceModal
          sourceName={duplicateSource.name}
          onClose={() => setDuplicateSource(null)}
          onConfirm={async (name, mode) => {
            await onDuplicate(duplicateSource.id, name, mode);
            setDuplicateSource(null);
          }}
        />
      )}
    </>
  );
};

export default WorkspaceSwitcher;
```

- [ ] **Step 2: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/WorkspaceSwitcher.tsx
git commit -m "feat: overhaul WorkspaceSwitcher with context menus and archived section"
```

---

## Task 6: App.tsx handlers + Sidebar threading

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update Sidebar.tsx**

In `frontend/src/components/Sidebar.tsx`:

1. Update the `Workspace` interface and `SidebarProps` (lines 5–14) to:

```tsx
interface SidebarProps {
  currentView: string;
  onViewChange: (view: string) => void;
  wikiName: string;
  onOpenSettings: () => void;
  workspaces: { id: string; name: string; archived?: boolean }[];
  activeWorkspaceId: string;
  onSwitchWorkspace: (id: string) => void;
  onNewWorkspace: () => void;
  onArchiveWorkspace: (id: string) => void;
  onUnarchiveWorkspace: (id: string) => void;
  onDuplicateWorkspace: (id: string, name: string, mode: 'full' | 'template') => Promise<void>;
}
```

2. Update the function signature (line 17) to destructure the new props:

```tsx
const Sidebar: React.FC<SidebarProps> = ({
  currentView, onViewChange, wikiName, onOpenSettings,
  workspaces, activeWorkspaceId,
  onSwitchWorkspace, onNewWorkspace,
  onArchiveWorkspace, onUnarchiveWorkspace, onDuplicateWorkspace,
}) => {
```

3. Update the `<WorkspaceSwitcher>` usage inside the Sidebar render (find the `<WorkspaceSwitcher` block) to pass the new props:

```tsx
<WorkspaceSwitcher
  workspaces={workspaces}
  activeWorkspaceId={activeWorkspaceId}
  onSwitch={onSwitchWorkspace}
  onNewWorkspace={onNewWorkspace}
  onArchive={onArchiveWorkspace}
  onUnarchive={onUnarchiveWorkspace}
  onDuplicate={onDuplicateWorkspace}
/>
```

- [ ] **Step 2: Update App.tsx**

In `frontend/src/App.tsx`:

1. Update the workspaces state type at line 28 to include `archived`:

```tsx
const [workspaces, setWorkspaces] = useState<{ id: string; name: string; archived?: boolean }[]>([]);
```

2. Add three new handlers after `handleNewWorkspace` (after line ~176):

```tsx
const handleArchiveWorkspace = async (id: string) => {
  await fetch(`${API_BASE}/workspaces/${id}/archive`, { method: 'POST' });
  fetchWorkspaces();
};

const handleUnarchiveWorkspace = async (id: string) => {
  await fetch(`${API_BASE}/workspaces/${id}/unarchive`, { method: 'POST' });
  fetchWorkspaces();
};

const handleDuplicateWorkspace = async (id: string, name: string, mode: 'full' | 'template') => {
  const res = await fetch(`${API_BASE}/workspaces/${id}/duplicate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, mode }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail ?? 'Duplicate failed');
  }
  const data = await res.json();
  setActiveWorkspaceId(data.id);
  setChatHistory([]);
  setCurrentView('Wiki');
  setSourcesMetadata({});
  if (data.setup_required) {
    setReconfigureMode(false);
    setExistingFolders([]);
    setSetupState('required');
  } else {
    setSetupState('ready');
  }
  fetchWorkspaces();
};
```

3. Find the `<Sidebar` usage (around line 357) and add the three new props:

```tsx
<Sidebar
  currentView={currentView}
  onViewChange={setCurrentView}
  wikiName={wikiName}
  onOpenSettings={() => setShowSettings(true)}
  workspaces={workspaces}
  activeWorkspaceId={activeWorkspaceId}
  onSwitchWorkspace={handleSwitchWorkspace}
  onNewWorkspace={handleNewWorkspace}
  onArchiveWorkspace={handleArchiveWorkspace}
  onUnarchiveWorkspace={handleUnarchiveWorkspace}
  onDuplicateWorkspace={handleDuplicateWorkspace}
/>
```

- [ ] **Step 3: Build to verify no TypeScript errors**

```bash
cd Faragopedia-Sales/frontend
npm run build 2>&1 | tail -20
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/Sidebar.tsx \
        Faragopedia-Sales/frontend/src/App.tsx
git commit -m "feat: wire up archive, unarchive, and duplicate workspace handlers"
```

---

## Task 7: Final verification

- [ ] **Step 1: Run full backend test suite**

```bash
cd Faragopedia-Sales/backend
python -m pytest --tb=short 2>&1 | tail -20
```

Expected: All tests pass.

- [ ] **Step 2: Confirm frontend builds cleanly**

```bash
cd Faragopedia-Sales/frontend
npm run build 2>&1 | tail -10
```

Expected: Build succeeds.
