/* useTickerSearch — the ONLY network call behind "tickers in the same ⌘K field".
 *
 * Ajay 2026-09-18, verbatim: "can you make global search help find ickers also
 * directly in the same field".
 *
 * It reads `/symbol-search` (backend/main.py:1122 — a Finnhub proxy, free tier,
 * 6 h server cache) and hands the body back UNTOUCHED. Shape-coercion and
 * ranking live in lib/tickerSearch, so a junk body can never reach the palette
 * through here.
 *
 * FAIL OPEN is the contract: the page half of the palette is synchronous and
 * must never wait on, be blanked by, or be thrown by this hook. Every failure
 * path — !ok, network error, bad JSON, timeout — ends at `status:'error'` with
 * `raw:null`, and the component keeps rendering pages.
 *
 * Cancellation is the SupportLevels.tsx:175-189 idiom (a `seq` generation ref +
 * an AbortController per run), not a third invention. The existing
 * GlobalStockSearch typeahead has no AbortController and CAN be overwritten by
 * a stale response — that bug is deliberately not copied here.
 */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';

/** Keystrokes closer together than this collapse into one request.
 *
 *  NOT MEASURED — a UX trade. The endpoint caches per distinct prefix
 *  (main.py:1135), so every prefix that escapes the debounce is its own cold
 *  provider call: at the 180 ms the existing typeahead uses, an 8-character
 *  ticker typed at a normal cadence is 7 requests. 300 ms collapses a
 *  ~220 ms/key cadence to one; a slower typist still fires per character.
 *  No interval fixes that outright. */
export const TICKER_DEBOUNCE_MS = 300;

/** A lookup that has not answered by here is treated as failed, not pending. */
export const TICKER_TIMEOUT_MS = 4000;

/** One character measured (2026-09-18) as unrelated large caps — `q=d` returned
 *  D, NVDA, AVGO, LLY. `q=""` is a 422, never an empty envelope. */
export const MIN_TICKER_QUERY_LEN = 2;

/** The effective lookup term: the FIRST token of what he typed, length-gated.
 *
 *  Finnhub does not phrase-match — "digital ocean" measured `{"results":[]}`
 *  while "digital" returns DOCN — so the first token is what gets asked. */
export function tickerQuery(raw: string): string {
  const first = (raw || '').trim().replace(/\s+/g, ' ').split(' ')[0] || '';
  return first.length >= MIN_TICKER_QUERY_LEN ? first : '';
}

export type TickerSearchState = {
  /** The parsed response body, verbatim. Never shape-checked here. */
  raw: unknown;
  status: 'idle' | 'loading' | 'done' | 'error';
  /** The effective query `raw` belongs to — '' while idle. */
  query: string;
};

const IDLE: TickerSearchState = { raw: null, status: 'idle', query: '' };

export function useTickerSearch(query: string, enabled: boolean): TickerSearchState {
  const q = tickerQuery(query);
  const [state, setState] = useState<TickerSearchState>(IDLE);
  const seq = useRef(0);

  // Keyed on the EFFECTIVE query, never the raw one: typing a trailing space,
  // or walking "digital" out to "digital ocean", must not re-fetch and must not
  // blank the rows already on screen.
  useEffect(() => {
    const my = ++seq.current;

    if (!enabled || !q) {
      setState((s) => (s.status === 'idle' ? s : IDLE));
      return;
    }

    // Only reached when the effective query actually changed, so clearing `raw`
    // here cannot blank a still-valid result.
    setState({ raw: null, status: 'loading', query: q });

    let timedOut = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    const ctl = new AbortController();

    const debounceId = setTimeout(() => {
      timeoutId = setTimeout(() => { timedOut = true; ctl.abort(); }, TICKER_TIMEOUT_MS);
      void (async () => {
        try {
          // Plain fetch — installAuthRedirect patches window.fetch to inject
          // credentials; setting them by hand would skip that branch.
          const r = await fetch(`${API}/symbol-search?q=${encodeURIComponent(q)}`, { signal: ctl.signal });
          if (!r || !r.ok) throw new Error(`symbol-search ${r ? r.status : 'no response'}`);
          const body = await r.json();
          if (my !== seq.current) return;
          setState({ raw: body, status: 'done', query: q });
        } catch (e: any) {
          if (my !== seq.current) return;
          // A supersede / unmount abort must set NOTHING. A timeout abort is a
          // real failure and says so.
          if (e?.name === 'AbortError' && !timedOut) return;
          setState({ raw: null, status: 'error', query: q });
        } finally {
          if (timeoutId) clearTimeout(timeoutId);
        }
      })();
    }, TICKER_DEBOUNCE_MS);

    return () => {
      clearTimeout(debounceId);
      if (timeoutId) clearTimeout(timeoutId);
      ctl.abort();
    };
  }, [q, enabled]);

  return state;
}
