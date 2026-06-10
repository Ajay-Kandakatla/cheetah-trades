/* LiveTapeRead — the real-time pattern-reading strip for Day Trading + Scalping
 * (Ajay 2026-06-10: "I need these pattern reading logic in day trading and also
 * Scalping… real time trading… the right indicators").
 *
 * For the symbol on the chart: the latest completed 5-min candle read against
 * its levels (SEPA pivot, forming daily-pattern line, VWAP, opening range, day
 * high) — who won the bar, at what level, on what volume — plus the daily
 * pattern verdict chip for swing context. Polls every 60s while mounted.
 * Descriptive supply/demand reads ("constructive/deteriorating"), never
 * predictions — same honesty contract as the SEPA Watch. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { usePatternVerdicts } from '../hooks/usePatternVerdicts';
import { PatternChips } from './PatternChips';
import { TickerCell } from './TickerCell';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280' };
const STATE_META: Record<string, { icon: string; color: string }> = {
  BREAKOUT_STRONG: { icon: '🟢', color: C.green },
  RECLAIM: { icon: '🟢', color: C.green },
  BREAKOUT_WEAK: { icon: '🟡', color: C.amber },
  REJECTION: { icon: '🟠', color: C.amber },
  BREAKDOWN: { icon: '🔴', color: C.red },
  STALL: { icon: '➖', color: C.muted },
};

type Read = {
  state: string; verdict: string; severity: string; reasons: string[];
  metrics?: { body_pct?: number; clv?: number; vol_ratio?: number | null;
              ref_name?: string | null; ref_level?: number | null };
} | null;
type TapeRow = {
  ok: boolean; symbol: string; note?: string; last_price?: number; bar_ts?: string;
  read?: Read; pivot?: number | null;
  levels?: { pivot?: number | null; pattern_line?: number | null; pattern_name?: string | null;
             vwap?: number | null; or_high?: number | null; day_high?: number | null };
};

const POLL_MS = 60_000;

export function LiveTapeRead({ symbol }: { symbol: string }) {
  const [row, setRow] = useState<TapeRow | null>(null);
  const { verdicts } = usePatternVerdicts();

  useEffect(() => {
    let alive = true;
    setRow(null);
    const load = () =>
      fetch(`${API}/scalping/tape-read/${encodeURIComponent(symbol)}`, { cache: 'no-store' })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((d) => { if (alive) setRow(d); })
        .catch(() => undefined);
    load();
    const id = setInterval(load, POLL_MS);
    return () => { alive = false; clearInterval(id); };
  }, [symbol]);

  if (!row) return null;

  const read = row.read || null;
  const meta = read ? STATE_META[read.state] || { icon: '🕯', color: C.muted } : null;
  const lv = row.levels || {};
  const m = read?.metrics || {};
  const barTime = row.bar_ts ? new Date(row.bar_ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

  const lvl = (label: string, v?: number | null, hot = false) =>
    v != null ? (
      <span key={label} style={{ color: hot ? C.amber : C.muted }}>
        {label} <b style={{ fontVariantNumeric: 'tabular-nums' }}>{v}</b>
      </span>
    ) : null;

  return (
    <div style={{ padding: '0.55rem 0.75rem', borderRadius: 10, marginBottom: 8,
                  background: read ? `${(meta as any).color}0d` : 'var(--bg-raised,#16181d)',
                  border: `1px solid ${read ? (meta as any).color + '55' : 'var(--hairline,#2a2a2a)'}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <TickerCell symbol={row.symbol} size="0.86rem" />
        {!row.ok ? (
          <span style={{ fontSize: '0.74rem', color: C.muted }}>{row.note}</span>
        ) : read ? (
          <>
            <span style={{ fontSize: '0.78rem', fontWeight: 800, color: (meta as any).color }}>
              {(meta as any).icon} {read.state.replace(/_/g, ' ')}
            </span>
            <span style={{ fontSize: '0.7rem', fontWeight: 700, color: (meta as any).color,
                           border: `1px solid ${(meta as any).color}55`, borderRadius: 5, padding: '0 6px' }}>
              {read.verdict}
            </span>
          </>
        ) : (
          <span style={{ fontSize: '0.74rem', color: C.muted }}>➖ quiet — nothing happening at a level this 5-min bar</span>
        )}
        <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 4, alignItems: 'center' }}>
          <PatternChips v={verdicts.get(symbol.toUpperCase())} max={1} />
          {barTime && <span style={{ fontSize: '0.62rem', color: C.sub }}>bar {barTime} · refreshes 60s</span>}
        </span>
      </div>

      {read && read.reasons?.length > 0 && (
        <div style={{ fontSize: '0.72rem', color: 'var(--ink,inherit)', marginTop: 4, opacity: 0.9 }}>
          {read.reasons.slice(0, 2).join(' · ')}
        </div>
      )}

      <div style={{ display: 'flex', gap: 14, marginTop: 4, fontSize: '0.68rem', flexWrap: 'wrap' }}>
        {lvl('pivot', lv.pivot)}
        {lvl(lv.pattern_name || 'pattern line', lv.pattern_line, true)}
        {lvl('VWAP', lv.vwap)}
        {lvl('OR-high', lv.or_high)}
        {lvl('day-high', lv.day_high)}
        {read && m.body_pct != null && (
          <span style={{ color: C.sub }}>
            bar: body {(m.body_pct * 100).toFixed(0)}%{m.clv != null ? ` · CLV ${m.clv > 0 ? '+' : ''}${m.clv}` : ''}{m.vol_ratio != null ? ` · vol ${m.vol_ratio}×` : ''}
          </span>
        )}
      </div>
    </div>
  );
}
