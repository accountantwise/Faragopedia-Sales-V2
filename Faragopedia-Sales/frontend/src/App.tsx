import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import WikiView from './components/WikiView';
import SourcesView from './components/SourcesView';
import ArchiveView from './components/ArchiveView';
import { Loader2, Activity, AlertCircle, CheckCircle2, X, Upload, MessageSquare } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || `http://${window.location.hostname}:8300/api`;

const App: React.FC = () => {
  const [currentView, setCurrentView] = useState('Wiki');
  const [healthResult, setHealthResult] = useState<any>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  const handleHealthCheck = async () => {
    setHealthLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (!response.ok) throw new Error('Health check failed');
      const data = await response.json();
      setHealthResult(data);
    } catch (err) {
      alert('Error connecting to backend for health check');
    } finally {
      setHealthLoading(false);
    }
  };

  const [uploading, setUploading] = useState(false);
  const [chatQuery, setChatQuery] = useState('');
  const [chatHistory, setChatHistory] = useState<{ role: 'user' | 'assistant', content: string }[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData,
      });
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
    setChatHistory(prev => [...prev, { role: 'user', content: userMessage }]);
    setChatLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chat?query=${encodeURIComponent(userMessage)}`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Chat failed');
      const data = await response.json();
      setChatHistory(prev => [...prev, { role: 'assistant', content: data.response }]);
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error processing your request.' }]);
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
              Add new documents, PDFs, or text files to expand the Faragopedia knowledge base.
              The AI will automatically ingest and link entities.
            </p>
            <label className="bg-white rounded-2xl shadow-sm border border-gray-200 p-12 flex flex-col items-center border-dashed border-2 hover:border-blue-400 transition-colors cursor-pointer group relative">
              <input type="file" className="hidden" onChange={handleFileUpload} disabled={uploading} />
              <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mb-6 group-hover:bg-blue-100 transition-colors">
                {uploading ? (
                  <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
                ) : (
                  <Upload className="w-8 h-8 text-blue-600" />
                )}
              </div>
              <p className="text-lg font-medium text-gray-700">
                {uploading ? 'Uploading and Ingesting...' : 'Click to select a file to upload'}
              </p>
              <p className="text-sm text-gray-400 mt-2">Support for PDF, TXT, and Markdown</p>
            </label>
          </div>
        );
      case 'Chat':
        return (
          <div className="p-12 max-w-4xl mx-auto h-full flex flex-col">
            <h1 className="text-4xl font-extrabold text-gray-900 mb-6 tracking-tight">AI Assistant</h1>
            <p className="text-xl text-gray-500 mb-8 leading-relaxed">
              Ask questions about your data. The LLM synthesizes answers from existing wiki pages and cites its sources.
            </p>
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 flex-grow flex flex-col overflow-hidden mb-8">
              <div className="flex-grow overflow-y-auto p-6 space-y-4">
                {chatHistory.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-gray-400 space-y-4">
                    <MessageSquare className="w-12 h-12 opacity-20" />
                    <p>Start a conversation with your Wiki</p>
                  </div>
                ) : (
                  chatHistory.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] px-4 py-3 rounded-2xl ${
                        msg.role === 'user' 
                          ? 'bg-blue-600 text-white rounded-tr-none' 
                          : 'bg-gray-100 text-gray-800 rounded-tl-none'
                      }`}>
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                      </div>
                    </div>
                  ))
                )}
                {chatLoading && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-tl-none flex items-center space-x-2">
                      <Loader2 className="w-4 h-4 animate-spin text-gray-500" />
                      <span className="text-sm text-gray-500">AI is thinking...</span>
                    </div>
                  </div>
                )}
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
                    <Activity className="w-5 h-5 transform rotate-90" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      case 'Archive':
        return <ArchiveView />;
      default:
        return <div className="p-8">Select a view</div>;
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 font-sans antialiased text-gray-900">
      <Sidebar 
        currentView={currentView} 
        onViewChange={setCurrentView} 
        onHealthCheck={handleHealthCheck}
      />
      <main className="flex-grow overflow-hidden relative">
        {renderContent()}

        {/* Health Check Loading Overlay */}
        {healthLoading && (
          <div className="absolute inset-0 bg-white/60 backdrop-blur-sm z-50 flex items-center justify-center">
            <div className="bg-white p-8 rounded-2xl shadow-2xl border flex flex-col items-center">
              <Loader2 className="w-12 h-12 text-blue-600 animate-spin mb-4" />
              <p className="text-lg font-semibold text-gray-800">Checking Wiki Health...</p>
              <p className="text-sm text-gray-500">Scanning for orphans and dead links</p>
            </div>
          </div>
        )}

        {/* Health Check Modal */}
        {healthResult && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-3xl shadow-2xl max-w-lg w-full overflow-hidden">
              <div className={`p-6 flex items-center justify-between border-b ${
                healthResult.status === 'healthy' ? 'bg-green-50' : 'bg-amber-50'
              }`}>
                <div className="flex items-center">
                  {healthResult.status === 'healthy' ? (
                    <CheckCircle2 className="w-6 h-6 text-green-600 mr-3" />
                  ) : (
                    <AlertCircle className="w-6 h-6 text-amber-600 mr-3" />
                  )}
                  <h3 className="text-xl font-bold text-gray-900">Health Report</h3>
                </div>
                <button onClick={() => setHealthResult(null)} className="p-2 hover:bg-black/5 rounded-full transition-colors">
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>
              <div className="p-8 space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-50 p-4 rounded-xl text-center">
                    <p className="text-sm text-gray-500 uppercase font-semibold">Total Pages</p>
                    <p className="text-3xl font-black text-blue-600">{healthResult.total_pages}</p>
                  </div>
                  <div className="bg-gray-50 p-4 rounded-xl text-center">
                    <p className="text-sm text-gray-500 uppercase font-semibold">Status</p>
                    <p className={`text-xl font-bold capitalize ${
                      healthResult.status === 'healthy' ? 'text-green-600' : 'text-amber-600'
                    }`}>{healthResult.status}</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <p className="text-sm font-bold text-gray-700 mb-2 flex items-center">
                      <span className="w-2 h-2 bg-amber-500 rounded-full mr-2"></span>
                      Orphan Pages ({healthResult.orphan_pages.length})
                    </p>
                    {healthResult.orphan_pages.length > 0 ? (
                      <div className="bg-amber-50/50 p-3 rounded-lg text-sm text-amber-900 max-h-32 overflow-y-auto">
                        {healthResult.orphan_pages.join(', ')}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-400 italic">None found - All pages are linked!</p>
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-bold text-gray-700 mb-2 flex items-center">
                      <span className="w-2 h-2 bg-red-500 rounded-full mr-2"></span>
                      Missing Pages ({healthResult.missing_pages.length})
                    </p>
                    {healthResult.missing_pages.length > 0 ? (
                      <div className="bg-red-50/50 p-3 rounded-lg text-sm text-red-900 max-h-32 overflow-y-auto">
                        {healthResult.missing_pages.join(', ')}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-400 italic">None found - No dead links!</p>
                    )}
                  </div>
                </div>
              </div>
              <div className="p-6 bg-gray-50 flex justify-end">
                <button 
                  onClick={() => setHealthResult(null)}
                  className="px-6 py-2 bg-gray-900 text-white rounded-xl font-semibold hover:bg-gray-800 transition-all shadow-lg"
                >
                  Close Report
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
