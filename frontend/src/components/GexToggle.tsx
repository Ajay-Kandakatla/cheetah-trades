/* 🧲 GexToggle — "🧲 Bullish GEX first", the Chart Maps checkbox (Ajay
 * 2026-09-27: "make it sorted by bullish gex please.." → "Checkbox, ON by
 * default").
 *
 * Ticked (the default): bullish names first, strongest first, then mixed, then
 * bearish, then names with no read — each group in the SERVED order. Unticked:
 * the tab's own order. It re-orders only; NOTHING is hidden. The tally beside
 * the label is served-legend labels over the tiles on screen, the hover is the
 * SERVED rule and scope sentence, and a tab the server says keeps its own
 * order (0DTE) shows the box disabled with the served reason.
 *
 * The live line says where the just-in-time read stands: reading, still
 * reading, failed (last close shown), market closed, or the read's own time.
 * UNMEASURED.
 */
import type { ReactNode } from 'react';
import type { GexLiveState } from '../hooks/useGexLive';
import type { GexSortOff } from '../lib/gexRead';

export function GexToggle({ on, onChange, counts, rule, scope, sortOff, live }: {
  on: boolean;
  onChange: (v: boolean) => void;
  counts: ReadonlyArray<{ key: string; label: string; n: number }>;
  rule?: string | null;
  scope?: string | null;
  sortOff?: GexSortOff | null;
  live?: Pick<GexLiveState, 'payload' | 'loading' | 'error' | 'pending'> | null;
}) {
  const title = [rule, scope, sortOff?.title].filter(Boolean).join('\n');
  const p = live?.payload ?? null;
  let liveLine: ReactNode = null;
  if (live?.loading) {
    liveLine = <span className="gex-live"> · live read…</span>;
  } else if (live?.pending) {
    liveLine = <span className="gex-live"> · live: {live.pending} still reading</span>;
  } else if (live?.error) {
    liveLine = <span className="gex-live gex-live-failed" title={live.error}> · live read failed — last close shown</span>;
  } else if (p && p.market_closed) {
    liveLine = <span className="gex-live" title={p.note || undefined}> · last close (market closed)</span>;
  } else if (p && typeof p.as_of_text === 'string' && p.as_of_text) {
    liveLine = <span className="gex-live" title={p.note || undefined}> · {p.as_of_text}</span>;
  }
  return (
    <label className="cm-ctl cm-ctl-check gex-toggle" title={title || undefined}>
      <input type="checkbox" checked={on} disabled={Boolean(sortOff)}
             onChange={(e) => onChange(e.target.checked)} />
      🧲 Bullish GEX first
      <span className="gex-count">{counts.map((c) => ` · ${c.n} ${c.label}`).join('')}</span>
      {sortOff ? <span className="gex-sort-off"> · {sortOff.label}</span> : null}
      {liveLine}
    </label>
  );
}
