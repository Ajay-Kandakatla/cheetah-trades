/* RankTrendChart — "TradingView for rank" on the SEPA detail page.
   How a stock moved through the SEPA ranking over a real TIMELINE (x = date),
   rank inverted (#1 at top). Daily = last 30 days, Intraday = last 10 days.
   Axis labels are crisp HTML overlays (the SVG is stretched, so text never goes
   in it). A dotted FLOOR baseline marks the bottom/out-of-ranking level so empty
   stretches still read as "down here", not blank. Optional Score/Price overlays
   (off by default). Markers: breakout / became-buyable / stage change. Gaps
   (fell out of the ranking) stay as gaps — real values are never invented. */
import { useEffect, useMemo, useState } from 'react';
import { API } from '../lib/apiBase';

type Pt = {
  t: number; date: string | null;
  rank: number | null; total: number | null;
  score: number | null; price: number | null;
  events: string[];
};
type Resp = {
  symbol: string; granularity: string; days: number; points: Pt[];
  best_rank: number | null; worst_rank: number | null; current_rank: number | null;
};

const W = 760, H = 248;
const PAD = { l: 34, r: 12, t: 14, b: 24 };        // gutters for HTML #labels (left) + dates (bottom)
const PLOT_W = W - PAD.l - PAD.r;
const PLOT_H = H - PAD.t - PAD.b;
const RANK_COLOR = '#e2e8f0';
const SCORE_COLOR = '#10b981';
const PRICE_COLOR = '#38bdf8';
const EV: Record<string, { color: string; glyph: string; label: string }> = {
  breakout:       { color: '#10b981', glyph: '▲', label: 'Breakout on volume' },
  became_buyable: { color: '#fbbf24', glyph: '★', label: 'Became buyable' },
};
function evMeta(e: string) {
  if (e.startsWith('stage_')) return { color: '#a78bfa', glyph: '◆', label: `Stage → ${e.slice(6)}` };
  return EV[e] || { color: '#94a3b8', glyph: '•', label: e };
}
function fmtDate(tSec: number): string {
  const d = new Date(tSec * 1000);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}
const xPct = (x: number) => (x / W) * 100;
const yPct = (y: number) => (y / H) * 100;

