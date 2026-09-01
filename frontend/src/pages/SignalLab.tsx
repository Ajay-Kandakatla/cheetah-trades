/* Signal Lab — Ajay's own tickers on 1-minute candles with BUY/SELL tags.
 *
 * Ajay 2026-09-01: "calculate entries with a buy or sell indicator on a
 * stock ticker I add to a new page ... interface like GainzAlgo ... same
 * concepts from what we build with ORB, Liquidity grab, BOS ... custom
 * tickers on demand like the session tab but more real time feedback."
 *
 * Presentation borrows GainzAlgo's UI conventions (BUY/SELL labels printed
 * at the signal candle, stop/target attached, non-repainting closed-bar
 * signals). The math is this app's own — daytrading/signal_lab.py — and
 * SMC stays flagged as uncited convention.
 *
 * Realtime = polling: 1-minute candles close once a minute, so the board
 * refreshes every 45s while a session is on (premarket/regular/afterhours)
 * and sits still when the market is closed. Whoever asked LAST owns the
 * screen (the Support-tab race lesson, 2026-08-31).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { PatternChart } from '../components/PatternChart';
import { SymbolSearch } from '../components/SymbolSearch';
import type { CmTile } from '../lib/chartMaps';

type Feed = {
  t: string; kind: string; label: string;
  price?: number | null; stop?: number | null; target?: number | null; why: string;
};
type Row = {
  symbol: string; error?: string; tile?: CmTile; feed?: Feed[];
  latest?: Feed | null; session?: string; last_bar_et?: string;
};
type Payload = {
  rows: Row[]; count: number; session_state: string;
  method_note: string; as_of: string;
};

const POLL_MS = 45_000;
const LS_KEY = 'signal-lab-symbols';

function loadLocal(): string[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.filter((s) => typeof s === 'string') : [];
  } catch { return []; }
}
function saveLocal(syms: string[]) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(syms)); } catch { /* private mode */ }
}

export function SignalLabPage() {
  const [symbols, setSymbols] = useState<string[]>(() => loadLocal());
  const [data, setData] = useState<Payload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const seq = useRef(0);
  const timer = useRef<number | null>(null);

  // server watchlist wins over localStorage once it answers — the list
  // follows him across browsers; localStorage is the offline fallback
  useEffect(() => {
    const my = ++seq.current;
    fetch(`${API}/day/signal-lab/watchlist`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (my !== seq.current || !j) return;
        if (Array.isArray(j.symbols) && j.symbols.length) {
          setSymbols(j.symbols); saveLocal(j.symbols);
        }
      })
      .catch(() => { /* localStorage list stands */ });
  }, []);

  const load = useCallback((quiet = false) => {
    if (!symbols.length) { setData(null); return; }
    const my = ++seq.current;
    if (!quiet) setLoading(true);
    fetch(`${API}/day/signal-lab/board?symbols=${encodeURIComponent(symbols.join(','))}`,
          { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j: Payload) => {
        if (my !== seq.current) return;
        setData(j); setErr(null); setLoading(false);
      })
      .catch((e) => {
        if (my !== seq.current) return;
        setErr(String(e?.message ?? e)); setLoading(false);
      });
  }, [symbols]);

  useEffect(() => { load(); }, [load]);

  // poll only while a session is on — closed tape produces no new closed bars
  useEffect(() => {
    if (timer.current) window.clearInterval(timer.current);
    if (!data || data.session_state === 'closed') return undefined;
    timer.current = window.setInterval(() => load(true), POLL_MS);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [data?.session_state, load]);

  const add = (sym: string) => {
    const s = sym.trim().toUpperCase();
    if (!s || symbols.includes(s)) return;
    const next = [...symbols, s].slice(-12);
    setSymbols(next); saveLocal(next);
    fetch(`${API}/day/signal-lab/watchlist/${encodeURIComponent(s)}`,
          { method: 'POST', credentials: 'include' }).catch(() => {});
  };
  const remove = (sym: string) => {
    const next = symbols.filter((x) => x !== sym);
    setSymbols(next); saveLocal(next);
    fetch(`${API}/day/signal-lab/watchlist/${encodeURIComponent(sym)}`,
          { method: 'DELETE', credentials: 'include' }).catch(() => {});
  };

  return (
    <div className="cm-page">
      <header className="cm-pagehead">
        <div className="cm-pagehead__col">
          <div className="eyebrow">1-minute entries</div>
          <h1 className="display cm-pagehead__title">⚡ Signal Lab</h1>
          <p className="lede">
            Your tickers, live BUY / SELL tags on 1-minute candles — the
            opening range, liquidity sweeps and BOS/CHoCH structure this app
            already computes, composed into the five-step entry. Signals fire
            on closed bars only and never repaint.
          </p>
        </div>
      </header>

      <div className="slab-controls">
        <SymbolSearch onAdd={add} placeholder="Add a ticker to watch — e.g. TSLA, IREN, SNDK" />
        <div className="slab-chips">
          {symbols.map((s) => (
            <span key={s} className="slab-chip">
              {s}
              <button type="button" className="slab-chip__x" aria-label={`Remove ${s}`}
                      onClick={() => remove(s)}>×</button>
            </span>
          ))}
        </div>
      </div>

      {!symbols.length ? (
        <div className="cm-note">Add a ticker above — the board watches up to 12 at once.</div>
      ) : null}
      {loading && !data ? <div className="cm-note">Reading the tape…</div> : null}
      {err ? <div className="cm-note cm-note-warn">Signal lab unavailable: {err}</div> : null}

      {data ? (
        <>
          <div className="slab-meta">
            <span className={`slab-state slab-state--${data.session_state}`}>
              {data.session_state === 'regular' ? 'LIVE — refreshing every 45s'
                : data.session_state === 'closed' ? 'MARKET CLOSED — last session shown'
                : `${data.session_state.toUpperCase()} — refreshing every 45s`}
            </span>
          </div>
          <div className="cm-grid">
            {data.rows.map((r) => r.tile ? (
              <div key={r.symbol} className="slab-cell">
                <PatternChart tile={r.tile} tvTf="daily" />
                {r.latest ? (
                  <div className={`slab-latest slab-latest--${r.latest.kind}`}>
                    <b>{r.latest.label}</b> {r.latest.t} @ ${r.latest.price?.toFixed(2)}
                    {r.latest.stop != null ? <> · stop ${r.latest.stop.toFixed(2)}</> : null}
                    {r.latest.target != null ? <> · target ${r.latest.target.toFixed(2)}</> : null}
                  </div>
                ) : (
                  <div className="slab-latest slab-latest--none">no entry signal this session</div>
                )}
                <ul className="slab-feed">
                  {(r.feed || []).slice(0, 5).map((f, i) => (
                    <li key={`${f.t}-${f.kind}-${i}`} className={`slab-feed__row slab-feed__row--${f.kind}`}>
                      <span className="mono">{f.t}</span>
                      <b>{f.label}</b>
                      <span className="slab-feed__why">{f.why}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div key={r.symbol} className="cm-note cm-note-warn">
                {r.symbol}: {r.error || 'no data'}
              </div>
            ))}
          </div>
          <p className="rw__note">{data.method_note}</p>
        </>
      ) : null}
    </div>
  );
}
