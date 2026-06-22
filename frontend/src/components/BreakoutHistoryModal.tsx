/* BreakoutHistoryModal — "where did each breakout actually fire?" (Ajay
   2026-06-15: "add a trend page or modal of the breakouts when clicked on the
   breakout chip... To see where the breakout occurred").

   Opened from the 🚀 BreakoutStats chip. Fetches /sepa/breakout/{symbol}/history
   and plots the trailing-year CLOSE line with a 🟢 marker pinned at every
   volume-confirmed breakout bar (close above the prior 21-day high on >1.5×
   average volume — Minervini, Trade Like a Stock Market Wizard p.203), plus a
   dated list with each breakout's price + volume surge.

   Display-only. Matches the SignalDrillModal pattern: portal, Escape +
   click-outside to close. */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { API } from '../lib/apiBase';
import { fmtVol } from './BreakoutStats';

type SeriesPt = { date: string; close: number; volume: number };
/** "Whose hands fired this breakout?" — institutional accumulation vs churn
 *  (Minervini, Think & Trade Like a Champion p.186). volume.breakout_footprint. */
type Footprint = {
  hands: 'heavy_institutional' | 'institutional' | 'light' | 'suspect';
  strength: number;            // 0-100
  close_location: number;      // -1 (closed at low) .. +1 (closed at high)
  vol_ratio?: number | null;
  up_days: number;
  down_days: number;
  up_down_vol_ratio?: number | null;
  big_block: boolean;
};
type Marker = {
  date: string; close: number; volume: number;
  vol_ratio?: number | null;
  footprint?: Footprint | null;
};
type Emerging = {
  emerging: boolean;
  distance_to_high_pct?: number;
  pivot_price?: number;
  cmf?: number | null;
  up_down_vol_ratio?: number | null;
  pocket_pivot?: boolean;
  hands?: 'institutional' | 'light';
  strength?: number;
};
type History = {
  ok: boolean;
  symbol: string;
  last_close?: number | null;
  breakout_count?: number | null;
  window_bars?: number | null;
  avg_vol_50?: number | null;
  series: SeriesPt[];
  breakouts: Marker[];
  emerging?: Emerging | null;
};

/** hands → colour + glyph + label, shared by the chart markers and the list. */
const HANDS_META: Record<Footprint['hands'], { color: string; glyph: string; label: string }> = {
  heavy_institutional: { color: '#10b981', glyph: '🟢', label: 'Heavy institutional accumulation' },
  institutional:       { color: '#34d399', glyph: '🟢', label: 'Institutional accumulation' },
  light:               { color: '#94a3b8', glyph: '⚪', label: 'Light — low-conviction breakout' },
  suspect:             { color: '#f59e0b', glyph: '🟠', label: 'Suspect — churn (weak close on heavy volume)' },
};
const handsMeta = (h?: Footprint['hands'] | null) =>
  (h && HANDS_META[h]) || { color: '#10b981', glyph: '🟢', label: 'Volume-confirmed breakout' };

/** Multi-line native-hover text for a breakout marker — the "who" read. */
function markerTitle(m: Marker): string {
  const lines = [`${fmtDate(m.date)} · $${m.close.toFixed(2)}`];
  const fp = m.footprint;
  if (fp) {
    const loc = fp.close_location > 0.33 ? 'closed near the high'
      : fp.close_location < 0 ? 'closed in the lower half (gave it back)'
      : 'closed mid-range';
    lines.push(`${fp.vol_ratio ? `${fp.vol_ratio}× volume · ` : ''}${loc}`);
    lines.push(`${fp.up_days} up / ${fp.down_days} down days into it`);
    lines.push(`→ ${handsMeta(fp.hands).label} (${fp.strength}/100)`);
  } else if (m.vol_ratio) {
    lines.push(`${m.vol_ratio}× volume`);
  }
  return lines.join('\n');
}

const fmtDate = (d: string) => {
  const p = d.split('-');
  return p.length === 3 ? `${p[1]}/${p[2]}/${p[0].slice(2)}` : d;
};

