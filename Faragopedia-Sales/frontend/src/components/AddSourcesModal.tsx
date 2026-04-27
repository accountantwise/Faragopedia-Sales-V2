import React, { useState, useRef } from 'react';
import { X, Upload, FileText, Loader2 } from 'lucide-react';
import { API_BASE } from '../config';

interface Props {
  open: boolean;
  onClose: () => void;
  onSourceAdded: () => void;
}

type Tab = 'files' | 'url' | 'paste';

const AddSourcesModal: React.FC<Props> = ({ open, onClose, onSourceAdded }) => {
  const [activeTab, setActiveTab] = useState<Tab>('files');

  // Files tab
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // URL tab
  const [urlText, setUrlText] = useState('');
  const [crawling, setCrawling] = useState(false);

  // Paste tab
  const [pasteName, setPasteName] = useState('');
  const [pasteContent, setPasteContent] = useState('');
  const [saving, setSaving] = useState(false);

  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const switchTab = (tab: Tab) => { setActiveTab(tab); setError(null); };

  // ── Files tab handlers ────────────────────────────────────────────────────

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = () => setIsDragging(false);
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    setSelectedFiles(prev => [...prev, ...Array.from(e.dataTransfer.files)]);
  };
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedFiles(prev => [...prev, ...Array.from(e.target.files ?? [])]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };
  const removeFile = (index: number) => setSelectedFiles(prev => prev.filter((_, i) => i !== index));

  const handleFilesSubmit = async () => {
    if (selectedFiles.length === 0) return;
    setUploading(true);
    setError(null);
    let anySuccess = false;
    for (const file of selectedFiles) {
      try {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(`${API_BASE}/upload?ingest=false`, { method: 'POST', body: formData });
        if (!res.ok) throw new Error(`Failed to upload ${file.name}`);
        anySuccess = true;
      } catch (err: any) {
        setError(err.message);
      }
    }
    setUploading(false);
    if (anySuccess) { onSourceAdded(); onClose(); }
  };

  // ── URL tab handler ───────────────────────────────────────────────────────

  const handleUrlSubmit = async () => {
    const urls = urlText.split('\n').map(u => u.trim()).filter(Boolean);
    if (urls.length === 0) return;
    setCrawling(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/scrape-urls`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to start crawl');
      }
      onClose();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setCrawling(false);
    }
  };

  // ── Paste tab handler ─────────────────────────────────────────────────────

  const handlePasteSubmit = async () => {
    if (!pasteContent.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/paste`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: pasteContent, name: pasteName || undefined }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to save');
      }
      onSourceAdded();
      onClose();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-0">
          <h2 className="text-lg font-semibold text-gray-900">Add Sources</h2>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-md hover:bg-gray-100 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200 mx-6 mt-4">
          {(['files', 'url', 'paste'] as Tab[]).map(tab => (
            <button
              key={tab}
              onClick={() => switchTab(tab)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                activeTab === tab
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab === 'files' ? '📁 Files' : tab === 'url' ? '🔗 URL' : '📋 Paste Text'}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="px-6 py-5 overflow-y-auto flex-1 min-h-0">

          {error && (
            <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
              {error}
            </div>
          )}

          {/* ── Files tab ── */}
          {activeTab === 'files' && (
            <div>
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                  isDragging
                    ? 'border-blue-400 bg-blue-50'
                    : 'border-gray-300 hover:border-gray-400 bg-gray-50'
                }`}
              >
                <Upload className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                <p className="text-sm font-medium text-gray-600">Drop files here or click to browse</p>
                <p className="text-xs text-gray-400 mt-1">PDF, TXT, MD, DOCX and more</p>
                <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileSelect} />
              </div>

              {selectedFiles.length > 0 && (
                <ul className="mt-3 space-y-1 max-h-48 overflow-y-auto">
                  {selectedFiles.map((file, i) => (
                    <li key={i} className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-md text-sm text-gray-700">
                      <FileText className="w-4 h-4 text-gray-400 shrink-0" />
                      <span className="truncate flex-1">{file.name}</span>
                      <button onClick={() => removeFile(i)} className="text-gray-400 hover:text-red-500 ml-auto transition-colors">
                        <X className="w-4 h-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <button
                onClick={handleFilesSubmit}
                disabled={selectedFiles.length === 0 || uploading}
                className="mt-4 w-full py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
              >
                {uploading
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> Uploading...</>
                  : `Upload ${selectedFiles.length > 0 ? selectedFiles.length + ' ' : ''}File${selectedFiles.length !== 1 ? 's' : ''}`
                }
              </button>
            </div>
          )}

          {/* ── URL tab ── */}
          {activeTab === 'url' && (
            <div>
              <textarea
                value={urlText}
                onChange={e => setUrlText(e.target.value)}
                placeholder={"https://example.com\nhttps://another-site.com\n\nOne URL per line"}
                className="w-full h-28 px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono text-gray-700 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-400 mt-1 mb-4">
                Each URL will be crawled and analyzed. Sources appear in the list when ready (~30–60s).
              </p>
              <button
                onClick={handleUrlSubmit}
                disabled={!urlText.trim() || crawling}
                className="w-full py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
              >
                {crawling ? <><Loader2 className="w-4 h-4 animate-spin" /> Starting...</> : 'Start Crawl'}
              </button>
            </div>
          )}

          {/* ── Paste tab ── */}
          {activeTab === 'paste' && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <label className="text-xs text-gray-500 whitespace-nowrap">Name (optional):</label>
                <input
                  type="text"
                  value={pasteName}
                  onChange={e => setPasteName(e.target.value)}
                  placeholder="Auto-generated if left blank"
                  className="flex-1 px-3 py-1.5 border border-gray-200 rounded-md text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <textarea
                value={pasteContent}
                onChange={e => setPasteContent(e.target.value)}
                placeholder="Paste your text here..."
                className="w-full h-36 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handlePasteSubmit}
                disabled={!pasteContent.trim() || saving}
                className="mt-4 w-full py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
              >
                {saving ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</> : 'Save as Source'}
              </button>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};

export default AddSourcesModal;
