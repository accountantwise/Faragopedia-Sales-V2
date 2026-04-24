# Wiki Index Markdown Companion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-generate `wiki/_meta/index.md` (with clickable wikilinks grouped by entity type and flat A–Z) every time `search-index.json` is rebuilt, and display it in the wiki UI as a read-only page with a fixed "Index" link in the left panel.

**Architecture:** `_rebuild_index_md()` is called at the end of the existing `_rebuild_search_index()` method using the same in-memory `pages` list — no extra I/O. The frontend detects `system: true` in frontmatter to suppress editing controls. `_meta/` is excluded from `list_pages()` so it never pollutes search results or the entity type tree.

**Tech Stack:** Python / FastAPI backend (`wiki_manager.py`), React 18 / TypeScript frontend (`WikiView.tsx`), pytest for backend tests.

---

### Task 1: Backend — `_rebuild_index_md()` + exclusions

**Files:**
- Modify: `Faragopedia-Sales/backend/agent/wiki_manager.py`
- Test: `Faragopedia-Sales/backend/tests/test_wiki_manager.py`

- [ ] **Step 1: Write the failing tests**

Add to `test_wiki_manager.py`:

```python
import json

def test_rebuild_search_index_creates_index_md(temp_dirs):
    """_rebuild_search_index() must write wiki/_meta/index.md."""
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)

    # Create a page so index has content
    contacts_dir = os.path.join(wiki, "contacts")
    os.makedirs(contacts_dir, exist_ok=True)
    type_yaml = os.path.join(contacts_dir, "_type.yaml")
    with open(type_yaml, "w") as f:
        f.write("name: contacts\n")
    page_path = os.path.join(contacts_dir, "jane-doe.md")
    with open(page_path, "w") as f:
        f.write("---\nname: Jane Doe\ntags:\n  - prospect\n---\n# Jane Doe\n")

    manager._rebuild_search_index()

    index_md = os.path.join(wiki, "_meta", "index.md")
    assert os.path.exists(index_md), "_meta/index.md was not created"


def test_index_md_content(temp_dirs):
    """_meta/index.md must contain frontmatter, by-type sections, and A-Z list."""
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)

    contacts_dir = os.path.join(wiki, "contacts")
    os.makedirs(contacts_dir, exist_ok=True)
    with open(os.path.join(contacts_dir, "_type.yaml"), "w") as f:
        f.write("name: contacts\n")
    with open(os.path.join(contacts_dir, "jane-doe.md"), "w") as f:
        f.write("---\nname: Jane Doe\ntags:\n  - prospect\n---\n# Jane\n")
    with open(os.path.join(contacts_dir, "adam-smith.md"), "w") as f:
        f.write("---\nname: Adam Smith\ntags: []\n---\n# Adam\n")

    manager._rebuild_search_index()

    index_md = os.path.join(wiki, "_meta", "index.md")
    with open(index_md, "r", encoding="utf-8") as f:
        text = f.read()

    # Frontmatter
    assert "system: true" in text
    assert "generated_at:" in text

    # By-type section
    assert "## By Type" in text
    assert "### Contacts" in text
    assert "[[contacts/jane-doe]]" in text
    assert "`#prospect`" in text

    # A-Z section: Adam should appear before Jane
    assert "## All Pages (A" in text
    adam_pos = text.index("adam-smith")
    jane_pos = text.index("jane-doe")
    assert adam_pos < jane_pos, "A-Z list is not sorted alphabetically by title"


