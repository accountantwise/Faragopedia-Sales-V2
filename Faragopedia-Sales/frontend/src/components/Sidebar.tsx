import React from 'react';
import { Book, MessageSquare, Layers, Archive, Activity, Settings, RefreshCw } from 'lucide-react';

interface SidebarProps {
  currentView: string;
  onViewChange: (view: string) => void;
  wikiName: string;
  onReconfigure: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ currentView, onViewChange, wikiName, onReconfigure }) => {
  const menuItems = [
    { name: 'Wiki', icon: <Book className="w-5 h-5" /> },
    { name: 'Sources', icon: <Layers className="w-5 h-5" /> },
    { name: 'Chat', icon: <MessageSquare className="w-5 h-5" /> },
    { name: 'Archive', icon: <Archive className="w-5 h-5" /> },
    { name: 'Lint', icon: <Activity className="w-5 h-5" /> },
    { name: 'Settings', icon: <Settings className="w-5 h-5" /> },
  ];

  return (
    <div className="flex flex-col h-screen w-64 bg-bg-sidebar text-white shadow-xl">
      <div className="p-6 text-2xl font-bold border-b border-white/10 flex items-center">
        <div className="w-8 h-8 bg-primary rounded-lg mr-3 flex items-center justify-center text-sm transition-colors">
          {wikiName.slice(0, 2).toUpperCase()}
        </div>
        {wikiName}
      </div>

      <nav className="flex-grow p-4">
        <ul className="space-y-2">
          {menuItems.map((item) => (
            <li key={item.name}>
              <button
                onClick={() => onViewChange(item.name)}
                className={`w-full text-left px-4 py-3 rounded-lg transition-all duration-200 flex items-center space-x-3 ${
                  currentView === item.name
                    ? 'bg-primary text-white shadow-lg opacity-100'
                    : 'hover:bg-white/10 text-gray-300 hover:text-white'
                }`}
              >
                {item.icon}
                <span className="font-medium">{item.name}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="p-4 border-t border-white/10 space-y-2">
        <button
          onClick={onReconfigure}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 text-sm transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Reconfigure Wiki
        </button>
        <p className="text-xs text-gray-400 text-center uppercase tracking-wider">
          {wikiName} v0.2.0
        </p>
      </div>
    </div>
  );
};

export default Sidebar;
