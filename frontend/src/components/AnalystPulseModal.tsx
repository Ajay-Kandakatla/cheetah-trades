/* AnalystPulseModal — full analyst drill-in for one ticker. Opens from
 * the AnalystPulseChip; fetches GET /sepa/analyst/{symbol} on mount.
 *
 * Sections:
 *   a. Price targets — mean/median/high/low vs live price bar + implied
 *      upside. FRAMED per TLSW Ch.4 "Value Comes at a Price" (p.41/p.44):
 *      great companies almost always look expensive; analysts
 *      systematically underestimate winners ("High Growth Baffles the
 *      Analysts"). Targets are analyst DATA, not Minervini methodology —
 *      stated verbatim in the section.
 *   b. Estimate revisions — 0q / FY / next-FY rows, current vs 30d vs
 *      90d + rev %s. The ±5% p.124 threshold highlights when crossed.
 *      The book doesn't specify the 5% study's lookback window — we key
 *      off 30d with 90d as context (honesty note rendered).
 *   c. Recent analyst actions (90d) — date, firm, grade change, PT
 *      change. When read.context == 'broken' a p.89 trap banner sits on
 *      top: upgrades on broken stocks are often valuation calls that
 *      "turn out to be good short candidates".
 *   d. Last earnings surprise — pp.121-123 framing ("the bigger the
 *      earnings surprise, the better"; <2% beats labeled
 *      managed-expectations territory).
 *   e. Footer cites row.
 *
 * Display + tracking only — none of this feeds the composite SEPA score.
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { API } from '../lib/apiBase';
import { REVISION_BIG_PCT, type AnalystMapEntry } from '../hooks/useAnalystMap';

const GREEN = '#10b981';
const RED   = '#ef4444';
const AMBER = '#f59e0b';
const SUB   = '#8a93a6';

type EpsTrendRow = {
  current: number | null;
  d30: number | null;
  d90: number | null;
  rev_pct_30d: number | null;
  rev_pct_90d: number | null;
};

type AnalystAction = {
  date: string;
  firm: string;
  action: string;
  from_grade?: string | null;
  to_grade?: string | null;
  prior_pt?: number | null;
  new_pt?: number | null;
};

/** The cached yfinance doc — GET /sepa/analyst/{symbol} nests it under
 *  `doc` (top-level keys kept as a fallback for older payload shapes). */
type AnalystDoc = {
  fetched_at?: number | string | null;
  targets?: {
    mean?: number | null; median?: number | null;
    high?: number | null; low?: number | null; current?: number | null;
  } | null;
  eps_trend?: Partial<Record<'0q' | '0y' | '+1y', EpsTrendRow>> | null;
  rev_counts?: unknown;
  actions?: AnalystAction[] | null;
};

type AnalystDetail = AnalystDoc & {
  symbol: string;
  doc?: AnalystDoc | null;
  read?: (Partial<AnalystMapEntry> & { context?: string | null }) | null;
  /** p.121-123 surprise join from the earnings_calendar cache. */
  last_report?: {
    date?: string | null; when?: string | null;
    eps_actual?: number | null; eps_estimate?: number | null;
    surprise_pct?: number | null;
  } | null;
  last_surprise_pct?: number | null;
  live_price?: number | null;
};

function num(v: unknown): number | null {
  return typeof v === 'number' && isFinite(v) ? v : null;
}

function fmtMoney(v: number | null | undefined): string {
  return v == null ? '—' : `$${v.toFixed(2)}`;
}

function fmtEps(v: number | null | undefined): string {
  return v == null ? '—' : v.toFixed(2);
}

