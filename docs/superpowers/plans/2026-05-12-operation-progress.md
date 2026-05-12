# Operation Progress Indicators — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give users visible feedback that ingest, URL crawl, and lint operations are running — and show a clear success or error result when each finishes.

**Architecture:** Frontend-only. A new `OperationToastContext` holds all in-flight operation state. The existing 5-second `GET /sources/metadata` poll in `App.tsx` is augmented to call `completeIngest` and `completeCrawl` when it detects completion. Lint is synchronous so its inline states are already wired — we add the missing hint text and success banner. No backend changes.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, lucide-react. No test runner — verify each task by running `npm run dev` in `Faragopedia-Sales/frontend/`.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/OperationToastContext.tsx` | **Create** | Operation state, actions, auto-dismiss timers |
| `src/components/OperationToastStack.tsx` | **Create** | Renders ingest + crawl toasts at bottom-right |
| `src/main.tsx` | **Modify** | Wrap `<App>` with `<OperationToastProvider>` |
| `src/App.tsx` | **Modify** | Use context in metadata poll; remove old toast system; render `<OperationToastStack>` |
| `src/components/SourcesView.tsx` | **Modify** | Call `startIngest` when ingest is triggered |
| `src/components/AddSourcesModal.tsx` | **Modify** | Call `startCrawl` after URL crawl starts |
| `src/components/LintView.tsx` | **Modify** | Add time-estimate hint, analysis-complete banner, fix hint, snapshot link |

---

## Task 1: Create `OperationToastContext.tsx`

**Files:**
- Create: `Faragopedia-Sales/frontend/src/OperationToastContext.tsx`

- [ ] **Step 1: Create the file with types, context, provider, and hook**

```tsx
import React, { createContext, useContext, useState, useRef, useCallback, useEffect } from 'react';

export type OperationStatus = 'running' | 'done' | 'error';

export type IngestOperation = {
  id: string;
  kind: 'ingest';
  status: OperationStatus;
  filenames: string[];
  completed: Set<string>;
  failed: Set<string>;
};

export type CrawlOperation = {
  id: string;
  kind: 'crawl';
  status: OperationStatus;
  urls: string[];
  newFiles?: string[];
};

export type Operation = IngestOperation | CrawlOperation;

type ContextValue = {
  operations: Operation[];
  startIngest: (filenames: string[]) => void;
  completeIngest: (filename: string) => void;
  failIngest: (filename: string) => void;
  startCrawl: (urls: string[]) => void;
  completeCrawl: (newFilenames: string[]) => void;
  dismissOperation: (id: string) => void;
};

const OperationToastContext = createContext<ContextValue | null>(null);

export const useOperationToasts = (): ContextValue => {
  const ctx = useContext(OperationToastContext);
  if (!ctx) throw new Error('useOperationToasts must be used within OperationToastProvider');
  return ctx;
};

