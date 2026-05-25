/* ChatterMomentumDrillModal — explains the "Chatter momentum" label.
 *
 *  User opens this by tapping the momentum chip on the SEPA detail
 *  page's Chatter tab. Goal of the modal:
 *
 *   1. Spell out what the label MEASURES (Reddit/HN chatter velocity
 *      vs prior week, NOT stock-price momentum) because the chip alone
 *      reads like "the stock is fading" — which is wrong and could
 *      mislead a trade.
 *
 *   2. Show the trend over time so the user can see whether the
 *      current label is a one-day blip or a real multi-week trend.
 *
 *   3. List the underlying snapshots (mentions, velocity, sentiment)
 *      so the user can audit "how was this computed?"
 *
 *  Data source: GET /sepa/chatter/{symbol}/history (60 days by default).
 *  History collection started filling on 2026-05-20 — older tickers
 *  will show the "collecting forward" empty state until the daily
 *  cron (5:30 AM ET) has run a few times.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

type HistoryRow = {
  symbol:            string;
  fetched_at:        number;
  mentions_7d:       number;
  mentions_prior_7d: number;
  mention_velocity:  number;
  momentum_label:    'ramping' | 'steady' | 'fading' | 'quiet' | null;
  sentiment_ratio:   number | null;
  bullish:           number;
  bearish:           number;
  hn_stories:        number;
  n_threads:         number;
};

type CurrentSummary = {
  mentions_7d:       number;
  mentions_prior_7d: number;
  mention_velocity:  number;
  momentum_label:    'ramping' | 'steady' | 'fading' | 'quiet';
  sentiment_ratio:   number | null;
};

const LABEL_COLOR: Record<string, string> = {
  ramping: '#22c55e',
  steady:  '#9aa8c8',
  fading:  '#f59e0b',
  quiet:   '#6a6a72',
};

function fmtDate(epoch: number): string {
  const d = new Date(epoch * 1000);
  return d.toLocaleDateString('en-US', { month: 'short', day: '2-digit' });
}

function fmtDateTime(epoch: number): string {
  const d = new Date(epoch * 1000);
  return d.toLocaleString('en-US', {
    month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

/** Tiny inline SVG sparkline. No chart lib — matches the codebase style.
 *
 *  Renders the series as a polyline against the modal's dark theme;
 *  draws axis-floor at the min and a faint mid-line at velocity=1.0
 *  for the velocity sparkline (the threshold between "ramping" / "fading").
 */
function Sparkline({
  values, color, height = 60, width = 320, threshold,
}: {
  values: number[]; color: string; height?: number; width?: number;
  threshold?: number;     // optional horizontal reference line (e.g. 1.0)
}) {
  if (values.length === 0) {
    return <div style={{
      width, height, display: 'flex', alignItems: 'center',
      justifyContent: 'center', color: '#6a6a72', fontSize: '0.78rem',
      border: '1px dashed rgba(255,255,255,0.08)', borderRadius: 6,
    }}>no history yet</div>;
  }
  const lo = Math.min(...values, threshold ?? Infinity);
  const hi = Math.max(...values, threshold ?? -Infinity);
  const range = Math.max(hi - lo, 0.01);
  const stepX = values.length > 1 ? width / (values.length - 1) : 0;
  const pts = values.map((v, i) => {
    const x = i * stepX;
    const y = height - ((v - lo) / range) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const thresholdY = threshold != null
    ? height - ((threshold - lo) / range) * (height - 4) - 2
    : null;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}
         style={{ display: 'block' }}>
      {thresholdY != null && (
        <line x1={0} y1={thresholdY} x2={width} y2={thresholdY}
              stroke="rgba(255,255,255,0.15)" strokeDasharray="3 3" strokeWidth={1} />
      )}
      <polyline fill="none" stroke={color} strokeWidth={1.8}
                strokeLinejoin="round" strokeLinecap="round"
                points={pts} />
      {/* Dots at each data point so single-snapshot history is still visible. */}
      {values.map((v, i) => {
        const x = i * stepX;
        const y = height - ((v - lo) / range) * (height - 4) - 2;
        return <circle key={i} cx={x} cy={y} r={2} fill={color} />;
      })}
    </svg>
  );
}

