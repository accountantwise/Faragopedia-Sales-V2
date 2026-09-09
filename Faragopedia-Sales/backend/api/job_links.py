"""Stable source-document links, resolved through a closed lookup table.

Wiki pages carry a key, never a live storage URL:

    [Open job folder](https://<wiki-host>/api/job/job-526)

`GET /api/job/{key}` looks the key up and 302s to wherever that job's folder currently
lives. When files move — a Dropbox reorganisation, or the migration to Google Drive —
the table is refreshed and every link across the wiki re-points at once. No page is
rewritten and nothing is re-ingested.

Mounted under /api deliberately: the wiki frontend proxies /api same-origin, so a person
browsing the wiki can follow these links with no additional access policy, while the
dedicated external API hostname still requires X-Api-Key via the middleware in main.py.

Two safety rules, both from the design doc (§4 of the callsheet decisions):

1. CLOSED LOOKUP. The table is the sole authority on where a key points. A destination
   is never accepted as a request parameter — that would be an open redirect, letting
   anyone send phishing links carrying Farago's own domain. It is especially dangerous
   here because the legitimate flow genuinely does end on a Google or Dropbox sign-in
   screen, so people are trained to expect exactly what the attack imitates. An unknown
   key returns 404, never a redirect.

2. HOST ALLOWLIST AT REDIRECT TIME. Even a stored destination is checked against
   ALLOWED_HOSTS before redirecting, so a corrupted or tampered table row cannot bounce
   somebody off-site.

Access to the folder itself stays with Dropbox/Drive: someone without permission gets
that provider's own access screen, which is expected behaviour rather than a broken link.
"""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from api.routes import WM

job_links_router = APIRouter()

# Storage providers we will ever redirect to. Matched on exact host or subdomain, so
# "dropbox.com.evil.test" cannot pass.
ALLOWED_HOSTS = ("dropbox.com", "drive.google.com", "docs.google.com")

TABLE_FILENAME = "job-links.json"


def _table_path(wm) -> str:
    return os.path.join(wm.wiki_dir, "_meta", TABLE_FILENAME)


def load_table(wm) -> dict:
    path = _table_path(wm)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get("links", {}) if isinstance(data, dict) else {}


def host_is_allowed(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    if not host:
        return False
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS)


@job_links_router.get("/job/{key}")
async def resolve_job_link(wm: WM, key: str):
    """302 to the current location of a job's source folder."""
    entry = load_table(wm).get(key)
    if not entry:
        # Deliberately indistinguishable from a key that exists but is unmapped: the key
        # is a job number and therefore guessable, so enumeration should reveal nothing.
        raise HTTPException(
            status_code=404,
            detail=f"No source folder is registered for '{key}'.",
        )

    url = (entry.get("url") or "").strip() if isinstance(entry, dict) else str(entry).strip()
    if not url:
        raise HTTPException(status_code=404, detail=f"'{key}' has no destination recorded.")
    if not host_is_allowed(url):
        # A stored row pointing somewhere unexpected is a data-integrity problem, not a
        # routing one. Refuse rather than forward.
        raise HTTPException(
            status_code=502,
            detail="The recorded destination is not an approved storage host.",
        )
    return RedirectResponse(url=url, status_code=302)


@job_links_router.put("/job-links")
async def replace_job_links(wm: WM, payload: dict):
    """Replace the whole table.

    Whole-table replacement rather than per-key patching: the table is generated from the
    archive by the migration pipeline, so a partial update would let it drift out of step
    with the source of truth.

    Every destination is validated on the way in as well as on the way out, so a bad row
    is rejected at the point somebody can still see the error.

    Auth note: on the dedicated external API hostname this requires X-Api-Key via the
    middleware in main.py. Reached same-origin from the wiki it is open, exactly like
    PUT /api/pages — anyone who can reach the wiki can already edit it, and this endpoint
    is inside that same trust boundary rather than widening it.
    """
    links = payload.get("links")
    if not isinstance(links, dict):
        raise HTTPException(status_code=422, detail="links must be an object of key -> entry")

    cleaned: dict[str, dict] = {}
    for key, entry in links.items():
        if not isinstance(entry, dict):
            raise HTTPException(status_code=422, detail=f"'{key}': entry must be an object")
        url = (entry.get("url") or "").strip()
        if not url:
            raise HTTPException(status_code=422, detail=f"'{key}': missing url")
        if not host_is_allowed(url):
            raise HTTPException(
                status_code=422,
                detail=f"'{key}': url host is not an approved storage host",
            )
        cleaned[key] = entry

    path = _table_path(wm)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"links": cleaned}, f, indent=2, sort_keys=True)
    return {"message": "Job links replaced", "count": len(cleaned)}


@job_links_router.get("/job-links")
async def list_job_links(wm: WM):
    """Read the table back, for checking what a refresh actually wrote."""
    table = load_table(wm)
    return {"count": len(table), "links": table}
