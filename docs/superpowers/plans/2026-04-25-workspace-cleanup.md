# Workspace Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three workspace management improvements: a cancel X button in the setup wizard (new-workspace flow only), permanent delete for archived workspaces (with name confirmation), and rename for non-archived workspaces.

**Architecture:** Two new React modal components (`DeleteWorkspaceModal`, `RenameWorkspaceModal`) follow the existing `DuplicateWorkspaceModal` pattern. A new `PATCH /api/workspaces/{id}` backend route calls the already-existing `update_workspace_name()`. `WorkspaceSwitcher` and `Sidebar` get new props threaded from `App.tsx`, and `SetupWizard` renders an X button when `onCancel` is defined.

**Tech Stack:** React + TypeScript (frontend), FastAPI + Python (backend), pytest (backend tests), Tailwind CSS, Lucide icons.

---

## File Map

| Action | File |
|---|---|
| Modify | `Faragopedia-Sales/backend/api/workspace_routes.py` |
| Add tests | `Faragopedia-Sales/backend/tests/test_workspace_rename.py` |
| Create | `Faragopedia-Sales/frontend/src/components/DeleteWorkspaceModal.tsx` |
| Create | `Faragopedia-Sales/frontend/src/components/RenameWorkspaceModal.tsx` |
| Modify | `Faragopedia-Sales/frontend/src/components/SetupWizard.tsx` |
| Modify | `Faragopedia-Sales/frontend/src/components/WorkspaceSwitcher.tsx` |
| Modify | `Faragopedia-Sales/frontend/src/components/Sidebar.tsx` |
| Modify | `Faragopedia-Sales/frontend/src/App.tsx` |

---

## Task 1: Backend — PATCH rename route + tests

**Files:**
- Modify: `Faragopedia-Sales/backend/api/workspace_routes.py`
- Create: `Faragopedia-Sales/backend/tests/test_workspace_rename.py`

Note: `update_workspace_name(workspace_id, name)` already exists in `workspace_manager.py` at line 200. This task only adds the route and tests.

- [ ] **Step 1: Write the failing tests**

Create `Faragopedia-Sales/backend/tests/test_workspace_rename.py`:

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


def test_rename_workspace_updates_name(ws_env):
    wm.update_workspace_name("ws-b", "Renamed B")
    registry = json.loads((ws_env / "registry.json").read_text())
    ws_b = next(ws for ws in registry["workspaces"] if ws["id"] == "ws-b")
    assert ws_b["name"] == "Renamed B"


def test_rename_active_workspace_updates_name(ws_env):
    """Renaming the active workspace is allowed."""
    wm.update_workspace_name("ws-a", "Renamed A")
    registry = json.loads((ws_env / "registry.json").read_text())
    ws_a = next(ws for ws in registry["workspaces"] if ws["id"] == "ws-a")
    assert ws_a["name"] == "Renamed A"


def test_rename_nonexistent_raises(ws_env):
    with pytest.raises(ValueError, match="not found"):
        wm.update_workspace_name("no-such", "Whatever")
```

- [ ] **Step 2: Run tests to verify they fail correctly**

```
cd Faragopedia-Sales/backend
python -m pytest tests/test_workspace_rename.py -v
```

Expected: `test_rename_workspace_updates_name` and `test_rename_active_workspace_updates_name` PASS (the function already exists), `test_rename_nonexistent_raises` PASS. All three should pass — this confirms the existing `update_workspace_name` works and the route just needs to be wired up.

- [ ] **Step 3: Add the PATCH route to workspace_routes.py**

In `Faragopedia-Sales/backend/api/workspace_routes.py`, add after the existing imports block:

```python
class RenameWorkspaceRequest(BaseModel):
    name: str
