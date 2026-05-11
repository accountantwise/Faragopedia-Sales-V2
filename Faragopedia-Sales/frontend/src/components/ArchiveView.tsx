import React, { useState, useEffect, useRef } from 'react';
import { FileText, FileCheck, RotateCcw, Trash2, Loader2, Archive, X } from 'lucide-react';

import { API_BASE } from '../config';
import { formatPageName } from '../utils/formatPageName';
import ErrorToast from './ErrorToast';

const ArchiveView: React.FC = () => {
  const [archivedPages, setArchivedPages] = useState<string[]>([]);
  const [archivedSources, setArchivedSources] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState<boolean>(false);

  const totalItems = archivedPages.length + archivedSources.length;
  const allSelected = selectedItems.size === totalItems && totalItems > 0;
  const someSelected = selectedItems.size > 0 && !allSelected;

  const selectAllRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchArchivedItems();
  }, []);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someSelected;
    }
  }, [someSelected]);

  const fetchArchivedItems = async () => {
    try {
      setLoading(true);
      const [pagesRes, sourcesRes] = await Promise.all([
        fetch(`${API_BASE}/archive/pages`),
        fetch(`${API_BASE}/archive/sources`)
      ]);

      if (!pagesRes.ok || !sourcesRes.ok) throw new Error('Failed to fetch archived items');

      const pages = await pagesRes.json();
      const sources = await sourcesRes.json();

      setArchivedPages(pages);
      setArchivedSources(sources);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleItem = (key: string) => {
    setSelectedItems(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const toggleAll = () => {
    if (allSelected) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set<string>([
        ...archivedPages.map(p => `page:${p}`),
        ...archivedSources.map(s => `source:${s}`),
      ]));
    }
  };

  const clearSelection = () => setSelectedItems(new Set());

  const handleBulkRestore = async () => {
    setBulkLoading(true);
    const items = Array.from(selectedItems);
    const results = await Promise.allSettled(
      items.map(key => {
        const colonIdx = key.indexOf(':');
        const type = key.slice(0, colonIdx);
        const filename = key.slice(colonIdx + 1);
        const endpoint = type === 'page'
          ? `/archive/pages/${filename}/restore`
          : `/archive/sources/${encodeURIComponent(filename)}/restore`;
        return fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
      })
    );
    const failed = results.filter(
      r => r.status === 'rejected' || (r.status === 'fulfilled' && !r.value.ok)
    ).length;
    if (failed > 0) setError(`${failed} of ${items.length} items failed to restore.`);
    clearSelection();
    await fetchArchivedItems();
    setBulkLoading(false);
  };

  const handleBulkDelete = async () => {
    if (!window.confirm(`Permanently delete ${selectedItems.size} item${selectedItems.size === 1 ? '' : 's'}? This cannot be undone.`)) return;
    setBulkLoading(true);
    const items = Array.from(selectedItems);
    const results = await Promise.allSettled(
      items.map(key => {
        const colonIdx = key.indexOf(':');
        const type = key.slice(0, colonIdx);
        const filename = key.slice(colonIdx + 1);
        const endpoint = type === 'page'
          ? `/archive/pages/${filename}/permanent`
          : `/archive/sources/${encodeURIComponent(filename)}/permanent`;
        return fetch(`${API_BASE}${endpoint}`, { method: 'DELETE' });
      })
    );
    const failed = results.filter(
      r => r.status === 'rejected' || (r.status === 'fulfilled' && !r.value.ok)
    ).length;
    if (failed > 0) setError(`${failed} of ${items.length} items failed to delete.`);
    clearSelection();
    await fetchArchivedItems();
    setBulkLoading(false);
  };

  const handleRestore = async (filename: string, type: 'page' | 'source') => {
    setActionLoading(`${type}-restore-${filename}`);
    try {
      // Pages use a path param (subdir/file.md) so no encoding; sources are flat filenames
      const endpoint = type === 'page' ? `/archive/pages/${filename}/restore` : `/archive/sources/${encodeURIComponent(filename)}/restore`;
      const response = await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
      if (!response.ok) throw new Error(`Failed to restore ${type}`);
      await fetchArchivedItems();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeletePermanent = async (filename: string, type: 'page' | 'source') => {
    if (!window.confirm(`Are you sure you want to PERMANENTLY delete this ${type}? This cannot be undone.`)) return;
    
    setActionLoading(`${type}-delete-${filename}`);
    try {
      const endpoint = type === 'page' ? `/archive/pages/${filename}/permanent` : `/archive/sources/${encodeURIComponent(filename)}/permanent`;
      const response = await fetch(`${API_BASE}${endpoint}`, { method: 'DELETE' });
      if (!response.ok) throw new Error(`Failed to delete ${type}`);
      await fetchArchivedItems();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="animate-spin mr-2" /> Loading Archive...
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-12 max-w-6xl mx-auto">
      <div className="flex items-center space-x-4 mb-8">
        <div className="p-3 bg-amber-100 dark:bg-amber-900/30 rounded-2xl text-amber-600 dark:text-amber-400">
          <Archive className="w-8 h-8" />
        </div>
        <div>
          <h1 className="text-4xl font-extrabold text-gray-900 dark:text-gray-100 tracking-tight">Archive</h1>
          <p className="text-gray-500 dark:text-gray-400">Restore or permanently delete your archived files.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
        {/* Archived Wiki Pages */}
        <section>
          <h2 className="text-xl font-bold text-gray-800 dark:text-gray-200 mb-6 flex items-center">
            <FileText className="w-5 h-5 mr-2 text-blue-600 dark:text-blue-400" />
            Archived Wiki Pages
          </h2>
          {archivedPages.length === 0 ? (
            <div className="bg-gray-50 dark:bg-gray-800 border border-dashed border-gray-200 dark:border-gray-700 rounded-2xl p-8 text-center text-gray-400 dark:text-gray-500">
              No archived pages found.
            </div>
          ) : (
            <div className="space-y-3">
              {archivedPages.map((page) => (
                <div key={page} className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-xl p-4 flex items-center justify-between shadow-sm hover:shadow-md transition-shadow">
                  <div className="flex items-center space-x-3 overflow-hidden">
                    <FileText className="w-5 h-5 text-gray-400 dark:text-gray-500 flex-shrink-0" />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">
                      {formatPageName(page)}
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleRestore(page, 'page')}
                      disabled={!!actionLoading}
                      title="Restore"
                      className="p-2 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
                    >
                      {actionLoading === `page-restore-${page}` ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => handleDeletePermanent(page, 'page')}
                      disabled={!!actionLoading}
                      title="Delete Permanently"
                      className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors"
                    >
                      {actionLoading === `page-delete-${page}` ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Archived Sources */}
        <section>
          <h2 className="text-xl font-bold text-gray-800 dark:text-gray-200 mb-6 flex items-center">
            <FileCheck className="w-5 h-5 mr-2 text-green-600 dark:text-green-400" />
            Archived Sources
          </h2>
          {archivedSources.length === 0 ? (
            <div className="bg-gray-50 dark:bg-gray-800 border border-dashed border-gray-200 dark:border-gray-700 rounded-2xl p-8 text-center text-gray-400 dark:text-gray-500">
              No archived sources found.
            </div>
          ) : (
            <div className="space-y-3">
              {archivedSources.map((source) => (
                <div key={source} className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-xl p-4 flex items-center justify-between shadow-sm hover:shadow-md transition-shadow">
                  <div className="flex items-center space-x-3 overflow-hidden">
                    <FileCheck className="w-5 h-5 text-gray-400 dark:text-gray-500 flex-shrink-0" />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">{source}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleRestore(source, 'source')}
                      disabled={!!actionLoading}
                      title="Restore"
                      className="p-2 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
                    >
                      {actionLoading === `source-restore-${source}` ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => handleDeletePermanent(source, 'source')}
                      disabled={!!actionLoading}
                      title="Delete Permanently"
                      className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors"
                    >
                      {actionLoading === `source-delete-${source}` ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {error && (
        <ErrorToast message={error} onDismiss={() => setError(null)} />
      )}
    </div>
  );
};

export default ArchiveView;
