/* SepaRankCompare — multi-stock rank-trend comparison (portfolio page).
   Compares several names' SEPA rank over a date window without the spaghetti
   problem, two ways (research-backed):
     • Overlay (bump chart) — all on one axis, with FOCUS+CONTEXT (hover a name
       → it pops, the rest fade) and DIRECT END-LABELS instead of a legend.
     • Small multiples — one mini panel per name; never tangled.
   Multi-select from the leaderboard; rank inverted (#1 top). Custom SVG. */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';

type Pt = { t: number; date: string | null; rank: number | null; total: number | null; score: number | null };
type Series = { points: Pt[]; best_rank: number | null; worst_rank: number | null; current_rank: number | null };
type Batch = { symbols: string[]; days: number; granularity: string; series: Record<string, Series> };

const COLORS = ['#10b981', '#38bdf8', '#fbbf24', '#a78bfa', '#f472b6', '#fb923c',
                '#34d399', '#60a5fa', '#facc15', '#c084fc', '#f87171', '#4ade80'];
const W = 760, H = 300;
const PAD = { l: 34, r: 60, t: 14, b: 24 };       // right gutter for end-labels
const PLOT_W = W - PAD.l - PAD.r;
const PLOT_H = H - PAD.t - PAD.b;
const xPct = (x: number) => (x / W) * 100;
const yPct = (y: number) => (y / H) * 100;
const fmtDate = (tSec: number) => { const d = new Date(tSec * 1000); return `${d.getMonth() + 1}/${d.getDate()}`; };

