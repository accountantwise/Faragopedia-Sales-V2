# Wiki Markdown Import — Design Spec

**Date:** 2026-04-27  
**Status:** Approved

## Overview

Users can import pre-made `.md` files directly into a wiki folder, bypassing the ingestion pipeline. This supports bringing in externally created reports, contact files, or other structured content where wiki links may already reference the target filenames. Full integration (frontmatter validation, link resolution) can be done later via the lint process.

---

## Entry Point

The wiki sidebar header gets a new import icon button alongside the existing **New Page** and **New Folder** buttons.

- **Disabled by default.** Becomes active only when the user has a folder selected in the sidebar.
- **Tooltip (active):** "Import markdown files into [folder name]"
- **Tooltip (inactive):** "Select a folder first"

**New folder workflow:** user clicks New Folder → creates it → it becomes the active selection → clicks Import.

---

## Modal Behavior

Modal title: **"Import into [folder name]"**

### File selection
- Drag-and-drop zone accepting `.md` files only
- Non-.md files are filtered silently; a note appears below the zone: _"X file(s) skipped — only .md files are accepted"_
- Standard file browser (click to browse) also restricted to `.md`

### File list
Each queued file shows its filename and one of:
- **Ready** (green) — no conflict, clear to import
- **Conflict** (yellow warning) — filename already exists in the target folder, with three inline action buttons:
  - **Overwrite** — replace the existing wiki page
  - **Skip** — exclude this file from the import
  - **Rename…** — opens an inline text input to set a new filename before import

Conflict detection is client-side: the frontend compares queued filenames against the existing page list for the target folder (fetched when the modal opens).

### Import button
Disabled until:
1. At least one file is queued
2. Every conflicted file has a resolution chosen (Overwrite, Skip, or a valid Rename)

A Rename target that itself conflicts shows an inline red hint: _"That name is already taken"_ and keeps the Import button disabled.

### Post-import
After all files land successfully:
1. Backend rebuilds `search-index.json` and `_meta/index.md` (single rebuild, not per-file)
2. Modal closes
3. Sidebar refreshes to show newly imported pages

---

## Backend

### New endpoint

```
POST /wiki/import
Content-Type: multipart/form-data
```

**Fields:**
| Field | Type | Description |
|---|---|---|
| `folder` | string | Target folder slug |
| `files[]` | file[] | One or more `.md` file uploads |
| `conflict_resolutions` | JSON string | Map of `{ "filename.md": "overwrite" \| "skip" \| { "rename": "new-name.md" } }` |

**Validation:**
- Folder must exist → 404 if not
- All files must be `.md` → 400 per non-md file
- Rename targets must not themselves conflict → per-file error if so

**Write behaviour:**
- Files are written directly to `wiki/{folder}/{filename}.md`
- Files marked `skip` are not written
- `_rebuild_search_index()` is called once after all writes complete

**No ingestion pipeline is invoked.** Frontmatter is written as-is.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Non-.md file dropped | Silently filtered; count shown in note below drop zone |
| Folder deleted between modal open and import | 404 from backend → error banner: "Folder no longer exists. Please close and try again." |
| Rename target conflicts | Inline red hint on the rename input; Import button stays disabled |
| Write failure (permissions, disk, etc.) | Backend returns per-file error list; modal stays open; failed files shown with error and retry option |
| Partial success | Successfully imported files listed as "Imported"; failed files remain in list for retry or dismissal |

---

## Out of Scope

- Frontmatter injection or merging — files land exactly as written; lint handles validation later
- Multi-folder import in a single operation
- Sub-folder creation during import (use New Folder first)
- Ingestion of imported files (user can trigger that separately per file if desired)