export const OperationToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [operations, setOperations] = useState<Operation[]>([]);
  const crawlTimerRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const dismissTimerRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // Auto-dismiss 'done' operations after 4 seconds
  useEffect(() => {
    operations.forEach(op => {
      if (op.status === 'done' && !dismissTimerRef.current[op.id]) {
        dismissTimerRef.current[op.id] = setTimeout(() => {
          setOperations(prev => prev.filter(o => o.id !== op.id));
          delete dismissTimerRef.current[op.id];
        }, 4000);
      }
    });
  }, [operations]);

  const startIngest = useCallback((filenames: string[]) => {
    setOperations(prev => {
      // Merge into existing running ingest group if one exists
      const existingIdx = prev.findIndex(op => op.kind === 'ingest' && op.status === 'running');
      if (existingIdx >= 0) {
        return prev.map((op, i) => {
          if (i !== existingIdx) return op;
          const ingest = op as IngestOperation;
          return { ...ingest, filenames: [...ingest.filenames, ...filenames] };
        });
      }
      const op: IngestOperation = {
        id: `ingest-${Date.now()}`,
        kind: 'ingest',
        status: 'running',
        filenames,
        completed: new Set(),
        failed: new Set(),
      };
      return [...prev, op];
    });
  }, []);

  const completeIngest = useCallback((filename: string) => {
    setOperations(prev => prev.map(op => {
      if (op.kind !== 'ingest' || op.status !== 'running') return op;
      const ingest = op as IngestOperation;
      const completed = new Set(ingest.completed);
      completed.add(filename);
      const allDone = ingest.filenames.every(f => completed.has(f) || ingest.failed.has(f));
      const status: OperationStatus = allDone
        ? (ingest.failed.size > 0 ? 'error' : 'done')
        : 'running';
      return { ...ingest, completed, status };
    }));
  }, []);

  const failIngest = useCallback((filename: string) => {
    setOperations(prev => prev.map(op => {
      if (op.kind !== 'ingest' || op.status !== 'running') return op;
      const ingest = op as IngestOperation;
      const failed = new Set(ingest.failed);
      failed.add(filename);
      const allDone = ingest.filenames.every(f => ingest.completed.has(f) || failed.has(f));
      return { ...ingest, failed, status: allDone ? 'error' : 'running' };
    }));
  }, []);

  const startCrawl = useCallback((urls: string[]) => {
    const id = `crawl-${Date.now()}`;
    const op: CrawlOperation = { id, kind: 'crawl', status: 'running', urls };
    setOperations(prev => [...prev, op]);
    // Soft timeout after 2 minutes
    crawlTimerRef.current[id] = setTimeout(() => {
      setOperations(prev => prev.map(o =>
        o.id === id && o.status === 'running' ? { ...o, status: 'error' as OperationStatus } : o
      ));
      delete crawlTimerRef.current[id];
    }, 120_000);
  }, []);

  const completeCrawl = useCallback((newFilenames: string[]) => {
    setOperations(prev => {
      const crawl = prev.find(op => op.kind === 'crawl' && op.status === 'running') as CrawlOperation | undefined;
      if (!crawl) return prev;
      if (crawlTimerRef.current[crawl.id]) {
        clearTimeout(crawlTimerRef.current[crawl.id]);
        delete crawlTimerRef.current[crawl.id];
      }
      return prev.map(op =>
        op.id === crawl.id
          ? { ...op, status: 'done' as OperationStatus, newFiles: newFilenames } as CrawlOperation
          : op
      );
    });
  }, []);

  const dismissOperation = useCallback((id: string) => {
    if (dismissTimerRef.current[id]) {
      clearTimeout(dismissTimerRef.current[id]);
      delete dismissTimerRef.current[id];
    }
    setOperations(prev => prev.filter(op => op.id !== id));
  }, []);

  return (
    <OperationToastContext.Provider value={{
      operations, startIngest, completeIngest, failIngest,
      startCrawl, completeCrawl, dismissOperation,
    }}>
      {children}
    </OperationToastContext.Provider>
  );
};
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd Faragopedia-Sales/frontend && npx tsc --noEmit`
Expected: no errors from the new file (ignore pre-existing errors if any).

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/OperationToastContext.tsx
git commit -m "feat: add OperationToastContext for ingest and crawl progress state"
```

---

## Task 2: Create `OperationToastStack.tsx`

**Files:**
- Create: `Faragopedia-Sales/frontend/src/components/OperationToastStack.tsx`

- [ ] **Step 1: Create the component**

