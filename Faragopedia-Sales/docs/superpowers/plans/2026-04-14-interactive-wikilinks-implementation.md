# Interactive WikiLinks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `[[WikiLinks]]` so clicking them in the WikiView navigates to the target page.

**Architecture:** Two surgical changes — (1) replace the over-aggressive `secure_filename` on the GET pages route with a path-traversal-safe validator that preserves the characters `_get_page_path` uses when naming files; (2) fix the frontend preprocessor to apply the same sanitization rules when building hrefs from `[[...]]` syntax.

**Tech Stack:** Python/FastAPI (pytest), React/TypeScript (Vite, manual verification — no frontend test runner installed)

---

## File Map

| File | What changes |
|------|-------------|
| `backend/api/routes.py` | Add `safe_wiki_filename()`; use it in `GET /pages/{filename}` instead of `secure_filename` |
| `backend/tests/test_api.py` | Add tests for `safe_wiki_filename` and the updated route behaviour |
| `frontend/src/components/WikiView.tsx` | Fix `processWikiLinks` regex replacement to mirror `_get_page_path` |

---

## Task 1: Backend — `safe_wiki_filename` validator

**Files:**
- Modify: `backend/api/routes.py`
- Test: `backend/tests/test_api.py`

---

- [ ] **Step 1: Write the failing tests**

First, add `import pytest` to the imports block at the **top** of `backend/tests/test_api.py` (after the existing imports):

```python
import pytest
```

Then add the following tests to the **bottom** of the file. The import of `safe_wiki_filename` will fail until the function is added in Step 3, which is the expected red state.

```python
# --- safe_wiki_filename unit tests ---

from api.routes import safe_wiki_filename

def test_safe_wiki_filename_plain():
    assert safe_wiki_filename("FastAPI.md") == "FastAPI.md"

def test_safe_wiki_filename_preserves_parens():
    # This is the real bug: secure_filename mangles these
    assert safe_wiki_filename("Agent_(Managed_Agents_Concept).md") == "Agent_(Managed_Agents_Concept).md"

def test_safe_wiki_filename_preserves_plus():
    assert safe_wiki_filename("Agent_SDK_+_Trigger.dev.md") == "Agent_SDK_+_Trigger.dev.md"

def test_safe_wiki_filename_strips_directory_components():
    # Path traversal attempt: basename strips the leading ../
    # The function must NOT raise — it just returns the safe basename
    result = safe_wiki_filename("../etc/passwd.md")
    assert result == "passwd.md"

def test_safe_wiki_filename_rejects_non_md():
    with pytest.raises(ValueError):
        safe_wiki_filename("passwd")

def test_safe_wiki_filename_rejects_non_md_with_traversal():
    with pytest.raises(ValueError):
        safe_wiki_filename("../etc/passwd")

# --- Route integration: GET /pages/{filename} passes correct name to get_page_content ---

@patch("api.routes.wiki_manager.get_page_content")
def test_get_page_preserves_parens_in_filename(mock_get):
    """Ensure the route does NOT mangle parentheses before calling get_page_content."""
    mock_get.return_value = "# Agent"
    response = client.get("/api/pages/Agent_(Managed_Agents_Concept).md")
    assert response.status_code == 200
    mock_get.assert_called_once_with("Agent_(Managed_Agents_Concept).md")

@patch("api.routes.wiki_manager.get_page_content")
def test_get_page_rejects_non_md(mock_get):
    """Filename without .md extension must return 400, not 404/500."""
    response = client.get("/api/pages/passwd")
    assert response.status_code == 400
    mock_get.assert_not_called()
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run from the project root:
```bash
cd "C:\Users\Colacho\Nextcloud\AI\VS Code\Faragopedia\Faragopedia-Sales"
python -m pytest backend/tests/test_api.py -v -k "safe_wiki or preserves_parens or rejects_non_md"
```
Expected: `ImportError: cannot import name 'safe_wiki_filename' from 'api.routes'`

- [ ] **Step 3: Add `safe_wiki_filename` to `routes.py`**

Open `backend/api/routes.py`. After the `secure_filename` function (line 34), insert:

```python
def safe_wiki_filename(filename: str) -> str:
    """
    Validate a wiki page filename for safe lookup.
    Strips directory components and enforces .md extension without
    mangling the characters that _get_page_path preserves (parentheses, +, etc.).
    """
    filename = os.path.basename(filename)
    if not filename.endswith(".md"):
        raise ValueError(f"Invalid page filename: {filename!r} — must end with .md")
    wiki_real = os.path.realpath(WIKI_DIR)
    resolved = os.path.realpath(os.path.join(wiki_real, filename))
    if not (resolved == wiki_real or resolved.startswith(wiki_real + os.sep)):
        raise ValueError("Path traversal detected")
    return filename
