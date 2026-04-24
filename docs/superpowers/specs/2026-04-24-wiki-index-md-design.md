# Wiki Index Markdown Companion — Design Spec

**Date:** 2026-04-24  
**Status:** Approved

---

## Overview

Every time the search index is rebuilt (`search-index.json`), a human-readable companion file `wiki/_meta/index.md` is generated alongside it. This file lists all wiki pages as clickable wikilinks, organized first by entity type and then as a flat alphabetical list. It is displayed in the wiki UI as a read-only page — users can navigate from it but cannot edit it.

---

## Backend

### Generation

`WikiManager._rebuild_search_index()` (in `backend/agent/wiki_manager.py`) is the single point where `search-index.json` is written. Immediately after writing the JSON, a new private method `_rebuild_index_md()` is called with the same in-memory data — no extra file I/O.

`_rebuild_index_md()` produces `wiki/_meta/index.md` with the following structure:

```markdown
---
system: true
generated_at: <ISO timestamp>
---

# Wiki Index

## By Type

### Contacts
- [[contacts/john-smith]] — John Smith `#client` `#active`
- [[contacts/jane-doe]] — Jane Doe `#prospect`

### Clients
- [[clients/acme-corp]] — Acme Corp `#active`

---

## All Pages (A–Z)

- [[clients/acme-corp]] — Acme Corp
- [[contacts/jane-doe]] — Jane Doe
- [[contacts/john-smith]] — John Smith
```

**Generation rules:**
- Entity type sections are sorted alphabetically by type name
- Pages within each section are sorted alphabetically by display title
- The flat A–Z list is sorted alphabetically by display title across all types
- Tags are rendered as inline backtick-wrapped strings (e.g. `` `#tag` ``)
- Pages with no tags omit the tag portion entirely
- The `_meta/` folder is never created as an entity type (no `_type.yaml`)

### Rebuild triggers

`_rebuild_index_md()` is called from `_rebuild_search_index()`, which already fires on:
- Page create / update / delete
- Tag changes
- Source ingestion
- Snapshot restore

No new triggers are needed.

---

## Frontend

### Read-only enforcement

`WikiView.tsx` checks for `frontmatter.system === true` on the loaded page. When true:
- The **Edit** button is hidden
- Tag edit controls (add/remove tag buttons) are hidden
- All other navigation (back/forward, wikilink clicks) works normally

No backend permission changes are needed — the restriction is UI-only, consistent with the app's single-user architecture.

### Sidebar entry

A fixed **"Index"** link is added to the sidebar (above entity type sections), pointing to `_meta/index.md`. This link is always visible regardless of which entity types exist. The `_meta/` folder does not appear in the entity type list.

---

## Data flow

```
Any mutation (create/update/delete/tag/ingest/restore)
  → _rebuild_search_index()
      → writes wiki/search-index.json   (existing)
      → _rebuild_index_md()             (new)
          → writes wiki/_meta/index.md
```

---

## What does not change

- Wikilink navigation — already processes `[[path/name]]` links, zero changes needed
- Search index rebuild triggers — all existing paths already covered
- Backend API endpoints — no new routes required
- Snapshot/archive behavior — `_meta/` folder contents are included in existing snapshot ZIPs automatically

---

## Out of scope

- Server-side read-only enforcement (single-user app, UI restriction is sufficient)
- Exposing `log.md` in the wiki UI (separate concern, not part of this spec)
- Pagination or filtering within the index page (the index is a static generated file)
