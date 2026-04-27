# Dynamic Frontmatter Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make frontmatter fields in the wiki view editable inline — enum fields show a styled dropdown, text fields become inputs on click, each saving independently via a new PATCH endpoint.

**Architecture:** The entity type `_type.yaml` files are the source of truth for field schemas. A new `GET /entity-types/{type}/field-schema` endpoint extracts enum fields and their values. A `PATCH /pages/{path}/frontmatter` endpoint updates a single field in place. The frontend fetches the schema on page load and renders interactive badges in view mode.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript (frontend), existing `load_type_yaml` / `_parse_frontmatter` / `_render_frontmatter` helpers already in codebase.

---

## File Map

| File | What changes |
|------|-------------|
| `backend/agent/schema_builder.py` | Update default contacts schema to include full rich field set |
| `backend/agent/wiki_manager.py` | Add `get_field_schema()` and `patch_frontmatter_field()` |
| `backend/api/routes.py` | Add `GET /entity-types/{type}/field-schema` and `PATCH /pages/{path}/frontmatter` |
| `backend/tests/test_api.py` | Add tests for both new routes |
| `frontend/src/components/WikiView.tsx` | Add schema state + fetch, replace static value span with interactive component |

---

### Task 1: Update contacts schema in `schema_builder.py`

The default contacts schema in `_DEFAULT_TYPE_YAMLS` has only basic fields. The real contact pages use a richer schema with enum fields. Update it so that `bootstrap_type_yamls()` seeds the correct schema into new installs, and `get_field_schema()` (Task 2) returns useful data.

**Files:**
- Modify: `backend/agent/schema_builder.py:28-41`

- [ ] **Step 1: Replace the contacts entry in `_DEFAULT_TYPE_YAMLS`**

In `backend/agent/schema_builder.py`, find the `"contacts"` key in `_DEFAULT_TYPE_YAMLS` (around line 28) and replace it:

```python
    "contacts": {
        "name": "Contacts",
        "description": "Individual people across all organisations",
        "singular": "contact",
        "fields": [
            {"name": "type", "type": "string", "default": "contact"},
            {"name": "name", "type": "string", "required": True},
            {"name": "company", "type": "string"},
            {"name": "job_title", "type": "string"},
            {"name": "department", "type": "string"},
            {"name": "seniority", "type": "enum",
             "values": ["Director", "Manager", "Executive", "C-Suite", "Freelance"]},
            {"name": "email", "type": "string"},
            {"name": "phone", "type": "string"},
            {"name": "linkedin", "type": "string"},
            {"name": "source", "type": "enum",
             "values": ["RocketReach", "LinkedIn", "Referral", "Event", "Inbound", "Meeting Log"]},
            {"name": "relationship", "type": "enum",
             "values": ["Cold", "Warm", "Hot", "Client", "Lapsed"]},
            {"name": "farago_contact", "type": "string"},
            {"name": "industries", "type": "list", "default": "[]"},
            {"name": "role_tags", "type": "list", "default": "[]"},
            {"name": "internal_or_freelance", "type": "enum",
             "values": ["Internal", "Freelance"]},
            {"name": "first_contacted", "type": "date"},
            {"name": "last_contacted", "type": "date"},
            {"name": "last_meeting", "type": "date"},
            {"name": "next_follow_up", "type": "date"},
            {"name": "status", "type": "enum",
             "values": ["Active", "Dormant", "Converted", "Lost"]},
            {"name": "notes", "type": "string"},
        ],
        "sections": ["Summary", "Interaction History", "Related Contacts"],
    },
```

- [ ] **Step 2: Commit**

```bash
git add Faragopedia-Sales/backend/agent/schema_builder.py
git commit -m "feat: update contacts schema with full field set and enum values"
```

---

### Task 2: Add `get_field_schema()` to `wiki_manager.py`

This method reads the entity type's `_type.yaml` and returns only enum fields with their values.

