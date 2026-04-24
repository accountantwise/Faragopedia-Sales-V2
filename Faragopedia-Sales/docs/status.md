# Project Status

> This is the living status document for Faragopedia-Sales.
> AI agents should read this at the start of every session and update it at the
> end of any session where meaningful work was done.

---

## Current Phase: 🟡 MVP Development / Prototype Functional

**Last updated:** 2026-04-24

---

## Recent Activity

| Date       | Agent/Person | Summary                                       |
| ---------- | ------------ | --------------------------------------------- |
| 2026-04-24 | Claude | **Entity Type Templates — designed and planned**. Design spec saved to `docs/superpowers/specs/2026-04-24-entity-templates-design.md`. Full 5-task TDD implementation plan saved to `docs/superpowers/plans/2026-04-24-entity-templates.md`. Feature: during setup wizard completion, generate a `_template.md` per entity type co-located with `_type.yaml`; filter `_`-prefixed files from `list_pages()`; pre-populate new pages from the template. Pure backend — no frontend changes. No code changes yet. |
| 2026-04-22 | Claude | **Settings Section — designed and planned** (branch: `setup-wizard`). Design spec saved to `docs/superpowers/specs/2026-04-22-settings-design.md`. Full 13-task TDD implementation plan saved to `docs/superpowers/plans/2026-04-22-settings-implementation.md`. Feature covers: slide-out SettingsDrawer (theme toggle, reconfigure, export zip), Tailwind dark mode (`dark:` class strategy), backend export/import API (3 endpoints), SetupWizard step-0 import-from-backup flow. Backend tasks (1–5) → Claude. Frontend tasks (6–13) → Gemini. No code changes yet. |
| 2026-04-21 | Claude | **Setup Wizard — All 10 tasks complete** (branch: `setup-wizard`). Tasks 3–9 implemented: `setup_wizard.py` Pydantic models + core functions + `complete_setup()`; `setup_routes.py` 5 endpoints + `suggest_schema_llm()`; `main.py` startup migration + WikiManager init; `Sidebar.tsx` wikiName prop + Reconfigure button; `App.tsx` setup state gating + reconfigure flow; `SetupWizard.tsx` full 3-step wizard (identity → schema review → confirm/launch). `wiki_config.json` generated on setup completion. |
| 2026-04-21 | Claude | **Setup Wizard — Tasks 1–2 complete** (branch: `setup-wizard`). Task 1: `WikiManager._load_system_prompt()` now returns a stub string instead of raising `FileNotFoundError` when schema files are absent. Task 2: Replaced module-level `WikiManager` singleton in `routes.py` with FastAPI DI (`get_wiki_manager`, `set_wiki_manager`, `WM = Annotated[WikiManager, Depends(...)]`); `safe_wiki_filename` now takes explicit `wm` param; all 139 tests updated and passing. Tasks 3–10 remain. |
| 2026-04-20 | Claude | **Desktop UI/UX Polish**: Standardized list and search item padding, adjusted chat bubble spacing, constrained Wiki width for readability, and fixed search results layout bugs (nested scrollbars, overlap). Changed New Page icon. |
| 2026-04-20 | Claude | **Branch Merges**: Merged all feature branches (`big-refactor`, `dynamic-folders`, `search-and-tags`, `bulk-actions`, `linting-system`) into `main` and pruned local/remote branches. |
| 2026-04-20 | Claude | **Actionable Lint — Tasks 4–7 complete** (branch: `bulk-actions` / `linting-system`). API endpoints for lint fix & snapshot management added. Frontend: implemented `LintView.tsx` with bulk apply and `SnapshotsPanel.tsx` for rollbacks. Wired up successfully. |
| 2026-04-20 | Claude | **Actionable Lint — Tasks 1–3 complete**. Backend fully implemented: `LintFinding` updated with `fix_confidence` and `fix_description`; new models `LintFixPlan`, `FixReport`, `Snapshot`; `FIX_HUMAN_TEMPLATE` added; snapshot methods added to `WikiManager`; `fix_lint_findings` + `_run_fix_llm` added; `snapshots_data` Docker volume added. |
| 2026-04-19 | Claude | **Bulk Move & Bulk Download — fully implemented** (branch: `bulk-actions`). All 7 tasks complete. Backend: `POST /pages/bulk-move` (renames pages between entity subdirs, rewrites all `[[wikilinks]]` across the wiki via `rewrite_wikilinks`), `POST /pages/bulk-download` (ZIP stream of selected pages), `POST /sources/bulk-download` (ZIP stream of selected sources). Frontend: new `MoveDialog.tsx` component (radio-button destination picker), bulk Move + Download buttons added to `WikiView` and `SourcesView` desktop toolbars and mobile floating action menus. 12 backend tests passing, 3 smoke test sections added. Branch pushed to GitHub. |
| 2026-04-19 | Claude | **Search & Tags — fully implemented** (branch: `search-and-tags`). All 8 tasks complete. Backend: `_parse_frontmatter`, `_render_frontmatter`, `_strip_markdown`, `_rebuild_search_index` added to `WikiManager`; index rebuilt on every write; `update_page_tags`, `update_source_tags` added; `_suggest_tags` via LLM; 5 new API endpoints (`GET /search/index`, `GET /tags`, `PATCH /pages/{path}/tags`, `PATCH /sources/{filename}/tags`, `POST /search/rebuild`). Frontend: `WikiView.tsx` — full-width search bar, client-side results panel with tag filter row, tag chips below page title with add/remove/AI-suggestion UI; `SourcesView.tsx` — same search + tag chips pattern. 111 backend tests passing. |
| 2026-04-18 | Claude | **Search & Tags — designed and planned** (branch: `search-and-tags`, off `dynamic-folders`). Per-view keyword search (client-side JSON index), shared free-form tag system (pages + sources), AI tag suggestion. Design spec saved to `docs/superpowers/specs/2026-04-18-search-and-tags-design.md`. Full 8-task TDD implementation plan saved to `docs/superpowers/plans/2026-04-18-search-and-tags.md`. No code changes yet. |
| 2026-04-18 | Claude | **Dynamic Folders — all 7 tasks complete** (branch: `dynamic-folders`). Seeded `_type.yaml` for 5 entity folders; built `schema_builder.py` (TDD, 6 tests); added folder CRUD + page move + wikilink rewriting to `WikiManager` (TDD, 10 tests); added 5 new API endpoints (TDD, 17 API tests); updated `WikiView.tsx` with dynamic sidebar, New Folder dialog, Move Page dialog; regenerated `SCHEMA.md`; e2e integration test. 87 tests passing. |
| 2026-04-17 | Claude | **Dynamic Folders feature designed and planned** (branch: `dynamic-folders`, off `big-refactor`). Designed collaborative wiki architecture: `_type.yaml` per folder, `SCHEMA_TEMPLATE.md` + auto-generated `SCHEMA.md`, folder CRUD, page move, wikilink rewriting. Full 7-task implementation plan saved to `docs/superpowers/plans/2026-04-17-dynamic-folders.md`. No code changes yet — plan only. |
| 2026-04-16 | Gemini | **Wiki-Concept Integration — Tasks 1–12 complete** (branch: `big-refactor`). All frontend and backend tasks finished, verified with tests. |
| 2026-04-16 | Claude | **Wiki-Concept Integration — Tasks 1–9 complete** (branch: `big-refactor`). See details below. Tasks 10–12 remain. |
| 2026-04-15 | Claude | **Wiki-Concept Integration Plan**: Authored design spec (`docs/superpowers/specs/2026-04-15-wiki-integration-design.md`) and full implementation plan (`docs/superpowers/plans/2026-04-15-wiki-integration-claude.md`). Plan covers 12 tasks: schema files, new Pydantic models, recursive traversal, path security, ingest redesign, query update, lint operation, create_new_page, API routes, WikiView tree, LintView/Sidebar/App, and final integration test. |
| 2026-04-14 | Gemini | **Documentation Audit**: Synchronized `AGENTS.md`, updated `docs/flaws-and-bugs-report.md` with resolved features, and authored [ADR 0001](decisions/0001-file-management-and-ingestion.md). |
| 2026-04-14 | Gemini | **Improved Ingestion**: Added manual ingestion control. Users can now upload sources without immediate ingestion, track status via a new metadata system, and trigger ingestion manually from the Sources view. |
| 2026-04-14 | Gemini | **Sources Navigation**: Implemented back/forward history navigation in the Sources view, mirroring the Wiki view behavior. |
| 2026-04-14 | Gemini | **File Management**: Added Archive, Restore, Delete (Trash Bin), and Download capabilities for both Wiki pages and Sources. Implemented a new 'Archive' storage location and UI view. Added 'New Page' feature (Untitled.md default). |
| 2026-04-14 | Gemini | **Sources View**: Added a new view to browse and read raw source files (including PDF text extraction). Implemented backend endpoints `GET /api/sources` and `GET /api/sources/{filename}`. |
| 2026-04-14 | Gemini | **Deployment Fixes**: Resolved "empty container" issue by removing source code volume mounts in `docker-compose.yml`. Updated `backend/main.py` CORS and frontend `App.tsx`/`WikiView.tsx` to use dynamic backend URLs based on `window.location.hostname`. |
| 2026-04-14 | Claude       | **Ingestion Race Condition Fix**: Added `asyncio.Lock` to `WikiManager`. `ingest_source` split into two phases — LLM inference runs concurrently, file writes serialized. 33/33 tests passing. Merged to main. |
| 2026-04-14 | Claude       | **Interactive WikiLinks Fix**: Fixed filename mismatch between `_get_page_path` and `secure_filename`. Added `safe_wiki_filename` to routes for path-traversal-safe page lookups. Fixed `processWikiLinks` in `WikiView.tsx` to mirror backend sanitization rules. 18/18 tests passing. Merged to main. |
| 2026-04-14 | Gemini       | **Interactive WikiLinks & Port Refactoring**: Changed backend port to 8300 to resolve allocation conflicts. Updated all API calls and documentation. Implemented interactive `[[WikiLinks]]` in the frontend for associative navigation. |
| 2026-04-14 | Gemini       | **Local Development Workflow**: Verified local execution of FastAPI and Vite without Docker. Successfully tested ingestion and chat with OpenRouter/Claude Sonnet. |
| 2026-04-13 | Gemini       | **Implemented Multi-Provider LLM Support**: Added dynamic switching between OpenAI, Anthropic, Gemini, and OpenRouter via factory pattern in `WikiManager`. Updated tests and API to handle multiple providers. |
| 2026-04-13 | Gemini       | **Finalized MVP Features**: Implemented `WikiView`, `Upload`, and `Chat` frontend views with `react-markdown` and `lucide-react`. Added Wiki Health Check logic to `WikiManager`. |
| 2026-04-13 | Gemini       | **Completed Scaffolding**: Built FastAPI backend with upload/chat routes and React/Vite/Tailwind frontend layout. |
| 2026-04-13 | Gemini       | **Architectural Design**: Authored design docs and implementation plans for the LLM Wiki webapp. |
| 2026-04-13 | Claude       | Initialized project scaffold, shared AI context, Docker skeleton. |

