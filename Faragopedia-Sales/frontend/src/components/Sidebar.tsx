import React from 'react';
import { Book, MessageSquare, Layers, Archive, Activity, Settings } from 'lucide-react';

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
  ];

  return (
    <div className="flex flex-col h-screen w-64 bg-gray-800 text-white shadow-xl">
      <div className="p-6 text-2xl font-bold border-b border-gray-700 flex items-center">
        <div className="w-8 h-8 bg-blue-600 rounded-lg mr-3 flex items-center justify-center text-sm">
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
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
                    : 'hover:bg-gray-700 text-gray-300 hover:text-white'
                }`}
              >
                {item.icon}
                <span className="font-medium">{item.name}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="p-4 border-t border-gray-700 space-y-2">
        <button
          onClick={onReconfigure}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700 text-sm transition-colors"
        >
          <Settings className="w-4 h-4" />
          Reconfigure Wiki
        </button>
        <p className="text-xs text-gray-500 text-center uppercase tracking-wider">
          {wikiName} v0.2.0
        </p>
      </div>
    </div>
  );
};

export default Sidebar;
