# Archive Bulk Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bulk select, bulk restore, and bulk permanent-delete to `ArchiveView.tsx` with a floating action bar.

**Architecture:** All changes are confined to the single React component `ArchiveView.tsx`. Selection state lives in a `Set<string>` keyed by `page:{filename}` or `source:{filename}`. Bulk operations fan out existing per-item API calls via `Promise.allSettled`. No backend changes required.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Lucide React, existing `API_BASE` config.

---

## File Map

| File | Change |
|------|--------|
| `Faragopedia-Sales/frontend/src/components/ArchiveView.tsx` | All changes — state, handlers, UI |

---

### Task 1: Add selection state, helpers, and bulk action handlers

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/ArchiveView.tsx`

- [ ] **Step 1: Add `useRef` to the React import and `X` to the Lucide import**

Replace the existing import lines at the top of the file:

```tsx
import React, { useState, useEffect, useRef } from 'react';
import { FileText, FileCheck, RotateCcw, Trash2, Loader2, Archive, X } from 'lucide-react';
```

- [ ] **Step 2: Add selection state and `bulkLoading` state**

Add these two state declarations immediately after the existing `const [error, setError]` line (line 13):

```tsx
const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
const [bulkLoading, setBulkLoading] = useState<boolean>(false);
```

- [ ] **Step 3: Add derived values**

Add these three derived constants immediately after the new state declarations:

```tsx
const totalItems = archivedPages.length + archivedSources.length;
const allSelected = selectedItems.size === totalItems && totalItems > 0;
const someSelected = selectedItems.size > 0 && !allSelected;
```

- [ ] **Step 4: Add a ref for the Select All checkbox's indeterminate state**

Add this ref declaration after the derived values:

```tsx
const selectAllRef = useRef<HTMLInputElement>(null);
```

- [ ] **Step 5: Add a `useEffect` to sync the indeterminate state on the Select All checkbox**

Add this effect after the existing `useEffect(() => { fetchArchivedItems(); }, [])`:

```tsx
useEffect(() => {
  if (selectAllRef.current) {
    selectAllRef.current.indeterminate = someSelected;
  }
}, [someSelected]);
```

- [ ] **Step 6: Add selection helper functions**

Add these three helper functions after the `fetchArchivedItems` function (around line 39):

```tsx
const toggleItem = (key: string) => {
  setSelectedItems(prev => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });
};

const toggleAll = () => {
  if (allSelected) {
    setSelectedItems(new Set());
  } else {
    setSelectedItems(new Set<string>([
      ...archivedPages.map(p => `page:${p}`),
      ...archivedSources.map(s => `source:${s}`),
    ]));
  }
};

const clearSelection = () => setSelectedItems(new Set());
```

- [ ] **Step 7: Add `handleBulkRestore`**

Add this function after `clearSelection`:

```tsx
const handleBulkRestore = async () => {
  setBulkLoading(true);
  const items = Array.from(selectedItems);
  const results = await Promise.allSettled(
    items.map(key => {
      const colonIdx = key.indexOf(':');
      const type = key.slice(0, colonIdx);
      const filename = key.slice(colonIdx + 1);
      const endpoint = type === 'page'
        ? `/archive/pages/${filename}/restore`
        : `/archive/sources/${encodeURIComponent(filename)}/restore`;
      return fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
    })
  );
  const failed = results.filter(
    r => r.status === 'rejected' || (r.status === 'fulfilled' && !r.value.ok)
  ).length;
  if (failed > 0) setError(`${failed} of ${items.length} items failed to restore.`);
  clearSelection();
  await fetchArchivedItems();
  setBulkLoading(false);
};
```

- [ ] **Step 8: Add `handleBulkDelete`**

Add this function after `handleBulkRestore`:

```tsx
const handleBulkDelete = async () => {
  if (!window.confirm(`Permanently delete ${selectedItems.size} item${selectedItems.size === 1 ? '' : 's'}? This cannot be undone.`)) return;
  setBulkLoading(true);
  const items = Array.from(selectedItems);
  const results = await Promise.allSettled(
    items.map(key => {
      const colonIdx = key.indexOf(':');
      const type = key.slice(0, colonIdx);
      const filename = key.slice(colonIdx + 1);
      const endpoint = type === 'page'
        ? `/archive/pages/${filename}/permanent`
        : `/archive/sources/${encodeURIComponent(filename)}/permanent`;
      return fetch(`${API_BASE}${endpoint}`, { method: 'DELETE' });
    })
  );
  const failed = results.filter(
    r => r.status === 'rejected' || (r.status === 'fulfilled' && !r.value.ok)
  ).length;
  if (failed > 0) setError(`${failed} of ${items.length} items failed to delete.`);
  clearSelection();
  await fetchArchivedItems();
  setBulkLoading(false);
};
```

- [ ] **Step 9: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/ArchiveView.tsx
git commit -m "feat: add selection state and bulk action handlers to ArchiveView"
```

