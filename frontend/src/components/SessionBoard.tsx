/* SessionBoard — the Session tab on /chart-maps.
 *
 * Ajay 2026-08-31: "a tab for ORB/ FVG/ Bullish sentiment or bearish for all
 * the onces in demand zone. and deep demand zones ... I will use this tab
 * after market open to figure out market sentiment."
 *
 * The daily boards answer WHICH NAMES. This answers whether the session is
 * confirming the daily band that listed them. Rows, not chart tiles: this is a
 * scan-99-names-fast surface, and 99 sparklines is a slower read than 99 lines
 * of text (same declutter call as the scanner card).
 *
 * All numbers come from backend/supply_demand/session_board.py; everything
 * shaped here lives in ../lib/sessionBoard so it can be tested without a DOM.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { PatternChart } from './PatternChart';
import OverlayLegend from './OverlayLegend';
import { filterTile, loadHidden, presentGroups, saveHidden } from '../lib/chartOverlays';
import {
  BIAS_META, BIAS_ORDER, biasTally, filterRows, sessionLabel,
} from '../lib/sessionBoard';
import type { Bias, SessionPayload, SessionRow } from '../lib/sessionBoard';

const POLL_MS = 6000;

function toneColor(tone: string): string {
  if (tone === 'good') return 'var(--cm-green, #22c55e)';
  if (tone === 'poor') return 'var(--cm-red, #dc2626)';
  return 'var(--cm-slate, #8595ad)';
}

export default function SessionBoard({ onPick }: { onPick?: (sym: string) => void }) {
  const [tf, setTf] = useState<string>('15m');
  const [bias, setBias] = useState<Bias | 'all'>('all');
  const [atBandOnly, setAtBandOnly] = useState(false);
  const [setupsOnly, setSetupsOnly] = useState(false);
  const [data, setData] = useState<SessionPayload | null>(null);
  const [hiddenOverlays, setHiddenOverlays] = useState<Set<string>>(() => loadHidden());
  const toggleOverlay = (key: string) => {
    setHiddenOverlays((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      saveHidden(next);
      return next;
    });
  };
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const timer = useRef<number | null>(null);

  const load = useCallback((quiet = false) => {
    if (!quiet) setLoading(true);
    fetch(`${API}/supply-demand/session-board?tf=${encodeURIComponent(tf)}`,
          { credentials: 'include' })
      .then((r) => r.json())
      .then((d: SessionPayload) => { setData(d); setErr(null); setLoading(false); })
      .catch((e) => { setErr(String((e as Error).message || e)); setLoading(false); });
  }, [tf]);

  useEffect(() => { load(); }, [load]);

  // Poll only while a pass is warming. A board that re-fetched on a timer all
  // session would re-read 99 names every tick for no new information — the
  // server cache is 3 minutes wide and says its own age.
  useEffect(() => {
    if (timer.current) { window.clearInterval(timer.current); timer.current = null; }
    if (data?.warming) {
      timer.current = window.setInterval(() => load(true), POLL_MS);
    }
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [data?.warming, load]);

  const rows = data?.rows || [];
  const tally = useMemo(() => biasTally(rows), [rows]);
  const shown = useMemo(() => filterRows(rows, bias, atBandOnly, setupsOnly),
                        [rows, bias, atBandOnly, setupsOnly]);

  // Three states, three banners. Before the payload arrives we know NOTHING
  // about the session, and the first build claimed "Market is closed" during
  // load — at 09:40 on a Monday (Ajay's screenshot, 2026-08-31). Loading and
  // warming are neutral; only a real payload gets to make claims.
  const pending = !data || data.warming;
  const liveClass = pending ? 'cm-session'
    : data.live ? 'cm-session cm-session-open' : 'cm-session cm-session-closed';

  return (
    <div className="sb">
      <div className={liveClass}>
        <strong>
          {!data ? 'loading…' : data.warming && !data.count ? 'reading the session…'
            : sessionLabel(data)}
        </strong>
        <span>
          {!data ? ''
            : data.warming && !data.count
              ? 'First pass across the demand boards — a cold read takes a couple of minutes.'
              : data.live
                ? 'Reading the session as it runs.'
                : 'Market is closed — this is the last completed session.'}
        </span>
        {!!rows.length && (
          <span className="cm-session-counts">
            {BIAS_ORDER.filter((b) => tally[b]).map((b) => (
              <span key={b} style={{ marginRight: '0.9rem', color: toneColor(BIAS_META[b].tone) }}>
                {BIAS_META[b].dot} {tally[b]} {BIAS_META[b].label.toLowerCase()}
              </span>
            ))}
            <span style={{ opacity: 0.8 }}>
              · {rows.length} names from Back in Demand + Deep Demand
              {data?.age_sec != null ? ` · read ${Math.round(data.age_sec)}s ago` : ''}
              {data?.unreadable ? ` · ${data.unreadable} with no intraday read` : ''}
            </span>
          </span>
        )}
      </div>

      <div className="sb-controls">
        <label>
          Timeframe{' '}
          <select value={tf} onChange={(e) => setTf(e.target.value)}>
            <option value="15m">15 min</option>
            <option value="60m">1 hour</option>
          </select>
        </label>
        <label>
          Bias{' '}
          <select value={bias} onChange={(e) => setBias(e.target.value as Bias | 'all')}>
            <option value="all">All</option>
            {BIAS_ORDER.map((b) => (
              <option key={b} value={b}>{BIAS_META[b].label}</option>
            ))}
          </select>
        </label>
        <label>
          <input type="checkbox" checked={atBandOnly}
                 onChange={(e) => setAtBandOnly(e.target.checked)} />
          {' '}At the daily band
        </label>
        <label>
          <input type="checkbox" checked={setupsOnly}
                 onChange={(e) => setSetupsOnly(e.target.checked)} />
          {' '}Complete SMC setup
        </label>
        <button type="button" className="sb-refresh" onClick={() => load()}>Refresh</button>
      </div>

      {err && <p className="sb-err">Could not load the session board: {err}</p>}

      {data?.warming && (
        <p className="sb-warm">
          {data.note || 'Reading the session…'}
          {' '}A cold pass reads ~99 names and takes a couple of minutes; it refreshes here on its own.
        </p>
      )}

      {!loading && !data?.warming && !shown.length && (
        <p className="sb-warm">
          No names match this filter{rows.length ? ` (${rows.length} on the board)` : ''}.
        </p>
      )}

      {/* Same grid, same tile renderer as the Demand boards (Ajay 2026-08-31:
        * "make this view like Demand view"). A row whose frame had no bars
        * still shows — as a text card naming the reason — because dropping it
        * would misreport coverage. */}
      <OverlayLegend
        present={presentGroups(shown.map((r) => r.tile).filter(Boolean))}
        hidden={hiddenOverlays} onToggle={toggleOverlay} />
      <div className="cm-grid">
        {shown.map((r) => r.tile
          ? <PatternChart key={r.symbol} tile={filterTile(r.tile, hiddenOverlays)} tvTf="15m" />
          : <NoDataCard key={r.symbol} row={r} onPick={onPick} />)}
      </div>

      {!!data?.disclaimer && <p className="sb-disc">{data.disclaimer}</p>}
    </div>
  );
}

function NoDataCard({ row, onPick }: { row: SessionRow; onPick?: (s: string) => void }) {
  const meta = BIAS_META[row.bias] || BIAS_META.unknown;
  return (
    <div className="sb-nodata">
      <button type="button" className="sb-sym" onClick={() => onPick?.(row.symbol)}
              title="Open this name on the Support Levels tab">
        {row.symbol}
      </button>
      <span className="sb-name">{row.name || ''}</span>
      <span className="sb-bias" style={{ color: toneColor(meta.tone) }}>
        {meta.dot} {meta.label}
      </span>
      <span className="sb-chip sb-chip-muted">
        {row.unavailable?.[0] || 'no intraday bars'}
      </span>
    </div>
  );
}
