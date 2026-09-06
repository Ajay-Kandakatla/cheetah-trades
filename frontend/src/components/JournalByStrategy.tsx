/* JournalByStrategy — the Auto-Pilot journal split by entry lane.
 *
 * Ajay 2026-09-05: "Keep the minervini entries but also make sure you have
 * demand zone and catalyst based entries time to time and journal it
 * appropriately." The engine now tags every entry with the lane that produced
 * it (trading.entries.enter(..., strategy=...)): minervini (the book gates in
 * auto_entry.py / risk_rules.py, untouched), demand_zone and breakout (the
 * zone-edge signals — owner rules, the alert gates), catalyst (the Catalysts
 * board's room-to-supply names — owner rules), manual (this page). The journal
 * summary carries `by_strategy` and this table is where the lanes are compared
 * side by side.
 *
 * Honesty rules baked in: a lane with no fills says "no trades yet" (a 0-of-0
 * win rate is not a rate), a lane with only OPEN trades shows "—" for every
 * closed-only stat, nulls print "—" (never NaN), the note under the table says
 * this is a PAPER account with small n. Nothing here places or moves an order.
 */
import type { CSSProperties } from 'react';

export type StrategyKey = 'minervini' | 'demand_zone' | 'breakout' | 'catalyst' | 'manual';

/** One lane's block in journal.summary.by_strategy. Every field optional —
 *  the API and the page deploy separately, and a lane the engine has never
 *  used may arrive as a partial block or not at all. */
export type StrategyStats = {
  n?: number | null;
  open?: number | null;
  closed?: number | null;
  wins?: number | null;
  losses?: number | null;
  win_rate_pct?: number | null;
  avg_r?: number | null;
  expectancy_pct?: number | null;
  realized_pnl?: number | null;
};

export type StrategyMeta = { glyph: string; label: string; blurb: string };

/** Fixed row order — the book lane first, then the two zone lanes, then the
 *  catalyst lane, then hand entries. */
export const STRATEGY_ORDER: StrategyKey[] = ['minervini', 'demand_zone', 'breakout', 'catalyst', 'manual'];

export const STRATEGY_META: Record<StrategyKey, StrategyMeta> = {
  minervini: {
    glyph: '📈', label: 'Minervini',
    blurb: 'SEPA buyable list — the book gates in auto_entry.py / risk_rules.py (TLSW), unchanged.',
  },
  demand_zone: {
    glyph: '🧲', label: 'demand zone',
    blurb: 'Zone-edge demand arrivals and bounces off a demand band, with ≥ 5% room to the first band overhead — owner rules (the alert gates), not the book.',
  },
  breakout: {
    glyph: '🚀', label: 'breakout',
    blurb: 'Breaking through the LAST supply band toward new highs — owner rules (the alert gates), not the book.',
  },
  catalyst: {
    glyph: '🗞️', label: 'catalyst',
    blurb: 'Catalysts board names clearing the room floor — owner rules, not the book.',
  },
  manual: {
    glyph: '✋', label: 'manual',
    blurb: 'Entered by hand on this page (also every row from before 2026-09-05, which carried no lane tag).',
  },
};

const UNKNOWN_GLYPH = '•';

/** Meta for any tag. Absent tag → manual (the pre-2026-09-05 rows). A tag we
 *  do not know is shown as itself, underscores spaced — never relabelled as a
 *  known lane. */
export function strategyMeta(key?: string | null): StrategyMeta {
  if (key == null || key === '') return STRATEGY_META.manual;
  const known = (STRATEGY_META as Record<string, StrategyMeta>)[key];
  if (known) return known;
  return { glyph: UNKNOWN_GLYPH, label: String(key).replace(/_/g, ' '), blurb: `Lane "${key}" — not one the page knows; shown as the engine tagged it.` };
}

/** Canonical lanes first (null when the server sent none), then anything the
 *  server added that we do not know. */
export function strategyRows(by?: Record<string, StrategyStats | null | undefined> | null): Array<[string, StrategyStats | null]> {
  const src = by && typeof by === 'object' ? by : {};
  const out: Array<[string, StrategyStats | null]> = [];
  for (const k of STRATEGY_ORDER) out.push([k, src[k] && typeof src[k] === 'object' ? (src[k] as StrategyStats) : null]);
  for (const k of Object.keys(src)) {
    if ((STRATEGY_ORDER as string[]).includes(k)) continue;
    if (src[k] && typeof src[k] === 'object') out.push([k, src[k] as StrategyStats]);
  }
  return out;
}

