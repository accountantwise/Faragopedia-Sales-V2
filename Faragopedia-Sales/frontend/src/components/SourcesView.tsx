import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { FileText, ChevronRight, Loader2, FileCheck, Trash2, Download, ArrowLeft, ArrowRight, Plus, Database, MoreVertical, X } from 'lucide-react';

import { API_BASE } from '../config';
import ErrorToast from './ErrorToast';
import AddSourcesModal from './AddSourcesModal';

const SourcesView: React.FC = () => {
  const [sources, setSources] = useState<string[]>([]);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [historyStack, setHistoryStack] = useState<string[]>([]);
  const [forwardStack, setForwardStack] = useState<string[]>([]);
  const [metadata, setMetadata] = useState<Record<string, { ingested: boolean, ingested_at: string | null }>>({});
  const [ingesting, setIngesting] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState<boolean>(false);

  const [loading, setLoading] = useState<boolean>(true);
  const [contentLoading, setContentLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  // Resizable sidebar state
  const [sidebarWidth, setSidebarWidth] = useState<number>(256);
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);

  // Mobile/Tablet responsive states
  const [isDesktop, setIsDesktop] = useState(window.innerWidth >= 1024);
  const [showMobileList, setShowMobileList] = useState(true);
  const [showActionMenu, setShowActionMenu] = useState(false);

  const handleMouseDown = (e: React.MouseEvent) => {
    dragRef.current = { startX: e.clientX, startWidth: sidebarWidth };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!dragRef.current) return;
    const { startX, startWidth } = dragRef.current;
    const newWidth = Math.min(Math.max(200, startWidth + (e.clientX - startX)), 800);
    setSidebarWidth(newWidth);
  }, []);

  const handleMouseUp = useCallback(() => {
    if (dragRef.current) {
      dragRef.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
  }, []);

  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    
    // Track window resizes for responsive layout
    const handleResize = () => setIsDesktop(window.innerWidth >= 1024);
    window.addEventListener('resize', handleResize);
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      window.removeEventListener('resize', handleResize);
    };
  }, [handleMouseMove, handleMouseUp]);

  useEffect(() => {
    fetchSources();
    fetchMetadata();
    
    // Poll metadata occasionally to catch background ingestion updates
    const interval = setInterval(fetchMetadata, 5000);
    return () => clearInterval(interval);
  }, []);

  const parseFrontmatter = (text: string) => {
    const match = text.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
    if (match) {
      const frontmatterText = match[1];
      const restContent = match[2];
      const tags: {key: string, value: string}[] = [];
      frontmatterText.split('\n').forEach(line => {
        const colonIdx = line.indexOf(':');
        if (colonIdx > -1) {
          const key = line.substring(0, colonIdx).trim();
          const val = line.substring(colonIdx + 1).trim();
          if (key && val) tags.push({ key, value: val });
        }
      });
      return { tags, content: restContent };
    }
    return { tags: [], content: text };
  };

  const fetchMetadata = async () => {
    try {
      const response = await fetch(`${API_BASE}/sources/metadata`);
      if (response.ok) {
        const data = await response.json();
        setMetadata(data);
      }
    } catch (err) {
      console.error('Failed to fetch metadata', err);
    }
  };

  const fetchSources = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/sources`);
      if (!response.ok) throw new Error('Failed to fetch sources');
      const data = await response.json();
      setSources(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchSourceContent = async (filename: string, addToHistory: boolean = true) => {
    try {
      setContentLoading(true);
      
      if (addToHistory && selectedSource && selectedSource !== filename) {
        setHistoryStack(prev => [...prev, selectedSource]);
        setForwardStack([]);
      }

      setSelectedSource(filename);
      
      const response = await fetch(`${API_BASE}/sources/${encodeURIComponent(filename)}`);
      if (!response.ok) throw new Error('Failed to fetch source content');
      
      const data = await response.json();
      setContent(data.content);
      
      // Auto-switch away from list view on small screens
      setShowMobileList(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setContentLoading(false);
    }
  };

  const handleBack = () => {
    if (historyStack.length === 0) return;
    const previous = historyStack[historyStack.length - 1];
    setHistoryStack(prev => prev.slice(0, -1));
    if (selectedSource) setForwardStack(prev => [selectedSource, ...prev]);
    fetchSourceContent(previous, false);
  };

  const handleForward = () => {
    if (forwardStack.length === 0) return;
    const next = forwardStack[0];
    setForwardStack(prev => prev.slice(1));
    if (selectedSource) setHistoryStack(prev => [...prev, selectedSource]);
    fetchSourceContent(next, false);
  };

  const handleIngest = async () => {
    if (!selectedSource) return;
    try {
      setIngesting(selectedSource);
      const response = await fetch(`${API_BASE}/sources/${encodeURIComponent(selectedSource)}/ingest`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Failed to start ingestion');
      // Metadata will be updated by polling
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIngesting(null);
    }
  };

  const handleDelete = async () => {
    if (!selectedSource) return;
    if (!window.confirm(`Move source '${selectedSource}' to archive?`)) return;

    try {
      setIsDeleting(true);
      const response = await fetch(`${API_BASE}/sources/${encodeURIComponent(selectedSource)}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete source');
      
      setSelectedSource(null);
      setContent(null);
      fetchSources();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDownload = () => {
    if (!selectedSource) return;
    window.open(`${API_BASE}/sources/${encodeURIComponent(selectedSource)}/download`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="animate-spin mr-2" /> Loading Sources...
      </div>
    );
  }

  return (
    <div className="flex h-full relative">
      {/* Sidebar - Source List */}
      <div 
        className={`border-r bg-white overflow-y-auto p-4 flex-col flex-shrink-0 ${!isDesktop && !showMobileList ? 'hidden' : 'flex'} ${!isDesktop ? 'w-full' : ''}`}
        style={isDesktop ? { width: sidebarWidth } : undefined}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Sources</h2>
          <button
            onClick={() => setShowAddModal(true)}
            className="p-1.5 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors"
            title="Add Source"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
        {sources.length === 0 ? (
          <p className="text-gray-500 text-sm">No source files found. Upload some data!</p>
        ) : (
          <ul className="space-y-1">
            {sources.map((source) => (
              <li key={source}>
                <button
                  onClick={() => fetchSourceContent(source)}
                  className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors flex items-center justify-between ${
                    selectedSource === source
                      ? 'bg-blue-50 text-blue-700 font-medium'
                      : 'hover:bg-gray-100 text-gray-700'
                  }`}
                >
                  <span className="flex items-start text-left max-w-[85%]">
                    <FileCheck className={`w-4 h-4 mr-2 mt-0.5 shrink-0 ${metadata[source]?.ingested ? 'text-green-500' : 'text-gray-400 opacity-50'}`} />
                    <span className="break-words line-clamp-2">{source}</span>
                  </span>
                  {selectedSource === source && <ChevronRight className="w-4 h-4" />}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Drag Handle Gutter */}
      {isDesktop && (
        <div
          onMouseDown={handleMouseDown}
          className="w-1 bg-transparent hover:bg-blue-400 cursor-col-resize transition-colors z-20 flex-shrink-0"
        />
      )}

      {/* Main Content - Source View */}
      <div className={`flex-grow overflow-y-auto bg-white flex-col ${!isDesktop && showMobileList ? 'hidden' : 'flex'}`}>
        {/* Navigation Header */}
        <div className="hidden lg:flex border-b px-8 py-3 items-center justify-between sticky top-0 bg-white/80 backdrop-blur-sm z-10">
          <div className="flex items-center space-x-2">
            <button
              onClick={handleBack}
              disabled={historyStack.length === 0}
              className={`p-1.5 rounded-md transition-colors ${
                historyStack.length === 0 ? 'text-gray-300 cursor-not-allowed' : 'text-gray-600 hover:bg-gray-100'
              }`}
              title="Back"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <button
              onClick={handleForward}
              disabled={forwardStack.length === 0}
              className={`p-1.5 rounded-md transition-colors ${
                forwardStack.length === 0 ? 'text-gray-300 cursor-not-allowed' : 'text-gray-600 hover:bg-gray-100'
              }`}
              title="Forward"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
            {selectedSource && (
              <div className="flex items-center ml-4 space-x-3">
                <span className="text-sm font-medium text-gray-500 truncate max-w-xs">
                  {selectedSource}
                </span>
                {metadata[selectedSource]?.ingested ? (
                  <span className="flex items-center px-2 py-0.5 rounded-full bg-green-50 text-green-600 text-[10px] font-bold uppercase tracking-wider border border-green-100">
                    <Database className="w-3 h-3 mr-1" />
                    Ingested
                  </span>
                ) : (
                  <span className="flex items-center px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 text-[10px] font-bold uppercase tracking-wider border border-amber-100">
                    Pending
                  </span>
                )
                }
              </div>
            )}
          </div>
          
          {selectedSource && (
            <div className="flex items-center space-x-2">
              {!metadata[selectedSource]?.ingested && (
                <button
                  onClick={handleIngest}
                  disabled={!!ingesting}
                  className="flex items-center px-3 py-1.5 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 transition-colors disabled:bg-blue-400"
                >
                  {ingesting === selectedSource ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                  ) : (
                    <Database className="w-4 h-4 mr-1.5" />
                  )}
                  {ingesting === selectedSource ? 'Ingesting...' : 'Ingest'}
                </button>
              )}
              <button
                onClick={handleDownload}
                className="p-1.5 text-gray-500 hover:bg-gray-100 rounded-md transition-colors"
                title="Download Source"
              >
                <Download className="w-5 h-5" />
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="p-1.5 text-red-500 hover:bg-red-50 rounded-md transition-colors disabled:opacity-50"
                title="Move to Archive"
              >
                {isDeleting ? <Loader2 className="w-5 h-5 animate-spin" /> : <Trash2 className="w-5 h-5" />}
              </button>
            </div>
          )}
        </div>

        <div className="p-8 flex-grow pb-28 lg:pb-8">
          {contentLoading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="animate-spin mr-2" /> Loading source content...
            </div>
          ) : content ? (
            selectedSource?.endsWith('.md') ? (
              <div className="prose prose-slate max-w-none">
                {(() => {
                   const { tags, content: cleanContent } = parseFrontmatter(content);
                   return (
                     <>
                       {tags.length > 0 && (
                         <div className="flex flex-wrap gap-2 mb-8 p-4 bg-gray-50/80 rounded-xl border border-gray-100 shadow-sm backdrop-blur-sm">
                           {tags.map((t, idx) => (
                             <span key={idx} className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-white border border-gray-200 text-gray-700 shadow-sm uppercase tracking-wider">
                               <span className="text-gray-400 mr-2 text-[10px]">{t.key}:</span>
                               <span className="text-blue-600 font-bold">{t.value}</span>
                             </span>
                           ))}
                         </div>
                       )}
                       <ReactMarkdown
                         components={{
                           a: ({ node, ...props }) => (
                             <a 
                               {...props} 
                               className="text-blue-600 hover:underline" 
                               target="_blank" 
                               rel="noopener noreferrer" 
                             />
                           )
                         }}
                       >
                         {cleanContent}
                       </ReactMarkdown>
                     </>
                   );
                })()}
              </div>
            ) : (
              <div className="bg-gray-50 p-6 rounded-lg border border-gray-200">
                <pre className="whitespace-pre-wrap font-mono text-sm text-gray-800 leading-relaxed">
                  {content}
                </pre>
              </div>
            )
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <FileCheck className="w-16 h-16 mb-4 opacity-20" />
              <p>Select a source file from the list to view its content.</p>
              <p className="text-sm mt-2 italic text-gray-300">PDFs will show extracted text.</p>
            </div>
          )}
        </div>
      </div>

      {/* Floating Mobile Toggle Button */}
      {!isDesktop && !showMobileList && (
        <button
          onClick={() => setShowMobileList(true)}
          className="fixed bottom-6 left-6 p-4 bg-gray-900 text-white rounded-full shadow-xl hover:bg-black hover:scale-105 active:scale-95 transition-all z-40 flex items-center justify-center transform"
          title="Back to Sources List"
        >
          <ArrowLeft className="w-6 h-6" />
        </button>
      )}

      {/* Floating Mobile Action Menu */}
      {!isDesktop && !showMobileList && selectedSource && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex flex-col items-center">
          {showActionMenu && (
            <div className="flex flex-col items-stretch space-y-3 mb-4 animate-in slide-in-from-bottom-2 fade-in duration-200">
              {!metadata[selectedSource]?.ingested && (
                <button
                  onClick={() => { handleIngest(); setShowActionMenu(false); }}
                  disabled={!!ingesting}
                  className="flex justify-start items-center px-5 py-2 bg-blue-600 text-white rounded-full shadow-md text-sm font-medium hover:bg-blue-700 transition-colors disabled:bg-blue-400"
                >
                  {ingesting === selectedSource ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-3" />
                  ) : (
                    <Database className="w-4 h-4 mr-3" />
                  )}
                  {ingesting === selectedSource ? 'Ingesting...' : 'Ingest'}
                </button>
              )}
              
              <button
                onClick={() => { handleDownload(); setShowActionMenu(false); }}
                className="flex justify-start items-center px-5 py-2 bg-white text-gray-700 rounded-full shadow-md text-sm font-medium hover:bg-gray-50 transition-colors"
              >
                <Download className="w-4 h-4 mr-3" />
                Download
              </button>
              <button
                onClick={() => { handleDelete(); setShowActionMenu(false); }}
                disabled={isDeleting}
                className="flex justify-start items-center px-5 py-2 bg-red-50 text-red-600 rounded-full shadow-md text-sm font-medium hover:bg-red-100 transition-colors disabled:opacity-50"
              >
                {isDeleting ? <Loader2 className="w-4 h-4 animate-spin mr-3" /> : <Trash2 className="w-4 h-4 mr-3" />}
                Archive
              </button>
            </div>
          )}
          
          <button
            onClick={() => setShowActionMenu(!showActionMenu)}
            className={`p-4 rounded-full shadow-xl transition-all transform hover:scale-105 active:scale-95 flex items-center justify-center bg-gray-900 text-white`}
            title="Page Actions"
          >
            {showActionMenu ? <X className="w-6 h-6" /> : <MoreVertical className="w-6 h-6" />}
          </button>
        </div>
      )}

      <AddSourcesModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onSourceAdded={() => { fetchSources(); fetchMetadata(); }}
      />

      {error && (
        <ErrorToast message={error} onDismiss={() => setError(null)} />
      )}
    </div>
  );
};

export default SourcesView;