function fmtPct(v: number | null | undefined, dec = 1): string {
  if (v == null || !isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(dec)}%`;
}

/** Pull 30d up/down revision counts out of whatever shape the backend
 *  ships (flat, yfinance-style camelCase, or keyed per period). */
function revCounts30d(rc: unknown): { up: number | null; down: number | null } {
  if (!rc || typeof rc !== 'object') return { up: null, down: null };
  const o = rc as Record<string, any>;
  const upFlat = num(o.up_30d) ?? num(o.up_last_30d) ?? num(o.upLast30days) ?? num(o.up);
  const dnFlat = num(o.down_30d) ?? num(o.down_last_30d) ?? num(o.downLast30days) ?? num(o.down);
  if (upFlat != null || dnFlat != null) return { up: upFlat, down: dnFlat };
  const p = o['0y'] ?? o['0q'] ?? null;
  if (p && typeof p === 'object') {
    return {
      up: num(p.up_30d) ?? num(p.upLast30days) ?? num(p.up),
      down: num(p.down_30d) ?? num(p.downLast30days) ?? num(p.down),
    };
  }
  return { up: null, down: null };
}

function actionTone(a: AnalystAction): string {
  const prior = num(a.prior_pt);
  const next = num(a.new_pt);
  if (prior != null && next != null && next !== prior) return next > prior ? GREEN : RED;
  const s = `${a.action || ''}`.toLowerCase();
  if (/(up|raise|boost|initiat|outperform|overweight|buy)/.test(s)) return GREEN;
  if (/(down|cut|lower|reduc|underperform|underweight|sell)/.test(s)) return RED;
  return SUB;
}

const PERIOD_LABEL: Record<'0q' | '0y' | '+1y', string> = {
  '0q':  'Current Q',
  '0y':  'Current FY',
  '+1y': 'Next FY',
};

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="eyebrow" style={{ margin: '1rem 0 0.4rem', fontSize: '0.72rem' }}>
      {children}
    </div>
  );
}

/** Horizontal low→high target range with mean / median / now markers. */
function TargetBar({ low, high, mean, median, now }: {
  low: number; high: number; mean: number | null; median: number | null; now: number | null;
}) {
  const pos = (v: number) => `${Math.max(0, Math.min(100, ((v - low) / (high - low)) * 100))}%`;
  const tick = (v: number | null, color: string, label: string, top: boolean) => {
    if (v == null) return null;
    return (
      <div style={{ position: 'absolute', left: pos(v), transform: 'translateX(-50%)', textAlign: 'center', [top ? 'bottom' : 'top']: '100%' } as React.CSSProperties}>
        <div style={{ fontSize: '0.7rem', color, whiteSpace: 'nowrap', lineHeight: 1.3 }}>
          {top ? <>{label}<br />${v.toFixed(2)}</> : <>${v.toFixed(2)}<br />{label}</>}
        </div>
      </div>
    );
  };
  return (
    <div style={{ margin: '2.4rem 0.5rem 2.6rem', position: 'relative' }}>
      <div style={{
        height: 6, borderRadius: 3,
        background: `linear-gradient(90deg, ${RED}55, ${GREEN}55)`,
        position: 'relative',
      }}>
        {[mean, median, now].map((v, i) => v == null ? null : (
          <div key={i} style={{
            position: 'absolute', left: pos(v), top: -4, bottom: -4, width: 2,
            transform: 'translateX(-50%)',
            background: i === 2 ? '#e2e8f0' : i === 0 ? GREEN : '#38bdf8',
          }} />
        ))}
      </div>
      {tick(now, '#e2e8f0', 'now', true)}
      {tick(mean, GREEN, 'mean', false)}
      {tick(median, '#38bdf8', 'median', false)}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: SUB, marginTop: '0.2rem' }}>
        <span>low ${low.toFixed(2)}</span>
        <span>high ${high.toFixed(2)}</span>
      </div>
    </div>
  );
}

export function AnalystPulseModal({ symbol, onClose }: { symbol: string; onClose: () => void }) {
  const [data, setData] = useState<AnalystDetail | null>(null);
  const [err, setErr] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetch(`${API}/sepa/analyst/${encodeURIComponent(symbol)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((j: AnalystDetail) => { if (alive) { setData(j); setErr(false); } })
      .catch(() => { if (alive) setErr(true); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [symbol]);

  // The backend nests the cached yfinance doc under `doc` (null when the
  // symbol has never been fetched); fall back to top-level keys.
  const doc: AnalystDoc | null = data?.doc ?? data ?? null;
  const t = doc?.targets ?? null;
  const live = num(data?.live_price) ?? num(t?.current);
  const mean = num(t?.mean);
  const upside = mean != null && live != null && live > 0
    ? ((mean / live) - 1) * 100
    : num(data?.read?.implied_upside_pct ?? null);
  const counts = revCounts30d(doc?.rev_counts);
  const actions = (doc?.actions ?? []).slice(0, 20);
  const broken = (data?.read?.context === 'broken') || Boolean(data?.read?.p89_trap);
  const surprise = num(data?.last_report?.surprise_pct ?? data?.last_surprise_pct);

  const trendRows = (['0q', '0y', '+1y'] as const)
    .map((k) => ({ k, row: doc?.eps_trend?.[k] }))
    .filter((x): x is { k: '0q' | '0y' | '+1y'; row: EpsTrendRow } => x.row != null);

  const cellBase: React.CSSProperties = {
    padding: '0.3rem 0.5rem', fontSize: '0.74rem', textAlign: 'right',
    borderBottom: '1px solid var(--hairline, #2a2a2a)', whiteSpace: 'nowrap',
  };
  const revCell = (v: number | null): React.CSSProperties => ({
    ...cellBase,
    fontWeight: v != null && Math.abs(v) >= REVISION_BIG_PCT ? 700 : 400,
    color: v == null ? SUB
      : Math.abs(v) >= REVISION_BIG_PCT ? (v > 0 ? GREEN : RED)
      : v > 0 ? `${GREEN}cc` : v < 0 ? `${RED}cc` : SUB,
    background: v != null && Math.abs(v) >= REVISION_BIG_PCT
      ? (v > 0 ? `${GREEN}14` : `${RED}14`) : 'transparent',
  });

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: '1rem', overflowY: 'auto',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-raised, #1a1a1a)', color: 'var(--ink, inherit)',
          border: '1px solid var(--rule, #333)', borderRadius: 8,
          width: '100%',
          maxWidth: 'min(680px, calc(100vw - 2rem))',
          maxHeight: '90vh', overflow: 'auto',
          padding: '1.1rem clamp(0.8rem, 3vw, 1.3rem)',
          minWidth: 0,
        }}
      >
        <header style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
          gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.3rem',
        }}>
          <div>
            <div className="eyebrow">📊 Analyst Pulse · estimates &amp; targets</div>
            <h2 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1.3rem' }}>{symbol}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'transparent', border: '1px solid var(--hairline, #2a2a2a)',
              color: 'inherit', borderRadius: 6, cursor: 'pointer',
              fontSize: '0.85rem', padding: '2px 10px',
            }}
          >
            ✕
          </button>
        </header>

        {loading && <p style={{ fontSize: '0.8rem', color: SUB }}>Loading analyst data…</p>}
        {err && (
          <p style={{ fontSize: '0.8rem', color: AMBER }}>
            Couldn't load analyst data for {symbol} right now — try again in a minute.
          </p>
        )}

        {!loading && !err && data && (
          <>
            {/* ── a. Price targets ─────────────────────────────────── */}
            <SectionTitle>Price targets</SectionTitle>
            {t && num(t.low) != null && num(t.high) != null && num(t.high)! > num(t.low)! ? (
              <>
                <TargetBar
                  low={num(t.low)!} high={num(t.high)!}
                  mean={mean} median={num(t.median)} now={live}
                />
                <p style={{ fontSize: '0.82rem', margin: '0 0 0.3rem' }}>
                  Mean target {fmtMoney(mean)} vs {live != null ? `$${live.toFixed(2)}` : '—'} now
                  {upside != null && (
                    <>
                      {' → implied '}
                      <strong style={{ color: upside >= 0 ? GREEN : RED }}>
                        {fmtPct(upside, 1)}
                      </strong>
                    </>
                  )}
                </p>
              </>
            ) : (
              <p style={{ fontSize: '0.78rem', color: SUB }}>No price-target data for {symbol}.</p>
            )}
            <p style={{ fontSize: '0.72rem', color: SUB, margin: '0.2rem 0 0', lineHeight: 1.5 }}>
              Great companies almost always look expensive — "High Growth Baffles the Analysts"
              (TLSW p.44; Ch.4 "Value Comes at a Price", p.41). Targets are analyst data,
              not Minervini methodology.
            </p>

            {/* ── b. Estimate revisions ────────────────────────────── */}
            <SectionTitle>Estimate revisions (EPS)</SectionTitle>
            {trendRows.length > 0 ? (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['', 'Now', '30d ago', '90d ago', 'Δ30d', 'Δ90d'].map((h, i) => (
                        <th key={h || 'p'} style={{
                          ...cellBase, color: SUB, fontWeight: 600,
                          textAlign: i === 0 ? 'left' : 'right',
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {trendRows.map(({ k, row }) => (
                      <tr key={k}>
                        <td style={{ ...cellBase, textAlign: 'left', fontWeight: 600 }}>{PERIOD_LABEL[k]}</td>
                        <td style={cellBase} className="mono">{fmtEps(num(row.current))}</td>
                        <td style={cellBase} className="mono">{fmtEps(num(row.d30))}</td>
                        <td style={cellBase} className="mono">{fmtEps(num(row.d90))}</td>
                        <td style={revCell(num(row.rev_pct_30d))} className="mono">{fmtPct(num(row.rev_pct_30d))}</td>
                        <td style={revCell(num(row.rev_pct_90d))} className="mono">{fmtPct(num(row.rev_pct_90d))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p style={{ fontSize: '0.78rem', color: SUB }}>No estimate-trend data for {symbol}.</p>
            )}
            {(counts.up != null || counts.down != null) && (
              <p style={{ fontSize: '0.76rem', margin: '0.4rem 0 0' }}>
                Last 30 days:{' '}
                <span style={{ color: GREEN, fontWeight: 600 }}>{counts.up ?? 0} up</span>
                {' · '}
                <span style={{ color: RED, fontWeight: 600 }}>{counts.down ?? 0} down</span>
                {' '}revisions
              </p>
            )}
            <p style={{ fontSize: '0.72rem', color: SUB, margin: '0.35rem 0 0', lineHeight: 1.5 }}>
              Revisions of <strong>±{REVISION_BIG_PCT}% or more</strong> are highlighted — "when
              estimates are revised upward by 5 percent or more, stocks tend to show
              better-than-average performance. Conversely, with downward revisions of 5 percent or
              more, stocks exhibit lower than average performance" (TLSW p.124). The book doesn't
              specify the study's lookback window — we key off 30d, with 90d as context.
            </p>

            {/* ── c. Recent analyst actions ────────────────────────── */}
            <SectionTitle>Recent analyst actions (90d)</SectionTitle>
            {broken && (
              <div style={{
                border: `1px solid ${AMBER}66`, background: `${AMBER}14`, color: AMBER,
                borderRadius: 6, padding: '0.5rem 0.7rem', fontSize: '0.74rem',
                lineHeight: 1.5, marginBottom: '0.5rem',
              }}>
                ⚠ <strong>p.89 trap risk</strong> — {symbol} is not in a confirmed uptrend
                (not Stage 2 / scan qualifier). Upgrades and target raises on broken stocks are
                often valuation calls after the break and frequently "turn out to be good short
                candidates" (TLSW p.89). "Trust what you see, not what you hear. Tune out the
                analyst" (p.86). Read the actions below as caution, not endorsement.
              </div>
            )}
            {actions.length > 0 ? (
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 4 }}>
                {actions.map((a, i) => {
                  const tone = actionTone(a);
                  return (
                    <li key={`${a.date}-${a.firm}-${i}`} style={{
                      display: 'grid',
                      gridTemplateColumns: 'auto minmax(0,1fr) auto',
                      gap: '0.5rem', alignItems: 'baseline',
                      padding: '0.3rem 0.55rem', borderRadius: 4,
                      border: `1px solid ${tone}33`, background: `${tone}0d`,
                      fontSize: '0.74rem', minWidth: 0,
                    }}>
                      <span className="mono" style={{ color: SUB }}>{a.date}</span>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        <strong>{a.firm}</strong>
                        {' · '}{a.action}
                        {(a.from_grade || a.to_grade) && (
                          <span style={{ color: SUB }}>
                            {' '}{a.from_grade ?? '—'} → {a.to_grade ?? '—'}
                          </span>
                        )}
                      </span>
                      <span className="mono" style={{ color: tone, fontWeight: 600 }}>
                        {a.prior_pt != null || a.new_pt != null
                          ? `${a.prior_pt != null ? `$${a.prior_pt}` : '—'} → ${a.new_pt != null ? `$${a.new_pt}` : '—'}`
                          : ''}
                      </span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p style={{ fontSize: '0.78rem', color: SUB }}>No analyst actions in the last 90 days.</p>
            )}

            {/* ── d. Last earnings surprise ────────────────────────── */}
            <SectionTitle>Last earnings surprise</SectionTitle>
            {surprise != null ? (
              <p style={{ fontSize: '0.8rem', margin: 0, lineHeight: 1.55 }}>
                <strong style={{
                  color: surprise >= 2 ? GREEN : surprise >= 0 ? AMBER : RED,
                  fontSize: '0.95rem',
                }}>
                  {fmtPct(surprise, 1)}
                </strong>
                {' vs consensus. '}
                {surprise >= 2 ? (
                  <span>
                    Meaningful beat — "the bigger the earnings surprise, the better" (TLSW p.121);
                    post-earnings drift can persist for months.
                  </span>
                ) : surprise >= 0 ? (
                  <span style={{ color: AMBER }}>
                    Penny-beat — managed-expectations territory (pp.122-123): companies guide
                    analysts low and step over the bar; only a "meaningful margin" counts.
                  </span>
                ) : (
                  <span style={{ color: RED }}>
                    Miss — the downside cohort of the surprise studies (pp.121-123).
                  </span>
                )}
              </p>
            ) : (
              <p style={{ fontSize: '0.78rem', color: SUB }}>No recent surprise data for {symbol}.</p>
            )}

            {/* ── e. Cites footer ──────────────────────────────────── */}
            <footer style={{
              marginTop: '1rem', paddingTop: '0.6rem',
              borderTop: '1px solid var(--hairline, #2a2a2a)',
              fontSize: '0.7rem', color: SUB, lineHeight: 1.5,
            }}>
              Sources: TLSW (Minervini 2013) — p.41/p.44 "Value Comes at a Price" / "High Growth
              Baffles the Analysts" · pp.121-123 earnings surprises · p.124 ±5% revisions ·
              p.125 estimates trending higher / red flag · p.86 "tune out the analyst" ·
              p.89 "Brokerage House Opinions" upgrade-trap. Display + tracking only — analyst
              data does NOT feed the composite SEPA score.
            </footer>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
