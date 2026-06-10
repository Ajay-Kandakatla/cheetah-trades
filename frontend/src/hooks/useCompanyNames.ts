/* useCompanyNames — the app-wide {SYMBOL → company name} map, fetched ONCE per
 * session from /sepa/company-names (~6k cached names, warmed daily). Powers the
 * tiny name label under every clickable ticker (Ajay 2026-06-10). Module-level
 * cache + in-flight dedup: dozens of TickerLinks mounting at once produce one
 * request. Fails quiet — tickers render without names if the fetch dies. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

let cache: Map<string, string> | null = null;
let inflight: Promise<Map<string, string>> | null = null;
const listeners = new Set<(m: Map<string, string>) => void>();

function fetchNames(): Promise<Map<string, string>> {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = fetch(`${API}/sepa/company-names`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => {
        const m = new Map<string, string>();
        for (const [sym, name] of Object.entries(d?.names || {})) {
          if (typeof name === 'string' && name) m.set(sym.toUpperCase(), name);
        }
        cache = m;
        listeners.forEach((fn) => fn(m));
        return m;
      })
      .finally(() => { inflight = null; });
  }
  return inflight;
}

export function useCompanyNames(): Map<string, string> {
  const [names, setNames] = useState<Map<string, string>>(cache || new Map());
  useEffect(() => {
    let alive = true;
    const on = (m: Map<string, string>) => { if (alive) setNames(m); };
    listeners.add(on);
    if (!cache) fetchNames().catch(() => undefined);
    return () => { alive = false; listeners.delete(on); };
  }, []);
  return names;
}
