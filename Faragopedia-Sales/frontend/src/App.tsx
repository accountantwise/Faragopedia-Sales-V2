import React, { useState, useRef, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import SetupWizard from './components/SetupWizard';
import WikiView from './components/WikiView';
import SourcesView from './components/SourcesView';
import ArchiveView from './components/ArchiveView';
import LintView from './components/LintView';
import { Loader2, MessageSquare, Send, Menu, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { API_BASE } from './config';
import SettingsDrawer from './components/SettingsDrawer';

const App: React.FC = () => {
  const [setupState, setSetupState] = useState<'loading' | 'required' | 'ready'>('loading');
  const [wikiName, setWikiName] = useState('Wiki');
  const [reconfigureMode, setReconfigureMode] = useState(false);
  const [existingFolders, setExistingFolders] = useState<string[]>([]);
  const [currentView, setCurrentView] = useState('Wiki');
  const [chatQuery, setChatQuery] = useState('');
  const [chatHistory, setChatHistory] = useState<{ id: number, role: 'user' | 'assistant', content: string }[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sourcesMetadata, setSourcesMetadata] = useState<Record<string, { ingested: boolean; ingested_at: string | null; tags: string[] }>>({});
  const prevMetadataRef = useRef<Record<string, { ingested: boolean; ingested_at: string | null; tags: string[] }>>({});
  const [toasts, setToasts] = useState<{ id: number; message: string }[]>([]);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const [workspaces, setWorkspaces] = useState<{ id: string; name: string; archived?: boolean }[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState('');

  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>(() => {
    try { return (localStorage.getItem('faragopedia-theme') as 'light' | 'dark' | 'system') ?? 'system'; } catch (_) { return 'system'; }
  });
  const [settingsOpen, setSettingsOpen] = useState(false);

  const fetchWorkspaces = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/workspaces`);
      if (!res.ok) return;
      const data = await res.json();
      setWorkspaces(data.workspaces ?? []);
      setActiveWorkspaceId(data.active_workspace_id ?? '');
    } catch (_) {}
  }, []);

  // Setup status check — must be first useEffect
  useEffect(() => {
    fetch(`${API_BASE}/setup/status`)
      .then(r => r.json())
      .then(data => {
        if (data.setup_required) {
          setSetupState('required');
        } else {
          setWikiName(data.wiki_name || 'Wiki');
          setSetupState('ready');
          fetchWorkspaces();
        }
      })
      .catch(() => setSetupState('required'));
  }, [fetchWorkspaces]);

  useEffect(() => {
    try { localStorage.setItem('faragopedia-theme', theme); } catch (_) {}
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else if (theme === 'light') {
      root.classList.remove('dark');
    } else {
      const mq = window.matchMedia('(prefers-color-scheme: dark)');
      root.classList.toggle('dark', mq.matches);
      const handler = (e: MediaQueryListEvent) => root.classList.toggle('dark', e.matches);
      mq.addEventListener('change', handler);
      return () => mq.removeEventListener('change', handler);
    }
  }, [theme]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, chatLoading]);

  const addToast = useCallback((message: string) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const res = await fetch(`${API_BASE}/sources/metadata`);
        if (!res.ok) return;
        const data: Record<string, { ingested: boolean; ingested_at: string | null; tags: string[] }> = await res.json();

        // Fire toast for any source that just became ingested
        const prev = prevMetadataRef.current;
        Object.entries(data).forEach(([filename, meta]) => {
          if (meta.ingested && prev[filename] && !prev[filename].ingested) {
            addToast(`"${filename}" ingested successfully.`);
          }
        });

        prevMetadataRef.current = data;
        setSourcesMetadata(data);
      } catch (err) {
        console.error('Failed to fetch metadata', err);
      }
    };

    fetchMetadata();
    const interval = setInterval(fetchMetadata, 5000);
    return () => clearInterval(interval);
  }, [addToast]);

  const handleSetupComplete = async () => {
    const res = await fetch(`${API_BASE}/setup/config`);
    if (res.ok) {
      const data = await res.json();
      setWikiName(data.wiki_name);
    }
    setReconfigureMode(false);
    setSetupState('ready');
  };

  const handleReconfigure = async () => {
    // We use /folders (GET) instead of /clear (POST) to avoid deleting
    // the wiki_config.json until the user actually completes the wizard.
    const res = await fetch(`${API_BASE}/setup/folders`);
    if (res.ok) {
      const data = await res.json();
      setExistingFolders(data.existing_folders);
    }
    setReconfigureMode(true);
    setSetupState('required');
  };

  const handleSetupCancel = () => {
    setReconfigureMode(false);
    setSetupState('ready');
  };

  const handleSwitchWorkspace = async (id: string) => {
    const res = await fetch(`${API_BASE}/workspaces/${id}/switch`, { method: 'POST' });
    if (!res.ok) return;
    const data = await res.json();
    setActiveWorkspaceId(id);
    setChatHistory([]);
    setCurrentView('Wiki');
    setSourcesMetadata({});
    if (data.setup_required) {
      setReconfigureMode(false);
      setExistingFolders([]);
      setSetupState('required');
    } else {
      setWikiName(data.wiki_name || 'Wiki');
      setSetupState('ready');
    }
    fetchWorkspaces();
  };

  const handleNewWorkspace = async () => {
    const res = await fetch(`${API_BASE}/workspaces`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'New Workspace' }),
    });
    if (!res.ok) return;
    const data = await res.json();
    setActiveWorkspaceId(data.id);
    setChatHistory([]);
    setCurrentView('Wiki');
    setSourcesMetadata({});
    setSetupState('required');
    setReconfigureMode(false);
    setExistingFolders([]);
    fetchWorkspaces();
  };

  const handleArchiveWorkspace = async (id: string) => {
    await fetch(`${API_BASE}/workspaces/${id}/archive`, { method: 'POST' });
    fetchWorkspaces();
  };

  const handleUnarchiveWorkspace = async (id: string) => {
    await fetch(`${API_BASE}/workspaces/${id}/unarchive`, { method: 'POST' });
    fetchWorkspaces();
  };

  const handleDuplicateWorkspace = async (id: string, name: string, mode: 'full' | 'template') => {
    const res = await fetch(`${API_BASE}/workspaces/${id}/duplicate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, mode }),
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail ?? 'Duplicate failed');
    }
    const data = await res.json();
    setActiveWorkspaceId(data.id);
    setChatHistory([]);
    setCurrentView('Wiki');
    setSourcesMetadata({});
    if (data.setup_required) {
      setReconfigureMode(false);
      setExistingFolders([]);
      setSetupState('required');
    } else {
      setSetupState('ready');
    }
    fetchWorkspaces();
  };

  const handleChat = async () => {
    if (!chatQuery.trim()) return;
    const userMessage = chatQuery;
    setChatQuery('');
    setChatHistory(prev => [...prev, { id: Date.now(), role: 'user', content: userMessage }]);
    setChatLoading(true);
    try {
      const response = await fetch(`${API_BASE}/chat?query=${encodeURIComponent(userMessage)}`, { method: 'POST' });
      if (!response.ok) throw new Error('Chat failed');
      const data = await response.json();
      setChatHistory(prev => [...prev, { id: Date.now(), role: 'assistant', content: data.response }]);
    } catch (err) {
      setChatHistory(prev => [...prev, { id: Date.now(), role: 'assistant', content: 'Sorry, I encountered an error.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  const renderContent = () => {
    switch (currentView) {
      case 'Wiki':
        return <WikiView key={activeWorkspaceId} />;
      case 'Sources':
        return <SourcesView key={activeWorkspaceId} sourcesMetadata={sourcesMetadata} />;
      case 'Chat':
        return (
          <div className="p-12 max-w-4xl mx-auto h-full flex flex-col">
            <h1 className="text-4xl font-extrabold text-gray-900 dark:text-gray-100 mb-6 tracking-tight">AI Assistant</h1>
            <p className="text-xl text-gray-500 dark:text-gray-400 mb-8 leading-relaxed">
              Ask questions about your data. The AI synthesises answers from wiki pages and cites sources.
            </p>
            <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 flex-grow flex flex-col overflow-hidden mb-8">
              <div className="flex-grow overflow-y-auto p-6 space-y-4">
                {chatHistory.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-gray-400 dark:text-gray-600 space-y-4">
                    <MessageSquare className="w-12 h-12 opacity-20" />
                    <p>Start a conversation with your Wiki</p>
                  </div>
                ) : (
                  chatHistory.map((msg) => {
                    const processChatLinks = (text: string) => {
                      return text.replace(/\[\[(.*?)\]\]/g, (match, p1) => {
                        const trimmed = p1.trim();
                        const slug = trimmed.toLowerCase().replace(/\s+/g, '-');
                        if (trimmed.includes('/')) {
                          return `[${trimmed.split('/').pop()?.replace(/-/g, ' ')}](#${trimmed.replace('/', '__')})`;
                        }
                        return `[${trimmed}](#${slug})`;
                      });
                    };

                    return (
                      <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[80%] px-5 py-3 rounded-2xl ${
                          msg.role === 'user'
                            ? 'bg-blue-600 text-white rounded-tr-none'
                            : 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-tl-none prose prose-sm prose-slate dark:prose-invert max-w-none'
                        }`}>
                          {msg.role === 'user' ? (
                            <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                          ) : (
                            <ReactMarkdown
                              className="text-sm leading-relaxed whitespace-pre-wrap"
                              components={{
                                a: ({ node, ...props }) => {
                                  const isInternal = props.href?.startsWith('#');
                                  if (isInternal) {
                                    return (
                                      <a
                                        {...props}
                                        className="text-blue-600 hover:underline font-medium"
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
                              {processChatLinks(msg.content)}
                            </ReactMarkdown>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
                {chatLoading && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 px-5 py-3 rounded-2xl rounded-tl-none flex items-center space-x-2">
                      <Loader2 className="w-4 h-4 animate-spin text-gray-500" />
                      <span className="text-sm text-gray-500">AI is thinking...</span>
                    </div>
                  </div>
                )}
                <div ref={chatBottomRef} />
              </div>
              <div className="p-4 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
                <div className="relative">
                  <input
                    type="text"
                    value={chatQuery}
                    onChange={(e) => setChatQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleChat()}
                    placeholder="Ask a question..."
                    disabled={chatLoading}
                    className="w-full px-6 py-4 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all pr-16 placeholder:text-gray-400 dark:placeholder:text-gray-500"
                  />
                  <button
                    onClick={handleChat}
                    disabled={chatLoading || !chatQuery.trim()}
                    className="absolute right-3 top-3 bg-blue-600 text-white p-2 rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
                  >
                    <Send className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      case 'Archive':
        return <ArchiveView key={activeWorkspaceId} />;
      case 'Lint':
        return <LintView key={activeWorkspaceId} />;
      default:
        return <div className="p-8">Select a view</div>;
    }
  };

  if (setupState === 'loading') {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (setupState === 'required') {
    return (
      <SetupWizard
        onComplete={handleSetupComplete}
        onCancel={handleSetupCancel}
        reconfigureMode={reconfigureMode}
        existingFolders={existingFolders}
      />
    );
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-950 font-sans antialiased text-gray-900 dark:text-gray-100 overflow-hidden">
      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar container */}
      <div
        className={`fixed inset-y-0 left-0 z-50 flex-shrink-0 h-screen bg-gray-800 overflow-hidden transition-all duration-300 ease-in-out transform ${
          mobileMenuOpen ? 'translate-x-0 w-64' : '-translate-x-full w-64'
        } md:relative md:translate-x-0 ${sidebarOpen ? 'md:w-64' : 'md:w-0'}`}
      >
        <div className="w-64 h-full relative">
          <Sidebar
            currentView={currentView}
            onViewChange={(v) => { setCurrentView(v); setMobileMenuOpen(false); }}
            wikiName={wikiName}
            onOpenSettings={() => setSettingsOpen(true)}
            workspaces={workspaces}
            activeWorkspaceId={activeWorkspaceId}
            onSwitchWorkspace={handleSwitchWorkspace}
            onNewWorkspace={handleNewWorkspace}
            onArchiveWorkspace={handleArchiveWorkspace}
            onUnarchiveWorkspace={handleUnarchiveWorkspace}
            onDuplicateWorkspace={handleDuplicateWorkspace}
          />
          <button
            className="md:hidden absolute top-4 right-4 text-gray-400 hover:text-white p-2 rounded-lg bg-gray-800/80"
            onClick={() => setMobileMenuOpen(false)}
          >
            <X className="w-6 h-6" />
          </button>
        </div>
      </div>

      <main className="flex-grow flex flex-col overflow-hidden relative w-full">
        <div className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-4 py-4 flex items-center shrink-0 z-30 relative shadow-sm">
          <button
            onClick={() => {
              if (window.innerWidth < 768) setMobileMenuOpen(true);
              else setSidebarOpen(prev => !prev);
            }}
            className="p-2 -ml-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg flex items-center justify-center transition-colors focus:ring-2 focus:ring-blue-500 outline-none"
            aria-label="Toggle Navigation"
          >
            <Menu className="w-6 h-6" />
          </button>
          {!sidebarOpen && (
            <span className="hidden md:ml-4 font-bold text-gray-800 dark:text-gray-200 md:inline-block">{wikiName}</span>
          )}
          <span className="ml-4 font-bold text-gray-800 dark:text-gray-200 md:hidden">{wikiName}</span>
        </div>
        <div className="flex-grow overflow-hidden relative h-full">
          {renderContent()}
        </div>
        <ToastContainer toasts={toasts} />
      </main>
      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        theme={theme}
        onThemeChange={setTheme}
        onReconfigure={() => { setSettingsOpen(false); handleReconfigure(); }}
      />
    </div>
  );
};

{/* Global ingestion toasts component styled for premium feel */}
const ToastContainer: React.FC<{ toasts: { id: number; message: string }[] }> = ({ toasts }) => (
  <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 pointer-events-none">
    {toasts.map(t => (
      <div
        key={t.id}
        className="bg-gray-900/95 backdrop-blur text-white text-sm px-5 py-4 rounded-2xl shadow-2xl border border-white/10 flex items-center gap-3 animate-in slide-in-from-right-full fade-in duration-300"
      >
        <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse shadow-[0_0_8px_rgba(74,222,128,0.5)]" />
        {t.message}
      </div>
    ))}
  </div>
);

export default App;
