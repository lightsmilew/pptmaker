// Navigation bar component - Soft UI Style

import { Home } from 'lucide-react';
import { Button } from '@/components/ui';

interface NavBarProps {
  projectName?: string;
  onHome?: () => void;
}

export function NavBar({ projectName, onHome }: NavBarProps) {
  return (
    <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-xl border-b border-transparent shadow-soft-sm">
      <div className="max-w-6xl mx-auto px-4 md:px-6 lg:px-8">
        <div className="h-16 flex items-center justify-between">
          {/* Logo & Title */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center shadow-soft-indigo">
              <img
                src="/ppt-agent-icon.svg"
                alt="PPTMaker"
                className="w-6 h-6 object-contain"
              />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-gray-800">PPTMaker</h1>
              {projectName && (
                <p className="text-xs text-gray-400 truncate max-w-[200px]">{projectName}</p>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            {onHome && (
              <Button variant="ghost" size="sm" onClick={onHome}>
                <Home className="w-4 h-4 mr-1.5" />
                <span className="hidden sm:inline">首页</span>
              </Button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
