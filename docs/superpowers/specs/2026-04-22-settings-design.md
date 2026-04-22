# Settings Section — Design Spec
**Date:** 2026-04-22  
**Branch:** setup-wizard  
**Implementation split:** Backend → Claude. Frontend → Gemini per Claude's written instructions.

---

## Overview

Add a Settings section to Faragopedia-Sales. It surfaces three features: appearance (theme), wiki reconfiguration, and export/import of wiki infrastructure files. Settings opens as a slide-out drawer from the sidebar. Import lives exclusively inside the SetupWizard as an alternative to the creation flow.

---

## 1. Settings Drawer

### Trigger
- Remove the existing "Reconfigure Wiki" button from the Sidebar footer.
- Add a `⚙` gear icon (`Settings` from lucide-react) pinned to the bottom of the sidebar, above where the reconfigure button was.
- Clicking it sets `settingsOpen = true` in `App.tsx`.

### Layout
- 320px panel slides in from the right edge of the viewport.
- Semi-transparent dark backdrop covers the rest of the app (`bg-black/40` or equivalent).
- Clicking the backdrop closes the drawer.
- Header: "Settings" label + `✕` close button.
- Footer: displays the current wiki name (read from `wiki_config.json` via existing `/api/setup/config`).

### Sections (top to bottom)

#### Appearance
- Section label: "APPEARANCE"
- Segmented pill control with three equal segments: `☀ Light` · `◑ System` · `● Dark`
- Active segment highlighted in blue (`bg-blue-600 text-white`), inactive segments muted.
- Selection updates theme immediately.

#### Wiki
- Section label: "WIKI"
- Single button: "↻ Reconfigure Wiki" — calls the existing `handleReconfigure()` flow in `App.tsx` and closes the drawer.

#### Export
- Section label: "EXPORT"
- Description line: "Wiki infrastructure files"
- Sub-label listing included files: `SCHEMA.md · index.md · log.md · company_profile.md · wiki_config.json`
- Button: "⬇ Download as .zip" — calls `GET /api/export/bundle`, triggers browser download.

---

## 2. Theme System

### State
- Single `theme` state in `App.tsx`: `'light' | 'dark' | 'system'`. Default `'system'`.
- Persisted to `localStorage` under key `faragopedia-theme`.
- On mount, read from `localStorage` (fallback to `'system'`).

### Application
- A `useEffect` watches `theme`. It resolves the effective mode:
  - `'light'` → remove `dark` class from `<html>`
  - `'dark'` → add `dark` class to `<html>`
  - `'system'` → add/remove `dark` based on `window.matchMedia('(prefers-color-scheme: dark)')`, with a listener to update on OS change.
- Tailwind `darkMode: 'class'` must be set in `tailwind.config.js` (add if not already present).
- All existing components use hardcoded light-mode Tailwind classes. The implementation plan must include retrofitting every component with `dark:` variants. This is the largest part of the frontend work.

---

## 3. Export — Backend Endpoint

**Endpoint:** `GET /api/export/bundle`  
**Response:** `application/zip` with `Content-Disposition: attachment; filename="wiki-bundle.zip"`

### Files included (all read from the wiki root directory)
| File | Notes |
|---|---|
| `SCHEMA.md` | LLM operating manual / entity schema |
| `index.md` | Master page catalog |
| `log.md` | Append-only activity log |
| `company_profile.md` | Org identity |
| `wiki_config.json` | Setup config (name, org, entity types) |

### Behaviour
- If a file doesn't exist, skip it silently (don't error).
- Use Python's `zipfile` stdlib — no new dependencies.
- Wiki root path comes from the same source used by `WikiManager` (`WIKI_DIR` env var or default).

### New file
`Faragopedia-Sales/backend/api/export_routes.py`  
Registered in `main.py` under prefix `/api/export`.

---

## 4. Import — SetupWizard Changes

### New "step 0" — Getting Started screen
Before the current Step 1 (Identity), insert a new first screen with two options:

**Option A — Start fresh**  
> Proceeds to the existing Step 1 → Step 2 → Step 3 flow unchanged.

