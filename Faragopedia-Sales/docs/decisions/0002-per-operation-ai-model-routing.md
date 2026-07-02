# ADR 0002: Per-Operation AI Model Routing

**Date:** 2026-05-19
**Status:** Accepted (partially superseded by ADR 0004 — `FIX_AI_*` was merged into `LINT_AI_*`, and ingest gained its own `INGEST_AI_*` override)

## Context

All LLM operations (ingest, query, lint, fix, tag suggestion) previously shared a single model configured via `AI_PROVIDER` and `AI_MODEL` env vars. This forced a one-size-fits-all model choice:

- Expensive models (Claude Sonnet) produced high-quality results but cost ~$0.50 per lint run.
- Cheaper models (Gemini 2.5 Flash) cost ~$0.03 per lint but produced weak findings.
- Linting and fix operations are pattern-matching/analysis tasks — they don't need the same reasoning depth as ingest or query.

Additionally, `PydanticOutputParser` was used for structured output across all operations. It injects a verbose JSON schema into the prompt and hopes the model outputs raw JSON. This broke with Gemini because:
1. Gemini wraps JSON in markdown code fences, which `PydanticOutputParser` cannot parse.
2. The verbose format instructions caused output to exceed Gemini Flash's 65,535-token ceiling, returning truncated JSON.

## Decision

### 1. Per-operation env var overrides

`_init_llm(operation=None)` now checks for `{OPERATION}_AI_PROVIDER` and `{OPERATION}_AI_MODEL` before falling back to the global `AI_PROVIDER` / `AI_MODEL`. Any operation name can be used; currently supported overrides are `LINT` and `FIX`.

Example `.env`:
```
AI_PROVIDER=openrouter
AI_MODEL=anthropic/claude-sonnet-4.6

LINT_AI_PROVIDER=openrouter
LINT_AI_MODEL=anthropic/claude-haiku-4.5

FIX_AI_PROVIDER=openrouter
FIX_AI_MODEL=anthropic/claude-haiku-4.5
```

### 2. Migrate all structured output to `with_structured_output()`

All three LLM operations (ingest, lint, fix) were migrated from `PydanticOutputParser` to LangChain's `with_structured_output()`. This uses the model's native function calling / tool use API rather than prompt-injected JSON schemas. The mechanism adapts automatically per provider (OpenAI function calling, Anthropic tool use, Gemini function declarations), making model swaps transparent.

`PydanticOutputParser` was removed entirely from `wiki_manager.py`.

## Consequences

- **Cost:** Lint/fix now run on Haiku 4.5 (~$0.05–0.10/run vs ~$0.50 for Sonnet). Ingest and query remain on Sonnet.
- **Quality:** Haiku produces acceptable lint findings — not as deep as Sonnet but significantly better than Gemini Flash.
- **Flexibility:** Any model can be swapped for any operation via env vars and a Portainer redeploy, with no code changes required.
- **Reliability:** `with_structured_output()` eliminates markdown-fence and truncation parse failures. Structured output now works correctly across all tested providers (Anthropic, Google via OpenRouter).
- **Extensibility:** Additional operations (e.g. `QUERY`, `INGEST`) can be given their own model overrides by adding the env vars and a `self._init_llm("query")` call — no structural changes needed.
