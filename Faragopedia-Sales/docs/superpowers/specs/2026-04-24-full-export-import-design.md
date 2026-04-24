# Wiki Export & Import — Design Spec

**Date:** 2026-04-24  
**Status:** Approved

## Overview

Replace the existing partial bundle export (5 files) with a full-fidelity export/import system offering two modes:

- **Full** — complete migration of all wiki data, sources, archive, snapshots, and schema to a new server
- **Template** — schema and folder structure only, giving a clean starting point with the organization's entity types and company profile pre-configured but no actual data

Importing either bundle type bypasses the setup wizard entirely since `wiki_config.json` is present in both. Environment-specific settings (API keys, model config, port config) are excluded from all bundles.

---

## Bundle Contents by Mode

### Full Bundle (`faragopedia-full-YYYYMMDD-HHmmss.zip`)

```
manifest.json              ← version, type: "full", exported_at
schema/
  SCHEMA.md
  SCHEMA_TEMPLATE.md
  company_profile.md
  wiki_config.json
wiki/
  index.md
  log.md
  search-index.json
  {entity_type}/
    _type.yaml
    {page}.md
sources/
  .metadata.json           ← ingestion status (ingested, ingested_at, tags)
  {uploaded files}
archive/
  pages/
    {deleted pages}.md
  sources/
    {deleted sources}
snapshots/
  {snapshot-id}.zip
```

### Template Bundle (`faragopedia-template-YYYYMMDD-HHmmss.zip`)

```
manifest.json              ← version, type: "template", exported_at
schema/
  SCHEMA.md
  SCHEMA_TEMPLATE.md
  company_profile.md
  wiki_config.json
wiki/
  {entity_type}/
    _type.yaml             ← folder structure only, no page files
```

Template imports generate fresh empty `index.md` and `log.md` on the new server. No sources, archive, snapshots, or wiki page content is included.

### manifest.json

```json
{
  "version": 1,
  "type": "full",
  "exported_at": "2026-04-24T10:00:00Z",
  "app_version": "1.0.0"
}
```

The `type` field (`"full"` or `"template"`) tells the import handler which restoration path to take. The `version` field enables forward compatibility checks.

### Ingestion Status Preservation (Full only)

`sources/.metadata.json` maps each filename to its ingestion state:

```json
{
  "document.pdf": {
    "ingested": true,
    "ingested_at": "2026-04-20 14:32:01",
    "tags": ["client", "contract"]
  }
}
```

Including this file ensures sources show as "already ingested" on the new server — the user will not be prompted to re-ingest them. If the file is missing from an older bundle, sources default to `ingested: false` (safe fallback).

---

## Export

### Backend

**Two endpoints** (or a single endpoint with a `?type=full|template` query param — prefer two explicit endpoints for clarity):

- `GET /api/export/bundle/full` — Full export
- `GET /api/export/bundle/template` — Template export

Both:
1. Generate `manifest.json` in memory with correct `type`, timestamp, and app version
2. Stream a ZIP to the response (do not buffer in memory)
3. Set `Content-Disposition` with the appropriate filename

**Full** walks `schema/`, `wiki/`, `sources/`, `archive/`, `snapshots/` recursively.  
**Template** walks `schema/` fully and `wiki/` but only includes `_type.yaml` files (skips `.md` pages and `search-index.json`).

Excluded from all bundles: `.env`, API keys, port config.

### Frontend

In `SettingsDrawer.tsx`, add an **Export** section with two buttons:

- **Export Full** — "Download everything: all wiki pages, sources, archive, and snapshots. Use this to migrate to a new server."
- **Export Template** — "Download your schema and folder structure only, with no content. Use this to share your setup as a starting point for others."

Each button triggers a direct download (anchor click to the respective endpoint). No confirmation dialog needed (non-destructive).

---

## Import

### Backend

**Single endpoint:** `POST /api/export/import` (replaces existing two-step flow)

Steps:
1. Receive ZIP as multipart upload, stream to a temp file on disk
2. Open ZIP, validate `manifest.json` exists, `version` is compatible, `type` is `"full"` or `"template"`
3. Unpack all contents to a temporary staging directory
4. Validate staging has required structure (`schema/wiki_config.json` must be present)
5. Clear existing target directories:
   - **Full:** clear `wiki/`, `sources/`, `archive/`, `snapshots/`, `schema/`
   - **Template:** clear `wiki/`, `schema/` only (leave sources/archive/snapshots untouched)
6. Move staged contents to final locations
7. **Template only:** generate fresh `wiki/index.md` and `wiki/log.md`
8. Clean up temp staging directory
9. Reinitialize `WikiManager` with restored data
10. Rebuild search index via `_rebuild_search_index()`
11. Return `{"status": "ok", "type": "full"|"template"}`

The existing `POST /api/export/import/finalize` endpoint is deprecated and removed.

### Setup-Complete on Import

`wiki_config.json` presence on disk is what the setup check reads. Both bundle types include it, so the wizard is automatically bypassed after any import — no additional flag or state change required.

### Frontend

**Two entry points, same upload flow:**

1. **Settings Drawer** (`SettingsDrawer.tsx`) — Import section alongside Export. Single "Import" button opens a `.zip` file picker, uploads to `/api/export/import`, shows a spinner, then reloads the app on success. The bundle `type` is detected automatically on the backend.

2. **Setup Wizard** (`SetupWizard.tsx`) — "Already have a Faragopedia export? Import it instead." visible on the wizard's first screen. Same file picker + upload flow. On success, page reloads and the wizard is bypassed.

Both share the same upload helper function.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Missing `manifest.json` | Return 400; no files written |
| Incompatible `manifest.version` | Return 400 with version mismatch message; no files written |
| Unknown `manifest.type` | Return 400; no files written |
| Missing `schema/wiki_config.json` | Return 400; no files written |
| Failure during unpack/move | Clean up temp dir; existing data untouched; return 500 |
| Missing `sources/.metadata.json` (Full import) | Import proceeds; sources default to `ingested: false` |
| Large bundle | Streamed to disk, not held in memory; no size limit imposed |

---

## Files Changed

### Backend
- `api/export_routes.py` — Add `GET /bundle/full` and `GET /bundle/template`; replace two-step import with single atomic `POST /import`
- `wiki_manager.py` — Add `reinitialize()` method to reload state after import; add method to generate fresh `index.md` and `log.md` for template imports

### Frontend
- `src/components/SettingsDrawer.tsx` — Add Export (Full + Template buttons with descriptions) and Import sections
- `src/components/SetupWizard.tsx` — Add "Import existing export" entry point on first screen

### Removed
- `POST /api/export/import/finalize` — Removed; single-step import replaces the two-step flow
- `GET /api/export/bundle` — Replaced by `/bundle/full` and `/bundle/template`

---

## Out of Scope

- Merging two Faragopedia instances (import is a full replace)
- Incremental/differential exports
- Scheduled or automated exports
- Authentication / access control on export endpoints
- Environment config (`.env`, API keys, model settings) — user re-enters these on new server
