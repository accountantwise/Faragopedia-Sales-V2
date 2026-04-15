# Ingestion Race Condition Fix — Design Spec
**Date:** 2026-04-14
**Status:** Approved
**Bug reference:** `docs/flaws-and-bugs-report.md` §1.2

---

## Problem

`WikiManager.ingest_source` is fired as an `asyncio.create_task` from the upload
route. Multiple simultaneous uploads run their ingestion coroutines concurrently.
The file-writing section of `ingest_source` has no synchronization:

- `update_index()` reads the wiki directory and **overwrites** `index.md` entirely.
  Two concurrent calls both snapshot the directory at similar times, then both
  write — the last writer wins and the index may be missing pages written by the
  other coroutine.
- `_append_to_log()` opens `log.md` in append mode. Concurrent appends can
  interleave, corrupting log entries.
- Entity page updates (`open("a")`) can produce garbled content if two ingestions
  update the same entity simultaneously.

---

## Design

### Guiding principle

Only the file-write section needs serialization. The LLM inference (`chain.ainvoke`)
is safe to run concurrently — serializing it would make every user wait for every
other user's LLM call to finish before theirs starts, which is unacceptable under
multi-user load.

---

### Change 1: Add `_write_lock` to `WikiManager`

In `WikiManager.__init__`, add:

```python
self._write_lock = asyncio.Lock()
```

The lock is created once and lives for the lifetime of the server process.
`asyncio` must also be imported at the top of `wiki_manager.py`.

---

### Change 2: Restructure `ingest_source` into two phases

```
Phase 1 — Free (concurrent)
  - Read source file from disk
  - Call LLM via chain.ainvoke()          ← slow, safe to parallelize

Phase 2 — Locked (serialized)
  async with self._write_lock:
  - Write summary page (_write_page)
  - Update/create entity pages
  - Rebuild index (update_index)
  - Append to log (_append_to_log)
```

No other methods change. `update_index`, `_write_page`, and `_append_to_log`
remain as-is — they are only called from within the locked section.

---

### Error handling

- **Exception in Phase 1 (LLM failure):** Propagates before the lock is ever
  acquired. No partial writes. Lock remains available for other coroutines.
- **Exception in Phase 2 (disk error):** Python's `async with` releases the lock
  automatically on exit, even on exception. Subsequent ingestions are not
  deadlocked. The wiki may be partially written for the failed ingestion only.
- **Pre-existing issue:** `asyncio.create_task` in `routes.py` silently swallows
  exceptions from background tasks. This is out of scope for this fix.

---

### Testing

One new test in `backend/tests/test_wiki_manager.py`:

**`test_concurrent_ingestion_no_corruption`**
- Runs two `ingest_source` coroutines concurrently via `asyncio.gather`
- Mocks the LLM call so both complete at the same time (worst-case race)
- Asserts `index.md` is valid and contains entries for both ingested files
- Asserts `log.md` contains two distinct log entries

---

## Files changed

| File | Change |
|------|--------|
| `backend/agent/wiki_manager.py` | Add `import asyncio`; add `self._write_lock`; restructure `ingest_source` |
| `backend/tests/test_wiki_manager.py` | Add concurrent ingestion test |

---

## Out of scope

- Silent exception swallowing in `asyncio.create_task` (separate issue)
- Multi-process locking (single-process FastAPI server; `asyncio.Lock` is sufficient)
- Job status / progress tracking for uploads