function Chart({ h }: { h: History }) {
  const data = h.series || [];
  const n = data.length;
  if (n < 2) {
    return <p className="mono" style={{ opacity: 0.7, fontSize: '0.8rem' }}>
      Not enough price history to chart.
    </p>;
  }
  const W = 680, H = 240, PL = 42, PR = 12, PT = 14, PB = 26;
  const iw = W - PL - PR, ih = H - PT - PB;
  const closes = data.map((d) => d.close);
  const lo = Math.min(...closes), hi = Math.max(...closes);
  const span = hi - lo || 1;
  const x = (i: number) => PL + (i / (n - 1)) * iw;
  const y = (c: number) => PT + (1 - (c - lo) / span) * ih;
  const line = data.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(d.close).toFixed(1)}`).join(' ');

  // Pin each breakout marker to its bar in the series (match by date).
  const idxByDate = new Map(data.map((d, i) => [d.date, i] as const));
  const marks = (h.breakouts || [])
    .map((b) => ({ b, i: idxByDate.get(b.date) }))
    .filter((m): m is { b: Marker; i: number } => m.i != null);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
         aria-label={`${h.symbol} close price with ${marks.length} breakout markers`}
         style={{ display: 'block' }}>
      <line x1={PL} y1={y(hi)} x2={PL + iw} y2={y(hi)} stroke="var(--hairline,#2a2a2a)" strokeDasharray="3 3" />
      <line x1={PL} y1={y(lo)} x2={PL + iw} y2={y(lo)} stroke="var(--hairline,#2a2a2a)" strokeDasharray="3 3" />
      <text x={PL - 5} y={y(hi) + 3} textAnchor="end" fontSize="9" fill="var(--cm-slate,#8595ad)">${hi.toFixed(hi < 20 ? 1 : 0)}</text>
      <text x={PL - 5} y={y(lo) + 3} textAnchor="end" fontSize="9" fill="var(--cm-slate,#8595ad)">${lo.toFixed(lo < 20 ? 1 : 0)}</text>

      {/* vertical guide at each breakout, tinted by whose hands fired it */}
      {marks.map((m, k) => {
        const col = handsMeta(m.b.footprint?.hands).color;
        return (
          <line key={`g${k}`} x1={x(m.i)} y1={PT} x2={x(m.i)} y2={PT + ih}
                stroke={col} strokeOpacity={0.18} strokeWidth="1" />
        );
      })}
      {/* close line */}
      <path d={line} fill="none" stroke="#cbd5e1" strokeWidth="1.5" />
      {/* breakout markers — colour = whose hands (institutional vs churn) */}
      {marks.map((m, k) => {
        const meta = handsMeta(m.b.footprint?.hands);
        const heavy = m.b.footprint?.hands === 'heavy_institutional';
        return (
          <circle key={`m${k}`} cx={x(m.i)} cy={y(m.b.close)} r={heavy ? 4.4 : 3.6}
                  fill={meta.color} stroke="#0b1220" strokeWidth="0.6">
            <title>{markerTitle(m.b)}</title>
          </circle>
        );
      })}
      {/* emerging breakout — a hollow dashed ring pinned to the LAST bar,
          "setting up now" (the forward read), with whose hands are building it */}
      {h.emerging?.emerging && (
        <circle cx={x(n - 1)} cy={y(data[n - 1].close)} r="6"
                fill="none" stroke="#38bdf8" strokeWidth="1.6" strokeDasharray="2.5 2">
          <title>{`Emerging breakout — setting up now\n${h.emerging.distance_to_high_pct}% under the $${h.emerging.pivot_price} pivot\n→ ${h.emerging.hands === 'institutional' ? 'institutional hands building' : 'light accumulation'}${h.emerging.pocket_pivot ? ' · pocket pivot' : ''}`}</title>
        </circle>
      )}
      <text x={x(0)} y={H - 8} textAnchor="start" fontSize="9" fill="var(--cm-slate,#8595ad)">{fmtDate(data[0].date)}</text>
      <text x={x(n - 1)} y={H - 8} textAnchor="end" fontSize="9" fill="var(--cm-slate,#8595ad)">{fmtDate(data[n - 1].date)}</text>
    </svg>
  );
}

/* The fetch + chart + list — shared by the modal (chip drill) AND the SEPA
   detail page's Breakout tab. */
export function BreakoutHistoryBody({ symbol }: { symbol: string }) {
  const [h, setH] = useState<History | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    let alive = true;
    setState('loading');
    fetch(`${API}/sepa/breakout/${encodeURIComponent(symbol)}/history`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (!alive) return;
        if (j && j.ok) { setH(j as History); setState('ready'); }
        else setState('error');
      })
      .catch(() => { if (alive) setState('error'); });
    return () => { alive = false; };
  }, [symbol]);

  const count = h?.breakout_count ?? h?.breakouts?.length ?? 0;

  return (
    <>
      <div className="eyebrow" style={{ fontSize: '0.66rem', color: '#9aa8c8' }}>
        Breakout history · last 1y
      </div>
      <h3 style={{ margin: '0.15rem 0 0', fontSize: '1.05rem' }}>
        🚀 {symbol} — {count} volume-confirmed breakout{count === 1 ? '' : 's'}
      </h3>

      {state === 'loading' && (
        <p className="mono" style={{ opacity: 0.7, fontSize: '0.8rem', marginTop: '1rem' }}>…loading breakout history</p>
      )}
      {state === 'error' && (
        <p className="mono" style={{ color: '#fca5a5', fontSize: '0.8rem', marginTop: '1rem' }}>
          Couldn't load breakout history for {symbol}.
        </p>
      )}

      {state === 'ready' && h && (
        <>
          <p style={{ fontSize: '0.74rem', color: '#9aa8c8', margin: '0.5rem 0 0.5rem', lineHeight: 1.5 }}>
            Each marker is a <strong>volume-confirmed breakout</strong> — a close above the prior
            21-day high on more than 1.5× average volume (<em>Trade Like a Stock Market Wizard</em>
            p.203). <strong>Colour = whose hands fired it:</strong> a real breakout is institutions
            accumulating; a weak close on heavy volume is churn (<em>Think &amp; Trade Like a
            Champion</em> p.186). Hover any point for the read.
          </p>

          {/* who's-behind-it legend */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem 0.9rem', fontSize: '0.66rem',
                        color: '#9aa8c8', margin: '0 0 0.6rem' }}>
            {(['heavy_institutional', 'institutional', 'light', 'suspect'] as const).map((k) => (
              <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 9, height: 9, borderRadius: '50%', background: HANDS_META[k].color,
                               display: 'inline-block' }} />
                {HANDS_META[k].label.replace(/ —.*/, '')}
              </span>
            ))}
            {h.emerging?.emerging && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', border: '1.6px dashed #38bdf8',
                               display: 'inline-block' }} />
                Emerging (setting up)
              </span>
            )}
          </div>

          <Chart h={h} />

          {/* emerging callout — the forward "who's loading it now" read */}
          {h.emerging?.emerging && (
            <div style={{ marginTop: '0.7rem', padding: '0.5rem 0.7rem', borderRadius: 8,
                          border: '1px solid rgba(56,189,248,0.4)', background: 'rgba(56,189,248,0.08)',
                          fontSize: '0.74rem', color: '#cfe8ff', lineHeight: 1.5 }}>
              ⏳ <strong>Emerging breakout — setting up now.</strong> Coiling{' '}
              {h.emerging.distance_to_high_pct}% under the ${h.emerging.pivot_price} pivot with{' '}
              {h.emerging.hands === 'institutional' ? 'institutional hands building' : 'light accumulation'}
              {h.emerging.cmf != null ? ` (CMF ${h.emerging.cmf > 0 ? '+' : ''}${h.emerging.cmf})` : ''}
              {h.emerging.pocket_pivot ? ' · pocket pivot fired' : ''}. Not a breakout yet — a watch,
              not a buy (VCP/pivot, <em>TLSW</em> Ch.7).
            </div>
          )}

          {h.breakouts && h.breakouts.length > 0 ? (
            <div style={{ marginTop: '0.9rem' }}>
              <div className="eyebrow" style={{ fontSize: '0.62rem', marginBottom: 4 }}>
                Each breakout (newest first) — who fired it
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {h.breakouts.slice().reverse().map((b, i) => {
                  const meta = handsMeta(b.footprint?.hands);
                  return (
                    <div key={i} className="mono"
                         style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', alignItems: 'center',
                                  fontSize: '0.74rem', padding: '3px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <span style={{ color: meta.color, minWidth: 78 }}>{meta.glyph} {fmtDate(b.date)}</span>
                      <span style={{ color: '#cfcfd4' }}>${b.close.toFixed(2)}</span>
                      <span style={{ color: meta.color, flex: 1, textAlign: 'right',
                                     overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={`${b.footprint?.strength ?? ''}${b.footprint ? '/100' : ''}`}>
                        {meta.label.replace(/ \(.*\)/, '').replace(/ —.*/, b.footprint?.hands === 'suspect' ? ' — churn' : '')}
                      </span>
                      <span style={{ color: '#9aa8c8', minWidth: 92, textAlign: 'right' }}>
                        {fmtVol(b.volume)}{b.vol_ratio ? ` · ${b.vol_ratio}×` : ''}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <p className="mono" style={{ opacity: 0.7, fontSize: '0.78rem', marginTop: '0.75rem' }}>
              No volume-confirmed breakouts in the trailing year.
            </p>
          )}
        </>
      )}
    </>
  );
}

export function BreakoutHistoryModal({ symbol, onClose }: { symbol: string; onClose: () => void }) {
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onEsc);
    return () => window.removeEventListener('keydown', onEsc);
  }, [onClose]);

  return createPortal(
    <div role="dialog" aria-modal="true" aria-label={`${symbol} breakout history`}
         onClick={(e) => { e.stopPropagation(); onClose(); }}
         style={{
           position: 'fixed', inset: 0, background: 'rgba(4,8,16,0.72)',
           display: 'flex', alignItems: 'center', justifyContent: 'center',
           zIndex: 1000, padding: '1rem',
         }}>
      <div onClick={(e) => e.stopPropagation()}
           style={{
             position: 'relative',
             background: 'var(--cm-panel,#0f1623)', border: '1px solid var(--hairline,#243044)',
             borderRadius: 12, width: 'min(720px, 96vw)', maxHeight: '88vh', overflow: 'auto',
             padding: '1rem 1.1rem', boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
           }}>
        <button type="button" onClick={(e) => { e.stopPropagation(); onClose(); }} aria-label="Close"
                style={{ position: 'absolute', top: 8, right: 12, background: 'none', border: 'none',
                         color: '#9aa8c8', fontSize: '1.3rem', cursor: 'pointer', lineHeight: 1 }}>
          ×
        </button>
        <BreakoutHistoryBody symbol={symbol} />
      </div>
    </div>,
    document.body,
  );
}
