/* GaugeTrend — the market-gauge score over time (Ajay 2026-06-13: "a trend graph
   in the market gauge page storing previous reads"). Reads /market/gauge/history
   (one point per ET day). Bands: ≥67 Constructive (green), 34–66 Caution (amber),
   <34 Risk-Off (red). History accumulates from 2026-06-13; earlier reads weren't
   retained, so the line is short at first. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

type Row = { date_et: string; score: number; state?: string };

const C_RISK = '#ef4444';
const C_CAUTION = '#d97706';
const C_CONSTR = '#10b981';
const bandColor = (s: number) => (s >= 67 ? C_CONSTR : s >= 34 ? C_CAUTION : C_RISK);
const fmtDate = (d: string) => { const p = d.split('-'); return p.length === 3 ? `${p[1]}/${p[2]}` : d; };

function Chart({ data }: { data: Row[] }) {
  const W = 640, H = 180, PL = 30, PR = 14, PT = 12, PB = 22;
  const iw = W - PL - PR, ih = H - PT - PB;
  const n = data.length;
  const [hover, setHover] = useState<number | null>(null);
  const x = (i: number) => PL + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
  const y = (s: number) => PT + (1 - Math.max(0, Math.min(100, s)) / 100) * ih;
  const line = data.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(d.score).toFixed(1)}`).join(' ');
  const last = data[n - 1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
         aria-label="Market gauge score over time" style={{ display: 'block' }}>
      <rect x={PL} y={y(100)} width={iw} height={y(67) - y(100)} fill="rgba(16,185,129,0.10)" />
      <rect x={PL} y={y(67)} width={iw} height={y(34) - y(67)} fill="rgba(217,119,6,0.10)" />
      <rect x={PL} y={y(34)} width={iw} height={y(0) - y(34)} fill="rgba(239,68,68,0.10)" />
      {[67, 34].map((t) => (
        <g key={t}>
          <line x1={PL} y1={y(t)} x2={PL + iw} y2={y(t)} stroke="var(--hairline,#2a2a2a)" strokeDasharray="3 3" />
          <text x={PL - 4} y={y(t) + 3} textAnchor="end" fontSize="9" fill="var(--cm-slate,#8595ad)">{t}</text>
        </g>
      ))}
      <text x={PL - 4} y={y(100) + 8} textAnchor="end" fontSize="9" fill="var(--cm-slate,#8595ad)">100</text>
      <text x={PL - 4} y={y(0)} textAnchor="end" fontSize="9" fill="var(--cm-slate,#8595ad)">0</text>
      <path d={line} fill="none" stroke={bandColor(last.score)} strokeWidth="2" />
      {data.map((d, i) => {
        const cx = x(i), cy = y(d.score), isHover = hover === i;
        return (
          <g key={i}>
            <circle cx={cx} cy={cy} r={isHover ? 4.5 : i === n - 1 ? 3.5 : 2} fill={bandColor(d.score)} />
            {/* invisible larger hit target so each dot is easy to hover / tap */}
            <circle cx={cx} cy={cy} r={11} fill="transparent" style={{ cursor: 'pointer' }}
                    onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
                    onClick={() => setHover((h) => (h === i ? null : i))}>
              <title>{`${fmtDate(d.date_et)} · score ${d.score}${d.state ? ` · ${d.state}` : ''}`}</title>
            </circle>
          </g>
        );
      })}
      {/* score label — always on the last point, and on whichever dot is hovered */}
      {hover !== n - 1 && (
        <text x={x(n - 1)} y={y(last.score) - 7} textAnchor="middle" fontSize="11" fontWeight={700} fill={bandColor(last.score)}>{last.score}</text>
      )}
      {hover != null && (() => {
        const d = data[hover], cx = x(hover), cy = y(d.score);
        const below = cy - 14 < PT;          // near the top → drop the label below the dot
        return (
          <text x={cx} y={below ? cy + 15 : cy - 7} textAnchor="middle" fontSize="11"
                fontWeight={700} fill={bandColor(d.score)} pointerEvents="none">{d.score}</text>
        );
      })()}
      <text x={x(0)} y={H - 6} textAnchor="start" fontSize="9" fill="var(--cm-slate,#8595ad)">{fmtDate(data[0].date_et)}</text>
      <text x={x(n - 1)} y={H - 6} textAnchor="end" fontSize="9" fill="var(--cm-slate,#8595ad)">{fmtDate(last.date_et)}</text>
    </svg>
  );
}

export function GaugeTrend({ days = 90 }: { days?: number }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/market/gauge/history?days=${days}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive) { setRows(j?.rows ?? []); setLoading(false); } })
      .catch(() => { if (alive) { setRows([]); setLoading(false); } });
    return () => { alive = false; };
  }, [days]);

  if (loading) return null;
  const data = rows ?? [];

  return (
    <section className="mg-trend" style={{ marginTop: '1.25rem' }}>
      <div className="eyebrow" style={{ marginBottom: '0.5rem' }}>📈 Gauge trend</div>
      {data.length < 2 ? (
        <p style={{ color: 'var(--cm-slate,#8595ad)', fontSize: '0.8rem', lineHeight: 1.5 }}>
          Building history — {data.length} daily read{data.length === 1 ? '' : 's'} stored so far.
          The line fills in over the coming days (one point per trading day); earlier reads weren't retained.
        </p>
      ) : (
        <Chart data={data} />
      )}
    </section>
  );
}
