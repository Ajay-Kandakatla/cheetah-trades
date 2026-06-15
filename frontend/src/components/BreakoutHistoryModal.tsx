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
type Marker = { date: string; close: number; volume: number; vol_ratio?: number | null };
type History = {
  ok: boolean;
  symbol: string;
  last_close?: number | null;
  breakout_count?: number | null;
  window_bars?: number | null;
  avg_vol_50?: number | null;
  series: SeriesPt[];
  breakouts: Marker[];
};

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

      {/* vertical guide at each breakout */}
      {marks.map((m, k) => (
        <line key={`g${k}`} x1={x(m.i)} y1={PT} x2={x(m.i)} y2={PT + ih}
              stroke="rgba(16,185,129,0.22)" strokeWidth="1" />
      ))}
      {/* close line */}
      <path d={line} fill="none" stroke="#cbd5e1" strokeWidth="1.5" />
      {/* breakout markers */}
      {marks.map((m, k) => (
        <circle key={`m${k}`} cx={x(m.i)} cy={y(m.b.close)} r="3.6"
                fill="#10b981" stroke="#0b1220" strokeWidth="0.6">
          <title>{`${fmtDate(m.b.date)} · $${m.b.close.toFixed(2)}${m.b.vol_ratio ? ` · ${m.b.vol_ratio}× vol` : ''}`}</title>
        </circle>
      ))}
      <text x={x(0)} y={H - 8} textAnchor="start" fontSize="9" fill="var(--cm-slate,#8595ad)">{fmtDate(data[0].date)}</text>
      <text x={x(n - 1)} y={H - 8} textAnchor="end" fontSize="9" fill="var(--cm-slate,#8595ad)">{fmtDate(data[n - 1].date)}</text>
    </svg>
  );
}

export function BreakoutHistoryModal({ symbol, onClose }: { symbol: string; onClose: () => void }) {
  const [h, setH] = useState<History | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onEsc);
    return () => window.removeEventListener('keydown', onEsc);
  }, [onClose]);

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
             background: 'var(--cm-panel,#0f1623)', border: '1px solid var(--hairline,#243044)',
             borderRadius: 12, width: 'min(720px, 96vw)', maxHeight: '88vh', overflow: 'auto',
             padding: '1rem 1.1rem', boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
           }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem' }}>
          <div>
            <div className="eyebrow" style={{ fontSize: '0.66rem', color: '#9aa8c8' }}>
              Breakout history · last 1y
            </div>
            <h3 style={{ margin: '0.15rem 0 0', fontSize: '1.05rem' }}>
              🚀 {symbol} — {count} volume-confirmed breakout{count === 1 ? '' : 's'}
            </h3>
          </div>
          <button type="button" onClick={(e) => { e.stopPropagation(); onClose(); }} aria-label="Close"
                  style={{ background: 'none', border: 'none', color: '#9aa8c8', fontSize: '1.3rem', cursor: 'pointer', lineHeight: 1 }}>
            ×
          </button>
        </div>

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
            <p style={{ fontSize: '0.74rem', color: '#9aa8c8', margin: '0.5rem 0 0.75rem', lineHeight: 1.5 }}>
              Each 🟢 marks where a <strong>volume-confirmed breakout</strong> fired — a close above the
              prior 21-day high on more than 1.5× average volume (Minervini,
              <em> Trade Like a Stock Market Wizard</em> p.203).
            </p>
            <Chart h={h} />

            {h.breakouts && h.breakouts.length > 0 ? (
              <div style={{ marginTop: '0.9rem' }}>
                <div className="eyebrow" style={{ fontSize: '0.62rem', marginBottom: 4 }}>
                  Each breakout (newest first)
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {h.breakouts.slice().reverse().map((b, i) => (
                    <div key={i} className="mono"
                         style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem',
                                  fontSize: '0.74rem', padding: '3px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <span style={{ color: '#10b981' }}>🟢 {fmtDate(b.date)}</span>
                      <span style={{ color: '#cfcfd4' }}>${b.close.toFixed(2)}</span>
                      <span style={{ color: '#9aa8c8' }}>
                        {fmtVol(b.volume)} sh{b.vol_ratio ? ` · ${b.vol_ratio}×` : ''}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="mono" style={{ opacity: 0.7, fontSize: '0.78rem', marginTop: '0.75rem' }}>
                No volume-confirmed breakouts in the trailing year.
              </p>
            )}
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
