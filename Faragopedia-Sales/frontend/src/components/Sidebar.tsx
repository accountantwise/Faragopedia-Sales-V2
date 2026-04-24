import React from 'react';
import { Book, MessageSquare, Layers, Archive, Activity, Settings } from 'lucide-react';
import WorkspaceSwitcher from './WorkspaceSwitcher';

interface SidebarProps {
  currentView: string;
  onViewChange: (view: string) => void;
  wikiName: string;
  onOpenSettings: () => void;
  // new:
  workspaces: { id: string; name: string }[];
  activeWorkspaceId: string;
  onSwitchWorkspace: (id: string) => void;
  onNewWorkspace: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ currentView, onViewChange, wikiName, onOpenSettings, workspaces, activeWorkspaceId, onSwitchWorkspace, onNewWorkspace }) => {
  const menuItems = [
    { name: 'Wiki', icon: <Book className="w-5 h-5" /> },
    { name: 'Sources', icon: <Layers className="w-5 h-5" /> },
    { name: 'Chat', icon: <MessageSquare className="w-5 h-5" /> },
    { name: 'Archive', icon: <Archive className="w-5 h-5" /> },
    { name: 'Lint', icon: <Activity className="w-5 h-5" /> },
  ];

  return (
    <div className="flex flex-col h-screen w-64 bg-gray-800 text-white shadow-xl">
      <WorkspaceSwitcher
        workspaces={workspaces}
        activeWorkspaceId={activeWorkspaceId}
        onSwitch={onSwitchWorkspace}
        onNewWorkspace={onNewWorkspace}
      />

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

      <div className="p-4 border-t border-gray-700 flex items-center justify-between">
        <p className="text-xs text-gray-500 uppercase tracking-wider">{wikiName} v0.2.0</p>
        <button
          onClick={onOpenSettings}
          title="Settings"
          className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
        >
          <Settings className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
};

export default Sidebar;
