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
