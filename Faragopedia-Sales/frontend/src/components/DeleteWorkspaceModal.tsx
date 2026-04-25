import React, { useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface DeleteWorkspaceModalProps {
  workspaceName: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

const DeleteWorkspaceModal: React.FC<DeleteWorkspaceModalProps> = ({
  workspaceName,
  onConfirm,
  onClose,
}) => {
  const [confirmText, setConfirmText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const isMatch = confirmText === workspaceName;

  const handleSubmit = async () => {
    if (!isMatch) return;
    setLoading(true);
    setError('');
    try {
      await onConfirm();
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
            <AlertTriangle className="w-5 h-5 text-red-400" />
            Delete workspace permanently
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-gray-400 mb-5">
          This action <span className="text-white font-medium">cannot be undone</span>. All pages,
          sources, and data in <span className="text-white font-medium">{workspaceName}</span> will
          be deleted forever.
        </p>

        <div className="mb-5">
          <label className="block text-sm text-gray-300 mb-1">
            Type <span className="font-mono text-white">{workspaceName}</span> to confirm
          </label>
          <input
            type="text"
            value={confirmText}
            onChange={e => setConfirmText(e.target.value)}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-red-500"
            autoFocus
            onKeyDown={e => e.key === 'Enter' && isMatch && handleSubmit()}
          />
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
            disabled={!isMatch || loading}
            className="px-4 py-2 text-sm bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
          >
            {loading ? 'Deleting…' : 'Delete forever'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeleteWorkspaceModal;