```tsx
import React from 'react';
import { Loader2, CheckCircle2, XCircle, X } from 'lucide-react';
import { useOperationToasts, IngestOperation, CrawlOperation } from '../OperationToastContext';

const BASE =
  'bg-gray-900/95 backdrop-blur text-white text-sm rounded-2xl shadow-2xl border border-white/10 ' +
  'animate-in slide-in-from-right-full fade-in duration-300 overflow-hidden';

// ── Ingest toast ─────────────────────────────────────────────────────────────

const IngestToast: React.FC<{ op: IngestOperation; onDismiss: () => void }> = ({ op, onDismiss }) => {
  const { filenames, completed, failed, status } = op;
  const isGrouped = filenames.length > 1;
  const doneCount = completed.size + failed.size;
  const progress = filenames.length > 0 ? Math.round((doneCount / filenames.length) * 100) : 0;

  const borderColor =
    status === 'done' ? 'border-l-4 border-l-green-400' :
    status === 'error' ? 'border-l-4 border-l-red-400' :
    'border-l-4 border-l-blue-400';

  const headerText =
    status === 'done' ? (filenames.length === 1 ? 'Ingested' : `${filenames.length} files ingested`) :
    status === 'error' ? `${completed.size} of ${filenames.length} ingested` :
    filenames.length === 1 ? 'Ingesting…' : `Ingesting ${filenames.length} files…`;

  const headerColor =
    status === 'done' ? 'text-green-400' :
    status === 'error' ? 'text-red-400' :
    'text-white';

  const StatusIcon =
    status === 'done' ? <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" /> :
    status === 'error' ? <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" /> :
    <Loader2 className="w-4 h-4 animate-spin text-blue-400 flex-shrink-0" />;

  if (!isGrouped) {
    // Single-file: compact two-line layout
    return (
      <div className={`${BASE} ${borderColor} px-4 py-3 min-w-[200px] max-w-[260px]`}>
        <div className="flex items-center gap-3">
          {StatusIcon}
          <div className="flex-1 min-w-0">
            <div className={`font-semibold text-sm ${headerColor}`}>{headerText}</div>
            <div className="text-xs text-gray-400 truncate">{filenames[0]}</div>
          </div>
          {status !== 'running' && (
            <button onClick={onDismiss} className="text-gray-500 hover:text-gray-300 ml-1">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    );
  }

  // Grouped layout
  return (
    <div className={`${BASE} ${borderColor} px-4 py-3 min-w-[240px] max-w-[280px]`}>
      <div className="flex items-center gap-2 mb-2">
        {StatusIcon}
        <span className={`font-semibold text-sm flex-1 ${headerColor}`}>{headerText}</span>
        {status !== 'running' && (
          <button onClick={onDismiss} className="text-gray-500 hover:text-gray-300">
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      <div className="space-y-1 mb-2">
        {filenames.map(f => {
          const isDone = completed.has(f);
          const isFailed = failed.has(f);
          return (
            <div key={f} className="flex items-center gap-2 text-xs">
              {isDone
                ? <CheckCircle2 className="w-3 h-3 text-green-400 flex-shrink-0" />
                : isFailed
                  ? <XCircle className="w-3 h-3 text-red-400 flex-shrink-0" />
                  : <Loader2 className="w-3 h-3 animate-spin text-gray-500 flex-shrink-0" />
              }
              <span className={`truncate ${isDone ? 'text-green-300' : isFailed ? 'text-red-300' : 'text-gray-400'}`}>
                {f}
              </span>
            </div>
          );
        })}
      </div>
      <div className="bg-gray-700 rounded-full h-1">
        <div
          className={`h-1 rounded-full transition-all duration-500 ${status === 'error' ? 'bg-red-400' : status === 'done' ? 'bg-green-400' : 'bg-blue-400'}`}
          style={{ width: `${progress}%` }}
        />
      </div>
      {status === 'error' && (
        <button
          onClick={onDismiss}
          className="mt-2 text-xs bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded text-gray-300 transition-colors"
        >
          Dismiss
        </button>
      )}
    </div>
  );
};

// ── Crawl toast ───────────────────────────────────────────────────────────────

const CrawlToast: React.FC<{ op: CrawlOperation; onDismiss: () => void }> = ({ op, onDismiss }) => {
  const { urls, status, newFiles } = op;

  const borderColor =
    status === 'done' ? 'border-l-4 border-l-green-400' : 'border-l-4 border-l-amber-400';

  const headerText =
    status === 'done'
      ? `${newFiles?.length ?? 0} source${(newFiles?.length ?? 0) !== 1 ? 's' : ''} added`
      : 'Crawling URLs…';

  const headerColor = status === 'done' ? 'text-green-400' : 'text-amber-300';

  const StatusIcon =
    status === 'done'
      ? <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
      : <Loader2 className="w-4 h-4 animate-spin text-amber-400 flex-shrink-0" />;

  return (
    <div className={`${BASE} ${borderColor} px-4 py-3 min-w-[220px] max-w-[280px]`}>
      <div className="flex items-center gap-2 mb-1">
        {StatusIcon}
        <span className={`font-semibold text-sm flex-1 ${headerColor}`}>{headerText}</span>
        {status !== 'running' && (
          <button onClick={onDismiss} className="text-gray-500 hover:text-gray-300">
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      {status === 'running' && (
        <>
          {urls.slice(0, 3).map((url, i) => (
            <div key={i} className="text-xs text-gray-400 truncate">{url}</div>
          ))}
          {urls.length > 3 && (
            <div className="text-xs text-gray-500">+{urls.length - 3} more</div>
          )}
          <div className="text-xs text-gray-500 mt-1">Sources will appear when ready</div>
        </>
      )}
      {status === 'done' && newFiles && newFiles.length > 0 && (
        <div className="space-y-0.5 mt-1">
          {newFiles.slice(0, 3).map(f => (
            <div key={f} className="text-xs text-gray-400 truncate">{f}</div>
          ))}
          {newFiles.length > 3 && (
            <div className="text-xs text-gray-500">+{newFiles.length - 3} more</div>
          )}
        </div>
      )}
      {status === 'error' && (
        <>
          <div className="text-xs text-amber-400/80 mt-1">
            Crawl may have failed — check sources list
          </div>
          <button
            onClick={onDismiss}
            className="mt-2 text-xs bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded text-gray-300 transition-colors"
          >
            Dismiss
          </button>
        </>
      )}
    </div>
  );
};

// ── Stack ─────────────────────────────────────────────────────────────────────

const OperationToastStack: React.FC = () => {
  const { operations, dismissOperation } = useOperationToasts();
  if (operations.length === 0) return null;
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 pointer-events-auto">
      {operations.map(op =>
        op.kind === 'ingest'
          ? <IngestToast key={op.id} op={op as IngestOperation} onDismiss={() => dismissOperation(op.id)} />
          : <CrawlToast key={op.id} op={op as CrawlOperation} onDismiss={() => dismissOperation(op.id)} />
      )}
    </div>
  );
};

export default OperationToastStack;
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd Faragopedia-Sales/frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/OperationToastStack.tsx
git commit -m "feat: add OperationToastStack component"
```

