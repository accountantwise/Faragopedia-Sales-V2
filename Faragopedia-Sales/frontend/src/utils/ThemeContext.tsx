import React, { createContext, useContext, useEffect, useState } from 'react';

export type ThemeMode = 'light' | 'dark' | 'system';
export type ColorTheme = 'default' | 'linear' | 'oceanic';

interface ThemeContextType {
  mode: ThemeMode;
  theme: ColorTheme;
  setMode: (mode: ThemeMode) => void;
  setTheme: (theme: ColorTheme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mode, setMode] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem('fp-theme-mode');
    return (saved as ThemeMode) || 'system';
  });

  const [theme, setTheme] = useState<ColorTheme>(() => {
    const saved = localStorage.getItem('fp-color-theme');
    return (saved as ColorTheme) || 'default';
  });

  useEffect(() => {
    localStorage.setItem('fp-theme-mode', mode);
  }, [mode]);

  useEffect(() => {
    localStorage.setItem('fp-color-theme', theme);
  }, [theme]);

  useEffect(() => {
    const root = window.document.documentElement;
    
    // Handle Mode (Light/Dark)
    const applyMode = () => {
      root.classList.remove('light', 'dark');
      if (mode === 'system') {
        const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        root.classList.add(systemPrefersDark ? 'dark' : 'light');
      } else {
        root.classList.add(mode);
      }
    };

    applyMode();

    // Listen for system changes if mode is 'system'
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      if (mode === 'system') applyMode();
    };
    
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [mode]);

  useEffect(() => {
    const root = window.document.documentElement;
    // Handle Color Theme
    root.classList.remove('theme-default', 'theme-linear', 'theme-oceanic');
    root.classList.add(`theme-${theme}`);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ mode, theme, setMode, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
