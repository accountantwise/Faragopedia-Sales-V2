# Workspace Archive & Duplicate — Design Spec

**Date:** 2026-04-25  
**Status:** Approved

## Overview

Add Archive and Duplicate actions to the workspace switcher. Archive soft-hides a workspace (restorable). Duplicate creates a new workspace from an existing one — either as a full content copy or as an empty wiki with the same schema structure.

---

## Backend

### Registry Schema Change

Add an `archived` boolean field to each workspace entry in `registry.json`. Defaults to `false` for all existing and new workspaces.

```json
{
  "id": "my-workspace",
  "name": "My Workspace",
  "created_at": "2026-04-25T10:00:00",
  "archived": false
}
```

### New Endpoints (`workspace_routes.py`)

#### `POST /api/workspaces/{id}/archive`
- Sets `archived: true` in registry entry.
- Returns 400 if the workspace is currently active (user must switch away first).
- Returns updated workspace object.

#### `POST /api/workspaces/{id}/unarchive`
- Sets `archived: false` in registry entry.
- Returns updated workspace object.

#### `POST /api/workspaces/{id}/duplicate`

**Request body:**
```json
{
  "name": "Copy of My Workspace",
  "mode": "full" | "template"
}
```

**Full mode:**
1. Slug the new name (same logic as workspace create, with uniqueness suffix if needed).
2. `shutil.copytree` all 5 workspace directories (`schema/`, `wiki/`, `sources/`, `archive/`, `snapshots/`) into the new workspace directory.
3. Add new registry entry with `archived: false`. `setup_complete` is `true` (inherited from source).
4. Switch active workspace to the new workspace.
5. Return `{"id": ..., "name": ..., "setup_required": false}`.

**Template mode:**
1. Slug the new name.
2. Create the new workspace directory with all 5 empty subdirectories.
3. Copy `schema/` from source into new workspace `schema/`.
4. Delete `schema/wiki_config.json` from the copy (forces setup wizard).
5. Walk `wiki/` in source; for each entity folder, create the matching folder in the new workspace `wiki/` and copy its `_type.yaml` and `_template.md` files only (no content pages).
6. Add new registry entry with `archived: false`, `setup_complete: false`.
7. Switch active workspace to the new workspace.
8. Return `{"id": ..., "name": ..., "setup_required": true}`.
   - Frontend receives `setup_required: true` and triggers the setup wizard, which detects the pre-copied `_type.yaml` files and pre-populates entity types (same path as importing a template bundle).

**Error cases for both modes:**
- Source workspace not found → 404.
- Name empty or results in duplicate slug after all suffix attempts → 400.

---

## Frontend

### WorkspaceSwitcher — Context Menu

Each workspace row in the dropdown gains a `...` icon button:
- **Desktop:** visible on row hover.
- **Mobile/touch:** always visible.

Clicking opens a small popover menu anchored to the button:

| Action | Condition | Behaviour |
|--------|-----------|-----------|
| Duplicate | Always available | Opens `DuplicateWorkspaceModal` pre-filled with source workspace |
| Archive | Non-active workspace only | Immediately calls `POST .../archive`, removes row from active list |
| Archive (greyed) | Active workspace | Disabled with tooltip: "Switch to another workspace first" |

### Archived Section

A collapsed disclosure row at the very bottom of the switcher dropdown, labelled **"Archived"** with a count badge (e.g., "Archived · 2"). Clicking it toggles open/closed to reveal archived workspace rows.

Each archived workspace row's `...` menu shows only:
- **Restore** — calls `POST .../unarchive`, moves workspace back to active list.

Archived workspaces cannot be switched to, duplicated, or set as active from this UI.

### DuplicateWorkspaceModal

A modal dialog with:

1. **Name field** — text input, pre-filled with "Copy of [source name]", user-editable.
2. **Mode selection** — two clickable cards (radio-style):
   - **Full Copy** — subtitle: "Copies all pages, sources, and content."
   - **Empty Wiki** — subtitle: "Copies the schema structure only. You'll complete setup to configure the new wiki."
3. **Duplicate button** — calls `POST /api/workspaces/{id}/duplicate` with `{name, mode}`.
   - Shows loading state while request is in-flight.
   - On success: closes modal, switches to new workspace (triggering setup wizard if template mode).
   - On error: shows inline error message.

---

## Data Flow Summary

```
User clicks "..." on workspace row
  → Duplicate → DuplicateWorkspaceModal
      → POST /workspaces/{id}/duplicate {name, mode}
          full:     copytree → switch → app ready
          template: copy schema/_type.yaml → switch → setup wizard (pre-populated)
  → Archive → POST /workspaces/{id}/archive
      → registry archived=true → row moves to Archived section
  → Restore → POST /workspaces/{id}/unarchive
      → registry archived=false → row moves back to active list
```

---

## Constraints & Edge Cases

- Active workspace cannot be archived. The `...` menu shows Archive as disabled with a tooltip.
- Archived workspaces cannot be duplicated from the UI (no `...` menu option while archived).
- Duplicate name collision: backend appends `-2`, `-3` etc. to the slug (same as workspace create).
- Template mode: the setup wizard must handle the case where `_type.yaml` files already exist in the wiki dir and use them to pre-populate entity types. This is already handled by the existing import-template path.
- `GET /api/workspaces` should return all workspaces including archived ones (frontend filters the display), so the archived count is always accurate.
