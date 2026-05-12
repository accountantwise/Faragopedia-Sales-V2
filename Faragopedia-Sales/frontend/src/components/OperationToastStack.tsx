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
