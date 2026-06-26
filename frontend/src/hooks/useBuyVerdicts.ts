/* useBuyVerdicts — batch Cheetah-Verdict (Minervini SEPA + Bonde) for a set of
 * symbols, so the Auto-Pilot positions table and the Portfolio cards show the
 * same buy verdict the Analysis tab shows, per holding. One request for the
 * whole set; cache-first on the backend with a bounded on-demand fallback. */
import { useEffect, useMemo, useState } from 'react';
import { API } from '../lib/apiBase';
import { verdictsKey, type SlimVerdict } from '../lib/buyVerdicts';

export function useBuyVerdicts(symbols: string[]) {
  const key = useMemo(() => verdictsKey(symbols), [symbols.join('|')]);
  const [verdicts, setVerdicts] = useState<Map<string, SlimVerdict | null>>(new Map());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!key) { setVerdicts(new Map()); return; }
    let alive = true;
    setLoading(true);
    fetch(`${API}/sepa/verdicts?symbols=${encodeURIComponent(key)}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (!alive) return;
        const m = new Map<string, SlimVerdict | null>();
        const v = (j && j.verdicts) || {};
        for (const sym of Object.keys(v)) m.set(sym, v[sym]);
        setVerdicts(m);
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [key]);

  return { verdicts, loading };
}