```

- [ ] **Step 4: Update `GET /pages/{filename}` to use `safe_wiki_filename`**

Replace the existing `get_page` route (starting at `@router.get("/pages/{filename}")`) with:

```python
@router.get("/pages/{filename}")
async def get_page(filename: str):
    try:
        safe_name = safe_wiki_filename(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        return {"content": wiki_manager.get_page_content(safe_name)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading page: {str(e)}")
```

- [ ] **Step 5: Run all backend tests to confirm green**

```bash
python -m pytest backend/tests/test_api.py -v
```
Expected: all tests pass, including the new ones. The existing `test_get_page` and `test_get_page_not_found` tests must still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes.py backend/tests/test_api.py
git commit -m "fix(api): replace secure_filename on GET /pages with safe path validator

secure_filename was mangling parentheses and + signs in wiki page filenames
that _get_page_path preserves. safe_wiki_filename prevents path traversal via
os.path.basename + .md enforcement without changing valid page characters."
```

---

## Task 2: Frontend — Fix `processWikiLinks`

**Files:**
- Modify: `frontend/src/components/WikiView.tsx:48-53`

No frontend test runner is installed. Verification is manual via the Vite dev server.

---

- [ ] **Step 1: Update `processWikiLinks` in `WikiView.tsx`**

Find the `processWikiLinks` function (lines 48–53):

```typescript
  const processWikiLinks = (text: string) => {
    return text.replace(/\[\[(.*?)\]\]/g, (match, p1) => {
      // Use the page name as the hash to identify internal links
      return `[${p1}](#${p1})`;
    });
  };
```

Replace it with:

```typescript
  const processWikiLinks = (text: string) => {
    return text.replace(/\[\[(.*?)\]\]/g, (match, p1) => {
      // Mirror wiki_manager._get_page_path: replace spaces, forward/back slashes with _
      const safeTitle = p1.replace(/[ /\\]/g, '_');
      return `[${p1}](#${safeTitle})`;
    });
  };
```

- [ ] **Step 2: Start the dev server and verify manually**

In one terminal:
```bash
cd "C:\Users\Colacho\Nextcloud\AI\VS Code\Faragopedia\Faragopedia-Sales\backend"
uvicorn main:app --host 0.0.0.0 --port 8300 --reload
```
In a second terminal:
```bash
cd "C:\Users\Colacho\Nextcloud\AI\VS Code\Faragopedia\Faragopedia-Sales\frontend"
npm run dev
```

Open the app, navigate to the Wiki view, select a page that contains a `[[WikiLink]]` (e.g. `index.md` or any entity page).

Check that:
- [ ] WikiLinks render as blue clickable links (not plain text)
- [ ] Clicking a WikiLink loads the target page content in the main content area
- [ ] Clicking a WikiLink to a page with parentheses in its name (e.g. `[[Agent (Managed Agents Concept)]]`) loads correctly
- [ ] Clicking a dead WikiLink (target page doesn't exist) shows the error toast
- [ ] External markdown links (starting with `http`) still open in a new tab

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/WikiView.tsx
git commit -m "fix(ui): correct WikiLink href sanitization to match backend naming

processWikiLinks was emitting raw page names with spaces as hrefs.
The a-renderer reconstructed filenames that didn't match what
_get_page_path created (spaces should become underscores). Now mirrors
the same replacement rules so [[Page Name]] resolves to Page_Name.md."
```
