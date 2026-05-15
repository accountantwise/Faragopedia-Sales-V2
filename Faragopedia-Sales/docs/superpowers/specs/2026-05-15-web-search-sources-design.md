# Web Search Sources — Design

**Status:** Draft — pending user review
**Date:** 2026-05-15
**Scope:** Faragopedia-Sales (consumer) + Wisecrawler (provider)
**Companion doc:** [`2026-05-15-wisecrawler-search-endpoint-brief.md`](2026-05-15-wisecrawler-search-endpoint-brief.md) — portable, self-contained brief for the Wisecrawler-side implementation. Drop it into the Wisecrawler repo when ready to build that half.

---

## 1. Goal

Let the end user add sources to Faragopedia by typing a keyword or phrase — without needing a specific URL or file. The flow mimics NotebookLM's web search: query → candidate results → user picks which to ingest → existing crawl pipeline handles the rest.

## 2. Non-goals

- No filters (domain, freshness, language) in v1 — see Section 9 alternatives considered.
- No caching of search results — see Section 9.
- No auto-ingest of top N. The user always picks.
- No new ingest pipeline. The existing `/scrape-urls` → crawl → analyze → save raw → manual Ingest flow is reused verbatim.
- "Find Contacts" (via `pp-contact-goat`) is **not** in scope. Mentioned in Section 10 as future work.

## 3. Architecture

Wisecrawler stays a standalone service. It gains one new endpoint (`POST /v1/search`) that wraps Brave Search. Faragopedia gains a new `🔍 Search` tab in the existing `AddSourcesModal`, a proxy route, and a thin client helper.

```
┌─ Faragopedia ────────────────┐    ┌─ Wisecrawler ─────────────────┐
│ AddSourcesModal              │    │                               │
│   └─ Search tab ─────────────┼──▶ │ POST /v1/search               │
│        ↓ user picks URLs     │    │   → brave_search.query()      │
│   POST /search (proxy)       │    │   ← [{title, url, snippet}]   │
│   POST /scrape-urls (reuse)  │◀───│                               │
│        ↓                     │    │ POST /v1/crawl  (existing)    │
│   existing crawl pipeline    │    │ POST /v1/crawl/analyze        │
└──────────────────────────────┘    └───────────────────────────────┘
```

### Why standalone Wisecrawler

- Wisecrawler keeps reuse value for future apps. Absorbing it into Faragopedia kills that.
- One HTTP hop on localhost/LAN is invisible compared to crawl/analyze latency (tens of seconds).
- Search is firmly Wisecrawler's domain (it's about *finding* and *fetching* web content). Faragopedia stays focused on the wiki schema and UX.

## 4. Component breakdown

### 4.1 Wisecrawler — new code

| File | Purpose | Size |
|---|---|---|
| `brave_search.py` | `async def query(q: str, count: int = 10) -> list[dict]` — wraps `GET https://api.search.brave.com/res/v1/web/search?q=…&count=…`. Extracts `{title, url, snippet}` from `web.results[]`. Uses `httpx.AsyncClient`. Auth header: `X-Subscription-Token: $BRAVE_API_KEY`. | ~30 lines |
| `routes/...` (existing routes module) | New `POST /v1/search` — Pydantic request `{query: str, count: int = 10}`, response `{results: [{title, url, snippet}]}`. 503 if `BRAVE_API_KEY` unset. | ~20 lines |
| `.env.example` / `README` / deploy config | Document new `BRAVE_API_KEY` env var. | trivial |

Full self-contained details in the [Wisecrawler brief](2026-05-15-wisecrawler-search-endpoint-brief.md).

### 4.2 Faragopedia — new code

| File | Change |
|---|---|
| [backend/agent/wisecrawler.py](../../../backend/agent/wisecrawler.py) | Add `async def search(query: str, count: int = 10) -> list[dict]`. POSTs to `{base_url}/v1/search` using existing `_get_base_url()` / `_get_headers()` helpers. Same timeout pattern as `analyze_crawl` (120s). |
| [backend/api/routes.py](../../../backend/api/routes.py) | Add `POST /search` proxy route. Pydantic request `{query: str, count: int = 10}`. Returns `{results: [...]}` untouched. Returns 503 if `WISECRAWLER_BASE_URL` not configured (same gate `/scrape-urls` uses today). Passes through Wisecrawler 4xx/5xx with original status. |
| [frontend/src/components/AddSourcesModal.tsx](../../../frontend/src/components/AddSourcesModal.tsx) | Add 4th tab `'search'`. New local state: `searchQuery: string`, `searching: boolean`, `searchResults: SearchResult[]`, `selectedUrls: Set<string>`. On Search submit: POST `/search`. On "Ingest Selected": POST `/scrape-urls` with selected URLs, call `startCrawl(selectedUrls)`, close modal. |

