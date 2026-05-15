# Web Search Sources — Faragopedia Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `🔍 Search` tab to the existing Add Sources modal. The tab accepts a keyword query, calls a new `/search` route that proxies to Wisecrawler's `POST /v1/search` (Brave-backed), shows result cards with checkboxes, and on "Ingest Selected" pushes the chosen URLs through the **existing** `/scrape-urls` crawl pipeline.

**Architecture:** Faragopedia is the consumer; Wisecrawler is the provider. This plan covers the **Faragopedia side only** — a new client function in `agent/wisecrawler.py`, a new proxy route in `api/routes.py`, and a new tab in `AddSourcesModal.tsx`. No new ingestion code. No new toast component. The Wisecrawler side is implemented separately using the portable brief at `docs/superpowers/specs/2026-05-15-wisecrawler-search-endpoint-brief.md`.

**Tech Stack:** Python/FastAPI, httpx (already in requirements), pytest + pytest-asyncio, React/TypeScript, Tailwind CSS, lucide-react icons.

**Spec:** [`docs/superpowers/specs/2026-05-15-web-search-sources-design.md`](../specs/2026-05-15-web-search-sources-design.md)

---

## Pre-requisites

- Wisecrawler must have `POST /v1/search` deployed (per the Wisecrawler brief) for full end-to-end smoke testing in Task 4. Tasks 1–3 are unit/integration testable without a live Wisecrawler thanks to mocking.
- `WISECRAWLER_BASE_URL` and `WISECRAWLER_API_KEY` already exist in `.env` from the prior Add Sources Modal work — no new env vars on the Faragopedia side.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `Faragopedia-Sales/backend/agent/wisecrawler.py` | Add `async def search(query, count)` client function |
| Modify | `Faragopedia-Sales/backend/tests/test_wisecrawler.py` | Add unit tests for `search()` |
| Modify | `Faragopedia-Sales/backend/api/routes.py` | Add `POST /search` proxy route |
| Modify | `Faragopedia-Sales/backend/tests/test_sources.py` | Add tests for `POST /search` route |
| Modify | `Faragopedia-Sales/frontend/src/components/AddSourcesModal.tsx` | Add `'search'` tab — state, handlers, markup |

---

## Task 1: Backend — `search()` client function

**Files:**
- Modify: `Faragopedia-Sales/backend/agent/wisecrawler.py`
- Modify: `Faragopedia-Sales/backend/tests/test_wisecrawler.py`

- [ ] **Step 1: Write the failing tests**

Append to `Faragopedia-Sales/backend/tests/test_wisecrawler.py`:

