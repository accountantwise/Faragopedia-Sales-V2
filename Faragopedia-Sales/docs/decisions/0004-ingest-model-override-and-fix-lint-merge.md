# ADR 0004: Ingest Gets Its Own Model Override; Fix Merges Into Lint

**Date:** 2026-07-02
**Status:** Accepted
**Supersedes:** Parts of ADR 0002

## Context

ADR 0002 added per-operation env var overrides via `_init_llm(operation)`, but only
wired the override into the `lint` and `fix` call sites (`_run_lint_llm`,
`_run_fix_llm`). `WikiManager.__init__` built the shared `self.llm` — used for
ingest, query, and tag suggestion — via a bare `self._init_llm()` call, so ingest
had no dedicated override and silently fell back to the global `AI_PROVIDER`/
`AI_MODEL`. This looked like ingest was "hardcoded" and ignoring the per-operation
vars, when really no per-operation var for ingest existed yet (tracked as a TODO
in `docs/status.md`).

Separately, `fix` (applying lint-suggested edits) and `lint` (finding issues) had
independent env vars (`LINT_AI_*` / `FIX_AI_*`) even though in practice they were
always set to the same model — fix is a follow-on step of the lint workflow, not
an independently-tuned operation.

## Decision

1. **Ingest gets its own bucket.** `WikiManager.__init__` now builds a dedicated
   `self.ingest_llm = self._init_llm("ingest")`, and `_run_ingest_llm` uses it
   instead of `self.llm`. New env vars: `INGEST_AI_PROVIDER` / `INGEST_AI_MODEL`.
   `self.llm` (built with no prefix) remains the default for query and tag
   suggestion — i.e. "everything else."

2. **Fix merges into lint.** `_run_fix_llm` now calls `self._init_llm("lint")`
   instead of `self._init_llm("fix")`. `FIX_AI_PROVIDER` / `FIX_AI_MODEL` are
   removed; `LINT_AI_PROVIDER` / `LINT_AI_MODEL` now govern both operations.

There are now exactly three configurable buckets, each set via env vars passed
through `docker-compose.yml`:

| Bucket | Env vars | Covers |
| --- | --- | --- |
| Ingest | `INGEST_AI_PROVIDER` / `INGEST_AI_MODEL` | Source ingestion |
| Lint | `LINT_AI_PROVIDER` / `LINT_AI_MODEL` | Wiki linting + applying lint fixes |
| Default | `AI_PROVIDER` / `AI_MODEL` | Query, tag suggestion, and ingest/lint when unset |

## Consequences

- No behavior change for the current deployment: `INGEST_AI_*` is left unset in
  `.env`, so ingest continues on the global default (`anthropic/claude-sonnet-4.6`
  via OpenRouter), matching pre-change behavior. `LINT_AI_*` already matched
  `FIX_AI_*` (`anthropic/claude-haiku-4.5`), so merging them is a no-op today.
- Losing independent fix/lint tuning is an accepted tradeoff — if a future need
  arises to run fix on a different model than lint, reintroduce `FIX_AI_*` as its
  own bucket.
- `docker-compose.yml`, `.env.example`, and `docs/deployment.md` updated to match.