### 4.3 Reused — no changes

- `OperationToastContext.startCrawl(urls)` — fires the existing crawl toast.
- `POST /scrape-urls` — background-task crawl pipeline, unchanged.
- Sources view, raw source storage, manual Ingest button on each source — unchanged.

## 5. UI specification

The Search tab lives inside the existing `AddSourcesModal` (same modal width, same tab strip pattern as Files / URL / Paste Text).

**Layout (top to bottom):**

1. **Query input row** — full-width text input + Search button (blue, matches existing CTA color). Below it a small hint: "Brave Search · ~10 results · free tier 2,000/month".
2. **Selected count** — small uppercase label above the result list: "N of 10 results selected". Hidden before first search.
3. **Result list** — scrollable region (max-height ~280px). Each result card:
   - Checkbox (left, 3px top margin)
   - Title (blue, 13px, font-medium, clickable in a new tab — `<a target="_blank" rel="noopener">`)
   - URL (green, 11px) — Brave returns clean URLs; show breadcrumb-style domain › path
   - Snippet (gray, 12px, max ~3 lines, no truncation beyond what flexbox provides)
   - Selected cards have `bg-blue-50`
4. **Action button** — full-width "Ingest N Selected Sources". Disabled when `selectedUrls.size === 0`. Same color as the Files tab's Upload button.

**States:**
- Initial: query input empty, no result list visible.
- Searching: input disabled, Search button shows `Loader2` spinner.
- Empty results: result region shows "No results for '<query>'" in muted text.
- Error: red banner at top of modal body (same component the other tabs use today).
- Ingesting: action button shows `Loader2` "Crawl started — closing", brief delay (1.5s like the URL tab), then modal closes.

Reference mockup: `.superpowers/brainstorm/2008-1778838516/content/search-tab-layout.html` (browsing the brainstorm session). The mockup also serves as a visual acceptance reference during implementation.

## 6. Data flow (happy path)

```
User                Frontend              Faragopedia BE        Wisecrawler           Brave
 │                     │                       │                    │                  │
 │─ types query ─────▶ │                       │                    │                  │
 │─ clicks Search ───▶ │                       │                    │                  │
 │                     │── POST /search ─────▶ │                    │                  │
 │                     │                       │── POST /v1/search ▶│                  │
 │                     │                       │                    │── GET /web/search▶
 │                     │                       │                    │◀────── results ──│
 │                     │                       │◀───── results ──── │                  │
 │                     │◀── results ────────── │                    │                  │
 │◀── result cards ─── │                       │                    │                  │
 │─ checks N URLs ───▶ │                       │                    │                  │
 │─ Ingest Selected ─▶ │                       │                    │                  │
 │                     │── POST /scrape-urls ▶ │                    │                  │
 │                     │ (existing path: 202; background crawl + analyze starts)       │
 │                     │── startCrawl(urls)  ─ (toast appears)                         │
 │◀── modal closes ─── │                       │                    │                  │
                       (later — pages appear in Sources view; user clicks Ingest as today)
```

## 7. Error handling

| Case | Where caught | UI shows |
|---|---|---|
| `BRAVE_API_KEY` not set on Wisecrawler | Wisecrawler returns 503 | "Web search isn't configured. Ask the admin to set BRAVE_API_KEY." |
| `WISECRAWLER_BASE_URL` not set on Faragopedia | Faragopedia returns 503 (existing gate) | "Web search service unavailable." |
| Brave returns 429 (rate limit) | Wisecrawler returns 429 | "Search rate limit reached. Try again in a minute." |
| Brave 5xx / network failure | Wisecrawler returns 502 | "Web search failed. Please try again." |
| Empty results | 200 with empty list | "No results for '<query>'." |
| Empty query | Frontend (Search button disabled) | — |
| Wisecrawler unreachable | Faragopedia returns 503 (existing pattern) | "Web search service unavailable." |

## 8. Testing

### Wisecrawler
- Unit: `brave_search.query()` with mocked `httpx` — success, empty results, 429 passthrough, 5xx → raises.
- Route: FastAPI `TestClient` — success, missing key (503), Brave 429 passthrough, malformed Brave response.

