# Wiki Markdown Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to import pre-made `.md` files directly into a wiki folder from the sidebar, bypassing ingestion.

**Architecture:** A new `POST /wiki/import` backend endpoint writes files directly to the wiki folder and rebuilds the search index. A new `ImportWikiModal` React component handles file selection and inline conflict resolution. `WikiView` gains a `selectedFolder` state (set by clicking a folder header) and an import button that opens the modal scoped to the selected folder.

**Tech Stack:** FastAPI (Python), React + TypeScript, lucide-react icons, pytest + TestClient

---

## File Map

| Action | Path |
|---|---|
| Create | `Faragopedia-Sales/backend/tests/test_wiki_import.py` |
| Modify | `Faragopedia-Sales/backend/agent/wiki_manager.py` (add `import_pages` after `list_pages` ~line 1278) |
| Modify | `Faragopedia-Sales/backend/api/routes.py` (add `Form` to FastAPI import; add `POST /wiki/import` endpoint) |
| Create | `Faragopedia-Sales/frontend/src/components/ImportWikiModal.tsx` |
| Modify | `Faragopedia-Sales/frontend/src/components/WikiView.tsx` (selectedFolder state, folder header click, import button, modal render) |

---

## Task 1: WikiManager.import_pages — tests + implementation

**Files:**
- Create: `Faragopedia-Sales/backend/tests/test_wiki_import.py`
- Modify: `Faragopedia-Sales/backend/agent/wiki_manager.py`

- [ ] **Step 1: Write the failing unit tests**

Create `Faragopedia-Sales/backend/tests/test_wiki_import.py`:

```python
import asyncio
import os
import pytest
from unittest.mock import MagicMock, patch

from agent.wiki_manager import WikiManager


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-4")


@pytest.fixture
def wm(tmp_path, mock_env):
    return WikiManager(
        sources_dir=str(tmp_path / "sources"),
        wiki_dir=str(tmp_path / "wiki"),
        archive_dir=str(tmp_path / "archive"),
        snapshots_dir=str(tmp_path / "snapshots"),
        llm=MagicMock(),
    )


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_import_pages_happy_path(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    files = [("acme.md", b"# Acme\nname: Acme Corp"), ("nike.md", b"# Nike\nname: Nike")]
    result = run(wm.import_pages("clients", files, {}))
    assert "clients/acme.md" in result["imported"]
    assert "clients/nike.md" in result["imported"]
    assert result["skipped"] == []
    assert result["errors"] == {}
    assert os.path.exists(os.path.join(wm.wiki_dir, "clients", "acme.md"))


def test_import_pages_skip_resolution(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    existing = os.path.join(wm.wiki_dir, "clients", "acme.md")
    with open(existing, "w") as f:
        f.write("original")
    files = [("acme.md", b"new content")]
    result = run(wm.import_pages("clients", files, {"acme.md": "skip"}))
    assert "acme.md" in result["skipped"]
    assert result["imported"] == []
    assert open(existing).read() == "original"


def test_import_pages_overwrite_resolution(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    existing = os.path.join(wm.wiki_dir, "clients", "acme.md")
    with open(existing, "w") as f:
        f.write("original")
    files = [("acme.md", b"new content")]
    result = run(wm.import_pages("clients", files, {"acme.md": "overwrite"}))
    assert "clients/acme.md" in result["imported"]
    assert open(existing, "rb").read() == b"new content"


def test_import_pages_rename_resolution(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    existing = os.path.join(wm.wiki_dir, "clients", "acme.md")
    with open(existing, "w") as f:
        f.write("original")
    files = [("acme.md", b"new content")]
    result = run(wm.import_pages("clients", files, {"acme.md": {"rename": "acme-v2.md"}}))
    assert "clients/acme-v2.md" in result["imported"]
    assert open(existing).read() == "original"


def test_import_pages_rename_conflict_error(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    for name in ("acme.md", "acme-v2.md"):
        with open(os.path.join(wm.wiki_dir, "clients", name), "w") as f:
            f.write("existing")
    files = [("acme.md", b"new content")]
    result = run(wm.import_pages("clients", files, {"acme.md": {"rename": "acme-v2.md"}}))
    assert "acme.md" in result["errors"]
    assert result["imported"] == []


def test_import_pages_missing_folder_raises(wm):
    files = [("acme.md", b"content")]
    with pytest.raises(FileNotFoundError):
        run(wm.import_pages("nonexistent", files, {}))


def test_import_pages_rebuilds_search_index(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    files = [("acme.md", b"---\nname: Acme\n---\n# Acme")]
    with patch.object(wm, "_rebuild_search_index") as mock_rebuild:
        run(wm.import_pages("clients", files, {}))
    mock_rebuild.assert_called_once()


def test_import_pages_no_rebuild_when_all_skipped(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    files = [("acme.md", b"content")]
    with patch.object(wm, "_rebuild_search_index") as mock_rebuild:
        run(wm.import_pages("clients", files, {"acme.md": "skip"}))
    mock_rebuild.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "Faragopedia-Sales/backend"
python -m pytest tests/test_wiki_import.py -v
```