**Files:**
- Modify: `backend/agent/wiki_manager.py` (after `get_entity_types()` around line 494)
- Test: `backend/tests/test_wiki_manager.py`

- [ ] **Step 1: Write the failing test**

Open `backend/tests/test_wiki_manager.py` and add at the bottom:

```python
def test_get_field_schema_returns_enum_fields(tmp_path):
    import yaml
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    contacts_dir = wiki_dir / "contacts"
    contacts_dir.mkdir()
    (contacts_dir / "_type.yaml").write_text(yaml.dump({
        "name": "Contacts",
        "singular": "contact",
        "fields": [
            {"name": "type", "type": "string", "default": "contact"},
            {"name": "name", "type": "string"},
            {"name": "status", "type": "enum", "values": ["Active", "Dormant"]},
            {"name": "relationship", "type": "enum", "values": ["Cold", "Warm", "Hot"]},
            {"name": "notes", "type": "string"},
            {"name": "tags", "type": "list", "default": "[]"},
        ],
    }))
    from agent.wiki_manager import WikiManager
    wm = WikiManager(wiki_dir=str(wiki_dir), sources_dir=str(tmp_path / "sources"))
    schema = wm.get_field_schema("contacts")
    assert schema == {
        "status": ["Active", "Dormant"],
        "relationship": ["Cold", "Warm", "Hot"],
    }

def test_get_field_schema_unknown_type_returns_empty(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    from agent.wiki_manager import WikiManager
    wm = WikiManager(wiki_dir=str(wiki_dir), sources_dir=str(tmp_path / "sources"))
    assert wm.get_field_schema("nonexistent") == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_wiki_manager.py::test_get_field_schema_returns_enum_fields tests/test_wiki_manager.py::test_get_field_schema_unknown_type_returns_empty -v
```

Expected: FAIL with `AttributeError: 'WikiManager' object has no attribute 'get_field_schema'`

- [ ] **Step 3: Implement `get_field_schema()` in `wiki_manager.py`**

Open `backend/agent/wiki_manager.py`. After the `get_entity_types()` method (around line 496), add:

```python
    def get_field_schema(self, entity_type: str) -> dict:
        """Return a dict of {field_name: [option, ...]} for enum fields of an entity type.
        Reads from _type.yaml. Returns {} if type not found or has no enum fields.
        """
        from agent.schema_builder import load_type_yaml
        folder_path = os.path.join(self.wiki_dir, entity_type)
        type_data = load_type_yaml(folder_path)
        if not type_data:
            return {}
        return {
            field["name"]: field["values"]
            for field in type_data.get("fields", [])
            if field.get("type") == "enum" and field.get("values")
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_wiki_manager.py::test_get_field_schema_returns_enum_fields tests/test_wiki_manager.py::test_get_field_schema_unknown_type_returns_empty -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/agent/wiki_manager.py Faragopedia-Sales/backend/tests/test_wiki_manager.py
git commit -m "feat: add get_field_schema() to WikiManager"
```

---

### Task 3: Add `patch_frontmatter_field()` to `wiki_manager.py`

Updates a single frontmatter key in a page file and rebuilds the search index.

**Files:**
- Modify: `backend/agent/wiki_manager.py` (after `get_field_schema()`)
- Test: `backend/tests/test_wiki_manager.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_wiki_manager.py`:

```python
import pytest

@pytest.mark.asyncio
async def test_patch_frontmatter_field_updates_value(tmp_path):
    import yaml
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    contacts_dir = wiki_dir / "contacts"
    contacts_dir.mkdir()
    page = contacts_dir / "alice.md"
    page.write_text("---\nname: Alice\nstatus: Active\n---\n\n## Summary\n")
    from agent.wiki_manager import WikiManager
    wm = WikiManager(wiki_dir=str(wiki_dir), sources_dir=str(tmp_path / "sources"))
    await wm.patch_frontmatter_field("contacts/alice.md", "status", "Dormant")
    updated = page.read_text()
    fm, _ = wm._parse_frontmatter(updated)
    assert fm["status"] == "Dormant"

@pytest.mark.asyncio
async def test_patch_frontmatter_field_bad_path_raises(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    from agent.wiki_manager import WikiManager
    wm = WikiManager(wiki_dir=str(wiki_dir), sources_dir=str(tmp_path / "sources"))
    with pytest.raises(FileNotFoundError):
        await wm.patch_frontmatter_field("contacts/missing.md", "status", "Active")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_wiki_manager.py::test_patch_frontmatter_field_updates_value tests/test_wiki_manager.py::test_patch_frontmatter_field_bad_path_raises -v
```

Expected: FAIL with `AttributeError: 'WikiManager' object has no attribute 'patch_frontmatter_field'`

- [ ] **Step 3: Implement `patch_frontmatter_field()` in `wiki_manager.py`**

After `get_field_schema()`, add:

```python
    async def patch_frontmatter_field(self, page_path: str, field: str, value) -> None:
        """Update a single frontmatter field in a page and rebuild the search index."""
        abs_path = os.path.join(self.wiki_dir, page_path.replace("/", os.sep))
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Page not found: {page_path}")
        async with self._write_lock:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            fm, body = self._parse_frontmatter(content)
            fm[field] = value
            updated = self._render_frontmatter(fm, body)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(updated)
        self._rebuild_search_index()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_wiki_manager.py::test_patch_frontmatter_field_updates_value tests/test_wiki_manager.py::test_patch_frontmatter_field_bad_path_raises -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/agent/wiki_manager.py Faragopedia-Sales/backend/tests/test_wiki_manager.py
git commit -m "feat: add patch_frontmatter_field() to WikiManager"
```

---

### Task 4: Add `GET /entity-types/{type}/field-schema` route

**Files:**
- Modify: `backend/api/routes.py` (after the `GET /entity-types` route around line 345)
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Open `backend/tests/test_api.py`. Find the existing `client` fixture and check that `mock_wm` has a `get_field_schema` mock. Add it to the fixture setup near line 50:

```python
    mock_wm.get_field_schema.return_value = {
        "status": ["Active", "Dormant"],
        "relationship": ["Cold", "Warm", "Hot"],
    }
```

Then add the test function at the bottom of the file:

```python
def test_get_field_schema_returns_schema(client):
    response = client.get("/entity-types/contacts/field-schema")
    assert response.status_code == 200
    data = response.json()
    assert data["schema"]["status"] == ["Active", "Dormant"]
    assert data["schema"]["relationship"] == ["Cold", "Warm", "Hot"]

def test_get_field_schema_unknown_type(client):
    from unittest.mock import MagicMock
    # get_entity_types already returns known types; nonexistent won't be in it
    response = client.get("/entity-types/nonexistent/field-schema")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_api.py::test_get_field_schema_returns_schema tests/test_api.py::test_get_field_schema_unknown_type -v
```

Expected: FAIL with 404/422 (route not found)

- [ ] **Step 3: Add the route in `routes.py`**

After the `GET /entity-types` route (around line 345), add:

```python
@router.get("/entity-types/{entity_type}/field-schema")
async def get_field_schema(wm: WM, entity_type: str):
    if entity_type not in get_valid_entity_subdirs(wm):
        raise HTTPException(status_code=404, detail=f"Unknown entity type: {entity_type}")
    try:
        return {"schema": wm.get_field_schema(entity_type)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_api.py::test_get_field_schema_returns_schema tests/test_api.py::test_get_field_schema_unknown_type -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Faragopedia-Sales/backend/api/routes.py Faragopedia-Sales/backend/tests/test_api.py
git commit -m "feat: add GET /entity-types/{type}/field-schema route"
```

---

### Task 5: Add `PATCH /pages/{path}/frontmatter` route