---

## What Exists Now

- [x] Project scaffold with shared AI-agent context (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`)
- [x] Git configuration (`.gitignore`, `.editorconfig`)
- [x] Docker setup and project structure (`backend/`, `frontend/`, `sources/`, `wiki/`)
- [x] Dockerfiles and docker-compose.yml with named volumes
- [x] Initial FastAPI (backend/main.py) and React (frontend/) placeholders
- [x] Backend routes for upload and chat (with security and Docker fixes)
- [x] Frontend layout with Sidebar and view switching (React + Tailwind)
- [x] WikiManager with LangChain ingestion and health check logic
- [x] Functional Wiki, Upload, Chat, and Health Check UI views
- [x] Multi-Provider LLM Integration (OpenAI, Anthropic, Gemini, OpenRouter)
- [x] Documentation structure (`docs/status.md`, `docs/decisions/`)
- [x] Port conflict resolved (Backend moved to 8300)
- [x] Local development verification (FastAPI + Vite)
- [x] Interactive [[WikiLinks]] ✅ Fixed (2026-04-14)
- [x] Ingestion Race Conditions ✅ Fixed (2026-04-14)
- [x] Backlinks/Linked Mentions ✅ Fixed (2026-04-14)
- [x] Navigation History (back/forward) ✅ Fixed (2026-04-14)
- [x] Edit Page capability ✅ Fixed (2026-04-14)
- [x] Sources View (Browse/Read raw data) ✅ Fixed (2026-04-14)
- [x] File Management (New, Archive, Restore, Delete, Download) ✅ (2026-04-14)
- [x] Improved Source Ingestion (Manual control, Status tracking) ✅ (2026-04-14)
- [x] Sources Navigation (Back/Forward) ✅ (2026-04-14)
- [x] Dynamic Folders (user-managed wiki folders, page move, wikilink rewriting, auto-generated SCHEMA.md) ✅ (2026-04-18) — branch: `dynamic-folders`
- [x] Search & Tags (per-view keyword search, shared tag vocabulary, AI tag suggestion) ✅ (2026-04-19) — branch: `search-and-tags`
- [x] Bulk Move (wiki pages between entity types, automatic wikilink rewriting) ✅ (2026-04-19) — branch: `bulk-actions`
- [x] Bulk Download (pages + sources as ZIP archive) ✅ (2026-04-19) — branch: `bulk-actions`
- [x] Actionable Lint (checkbox findings, Apply Selected, snapshot rollback) ✅ (2026-04-20) — branch: `bulk-actions`
- [x] Setup Wizard (first-run identity + LLM schema generation, company-agnostic config) ✅ (2026-04-21) — branch: `setup-wizard`
- [ ] Settings Section (slide-out drawer, dark mode, export/import infrastructure files) 🟡 Planned — branch: `setup-wizard`
- [ ] Entity Type Templates (`_template.md` per entity type, pre-populated new pages) 🟡 Planned — `main`

---

## Actionable Lint Progress (branch: `bulk-actions`)

| Task | Status | Description |
| ---- | ------ | ----------- |
| 1 | ✅ Done | Updated `LintFinding` (`fix_confidence`, `fix_description`); added `LintFixPlan`, `FixReport`, `Snapshot` models; updated `LINT_HUMAN_TEMPLATE`; added `FIX_HUMAN_TEMPLATE` |
| 2 | ✅ Done | Snapshot methods (`create_snapshot`, `list_snapshots`, `restore_snapshot`, `delete_snapshot`) + `snapshots_data` Docker volume |
| 3 | ✅ Done | `fix_lint_findings` + `_run_fix_llm` on WikiManager |
| 4 | ✅ Done | API endpoints: `POST /lint/fix`, `GET /snapshots`, `POST /snapshots/{id}/restore`, `DELETE /snapshots/{id}` |
| 5 | ✅ Done | `LintView.tsx` — checkboxes, fix-confidence badges, Select All, Apply Selected button, inline FixReport panel |
| 6 | ✅ Done | `SnapshotsPanel.tsx` — collapsible snapshot list with Restore (+ confirmation) and Delete |
| 7 | ✅ Done | Wire `SNAPSHOTS_DIR` into `WikiManager` instantiation in `routes.py` |

**Current test state:** All tests passing.

---

## Bulk Actions Progress (branch: `bulk-actions`)

| Task | Status | Description |
| ---- | ------ | ----------- |
| 1 | ✅ Done | `POST /pages/bulk-move` — moves pages between entity subdirs, rewrites all wikilinks via `rewrite_wikilinks` helper |
| 2 | ✅ Done | `POST /pages/bulk-download` — streams selected wiki pages as `pages-export.zip` |
| 3 | ✅ Done | `POST /sources/bulk-download` — streams selected source files as `sources-export.zip` |
| 4 | ✅ Done | `MoveDialog.tsx` — radio-button destination picker modal |
| 5 | ✅ Done | `WikiView.tsx` — bulk Move + Download buttons (desktop toolbar + mobile floating menu) |
| 6 | ✅ Done | `SourcesView.tsx` — bulk Download button (desktop toolbar + mobile floating menu) |
| 7 | ✅ Done | Smoke tests — sections 9–11 for move dialog, wiki download, sources download |

**Current test state:** 12 backend tests passing, 0 failed.

---

## Search & Tags Progress (branch: `search-and-tags`)

| Task | Status | Description |
| ---- | ------ | ----------- |
| 1 | ✅ Done | WikiManager parsing helpers + `_rebuild_search_index` + startup init |
| 2 | ✅ Done | Hook `_rebuild_search_index` into all write operations |
| 3 | ✅ Done | WikiManager tag management (`update_page_tags`, `update_source_tags`) |
| 4 | ✅ Done | `_suggest_tags` + hook into `save_page_content` and `ingest_source` |
| 5 | ✅ Done | API endpoints (`/search/index`, `/tags`, PATCH tags, `/search/rebuild`) |
| 6 | ✅ Done | Frontend WikiView — search bar + results panel |
| 7 | ✅ Done | Frontend WikiView — tag chips, add/remove, filter row, AI suggestion UI |
| 8 | ✅ Done | Frontend SourcesView — search bar + tag chips |

**Current test state:** 111 passed, 0 failed.

---

## Dynamic Folders Progress (branch: `dynamic-folders`)

| Task | Status | Description |
| ---- | ------ | ----------- |
| 1 | ✅ Done | Seed `_type.yaml` metadata files for 5 entity folders |
| 2 | ✅ Done | `schema_builder.py` — type discovery + SCHEMA.md assembly (TDD, 6 tests) |
| 3 | ✅ Done | `WikiManager` folder CRUD + page move + wikilink rewriting (TDD, 10 tests) |
| 4 | ✅ Done | 5 new API endpoints: entity-types, folder create/rename/delete, page move (TDD, 17 tests) |
| 5 | ✅ Done | `WikiView.tsx` — dynamic sidebar, New Folder dialog, Move Page dialog |
| 6 | ✅ Done | Regenerate `SCHEMA.md` from template + `_type.yaml` seed files |
| 7 | ✅ Done | End-to-end integration test |

**Current test state:** 87 passed, 0 failed.

---

## Wiki-Concept Integration Progress (branch: `big-refactor`)

| Task | Status | Description |
| ---- | ------ | ----------- |
| 1 | ✅ Done | Data migration: schema files copied to `backend/schema/`, wiki subdirs created, old pages deleted, Dockerfile updated |
| 2 | ✅ Done | New Pydantic models: `WikiPage`, `FaragoIngestionResult`, `LintFinding`, `LintReport`; `schema_dir` param + `_load_system_prompt()` added to WikiManager |
| 3 | ✅ Done | Recursive traversal: `list_pages()`, `update_index()`, `get_backlinks()` updated for subdirectory structure; `test_km_features.py` replaced |
| 4 | ✅ Done | Path security: `safe_wiki_filename` now requires `subdir/page.md` form with known entity subdirectory |
| 5 | ✅ Done | Ingest redesign: schema-aware `ingest_source()` using `FaragoIngestionResult` with retry logic; old `Entity`/`IngestionResult` models removed |
| 6 | ✅ Done | Query update: `query()` now uses system prompt + `ChatPromptTemplate`; `_run_query_llm()` extracted for testability |
| 7 | ✅ Done | Lint operation: `lint()` + `_run_lint_llm()` added; `health_check()` removed; `test_wiki_manager_health.py` deleted |
| 8 | ✅ Done | `create_new_page(entity_type)` — accepts entity_type param, writes to correct subdir with YAML frontmatter |
| 9 | ✅ Done | API routes — `GET /pages` grouped by entity type, `POST /lint` added, `GET /health` removed, all page routes use `{path:path}`, `POST /pages` accepts `entity_type`, `test_api.py` rewritten |
| 10 | ✅ Done | Frontend WikiView tree — collapsible entity sections, entity-type new-page menu, path-aware wikilinks |
| 11 | ✅ Done | Frontend Sidebar/LintView/App — replace Health Check with Lint nav, create LintView.tsx |
| 12 | ✅ Done | Final integration test |

**Current test state:** 52 passed, 0 failed (all backend tests clean).

## Setup Wizard Progress (branch: `setup-wizard`)

| Task | Status | Description |
| ---- | ------ | ----------- |
| 1 | ✅ Done | `WikiManager._load_system_prompt()` returns stub when schema files absent (no crash) |
| 2 | ✅ Done | FastAPI DI refactor: `get_wiki_manager`/`set_wiki_manager`/`WM` type alias; `safe_wiki_filename` takes explicit `wm`; 139 tests passing |
| 3 | ✅ Done | `setup_wizard.py` — Pydantic models + core functions (`is_setup_complete`, `get_wiki_config`, `migrate_existing`, `clear_setup`) + `BASE_SCHEMA_TEMPLATE` |
| 4 | ✅ Done | `setup_wizard.py` — `complete_setup()` orchestrator |
| 5 | ✅ Done | `setup_routes.py` — 5 setup API endpoints + `suggest_schema_llm()` |
| 6 | ✅ Done | `main.py` — startup migration + `WikiManager` init; register `setup_router` |
| 7 | ✅ Done | `Sidebar.tsx` — `wikiName` prop + Reconfigure button |
| 8 | ✅ Done | `App.tsx` — setup state gating + reconfigure flow |
| 9 | ✅ Done | `SetupWizard.tsx` — full 3-step wizard (identity → schema review → confirm/launch) |
| 10 | ✅ Done | End-to-end verification |

---

## Settings Section Progress (branch: `setup-wizard`)

**Plan:** `docs/superpowers/plans/2026-04-22-settings-implementation.md`
**Spec:** `docs/superpowers/specs/2026-04-22-settings-design.md`

### Backend (Claude implements)

| Task | Status | Description |
| ---- | ------ | ----------- |
| 1 | ⬜ Todo | `setup_wizard.py` — add `finalize_import()` function |
| 2 | ⬜ Todo | `export_routes.py` — `GET /api/export/bundle` (zip of 5 infrastructure files) |
| 3 | ⬜ Todo | `export_routes.py` — `POST /api/export/import` (stage zip, write SCHEMA.md + company_profile.md, return config) |
| 4 | ⬜ Todo | `export_routes.py` — `POST /api/export/import/finalize` (create entity folders, write wiki_config.json) |
| 5 | ⬜ Todo | `main.py` — register `export_router` under `/api/export` |

### Frontend (Gemini implements)

| Task | Status | Description |
| ---- | ------ | ----------- |
| 6 | ⬜ Todo | `tailwind.config.js` — add `darkMode: 'class'` |
| 7 | ⬜ Todo | `App.tsx` — theme state + `settingsOpen` + `useEffect` + render `SettingsDrawer` |
| 8 | ⬜ Todo | `Sidebar.tsx` — remove Reconfigure button, add gear icon + `onOpenSettings` prop |
| 9 | ⬜ Todo | `SettingsDrawer.tsx` — new slide-out component (theme segmented control, reconfigure button, export download) |
| 10 | ⬜ Todo | `SetupWizard.tsx` — add step-0 getting-started screen + import-from-backup flow |
| 11 | ⬜ Todo | Dark mode color mapping reference (no code — methodology task) |
| 12 | ⬜ Todo | Dark mode — `App.tsx` layout + inline chat UI |
| 13 | ⬜ Todo | Dark mode — `WikiView.tsx`, `SourcesView.tsx`, `ArchiveView.tsx`, `LintView.tsx` |

---

## Immediate Next Steps

1. **Execute Settings backend (Tasks 1–5)** — Claude implements `finalize_import` + `export_routes.py` + `main.py` registration on `setup-wizard` branch.
2. **Execute Settings frontend (Tasks 6–13)** — Gemini implements per `docs/superpowers/plans/2026-04-22-settings-implementation.md`.
3. Merge `setup-wizard` to `main` once Settings is complete and verified.
4. **Execute Entity Type Templates plan (Tasks 1–5)** — pure backend, `main` branch, per `docs/superpowers/plans/2026-04-24-entity-templates.md`.
5. Add Graph View (post-settings).
6. Monitor snapshot storage usage and add auto-pruning if needed.

---

## Entity Type Templates Progress (branch: `main`)

**Plan:** `docs/superpowers/plans/2026-04-24-entity-templates.md`
**Spec:** `docs/superpowers/specs/2026-04-24-entity-templates-design.md`

| Task | Status | Description |
| ---- | ------ | ----------- |
| 1 | ⬜ Todo | `schema_builder.py` — `generate_entity_template(folder_name, singular, fields, sections) -> str` |
| 2 | ⬜ Todo | `schema_builder.py` — `write_entity_templates(wiki_dir, entity_type_dicts)` |
| 3 | ⬜ Todo | `setup_wizard.py` `complete_setup()` — call `write_entity_templates()` after `_type.yaml` loop |
| 4 | ⬜ Todo | `wiki_manager.py` `list_pages()` — filter `_`-prefixed `.md` files from page list |
| 5 | ⬜ Todo | `wiki_manager.py` `create_new_page()` — read `_template.md` if present, fallback to stub |

---

## Known Issues / Blockers

*   **None**