Expected: `FAILED` — `AttributeError: 'WikiManager' object has no attribute 'import_pages'`

- [ ] **Step 3: Add import_pages to WikiManager**

In `Faragopedia-Sales/backend/agent/wiki_manager.py`, insert after the `list_pages` method (~line 1278):

```python
    async def import_pages(
        self,
        folder: str,
        files: list[tuple[str, bytes]],
        resolutions: dict[str, str | dict],
    ) -> dict:
        folder_path = os.path.join(self.wiki_dir, folder)
        if not os.path.isdir(folder_path):
            raise FileNotFoundError(f"Folder '{folder}' does not exist")

        imported: list[str] = []
        skipped: list[str] = []
        errors: dict[str, str] = {}

        for filename, content in files:
            resolution = resolutions.get(filename, "overwrite")

            if resolution == "skip":
                skipped.append(filename)
                continue

            if isinstance(resolution, dict) and "rename" in resolution:
                target_name = resolution["rename"]
            else:
                target_name = filename

            target_path = os.path.join(folder_path, target_name)

            if isinstance(resolution, dict) and "rename" in resolution and os.path.exists(target_path):
                errors[filename] = f"Rename target '{target_name}' already exists"
                continue

            try:
                with open(target_path, "wb") as fh:
                    fh.write(content)
                imported.append(f"{folder}/{target_name}")
            except OSError as e:
                errors[filename] = str(e)

        if imported:
            self._rebuild_search_index()

        return {"imported": imported, "skipped": skipped, "errors": errors}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd "Faragopedia-Sales/backend"
python -m pytest tests/test_wiki_import.py -v
```

Expected: All 8 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/tests/test_wiki_import.py Faragopedia-Sales/backend/agent/wiki_manager.py
git commit -m "feat: add WikiManager.import_pages method"
```

---

## Task 2: POST /wiki/import route

**Files:**
- Modify: `Faragopedia-Sales/backend/tests/test_wiki_import.py` (append route tests)
- Modify: `Faragopedia-Sales/backend/api/routes.py`

- [ ] **Step 1: Write failing route tests**

Append to `Faragopedia-Sales/backend/tests/test_wiki_import.py`:

```python
import io
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client(tmp_path, mock_env, monkeypatch):
    from agent import workspace_manager
    monkeypatch.setattr(workspace_manager, "get_wiki_dir", lambda: str(tmp_path / "wiki"))
    monkeypatch.setattr(workspace_manager, "get_sources_dir", lambda: str(tmp_path / "sources"))
    monkeypatch.setattr(workspace_manager, "get_archive_dir", lambda: str(tmp_path / "archive"))
    monkeypatch.setattr(workspace_manager, "get_snapshots_dir", lambda: str(tmp_path / "snapshots"))
    os.makedirs(str(tmp_path / "wiki" / "clients"), exist_ok=True)
    return TestClient(app)


def test_route_import_success(client):
    file_content = b"# Acme\nname: Acme Corp"
    response = client.post(
        "/api/wiki/import",
        data={"folder": "clients", "conflict_resolutions": "{}"},
        files=[("files", ("acme.md", io.BytesIO(file_content), "text/markdown"))],
    )
    assert response.status_code == 200
    data = response.json()
    assert "clients/acme.md" in data["imported"]