```

Then add the route after the `unarchive_workspace_endpoint` function (before the `duplicate_workspace_endpoint`):

```python
@workspace_router.patch("/{workspace_id}")
def rename_workspace_endpoint(workspace_id: str, payload: RenameWorkspaceRequest):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    try:
        workspace_manager.update_workspace_name(workspace_id, name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found")
    registry = workspace_manager.list_workspaces()
    entry = next((ws for ws in registry if ws["id"] == workspace_id), None)
    return entry
```

- [ ] **Step 4: Run tests again to verify all pass**

```
cd Faragopedia-Sales/backend
python -m pytest tests/test_workspace_rename.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Run the full backend test suite to check for regressions**

```
cd Faragopedia-Sales/backend
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add Faragopedia-Sales/backend/api/workspace_routes.py Faragopedia-Sales/backend/tests/test_workspace_rename.py
git commit -m "feat: add PATCH /api/workspaces/{id} rename endpoint"
```

---

## Task 2: Frontend — DeleteWorkspaceModal component

**Files:**
- Create: `Faragopedia-Sales/frontend/src/components/DeleteWorkspaceModal.tsx`

- [ ] **Step 1: Create the component**

Create `Faragopedia-Sales/frontend/src/components/DeleteWorkspaceModal.tsx`:

```tsx
import React, { useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface DeleteWorkspaceModalProps {
  workspaceName: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

const DeleteWorkspaceModal: React.FC<DeleteWorkspaceModalProps> = ({
  workspaceName,
  onConfirm,
  onClose,
}) => {
  const [confirmText, setConfirmText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const isMatch = confirmText === workspaceName;

  const handleSubmit = async () => {
    if (!isMatch) return;
    setLoading(true);
    setError('');
    try {
      await onConfirm();
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
            <AlertTriangle className="w-5 h-5 text-red-400" />
            Delete workspace permanently
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-gray-400 mb-5">
          This action <span className="text-white font-medium">cannot be undone</span>. All pages,
          sources, and data in <span className="text-white font-medium">{workspaceName}</span> will
          be deleted forever.
        </p>

        <div className="mb-5">
          <label className="block text-sm text-gray-300 mb-1">
            Type <span className="font-mono text-white">{workspaceName}</span> to confirm
          </label>
          <input
            type="text"
            value={confirmText}
            onChange={e => setConfirmText(e.target.value)}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-red-500"
            autoFocus
            onKeyDown={e => e.key === 'Enter' && isMatch && handleSubmit()}
          />
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
            disabled={!isMatch || loading}
            className="px-4 py-2 text-sm bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
          >
            {loading ? 'Deleting…' : 'Delete forever'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeleteWorkspaceModal;
```

- [ ] **Step 2: Verify TypeScript compiles**

```
cd Faragopedia-Sales/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/DeleteWorkspaceModal.tsx
git commit -m "feat: add DeleteWorkspaceModal component with name confirmation"
```

---

## Task 3: Frontend — RenameWorkspaceModal component

**Files:**
- Create: `Faragopedia-Sales/frontend/src/components/RenameWorkspaceModal.tsx`

- [ ] **Step 1: Create the component**

Create `Faragopedia-Sales/frontend/src/components/RenameWorkspaceModal.tsx`:

```tsx
import React, { useState } from 'react';
import { Pencil, X } from 'lucide-react';

interface RenameWorkspaceModalProps {
  currentName: string;
  onConfirm: (name: string) => Promise<void>;
  onClose: () => void;
}

const RenameWorkspaceModal: React.FC<RenameWorkspaceModalProps> = ({
  currentName,
  onConfirm,
  onClose,
}) => {
  const [name, setName] = useState(currentName);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const isValid = name.trim().length > 0 && name.trim() !== currentName;

  const handleSubmit = async () => {
    if (!isValid) return;
    setLoading(true);
    setError('');
    try {
      await onConfirm(name.trim());
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
            <Pencil className="w-5 h-5 text-blue-400" />
            Rename workspace
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="mb-5">
          <label className="block text-sm text-gray-300 mb-1">Workspace name</label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            autoFocus
            onKeyDown={e => e.key === 'Enter' && isValid && handleSubmit()}
          />
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
            disabled={!isValid || loading}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
          >
            {loading ? 'Renaming…' : 'Rename'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RenameWorkspaceModal;
```

- [ ] **Step 2: Verify TypeScript compiles**

```
cd Faragopedia-Sales/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/RenameWorkspaceModal.tsx
git commit -m "feat: add RenameWorkspaceModal component"
```

---

## Task 4: Frontend — SetupWizard cancel X button

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/SetupWizard.tsx`

The `onCancel?: () => void` prop already exists on `SetupWizardProps` (line 27). The wizard has four step renders (step 0–3), each returns its own JSX block. The X button must appear in all steps when `onCancel` is defined.

- [ ] **Step 1: Add X import to SetupWizard**

In `Faragopedia-Sales/frontend/src/components/SetupWizard.tsx` line 2, `X` is not yet imported from lucide-react. Update the import:

```tsx
import { Loader2, Plus, Trash2, ChevronDown, ChevronRight, X } from 'lucide-react';
```

- [ ] **Step 2: Add X button to step 0**

In the step 0 return block (around line 376–407), the outer wrapper div is:

```tsx
<div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center p-6">
  <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl p-8 w-full max-w-md border border-gray-200 dark:border-gray-800">
    <h1 ...>Get Started</h1>
```

Add a `relative` class and the X button inside the inner div, before `<h1>`:

```tsx
<div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center p-6">
  <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl p-8 w-full max-w-md border border-gray-200 dark:border-gray-800 relative">
    {onCancel && (
      <button
        onClick={onCancel}
        className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
        aria-label="Cancel setup"
      >
        <X className="w-5 h-5" />
      </button>
    )}
    <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Get Started</h1>
```

- [ ] **Step 3: Add X button to step 1**

In the step 1 return block (around line 412–), the inner div currently starts:

```tsx
<div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-800 w-full max-w-lg p-8">
  <h1 className="text-2xl font-bold ...
```

Add `relative` and the X button:

```tsx
<div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-800 w-full max-w-lg p-8 relative">
  {onCancel && (
    <button
      onClick={onCancel}
      className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
      aria-label="Cancel setup"
    >
      <X className="w-5 h-5" />
    </button>
  )}
  <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
```

- [ ] **Step 4: Add X button to steps 2 and 3**

**Step 2** (line ~462) is a full-width layout with no card wrapper. Add `relative` to the outer `min-h-screen` div and position the X button absolutely at the page level:

```tsx
<div className="min-h-screen bg-gray-50 dark:bg-gray-950 p-8 relative">
  {onCancel && (
    <button
      onClick={onCancel}
      className="absolute top-6 right-6 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
      aria-label="Cancel setup"
    >
      <X className="w-5 h-5" />
    </button>
  )}
  <div className="max-w-4xl mx-auto">
    <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-1">Review your schema</h1>
```

**Step 3** (line ~552) uses a card wrapper. Add `relative` to it and insert the X button before `<h1>`:

```tsx
<div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-800 w-full max-w-lg p-8 relative">
  {onCancel && (
    <button
      onClick={onCancel}
      className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
      aria-label="Cancel setup"
    >
      <X className="w-5 h-5" />
    </button>
  )}
  <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Ready to launch</h1>
```

- [ ] **Step 5: Verify TypeScript compiles**

```
cd Faragopedia-Sales/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/SetupWizard.tsx
git commit -m "feat: add cancel X button to SetupWizard when onCancel prop provided"
```

---

## Task 5: Frontend — App.tsx handlers and previousActiveWorkspaceId

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/App.tsx`

- [ ] **Step 1: Add previousActiveWorkspaceId state**

In `App.tsx`, after line 29 (`const [activeWorkspaceId, setActiveWorkspaceId] = useState('');`), add:

```tsx
const [previousActiveWorkspaceId, setPreviousActiveWorkspaceId] = useState('');
```

- [ ] **Step 2: Update handleNewWorkspace to capture previous active id**

Replace the existing `handleNewWorkspace` function (lines 161–177) with:

```tsx
const handleNewWorkspace = async () => {
  setPreviousActiveWorkspaceId(activeWorkspaceId);
  const res = await fetch(`${API_BASE}/workspaces`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: 'New Workspace' }),
  });
  if (!res.ok) return;
  const data = await res.json();
  setActiveWorkspaceId(data.id);
  setChatHistory([]);
  setCurrentView('Wiki');
  setSourcesMetadata({});
  setSetupState('required');
  setReconfigureMode(false);
  setExistingFolders([]);
  fetchWorkspaces();
};
```

- [ ] **Step 3: Update handleSetupComplete to clear previousActiveWorkspaceId**

Replace the existing `handleSetupComplete` function (lines 115–123) with:

```tsx
const handleSetupComplete = async () => {
  const res = await fetch(`${API_BASE}/setup/config`);
  if (res.ok) {
    const data = await res.json();
    setWikiName(data.wiki_name);
  }
  setReconfigureMode(false);
  setPreviousActiveWorkspaceId('');
  setSetupState('ready');
};
```

- [ ] **Step 4: Add handleDeleteWorkspace and handleRenameWorkspace**

After `handleUnarchiveWorkspace` (line 187), add:

```tsx
const handleDeleteWorkspace = async (id: string) => {
  const res = await fetch(`${API_BASE}/workspaces/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? 'Delete failed');
  }
  fetchWorkspaces();
};

