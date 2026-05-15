# Wisecrawler — `POST /v1/search` Endpoint (Brief)

**Status:** Ready for implementation
**Date:** 2026-05-15
**For:** Implementers working in the Wisecrawler repo
**Self-contained:** This brief is intentionally portable. It does **not** reference Faragopedia internals. Drop this file into the Wisecrawler repo (e.g. as `docs/specs/2026-05-15-search-endpoint.md` or paste into a GitHub issue) and a fresh contributor should have everything they need.

---

## 1. What and why

Wisecrawler needs a new endpoint that accepts a search query (keywords/phrase) and returns a ranked list of web results (`title`, `url`, `snippet`). The endpoint is the *front* of a longer pipeline used by a consumer app: the consumer takes the URLs the user selects and feeds them back into Wisecrawler's existing `/v1/crawl` and `/v1/crawl/analyze` endpoints.

This brief covers **only** the search endpoint. No changes to crawl or analyze.

## 2. Surface area

### Endpoint

```
POST /v1/search
Content-Type: application/json
Authorization: Bearer $WISECRAWLER_API_KEY    (if Wisecrawler already auths consumers)
```

### Request body

```json
{
  "query": "louis vuitton fall 2026 campaign",
  "count": 10
}
```

| Field | Type | Required | Default | Constraints |
|---|---|---|---|---|
| `query` | string | yes | — | non-empty after `.strip()`; reject empty with 400 |
| `count` | int | no | 10 | 1 ≤ count ≤ 20 (Brave's default page size) |

### Response body — 200

```json
{
  "results": [
    {
      "title": "Louis Vuitton Fall 2026 Campaign…",
      "url": "https://vogue.com/fashion/louis-vuitton-fall-2026",
      "snippet": "The maison's latest campaign, shot by Steven Meisel…"
    }
  ]
}
```

`results` is an ordered list of up to `count` items, in Brave's ranking order. Empty list (`[]`) on no results, **not** 404.

### Response codes

| Code | When | Body |
|---|---|---|
| 200 | Success (including empty results) | `{results: [...]}` |
| 400 | Empty `query` after strip, or `count` out of range | `{detail: "..."}` |
| 429 | Brave returned 429 (rate limit) | `{detail: "Search rate limit reached"}` |
| 502 | Brave returned 5xx, or network failure reaching Brave | `{detail: "Upstream search service failed"}` |
| 503 | `BRAVE_API_KEY` env var not set | `{detail: "BRAVE_API_KEY is not configured"}` |

## 3. Implementation

### New module: `brave_search.py`

```python
import os
import httpx

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def _get_api_key() -> str:
    key = os.getenv("BRAVE_API_KEY", "")
    if not key:
        raise ValueError("BRAVE_API_KEY is not configured")
    return key


async def query(q: str, count: int = 10) -> list[dict]:
    """Query Brave Search and return [{title, url, snippet}, ...]."""
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": _get_api_key(),
    }
    params = {"q": q, "count": count}
    async with httpx.AsyncClient() as client:
        response = await client.get(
            BRAVE_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

    web_results = (data.get("web") or {}).get("results") or []
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("description", ""),
        }
        for r in web_results
    ]
```

Note: Brave's field for the snippet is `description`, not `snippet`. We normalize on output.

### New route (add to existing FastAPI routes)

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import httpx
import brave_search

class SearchRequest(BaseModel):
    query: str
    count: int = Field(default=10, ge=1, le=20)

@router.post("/v1/search")
async def search(payload: SearchRequest):
    q = payload.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="query must not be empty")
    try:
        results = await brave_search.query(q, count=payload.count)
    except ValueError as e:                          # missing API key
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 429:
            raise HTTPException(status_code=429, detail="Search rate limit reached")
        raise HTTPException(status_code=502, detail="Upstream search service failed")
    except httpx.HTTPError:                          # network / timeout
        raise HTTPException(status_code=502, detail="Upstream search service failed")
    return {"results": results}
```

### Env var

Add to `.env.example`, deploy configs, and the README:

```
# Brave Search API key — get one at https://brave.com/search/api/
BRAVE_API_KEY=
```

**Auth provider:** Brave Search API (free tier 2,000 queries/month at time of writing; ~$3/1k beyond that).

## 4. Tests

### Unit — `brave_search.query()`

Use `httpx.MockTransport` or a fixture that monkeypatches `httpx.AsyncClient`.

| Case | Setup | Assert |
|---|---|---|
| Success | Mock returns valid Brave JSON with 3 results | Returns 3 dicts with `{title, url, snippet}` keys, snippet sourced from `description` |
| Empty | Mock returns `{"web": {"results": []}}` | Returns `[]` |
| Missing `web` key | Mock returns `{}` | Returns `[]` (no crash) |
| Brave 429 | Mock returns 429 | Raises `httpx.HTTPStatusError` |
| Brave 500 | Mock returns 500 | Raises `httpx.HTTPStatusError` |
| Missing API key | Unset env var | `_get_api_key()` raises `ValueError` |

### Route — `POST /v1/search`

Use FastAPI `TestClient`. Mock `brave_search.query` for these.

| Case | Setup | Status | Assert |
|---|---|---|---|
| Success | `query` returns 2 results | 200 | Body has `results` of length 2 |
| Empty query | Body `{"query": "  "}` | 400 | Detail mentions "must not be empty" |
| Count out of range | Body `{"query": "x", "count": 50}` | 422 | Pydantic validation error |
| Missing API key | `query` raises `ValueError` | 503 | Detail mentions `BRAVE_API_KEY` |
| Brave 429 | `query` raises `HTTPStatusError(429)` | 429 | Detail mentions "rate limit" |
| Brave 5xx | `query` raises `HTTPStatusError(500)` | 502 | Detail mentions upstream |
| Network failure | `query` raises `httpx.ConnectError` | 502 | Detail mentions upstream |

### Integration acceptance

A curl that demonstrates end-to-end success:

```bash
curl -s -X POST http://localhost:$WISECRAWLER_PORT/v1/search \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $WISECRAWLER_API_KEY" \
  -d '{"query":"louis vuitton fall 2026 campaign","count":5}' \
  | jq '.results[] | {title, url}'
```

Should return up to 5 `{title, url}` pairs from Brave's index.

## 5. Acceptance criteria

- [ ] `BRAVE_API_KEY` documented in `.env.example` and README.
- [ ] `brave_search.py` exists with `query()` function as specified.
- [ ] `POST /v1/search` returns ranked Brave results on success.
- [ ] Missing key → 503 with clear message.
- [ ] Brave 429 → 429 passthrough with clear message.
- [ ] Brave 5xx / network failure → 502 with clear message.
- [ ] Empty results → 200 with empty list (not 404).
- [ ] Unit tests pass (~6 cases for `brave_search.query()`).
- [ ] Route tests pass (~7 cases for `POST /v1/search`).
- [ ] Integration curl above returns real results.

## 6. Open questions for the implementer

- **Where does this route live in the existing route file structure?** Match whatever convention Wisecrawler uses for `/v1/crawl` and `/v1/crawl/analyze`.
- **Does Wisecrawler use a shared `httpx.AsyncClient`** for outbound calls, or a per-call client? Match the existing pattern; the snippet above uses per-call, which is fine for an endpoint hit at human speed.
- **Logging conventions** — log the query length and result count, but **not** the query text (privacy). Log all error paths.

## 7. Out of scope (for this brief)

- Caching, filters (domain/freshness/language), per-user keys, alternative search providers, contact-style enrichment. Future enhancements may revisit these on the Wisecrawler side, but they are not requirements of v1.