export function ChatterMomentumDrillModal({
  symbol, current, onClose,
}: {
  symbol: string;
  current: CurrentSummary;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setErr(null);
    fetch(`${API}/sepa/chatter/${encodeURIComponent(symbol)}/history?days=60`, {
      credentials: 'include',
    })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((j) => { if (!cancelled) setRows(j?.rows || []); })
      .catch((e) => { if (!cancelled) setErr(String(e?.message || e)); });
    return () => { cancelled = true; };
  }, [symbol]);

  const labelColor = LABEL_COLOR[current.momentum_label] || '#9aa8c8';

  return (
    <div
      role="dialog" aria-modal="true" aria-label="Chatter momentum trend"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '1rem', zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#141416', color: '#e6e6e6',
          width: 'min(720px, calc(100vw - 2rem))',
          maxHeight: 'calc(100vh - 2rem)', overflowY: 'auto',
          border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12,
          padding: '1.1rem 1.2rem 1rem',
        }}
      >
        <div style={{
          display: 'flex', alignItems: 'baseline',
          justifyContent: 'space-between', gap: '0.5rem',
          marginBottom: '0.5rem',
        }}>
          <div>
            <div className="eyebrow" style={{ color: labelColor, fontSize: '0.66rem' }}>
              Chatter momentum · how it's computed
            </div>
            <h2 style={{
              margin: 0, fontSize: '1.2rem',
              fontFamily: '"Times New Roman", Georgia, serif',
              fontStyle: 'italic',
            }}>
              {symbol} · <span style={{ color: labelColor }}>{current.momentum_label}</span>
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'none', border: '1px solid rgba(255,255,255,0.15)',
              color: '#cfcfd4', padding: '4px 10px', borderRadius: 4,
              cursor: 'pointer', fontSize: '0.85rem', fontFamily: 'inherit',
            }}
          >
            ✕
          </button>
        </div>

        {/* What this measures — the part that gets lost on the chip */}
        <div style={{
          padding: '0.55rem 0.75rem',
          background: 'rgba(245, 158, 11, 0.06)',
          border: '1px solid rgba(245, 158, 11, 0.22)',
          borderRadius: 6,
          fontSize: '0.8rem',
          lineHeight: 1.55,
          marginBottom: '0.9rem',
        }}>
          <strong style={{ color: '#f59e0b' }}>What this measures:</strong>{' '}
          velocity of <strong>Reddit + Hacker News mentions</strong> over the
          last 7 days vs the prior 7 days. <strong>It is NOT stock-price
          momentum.</strong> A quiet ticker can still be ripping (institutions
          don't post on Reddit). Use it as a "is retail talking about this?"
          signal, not as a trade entry.
        </div>

        {/* Decision rules */}
        <div style={{ marginBottom: '0.7rem' }}>
          <div className="eyebrow" style={{ fontSize: '0.62rem', marginBottom: 4 }}>
            How the label is decided
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'auto 1fr',
            gap: '3px 12px',
            fontSize: '0.76rem',
            lineHeight: 1.5,
          }}>
            <span style={{ color: LABEL_COLOR.ramping, fontWeight: 700 }}>ramping</span>
            <span style={{ color: '#cfcfd4' }}>velocity ≥ 1.5× AND ≥ 3 mentions this week</span>
            <span style={{ color: LABEL_COLOR.fading, fontWeight: 700 }}>fading</span>
            <span style={{ color: '#cfcfd4' }}>velocity ≤ 0.6× this week (had chatter, lost it)</span>
            <span style={{ color: LABEL_COLOR.steady, fontWeight: 700 }}>steady</span>
            <span style={{ color: '#cfcfd4' }}>between 0.6× and 1.5×</span>
            <span style={{ color: LABEL_COLOR.quiet, fontWeight: 700 }}>quiet</span>
            <span style={{ color: '#cfcfd4' }}>zero mentions either week</span>
          </div>
        </div>

        {/* Current snapshot */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
          gap: '0.5rem',
          marginBottom: '0.9rem',
        }}>
          <MetricCell label="This week"        value={current.mentions_7d.toString()} />
          <MetricCell label="Prior week"       value={current.mentions_prior_7d.toString()} />
          <MetricCell label="Velocity"
                      value={`${current.mention_velocity.toFixed(2)}×`}
                      color={current.mention_velocity >= 1.5 ? LABEL_COLOR.ramping
                            : current.mention_velocity <= 0.6 ? LABEL_COLOR.fading
                            : LABEL_COLOR.steady} />
          <MetricCell label="Sentiment"
                      value={current.sentiment_ratio == null ? '—'
                            : `${Math.round(current.sentiment_ratio * 100)}%`}
                      hint="bullish share of bullish+bearish" />
        </div>

        {/* Trend section */}
        <div style={{ marginBottom: '0.8rem' }}>
          <div className="eyebrow" style={{ fontSize: '0.62rem', marginBottom: 6 }}>
            Trend · last 60 days
          </div>

          {err && (
            <div style={{ color: '#fca5a5', fontSize: '0.8rem', marginBottom: '0.5rem' }}>
              {err}
            </div>
          )}

          {rows === null && !err && (
            <div style={{ color: '#9a9aa3', fontSize: '0.8rem' }}>loading history…</div>
          )}

          {rows && rows.length === 0 && (
            <div style={{
              padding: '0.7rem 0.9rem',
              background: 'rgba(20,20,22,0.55)',
              border: '1px dashed rgba(255,255,255,0.1)',
              borderRadius: 6,
              fontSize: '0.8rem',
              lineHeight: 1.55,
              color: '#9a9aa3',
            }}>
              No history yet for <strong>{symbol}</strong>. The chatter
              history collection started filling on <strong>2026-05-20</strong>;
              a daily cron (5:30 AM ET) prewarms the top 20 SEPA candidates,
              and every ticker you open also gets recorded. Check back in a
              few days for a trend line.
            </div>
          )}

          {rows && rows.length > 0 && (
            <>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: '0.7rem',
              }}>
                <div>
                  <div style={{
                    fontSize: '0.66rem', color: '#9a9aa3',
                    marginBottom: 3, letterSpacing: '0.06em', textTransform: 'uppercase',
                  }}>
                    Mentions per fetch ({rows.length} pt{rows.length === 1 ? '' : 's'})
                  </div>
                  <Sparkline
                    values={rows.map((r) => r.mentions_7d)}
                    color="#3b82f6"
                  />
                </div>
                <div>
                  <div style={{
                    fontSize: '0.66rem', color: '#9a9aa3',
                    marginBottom: 3, letterSpacing: '0.06em', textTransform: 'uppercase',
                  }}>
                    Velocity (1.0× line = even with prior week)
                  </div>
                  <Sparkline
                    values={rows.map((r) => r.mention_velocity)}
                    color={labelColor}
                    threshold={1.0}
                  />
                </div>
              </div>

              {/* Snapshot table */}
              <div style={{ marginTop: '0.7rem', overflowX: 'auto' }}>
                <table style={{
                  width: '100%', fontSize: '0.74rem',
                  borderCollapse: 'collapse',
                  fontFamily: 'ui-monospace, monospace',
                }}>
                  <thead>
                    <tr style={{ color: '#9a9aa3', textAlign: 'left' }}>
                      <th style={th}>When</th>
                      <th style={th}>7d</th>
                      <th style={th}>Prior 7d</th>
                      <th style={th}>Velocity</th>
                      <th style={th}>Label</th>
                      <th style={th}>Bull / Bear</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.slice().reverse().slice(0, 30).map((r, i) => (
                      <tr key={i} style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={td}>{fmtDateTime(r.fetched_at)}</td>
                        <td style={td}>{r.mentions_7d}</td>
                        <td style={td}>{r.mentions_prior_7d}</td>
                        <td style={td}>{r.mention_velocity.toFixed(2)}×</td>
                        <td style={{ ...td, color: LABEL_COLOR[r.momentum_label || 'quiet'] }}>
                          {r.momentum_label || '—'}
                        </td>
                        <td style={td}>{r.bullish} / {r.bearish}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {rows.length > 30 && (
                  <div style={{ fontSize: '0.7rem', color: '#6a6a72', marginTop: 4 }}>
                    Showing 30 most-recent of {rows.length} total snapshots.
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* When the trend started — meta */}
        {rows && rows.length > 0 && (
          <div style={{ fontSize: '0.68rem', color: '#6a6a72', marginTop: '0.4rem' }}>
            History collected since {fmtDate(rows[0].fetched_at)}. Each row
            = one chatter fetch (cron at 5:30 AM ET + on-demand when you
            open this ticker).
          </div>
        )}
      </div>
    </div>
  );
}


function MetricCell({ label, value, color, hint }: {
  label: string; value: string; color?: string; hint?: string;
}) {
  return (
    <div style={{
      padding: '0.45rem 0.6rem',
      background: 'rgba(20,20,22,0.55)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 5,
    }}>
      <div style={{
        fontSize: '0.62rem',
        color: '#9a9aa3',
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        marginBottom: 2,
      }}>
        {label}
      </div>
      <div className="mono" style={{
        fontSize: '1rem', fontWeight: 700,
        color: color || '#e6e6e6',
      }}>
        {value}
      </div>
      {hint && (
        <div style={{ fontSize: '0.62rem', color: '#6a6a72', marginTop: 1 }}>
          {hint}
        </div>
      )}
    </div>
  );
}


const th: React.CSSProperties = {
  padding: '4px 6px',
  fontWeight: 700,
  fontSize: '0.66rem',
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
};
const td: React.CSSProperties = {
  padding: '4px 6px',
  color: '#cfcfd4',
};
