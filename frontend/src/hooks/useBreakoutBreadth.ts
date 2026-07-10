/* useBreakoutBreadth — GET /sepa/breakout-breadth for the Breakouts strip. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import type { BreadthData } from '../lib/breakoutBreadth';

export function useBreakoutBreadth(days = 30) {
  const [data, setData] = useState<BreadthData | null>(null);
  useEffect(() => {
    let alive = true;
    fetch(`${API}/sepa/breakout-breadth?days=${days}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive) setData(j); })
      .catch(() => { if (alive) setData(null); });
    return () => { alive = false; };
  }, [days]);
  return data;
}
