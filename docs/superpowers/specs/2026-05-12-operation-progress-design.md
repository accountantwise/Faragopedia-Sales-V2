# Operation Progress Indicators — Design Spec

**Date:** 2026-05-12  
**Status:** Approved

## Problem

Users have no indication that long-running background operations (ingest, URL crawl) are working. The ingest button spinner disappears in ~100ms when the HTTP call returns, but the actual LLM work runs silently for 20–60 seconds. Lint is synchronous so the spinner is present, but feedback after completion is weak.

## Decisions

| Operation | Pattern |
|-----------|---------|
| Source ingest (single or bulk) | Grouped toast, bottom-right |
| URL crawl | Amber persistent toast, bottom-right |
| Run Lint | Inline, inside LintView |
| Apply Lint Fixes | Inline, inside LintView |

**Architecture:** Frontend-only. No new backend endpoints. Rides the existing 5-second `GET /sources/metadata` poll for ingest and crawl completion detection.

---

## Architecture

### New files

**`OperationToastContext.tsx`**  
React context + provider that holds all active operation state. Exposes:

```ts
startIngest(filenames: string[]): string        // returns operationId
completeIngest(filename: string): void
failIngest(filename: string, error?: string): void
startCrawl(urls: string[]): string              // returns operationId
completeCrawl(newFilenames: string[]): void
dismissOperation(id: string): void
```

`failCrawl` is not a public function — the context manages a 2-minute internal `setTimeout` per crawl operation and transitions to the soft-error state automatically when it fires.

State shape per operation:
```ts
type OperationStatus = 'running' | 'done' | 'error'

type OperationState =
  | { kind: 'ingest'; status: OperationStatus; filenames: string[]; completed: Set<string>; failed: Set<string> }
  | { kind: 'crawl';  status: OperationStatus; urls: string[];      newFiles?: string[] }
```

**`OperationToastStack.tsx`**  
Renders all active operations as a fixed bottom-right stack. Sits alongside (does not replace) the existing `ErrorToast`. Each toast maps to one `OperationState` entry.

### Modified files

**`App.tsx`** — two additions to the existing `GET /sources/metadata` poll loop:

1. **Ingest completion:** When a filename that was `ingested: false` flips to `true`, call `completeIngest(filename)`. Remove the existing `addToast('"X" ingested successfully.')` call — the grouped toast replaces it.

2. **Crawl completion:** Before each poll, snapshot the current filename set. When new filenames appear that weren't present before and a crawl operation is in-flight, call `completeCrawl(newFilenames)`. This is best-effort — if a manual file upload happens to complete concurrently it could resolve the crawl toast early. Acceptable given the backend provides no per-crawl completion signal.

**`SourcesView.tsx`** — call `startIngest([filename])` when the single-ingest button is clicked, and `startIngest(filenames)` when bulk-ingest is triggered, immediately after the HTTP call fires.

**`AddSourcesModal.tsx`** — call `startCrawl(urls)` after `POST /scrape-urls` succeeds, then close the modal.

**`LintView.tsx`** — improve existing inline states (described below).

---

## Operation Designs

### Ingest — Grouped Toast

**Lifecycle:**

1. **Running** — appears immediately when ingest is triggered. Blue left-border. Shows spinner + "Ingesting N files…" header, each filename listed as pending (⟳), progress bar at 0%.
2. **Partial** — as each 5s poll detects a file completing, it checks off (✓ green) and the progress bar advances proportionally.
3. **Done** — all files checked off. Border flips green. Header reads "N files ingested". Auto-dismisses after 4 seconds.
4. **Error** — any failure turns border red. Header reads "N of M ingested". Failed file shows "✕ filename — failed". Stays until manually dismissed.

**Single-file variant:** skips the list and progress bar — simpler two-line toast (spinner/checkmark + filename).

**New ingest triggered while toast is visible** adds filenames to the existing group rather than spawning a second toast — but only if the existing group is still in `running` status. A done or error group is left alone and a new toast is created.

---

### URL Crawl — Amber Toast

**Lifecycle:**

1. **Modal close:** Submit button text becomes "✓ Crawl started — closing", modal auto-closes after ~1.5s. Toast appears simultaneously.
2. **Crawling (persistent):** Amber left-border. "Crawling URLs…" with the submitted URLs listed beneath. "Sources will appear when ready." No timeout — crawls can take a while.
3. **Done:** When the metadata poll detects new filenames that weren't previously present, the toast flips green. "N sources added" with the new filenames listed. Auto-dismisses after 4s.

**Edge case — no files appear within 2 minutes:** Toast updates to soft-amber "Crawl may have failed — check the sources list." with a Dismiss button. Message is deliberately non-definitive since the backend gives no failure signal on `POST /scrape-urls`.

---

### Lint — Inline (inside LintView)

**Run Lint states:**

| State | Button | Below button |
|-------|--------|--------------|
| Idle | "⚡ Run Lint" (enabled) | — |
| Running | "⟳ Analysing wiki…" (disabled, greyed) | Blue hint: "⟳ This takes 20–40 seconds — reading all pages and running AI analysis" |
| Done | "⚡ Run Lint" (re-enabled) | Green banner: "✓ Analysis complete — 3 errors, 5 warnings, 2 suggestions" + findings list below |
| Error | "⚡ Run Lint" (re-enabled) | Red banner: "✕ Analysis failed — timeout. Try again or check backend logs." |

**Apply Fixes states:**

| State | Button | Below button |
|-------|--------|--------------|
| Idle | "Apply N selected" (green, enabled) | — |
| Applying | "⟳ Applying fixes…" (disabled, greyed) | Blue hint: "⟳ Writing changes to wiki — a snapshot is being created first" |
| Done | hidden (results replace it) | Green result block: "✓ N findings applied", file list (updated/created/skipped), "Snapshot saved · restore if needed" link |
| Error | "Apply N selected" (re-enabled) | Red banner: "✕ Fix failed — wiki was not modified. The pre-fix snapshot was not needed." |

The "restore if needed" link in the success result scrolls to the SnapshotsPanel.

---

## Out of Scope

- File upload (Files tab in AddSourcesModal) — the HTTP call is synchronous and fast; the existing button spinner is sufficient.
- Paste (Paste tab in AddSourcesModal) — same reasoning.
- Per-URL granular crawl status — would require a new backend endpoint; deferred.
- Real-time ingest progress via SSE — deferred.
