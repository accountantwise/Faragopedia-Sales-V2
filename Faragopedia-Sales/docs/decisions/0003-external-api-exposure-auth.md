# ADR 0003: External API Exposure & Auth

**Date:** 2026-07-01
**Status:** Accepted

## Context

A Trigger.dev cloud automation (in the separate `FaragoProjects-Rocketreach-leads-research` project) needs to call `POST /api/paste` and `POST /api/sources/{filename}/ingest` on this backend whenever a CRM contact is marked "Meeting Booked." Trigger.dev runs off-network, so the backend (FastAPI on port 8300, internal-only, CORS fully open, no auth) needs to become reachable from the public internet without compromising the frontend's existing internal-network access pattern.

## Decision

Two layers of defense, both enabled:

1. **Cloudflare Access + Service Token (primary gate).** A new tunnel hostname `faragopedia-api.ai-wise.uk` routes to `http://backend:8300`, separate from the existing frontend tunnel route. A Cloudflare Access application on that hostname requires a Service Token (`CF-Access-Client-Id` / `CF-Access-Client-Secret` headers) on every request, via a **Service Auth** policy action (not "Allow" + Service Token selector — Service Auth is Cloudflare's purpose-built action for pure machine-to-machine calls with no IdP login). This is dashboard/tunnel configuration only — no backend code involved, and it can't be bypassed by directly hitting the backend since the tunnel is the only public ingress.

   Originally planned as `api.faragopedia.ai-wise.uk`, but that's a second-level subdomain not covered by Cloudflare's default Universal SSL wildcard (`*.ai-wise.uk`, which only covers one level of nesting) — HTTPS reset at the TLS handshake while HTTP worked unauthenticated, a live exposure until caught. Renamed to `faragopedia-api.ai-wise.uk` (single-level, covered by the existing wildcard) rather than paying for Advanced Certificate Manager.
2. **Backend API key middleware (defense in depth).** `external_api_key_middleware` in `backend/main.py` requires an `X-API-Key` header matching `FARAGOPEDIA_API_KEY` on any `/api/*` request whose `Host` header matches `FARAGOPEDIA_API_HOSTNAME` (the dedicated tunnel hostname, `faragopedia-api.ai-wise.uk`). When either `FARAGOPEDIA_API_KEY` or `FARAGOPEDIA_API_HOSTNAME` is unset, the middleware is a no-op.

Both gates must pass for an external call to succeed, so a Cloudflare Access misconfiguration doesn't silently leave the API open.

## Consequences

- No frontend-facing behavior changes: requests to the main frontend hostname skip the key check entirely; CORS remains `allow_origins=["*"]` (used only for the frontend's internal cross-port calls in dev).
- Revoking the automation's access no longer requires a code change: delete the Cloudflare Service Token. Rotating the backend-level key still requires updating `FARAGOPEDIA_API_KEY` and a Portainer redeploy.
- The calling project holds three secrets after setup: `FARAGOPEDIA_CF_CLIENT_ID`, `FARAGOPEDIA_CF_CLIENT_SECRET`, and `FARAGOPEDIA_API_KEY` (plus `FARAGOPEDIA_API_URL`).
- The Cloudflare Tunnel and Access Application are configured entirely in the Cloudflare Zero Trust dashboard — this repo has no `cloudflared` config file, so that setup isn't version-controlled here.

## Incident: outage caused by the original CF-Connecting-IP check (2026-07-01)

The middleware originally gated on "does this request carry a `CF-Connecting-IP` header" rather than hostname, on the assumption that header is only present on the external automation's calls and absent on "internal" frontend traffic. That assumption was wrong: Cloudflare injects `CF-Connecting-IP` on **every** request that transits a Cloudflare Tunnel, including normal browser visits to the main site (`faragopedia.ai-wise.uk`), since the whole site — not just the new API route — is Cloudflare-tunneled. The first redeploy after adding the middleware 401'd every real user request; the wiki UI showed "Failed to fetch pages" / empty page lists, which looked like lost data/volumes but was actually every `/api/*` call being rejected.

Fixed by gating on `request.headers.get("host")` matching `FARAGOPEDIA_API_HOSTNAME` instead — the dedicated tunnel hostname is the actual distinguishing signal between the automation and real users, not header presence. Regression test: `test_frontend_request_with_cf_header_is_not_gated` in `backend/tests/test_external_api_key_middleware.py`.
