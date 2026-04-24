import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check, Plus } from 'lucide-react';

interface Workspace {
  id: string;
  name: string;
}

interface WorkspaceSwitcherProps {
  workspaces: Workspace[];
  activeWorkspaceId: string;
  onSwitch: (id: string) => void;
  onNewWorkspace: () => void;
}

const WorkspaceSwitcher: React.FC<WorkspaceSwitcherProps> = ({
  workspaces,
  activeWorkspaceId,
  onSwitch,
  onNewWorkspace,
}) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const activeWs = workspaces.find(ws => ws.id === activeWorkspaceId);
  const displayName = activeWs?.name ?? 'Workspace';

  return (
    <div ref={ref} className="relative">
      {/* Trigger button */}
      <button
        onClick={() => setOpen(prev => !prev)}
        className="w-full flex items-center gap-3 px-6 py-4 text-left hover:bg-gray-700 transition-colors border-b border-gray-700"
      >
        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-sm font-bold shrink-0">
          {displayName.slice(0, 2).toUpperCase()}
        </div>
        <span className="flex-grow font-bold text-xl truncate">{displayName}</span>
        <ChevronDown
          className={`w-4 h-4 text-gray-400 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute left-0 right-0 bg-gray-700 border border-gray-600 rounded-b-lg shadow-xl z-50 overflow-hidden">
          {workspaces.map(ws => (
            <button
              key={ws.id}
              onClick={() => {
                onSwitch(ws.id);
                setOpen(false);
              }}
              className="w-full flex items-center justify-between px-4 py-3 text-left text-sm hover:bg-gray-600 transition-colors"
            >
              <span className="truncate">{ws.name}</span>
              {ws.id === activeWorkspaceId && (
                <Check className="w-4 h-4 text-blue-400 shrink-0 ml-2" />
              )}
            </button>
          ))}
          <div className="border-t border-gray-600">
            <button
              onClick={() => {
                onNewWorkspace();
                setOpen(false);
              }}
              className="w-full flex items-center gap-2 px-4 py-3 text-sm text-blue-400 hover:bg-gray-600 transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Workspace
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default WorkspaceSwitcher;