**Files:**
- Modify: `backend/api/routes.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_api.py`, add `patch_frontmatter_field` mock to the `client` fixture (near the other AsyncMock lines):

```python
    mock_wm.patch_frontmatter_field = AsyncMock()
```

Then add test functions at the bottom:

```python
def test_patch_frontmatter_field_success(client):
    response = client.patch(
        "/pages/contacts/test-page.md/frontmatter",
        json={"field": "status", "value": "Dormant"}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True

def test_patch_frontmatter_field_missing_field(client):
    response = client.patch(
        "/pages/contacts/test-page.md/frontmatter",
        json={"value": "Dormant"}
    )
    assert response.status_code == 422

def test_patch_frontmatter_field_invalid_path(client):
    response = client.patch(
        "/pages/../etc/passwd/frontmatter",
        json={"field": "status", "value": "Dormant"}
    )
    assert response.status_code in (400, 422)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_api.py::test_patch_frontmatter_field_success tests/test_api.py::test_patch_frontmatter_field_missing_field tests/test_api.py::test_patch_frontmatter_field_invalid_path -v
```

Expected: FAIL (route not found)

- [ ] **Step 3: Add the route in `routes.py`**

Place this route **before** the `GET /pages/{path:path}` route (around line 304) so the more specific path isn't swallowed by the catch-all:

```python
@router.patch("/pages/{path:path}/frontmatter")
async def patch_frontmatter(wm: WM, path: str, payload: dict):
    field = payload.get("field")
    if not field:
        raise HTTPException(status_code=422, detail="'field' is required")
    value = payload.get("value", "")
    try:
        safe_path = safe_wiki_filename(path, wm)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await wm.patch_frontmatter_field(safe_path, field, value)
        return {"ok": True}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/test_api.py::test_patch_frontmatter_field_success tests/test_api.py::test_patch_frontmatter_field_missing_field tests/test_api.py::test_patch_frontmatter_field_invalid_path -v
```

Expected: PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
cd Faragopedia-Sales/backend
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests pass (or same failures as before this task).

- [ ] **Step 6: Commit**

```bash
git add Faragopedia-Sales/backend/api/routes.py Faragopedia-Sales/backend/tests/test_api.py
git commit -m "feat: add PATCH /pages/{path}/frontmatter route"
```

---

### Task 6: Add field schema state and fetch to `WikiView.tsx`

Add a `fieldSchema` state variable and fetch the schema whenever a new page loads.

**Files:**
- Modify: `frontend/src/components/WikiView.tsx`

- [ ] **Step 1: Add `fieldSchema` and `savingField` state**

In `WikiView.tsx`, find the state declarations block (around line 37). After the existing tag management state block (around line 84), add:

```typescript
  // Frontmatter inline editing
  const [fieldSchema, setFieldSchema] = useState<Record<string, string[]>>({});
  const [savingField, setSavingField] = useState<string | null>(null);
  const [savedField, setSavedField] = useState<string | null>(null);
```

- [ ] **Step 2: Add `fetchFieldSchema()` function**

Find `fetchSearchIndex` (around line 102). After the closing `};` of that function, add:

```typescript
  const fetchFieldSchema = async (pagePath: string) => {
    const entityType = pagePath.split('/')[0];
    if (!entityType || entityType.startsWith('_')) {
      setFieldSchema({});
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/entity-types/${entityType}/field-schema`);
      if (!res.ok) { setFieldSchema({}); return; }
      const data = await res.json();
      setFieldSchema(data.schema ?? {});
    } catch {
      setFieldSchema({});
    }
  };
```

- [ ] **Step 3: Call `fetchFieldSchema` when a page loads**

Find `fetchPageContent` (search for `const fetchPageContent`). Inside it, after the line that calls `setSelectedPage(filename)` (or sets the content), add a call:

```typescript
      fetchFieldSchema(filename);