def test_list_pages_excludes_meta(temp_dirs):
    """list_pages() must not include _meta/index.md."""
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)

    meta_dir = os.path.join(wiki, "_meta")
    os.makedirs(meta_dir, exist_ok=True)
    with open(os.path.join(meta_dir, "index.md"), "w") as f:
        f.write("---\nsystem: true\n---\n# Index\n")

    contacts_dir = os.path.join(wiki, "contacts")
    os.makedirs(contacts_dir, exist_ok=True)
    with open(os.path.join(contacts_dir, "_type.yaml"), "w") as f:
        f.write("name: contacts\n")
    with open(os.path.join(contacts_dir, "jane-doe.md"), "w") as f:
        f.write("---\nname: Jane Doe\n---\n# Jane\n")

    pages = manager.list_pages()
    assert "_meta/index.md" not in pages
    assert "contacts/jane-doe.md" in pages
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd Faragopedia-Sales
pytest backend/tests/test_wiki_manager.py::test_rebuild_search_index_creates_index_md backend/tests/test_wiki_manager.py::test_index_md_content backend/tests/test_wiki_manager.py::test_list_pages_excludes_meta -v
```

Expected: all 3 FAIL.

- [ ] **Step 3: Implement `_rebuild_index_md()` in `wiki_manager.py`**

Add this method to the `WikiManager` class, directly after `_rebuild_search_index()` (around line 321):

```python
def _rebuild_index_md(self, pages: list, generated_at: str) -> None:
    meta_dir = os.path.join(self.wiki_dir, "_meta")
    os.makedirs(meta_dir, exist_ok=True)

    by_type: dict = {}
    for page in pages:
        by_type.setdefault(page["entity_type"], []).append(page)

    lines = [
        "---",
        "system: true",
        f"generated_at: {generated_at}",
        "---",
        "",
        "# Wiki Index",
        "",
        "## By Type",
        "",
    ]

    for et in sorted(by_type.keys()):
        heading = et.replace("-", " ").replace("_", " ").title()
        lines.append(f"### {heading}")
        for page in sorted(by_type[et], key=lambda p: p["title"].lower()):
            path_no_ext = page["path"].removesuffix(".md")
            tag_str = " ".join(f"`#{t}`" for t in page["tags"]) if page["tags"] else ""
            entry = f"- [[{path_no_ext}]] — {page['title']}"
            if tag_str:
                entry += f" {tag_str}"
            lines.append(entry)
        lines.append("")

    lines += [
        "---",
        "",
        "## All Pages (A–Z)",
        "",
    ]

    for page in sorted(pages, key=lambda p: p["title"].lower()):
        path_no_ext = page["path"].removesuffix(".md")
        lines.append(f"- [[{path_no_ext}]] — {page['title']}")

    index_md_path = os.path.join(meta_dir, "index.md")
    with open(index_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
```

- [ ] **Step 4: Call `_rebuild_index_md()` at the end of `_rebuild_search_index()`**

In `wiki_manager.py`, the end of `_rebuild_search_index()` currently looks like (around line 314):

```python
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, index_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
```

Add one line after `os.replace(...)`:

```python
            os.replace(tmp_path, index_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        self._rebuild_index_md(pages, index["generated_at"])
```

- [ ] **Step 5: Exclude `_meta/` in `list_pages()`**

In `wiki_manager.py`, the `list_pages()` method (around line 1121) currently reads:

```python
                if rel_path in ("index.md", "log.md"):
                    continue
```

Change it to:

```python
                if rel_path in ("index.md", "log.md") or rel_path.startswith("_meta/"):
                    continue
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest backend/tests/test_wiki_manager.py::test_rebuild_search_index_creates_index_md backend/tests/test_wiki_manager.py::test_index_md_content backend/tests/test_wiki_manager.py::test_list_pages_excludes_meta -v
```

Expected: all 3 PASS.

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
pytest backend/tests/ -v
```

Expected: all existing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add Faragopedia-Sales/backend/agent/wiki_manager.py Faragopedia-Sales/backend/tests/test_wiki_manager.py
git commit -m "feat: auto-generate wiki/_meta/index.md on every index rebuild"
```

---

### Task 2: Frontend — read-only system page detection

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/WikiView.tsx`

- [ ] **Step 1: Add `isSystemPage` state**

In `WikiView.tsx`, find the block of `useState` declarations near the top (around line 44–52). Add after `const [isSaving, setIsSaving] = useState<boolean>(false);`:

```tsx
const [isSystemPage, setIsSystemPage] = useState<boolean>(false);
```

- [ ] **Step 2: Parse `system: true` in `fetchPageContent`**

In `fetchPageContent` (around line 264), after the tag-parsing block (after `setSuggestedTags([]);`), add:

```tsx
      const systemMatch = /^system:\s*true\s*$/m.test(contentData.content);
      setIsSystemPage(systemMatch);
```

- [ ] **Step 3: Hide Edit button for system pages**

The Edit button is inside `{!isEditing && (...)}` around line 1027. The full block is:

```tsx
                  {isEditing ? (
                    <>
                      <button onClick={handleSave} ...>Save</button>
                      <button onClick={() => { setIsEditing(false); ...}} ...>Cancel</button>
                    </>
                  ) : (
                    <button
                      onClick={() => setIsEditing(true)}
                      className="flex items-center px-3 py-1.5 bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-md text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                    >
                      <Edit3 className="w-4 h-4 mr-1.5" />
                      Edit
                    </button>
                  )}
```

Replace the entire `isEditing ? ... : <Edit button>` ternary with:

```tsx
                  {isEditing ? (
                    <>
                      <button onClick={handleSave} disabled={isSaving} className="flex items-center px-3 py-1.5 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 transition-colors disabled:opacity-50">
                        {isSaving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Save className="w-4 h-4 mr-1.5" />}
                        Save
                      </button>
                      <button
                        onClick={() => { setIsEditing(false); setEditedContent(content || ''); }}
                        disabled={isSaving}
                        className="flex items-center px-3 py-1.5 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-md text-sm font-medium hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                      >
                        <X className="w-4 h-4 mr-1.5" />
                        Cancel
                      </button>
                    </>
                  ) : !isSystemPage ? (
                    <button
                      onClick={() => setIsEditing(true)}
                      className="flex items-center px-3 py-1.5 bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-md text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                    >
                      <Edit3 className="w-4 h-4 mr-1.5" />
                      Edit
                    </button>
                  ) : null}
```

- [ ] **Step 4: Hide tag edit controls for system pages**

The tag area is rendered around line 1086 inside `{selectedPage && !isEditing && (...)}`. It contains add-tag inputs and remove (`×`) buttons. Find the tag controls div that starts with:

```tsx
            {selectedPage && !isEditing && (
              <div className="flex flex-wrap items-center gap-1.5 px-6 pb-3 pt-1 border-b ...
```

Add `&& !isSystemPage` to the condition:

```tsx
            {selectedPage && !isEditing && !isSystemPage && (
```

- [ ] **Step 5: Manual test — load `_meta/index.md`**

Start the dev server:
```bash
cd Faragopedia-Sales/frontend && npm run dev
```

Open the wiki in the browser. Navigate to any page, then in the browser console run:

```js
// This simulates what the Index link will do (Task 3).
// For now, manually trigger via the network tab or a temporary button.
```

Instead, trigger a rebuild by saving any page, then check the file system to confirm `wiki/_meta/index.md` exists and contains the expected content. The UI test for the Index link comes in Task 3.

- [ ] **Step 6: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/WikiView.tsx
git commit -m "feat: hide edit controls for system pages (system: true frontmatter)"
```

---

### Task 3: Frontend — Index link in wiki left panel

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/WikiView.tsx`

- [ ] **Step 1: Add the Index link above entity type sections**

In `WikiView.tsx`, find the tree rendering block that starts with (around line 862):

```tsx
        {Object.keys(entityTypes).length === 0 ? (
          <p className="text-gray-500 text-sm">No pages found. Ingest some data first!</p>
        ) : (
          <div className="space-y-1">
            {Object.entries(entityTypes).map(([section, typeData]) => {
```

Replace the opening of the `<div className="space-y-1">` block to insert the Index link before the entity type map:

```tsx
        {Object.keys(entityTypes).length === 0 ? (
          <p className="text-gray-500 text-sm">No pages found. Ingest some data first!</p>
        ) : (
          <div className="space-y-1">
            <button
              onClick={() => fetchPageContent('_meta/index.md')}
              className={`w-full text-left px-2 py-2 rounded-lg text-sm transition-colors flex items-center gap-2 ${
                selectedPage === '_meta/index.md'
                  ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-bold'
                  : 'hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400'
              }`}
            >
              <List className="w-3.5 h-3.5 shrink-0" />
              <span className="text-xs font-semibold uppercase tracking-wider">Index</span>
            </button>
            {Object.entries(entityTypes).map(([section, typeData]) => {
```

- [ ] **Step 2: Import the `List` icon**

At the top of `WikiView.tsx`, find the lucide-react import line (something like):

```tsx
import { Search, ChevronRight, Edit3, Save, X, ... } from 'lucide-react';
```

Add `List` to that import.

- [ ] **Step 3: Manual test — Index link navigation**

With the dev server running:

1. Open the wiki. Confirm the **"Index"** link appears above the entity type sections in the left panel.
2. Click **Index**. Confirm the right pane loads the index page content with wikilinks rendered.
3. Click one of the wikilinks. Confirm it navigates to the correct page.
4. Return to the Index page. Confirm there is **no Edit button** and **no tag controls**.
5. Save or create any page. Revisit the index page (navigate away and back) to confirm it reflects the update.

- [ ] **Step 4: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/WikiView.tsx
git commit -m "feat: add Index link to wiki left panel pointing to _meta/index.md"
```
