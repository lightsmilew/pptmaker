import { Home } from 'lucide-react';
import { Button } from '@/components/ui';
import { Brand } from './StudioShell';
export function NavBar({ projectName, onHome }: { projectName?:string; onHome?:()=>void }) {
 return <header className="studio-topbar"><Brand /><span>{projectName}</span>{onHome && <Button variant="ghost" size="sm" onClick={onHome}><Home size={14} />首页</Button>}</header>;
}