def test_route_import_folder_not_found(client):
    response = client.post(
        "/api/wiki/import",
        data={"folder": "nonexistent", "conflict_resolutions": "{}"},
        files=[("files", ("acme.md", io.BytesIO(b"content"), "text/markdown"))],
    )
    assert response.status_code == 404


def test_route_import_non_md_file_rejected(client):
    response = client.post(
        "/api/wiki/import",
        data={"folder": "clients", "conflict_resolutions": "{}"},
        files=[("files", ("report.pdf", io.BytesIO(b"content"), "application/pdf"))],
    )
    assert response.status_code == 400


def test_route_import_invalid_resolutions_json(client):
    response = client.post(
        "/api/wiki/import",
        data={"folder": "clients", "conflict_resolutions": "not-json"},
        files=[("files", ("acme.md", io.BytesIO(b"content"), "text/markdown"))],
    )
    assert response.status_code == 400
```

- [ ] **Step 2: Run route tests to confirm they fail**

```bash
cd "Faragopedia-Sales/backend"
python -m pytest tests/test_wiki_import.py::test_route_import_success tests/test_wiki_import.py::test_route_import_folder_not_found tests/test_wiki_import.py::test_route_import_non_md_file_rejected tests/test_wiki_import.py::test_route_import_invalid_resolutions_json -v
```

Expected: `FAILED` — 404 Not Found on `/api/wiki/import`

- [ ] **Step 3: Add Form to routes.py FastAPI imports**

In `Faragopedia-Sales/backend/api/routes.py`, line 1, change:

```python
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, BackgroundTasks, Depends
```

to:

```python
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, BackgroundTasks, Depends
```

- [ ] **Step 4: Add the route endpoint to routes.py**

Also verify `secure_filename` is imported — search routes.py for `secure_filename`. If missing, add:
```python
from werkzeug.utils import secure_filename
```

Then append the new endpoint at the end of `Faragopedia-Sales/backend/api/routes.py`:

```python
@router.post("/wiki/import")
async def import_wiki_files(
    wm: WM,
    folder: str = Form(...),
    files: list[UploadFile] = File(...),
    conflict_resolutions: str = Form(default="{}"),
):
    folder_path = os.path.join(wm.wiki_dir, folder)
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail=f"Folder '{folder}' not found")

    for f in files:
        if not (f.filename or "").endswith(".md"):
            raise HTTPException(status_code=400, detail=f"File '{f.filename}' is not a .md file")

    try:
        resolutions = json.loads(conflict_resolutions)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid conflict_resolutions JSON")

    file_data: list[tuple[str, bytes]] = []
    for f in files:
        safe_name = secure_filename(f.filename or "unnamed.md")
        if not safe_name:
            raise HTTPException(status_code=400, detail=f"Invalid filename '{f.filename}'")
        content = await f.read()
        file_data.append((safe_name, content))

    try:
        result = await wm.import_pages(folder, file_data, resolutions)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result
```

- [ ] **Step 5: Run all wiki import tests**

```bash
cd "Faragopedia-Sales/backend"
python -m pytest tests/test_wiki_import.py -v
```

Expected: All 12 tests `PASSED`

- [ ] **Step 6: Commit**

```bash
git add Faragopedia-Sales/backend/tests/test_wiki_import.py Faragopedia-Sales/backend/api/routes.py
git commit -m "feat: add POST /wiki/import endpoint"
```

---

## Task 3: ImportWikiModal component

**Files:**
- Create: `Faragopedia-Sales/frontend/src/components/ImportWikiModal.tsx`

- [ ] **Step 1: Create the component**

```tsx
import React, { useState, useRef, useEffect } from 'react'
import { X, Upload, FileText, AlertTriangle, CheckCircle, Loader2 } from 'lucide-react'
import { API_BASE } from '../config'

interface Props {
  folder: string
  onClose: () => void
  onImported: () => void
}

type ConflictResolution = 'overwrite' | 'skip' | { rename: string }

interface QueuedFile {
  file: File
  status: 'ready' | 'conflict' | 'imported' | 'error'
  resolution?: ConflictResolution
  renameValue?: string
  errorMessage?: string
}

