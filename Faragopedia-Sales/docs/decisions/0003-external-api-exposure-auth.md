# ADR 0003: External API Exposure & Auth

**Date:** 2026-07-01
**Status:** Accepted

## Context

A Trigger.dev cloud automation (in the separate `FaragoProjects-Rocketreach-leads-research` project) needs to call `POST /api/paste` and `POST /api/sources/{filename}/ingest` on this backend whenever a CRM contact is marked "Meeting Booked." Trigger.dev runs off-network, so the backend (FastAPI on port 8300, internal-only, CORS fully open, no auth) needs to become reachable from the public internet without compromising the frontend's existing internal-network access pattern.

## Decision

Two layers of defense, both enabled:

1. **Cloudflare Access + Service Token (primary gate).** A new tunnel hostname `api.faragopedia.ai-wise.uk` routes to `http://backend:8300`, separate from the existing frontend tunnel route. A Cloudflare Access application on that hostname requires a Service Token (`CF-Access-Client-Id` / `CF-Access-Client-Secret` headers) on every request. This is dashboard/tunnel configuration only — no backend code involved, and it can't be bypassed by directly hitting the backend since the tunnel is the only public ingress.
2. **Backend API key middleware (defense in depth).** `external_api_key_middleware` in `backend/main.py` requires an `X-API-Key` header matching `FARAGOPEDIA_API_KEY` on any `/api/*` request that carries a `CF-Connecting-IP` header (Cloudflare injects this only on tunneled/public requests — it's absent on internal Docker-network calls, so the existing frontend-to-backend traffic is untouched). When `FARAGOPEDIA_API_KEY` is unset, the middleware is a no-op.

Both gates must pass for an external call to succeed, so a Cloudflare Access misconfiguration doesn't silently leave the API open.

## Consequences

- No frontend-facing behavior changes: internal calls never carry `CF-Connecting-IP`, so they skip the key check entirely; CORS remains `allow_origins=["*"]` (used only for the frontend's internal cross-port calls in dev).
- Revoking the automation's access no longer requires a code change: delete the Cloudflare Service Token. Rotating the backend-level key still requires updating `FARAGOPEDIA_API_KEY` and a Portainer redeploy.
- The calling project holds three secrets after setup: `FARAGOPEDIA_CF_CLIENT_ID`, `FARAGOPEDIA_CF_CLIENT_SECRET`, and `FARAGOPEDIA_API_KEY` (plus `FARAGOPEDIA_API_URL`).
- The Cloudflare Tunnel and Access Application are configured entirely in the Cloudflare Zero Trust dashboard — this repo has no `cloudflared` config file, so that setup isn't version-controlled here.
