# Archive Bulk Actions Design

**Date:** 2026-05-11  
**Feature:** Bulk delete and bulk restore in the Archive view  
**Status:** Approved

---

## Overview

Add bulk selection with floating action bar to `ArchiveView.tsx`, allowing users to select multiple archived items (wiki pages and sources together) and restore or permanently delete them in one action.

---

## Architecture

This is a purely frontend change. No new backend endpoints are needed — bulk operations fan out existing per-item API calls in parallel. All changes are confined to `ArchiveView.tsx`.

---

## UI Components

### Checkboxes on Item Cards
Each item card (both pages and sources) gets a checkbox on its left edge, always visible. The card layout changes from `flex items-center justify-between` to accommodate the checkbox before the file icon + name group.

### Select All Control
A single "Select all / Deselect all" checkbox + label sits above the two-column grid, spanning both sections. States:
- **Unchecked** — no items selected
- **Indeterminate** — some but not all selected
- **Checked** — all items selected

Clicking it toggles between select-all and deselect-all.

### Floating Action Bar
Fixed to the bottom of the viewport. Appears with a smooth slide-up (`translate-y` transition) when `selectedItems.size > 0`, disappears when empty.

Contents (left to right):
- "N selected" count label
- Blue **Restore** button with RotateCcw icon
- Red **Delete permanently** button with Trash2 icon
- Grey **×** clear-selection button

All buttons disabled and bar shows a Loader2 spinner during an in-flight bulk operation.

---

## Selection State

```ts
const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
```

Each item's key is `page:${filename}` or `source:${filename}`. This keeps pages and sources in one unified pool while remaining distinguishable for API routing.

Helper toggles:
- `toggleItem(key)` — add or remove one key
- `toggleAll()` — if all selected, clear; otherwise select all
- `clearSelection()` — reset to empty set

Derived values:
- `totalItems = archivedPages.length + archivedSources.length`
- `allSelected = selectedItems.size === totalItems && totalItems > 0`
- `someSelected = selectedItems.size > 0 && !allSelected` (indeterminate state)

---

## Bulk Action Execution

### Bulk Restore
1. Fan out all selected items to their existing restore endpoints in parallel via `Promise.all`.
2. Pages: `POST /archive/pages/{filename}/restore`
3. Sources: `POST /archive/sources/{encodeURIComponent(filename)}/restore`
4. On completion: clear selection, refetch list.
5. On partial failure: show error toast — "N of M items failed to restore."

### Bulk Permanent Delete
1. Show a single `window.confirm`: "Permanently delete N items? This cannot be undone."
2. If confirmed, fan out all selected items to their permanent-delete endpoints in parallel.
3. Pages: `DELETE /archive/pages/{filename}/permanent`
4. Sources: `DELETE /archive/sources/{encodeURIComponent(filename)}/permanent`
5. On completion: clear selection, refetch list.
6. On partial failure: show error toast — "N of M items failed to delete."

### Loading State
- `bulkLoading: boolean` state tracks whether a bulk operation is in flight.
- During bulk operation: floating bar shows spinner, all buttons (individual + bulk) are disabled.
- Existing `actionLoading` for individual item actions continues to work independently.

---

## Error Handling

- Collect settled results from `Promise.allSettled` (not `Promise.all`) to avoid early-exit on first failure.
- Count rejections; if any, show: `"N of M items failed to [restore/delete]."` via existing `ErrorToast`.
- Successful items are still removed from the list on refetch.

---

## Files Changed

| File | Change |
|------|--------|
| `Faragopedia-Sales/frontend/src/components/ArchiveView.tsx` | All UI and logic changes |

No backend changes required.

---

## Out of Scope

- New backend bulk endpoints (per-item parallel calls are sufficient)
- Bulk actions on workspace archives (WorkspaceSwitcher handles those separately)
- Filtering or sorting within the archive view
