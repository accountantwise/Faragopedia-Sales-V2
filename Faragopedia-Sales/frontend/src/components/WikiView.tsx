import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { FileText, ChevronRight, Loader2, ArrowLeft, ArrowRight, Edit3, Save, X, Trash2, Download, Plus } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || `http://${window.location.hostname}:8300/api`;

const WikiView: React.FC = () => {
  const [pages, setPages] = useState<string[]>([]);
  const [selectedPage, setSelectedPage] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [backlinks, setBacklinks] = useState<string[]>([]);
  const [historyStack, setHistoryStack] = useState<string[]>([]);
  const [forwardStack, setForwardStack] = useState<string[]>([]);
  
  // Editing states
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editedContent, setEditedContent] = useState<string>('');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [isCreating, setIsCreating] = useState<boolean>(false);

  const [loading, setLoading] = useState<boolean>(true);
  const [contentLoading, setContentLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPages();
  }, []);

  const fetchPages = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/pages`);
      if (!response.ok) throw new Error('Failed to fetch pages');
      const data = await response.json();
      setPages(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchPageContent = async (filename: string, addToHistory: boolean = true) => {
    try {
      setContentLoading(true);
      setIsEditing(false); // Cancel editing when switching pages
      
      // History management
      if (addToHistory && selectedPage && selectedPage !== filename) {
        setHistoryStack(prev => [...prev, selectedPage]);
        setForwardStack([]);
      }

      setSelectedPage(filename);
      
      // Fetch content and backlinks in parallel
      const [contentRes, backlinksRes] = await Promise.all([
        fetch(`${API_BASE}/pages/${encodeURIComponent(filename)}`),
        fetch(`${API_BASE}/pages/${encodeURIComponent(filename)}/backlinks`)
      ]);

      if (!contentRes.ok) throw new Error('Failed to fetch page content');
      
      const contentData = await contentRes.json();
      const backlinksData = backlinksRes.ok ? await backlinksRes.json() : [];

      setContent(contentData.content);
      setEditedContent(contentData.content);
      setBacklinks(backlinksData);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setContentLoading(false);
    }
  };

  const handleSave = async () => {
    if (!selectedPage) return;
    try {
      setIsSaving(true);
      const response = await fetch(`${API_BASE}/pages/${encodeURIComponent(selectedPage)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editedContent }),
      });

      if (!response.ok) throw new Error('Failed to save page');
      
      setContent(editedContent);
      setIsEditing(false);
      // Refresh list in case title changed (though current implementation doesn't change filename on save)
      fetchPages();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleNewPage = async () => {
    try {
      setIsCreating(true);
      const response = await fetch(`${API_BASE}/pages`, { method: 'POST' });
      if (!response.ok) throw new Error('Failed to create new page');
      const data = await response.json();
      await fetchPages();
      await fetchPageContent(data.filename);
      setIsEditing(true); // Open in edit mode immediately
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedPage) return;
    if (!window.confirm(`Move '${selectedPage.replace('.md', '').replace(/_/g, ' ')}' to archive?`)) return;

    try {
      setIsDeleting(true);
      const response = await fetch(`${API_BASE}/pages/${encodeURIComponent(selectedPage)}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete page');
      
      setSelectedPage(null);
      setContent(null);
      fetchPages();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDownload = () => {
    if (!selectedPage) return;
    window.open(`${API_BASE}/pages/${encodeURIComponent(selectedPage)}/download`);
  };

  const handleBack = () => {
    if (historyStack.length === 0) return;
    const previous = historyStack[historyStack.length - 1];
    setHistoryStack(prev => prev.slice(0, -1));
    if (selectedPage) setForwardStack(prev => [selectedPage, ...prev]);
    fetchPageContent(previous, false);
  };

  const handleForward = () => {
    if (forwardStack.length === 0) return;
    const next = forwardStack[0];
    setForwardStack(prev => prev.slice(1));
    if (selectedPage) setHistoryStack(prev => [...prev, selectedPage]);
    fetchPageContent(next, false);
  };

  const processWikiLinks = (text: string) => {
    return text.replace(/\[\[(.*?)\]\]/g, (match, p1) => {
      const safeTitle = p1.replace(/[ /\\]/g, '_');
      return `[${p1}](#${safeTitle})`;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="animate-spin mr-2" /> Loading Wiki...
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Sidebar - Page List */}
      <div className="w-64 border-r bg-white overflow-y-auto p-4 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Pages</h2>
          <button 
            onClick={handleNewPage}
            disabled={isCreating}
            className="p-1.5 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors disabled:opacity-50"
            title="New Page"
          >
            {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          </button>
        </div>
        {pages.length === 0 ? (
          <p className="text-gray-500 text-sm">No pages found. Ingest some data first!</p>
        ) : (
          <ul className="space-y-1">
            {pages.map((page) => (
              <li key={page}>
                <button
                  onClick={() => fetchPageContent(page)}
                  className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors flex items-center justify-between ${
                    selectedPage === page
                      ? 'bg-blue-50 text-blue-700 font-medium'
                      : 'hover:bg-gray-100 text-gray-700'
                  }`}
                >
                  <span className="truncate flex items-center">
                    <FileText className="w-4 h-4 mr-2 opacity-70" />
                    {page.replace('.md', '').replace(/_/g, ' ')}
                  </span>
                  {selectedPage === page && <ChevronRight className="w-4 h-4" />}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Main Content - Markdown View */}
      <div className="flex-grow overflow-y-auto bg-white flex flex-col">
        {/* Navigation Header */}
        <div className="border-b px-8 py-3 flex items-center justify-between sticky top-0 bg-white/80 backdrop-blur-sm z-10">
          <div className="flex items-center space-x-2">
            <button
              onClick={handleBack}
              disabled={historyStack.length === 0 || isEditing}
              className={`p-1.5 rounded-md transition-colors ${
                historyStack.length === 0 || isEditing ? 'text-gray-300 cursor-not-allowed' : 'text-gray-600 hover:bg-gray-100'
              }`}
              title="Back"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <button
              onClick={handleForward}
              disabled={forwardStack.length === 0 || isEditing}
              className={`p-1.5 rounded-md transition-colors ${
                forwardStack.length === 0 || isEditing ? 'text-gray-300 cursor-not-allowed' : 'text-gray-600 hover:bg-gray-100'
              }`}
              title="Forward"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
            {selectedPage && (
              <span className="ml-4 text-sm font-medium text-gray-500 truncate max-w-xs">
                {selectedPage.replace('.md', '').replace(/_/g, ' ')}
              </span>
            )}
          </div>

          {selectedPage && (
            <div className="flex items-center space-x-2">
              {isEditing ? (
                <>
                  <button
                    onClick={handleSave}
                    disabled={isSaving}
                    className="flex items-center px-3 py-1.5 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 transition-colors disabled:opacity-50"
                  >
                    {isSaving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Save className="w-4 h-4 mr-1.5" />}
                    Save
                  </button>
                  <button
                    onClick={() => {
                      setIsEditing(false);
                      setEditedContent(content || '');
                    }}
                    disabled={isSaving}
                    className="flex items-center px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-200 transition-colors"
                  >
                    <X className="w-4 h-4 mr-1.5" />
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setIsEditing(true)}
                  className="flex items-center px-3 py-1.5 bg-white border border-gray-300 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-50 transition-colors"
                >
                  <Edit3 className="w-4 h-4 mr-1.5" />
                  Edit
                </button>
              )}
              
              <button
                onClick={handleDownload}
                className="p-1.5 text-gray-500 hover:bg-gray-100 rounded-md transition-colors"
                title="Download Page"
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

        <div className="p-8 flex-grow">
          {contentLoading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="animate-spin mr-2" /> Loading content...
            </div>
          ) : isEditing ? (
            <textarea
              value={editedContent}
              onChange={(e) => setEditedContent(e.target.value)}
              className="w-full h-full min-h-[500px] p-6 text-slate-800 font-mono text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-none"
              placeholder="Write your markdown here..."
            />
          ) : content ? (
            <div className="prose prose-slate max-w-none">
              <ReactMarkdown
                components={{
                  a: ({ node, ...props }) => {
                    const isInternal = props.href?.startsWith('#');
                    if (isInternal) {
                      const pageName = props.href?.slice(1);
                      return (
                        <a
                          {...props}
                          onClick={(e) => {
                            e.preventDefault();
                            if (pageName) fetchPageContent(pageName + '.md');
                          }}
                          className="text-blue-600 hover:underline cursor-pointer font-medium"
                        >
                          {props.children}
                        </a>
                      );
                    }
                    return (
                      <a 
                        {...props} 
                        className="text-blue-600 hover:underline" 
                        target="_blank" 
                        rel="noopener noreferrer" 
                      />
                    );
                  }
                }}
              >
                {processWikiLinks(content || '')}
              </ReactMarkdown>

              {/* Backlinks Section */}
              {backlinks.length > 0 && (
                <div className="mt-12 pt-8 border-t border-gray-100">
                  <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                    <FileText className="w-5 h-5 mr-2 opacity-50" />
                    Linked Mentions
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {backlinks.map((link) => (
                      <button
                        key={link}
                        onClick={() => fetchPageContent(link)}
                        className="text-left p-4 rounded-lg border border-gray-100 hover:border-blue-200 hover:bg-blue-50 transition-all group"
                      >
                        <div className="text-sm font-medium text-blue-600 group-hover:text-blue-700 truncate">
                          {link.replace('.md', '').replace(/_/g, ' ')}
                        </div>
                        <div className="text-xs text-gray-400 mt-1 uppercase tracking-wider">
                          Page Reference
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <FileText className="w-16 h-16 mb-4 opacity-20" />
              <p>Select a page from the list to view its content.</p>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="fixed bottom-4 right-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {error}
          <button onClick={() => setError(null)} className="ml-4 font-bold">&times;</button>
        </div>
      )}
    </div>
  );
};

export default WikiView;
