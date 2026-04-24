import React, { useState } from 'react';
import { Copy, X } from 'lucide-react';

interface DuplicateWorkspaceModalProps {
  sourceName: string;
  onClose: () => void;
  onConfirm: (name: string, mode: 'full' | 'template') => Promise<void>;
}

const DuplicateWorkspaceModal: React.FC<DuplicateWorkspaceModalProps> = ({
  sourceName,
  onClose,
  onConfirm,
}) => {
  const [name, setName] = useState(`Copy of ${sourceName}`);
  const [mode, setMode] = useState<'full' | 'template'>('full');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('Name is required.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await onConfirm(name.trim(), mode);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Something went wrong.');
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Copy className="w-5 h-5 text-blue-400" />
            Duplicate Workspace
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="mb-4">
          <label className="block text-sm text-gray-300 mb-1">Name</label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            autoFocus
          />
        </div>

        <div className="mb-5 grid grid-cols-2 gap-3">
          <button
            onClick={() => setMode('full')}
            className={`p-4 rounded-lg border text-left transition-colors ${
              mode === 'full'
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-gray-600 hover:border-gray-500'
            }`}
          >
            <div className="font-medium text-sm mb-1">Full Copy</div>
            <div className="text-xs text-gray-400">Copies all pages, sources, and content.</div>
          </button>
          <button
            onClick={() => setMode('template')}
            className={`p-4 rounded-lg border text-left transition-colors ${
              mode === 'template'
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-gray-600 hover:border-gray-500'
            }`}
          >
            <div className="font-medium text-sm mb-1">Empty Wiki</div>
            <div className="text-xs text-gray-400">Copies schema structure only. Setup wizard to configure.</div>
          </button>
        </div>

        {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-300 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg transition-colors"
          >
            {loading ? 'Duplicating…' : 'Duplicate'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DuplicateWorkspaceModal;
