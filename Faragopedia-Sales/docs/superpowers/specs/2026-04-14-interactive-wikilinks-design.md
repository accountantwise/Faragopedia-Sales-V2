# Interactive WikiLinks — Design Spec
**Date:** 2026-04-14
**Status:** Approved
**Bug reference:** `docs/flaws-and-bugs-report.md` §1.1

---

## Problem

The LLM generates internal links using `[[Page Name]]` syntax. Gemini's initial
implementation partially wired this up (preprocessing + custom `a` renderer), but
navigation is broken because of a filename mismatch:

- `wiki_manager.py::_get_page_path` sanitizes page names by replacing only
  spaces, `/`, and `\` with `_`, preserving parentheses and other characters.
  Example: `Agent (Managed Agents Concept)` → `Agent_(Managed_Agents_Concept).md`
- `routes.py::secure_filename` replaces ALL non-alphanumeric characters with `_`,
  mangling the same name to `Agent___Managed_Agents_Concept_.md`.
- Clicking a WikiLink triggers a 404 because the two sanitization paths produce
  different filenames.

---

## Design

### Guiding principle

Separate two distinct operations that are currently conflated in `secure_filename`:
1. **Sanitize untrusted upload input** — aggressive, replaces all special chars.
2. **Validate a known wiki page lookup** — conservative, only prevents path
   traversal; never mangles the name.

---

### Backend — `backend/api/routes.py`

**`secure_filename` stays unchanged** and continues to be used for `POST /upload`.

**`GET /pages/{filename}`** replaces `secure_filename` with a dedicated
path-traversal-safe validator:

```python
def safe_wiki_filename(filename: str) -> str:
    """
    Validate a wiki page filename for safe lookup.
    Prevents path traversal without mangling valid page characters.
    """
    # Strip any directory components
    filename = os.path.basename(filename)
    # Must end in .md
    if not filename.endswith(".md"):
        raise ValueError("Invalid page filename")
    # Resolve and confirm it stays inside WIKI_DIR
    resolved = os.path.realpath(os.path.join(WIKI_DIR, filename))
    if not resolved.startswith(os.path.realpath(WIKI_DIR)):
        raise ValueError("Path traversal detected")
    return filename
```

The route uses this function and raises HTTP 400 on `ValueError`.

---

### Frontend — `frontend/src/components/WikiView.tsx`

**`processWikiLinks`** is updated to apply the same sanitization rules as
`_get_page_path` when constructing the anchor href:

```typescript
const processWikiLinks = (text: string) => {
  return text.replace(/\[\[(.*?)\]\]/g, (match, p1) => {
    // Mirror wiki_manager._get_page_path: replace spaces, forward/back slashes with _
    const safeTitle = p1.replace(/[ /\\]/g, '_');
    return `[${p1}](#${safeTitle})`;
  });
};
```

The existing custom `a` renderer (intercepts `href` starting with `#`, calls
`fetchPageContent(pageName + '.md')`) requires no changes.

**Result for `[[Agent (Managed Agents Concept)]]`:**
```
processWikiLinks → [Agent (Managed Agents Concept)](#Agent_(Managed_Agents_Concept))
a renderer       → fetchPageContent('Agent_(Managed_Agents_Concept).md')
backend lookup   → wiki/Agent_(Managed_Agents_Concept).md ✓
```

---

### Error handling

- **Dead link (target page missing):** `fetchPageContent` receives a 404.
  The existing error toast in `WikiView` surfaces this. No new code needed.
- **External links:** The `a` renderer already distinguishes external links
  (no `#` prefix) and opens them in a new tab. No change.
- **Sidebar selection:** Not updated on WikiLink navigation — intentional.

---

## Out of scope

- Navigation history (back/forward) — tracked separately in the bugs report.
- Backlinks / linked mentions — tracked separately.
- Visual distinction between WikiLinks and regular Markdown links — not requested.

---

## Files changed

| File | Change |
|------|--------|
| `backend/api/routes.py` | Add `safe_wiki_filename`; use it in `GET /pages/{filename}` |
| `frontend/src/components/WikiView.tsx` | Fix `processWikiLinks` sanitization |
