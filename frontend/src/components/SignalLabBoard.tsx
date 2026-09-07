/* SignalLabBoard — the Signal Lab's working surface (controls + tiles +
 * feeds), shared by the standalone /signal-lab page and the Chart Maps
 * ⚡ Signals tab (Ajay 2026-09-01: "add the signals tab inside chart maps").
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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { useSignalWatchlist } from '../hooks/useSignalWatchlist';
import { PatternChart } from './PatternChart';
import { SymbolSearch } from './SymbolSearch';
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
export function SignalLabBoard() {
  // ONE watchlist for the app (Ajay 2026-09-07: "one click and add to signals
  // tab" from every board) — the store fetches the account's list once, the
  // cards' + Signals buttons write to it, this board renders it.
  const wl = useSignalWatchlist();
  const symbols = wl.symbols;
  const held = useMemo(() => new Set(wl.held), [wl.held]);
  const [data, setData] = useState<Payload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const seq = useRef(0);
  const timer = useRef<number | null>(null);

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

  const add = wl.add;
  const remove = wl.remove;

  return (
    <div className="slab">
      <div className="slab-controls">
        <SymbolSearch onAdd={add} placeholder="Add a ticker to watch — e.g. TSLA, IREN, SNDK" />
        <div className="slab-chips">
          {symbols.map((s) => (
            <span key={s} className="slab-chip" title={held.has(s) ? 'In your portfolio — rides the board by default' : undefined}>
              {held.has(s) ? '💼 ' : ''}{s}
              {held.has(s) ? null : (
                <button type="button" className="slab-chip__x" aria-label={`Remove ${s}`}
                        onClick={() => remove(s)}>×</button>
              )}
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