---

## Task 3: Wire Context into `App.tsx` and `main.tsx`

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/main.tsx`
- Modify: `Faragopedia-Sales/frontend/src/App.tsx`

- [ ] **Step 1: Wrap `<App>` with the provider in `main.tsx`**

Replace the entire file with:

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { OperationToastProvider } from './OperationToastContext'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <OperationToastProvider>
      <App />
    </OperationToastProvider>
  </React.StrictMode>,
)
```

- [ ] **Step 2: Update imports in `App.tsx`**

At the top of `App.tsx`, add two imports and remove the `Loader2` unused import if needed:

```tsx
// Add after existing imports:
import { useOperationToasts } from './OperationToastContext';
import OperationToastStack from './components/OperationToastStack';
```

- [ ] **Step 3: Add the context hook and filename tracking ref in `App.tsx`**

Inside the `App` component function, add these lines immediately after the existing `prevMetadataRef` declaration (line 25):

```tsx
const { completeIngest, completeCrawl } = useOperationToasts();
const prevFilenamesRef = useRef<Set<string>>(new Set());
```

- [ ] **Step 4: Update the metadata poll in `App.tsx` to call context actions**

Replace the metadata poll `useEffect` (lines 103–145) with:

```tsx
useEffect(() => {
  const fetchMetadata = async () => {
    try {
      const res = await fetch(`${API_BASE}/sources/metadata`);
      if (!res.ok) return;
      const data: Record<string, { ingested: boolean; ingested_at: string | null; tags: string[] }> = await res.json();

      const prev = prevMetadataRef.current;
      const prevFilenames = prevFilenamesRef.current;
      const currentFilenames = new Set(Object.keys(data));

      // Detect ingest completions
      Object.entries(data).forEach(([filename, meta]) => {
        if (meta.ingested && prev[filename] && !prev[filename].ingested) {
          completeIngest(filename);
        }
      });

      // Detect crawl completions — completeCrawl is a no-op when no crawl is in-flight
      const newFilenames = Array.from(currentFilenames).filter(f => !prevFilenames.has(f));
      if (newFilenames.length > 0) {
        completeCrawl(newFilenames);
      }

      prevMetadataRef.current = data;
      prevFilenamesRef.current = currentFilenames;
      setSourcesMetadata(data);
    } catch (err) {
      console.error('Failed to fetch metadata', err);
    }

    // Also refresh page read/unread state
    try {
      const pagesRes = await fetch(`${API_BASE}/pages/metadata`);
      if (pagesRes.ok) {
        const pagesData: Record<string, { read: boolean; read_at: string | null }> = await pagesRes.json();
        setPagesMetadata(prev => {
          const merged = { ...prev };
          for (const [k, v] of Object.entries(pagesData)) {
            if (merged[k]?.read !== true) merged[k] = v;
          }
          return merged;
        });
      }
    } catch {
      // non-fatal
    }
  };

  fetchMetadata();
  const interval = setInterval(fetchMetadata, 5000);
  return () => clearInterval(interval);
}, [addToast, completeIngest, completeCrawl, operations]);
```

