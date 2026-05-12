# Unread Page Indicators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show bold filenames and a numbered badge on folder headers in the wiki sidebar whenever ingest or lint creates/modifies pages the user hasn't opened yet.

**Architecture:** A new `.page-metadata.json` sidecar in the wiki directory tracks `read/read_at` per page path, written by `WikiManager` and consumed via two new API endpoints. App.tsx holds the `pagesMetadata` state and polls it every 5 seconds alongside sources metadata. WikiView receives `pagesMetadata` and an `onMarkPageRead` callback as props, applies bold text to unread filenames, renders a count badge on folder headers, and fires the mark-read callback the moment a page is opened.

**Tech Stack:** Python 3 + FastAPI, Pydantic v2, asyncio, React 18 + TypeScript, Tailwind CSS, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-05-12-unread-indicators-design.md`

---

## Task 1: WikiManager — page metadata infrastructure

**Files:**
- Modify: `Faragopedia-Sales/backend/agent/wiki_manager.py` (lines 186–200 for `__init__`, after line 477 for new methods)
- Create: `Faragopedia-Sales/backend/tests/test_page_metadata.py`

- [ ] **Step 1: Write the failing tests**

Create `Faragopedia-Sales/backend/tests/test_page_metadata.py`:

```python
import asyncio
import os
import json
import pytest
from unittest.mock import patch
from agent.wiki_manager import WikiManager


@pytest.fixture(autouse=True)
def mock_env():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "AI_PROVIDER": "openai",
        "AI_MODEL": "gpt-4o-mini"
    }):
        yield


@pytest.fixture
def wm(tmp_path):
    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()
    return WikiManager(sources_dir=str(sources), wiki_dir=str(wiki))


def test_page_metadata_path_set(wm):
    expected = os.path.join(wm.wiki_dir, ".page-metadata.json")
    assert wm.page_metadata_path == expected


def test_load_page_metadata_missing_file(wm):
    assert wm._load_page_metadata() == {}


def test_save_and_load_page_metadata(wm):
    data = {"clients/acme.md": {"read": False, "read_at": None}}
    wm._save_page_metadata(data)
    assert wm._load_page_metadata() == data


def test_get_pages_metadata_empty(wm):
    assert wm.get_pages_metadata() == {}


def test_mark_pages_unread(wm):
    wm._mark_pages_unread(["clients/acme.md", "clients/beta.md"])
    metadata = wm._load_page_metadata()
    assert metadata["clients/acme.md"]["read"] is False
    assert metadata["clients/acme.md"]["read_at"] is None
    assert metadata["clients/beta.md"]["read"] is False


def test_mark_pages_unread_resets_existing_read(wm):
    wm._save_page_metadata({
        "clients/acme.md": {"read": True, "read_at": "2026-05-12 10:00:00"}
    })
    wm._mark_pages_unread(["clients/acme.md"])
    assert wm._load_page_metadata()["clients/acme.md"]["read"] is False
    assert wm._load_page_metadata()["clients/acme.md"]["read_at"] is None


@pytest.mark.asyncio
async def test_mark_page_read(wm):
    wm._mark_pages_unread(["clients/acme.md"])
    await wm.mark_page_read("clients/acme.md")
    metadata = wm._load_page_metadata()
    assert metadata["clients/acme.md"]["read"] is True
    assert metadata["clients/acme.md"]["read_at"] is not None


