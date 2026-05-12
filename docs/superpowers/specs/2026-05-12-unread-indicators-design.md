# Unread Page Indicators — Design Spec

**Date:** 2026-05-12  
**Status:** Approved

## Overview

When ingest or lint creates or modifies wiki pages, those pages become "unread." The sidebar shows unread pages with bold text and shows parent folders with a numbered count badge — familiar patterns from email inboxes. Opening a page marks it read instantly.

## Problem

As the wiki grows, ingest and lint runs can create or modify many pages at once. There is currently no visual way to identify which pages are new or changed since you last looked.

## Design Decisions

- **Trigger:** A page becomes unread when ingest or lint actually writes to it. Runs that don't touch a page leave its read state unchanged.
- **Mark-read:** Automatically on open (no manual action required).
- **Storage:** Backend sidecar file — keeps UI state out of content frontmatter, matches the existing `sources/.metadata.json` pattern.
- **Default:** Pages absent from the sidecar are treated as read (safe default for existing pages before the feature ships).

---

## Data Storage

**File:** `Faragopedia-Sales/backend/wiki/.page-metadata.json`

```json
{
  "clients/acme-corp.md": {
    "read": false,
    "read_at": null
  },
  "clients/beta-ltd.md": {
    "read": true,
    "read_at": "2026-05-12 10:30:00"
  }
}
```

The file is read and written exclusively through `WikiManager`, protected by the existing `asyncio.Lock()` to prevent race conditions.

---

## Backend Changes

### New `WikiManager` methods

**`_load_page_metadata() -> dict`**  
Reads `.page-metadata.json`, returns empty dict if file doesn't exist.

**`_save_page_metadata(metadata: dict) -> None`**  
Writes the metadata dict back to `.page-metadata.json`.

**`_mark_pages_unread(paths: list[str]) -> None`**  
Sets `read: false, read_at: null` for each path. Called internally at the end of `ingest_source()` and `fix_lint_findings()` with the list of pages they wrote.

**`mark_page_read(path: str) -> None`**  
Sets `read: true, read_at: <utcnow>` for the given path.

**`get_pages_metadata() -> dict`**  
Returns the full metadata dict (for the API endpoint).

### New API endpoints (`main.py`)

**`GET /pages/metadata`**  
Returns the full page metadata dict. Frontend fetches this once on mount.

```json
{
  "clients/acme-corp.md": { "read": false, "read_at": null },
  "clients/beta-ltd.md":  { "read": true,  "read_at": "2026-05-12 10:30:00" }
}
```

**`POST /pages/{path:path}/mark-read`**  
Marks a single page as read. Called fire-and-forget by the frontend when a page is opened. Returns `{ "ok": true }`.

### Hooks into existing methods

- `WikiManager.ingest_source()` — call `_mark_pages_unread(newly_written_paths)` after writing pages
- `WikiManager.fix_lint_findings()` — call `_mark_pages_unread(changed_paths)` after applying fixes (the fix report already contains the list of changed files)

---

## Frontend Changes

### State (`App.tsx`)

```typescript
const [pagesMetadata, setPagesMetadata] = useState<
  Record<string, { read: boolean; read_at: string | null }>
>({});
```

Fetched once on mount from `GET /pages/metadata`. Passed down to `WikiView` as a prop.

### Re-fetch triggers

The frontend already detects:
- **Ingest completion** — via the `sourcesMetadata` polling loop; add a `fetchPagesMetadata()` call when a source transitions to `ingested: true`
- **Lint fix completion** — in the `POST /lint/fix` response handler; add a `fetchPagesMetadata()` call after the fix report is received

### Mark-read on open (`WikiView.tsx`)

Inside the existing `setCurrentPage(path)` handler:

1. Optimistically update `pagesMetadata` in local state: set `read: true` for that path
2. Fire `POST /pages/{path}/mark-read` in the background (no await)

### Sidebar — file items (`WikiView.tsx`)

Filename text classes change based on read state:

| State | Classes |
|-------|---------|
| Unread | `font-semibold text-gray-900 dark:text-white` |
| Read | `font-normal text-gray-600 dark:text-gray-300` (existing) |

### Sidebar — folder headers (`WikiView.tsx`)

Compute unread count per folder from `pagesMetadata`:

```typescript
const unreadCount = pages.filter(
  p => pagesMetadata[p]?.read === false
).length;
```

Render badge when `unreadCount > 0`:

```tsx
{unreadCount > 0 && (
  <span className="ml-auto px-1.5 py-0.5 rounded-full text-xs font-medium bg-blue-500 text-white">
    {unreadCount}
  </span>
)}
```

Badge disappears automatically when count reaches 0.

---

## Files Changed

| File | Change |
|------|--------|
| `Faragopedia-Sales/backend/wiki_manager.py` | Add `_load_page_metadata`, `_save_page_metadata`, `_mark_pages_unread`, `mark_page_read`, `get_pages_metadata`; hook into `ingest_source` and `fix_lint_findings` |
| `Faragopedia-Sales/backend/main.py` | Add `GET /pages/metadata` and `POST /pages/{path}/mark-read` endpoints |
| `Faragopedia-Sales/frontend/src/App.tsx` | Add `pagesMetadata` state, fetch on mount, re-fetch after ingest/lint, pass as prop to WikiView |
| `Faragopedia-Sales/frontend/src/components/WikiView.tsx` | Accept `pagesMetadata` prop, apply bold styling to unread file names, render count badge on folder headers, fire mark-read on page open |

---

## Error Handling

- `mark-read` is fire-and-forget: a network failure silently leaves the page bold until the next page fetch. This is acceptable — the page will eventually be re-fetched.
- If `.page-metadata.json` is missing or malformed on startup, `_load_page_metadata()` returns an empty dict (all pages treated as read). This is the safe default.
