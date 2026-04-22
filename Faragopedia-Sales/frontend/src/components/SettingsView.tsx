import React from 'react';
import { useTheme } from '../utils/ThemeContext';
import { Sun, Moon, Monitor, Palette } from 'lucide-react';

const SettingsView: React.FC = () => {
  const { mode, theme, setMode, setTheme } = useTheme();

  return (
    <div className="p-8 max-w-4xl mx-auto w-full h-full overflow-y-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-base mb-2">Settings</h1>
        <p className="text-text-muted">Manage your application appearance and preferences.</p>
      </div>

      <div className="space-y-8">
        {/* Appearance Mode */}
        <section className="bg-bg-elevated p-6 rounded-2xl shadow-sm border border-border-color">
          <h2 className="text-xl font-semibold text-text-base mb-4 flex items-center gap-2">
            <Monitor className="w-5 h-5 text-text-muted" />
            Appearance Mode
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button
              onClick={() => setMode('light')}
              className={`p-4 rounded-xl border-2 flex flex-col items-center justify-center gap-3 transition-all ${
                mode === 'light' ? 'border-primary bg-primary/5 text-primary' : 'border-border-color text-text-muted hover:border-text-muted'
              }`}
            >
              <Sun className="w-8 h-8" />
              <span className="font-medium">Light</span>
            </button>
            <button
              onClick={() => setMode('dark')}
              className={`p-4 rounded-xl border-2 flex flex-col items-center justify-center gap-3 transition-all ${
                mode === 'dark' ? 'border-primary bg-primary/5 text-primary' : 'border-border-color text-text-muted hover:border-text-muted'
              }`}
            >
              <Moon className="w-8 h-8" />
              <span className="font-medium">Dark</span>
            </button>
            <button
              onClick={() => setMode('system')}
              className={`p-4 rounded-xl border-2 flex flex-col items-center justify-center gap-3 transition-all ${
                mode === 'system' ? 'border-primary bg-primary/5 text-primary' : 'border-border-color text-text-muted hover:border-text-muted'
              }`}
            >
              <Monitor className="w-8 h-8" />
              <span className="font-medium">System</span>
            </button>
          </div>
        </section>

        {/* Color Theme */}
        <section className="bg-bg-elevated p-6 rounded-2xl shadow-sm border border-border-color">
          <h2 className="text-xl font-semibold text-text-base mb-4 flex items-center gap-2">
            <Palette className="w-5 h-5 text-text-muted" />
            Color Theme
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button
              onClick={() => setTheme('default')}
              className={`p-4 rounded-xl border-2 flex items-center gap-3 transition-all ${
                theme === 'default' ? 'border-primary bg-primary/5' : 'border-border-color hover:border-text-muted'
              }`}
            >
              <div className="w-8 h-8 rounded-full bg-blue-600 shadow-inner"></div>
              <div className="text-left">
                <div className={`font-medium ${theme === 'default' ? 'text-primary' : 'text-text-base'}`}>Classic Blue</div>
                <div className="text-xs text-text-muted">GitHub / Vercel style</div>
              </div>
            </button>
            <button
              onClick={() => setTheme('linear')}
              className={`p-4 rounded-xl border-2 flex items-center gap-3 transition-all ${
                theme === 'linear' ? 'border-primary bg-primary/5' : 'border-border-color hover:border-text-muted'
              }`}
            >
              <div className="w-8 h-8 rounded-full bg-purple-600 shadow-inner"></div>
              <div className="text-left">
                <div className={`font-medium ${theme === 'linear' ? 'text-primary' : 'text-text-base'}`}>Amethyst</div>
                <div className="text-xs text-text-muted">Linear / Discord style</div>
              </div>
            </button>
            <button
              onClick={() => setTheme('oceanic')}
              className={`p-4 rounded-xl border-2 flex items-center gap-3 transition-all ${
                theme === 'oceanic' ? 'border-primary bg-primary/5' : 'border-border-color hover:border-text-muted'
              }`}
            >
              <div className="w-8 h-8 rounded-full bg-teal-600 shadow-inner"></div>
              <div className="text-left">
                <div className={`font-medium ${theme === 'oceanic' ? 'text-primary' : 'text-text-base'}`}>Oceanic</div>
                <div className="text-xs text-text-muted">Stripe / Tailwind style</div>
              </div>
            </button>
          </div>
        </section>
      </div>
    </div>
  );
};

export default SettingsView;
