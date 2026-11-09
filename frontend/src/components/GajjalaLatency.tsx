/* GajjalaLatency — ⏱ Speed on the 🏁 Track record (GG LIVE P4, 2026-11-09).
 *
 * Ajay 2026-11-09: "I would like the autopilot to be continously monitored or
 * live tracked … where there is a low latency monitoring on the prices action
 * changes please?" This block shows how many seconds after the 5-minute entry
 * bar CLOSED each step happened: the pass read it, the phone rang, the lane saw
 * it, ordered, filled — before / since the live switch.
 *
 * Fed by GET /trading/gajjala/latency?span= (backend/chart_maps/gajjala/
 * latency.payload — the SAME function scripts/gajjala_latency_report.py
 * prints). Owner only: nothing renders for a non-owner, nor on a 403 / error.
 * Every word and number is SERVED (title, column labels, cell texts, the
 * stacked phone lines, the interval words, the stream-vs-1-minute check, the
 * bar-finality line, the footnote) — this file types none of its own.
 * Desktop: a table. Phone (≤ PHONE_MAX_PX): stacked `label: p50 · p90 (n)` lines.
 *
 * Mount (main session, after the merges): under the A+ charts on the 🏁 view in
 * GajjalaBoard.tsx — `<GajjalaLatency span={span} />`.
 */
import { useEffect, useState, type CSSProperties } from 'react';
import { API } from '../lib/apiBase';
import { useCurrentUser } from '../hooks/useUser';

export const LATENCY_PATH = '/trading/gajjala/latency';
export const PHONE_MAX_PX = 430;
const PHONE_MQ = `(max-width: ${PHONE_MAX_PX}px)`;

export type LatencyCell = { key: string; text: string; line?: string | null };
export type LatencySummary = { label: string; side: string; n: number; cells: LatencyCell[] };
export type LatencyCi = { key: string; label: string; text: string };
export type LatencyPair = { stream: string; tick: string; agree: boolean; n: number; text: string };
export type LatencyCheck = {
  title: string; same: number; different: number; n: number; pairs: LatencyPair[];
  entry_delta_r?: { n: number; text: string } | null; odd_lot_only?: { n: number; k: number; text: string } | null;
};
export type LatencyFinality = { n: number; text: string; parts?: { part: string; text: string }[] | null };
export type LatencyPayload = {
  title: string; span: string; columns: { key: string; label: string }[]; n_alerts: number;
  summary: LatencySummary[]; ci?: LatencyCi[] | null; footnote: string; placebo_text?: string | null;
  empty_text?: string | null; check?: LatencyCheck | null; finality?: LatencyFinality | null;
};

function phoneNow(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia(PHONE_MQ).matches;
}

function usePhone(): boolean {
  const [phone, setPhone] = useState<boolean>(phoneNow);
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const m = window.matchMedia(PHONE_MQ);
    const h = () => setPhone(m.matches);
    h();
    m.addEventListener?.('change', h);
    return () => m.removeEventListener?.('change', h);
  }, []);
  return phone;
}

const box: CSSProperties = { minWidth: 0, maxWidth: '100%', margin: '0.75rem 0', fontSize: '0.85rem' };
const wrap: CSSProperties = { minWidth: 0, overflowWrap: 'anywhere' };
const muted: CSSProperties = { ...wrap, opacity: 0.75, margin: '0.25rem 0' };
const cellStyle: CSSProperties = { padding: '0.15rem 0.5rem', textAlign: 'right', whiteSpace: 'nowrap' };

export function GajjalaLatency({ span }: { span: string }) {
  const { user } = useCurrentUser();
  const owner = user?.is_admin === true;
  const phone = usePhone();
  const [data, setData] = useState<LatencyPayload | null>(null);

  useEffect(() => {
    if (!owner) { setData(null); return; }
    let alive = true;
    fetch(`${API}${LATENCY_PATH}?span=${encodeURIComponent(span || '')}`, { credentials: 'include', cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: LatencyPayload | null) => { if (alive) setData(j && typeof j.title === 'string' ? j : null); })
      .catch(() => { if (alive) setData(null); });
    return () => { alive = false; };
  }, [owner, span]);

  if (!owner || !data) return null;
  const cols = data.columns || [];
  const summary = data.summary || [];
  return (
    <section data-testid="gg-latency" style={box}>
      <h4 style={{ ...wrap, margin: '0 0 0.35rem' }}>{data.title}</h4>
      {data.empty_text ? <p data-testid="gg-latency-empty" style={muted}>{data.empty_text}</p> : null}
      {summary.length > 0 && phone ? (
        <div data-testid="gg-latency-stacked">
          {summary.map((s) => (
            <div key={s.side} data-testid={`gg-latency-side-${s.side}`} style={{ ...wrap, margin: '0.35rem 0' }}>
              <div style={{ fontWeight: 600 }}>{s.label}</div>
              {(s.cells || []).map((c) => (
                <div key={c.key} data-testid="gg-latency-line" style={wrap}>{c.line ?? c.text}</div>
              ))}
            </div>
          ))}
        </div>
      ) : null}
      {summary.length > 0 && !phone ? (
        <div style={{ overflowX: 'auto', maxWidth: '100%' }}>
          <table data-testid="gg-latency-table" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th />
                {cols.map((c) => <th key={c.key} style={cellStyle}>{c.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {summary.map((s) => (
                <tr key={s.side} data-testid={`gg-latency-row-${s.side}`}>
                  <th style={{ ...cellStyle, textAlign: 'left' }}>{s.label}</th>
                  {(s.cells || []).map((c) => <td key={c.key} style={cellStyle}>{c.text}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {(data.ci || []).map((c) => <p key={c.key} data-testid="gg-latency-ci" style={muted}>{c.text}</p>)}
      {data.check ? (
        <div data-testid="gg-latency-check" style={{ ...wrap, margin: '0.5rem 0' }}>
          <div style={{ fontWeight: 600 }}>{data.check.title}</div>
          {(data.check.pairs || []).map((p) => <div key={`${p.stream}|${p.tick}`} style={wrap}>{p.text}</div>)}
          {data.check.entry_delta_r?.text ? <div style={wrap}>{data.check.entry_delta_r.text}</div> : null}
          {data.check.odd_lot_only?.text ? <div style={wrap}>{data.check.odd_lot_only.text}</div> : null}
        </div>
      ) : null}
      {data.finality ? (
        <div data-testid="gg-latency-finality" style={{ ...wrap, margin: '0.5rem 0' }}>
          <div>{data.finality.text}</div>
          {(data.finality.parts || []).map((p) => <div key={p.part} style={muted}>{p.text}</div>)}
        </div>
      ) : null}
      <p data-testid="gg-latency-footnote" style={muted}>{data.footnote}</p>
      {data.placebo_text ? <p style={muted}>{data.placebo_text}</p> : null}
    </section>
  );
}

export default GajjalaLatency;