/* ── formatters (null-safe; a sign where it carries meaning) ─────────────── */

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}
export function fmtInt(v?: number | null): string {
  const n = num(v);
  return n == null ? '—' : String(Math.round(n));
}
export function fmtPct(v?: number | null): string {
  const n = num(v);
  return n == null ? '—' : `${Math.round(n)}%`;
}
export function fmtR(v?: number | null): string {
  const n = num(v);
  return n == null ? '—' : `${n > 0 ? '+' : n < 0 ? '-' : ''}${Math.abs(n).toFixed(2)}R`;
}
export function fmtSignedPct(v?: number | null): string {
  const n = num(v);
  return n == null ? '—' : `${n > 0 ? '+' : n < 0 ? '-' : ''}${Math.abs(n).toFixed(1)}%`;
}
export function fmtMoney(v?: number | null): string {
  const n = num(v);
  if (n == null) return '—';
  const abs = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${n > 0 ? '+' : n < 0 ? '-' : ''}$${abs}`;
}

export const NO_TRADES_TEXT = 'no trades yet';
export const HONESTY_NOTE =
  'Paper account. Small n until ~2 weeks of fills — a two-trade win rate is not a rate; read realized $ and R, not %.';

/* ── styles (the Trading page's table look, kept local) ──────────────────── */
const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#8a93a6' };
const TH: CSSProperties = {
  textAlign: 'right', fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.05em',
  color: C.sub, fontWeight: 600, padding: '4px 8px', borderBottom: '1px solid var(--hairline,#2a2a2a)',
  whiteSpace: 'nowrap',
};
const TD: CSSProperties = {
  fontSize: '0.78rem', padding: '6px 8px', verticalAlign: 'top', whiteSpace: 'nowrap', textAlign: 'right',
  fontVariantNumeric: 'tabular-nums', borderBottom: '1px solid var(--hairline,#2a2a2a)',
};

function signColor(v?: number | null): string | undefined {
  const n = num(v);
  if (n == null || n === 0) return undefined;
  return n > 0 ? C.green : C.red;
}

/** The lane chip every TradeCard wears (trade.entry.strategy, fallback manual). */
export function StrategyChip({ strategy }: { strategy?: string | null }) {
  const m = strategyMeta(strategy);
  return (
    <span data-testid="strategy-chip" title={m.blurb}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.68rem', fontWeight: 700,
                   color: C.muted, border: `1px solid ${C.muted}55`, borderRadius: 999, padding: '1px 8px',
                   whiteSpace: 'nowrap' }}>
      {m.glyph} {m.label}
    </span>
  );
}

export function JournalByStrategy({ byStrategy }: { byStrategy?: Record<string, StrategyStats | null | undefined> | null }) {
  const rows = strategyRows(byStrategy);
  return (
    <section data-testid="journal-by-strategy" style={{ marginBottom: '1rem' }}>
      <div className="eyebrow" style={{ marginBottom: 6 }}>🧭 By entry lane</div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              <th style={{ ...TH, textAlign: 'left' }}>Lane</th>
              <th style={TH} title="Trades opened by this lane, open + closed.">n</th>
              <th style={TH}>open</th>
              <th style={TH}>closed</th>
              <th style={TH} title="Wins ÷ closed trades. Blank until something has closed.">win %</th>
              <th style={TH} title="Average realized R-multiple over closed trades.">avg R</th>
              <th style={TH} title="Average realized gain % per closed trade (wins and losses together).">expectancy</th>
              <th style={TH} title="Realized P&L on closed trades, paper dollars.">realized $</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([key, s]) => {
              const m = strategyMeta(key);
              const n = num(s?.n) ?? 0;
              const closed = num(s?.closed) ?? 0;
              const empty = !s || n <= 0;
              // Closed-only stats stay "—" while nothing has closed, even if the
              // server sent a 0 — 0-of-0 is not a rate.
              const hasClosed = closed > 0;
              return (
                <tr key={key} data-strategy={key} aria-label={`${m.glyph} ${m.label}`}
                    style={{ opacity: empty ? 0.55 : 1 }}>
                  <td style={{ ...TD, textAlign: 'left', fontVariantNumeric: 'normal' }} title={m.blurb}>
                    <span style={{ fontWeight: 700 }}>{m.glyph} {m.label}</span>
                  </td>
                  {empty ? (
                    <td style={{ ...TD, textAlign: 'left', color: C.sub, fontStyle: 'italic' }} colSpan={7}>{NO_TRADES_TEXT}</td>
                  ) : (
                    <>
                      <td style={TD}>{fmtInt(s!.n)}</td>
                      <td style={TD}>{fmtInt(s!.open)}</td>
                      <td style={TD}>{fmtInt(s!.closed)}</td>
                      <td style={TD}>{hasClosed ? fmtPct(s!.win_rate_pct) : '—'}</td>
                      <td style={{ ...TD, color: hasClosed ? signColor(s!.avg_r) : undefined }}>{hasClosed ? fmtR(s!.avg_r) : '—'}</td>
                      <td style={{ ...TD, color: hasClosed ? signColor(s!.expectancy_pct) : undefined }}>{hasClosed ? fmtSignedPct(s!.expectancy_pct) : '—'}</td>
                      <td style={{ ...TD, color: hasClosed ? signColor(s!.realized_pnl) : undefined }}>{hasClosed ? fmtMoney(s!.realized_pnl) : '—'}</td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: '0.68rem', color: C.sub, margin: '6px 0 0' }}>{HONESTY_NOTE}</p>
    </section>
  );
}