### Faragopedia backend
- Route: `POST /search` — success path (mock `wisecrawler.search`), missing `WISECRAWLER_BASE_URL` (503), Wisecrawler 4xx passthrough, Wisecrawler timeout.

### Faragopedia frontend
- Manual smoke test (no React tests in the project today):
  1. Open Add Sources → Search tab.
  2. Type a query that should have results; click Search; verify ~10 result cards appear.
  3. Check 2 boxes; verify the count label updates; click "Ingest 2 Selected Sources".
  4. Verify the crawl toast appears, modal closes after ~1.5s.
  5. Wait 30–60s; verify the 2 raw sources appear in Sources view.
  6. Click Ingest on each; verify wiki pages get created as with any other URL crawl.
- Edge cases to verify manually: empty results, search button disabled with empty query, Wisecrawler offline (503 error toast).

## 9. Alternatives considered & rejected

| Alternative | Why rejected |
|---|---|
| Absorb Wisecrawler into Faragopedia | Kills future-app reuse. One HTTP hop is invisible vs. crawl/analyze latency. Expands Faragopedia's surface unnecessarily. |
| Auto-ingest top N results | Silently writes pages the user never vetted; bad fit for a schema-bound wiki. |
| Add filters (domain / freshness) in v1 | YAGNI. Brave default ranking is good; add filters only if v1 hit rates disappoint. |
| In-memory result cache (5–15 min TTL) | Premature. Brave's 2,000 free queries/month is plenty for a single-user app. Revisit only if quota becomes a problem. |
| SerpAPI / Tavily / DuckDuckGo as backend | Brave: independent index, generous free tier, simple REST, good privacy story. SerpAPI most expensive (~$50/mo for 5k). Tavily LLM-opinionated output (we want raw results so the user can judge). DuckDuckGo is HTML-scraping — brittle. |
| Lightweight: save Brave snippets as sources, skip crawl | Loses 95% of the content. The whole point is full-page ingestion. |
| Separate "Search the Web" modal | Less discoverable than a tab; adds a new top-level action. The 4-tab modal is fine. |
| Per-user Brave key passed from Faragopedia | Multi-tenant friendly but adds key-management UI now. Env var matches existing Wisecrawler key pattern. |

## 10. Future work — explicitly out of scope

### 10.1 Find Contacts (`pp-contact-goat`)

A future feature where the user types a query (person, company, skill) and gets back structured *contacts* — LinkedIn profiles, mutuals via Happenstance, Deepline-enriched contacts. Targets `wiki/contacts/` directly. Sits as a 5th tab `👥 Find Contacts` alongside Search.

**Why deferred:**
- Different result shape (people, not articles) — needs a different result-card UI.
- Heavy auth: LinkedIn browser session, Happenstance cookies, Deepline credits.
- Rate-limited (14 free Happenstance searches/month) — needs UX that conveys scarcity.
- Best implemented after Web Search has proven the modal pattern.

**Likely shape when revisited:**
- Faragopedia shells out to `pp-contact-goat` (CLI), or a thin Wisecrawler endpoint that shells out on its behalf.
- Result cards show name / company / mutual-connection count / source (LinkedIn / Happenstance / Deepline).
- Selected contacts get ingested directly into `wiki/contacts/` with the contact entity template, bypassing the crawl pipeline.

### 10.2 Other natural extensions
- Filters (domain include/exclude, freshness, language) — pull in if v1 hit rates disappoint.
- Cache search results per session — pull in if quota becomes an issue.
- "Search history" pane — show prior queries and quickly re-run.

## 11. Acceptance criteria

- [ ] User can open Add Sources → Search tab and submit a keyword query.
- [ ] Up to ~10 result cards render with title, URL, and snippet.
- [ ] User can multi-select results and click "Ingest N Selected Sources".
- [ ] Selected URLs reach `/scrape-urls`; the existing crawl toast fires; modal closes.
- [ ] Resulting raw sources appear in Sources view within ~60s of selection.
- [ ] `BRAVE_API_KEY` and `WISECRAWLER_BASE_URL` misconfiguration produce clean error messages, not crashes.
- [ ] Wisecrawler-side unit and route tests pass (see brief).
- [ ] Faragopedia-side route test for `POST /search` passes.

## 12. Open questions

None at time of writing. If v1 ships and hit rates disappoint, the next decision point is filters (Section 10.2).
