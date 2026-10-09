import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import type { DesignCatalog } from '@/types/design';
export function useDesignCatalog() {
  const [catalog, setCatalog] = useState<DesignCatalog | null>(null);
  const [error, setError] = useState(''); const [revision, setRevision] = useState(0);
  useEffect(() => {
    let current = true; setError('');
    api.getDesignCatalog().then(data => { if (current) setCatalog(data); }).catch(e => { if (current) setError((e as Error).message); });
    return () => { current = false; };
  }, [revision]);
  return { catalog, error, retry: () => setRevision(r => r + 1) };
}