export function RankTrendChart({ symbol }: { symbol: string }) {
  const [granularity, setGranularity] = useState<'daily' | 'intraday'>('daily');
  const [showScore, setShowScore] = useState(false);
  const [showPrice, setShowPrice] = useState(false);
  const [data, setData] = useState<Resp | null>(null);
  const [state, setState] = useState<'loading' | 'ok' | 'empty' | 'err'>('loading');
  const [hover, setHover] = useState<number | null>(null);

  const windowDays = granularity === 'daily' ? 30 : 10;

  useEffect(() => {
    let alive = true;
    setState('loading');
    fetch(`${API}/sepa/rank-history/${encodeURIComponent(symbol)}?granularity=${granularity}&days=${windowDays}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: Resp) => {
        if (!alive) return;
        setData(d);
        setState((d.points || []).some((p) => p.rank != null) ? 'ok' : 'empty');
        setHover(null);
      })
      .catch(() => alive && setState('err'));
    return () => { alive = false; };
  }, [symbol, granularity, windowDays]);

  const geom = useMemo(() => {
    const pts = (data?.points || []).filter((p) => p.t);
    const nowSec = Math.floor(Date.now() / 1000);
    const tMax = Math.max(nowSec, ...pts.map((p) => p.t));
    const tMin = tMax - windowDays * 86400;
    const span = tMax - tMin || 1;
    const maxRank = Math.min(Math.max(data?.worst_rank || 20, 10), 150);
    const prices = pts.map((p) => p.price).filter((v): v is number => v != null);
    const pMin = Math.min(...prices, Infinity), pMax = Math.max(...prices, -Infinity);
    const x = (t: number) => PAD.l + Math.max(0, Math.min(1, (t - tMin) / span)) * PLOT_W;
    const yRank = (r: number) => PAD.t + ((Math.min(r, maxRank) - 1) / (maxRank - 1 || 1)) * PLOT_H;
    const yScore = (s: number) => PAD.t + (1 - s / 100) * PLOT_H;
    const yPrice = (p: number) => pMax === pMin ? PAD.t + PLOT_H / 2
      : PAD.t + (1 - (p - pMin) / (pMax - pMin)) * PLOT_H;
    const ticks = Array.from({ length: 6 }, (_, i) => tMin + (i / 5) * span);
    const floorY = yRank(maxRank);
    return { pts, tMin, tMax, span, maxRank, x, yRank, yScore, yPrice, ticks, floorY };
  }, [data, windowDays]);

  function linePath(yOf: (p: Pt) => number | null): string {
    let d = '', pen = false;
    geom.pts.forEach((p) => {
      const y = yOf(p);
      if (y == null) { pen = false; return; }
      d += `${pen ? 'L' : 'M'}${geom.x(p.t).toFixed(1)} ${y.toFixed(1)} `;
      pen = true;
    });
    return d.trim();
  }

  if (state === 'loading') return <p className="mono rank-chart__msg">…loading rank history</p>;
  if (state === 'err') return <p className="mono rank-chart__msg">Couldn't load rank history.</p>;
  if (state === 'empty' || !data)
    return (
      <p className="mono rank-chart__msg">
        No ranking history yet for {symbol} — it builds as scans accumulate (daily).
      </p>
    );

  const hp = hover != null ? geom.pts[hover] : null;
  const rankTicks = [1, Math.round(geom.maxRank / 2), geom.maxRank];
  const lastRanked = [...geom.pts].reverse().find((p) => p.rank != null);

  return (
    <div className="rank-chart">
      <div className="rank-chart__bar">
        <div className="rank-chart__summary mono">
          best <b>#{data.best_rank}</b> · worst <b>#{data.worst_rank}</b> · now <b>#{data.current_rank ?? '—'}</b>
        </div>
        <div className="rank-chart__toggles">
          <button className={granularity === 'daily' ? 'is-on' : ''} onClick={() => setGranularity('daily')}>30d</button>
          <button className={granularity === 'intraday' ? 'is-on' : ''} onClick={() => setGranularity('intraday')}>Intraday</button>
          <span className="rank-chart__sep" />
          <button className={showScore ? 'is-on' : ''} style={{ color: showScore ? SCORE_COLOR : undefined }} onClick={() => setShowScore((v) => !v)}>Score</button>
          <button className={showPrice ? 'is-on' : ''} style={{ color: showPrice ? PRICE_COLOR : undefined }} onClick={() => setShowPrice((v) => !v)}>Price</button>
        </div>
      </div>

      <div className="rank-chart__wrap">
        <svg viewBox={`0 0 ${W} ${H}`} className="rank-chart__svg" preserveAspectRatio="none">
          {rankTicks.map((r) => (
            <line key={r} x1={PAD.l} x2={W - PAD.r} y1={geom.yRank(r)} y2={geom.yRank(r)} className="rank-chart__grid" />
          ))}
          {/* dotted FLOOR baseline — the bottom/out-of-ranking level (always shown,
              so empty stretches read as "down here" rather than blank). */}
          <line x1={PAD.l} x2={W - PAD.r} y1={geom.floorY} y2={geom.floorY} className="rank-chart__floor" />
          {showScore && <path d={linePath((p) => (p.score != null ? geom.yScore(p.score) : null))} className="rank-chart__score" />}
          {showPrice && <path d={linePath((p) => (p.price != null ? geom.yPrice(p.price) : null))} className="rank-chart__price" />}
          <path d={linePath((p) => (p.rank != null ? geom.yRank(p.rank) : null))} className="rank-chart__rank" />
          {lastRanked && <circle cx={geom.x(lastRanked.t)} cy={geom.yRank(lastRanked.rank!)} r={3.2} className="rank-chart__dot" />}
          {geom.pts.map((p, i) =>
            p.rank != null && p.events.length ? (
              <text key={i} x={geom.x(p.t)} y={geom.yRank(p.rank) - 6} textAnchor="middle"
                    className="rank-chart__ev" fill={evMeta(p.events[0]).color}>
                {evMeta(p.events[0]).glyph}
              </text>
            ) : null,
          )}
          {hp && <line x1={geom.x(hp.t)} x2={geom.x(hp.t)} y1={PAD.t} y2={PAD.t + PLOT_H} className="rank-chart__cursor" />}
          <rect x={PAD.l} y={PAD.t} width={PLOT_W} height={PLOT_H} fill="transparent"
                onMouseLeave={() => setHover(null)}
                onMouseMove={(e) => {
                  const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
                  const targetT = geom.tMin + ((e.clientX - r.left) / r.width) * geom.span;
                  let bi = 0, bd = Infinity;
                  geom.pts.forEach((p, i) => { const dd = Math.abs(p.t - targetT); if (dd < bd) { bd = dd; bi = i; } });
                  setHover(bi);
                }} />
        </svg>

        {/* crisp HTML axis labels (overlaid by %, never stretched) */}
        {rankTicks.map((r) => (
          <span key={r} className="rank-chart__ylabel mono"
                style={{ top: `${yPct(geom.yRank(r))}%` }}>#{r}</span>
        ))}
        <span className="rank-chart__floor-tag mono" style={{ top: `${yPct(geom.floorY)}%` }}>out</span>
        {geom.ticks.map((t, i) => (
          <span key={i} className="rank-chart__xlabel mono"
                style={{
                  left: `${xPct(geom.x(t))}%`,
                  top: `${yPct(PAD.t + PLOT_H + 9)}%`,
                  transform: i === 0 ? 'none' : i === 5 ? 'translateX(-100%)' : 'translateX(-50%)',
                }}>
            {fmtDate(t)}
          </span>
        ))}

        {hp && (
          <div className="rank-chart__tip" style={{ left: `${xPct(geom.x(hp.t))}%` }}>
            <div className="rank-chart__tip-date mono">{hp.date}</div>
            <div className="mono">rank <b style={{ color: RANK_COLOR }}>{hp.rank != null ? `#${hp.rank}` : 'out'}</b>{hp.total ? <span className="rank-chart__tip-dim"> / {hp.total}</span> : null}</div>
            <div className="mono">score <b style={{ color: SCORE_COLOR }}>{hp.score ?? '—'}</b> · px <b style={{ color: PRICE_COLOR }}>{hp.price != null ? `$${hp.price}` : '—'}</b></div>
            {hp.events.map((e) => (
              <div key={e} className="rank-chart__tip-ev" style={{ color: evMeta(e).color }}>{evMeta(e).glyph} {evMeta(e).label}</div>
            ))}
          </div>
        )}
      </div>

      <div className="rank-chart__legend mono">
        <span style={{ color: RANK_COLOR }}>━ rank</span>
        {showScore && <span style={{ color: SCORE_COLOR }}>━ score</span>}
        {showPrice && <span style={{ color: PRICE_COLOR }}>━ price</span>}
        <span style={{ color: EV.breakout.color }}>▲ breakout</span>
        <span style={{ color: EV.became_buyable.color }}>★ buyable</span>
        <span style={{ color: '#a78bfa' }}>◆ stage</span>
        <span className="rank-chart__tip-dim">· dotted floor = out of the ranking</span>
      </div>
      <p className="rank-chart__foot mono">Derived from SEPA scan history · not investment advice</p>
    </div>
  );
}
