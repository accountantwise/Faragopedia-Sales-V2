import React, { useEffect, useState } from 'react';
import { X, RefreshCw, Download, Settings } from 'lucide-react';
import { API_BASE } from '../config';

interface SettingsDrawerProps {
  open: boolean;
  onClose: () => void;
  theme: 'light' | 'dark' | 'system';
  onThemeChange: (t: 'light' | 'dark' | 'system') => void;
  onReconfigure: () => void;
}

const THEMES: { value: 'light' | 'dark' | 'system'; label: string }[] = [
  { value: 'light', label: '☀ Light' },
  { value: 'system', label: '◑ System' },
  { value: 'dark', label: '● Dark' },
];

const SettingsDrawer: React.FC<SettingsDrawerProps> = ({
  open,
  onClose,
  theme,
  onThemeChange,
  onReconfigure,
}) => {
  const [wikiName, setWikiName] = useState('');
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (open && !wikiName) {
      fetch(`${API_BASE}/setup/config`)
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data?.wiki_name) setWikiName(data.wiki_name); })
        .catch(() => {});
    }
  }, [open, wikiName]);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const res = await fetch(`${API_BASE}/export/bundle`);
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'wiki-bundle.zip';
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/40 z-40"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={`fixed inset-y-0 z-50 w-80 bg-white dark:bg-gray-900 shadow-2xl flex flex-col transition-all duration-300 ease-in-out ${
          open ? 'right-0 visible' : 'right-[-320px] invisible pointer-events-none'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 font-semibold text-gray-900 dark:text-gray-100">
            <Settings className="w-4 h-4" />
            Settings
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">

          {/* Appearance */}
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-3">
              Appearance
            </p>
            <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-4">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Theme</p>
              <div className="flex bg-gray-200 dark:bg-gray-700 rounded-lg p-1 gap-1">
                {THEMES.map(t => (
                  <button
                    key={t.value}
                    onClick={() => onThemeChange(t.value)}
                    className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-all ${
                      theme === t.value
                        ? 'bg-blue-600 text-white shadow'
                        : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Wiki */}
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-3">
              Wiki
            </p>
            <button
              onClick={onReconfigure}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors text-sm"
            >
              <RefreshCw className="w-4 h-4" />
              Reconfigure Wiki
            </button>
          </div>

          {/* Export */}
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-3">
              Export
            </p>
            <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-4">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Wiki infrastructure files
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mb-4">
                SCHEMA.md · index.md · log.md · company_profile.md · wiki_config.json
              </p>
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors text-sm font-medium"
              >
                <Download className="w-4 h-4" />
                {downloading ? 'Downloading…' : 'Download as .zip'}
              </button>
            </div>
          </div>

        </div>

        {/* Footer */}
        {wikiName && (
          <div className="px-5 py-3 border-t border-gray-100 dark:border-gray-800">
            <p className="text-xs text-gray-400 dark:text-gray-600">{wikiName}</p>
          </div>
        )}
      </div>
    </>
  );
};

export default SettingsDrawer;
