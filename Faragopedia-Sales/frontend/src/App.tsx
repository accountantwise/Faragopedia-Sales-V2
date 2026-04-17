import React, { useState, useRef, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import WikiView from './components/WikiView';
import SourcesView from './components/SourcesView';
import ArchiveView from './components/ArchiveView';
import LintView from './components/LintView';
import { Loader2, Upload, MessageSquare, Send, Menu, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { API_BASE } from './config';

const App: React.FC = () => {
  const [currentView, setCurrentView] = useState('Wiki');
  const [uploading, setUploading] = useState(false);
  const [chatQuery, setChatQuery] = useState('');
  const [chatHistory, setChatHistory] = useState<{ id: number, role: 'user' | 'assistant', content: string }[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, chatLoading]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    setUploading(true);
    try {
      const response = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData });
      if (!response.ok) throw new Error('Upload failed');
      const data = await response.json();
      alert(`Success: ${data.message}`);
    } catch (err) {
      alert('Error uploading file');
    } finally {
      setUploading(false);
      if (event.target) event.target.value = '';
    }
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
        return <WikiView />;
      case 'Sources':
        return <SourcesView />;
      case 'Upload':
        return (
          <div className="p-12 max-w-4xl mx-auto">
            <h1 className="text-4xl font-extrabold text-gray-900 mb-6 tracking-tight">Upload Sources</h1>
            <p className="text-xl text-gray-500 mb-8 leading-relaxed">
              Add documents, PDFs, or text files. The AI will ingest and create Farago schema pages automatically.
            </p>
            <label className="bg-white rounded-2xl shadow-sm border border-gray-200 p-12 flex flex-col items-center border-dashed border-2 hover:border-blue-400 transition-colors cursor-pointer group relative">
              <input type="file" className="hidden" onChange={handleFileUpload} disabled={uploading} />
              <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mb-6 group-hover:bg-blue-100 transition-colors">
                {uploading ? <Loader2 className="w-8 h-8 text-blue-600 animate-spin" /> : <Upload className="w-8 h-8 text-blue-600" />}
              </div>
              <p className="text-lg font-medium text-gray-700">
                {uploading ? 'Uploading and ingesting...' : 'Click to select a file to upload'}
              </p>
              <p className="text-sm text-gray-400 mt-2">PDF, TXT, and Markdown supported</p>
            </label>
          </div>
        );
      case 'Chat':
        return (
          <div className="p-12 max-w-4xl mx-auto h-full flex flex-col">
            <h1 className="text-4xl font-extrabold text-gray-900 mb-6 tracking-tight">AI Assistant</h1>
            <p className="text-xl text-gray-500 mb-8 leading-relaxed">
              Ask questions about your data. The AI synthesises answers from wiki pages and cites sources.
            </p>
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 flex-grow flex flex-col overflow-hidden mb-8">
              <div className="flex-grow overflow-y-auto p-6 space-y-4">
                {chatHistory.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-gray-400 space-y-4">
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
                        <div className={`max-w-[80%] px-4 py-3 rounded-2xl ${
                          msg.role === 'user'
                            ? 'bg-blue-600 text-white rounded-tr-none'
                            : 'bg-gray-100 text-gray-800 rounded-tl-none prose prose-sm prose-slate max-w-none'
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
                    <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-tl-none flex items-center space-x-2">
                      <Loader2 className="w-4 h-4 animate-spin text-gray-500" />
                      <span className="text-sm text-gray-500">AI is thinking...</span>
                    </div>
                  </div>
                )}
                <div ref={chatBottomRef} />
              </div>
              <div className="p-4 bg-gray-50 border-t">
                <div className="relative">
                  <input
                    type="text"
                    value={chatQuery}
                    onChange={(e) => setChatQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleChat()}
                    placeholder="Ask a question..."
                    disabled={chatLoading}
                    className="w-full px-6 py-4 bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all pr-16"
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
        return <ArchiveView />;
      case 'Lint':
        return <LintView />;
      default:
        return <div className="p-8">Select a view</div>;
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 font-sans antialiased text-gray-900 overflow-hidden">
      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}
      
      {/* Sidebar container */}
      <div className={`fixed inset-y-0 left-0 z-50 transform ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'} md:relative md:translate-x-0 transition-transform duration-300 ease-in-out`}>
        <Sidebar currentView={currentView} onViewChange={(v) => { setCurrentView(v); setMobileMenuOpen(false); }} />
      </div>

      <main className="flex-grow flex flex-col overflow-hidden relative w-full">
        {/* Mobile header area */}
        <div className="md:hidden bg-white border-b px-4 py-3 flex items-center shrink-0">
          <button onClick={() => setMobileMenuOpen(true)} className="p-2 -ml-2 text-gray-600 hover:bg-gray-100 rounded-lg">
            <Menu className="w-6 h-6" />
          </button>
          <span className="ml-4 font-bold text-gray-800">Faragopedia</span>
        </div>
        <div className="flex-grow overflow-hidden relative h-full">
          {renderContent()}
        </div>
      </main>
    </div>
  );
};

export default App;