**Option B — Import from backup**  
> Shows a file picker (`.zip` only). On file selection:
> 1. Upload zip to `POST /api/export/import` (multipart form).
> 2. Backend validates and extracts `SCHEMA.md`, `company_profile.md`, `wiki_config.json`.
> 3. On success, skip to a confirmation screen (new Step 3 variant) showing what was found in the zip.
> 4. User confirms → wizard calls `complete_setup()` as normal → `onComplete()`.

This screen is skipped entirely in `reconfigureMode` (reconfiguring an existing wiki should not offer import).

### Import endpoint — Backend (two steps)

**Step 1 — Upload & stage**  
**Endpoint:** `POST /api/export/import`  
**Request:** `multipart/form-data` with a single `file` field (`.zip`)  
**Response:** `{ wiki_name, org_name, org_description, entity_types[] }`

Behaviour:
- Validate that the uploaded file is a valid zip.
- Extract `SCHEMA.md` and `company_profile.md` and write them to the wiki directory immediately — these must be preserved verbatim.
- Parse `wiki_config.json` to extract identity fields and return them to the frontend.
- Do **not** write `wiki_config.json`, `index.md`, or create entity folders yet.

**Step 2 — Finalize**  
**Endpoint:** `POST /api/export/import/finalize`  
**Request:** `{ wiki_name, org_name, org_description, entity_types[] }` (same shape returned by step 1, possibly edited by user on confirmation screen)  
**Response:** `{ success: true }`

Behaviour:
- Create entity folders from `entity_types`.
- Write `wiki_config.json` with `setup_complete: true`.
- Write fresh `index.md` and `log.md`.
- Do **not** regenerate or overwrite `SCHEMA.md` or `company_profile.md` (already written by step 1).

This two-step approach is necessary because `complete_setup()` regenerates `SCHEMA.md` from entity types, which would overwrite the richer imported version.

### Validation errors on upload (return HTTP 422)
- Not a valid zip file.
- `wiki_config.json` missing or unparseable.
- `SCHEMA.md` missing.

---

## 5. Sidebar Changes

| Change | Detail |
|---|---|
| Remove | "Reconfigure Wiki" button + `Settings` icon from footer |
| Add | `⚙` gear icon button at bottom of sidebar, `title="Settings"` tooltip |
| Prop removed | `onReconfigure` — no longer needed on Sidebar; reconfigure is triggered from inside the drawer |
| Prop added | `onOpenSettings: () => void` |

The gear icon calls `onOpenSettings`. Reconfigure is now only accessible from inside the drawer.

---

## 6. App.tsx Changes

New state:
```ts
const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system')
const [settingsOpen, setSettingsOpen] = useState(false)
```

Pass to `Sidebar`:
```tsx
<Sidebar
  ...existing props...
  onOpenSettings={() => setSettingsOpen(true)}
/>
```

Render `SettingsDrawer` outside `renderContent()`, always mounted:
```tsx
<SettingsDrawer
  open={settingsOpen}
  onClose={() => setSettingsOpen(false)}
  theme={theme}
  onThemeChange={setTheme}
  onReconfigure={() => { setSettingsOpen(false); handleReconfigure(); }}
/>
```

Theme `useEffect` also lives in `App.tsx`.

---

## 7. New Frontend Component

**`src/components/SettingsDrawer.tsx`**

Props:
```ts
interface SettingsDrawerProps {
  open: boolean
  onClose: () => void
  theme: 'light' | 'dark' | 'system'
  onThemeChange: (t: 'light' | 'dark' | 'system') => void
  onReconfigure: () => void
}
```

Internal state: `wikiName` (fetched from `/api/setup/config` on first open).

---

## 8. Files Touched

### Backend (Claude implements)
- `backend/api/export_routes.py` — new file: `GET /bundle`, `POST /import`, `POST /import/finalize`
- `backend/main.py` — register export router under `/api/export`

### Frontend (Gemini implements per plan)
- `frontend/src/App.tsx` — theme state, settingsOpen state, SettingsDrawer render, theme useEffect
- `frontend/src/components/Sidebar.tsx` — remove reconfigure button, add gear icon + onOpenSettings prop
- `frontend/src/components/SettingsDrawer.tsx` — new component
- `frontend/src/components/SetupWizard.tsx` — add step 0, import flow
- `frontend/tailwind.config.js` — add `darkMode: 'class'`
- All existing components — add `dark:` Tailwind variants (largest task)