export default function ImportWikiModal({ folder, onClose, onImported }: Props) {
  const [queuedFiles, setQueuedFiles] = useState<QueuedFile[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [skippedCount, setSkippedCount] = useState(0)
  const [importing, setImporting] = useState(false)
  const [existingPages, setExistingPages] = useState<Set<string>>(new Set())
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetch(`${API_BASE}/pages`)
      .then(r => r.json())
      .then((data: Record<string, string[]>) => {
        const pages = data[folder] || []
        setExistingPages(new Set(pages.map(p => p.split('/').pop()!)))
      })
      .catch(() => {})
  }, [folder])

  const addFiles = (incoming: FileList | File[]) => {
    const all = Array.from(incoming)
    const mdFiles = all.filter(f => f.name.endsWith('.md'))
    const dropped = all.length - mdFiles.length
    if (dropped > 0) setSkippedCount(prev => prev + dropped)
    setQueuedFiles(prev => {
      const seen = new Set(prev.map(q => q.file.name))
      const fresh: QueuedFile[] = mdFiles
        .filter(f => !seen.has(f.name))
        .map(f => ({
          file: f,
          status: existingPages.has(f.name) ? 'conflict' : 'ready',
        }))
      return [...prev, ...fresh]
    })
  }

  const setResolution = (filename: string, resolution: ConflictResolution) => {
    setQueuedFiles(prev =>
      prev.map(q =>
        q.file.name === filename
          ? { ...q, resolution, renameValue: typeof resolution === 'object' ? (q.renameValue ?? '') : undefined }
          : q
      )
    )
  }

  const setRenameValue = (filename: string, value: string) => {
    setQueuedFiles(prev =>
      prev.map(q =>
        q.file.name === filename
          ? { ...q, renameValue: value, resolution: { rename: value } }
          : q
      )
    )
  }

  const isRenameConflict = (q: QueuedFile): boolean => {
    if (typeof q.resolution !== 'object' || !q.resolution.rename) return false
    const target = q.resolution.rename
    if (!target.endsWith('.md')) return true
    const otherNames = queuedFiles
      .filter(other => other.file.name !== q.file.name)
      .map(other =>
        typeof other.resolution === 'object' && other.resolution.rename
          ? other.resolution.rename
          : other.file.name
      )
    return existingPages.has(target) || otherNames.includes(target)
  }

  const pendingFiles = queuedFiles.filter(q => q.status !== 'imported')

  const canImport =
    pendingFiles.length > 0 &&
    !importing &&
    pendingFiles.every(q => {
      if (q.status === 'conflict' && !q.resolution) return false
      if (typeof q.resolution === 'object') {
        return !!q.resolution.rename?.endsWith('.md') && !isRenameConflict(q)
      }
      return true
    })

  const handleImport = async () => {
    setImporting(true)
    const formData = new FormData()
    formData.append('folder', folder)
    const resolutions: Record<string, ConflictResolution> = {}
    for (const q of pendingFiles) {
      formData.append('files', q.file)
      if (q.resolution) resolutions[q.file.name] = q.resolution
    }
    formData.append('conflict_resolutions', JSON.stringify(resolutions))

    try {
      const res = await fetch(`${API_BASE}/wiki/import`, { method: 'POST', body: formData })
      const data = await res.json()
      setQueuedFiles(prev =>
        prev.map(q => {
          const resolvedName = typeof q.resolution === 'object' && q.resolution.rename
            ? q.resolution.rename
            : q.file.name
          const rel = `${folder}/${resolvedName}`
          if ((data.imported as string[])?.includes(rel)) return { ...q, status: 'imported' }
          if ((data.skipped as string[])?.includes(q.file.name)) return { ...q, status: 'imported' }
          const err = (data.errors as Record<string, string>)?.[q.file.name]
          if (err) return { ...q, status: 'error', errorMessage: err }
          return q
        })
      )
      if (!data.errors || Object.keys(data.errors).length === 0) {
        onImported()
        onClose()
      }
    } catch {
      // network error — leave modal open for retry
    } finally {
      setImporting(false)
    }
  }

  const importCount = pendingFiles.filter(q => q.resolution !== 'skip').length

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
      <div style={{ backgroundColor: 'white', borderRadius: '0.5rem', width: '100%', maxWidth: '28rem', maxHeight: '90vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-gray-800 flex-shrink-0">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Import into "{folder}"</h2>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
          <div
            onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={e => { e.preventDefault(); setIsDragging(false); addFiles(e.dataTransfer.files) }}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${isDragging ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-gray-400'}`}
          >
            <Upload className="w-6 h-6 text-gray-400 mx-auto mb-1" />
            <p className="text-sm text-gray-500 dark:text-gray-400">Drop .md files here or click to browse</p>
            <input ref={fileInputRef} type="file" accept=".md" multiple className="hidden" onChange={e => { if (e.target.files) addFiles(e.target.files) }} />
          </div>

          {skippedCount > 0 && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              {skippedCount} file{skippedCount > 1 ? 's' : ''} skipped — only .md files are accepted
            </p>
          )}

          {queuedFiles.length > 0 && (
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden divide-y divide-gray-100 dark:divide-gray-700">
              {queuedFiles.map(q => (
                <div
                  key={q.file.name}
                  className={`p-2.5 ${q.status === 'conflict' ? 'bg-yellow-50 dark:bg-yellow-900/20' : q.status === 'error' ? 'bg-red-50 dark:bg-red-900/20' : ''}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                      <span className="text-sm text-gray-700 dark:text-gray-300 truncate">{q.file.name}</span>
                    </div>
                    <div className="flex-shrink-0">
                      {q.status === 'ready' && <span className="text-xs text-green-600 dark:text-green-400">Ready</span>}
                      {q.status === 'imported' && <CheckCircle className="w-4 h-4 text-green-500" />}
                      {q.status === 'error' && <span className="text-xs text-red-600 dark:text-red-400">{q.errorMessage}</span>}
                      {q.status === 'conflict' && !q.resolution && (
                        <div className="flex items-center gap-1">
                          <AlertTriangle className="w-3.5 h-3.5 text-yellow-500" />
                          <button onClick={() => setResolution(q.file.name, 'overwrite')} className="text-xs px-1.5 py-0.5 border border-gray-200 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300">Overwrite</button>
                          <button onClick={() => setResolution(q.file.name, 'skip')} className="text-xs px-1.5 py-0.5 border border-gray-200 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300">Skip</button>
                          <button onClick={() => setResolution(q.file.name, { rename: '' })} className="text-xs px-1.5 py-0.5 border border-gray-200 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300">Rename…</button>
                        </div>
                      )}
                      {q.status === 'conflict' && q.resolution === 'overwrite' && <span className="text-xs text-blue-600 dark:text-blue-400">Overwrite</span>}
                      {q.status === 'conflict' && q.resolution === 'skip' && <span className="text-xs text-gray-400">Skip</span>}
                    </div>
                  </div>
                  {q.status === 'conflict' && typeof q.resolution === 'object' && (
                    <div className="mt-1.5 pl-5">
                      <input
                        type="text"
                        value={q.renameValue ?? ''}
                        onChange={e => setRenameValue(q.file.name, e.target.value)}
                        placeholder="new-filename.md"
                        className={`text-xs w-full border rounded px-2 py-1 dark:bg-gray-800 dark:text-gray-200 ${isRenameConflict(q) ? 'border-red-400' : 'border-gray-300 dark:border-gray-600'}`}
                      />
                      {isRenameConflict(q) && (
                        <p className="text-xs text-red-500 dark:text-red-400 mt-0.5">That name is already taken</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ padding: '12px 16px', borderTop: '1px solid #f3f4f6', display: 'flex', justifyContent: 'flex-end', flexShrink: 0 }}>
          <button
            onClick={handleImport}
            disabled={!canImport}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {importing && <Loader2 className="w-4 h-4 animate-spin" />}
            {importCount > 0 ? `Import ${importCount} file${importCount > 1 ? 's' : ''}` : 'Import'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd "Faragopedia-Sales/frontend"
npx tsc --noEmit
```

Expected: No errors involving `ImportWikiModal.tsx`

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/ImportWikiModal.tsx
git commit -m "feat: add ImportWikiModal component"
```

---

## Task 4: WikiView — selectedFolder state + folder header click

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/WikiView.tsx`

- [ ] **Step 1: Add selectedFolder state**

In `WikiView.tsx`, find the block of `useState` declarations (around lines 36-40). Add after the `expandedSections` declaration (line 37):

```tsx
const [selectedFolder, setSelectedFolder] = useState<string | null>(null)
const [showImportModal, setShowImportModal] = useState(false)
```

- [ ] **Step 2: Add import for ImportWikiModal**

Near the top of `WikiView.tsx` where other components are imported, add:

```tsx
import ImportWikiModal from './ImportWikiModal'
```

- [ ] **Step 3: Add Upload to lucide-react imports**

Line 4, change:
```tsx
import { FileText, ChevronRight, Loader2, ArrowLeft, ArrowRight, Edit3, Save, X, Trash2, Download, Plus, FilePlus, MoreVertical, MessageSquare, FolderPlus, Pencil, Search, ListChecks, MoveRight, List } from 'lucide-react'
```
to:
```tsx
import { FileText, ChevronRight, Loader2, ArrowLeft, ArrowRight, Edit3, Save, X, Trash2, Download, Plus, FilePlus, MoreVertical, MessageSquare, FolderPlus, Pencil, Search, ListChecks, MoveRight, List, Upload } from 'lucide-react'
```

- [ ] **Step 4: Make folder headers set selectedFolder on click**

Find the folder group header button (around line 925) that calls `toggleSection(section)`:

```tsx
<button
  onClick={() => toggleSection(section)}
  className="flex-1 text-left px-2 py-2 flex items-center justify-between text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md transition-colors"
>
```

Change the `onClick` and add a selected-state style:

```tsx
<button
  onClick={() => { toggleSection(section); setSelectedFolder(section) }}
  className={`flex-1 text-left px-2 py-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wider rounded-md transition-colors hover:bg-gray-50 dark:hover:bg-gray-800 ${
    selectedFolder === section
      ? 'text-blue-600 dark:text-blue-400'
      : 'text-gray-400 dark:text-gray-500'
  }`}
>
```

- [ ] **Step 5: Render ImportWikiModal when open**

Find where other modals are rendered (near the bottom of the WikiView JSX, look for `showNewFolderDialog` or similar modal renders). Add alongside them:

```tsx
{showImportModal && selectedFolder && (
  <ImportWikiModal
    folder={selectedFolder}
    onClose={() => setShowImportModal(false)}
    onImported={fetchPages}
  />
)}
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd "Faragopedia-Sales/frontend"
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/WikiView.tsx
git commit -m "feat: add selectedFolder state and folder header click to WikiView"
```

---

## Task 5: WikiView — Import button in sidebar header

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/WikiView.tsx`

- [ ] **Step 1: Add import button between FolderPlus and the New Page div**

Find the `FolderPlus` button (lines 742–748):

```tsx
<button
  onClick={() => setShowNewFolderDialog(true)}
  className="p-1.5 bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
  title="New Folder"
>
  <FolderPlus className="w-4 h-4" />
</button>
```

Add the import button immediately after it (before the `<div className="relative">` for New Page):

```tsx
<button
  onClick={() => setShowImportModal(true)}
  disabled={!selectedFolder}
  className="p-1.5 bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
  title={selectedFolder ? `Import markdown files into ${selectedFolder}` : 'Select a folder first'}
>
  <Upload className="w-4 h-4" />
</button>
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd "Faragopedia-Sales/frontend"
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 3: Start dev server and test the feature manually**

```bash
cd "Faragopedia-Sales/frontend"
npm run dev
```

Manual test checklist:
1. Open the wiki sidebar — confirm the import (Upload) button is greyed out with tooltip "Select a folder first"
2. Click a folder header — confirm it highlights blue and the import button becomes active with tooltip "Import markdown files into [folder]"
3. Click the import button — confirm the modal opens titled "Import into [folder]"
4. Drag a `.pdf` file into the drop zone — confirm it is rejected with the skipped count message
5. Drag a `.md` file — confirm it appears in the list as "Ready"
6. Drag a second `.md` file that shares a name with an existing wiki page — confirm it shows as "conflict" with Overwrite / Skip / Rename buttons
7. Click Rename… — confirm the inline input appears; type an existing filename — confirm "That name is already taken" hint; type a unique name ending in `.md` — confirm Import button enables
8. Click Import — confirm files land in the wiki folder and the sidebar refreshes

- [ ] **Step 4: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/WikiView.tsx
git commit -m "feat: add wiki markdown import button to sidebar"
```
