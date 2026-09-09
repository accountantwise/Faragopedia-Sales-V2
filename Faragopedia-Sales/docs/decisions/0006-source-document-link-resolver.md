# 0006 — Source-document links resolved through a closed lookup table

**Status:** Accepted, implemented and deployed 2026-09-07
**Numbering:** 0005 is taken by the Link View ADR on the unmerged `link-view` branch,
so this is 0006 to avoid a collision when those branches meet.
**Context:** the Farago callsheet migration, which imports one wiki page per production
job and needs each page to link back to that job's folder in external storage.

## Context

Imported job pages must link to the source folder — the imagery, treatments and other
paperwork the wiki does not carry. Two constraints make a plain URL unworkable:

1. **The archive is actively reorganised.** Folders get moved and renamed, and
   `00_Current Jobs` is a sibling of `01_Past Shoots` with jobs migrating across as they
   wrap. A stored path breaks silently. Resolving the 18 currently-imported jobs already
   turned up one whose path had changed since it was harvested.
2. **Storage is changing entirely.** Farago are migrating off Dropbox to Google Drive.
   Every stored Dropbox URL dies at cutover.

## Decision

Pages carry a **key**, never a live URL:

```markdown
[Open job folder](https://<wiki-host>/api/job/job-526)
```

`GET /api/job/{key}` looks the key up in `wiki/_meta/job-links.json` and 302s to the
current location. `PUT /api/job-links` replaces the whole table. The table is generated
externally, by `build_job_links.py` in the callsheet-migration repo, which keys it on the
**Dropbox folder ID** — IDs survive moves and renames — and re-derives the URL from the ID
on every run.

Consequences: a reorganisation needs one table refresh, and the migration to Drive needs
one script change. No page is rewritten and nothing is re-ingested.

### Mounted under `/api`, deliberately

The wiki frontend proxies `/api` same-origin (`VITE_API_BASE_URL=/api`), and the middleware
in `main.py` gates only requests arriving on the dedicated external API hostname. So a
person browsing the wiki follows these links with no additional Cloudflare Access policy,
while machine callers on the API hostname still need `X-Api-Key`.

Mounting the resolver on the API hostname instead — the obvious reading of ADR 0003 — would
have returned 403 to every human who clicked a link, because that hostname's Access policy
is service-token-only.

### Whole-table replacement, not per-key patching

The table is generated from the archive, so a partial update would let it drift from the
source of truth.

## Security

- **Closed lookup.** A destination is never accepted as a request parameter. That would be
  an open redirect, letting anyone send phishing links carrying Farago's own domain — and
  it is especially dangerous here because the legitimate flow genuinely ends on a Google or
  Dropbox sign-in screen, so people are trained to expect exactly what the attack imitates.
- **Unknown keys 404 and never redirect**, indistinguishable from a key that exists but is
  unmapped. Keys are job numbers and therefore guessable, so enumeration must reveal
  nothing.
- **Host allowlist at write time and again at redirect time**, so a corrupted or tampered
  table row cannot bounce somebody off-site. Matched on exact host or subdomain, so
  `dropbox.com.evil.test` fails.
- **Folder permissions remain the real access boundary.** Someone without access gets the
  storage provider's own screen, which is expected behaviour rather than a broken link.

⚠ `PUT /api/job-links` is ungated when reached same-origin, exactly like `PUT /api/pages`.
That is this application's existing trust boundary — anyone who can reach the wiki can
already edit it — rather than a widening of it. It is not, however, tighter than the wiki.

## Alternatives considered

- **Link straight at storage.** Simplest, and briefly shipped. Rejected: it breaks on any
  reorganisation, which is precisely what is expected here.
- **Resolve the folder ID to a URL at redirect time.** Robust, but it would put Dropbox
  credentials and SDK inside the wiki, coupling it to the platform being migrated away
  from. Keeping the resolver dependency-free pushes that work into the generating script,
  where the credentials already live.
- **Store the table as a wiki page.** Rejected: it would appear in the page list, the search
  index and the LLM's context, none of which is wanted for a machine-readable table.

## Tests

`backend/tests/test_job_links.py` — 24 tests, covering the allowlist (including suffix
attacks), redirect behaviour, unknown-key 404s, the ignored `?url=` parameter, refusal of a
tampered destination, whole-table replacement semantics and malformed payloads.