```python
@pytest.mark.asyncio
async def test_search_returns_results():
    mock_client = make_mock_client(
        post_response=make_mock_response({
            "results": [
                {"title": "First", "url": "https://a.com", "snippet": "first snippet"},
                {"title": "Second", "url": "https://b.com", "snippet": "second snippet"},
            ]
        })
    )
    with patch.dict(os.environ, {"WISECRAWLER_BASE_URL": "http://test-wc", "WISECRAWLER_API_KEY": "test-key"}):
        with patch("agent.wisecrawler.httpx.AsyncClient", return_value=mock_client):
            from agent.wisecrawler import search
            result = await search("lv fall 2026", count=5)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0] == {"title": "First", "url": "https://a.com", "snippet": "first snippet"}
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs[1]["json"] == {"query": "lv fall 2026", "count": 5}
    assert call_kwargs[0][0].endswith("/v1/search")
    assert "Authorization" in call_kwargs[1]["headers"]


@pytest.mark.asyncio
async def test_search_uses_default_count():
    mock_client = make_mock_client(
        post_response=make_mock_response({"results": []})
    )
    with patch.dict(os.environ, {"WISECRAWLER_BASE_URL": "http://test-wc", "WISECRAWLER_API_KEY": "test-key"}):
        with patch("agent.wisecrawler.httpx.AsyncClient", return_value=mock_client):
            from agent.wisecrawler import search
            await search("anything")
    call_kwargs = mock_client.post.call_args
    assert call_kwargs[1]["json"]["count"] == 10


@pytest.mark.asyncio
async def test_search_raises_when_base_url_missing():
    env = {k: v for k, v in os.environ.items() if k != "WISECRAWLER_BASE_URL"}
    with patch.dict(os.environ, env, clear=True):
        from agent.wisecrawler import search
        with pytest.raises(ValueError, match="WISECRAWLER_BASE_URL"):
            await search("anything")
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `Faragopedia-Sales/`:
```bash
cd backend && python -m pytest tests/test_wisecrawler.py::test_search_returns_results -v
```

Expected: FAIL with `ImportError: cannot import name 'search' from 'agent.wisecrawler'`.

- [ ] **Step 3: Implement `search()` in `wisecrawler.py`**

Append to `Faragopedia-Sales/backend/agent/wisecrawler.py`:

```python
async def search(query: str, count: int = 10) -> list[dict]:
    """POST /v1/search — returns a list of {title, url, snippet} dicts."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{_get_base_url()}/v1/search",
            json={"query": query, "count": count},
            headers=_get_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["results"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_wisecrawler.py -v
```

Expected: all `test_search_*` cases PASS, plus the existing `test_start_crawl_*`, `test_poll_until_done_*`, `test_analyze_crawl_*` tests remain green.

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/agent/wisecrawler.py Faragopedia-Sales/backend/tests/test_wisecrawler.py
git commit -m "feat: add search() client function to wisecrawler module"
```

---

## Task 2: Backend — `POST /search` proxy route

**Files:**
- Modify: `Faragopedia-Sales/backend/api/routes.py`
- Modify: `Faragopedia-Sales/backend/tests/test_sources.py`

- [ ] **Step 1: Write the failing tests**

Append to `Faragopedia-Sales/backend/tests/test_sources.py`:

```python
# ── Search endpoint ───────────────────────────────────────────────────────────

def test_search_returns_results():
    fake_results = [
        {"title": "A", "url": "https://a.com", "snippet": "a snip"},
        {"title": "B", "url": "https://b.com", "snippet": "b snip"},
    ]
    with patch.dict(os.environ, {"WISECRAWLER_BASE_URL": "http://test-wc"}):
        with patch("api.routes._wc_search", new_callable=AsyncMock, return_value=fake_results):
            response = client.post("/api/search", json={"query": "lv fall 2026", "count": 5})
    assert response.status_code == 200
    body = response.json()
    assert body == {"results": fake_results}


def test_search_default_count():
    with patch.dict(os.environ, {"WISECRAWLER_BASE_URL": "http://test-wc"}):
        with patch("api.routes._wc_search", new_callable=AsyncMock, return_value=[]) as mock:
            response = client.post("/api/search", json={"query": "x"})
    assert response.status_code == 200
    mock.assert_called_once_with("x", 10)


def test_search_empty_query():
    with patch.dict(os.environ, {"WISECRAWLER_BASE_URL": "http://test-wc"}):
        response = client.post("/api/search", json={"query": "   "})
    assert response.status_code == 422


def test_search_no_wisecrawler_url():
    env = {k: v for k, v in os.environ.items() if k != "WISECRAWLER_BASE_URL"}
    with patch.dict(os.environ, env, clear=True):
        response = client.post("/api/search", json={"query": "anything"})
    assert response.status_code == 503


def test_search_wisecrawler_503_passthrough():
    import httpx as _httpx
    def raise_503(*args, **kwargs):
        request = _httpx.Request("POST", "http://test-wc/v1/search")
        response = _httpx.Response(503, request=request, json={"detail": "BRAVE_API_KEY not configured"})
        raise _httpx.HTTPStatusError("503", request=request, response=response)

    with patch.dict(os.environ, {"WISECRAWLER_BASE_URL": "http://test-wc"}):
        with patch("api.routes._wc_search", new_callable=AsyncMock, side_effect=raise_503):
            response = client.post("/api/search", json={"query": "x"})
    assert response.status_code == 503


def test_search_wisecrawler_429_passthrough():
    import httpx as _httpx
    def raise_429(*args, **kwargs):
        request = _httpx.Request("POST", "http://test-wc/v1/search")
        response = _httpx.Response(429, request=request, json={"detail": "Search rate limit reached"})
        raise _httpx.HTTPStatusError("429", request=request, response=response)

    with patch.dict(os.environ, {"WISECRAWLER_BASE_URL": "http://test-wc"}):
        with patch("api.routes._wc_search", new_callable=AsyncMock, side_effect=raise_429):
            response = client.post("/api/search", json={"query": "x"})
    assert response.status_code == 429
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_sources.py::test_search_returns_results -v
```

Expected: FAIL with 404 (route not registered) or AttributeError on `_wc_search`.

- [ ] **Step 3: Implement `POST /search` route in `routes.py`**

Insert immediately after the existing `scrape_urls` route (around line 803), in `Faragopedia-Sales/backend/api/routes.py`:

```python
# ── Search via WiseCrawler (Brave-backed) ─────────────────────────────────────

async def _wc_search(query: str, count: int) -> list[dict]:
    """Indirection seam so tests can patch this symbol on api.routes."""
    from agent.wisecrawler import search as _search
    return await _search(query, count)


@router.post("/search")
async def search_web(payload: dict):
    import httpx as _httpx

    base_url = os.getenv("WISECRAWLER_BASE_URL", "")
    if not base_url:
        raise HTTPException(status_code=503, detail="WISECRAWLER_BASE_URL is not configured")

    query = (payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=422, detail="query is required")

    count = payload.get("count", 10)
    if not isinstance(count, int) or count < 1 or count > 20:
        raise HTTPException(status_code=422, detail="count must be an integer between 1 and 20")

    try:
        results = await _wc_search(query, count)
    except _httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 429:
            raise HTTPException(status_code=429, detail="Search rate limit reached. Try again in a minute.")
        if status == 503:
            raise HTTPException(status_code=503, detail="Web search isn't configured on the crawler service.")
        if status >= 500:
            raise HTTPException(status_code=502, detail="Web search failed. Please try again.")
        raise HTTPException(status_code=status, detail="Web search request rejected.")
    except _httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Web search service unavailable.")

    return {"results": results}
```

The `_wc_search` indirection exists so the tests can patch `api.routes._wc_search` cleanly (mirrors how the existing `_crawl_and_save` is patched).

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_sources.py -v -k search
```

Expected: all six `test_search_*` cases PASS. Run the full test_sources.py to verify no regressions:

```bash
cd backend && python -m pytest tests/test_sources.py -v
```

Expected: all tests green.

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/api/routes.py Faragopedia-Sales/backend/tests/test_sources.py
git commit -m "feat: add POST /search proxy route for Brave-backed web search"
```

---

## Task 3: Frontend — Search tab in AddSourcesModal

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/AddSourcesModal.tsx`

This task has no automated tests (the project has no React test setup). It ends with a manual smoke test. The mockup reference is `.superpowers/brainstorm/2008-1778838516/content/search-tab-layout.html`.

- [ ] **Step 1: Add `'search'` to the Tab union and add the icon import**

Replace `import { X, Upload, FileText, Loader2 } from 'lucide-react';` with:

```typescript
import { X, Upload, FileText, Loader2, Search as SearchIcon } from 'lucide-react';
```

Replace `type Tab = 'files' | 'url' | 'paste';` with:

```typescript
type Tab = 'files' | 'url' | 'paste' | 'search';

interface SearchResult {
  title: string;
  url: string;
  snippet: string;
}
```

- [ ] **Step 2: Add Search tab state and handlers**

Insert these state declarations immediately after the Paste tab state block (after `const [saving, setSaving] = useState(false);`):

```typescript
  // Search tab
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchPerformed, setSearchPerformed] = useState(false);
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
  const [ingesting, setIngesting] = useState(false);
```

Insert this handler block immediately after the Paste tab handler (`handlePasteSubmit`), before the `Render` comment:

```typescript
  // ── Search tab handlers ───────────────────────────────────────────────────

  const handleSearchSubmit = async () => {
    const q = searchQuery.trim();
    if (!q) return;
    setSearching(true);
    setError(null);
    setSearchResults([]);
    setSelectedUrls(new Set());
    try {
      const res = await fetch(`${API_BASE}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, count: 10 }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: 'Search failed' }));
        throw new Error(data.detail || 'Search failed');
      }
      const data = await res.json();
      setSearchResults(data.results || []);
      setSearchPerformed(true);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSearching(false);
    }
  };

  const toggleUrlSelection = (url: string) => {
    setSelectedUrls(prev => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  };

  const handleIngestSelected = async () => {
    if (selectedUrls.size === 0) return;
    const urls = Array.from(selectedUrls);
    setIngesting(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/scrape-urls`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to start crawl');
      }
      startCrawl(urls);
      setTimeout(onClose, 1500);
    } catch (err: any) {
      setError(err.message);
      setIngesting(false);
    }
  };
```

- [ ] **Step 3: Wire `'search'` into the tab list and add tab content**

Replace the tab strip line:

```typescript
{(['files', 'url', 'paste'] as Tab[]).map(tab => (
```

with:

```typescript
{(['files', 'url', 'paste', 'search'] as Tab[]).map(tab => (
```

And replace the tab label ternary:

```typescript
{tab === 'files' ? '📁 Files' : tab === 'url' ? '🔗 URL' : '📋 Paste Text'}
```

with:

```typescript
{tab === 'files' ? '📁 Files' : tab === 'url' ? '🔗 URL' : tab === 'paste' ? '📋 Paste Text' : '🔍 Search'}
```

Then insert this Search tab body immediately after the `{activeTab === 'paste' && (...)}` block, before the closing `</div>` of the modal body:

```tsx
          {/* ── Search tab ── */}
          {activeTab === 'search' && (
            <div className="flex flex-col flex-1 min-h-0">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleSearchSubmit(); }}
                  placeholder="Search the web…"
                  disabled={searching}
                  className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                />
                <button
                  onClick={handleSearchSubmit}
                  disabled={!searchQuery.trim() || searching}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
                >
                  {searching
                    ? <Loader2 className="w-4 h-4 animate-spin" />
                    : <><SearchIcon className="w-4 h-4" /> Search</>}
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-1 mb-3">Brave Search · up to 10 results per query.</p>

              {searchPerformed && searchResults.length === 0 && !searching && (
                <p className="text-sm text-gray-500 italic py-4 text-center">No results for "{searchQuery}".</p>
              )}

              {searchResults.length > 0 && (
                <>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-2">
                    {selectedUrls.size} of {searchResults.length} results selected
                  </p>
                  <ul className="border border-gray-200 rounded-lg overflow-y-auto" style={{ maxHeight: '40vh' }}>
                    {searchResults.map(r => {
                      const checked = selectedUrls.has(r.url);
                      return (
                        <li
                          key={r.url}
                          onClick={() => toggleUrlSelection(r.url)}
                          className={`flex gap-2.5 p-3 border-b border-gray-100 last:border-b-0 cursor-pointer transition-colors ${
                            checked ? 'bg-blue-50' : 'hover:bg-gray-50'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleUrlSelection(r.url)}
                            onClick={e => e.stopPropagation()}
                            className="mt-1 accent-blue-600 shrink-0"
                          />
                          <div className="flex-1 min-w-0">
                            <a
                              href={r.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={e => e.stopPropagation()}
                              className="text-sm font-medium text-blue-700 underline hover:text-blue-800 block leading-tight break-words"
                            >
                              {r.title}
                            </a>
                            <div className="text-xs text-emerald-700 mt-0.5 truncate">{r.url}</div>
                            <p className="text-xs text-gray-600 mt-1 leading-snug">{r.snippet}</p>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}

              <button
                onClick={handleIngestSelected}
                disabled={selectedUrls.size === 0 || ingesting}
                className="mt-4 shrink-0 w-full py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
              >
                {ingesting
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> Crawl started — closing</>
                  : `Ingest ${selectedUrls.size > 0 ? selectedUrls.size + ' ' : ''}Selected Source${selectedUrls.size !== 1 ? 's' : ''}`}
              </button>
            </div>
          )}
```

- [ ] **Step 4: Type-check the frontend build**

```bash
cd Faragopedia-Sales/frontend && npm run build
```

Expected: build succeeds with no TypeScript errors. If errors mention missing types for `Search as SearchIcon`, verify the lucide-react import line was changed.

- [ ] **Step 5: Manual smoke test**

Start the dev stack (or whichever method the user has running today — likely `docker compose up` from project root):

```bash
docker compose up
```

Then in a browser:

1. Open Faragopedia (default `http://localhost:5173` or whatever the user's port is).
2. Click "Add Sources" → click the new "🔍 Search" tab.
3. **Empty-query gate:** verify Search button is disabled until you type something.
4. **Backend-only test (Wisecrawler may not be ready):** with `WISECRAWLER_BASE_URL` unset on the backend, type a query and click Search. Verify the error banner shows "Web search service unavailable." (or the 503 detail). Confirm no crash.
5. **Live test (requires Wisecrawler `/v1/search` running):** set `WISECRAWLER_BASE_URL` and `BRAVE_API_KEY`, restart backend. Type a query, click Search; verify result cards render with title (blue, underlined, opens new tab when clicked), URL (green), snippet (gray).
6. Check 2 result boxes. Verify "2 of N results selected" updates. Verify the bottom CTA reads "Ingest 2 Selected Sources" and is enabled.
7. Click the bottom CTA. Verify the crawl toast appears (existing `OperationToastContext` behavior) and the modal closes after ~1.5s.
8. Wait 30–60s, switch to Sources view, verify the 2 new raw sources appear. Click Ingest on one of them; verify the wiki page is created as with any URL crawl.
9. **Empty results:** type a deliberately weird query (e.g. `aksdjfhakjsdf qweqwe nonsense xyz123`). Verify the "No results for '…'" message appears.

- [ ] **Step 6: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/AddSourcesModal.tsx
git commit -m "feat: add Search tab to AddSourcesModal for web-search ingestion"
```

---

## Task 4: Documentation + final verification

**Files:**
- Modify: `Faragopedia-Sales/docs/status.md`

- [ ] **Step 1: Update status.md**

Append a new "Immediate Priorities" line after the most recent completed item, marking this feature done:

```markdown
28. ~~Execute Web Search Sources plan (Tasks 1–3, Faragopedia side)~~ ✅ — see `docs/superpowers/plans/2026-05-15-web-search-sources-faragopedia.md`. Wisecrawler-side brief lives at `docs/superpowers/specs/2026-05-15-wisecrawler-search-endpoint-brief.md` — implement that in the Wisecrawler repo next.
```

(Numbering may differ — match the next available number in the existing list.)

- [ ] **Step 2: Run the full backend test suite**

```bash
cd backend && python -m pytest
```

Expected: all tests green. If a pre-existing test is broken (unrelated to this work), note it but do not fix in this commit.

- [ ] **Step 3: Run the frontend build one more time**

```bash
cd Faragopedia-Sales/frontend && npm run build
```

Expected: clean build.

- [ ] **Step 4: Final commit**

```bash
git add Faragopedia-Sales/docs/status.md
git commit -m "docs: mark web-search sources (Faragopedia side) complete"
```

- [ ] **Step 5: Verify acceptance criteria from the spec**

Open `docs/superpowers/specs/2026-05-15-web-search-sources-design.md` and tick each acceptance-criteria checkbox in Section 11. Any unchecked item means the work is not complete.

---

## Out of scope (handled separately)

- **Wisecrawler side** (`POST /v1/search`, `brave_search.py`, `BRAVE_API_KEY`). Self-contained brief: `docs/superpowers/specs/2026-05-15-wisecrawler-search-endpoint-brief.md`. Implement in the Wisecrawler repo after copying the brief there.
- **Find Contacts** (`pp-contact-goat`). Future work — see spec Section 10.

---

## Connection Smoke Test Runbook (deferred — run when Brave key is missing OR present)

This runbook replaces the original Task 3 Step 5 manual smoke test, split into two phases. **Phase 1 can run BEFORE setting up the Brave API key** — it verifies the entire network and auth path between Faragopedia and Wisecrawler using the upstream's BRAVE_API_KEY-missing 503 response as the success signal. **Phase 2 runs after the Brave key is set up** and covers live result rendering through ingestion.

### Prerequisites (both phases)

- Wisecrawler is deployed with the `POST /v1/search` endpoint from the brief (`docs/superpowers/specs/2026-05-15-wisecrawler-search-endpoint-brief.md`).
- Faragopedia has been deployed/restarted from `feature/web-search-sources` so it includes the new `/search` route and Search tab.
- `WISECRAWLER_BASE_URL` and `WISECRAWLER_API_KEY` are set in Faragopedia's environment and point at the running Wisecrawler.

### Phase 1 — Connection test (no Brave key required)

**Assumes:** `BRAVE_API_KEY` is NOT set on Wisecrawler. Wisecrawler will return 503 for any search call. We use that 503 as proof the wiring works.

**1a — Curl test (verifies backend ↔ Wisecrawler):**

From any shell that can reach Faragopedia's backend:

```bash
curl -s -X POST <faragopedia-host>/api/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"hello","count":3}' -w "\nHTTP %{http_code}\n"
```

| Outcome | Meaning |
|---|---|
| `HTTP 503` with detail mentioning "Web search isn't configured on the crawler service" or BRAVE_API_KEY | ✅ Full path works. Faragopedia reached Wisecrawler, Wisecrawler answered, error mapped correctly. Phase 1 passes. |
| `HTTP 503` with detail "WISECRAWLER_BASE_URL is not configured" | ❌ Faragopedia is missing the env var. Fix the env, redeploy/restart, re-run. |
| `HTTP 503` with detail "Web search service unavailable" | ❌ Faragopedia couldn't reach Wisecrawler (network / DNS / tunnel down). Check that the URL in `WISECRAWLER_BASE_URL` is correct and that the tunnel/host is up. |
| Connection refused / timeout | ❌ Faragopedia backend not running (or wrong host/port). |
| `HTTP 401/403` | ❌ `WISECRAWLER_API_KEY` is wrong or Wisecrawler is rejecting auth. |
| `HTTP 502` | ❌ Wisecrawler returned a 5xx (other than 503). Check Wisecrawler logs. |

**1b — UI test (verifies Search tab renders and shows errors):**

1. Open Faragopedia in a browser → click "Add Sources" → click 🔍 Search tab.
2. **Empty-query gate:** With the query input empty, verify the Search button is disabled.
3. Type any query (e.g. `test`) and click Search.
4. Expected: red error banner inside the modal with the same Wisecrawler 503 message from the curl test above. No crash; rest of the modal still works (you can switch back to Files/URL/Paste tabs).
5. **Test result rendering with mocked data (optional):** If you want to see what the result cards look like before getting a Brave key, the mockup at `.superpowers/brainstorm/2008-1778838516/content/search-tab-layout.html` shows the layout. (Or open that file directly in a browser.)

If 1a and 1b both pass, the Faragopedia side is **fully verified except for the live Brave path**. You can ship the branch with confidence; Phase 2 is just turning the key on.

### Phase 2 — Live smoke test (Brave key required)

**Assumes:** `BRAVE_API_KEY` is now set on Wisecrawler and Wisecrawler has been restarted to pick up the env var. (Verify with: `curl -X POST <wisecrawler>/v1/search -d '{"query":"test"}' -H 'Content-Type: application/json' -H "Authorization: Bearer $WISECRAWLER_API_KEY"` — should return a `{results: [...]}` with real Brave hits.)

1. **Live results render:** Open Faragopedia → Add Sources → Search. Type a real query (e.g. `louis vuitton fall 2026 campaign`), click Search. Verify ~10 result cards appear with blue title (clickable to a new tab), green URL, gray snippet.
2. **Selection updates count:** Check 2 boxes; verify the "2 of N results selected" label updates and the bottom button reads "Ingest 2 Selected Sources".
3. **Ingest pipeline fires:** Click "Ingest 2 Selected Sources". Verify the existing crawl toast appears and the modal closes after ~1.5s.
4. **Sources land:** Wait 30–60s; switch to Sources view; verify the 2 new raw sources have appeared. Click Ingest on one; verify the wiki page is created as with any URL-tab crawl.
5. **Empty-results state:** Open Search again; type a deliberately weird query (e.g. `aksdjfhakjsdf qweqwe nonsense xyz123`). Verify a "No results for '…'" message appears.
6. **Rate limit handling (optional):** If you spam-click Search enough times to trigger Brave's rate limit, verify the UI shows "Search rate limit reached. Try again in a minute."

Once Phase 2 passes, tick all acceptance criteria in `docs/superpowers/specs/2026-05-15-web-search-sources-design.md` §11 and the feature is ready to merge.

---

## Self-Review

**Spec coverage:**
- §3 Architecture (Wisecrawler standalone + `/v1/search` + Faragopedia proxy) → Tasks 1 (client) + 2 (proxy). ✓
- §4.2 Faragopedia components → Tasks 1, 2, 3 (one task per file). ✓
- §5 UI specification → Task 3 (tab strip, query row, count label, scrollable result list, action button, error/empty states). ✓
- §6 Data flow → exercised by Task 3 Step 5 manual smoke. ✓
- §7 Error handling matrix → Task 2 tests cover 503 (missing base URL), 429 passthrough, 503 passthrough; Task 3 smoke covers UI banner. ✓
- §8 Testing → unit tests (Task 1), route tests (Task 2), manual smoke (Task 3). ✓
- §11 Acceptance criteria → ticked in Task 4 Step 5. ✓
- §4.1 Wisecrawler components → explicitly out of scope, handled by the portable brief. ✓

**Placeholder scan:** No TBDs, no "implement appropriately", no "similar to Task N" — each task contains its own complete code. ✓

**Type consistency:**
- `search(query: str, count: int = 10) -> list[dict]` defined in Task 1, called the same way in Task 2's `_wc_search` indirection. ✓
- `SearchResult { title, url, snippet }` in frontend matches the dict shape Task 1 returns. ✓
- `selectedUrls: Set<string>`, `searchResults: SearchResult[]`, `searchPerformed: boolean` — used consistently across handlers and JSX. ✓
- `API_BASE` and `startCrawl` are already imported in the existing modal — no new imports needed beyond `SearchIcon`. ✓