export function SepaRankCompare() {
  const [universe, setUniverse] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [mode, setMode] = useState<'overlay' | 'multiples'>('overlay');
  const [windowDays, setWindowDays] = useState(30);
  const [data, setData] = useState<Batch | null>(null);
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/sepa/leaderboard?n=14`)
      .then((r) => r.json())
      .then((d) => {
        if (!alive) return;
        const syms: string[] = (d.leaders || []).map((l: { symbol: string }) => l.symbol);
        setUniverse(syms);
        setSelected(syms.slice(0, 5));
      })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!selected.length) { setData(null); return; }
    let alive = true;
    fetch(`${API}/sepa/rank-history-batch?symbols=${selected.join(',')}&days=${windowDays}&granularity=daily`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error())))
      .then((d: Batch) => alive && setData(d))
      .catch(() => {});
    return () => { alive = false; };
  }, [selected, windowDays]);

  const colorOf = (sym: string) => COLORS[Math.max(0, selected.indexOf(sym)) % COLORS.length];
  const toggle = (sym: string) =>
    setSelected((s) => s.includes(sym) ? s.filter((x) => x !== sym) : s.length >= 8 ? s : [...s, sym]);

  const geom = useMemo(() => {
    const nowSec = Math.floor(Date.now() / 1000);
    const tMax = nowSec, tMin = nowSec - windowDays * 86400, span = tMax - tMin || 1;
    let worst = 10;
    if (data) for (const s of Object.values(data.series)) worst = Math.max(worst, s.worst_rank || 10);
    const maxRank = Math.min(worst, 150);
    const x = (t: number) => PAD.l + Math.max(0, Math.min(1, (t - tMin) / span)) * PLOT_W;
    const yRank = (r: number) => PAD.t + ((Math.min(r, maxRank) - 1) / (maxRank - 1 || 1)) * PLOT_H;
    const ticks = Array.from({ length: 6 }, (_, i) => tMin + (i / 5) * span);
    return { tMin, tMax, span, maxRank, x, yRank, ticks };
  }, [data, windowDays]);

  function path(pts: Pt[], yOf: (r: number) => number, x: (t: number) => number): string {
    let d = '', pen = false;
    for (const p of pts) {
      if (p.rank == null) { pen = false; continue; }
      d += `${pen ? 'L' : 'M'}${x(p.t).toFixed(1)} ${yOf(p.rank).toFixed(1)} `;
      pen = true;
    }
    return d.trim();
  }

  const rankTicks = [1, Math.round(geom.maxRank / 2), geom.maxRank];

  return (
    <section className="rank-cmp">
      <div className="rank-cmp__head">
        <span className="eyebrow">📈 Compare rank trends</span>
        <div className="rank-cmp__toggles">
          <button className={mode === 'overlay' ? 'is-on' : ''} onClick={() => setMode('overlay')}>Overlay</button>
          <button className={mode === 'multiples' ? 'is-on' : ''} onClick={() => setMode('multiples')}>Small multiples</button>
          <span className="rank-cmp__sep" />
          <button className={windowDays === 30 ? 'is-on' : ''} onClick={() => setWindowDays(30)}>30d</button>
          <button className={windowDays === 14 ? 'is-on' : ''} onClick={() => setWindowDays(14)}>14d</button>
        </div>
      </div>
      <p className="rank-cmp__sub">Pick names to compare how their rank moved (hover to focus one). Up to 8.</p>

      {/* multi-select chips */}
      <div className="rank-cmp__picks">
        {universe.map((sym) => {
          const on = selected.includes(sym);
          return (
            <button key={sym} className={`rank-cmp__chip${on ? ' is-on' : ''}`}
                    style={on ? { color: colorOf(sym), borderColor: colorOf(sym) } : undefined}
                    onClick={() => toggle(sym)}>{sym}</button>
          );
        })}
      </div>

      {!data || !selected.length ? (
        <p className="rank-cmp__msg mono">Select at least one name to chart.</p>
      ) : mode === 'overlay' ? (
        <div className="rank-cmp__wrap">
          <svg viewBox={`0 0 ${W} ${H}`} className="rank-cmp__svg" preserveAspectRatio="none">
            {rankTicks.map((r) => <line key={r} x1={PAD.l} x2={W - PAD.r} y1={geom.yRank(r)} y2={geom.yRank(r)} className="rank-cmp__grid" />)}
            {selected.map((sym) => {
              const s = data.series[sym]; if (!s) return null;
              const dim = hover && hover !== sym;
              return <path key={sym} d={path(s.points, geom.yRank, geom.x)} fill="none"
                           stroke={dim ? '#475569' : colorOf(sym)} strokeWidth={hover === sym ? 2.6 : 1.8}
                           opacity={dim ? 0.45 : 1} vectorEffect="non-scaling-stroke"
                           style={{ transition: 'opacity .12s' }} />;
            })}
          </svg>
          {/* rank labels (left) */}
          {rankTicks.map((r) => <span key={r} className="rank-cmp__ylabel mono" style={{ top: `${yPct(geom.yRank(r))}%` }}>#{r}</span>)}
          {/* date labels (bottom) */}
          {geom.ticks.map((t, i) => (
            <span key={i} className="rank-cmp__xlabel mono"
                  style={{ left: `${xPct(geom.x(t))}%`, top: `${yPct(PAD.t + PLOT_H + 9)}%`,
                           transform: i === 0 ? 'none' : i === 5 ? 'translateX(-100%)' : 'translateX(-50%)' }}>{fmtDate(t)}</span>
          ))}
          {/* direct END-LABELS (replace the legend) */}
          {selected.map((sym) => {
            const s = data.series[sym]; if (!s) return null;
            const last = [...s.points].reverse().find((p) => p.rank != null); if (!last) return null;
            const dim = hover && hover !== sym;
            return (
              <span key={sym} className="rank-cmp__endlabel mono"
                    style={{ top: `${yPct(geom.yRank(last.rank!))}%`, left: `${xPct(PAD.l + PLOT_W) + 0.6}%`,
                             color: dim ? '#64748b' : colorOf(sym), fontWeight: hover === sym ? 700 : 500 }}
                    onMouseEnter={() => setHover(sym)} onMouseLeave={() => setHover(null)}>
                {sym} #{last.rank}
              </span>
            );
          })}
        </div>
      ) : (
        <div className="rank-cmp__cells">
          {selected.map((sym) => {
            const s = data.series[sym]; if (!s) return null;
            const w = 220, h = 96, pl = 4, pr = 4, pt = 8, pb = 6;
            const pw = w - pl - pr, ph = h - pt - pb;
            const x = (t: number) => pl + Math.max(0, Math.min(1, (t - geom.tMin) / geom.span)) * pw;
            const yR = (r: number) => pt + ((Math.min(r, geom.maxRank) - 1) / (geom.maxRank - 1 || 1)) * ph;
            return (
              <div key={sym} className="rank-cmp__cell">
                <div className="rank-cmp__cell-head">
                  <Link to={`/sepa/${sym}`} className="rank-cmp__cell-sym" style={{ color: colorOf(sym) }}>{sym}</Link>
                  <span className="mono rank-cmp__cell-meta">best #{s.best_rank} · now #{s.current_rank ?? '—'}</span>
                </div>
                <svg viewBox={`0 0 ${w} ${h}`} className="rank-cmp__cell-svg" preserveAspectRatio="none">
                  <line x1={pl} x2={w - pr} y1={yR(geom.maxRank)} y2={yR(geom.maxRank)} className="rank-cmp__grid" />
                  <path d={path(s.points, yR, x)} fill="none" stroke={colorOf(sym)} strokeWidth={1.8} vectorEffect="non-scaling-stroke" />
                </svg>
              </div>
            );
          })}
        </div>
      )}
      <p className="rank-cmp__foot mono">Shared #1-at-top axis · from SEPA scan history · not investment advice</p>
    </section>
  );
}