const handleRenameWorkspace = async (id: string, name: string) => {
  const res = await fetch(`${API_BASE}/workspaces/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? 'Rename failed');
  }
  fetchWorkspaces();
};
```

- [ ] **Step 5: Update the SetupWizard render to pass onCancel only for new-workspace flow**

Find the `if (setupState === 'required')` block (lines 359–368). Replace it with:

```tsx
if (setupState === 'required') {
  return (
    <SetupWizard
      onComplete={handleSetupComplete}
      onCancel={
        reconfigureMode
          ? handleSetupCancel
          : previousActiveWorkspaceId
            ? () => {
                handleSwitchWorkspace(previousActiveWorkspaceId);
                setPreviousActiveWorkspaceId('');
              }
            : undefined
      }
      reconfigureMode={reconfigureMode}
      existingFolders={existingFolders}
    />
  );
}
```

- [ ] **Step 6: Pass new handlers to Sidebar in the main render**

Find the `<Sidebar` block (around line 387–399). Add the two new props:

```tsx
<Sidebar
  currentView={currentView}
  onViewChange={(v) => { setCurrentView(v); setMobileMenuOpen(false); }}
  wikiName={wikiName}
  onOpenSettings={() => setSettingsOpen(true)}
  workspaces={workspaces}
  activeWorkspaceId={activeWorkspaceId}
  onSwitchWorkspace={handleSwitchWorkspace}
  onNewWorkspace={handleNewWorkspace}
  onArchiveWorkspace={handleArchiveWorkspace}
  onUnarchiveWorkspace={handleUnarchiveWorkspace}
  onDuplicateWorkspace={handleDuplicateWorkspace}
  onDeleteWorkspace={handleDeleteWorkspace}
  onRenameWorkspace={handleRenameWorkspace}
/>
```

- [ ] **Step 7: Verify TypeScript compiles**

```
cd Faragopedia-Sales/frontend
npx tsc --noEmit
```

Expected: TypeScript errors on `Sidebar` (props not yet accepted) — that is expected and will be fixed in the next task. Confirm there are no other unexpected errors.

- [ ] **Step 8: Commit**

```bash
git add Faragopedia-Sales/frontend/src/App.tsx
git commit -m "feat: add previousActiveWorkspaceId state, delete and rename handlers in App"
```

---

## Task 6: Frontend — Sidebar and WorkspaceSwitcher prop threading + context menus

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/Sidebar.tsx`
- Modify: `Faragopedia-Sales/frontend/src/components/WorkspaceSwitcher.tsx`

- [ ] **Step 1: Update Sidebar to accept and forward the two new props**

Replace the entire contents of `Faragopedia-Sales/frontend/src/components/Sidebar.tsx` with:

```tsx
import React from 'react';
import { Book, MessageSquare, Layers, Archive, Activity, Settings } from 'lucide-react';
import WorkspaceSwitcher from './WorkspaceSwitcher';

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
  onDeleteWorkspace: (id: string) => Promise<void>;
  onRenameWorkspace: (id: string, name: string) => Promise<void>;
}

const Sidebar: React.FC<SidebarProps> = ({
  currentView, onViewChange, wikiName, onOpenSettings,
  workspaces, activeWorkspaceId,
  onSwitchWorkspace, onNewWorkspace,
  onArchiveWorkspace, onUnarchiveWorkspace, onDuplicateWorkspace,
  onDeleteWorkspace, onRenameWorkspace,
}) => {
  const menuItems = [
    { name: 'Wiki', icon: <Book className="w-5 h-5" /> },
    { name: 'Sources', icon: <Layers className="w-5 h-5" /> },
    { name: 'Chat', icon: <MessageSquare className="w-5 h-5" /> },
    { name: 'Archive', icon: <Archive className="w-5 h-5" /> },
    { name: 'Lint', icon: <Activity className="w-5 h-5" /> },
  ];

  return (
    <div className="flex flex-col h-screen w-64 bg-gray-800 text-white shadow-xl">
      <WorkspaceSwitcher
        workspaces={workspaces}
        activeWorkspaceId={activeWorkspaceId}
        onSwitch={onSwitchWorkspace}
        onNewWorkspace={onNewWorkspace}
        onArchive={onArchiveWorkspace}
        onUnarchive={onUnarchiveWorkspace}
        onDuplicate={onDuplicateWorkspace}
        onDelete={onDeleteWorkspace}
        onRename={onRenameWorkspace}
      />

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

- [ ] **Step 2: Update WorkspaceSwitcher interface and imports**

In `Faragopedia-Sales/frontend/src/components/WorkspaceSwitcher.tsx`:

Update the import line to add `Pencil` and `Trash2`:

```tsx
import { ChevronDown, Check, Plus, MoreHorizontal, Copy, Archive, RotateCcw, ChevronRight, Pencil, Trash2 } from 'lucide-react';
```

Add import for the two new modals after the existing `DuplicateWorkspaceModal` import:

```tsx
import DeleteWorkspaceModal from './DeleteWorkspaceModal';
import RenameWorkspaceModal from './RenameWorkspaceModal';
```

Update `WorkspaceSwitcherProps` to add the two new props:

```tsx
interface WorkspaceSwitcherProps {
  workspaces: Workspace[];
  activeWorkspaceId: string;
  onSwitch: (id: string) => void;
  onNewWorkspace: () => void;
  onArchive: (id: string) => void;
  onUnarchive: (id: string) => void;
  onDuplicate: (id: string, name: string, mode: 'full' | 'template') => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onRename: (id: string, name: string) => Promise<void>;
}
```

- [ ] **Step 3: Add modal state and destructure new props**

In the component function signature, destructure the two new props:

```tsx
const WorkspaceSwitcher: React.FC<WorkspaceSwitcherProps> = ({
  workspaces,
  activeWorkspaceId,
  onSwitch,
  onNewWorkspace,
  onArchive,
  onUnarchive,
  onDuplicate,
  onDelete,
  onRename,
}) => {
```

After the existing state declarations (after `const [duplicateSource, setDuplicateSource] = useState<Workspace | null>(null);`), add:

```tsx
const [deleteTarget, setDeleteTarget] = useState<Workspace | null>(null);
const [renameTarget, setRenameTarget] = useState<Workspace | null>(null);
```

- [ ] **Step 4: Add Rename item to non-archived workspace context menu**

In the active-workspace context menu popover (the `<div>` starting around line 102 with class `absolute right-0 top-full ...`), add the Rename button **before** the Duplicate button:

```tsx
{contextMenuId === ws.id && (
  <div className="absolute right-0 top-full mt-1 bg-gray-800 border border-gray-600 rounded-lg shadow-xl z-10 w-44 py-1">
    <button
      onClick={e => {
        e.stopPropagation();
        setRenameTarget(ws);
        setContextMenuId(null);
        setOpen(false);
      }}
      className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-700 transition-colors"
    >
      <Pencil className="w-4 h-4" />
      Rename
    </button>
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
```

- [ ] **Step 5: Add Delete permanently item to archived workspace context menu**

In the archived-workspace context menu popover (around line 163), add a Delete permanently button after the Restore button:

```tsx
{contextMenuId === ws.id && (
  <div className="absolute right-0 top-full mt-1 bg-gray-800 border border-gray-600 rounded-lg shadow-xl z-10 w-44 py-1">
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
    <div className="border-t border-gray-700 my-1" />
    <button
      onClick={e => {
        e.stopPropagation();
        setDeleteTarget(ws);
        setContextMenuId(null);
        setOpen(false);
      }}
      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-gray-700 hover:text-red-300 transition-colors"
    >
      <Trash2 className="w-4 h-4" />
      Delete permanently
    </button>
  </div>
)}
```

- [ ] **Step 6: Render the two new modals outside the dropdown**

After the existing `{duplicateSource && (<DuplicateWorkspaceModal .../>)}` block, add:

```tsx
{renameTarget && (
  <RenameWorkspaceModal
    currentName={renameTarget.name}
    onClose={() => setRenameTarget(null)}
    onConfirm={async (name) => {
      await onRename(renameTarget.id, name);
      setRenameTarget(null);
    }}
  />
)}

{deleteTarget && (
  <DeleteWorkspaceModal
    workspaceName={deleteTarget.name}
    onClose={() => setDeleteTarget(null)}
    onConfirm={async () => {
      await onDelete(deleteTarget.id);
      setDeleteTarget(null);
    }}
  />
)}
```

- [ ] **Step 7: Verify TypeScript compiles with no errors**

```
cd Faragopedia-Sales/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 8: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/Sidebar.tsx Faragopedia-Sales/frontend/src/components/WorkspaceSwitcher.tsx
git commit -m "feat: add rename and delete-permanently to workspace context menus"
```

---

## Task 7: Verification

- [ ] **Step 1: Run the full backend test suite**

```
cd Faragopedia-Sales/backend
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 2: Run the frontend build**

```
cd Faragopedia-Sales/frontend
npm run build
```

Expected: Build succeeds with no TypeScript or Vite errors.

- [ ] **Step 3: Manual smoke test — Cancel in new workspace wizard**

Start the app. In the workspace switcher, click "New Workspace". Verify:
- X button appears in the top-right of every wizard step
- Clicking X returns to the previously active workspace
- The new unconfigured workspace appears in the switcher list (not deleted)

- [ ] **Step 4: Manual smoke test — Rename**

Open the workspace switcher. Hover a non-archived, non-active workspace. Click the context menu (⋯). Click "Rename". Verify:
- RenameWorkspaceModal opens pre-filled with current name
- "Rename" button is disabled when name is unchanged or empty
- Successful rename updates the name in the switcher

- [ ] **Step 5: Manual smoke test — Delete permanently**

Archive a workspace. Expand the Archived section. Hover the workspace, open context menu. Click "Delete permanently". Verify:
- DeleteWorkspaceModal opens with the workspace name
- "Delete forever" button is disabled until exact name is typed (case-sensitive)
- Confirming removes the workspace from the list entirely

- [ ] **Step 6: Final commit if any tweaks were needed**

```bash
git add -p
git commit -m "fix: smoke test corrections for workspace cleanup features"
```