---

### Task 2: Add checkboxes to item cards

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/ArchiveView.tsx`

Each card's left group currently has an icon + name. Add a checkbox before the icon. Also disable per-item buttons during `bulkLoading`.

- [ ] **Step 1: Update the Archived Wiki Pages card**

Find the page card's inner left div (currently starts with `<FileText className="w-5 h-5 text-gray-400`). Replace the entire card `<div key={page} ...>` with:

```tsx
<div key={page} className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-xl p-4 flex items-center justify-between shadow-sm hover:shadow-md transition-shadow">
  <div className="flex items-center space-x-3 overflow-hidden">
    <input
      type="checkbox"
      checked={selectedItems.has(`page:${page}`)}
      onChange={() => toggleItem(`page:${page}`)}
      disabled={bulkLoading}
      className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 flex-shrink-0 cursor-pointer"
    />
    <FileText className="w-5 h-5 text-gray-400 dark:text-gray-500 flex-shrink-0" />
    <span className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">
      {formatPageName(page)}
    </span>
  </div>
  <div className="flex items-center space-x-2">
    <button
      onClick={() => handleRestore(page, 'page')}
      disabled={!!actionLoading || bulkLoading}
      title="Restore"
      className="p-2 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors disabled:opacity-40"
    >
      {actionLoading === `page-restore-${page}` ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
    </button>
    <button
      onClick={() => handleDeletePermanent(page, 'page')}
      disabled={!!actionLoading || bulkLoading}
      title="Delete Permanently"
      className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors disabled:opacity-40"
    >
      {actionLoading === `page-delete-${page}` ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
    </button>
  </div>
</div>
```

- [ ] **Step 2: Update the Archived Sources card**

Replace the entire source card `<div key={source} ...>` with:

```tsx
<div key={source} className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-xl p-4 flex items-center justify-between shadow-sm hover:shadow-md transition-shadow">
  <div className="flex items-center space-x-3 overflow-hidden">
    <input
      type="checkbox"
      checked={selectedItems.has(`source:${source}`)}
      onChange={() => toggleItem(`source:${source}`)}
      disabled={bulkLoading}
      className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 flex-shrink-0 cursor-pointer"
    />
    <FileCheck className="w-5 h-5 text-gray-400 dark:text-gray-500 flex-shrink-0" />
    <span className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">{source}</span>
  </div>
  <div className="flex items-center space-x-2">
    <button
      onClick={() => handleRestore(source, 'source')}
      disabled={!!actionLoading || bulkLoading}
      title="Restore"
      className="p-2 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors disabled:opacity-40"
    >
      {actionLoading === `source-restore-${source}` ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
    </button>
    <button
      onClick={() => handleDeletePermanent(source, 'source')}
      disabled={!!actionLoading || bulkLoading}
      title="Delete Permanently"
      className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors disabled:opacity-40"
    >
      {actionLoading === `source-delete-${source}` ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
    </button>
  </div>
</div>
```

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/ArchiveView.tsx
git commit -m "feat: add checkboxes to archive item cards"
```

---

### Task 3: Add Select All control and floating action bar

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/ArchiveView.tsx`