- [ ] **Step 5: Remove the old toast system and render `OperationToastStack`**

a) Delete the `addToast` callback (lines 97–101):
```tsx
// DELETE these lines:
const addToast = useCallback((message: string) => {
  const id = Date.now();
  setToasts(prev => [...prev, { id, message }]);
  setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
}, []);
```

b) Delete the `toasts` state declaration (line 40):
```tsx
// DELETE this line:
const [toasts, setToasts] = useState<{ id: number; message: string }[]>([]);
```

c) In the JSX return, replace `<ToastContainer toasts={toasts} />` with `<OperationToastStack />`.

d) Delete the `ToastContainer` component at the bottom of the file (lines 509–522):
```tsx
// DELETE from here:
{/* Global ingestion toasts component styled for premium feel */}
const ToastContainer: React.FC<...> = ...
// to the closing brace.
```

e) Remove `addToast` from the `useEffect` dependency array and clean up the import of `useState` if `toasts` was the only `useState` usage removed (it wasn't — keep `useState`).

Final dep array for the metadata poll `useEffect`:
```tsx
}, [completeIngest, completeCrawl]);
```

- [ ] **Step 6: Start dev server and verify basic rendering**

Run: `cd Faragopedia-Sales/frontend && npm run dev`
Open the app in browser. Expected: app loads normally, no console errors, Sources view works.

- [ ] **Step 7: Commit**

```bash
git add Faragopedia-Sales/frontend/src/main.tsx Faragopedia-Sales/frontend/src/App.tsx
git commit -m "feat: wire OperationToastContext into App metadata poll"
```

---

## Task 4: Wire `startIngest` in `SourcesView.tsx`

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/SourcesView.tsx`

- [ ] **Step 1: Import the context hook**

At the top of `SourcesView.tsx`, add:

```tsx
import { useOperationToasts } from '../OperationToastContext';
```

- [ ] **Step 2: Destructure `startIngest` and `failIngest` inside the component**

Inside the `SourcesView` component function, add near the top with other state declarations:

```tsx
const { startIngest, failIngest } = useOperationToasts();
```

- [ ] **Step 3: Update `handleIngest` to call `startIngest`**

Replace the existing `handleIngest` function:

```tsx
const handleIngest = async () => {
  if (!selectedSource) return;
  try {
    setIngesting(selectedSource);
    startIngest([selectedSource]);
    const response = await fetch(`${API_BASE}/sources/${encodeURIComponent(selectedSource)}/ingest`, {
      method: 'POST'
    });
    if (!response.ok) {
      failIngest(selectedSource);
      throw new Error('Failed to start ingestion');
    }
    // Completion detected by App.tsx metadata poll
  } catch (err: any) {
    setError(err.message);
  } finally {
    setIngesting(null);
  }
};
```

- [ ] **Step 4: Update `handleBulkIngest` to call `startIngest`**

Replace the existing `handleBulkIngest` function:

```tsx
const handleBulkIngest = async () => {
  const filenames = Array.from(selectedItems);
  try {
    startIngest(filenames);
    await fetch(`${API_BASE}/sources/bulk-ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filenames }),
    });
    clearSelection();
  } catch {
    filenames.forEach(f => failIngest(f));
    setError('Failed to start bulk ingestion');
  }
};
```

- [ ] **Step 5: Verify in browser**

With dev server running: go to Sources view, click Ingest on a source. Expected: a blue "Ingesting…" toast appears bottom-right immediately and persists. When ingestion completes (up to 5s after backend finishes), toast turns green and auto-dismisses after 4s.

- [ ] **Step 6: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/SourcesView.tsx
git commit -m "feat: trigger ingest toast from SourcesView"
```

---

## Task 5: Wire `startCrawl` in `AddSourcesModal.tsx`

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/AddSourcesModal.tsx`

- [ ] **Step 1: Import the context hook**

At the top of `AddSourcesModal.tsx`, add:

```tsx
import { useOperationToasts } from '../OperationToastContext';
```

- [ ] **Step 2: Destructure `startCrawl` inside the component**

Inside `AddSourcesModal`, add near the other state declarations:

```tsx
const { startCrawl } = useOperationToasts();
```

- [ ] **Step 3: Update `handleUrlSubmit` to call `startCrawl` and auto-close**

Replace the existing `handleUrlSubmit`:

```tsx
const handleUrlSubmit = async () => {
  const urls = urlText.split('\n').map(u => u.trim()).filter(Boolean);
  if (urls.length === 0) return;
  setCrawling(true);
  setError(null);
  try {
    const res = await fetch(`${API_BASE}/scrape-urls`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls }),
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Failed to start crawl');
    }
    startCrawl(urls);
    // Brief confirmation before closing
    setTimeout(onClose, 1500);
  } catch (err: any) {
    setError(err.message);
    setCrawling(false);
  }
};
```

- [ ] **Step 4: Update the URL submit button label to confirm crawl start**

Find the URL submit button JSX and change the `crawling` label from `"Starting..."` to show confirmation after the fetch succeeds. Since `crawling` stays true until close (we don't call `setCrawling(false)` on success), update the button text:

```tsx
{crawling
  ? <><Loader2 className="w-4 h-4 animate-spin" /> Crawl started — closing</>
  : 'Start Crawl'
}
```

- [ ] **Step 5: Verify in browser**

Go to Add Sources → URL tab. Enter a URL and submit. Expected: button shows "Crawl started — closing", modal closes after ~1.5s, an amber "Crawling URLs…" toast appears bottom-right and persists. When new sources appear in the metadata poll, toast turns green and auto-dismisses.

- [ ] **Step 6: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/AddSourcesModal.tsx
git commit -m "feat: trigger crawl toast from AddSourcesModal"
```

---

## Task 6: Improve `LintView.tsx` Inline States

**Files:**
- Modify: `Faragopedia-Sales/frontend/src/components/LintView.tsx`

- [ ] **Step 1: Add `useRef` import and snapshot panel ref**

In `LintView.tsx`, add `useRef` to the React import:

```tsx
import React, { useState, useRef } from 'react';
```

Add `CheckCircle2` to the lucide-react import:

```tsx
import { Activity, Loader2, AlertCircle, AlertTriangle, Lightbulb, CheckSquare, Square, Wrench, CheckCircle2 } from 'lucide-react';
```

Inside the component, add the ref after the existing state declarations:

```tsx
const snapshotsPanelRef = useRef<HTMLDivElement>(null);
```

- [ ] **Step 2: Add time-estimate hint below the Run Lint button**

Find the `{loading && (` block (lines 140–150). Replace it with:

```tsx
{loading && (
  <div className="mt-4 space-y-1">
    <div className="flex items-center gap-2 text-sm text-blue-500 dark:text-blue-400">
      <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />
      <span>This takes 20–40 seconds — reading all pages and running AI analysis</span>
    </div>
    <div className="space-y-3 max-w-xl animate-pulse mt-4">
      <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded-full w-3/4"></div>
      <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded-full w-full"></div>
      <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded-full w-5/6"></div>
    </div>
  </div>
)}
```

- [ ] **Step 3: Add "Analysis complete" success banner**

Find the `{report && (` block (line 179). Inside it, immediately after the opening `<div className="space-y-6">`, add a success banner:

```tsx
{report && (
  <div className="space-y-6">
    <div className="flex items-center gap-3 p-4 bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-900/30 rounded-xl">
      <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0" />
      <p className="text-green-800 dark:text-green-300 font-semibold">{report.summary}</p>
    </div>

    {/* rest of existing report JSX — keep unchanged from here */}
    <div className="flex items-center justify-between">
      ...
```

- [ ] **Step 4: Add "Applying fixes" hint below the Apply button**

Find the sticky Apply button block (lines 249–263). Replace it with:

```tsx
{selected.size > 0 && (
  <div className="sticky bottom-4 flex flex-col gap-2">
    <button
      onClick={applySelected}
      disabled={applying}
      className="flex items-center px-6 py-3 bg-green-600 text-white rounded-xl font-semibold hover:bg-green-700 transition-colors disabled:opacity-50 shadow-lg"
    >
      {applying
        ? <Loader2 className="w-5 h-5 animate-spin mr-2" />
        : <Wrench className="w-5 h-5 mr-2" />
      }
      {applying ? 'Applying fixes…' : `Apply ${selected.size} selected`}
    </button>
    {applying && (
      <div className="flex items-center gap-2 text-sm text-blue-500 dark:text-blue-400 px-1">
        <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />
        <span>Writing changes to wiki — a snapshot is being created first</span>
      </div>
    )}
  </div>
)}
```

- [ ] **Step 5: Add snapshot link to the fix report display and wrap SnapshotsPanel**

Find the `{fixReport && (` block (lines 158–177). Replace just the bottom part to add the snapshot link:

```tsx
{fixReport && (
  <div className="p-4 bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-900/30 rounded-xl mb-6">
    <div className="flex items-center gap-2 mb-2">
      <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0" />
      <p className="text-green-800 dark:text-green-300 font-semibold">{fixReport.summary}</p>
    </div>
    {fixReport.files_changed.length > 0 && (
      <ul className="text-sm text-green-700 dark:text-green-400 space-y-1 ml-7">
        {fixReport.files_changed.map(f => (
          <li key={f} className="font-mono">{f}</li>
        ))}
      </ul>
    )}
    {fixReport.skipped.length > 0 && (
      <div className="mt-3 ml-7">
        <p className="text-sm font-medium text-amber-700 dark:text-amber-400">Skipped:</p>
        <ul className="text-sm text-amber-600 dark:text-amber-500 space-y-1 mt-1">
          {fixReport.skipped.map((s, i) => <li key={i}>{s}</li>)}
        </ul>
      </div>
    )}
    <p className="text-xs text-gray-500 dark:text-gray-400 mt-3 ml-7">
      Snapshot saved ·{' '}
      <button
        onClick={() => snapshotsPanelRef.current?.scrollIntoView({ behavior: 'smooth' })}
        className="text-blue-600 dark:text-blue-400 hover:underline"
      >
        restore if needed
      </button>
    </p>
  </div>
)}
```

Find the `<SnapshotsPanel key={snapshotsKey} />` line (line 267) and wrap it with the ref div:

```tsx
<div ref={snapshotsPanelRef}>
  <SnapshotsPanel key={snapshotsKey} />
</div>
```

- [ ] **Step 6: Verify in browser**

Go to Lint view. Expected:
- "Run Lint" button shows spinner + "Analysing wiki…" when clicked
- Time-estimate hint appears below button while waiting
- Green "Analysis complete — …" banner appears above findings when results return
- "Apply N selected" shows "Applying fixes…" + hint while applying
- Fix result shows files changed with "Snapshot saved · restore if needed" link that scrolls to SnapshotsPanel

- [ ] **Step 7: Commit**

```bash
git add Faragopedia-Sales/frontend/src/components/LintView.tsx
git commit -m "feat: improve LintView inline progress and result states"
```