@pytest.mark.asyncio
async def test_mark_page_read_creates_entry_if_absent(wm):
    await wm.mark_page_read("clients/new.md")
    metadata = wm._load_page_metadata()
    assert metadata["clients/new.md"]["read"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_page_metadata.py -v 2>&1 | head -40
```

Expected: All tests fail with `AttributeError: 'WikiManager' object has no attribute 'page_metadata_path'` (or similar).

- [ ] **Step 3: Add `page_metadata_path` to `WikiManager.__init__`**

In `Faragopedia-Sales/backend/agent/wiki_manager.py`, find the `__init__` block. After line 186 (`self.metadata_path = os.path.join(sources_dir, ".metadata.json")`), add:

```python
        self.page_metadata_path = os.path.join(self.wiki_dir, ".page-metadata.json")
```

- [ ] **Step 4: Add the five new methods to `WikiManager`**

In `Faragopedia-Sales/backend/agent/wiki_manager.py`, after the `get_sources_metadata` method (around line 477), add:

```python
    def _load_page_metadata(self) -> Dict:
        if not os.path.exists(self.page_metadata_path):
            return {}
        try:
            with open(self.page_metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_page_metadata(self, metadata: Dict) -> None:
        with open(self.page_metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def get_pages_metadata(self) -> Dict:
        return self._load_page_metadata()

    def _mark_pages_unread(self, paths: List[str]) -> None:
        """Mark pages as unread. Must be called while holding self._write_lock."""
        metadata = self._load_page_metadata()
        for path in paths:
            metadata[path] = {"read": False, "read_at": None}
        self._save_page_metadata(metadata)

    async def mark_page_read(self, path: str) -> None:
        async with self._write_lock:
            metadata = self._load_page_metadata()
            metadata[path] = {
                "read": True,
                "read_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._save_page_metadata(metadata)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_page_metadata.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 6: Commit**

```bash
git add Faragopedia-Sales/backend/agent/wiki_manager.py Faragopedia-Sales/backend/tests/test_page_metadata.py
git commit -m "feat: add page metadata infrastructure to WikiManager"
```

---

## Task 2: WikiManager — hook `ingest_source`

**Files:**
- Modify: `Faragopedia-Sales/backend/agent/wiki_manager.py` (line 676, inside `async with self._write_lock:`)
- Modify: `Faragopedia-Sales/backend/tests/test_page_metadata.py`

- [ ] **Step 1: Write the failing test**

Append to `Faragopedia-Sales/backend/tests/test_page_metadata.py`:

```python
@pytest.mark.asyncio
async def test_ingest_source_marks_pages_unread(wm, tmp_path):
    """Pages written by ingest_source should be marked unread."""
    # Pre-populate a page as read
    wm._save_page_metadata({
        "clients/acme.md": {"read": True, "read_at": "2026-05-12 10:00:00"}
    })

    # Simulate what ingest writes by calling _mark_pages_unread inside the lock
    # (integration smoke: verify the lock + method interaction)
    async with wm._write_lock:
        wm._mark_pages_unread(["clients/acme.md"])

    metadata = wm._load_page_metadata()
    assert metadata["clients/acme.md"]["read"] is False
```

- [ ] **Step 2: Run test to verify it passes (verifies the lock interaction works)**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_page_metadata.py::test_ingest_source_marks_pages_unread -v
```

Expected: PASS (this confirms the lock+method combination works before we wire it in).

- [ ] **Step 3: Add `_mark_pages_unread` call inside `ingest_source`'s write-lock block**

In `Faragopedia-Sales/backend/agent/wiki_manager.py`, find the `async with self._write_lock:` block inside `ingest_source` (around line 667). Add the call as the last line inside the block, after `self._append_to_log`:

Old:
```python
            self.update_index()
            self.mark_source_ingested(file_name, True)
            self._append_to_log("ingest", result.log_entry)
```

New:
```python
            self.update_index()
            self.mark_source_ingested(file_name, True)
            self._append_to_log("ingest", result.log_entry)
            self._mark_pages_unread([page.path for page in result.pages])
```

- [ ] **Step 4: Run full page metadata test suite**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_page_metadata.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/agent/wiki_manager.py Faragopedia-Sales/backend/tests/test_page_metadata.py
git commit -m "feat: mark pages unread after ingest_source writes them"
```

---

## Task 3: WikiManager — hook `fix_lint_findings`

**Files:**
- Modify: `Faragopedia-Sales/backend/agent/wiki_manager.py` (inside `async with self._write_lock:` in `fix_lint_findings`, around line 929)

- [ ] **Step 1: Write the failing test**

Append to `Faragopedia-Sales/backend/tests/test_page_metadata.py`:

```python
@pytest.mark.asyncio
async def test_fix_lint_marks_pages_unread(wm):
    """Pages written inside fix_lint_findings lock block should be marked unread."""
    wm._save_page_metadata({
        "clients/acme.md": {"read": True, "read_at": "2026-05-12 10:00:00"}
    })

    # Simulate what fix_lint_findings does inside its write-lock block
    async with wm._write_lock:
        files_changed = ["clients/acme.md", "photographers/jane.md"]
        wm._mark_pages_unread(files_changed)

    metadata = wm._load_page_metadata()
    assert metadata["clients/acme.md"]["read"] is False
    assert metadata["photographers/jane.md"]["read"] is False
```

- [ ] **Step 2: Run test to verify it passes**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_page_metadata.py::test_fix_lint_marks_pages_unread -v
```

Expected: PASS.

- [ ] **Step 3: Add `_mark_pages_unread` call inside `fix_lint_findings`'s write-lock block**

In `Faragopedia-Sales/backend/agent/wiki_manager.py`, find the `async with self._write_lock:` block inside `fix_lint_findings` (around line 919). Add the call as the last line inside the block, after `self._append_to_log`:

Old:
```python
            self.update_index()
            self._append_to_log("lint-fix", fix_plan.summary)
```

New:
```python
            self.update_index()
            self._append_to_log("lint-fix", fix_plan.summary)
            self._mark_pages_unread(files_changed)
```

- [ ] **Step 4: Run the full test suite**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_page_metadata.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/agent/wiki_manager.py
git commit -m "feat: mark pages unread after fix_lint_findings writes them"
```

---

## Task 4: API — add `GET /pages/metadata` and `POST /pages/mark-read`

**Files:**
- Modify: `Faragopedia-Sales/backend/api/routes.py` (before line 327, the `GET /pages/{path:path}` endpoint)

**Critical:** `GET /pages/metadata` must appear **before** `GET /pages/{path:path}` in the file. FastAPI matches routes in declaration order; if the catch-all `{path:path}` route appears first, it would match the literal path `"metadata"` and return a 404.

- [ ] **Step 1: Write the failing tests**

Create `Faragopedia-Sales/backend/tests/test_page_metadata_routes.py`:

```python
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_env():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "AI_PROVIDER": "openai",
        "AI_MODEL": "gpt-4o-mini"
    }):
        yield


@pytest.fixture
def client(tmp_path):
    from api.routes import set_wiki_manager
    mock_wm = MagicMock()
    mock_wm.get_pages_metadata.return_value = {
        "clients/acme.md": {"read": False, "read_at": None}
    }
    mock_wm.mark_page_read = AsyncMock(return_value=None)
    set_wiki_manager(mock_wm)

    from main import app
    with TestClient(app) as c:
        yield c, mock_wm

    set_wiki_manager(None)


def test_get_pages_metadata(client):
    c, mock_wm = client
    res = c.get("/api/pages/metadata")
    assert res.status_code == 200
    data = res.json()
    assert "clients/acme.md" in data
    assert data["clients/acme.md"]["read"] is False


def test_post_mark_read(client):
    c, mock_wm = client
    res = c.post("/api/pages/mark-read", json={"path": "clients/acme.md"})
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    mock_wm.mark_page_read.assert_called_once_with("clients/acme.md")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_page_metadata_routes.py -v 2>&1 | head -30
```

Expected: Both tests fail with 404 (routes don't exist yet).

- [ ] **Step 3: Add the `MarkReadRequest` model and two new endpoints to `routes.py`**

In `Faragopedia-Sales/backend/api/routes.py`, find the block just before `@router.get("/pages/{path:path}")` (line 327). Insert before it:

```python
class MarkReadRequest(BaseModel):
    path: str


@router.get("/pages/metadata")
async def get_pages_metadata(wm: WM):
    try:
        return wm.get_pages_metadata()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching pages metadata: {str(e)}")


@router.post("/pages/mark-read")
async def mark_page_read(wm: WM, body: MarkReadRequest):
    try:
        await wm.mark_page_read(body.path)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marking page as read: {str(e)}")


```

Also check the imports at the top of `routes.py` — confirm `BaseModel` is already imported from `pydantic`. If not, add it to the existing pydantic import line.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_page_metadata_routes.py -v
```

Expected: Both tests pass.

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/api/routes.py Faragopedia-Sales/backend/tests/test_page_metadata_routes.py
git commit -m "feat: add GET /pages/metadata and POST /pages/mark-read endpoints"
```

---

## Task 5: App.tsx — `pagesMetadata` state and polling

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/App.tsx`

- [ ] **Step 1: Add `pagesMetadata` state and `handleMarkPageRead` callback**

In `Faragopedia-Sales/frontend/src/App.tsx`, after line 25 (the `prevMetadataRef` line), add:

```typescript
  const [pagesMetadata, setPagesMetadata] = useState<Record<string, { read: boolean; read_at: string | null }>>({});

  const handleMarkPageRead = useCallback(async (path: string) => {
    setPagesMetadata(prev => ({
      ...prev,
      [path]: { read: true, read_at: new Date().toISOString() },
    }));
    fetch(`${API_BASE}/pages/mark-read`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    }).catch(() => {});
  }, []);
```

- [ ] **Step 2: Add pages metadata fetch to the existing polling `useEffect`**

In `Faragopedia-Sales/frontend/src/App.tsx`, find the `fetchMetadata` function inside the polling `useEffect` (lines 89–114). Extend it so pages metadata is fetched on the same 5-second interval.

Replace the `fetchMetadata` function body (keeping the existing sources-metadata logic intact):

```typescript
    const fetchMetadata = async () => {
      try {
        const res = await fetch(`${API_BASE}/sources/metadata`);
        if (!res.ok) return;
        const data: Record<string, { ingested: boolean; ingested_at: string | null; tags: string[] }> = await res.json();

        // Fire toast for any source that just became ingested
        const prev = prevMetadataRef.current;
        Object.entries(data).forEach(([filename, meta]) => {
          if (meta.ingested && prev[filename] && !prev[filename].ingested) {
            addToast(`"${filename}" ingested successfully.`);
          }
        });

        prevMetadataRef.current = data;
        setSourcesMetadata(data);
      } catch (err) {
        console.error('Failed to fetch metadata', err);
      }

      // Also refresh page read/unread state
      try {
        const pagesRes = await fetch(`${API_BASE}/pages/metadata`);
        if (pagesRes.ok) {
          const pagesData: Record<string, { read: boolean; read_at: string | null }> = await pagesRes.json();
          setPagesMetadata(pagesData);
        }
      } catch {
        // non-fatal
      }
    };
```

- [ ] **Step 3: Pass `pagesMetadata` and `handleMarkPageRead` to `WikiView`**

In `Faragopedia-Sales/frontend/src/App.tsx`, find line 260:

```typescript
        return <WikiView key={activeWorkspaceId} />;
```

Replace with:

```typescript
        return <WikiView key={activeWorkspaceId} pagesMetadata={pagesMetadata} onMarkPageRead={handleMarkPageRead} />;
```

- [ ] **Step 4: Confirm TypeScript compiles**

```bash
cd Faragopedia-Sales/frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: Errors about `WikiView` not accepting those props (because we haven't updated WikiView yet). That's expected — proceed to Task 6 before doing a clean compile check.

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/frontend/src/App.tsx
git commit -m "feat: add pagesMetadata state and polling in App.tsx"
```

---

## Task 6: WikiView.tsx — props, bold text, folder badge, mark-read

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/WikiView.tsx`

- [ ] **Step 1: Add the props interface and update the component signature**

In `Faragopedia-Sales/frontend/src/components/WikiView.tsx`, replace line 36:

```typescript
const WikiView: React.FC = () => {
```

With:

```typescript
interface WikiViewProps {
  pagesMetadata: Record<string, { read: boolean; read_at: string | null }>;
  onMarkPageRead: (path: string) => void;
}

const WikiView: React.FC<WikiViewProps> = ({ pagesMetadata, onMarkPageRead }) => {
```

- [ ] **Step 2: Call `onMarkPageRead` in `fetchPageContent`**

In `Faragopedia-Sales/frontend/src/components/WikiView.tsx`, find `fetchPageContent` (line 260). After line 276 (`setSelectedPage(filename);`), add:

```typescript
      onMarkPageRead(filename);
```

- [ ] **Step 3: Apply bold text to unread file names**

Find the `<span>` that renders the filename inside the page button (the span with `break-all line-clamp-2 leading-tight`). It currently looks like:

```tsx
            <span className="break-all line-clamp-2 leading-tight">
              {pagePath.split('/').pop()?.replace('.md', '').replace(/-/g, ' ')}
            </span>
```

Replace with:

```tsx
            <span className={`break-all line-clamp-2 leading-tight${
              pagesMetadata[pagePath]?.read === false && selectedPage !== pagePath
                ? ' font-semibold text-gray-900 dark:text-white'
                : ''
            }`}>
              {pagePath.split('/').pop()?.replace('.md', '').replace(/-/g, ' ')}
            </span>
```

- [ ] **Step 4: Add the unread count badge to folder headers**

Find the folder header rendering loop. Inside the loop body, before the `<div key={section}>` JSX, compute the unread count:

```tsx
          const unreadCount = sectionPages.filter(
            p => pagesMetadata[p]?.read === false
          ).length;
```

Then find the folder header `<span>` that renders the section name:

```tsx
              <span>{typeData.name || section}</span>
```

Replace with:

```tsx
              <span className="flex items-center gap-1.5">
                {typeData.name || section}
                {unreadCount > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full text-xs font-medium bg-blue-500 text-white leading-none">
                    {unreadCount}
                  </span>
                )}
              </span>
```

- [ ] **Step 5: Verify TypeScript compiles cleanly**

```bash
cd Faragopedia-Sales/frontend
npx tsc --noEmit 2>&1
```

Expected: No errors.

- [ ] **Step 6: Start the dev server and do a manual smoke test**

```bash
cd Faragopedia-Sales/frontend
npm run dev
```

Open the app. Verify:
1. On first load, all pages show normal (read) weight — no false positives.
2. Trigger an ingest. After the ingest completes (toast fires), the affected pages appear **bold** in the sidebar and the parent folder shows a **numbered blue badge**.
3. Click one of the bold pages — it should instantly go back to normal weight and the folder badge count should drop by 1.
4. When all pages in a folder are read, the badge disappears entirely.

- [ ] **Step 7: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/WikiView.tsx
git commit -m "feat: show bold unread filenames and folder count badges in sidebar"
```