- [ ] **Step 1: Add the Select All control above the grid**

Find the line:
```tsx
<div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
```

Insert this block immediately before it:

```tsx
{totalItems > 0 && (
  <div className="flex items-center space-x-3 mb-6">
    <input
      ref={selectAllRef}
      type="checkbox"
      checked={allSelected}
      onChange={toggleAll}
      disabled={bulkLoading}
      className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 cursor-pointer"
    />
    <span className="text-sm text-gray-600 dark:text-gray-400 select-none cursor-pointer" onClick={toggleAll}>
      {allSelected ? 'Deselect all' : 'Select all'}
    </span>
  </div>
)}
```

- [ ] **Step 2: Add the floating action bar**

Find the `{error && ...}` line near the bottom of the return. Insert this block immediately before it:

```tsx
<div
  className={`fixed bottom-0 left-0 right-0 z-50 transition-transform duration-200 ${
    selectedItems.size > 0 ? 'translate-y-0' : 'translate-y-full'
  }`}
>
  <div className="bg-gray-900 dark:bg-gray-950 border-t border-gray-700 px-6 py-4 flex items-center justify-between">
    <span className="text-sm font-medium text-gray-200">
      {selectedItems.size} selected
    </span>
    <div className="flex items-center space-x-3">
      {bulkLoading ? (
        <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
      ) : (
        <>
          <button
            onClick={handleBulkRestore}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            <span>Restore</span>
          </button>
          <button
            onClick={handleBulkDelete}
            className="flex items-center space-x-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            <span>Delete permanently</span>
          </button>
          <button
            onClick={clearSelection}
            title="Clear selection"
            className="p-2 text-gray-400 hover:text-gray-200 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </>
      )}
    </div>
  </div>
</div>
```

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/ArchiveView.tsx
git commit -m "feat: add Select All control and floating bulk action bar"
```

---

### Task 4: Browser verification

**Files:** none

- [ ] **Step 1: Ensure the dev server is running**

```bash
cd Faragopedia-Sales/frontend && npm run dev
```

Expected: Vite dev server starts on `http://localhost:5173` (or configured port).

- [ ] **Step 2: Navigate to the Archive view and verify checkboxes**

Open the app, navigate to the Archive view. Verify:
- Every item card (pages and sources) has a checkbox on the left.
- A "Select all" checkbox + label appears above the grid when items exist.
- No visual regressions on individual Restore / Delete buttons.

- [ ] **Step 3: Verify selection and floating bar**

- Check one item → floating bar slides up from bottom, shows "1 selected".
- Check more items → count updates.
- Check "Select all" → all checkboxes checked, label says "Deselect all".
- Click "Deselect all" → all unchecked, bar slides away.
- With some but not all checked → "Select all" checkbox shows indeterminate state (dash, not checkmark).

- [ ] **Step 4: Verify bulk restore**

- Check 1–2 archived pages/sources.
- Click Restore in the floating bar.
- Items disappear from the list; selection is cleared; bar slides away.

- [ ] **Step 5: Verify bulk permanent delete**

- Archive a test page (delete it from wiki view to send it to archive).
- Check it in Archive view.
- Click Delete permanently → confirm dialog shows correct item count.
- Confirm → item removed, selection cleared, bar slides away.

- [ ] **Step 6: Verify partial failure error toast**

This can be simulated by temporarily stopping the backend and performing a bulk restore — the error toast should show "N of M items failed to restore."

- [ ] **Step 7: Final commit if any minor fixes were made**

```bash
git add Faragopedia-Sales/frontend/src/components/ArchiveView.tsx
git commit -m "fix: browser-verified archive bulk actions"
```
