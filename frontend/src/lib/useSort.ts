/* useSort — tiny shared client-side sorter for the Day Trading / Scalping
 * tables (Ajay 2026-06-10: "tables to be sortable"). Same semantics as the
 * SepaRankLeaderboard sort bar: click a key to sort, click again to flip;
 * nulls always sink to the bottom regardless of direction. */
import { useMemo, useState } from 'react';

export type SortDir = 'asc' | 'desc';
type Getter<T> = (row: T) => number | string | null | undefined;

export function useSort<T>(rows: T[], getters: Record<string, Getter<T>>,
                           defaultKey: string, defaultDir: SortDir = 'desc') {
  const [key, setKey] = useState(defaultKey);
  const [dir, setDir] = useState<SortDir>(defaultDir);

  const sorted = useMemo(() => {
    const get = getters[key];
    if (!get) return rows;
    return [...rows].sort((a, b) => {
      const av = get(a), bv = get(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;                  // nulls last, both directions
      if (bv == null) return -1;
      const cmp = typeof av === 'string'
        ? av.localeCompare(String(bv))
        : (av as number) - (bv as number);
      return dir === 'asc' ? cmp : -cmp;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, key, dir]);

  const toggle = (k: string, preferred: SortDir = 'desc') => {
    if (k === key) setDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setKey(k); setDir(preferred); }
  };
  const arrow = (k: string) => (k === key ? (dir === 'asc' ? ' ▲' : ' ▼') : '');

  return { sorted, key, dir, toggle, arrow };
}