```

The exact location is after the line `setSelectedPage(filename);` inside `fetchPageContent`. Look for:

```typescript
      setSelectedPage(filename);
```

And add the call immediately after it:

```typescript
      setSelectedPage(filename);
      fetchFieldSchema(filename);
```

- [ ] **Step 4: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/WikiView.tsx
git commit -m "feat: add fieldSchema state and fetch on page load"
```

---

### Task 7: Add `patchFrontmatterField()` helper and `FrontmatterValue` component to `WikiView.tsx`

Replace the static value span in the frontmatter display with an interactive component.

**Files:**
- Modify: `frontend/src/components/WikiView.tsx`

- [ ] **Step 1: Add `patchFrontmatterField()` helper**

Find `renderFrontmatterValue` (line 690). Just before it, add:

```typescript
  const patchFrontmatterField = async (field: string, value: string) => {
    if (!selectedPage) return;
    setSavingField(field);
    try {
      await fetch(`${API_BASE}/pages/${encodeURIComponent(selectedPage)}/frontmatter`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ field, value }),
      });
      // Update local content so the badge reflects the new value immediately
      setContent(prev => {
        if (!prev) return prev;
        return prev.replace(
          new RegExp(`^(${field}\\s*:).*$`, 'm'),
          `$1 ${value}`
        );
      });
      setSavedField(field);
      setTimeout(() => setSavedField(null), 1500);
    } catch {
      // silently fail — raw editor still available
    } finally {
      setSavingField(null);
    }
  };
```

- [ ] **Step 2: Add `FrontmatterValue` component**

Immediately after `patchFrontmatterField`, add the inline component. This component decides how to render each field:

```typescript
  const READ_ONLY_FM_FIELDS = new Set(['type', 'name']);

  const FrontmatterValue: React.FC<{ fieldKey: string; raw: string }> = ({ fieldKey, raw }) => {
    const value = raw.replace(/^["']|["']$/g, '').trim();
    const isSaving = savingField === fieldKey;
    const isSaved = savedField === fieldKey;
    const isReadOnly = READ_ONLY_FM_FIELDS.has(fieldKey);

    // List values (arrays) — render existing pill display, read-only
    if (value.startsWith('[') && !value.startsWith('[[')) {
      return <span className="text-blue-600 dark:text-blue-400 font-bold">{renderFrontmatterValue(raw)}</span>;
    }

    // Read-only fields
    if (isReadOnly) {
      return <span className="text-blue-600 dark:text-blue-400 font-bold">{renderFrontmatterValue(raw)}</span>;
    }

    // Saving indicator overlay
    const indicator = isSaving
      ? <span className="ml-1 text-gray-400 dark:text-gray-500 text-[9px]">…</span>
      : isSaved
      ? <span className="ml-1 text-green-500 text-[9px]">✓</span>
      : null;

    // Enum field — styled select
    if (fieldSchema[fieldKey]) {
      return (
        <span className="inline-flex items-center">
          <select
            value={value}
            disabled={isSaving}
            onChange={e => patchFrontmatterField(fieldKey, e.target.value)}
            className="text-blue-600 dark:text-blue-400 font-bold text-xs bg-transparent border-none outline-none cursor-pointer appearance-none pr-3 hover:underline focus:underline"
            style={{ fontFamily: 'inherit' }}
          >
            {!value && <option value="">—</option>}
            {fieldSchema[fieldKey].map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
          {indicator}
        </span>
      );
    }

    // Free-text field — click-to-edit input
    return <TextFrontmatterValue fieldKey={fieldKey} value={value} indicator={indicator} onSave={patchFrontmatterField} />;
  };
```

- [ ] **Step 3: Add `TextFrontmatterValue` helper component**

Just after `FrontmatterValue`, add this small component that handles the click-to-edit text input behaviour:

```typescript
  const TextFrontmatterValue: React.FC<{
    fieldKey: string;
    value: string;
    indicator: React.ReactNode;
    onSave: (field: string, value: string) => Promise<void>;
  }> = ({ fieldKey, value, indicator, onSave }) => {
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState(value);
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);

    const commit = () => {
      setEditing(false);
      if (draft !== value) onSave(fieldKey, draft);
    };

    if (!editing) {
      return (
        <span className="inline-flex items-center">
          <span
            className="text-blue-600 dark:text-blue-400 font-bold cursor-text hover:underline"
            onClick={() => { setDraft(value); setEditing(true); }}
          >
            {value || <span className="text-gray-300 dark:text-gray-600 italic font-normal">—</span>}
          </span>
          {indicator}
        </span>
      );
    }

    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={e => {
          if (e.key === 'Enter') commit();
          if (e.key === 'Escape') { setDraft(value); setEditing(false); }
        }}
        className="text-blue-600 dark:text-blue-400 font-bold text-xs bg-transparent border-b border-blue-400 dark:border-blue-600 outline-none min-w-[4rem]"
        style={{ fontFamily: 'inherit' }}
      />
    );
  };
```

- [ ] **Step 4: Replace the static value span in the frontmatter display**

Find the frontmatter display block (around line 1326). The current code is:

```tsx
                         {tags.map((t, idx) => (
                           <span key={idx} className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 shadow-sm uppercase tracking-wider">
                             <span className="text-gray-400 dark:text-gray-500 mr-2 text-[10px]">{t.key}:</span>
                             <span className="text-blue-600 dark:text-blue-400 font-bold">{renderFrontmatterValue(t.value)}</span>
                           </span>
                         ))}
```

Replace it with:

```tsx
                         {tags.map((t, idx) => (
                           <span key={idx} className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 shadow-sm uppercase tracking-wider">
                             <span className="text-gray-400 dark:text-gray-500 mr-2 text-[10px]">{t.key}:</span>
                             {isEditing
                               ? <span className="text-blue-600 dark:text-blue-400 font-bold">{renderFrontmatterValue(t.value)}</span>
                               : <FrontmatterValue fieldKey={t.key} raw={t.value} />
                             }
                           </span>
                         ))}
```

(When the user is in raw-editor mode, keep the static display to avoid confusion between the two edit modes.)

- [ ] **Step 5: Build and check for TypeScript errors**

```bash
cd Faragopedia-Sales/frontend
npm run build 2>&1 | tail -30
```

Expected: Build succeeds with no TypeScript errors. If there are errors, fix them before proceeding.

- [ ] **Step 6: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/WikiView.tsx
git commit -m "feat: add interactive frontmatter badges with dropdown and inline text editing"
```

---

### Task 8: Manual smoke test

Start the dev stack and verify the feature works end-to-end.

- [ ] **Step 1: Start the backend**

```bash
cd Faragopedia-Sales/backend
python main.py
```

- [ ] **Step 2: Start the frontend dev server**

```bash
cd Faragopedia-Sales/frontend
npm run dev
```

- [ ] **Step 3: Open a contact page and verify dropdowns**

1. Open the app in the browser
2. Navigate to any contact page (e.g. `contacts/alexandra-cernanova.md`)
3. Confirm the frontmatter block renders at the top
4. Click the `relationship` field value — a dropdown should appear with options: Cold, Warm, Hot, Client, Lapsed
5. Select a different value — the badge should update and a ✓ should briefly appear
6. Reload the page — the new value should persist
7. Click a text field (e.g. `email`) — it should become an editable input
8. Edit the value and press Enter — the badge updates, a ✓ appears briefly
9. Reload — value persists
10. Confirm `type` and `name` fields are NOT editable (no click behaviour)
11. Confirm `industries` and `role_tags` (list fields) still render as pill badges, not inputs

- [ ] **Step 4: Commit any fixes found during smoke test**

```bash
git add -p
git commit -m "fix: <describe what needed fixing>"
```
