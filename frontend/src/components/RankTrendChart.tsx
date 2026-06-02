/* RankTrendChart — "TradingView for rank" on the SEPA detail page.
   How a stock moved through the SEPA ranking over time: rank line (inverted —
   #1 at top), with optional SCORE and PRICE overlays, and event markers
   (breakout / became-buyable / stage change) so rank jumps line up with what
   actually happened. Daily by default; toggle to intraday. Custom SVG (matches
   the app's IntradayChart/Sparkline style — no chart dependency). */
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

const W = 720, H = 248;
const PAD = { l: 38, r: 14, t: 18, b: 22 };
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

export function RankTrendChart({ symbol }: { symbol: string }) {
  const [granularity, setGranularity] = useState<'daily' | 'intraday'>('daily');
  const [showScore, setShowScore] = useState(true);
  const [showPrice, setShowPrice] = useState(false);
  const [data, setData] = useState<Resp | null>(null);
  const [state, setState] = useState<'loading' | 'ok' | 'empty' | 'err'>('loading');
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    setState('loading');
    fetch(`${API}/sepa/rank-history/${encodeURIComponent(symbol)}?granularity=${granularity}&days=30`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: Resp) => {
        if (!alive) return;
        setData(d);
        setState((d.points || []).some((p) => p.rank != null) ? 'ok' : 'empty');
      })
      .catch(() => alive && setState('err'));
    return () => { alive = false; };
  }, [symbol, granularity]);

  const geom = useMemo(() => {
    const pts = data?.points || [];
    const n = pts.length;
    const maxRank = Math.min(Math.max(data?.worst_rank || 20, 10), 150); // clamp for resolution
    const prices = pts.map((p) => p.price).filter((v): v is number => v != null);
    const pMin = Math.min(...prices, Infinity), pMax = Math.max(...prices, -Infinity);
    const x = (i: number) => PAD.l + (n <= 1 ? 0 : (i / (n - 1)) * PLOT_W);
    const yRank = (r: number) => PAD.t + ((Math.min(r, maxRank) - 1) / (maxRank - 1 || 1)) * PLOT_H;
    const yScore = (s: number) => PAD.t + (1 - s / 100) * PLOT_H;
    const yPrice = (p: number) => pMax === pMin ? PAD.t + PLOT_H / 2
      : PAD.t + (1 - (p - pMin) / (pMax - pMin)) * PLOT_H;
    return { pts, n, maxRank, x, yRank, yScore, yPrice, pMin, pMax };
  }, [data]);

  // Build a path that BREAKS at null ranks (gaps = stock outside the ranked set).
  function linePath(yOf: (p: Pt) => number | null): string {
    let d = '', pen = false;
    geom.pts.forEach((p, i) => {
      const y = yOf(p);
      if (y == null) { pen = false; return; }
      d += `${pen ? 'L' : 'M'}${geom.x(i).toFixed(1)} ${y.toFixed(1)} `;
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

  return (
    <div className="rank-chart">
      <div className="rank-chart__bar">
        <div className="rank-chart__summary mono">
          best <b>#{data.best_rank}</b> · worst <b>#{data.worst_rank}</b> · now <b>#{data.current_rank ?? '—'}</b>
        </div>
        <div className="rank-chart__toggles">
          <button className={granularity === 'daily' ? 'is-on' : ''} onClick={() => setGranularity('daily')}>Daily</button>
          <button className={granularity === 'intraday' ? 'is-on' : ''} onClick={() => setGranularity('intraday')}>Intraday</button>
          <span className="rank-chart__sep" />
          <button className={showScore ? 'is-on' : ''} style={{ color: showScore ? SCORE_COLOR : undefined }} onClick={() => setShowScore((v) => !v)}>Score</button>
          <button className={showPrice ? 'is-on' : ''} style={{ color: showPrice ? PRICE_COLOR : undefined }} onClick={() => setShowPrice((v) => !v)}>Price</button>
        </div>
      </div>

      <div className="rank-chart__wrap">
        <svg viewBox={`0 0 ${W} ${H}`} className="rank-chart__svg" preserveAspectRatio="none">
          {/* rank gridlines + axis labels (#1 at top) */}
          {rankTicks.map((r) => (
            <g key={r}>
              <line x1={PAD.l} x2={W - PAD.r} y1={geom.yRank(r)} y2={geom.yRank(r)} className="rank-chart__grid" />
              <text x={PAD.l - 6} y={geom.yRank(r) + 3} className="rank-chart__axis" textAnchor="end">#{r}</text>
            </g>
          ))}
          {/* overlays first (under the rank line) */}
          {showScore && <path d={linePath((p) => (p.score != null ? geom.yScore(p.score) : null))} className="rank-chart__score" />}
          {showPrice && <path d={linePath((p) => (p.price != null ? geom.yPrice(p.price) : null))} className="rank-chart__price" />}
          {/* rank line */}
          <path d={linePath((p) => (p.rank != null ? geom.yRank(p.rank) : null))} className="rank-chart__rank" />
          {/* event markers on the rank line */}
          {geom.pts.map((p, i) =>
            p.rank != null && p.events.length ? (
              <text key={i} x={geom.x(i)} y={geom.yRank(p.rank) - 6} textAnchor="middle"
                    className="rank-chart__ev" fill={evMeta(p.events[0]).color}>
                {evMeta(p.events[0]).glyph}
              </text>
            ) : null,
          )}
          {/* hover guide */}
          {hp && (
            <line x1={geom.x(hover!)} x2={geom.x(hover!)} y1={PAD.t} y2={PAD.t + PLOT_H} className="rank-chart__cursor" />
          )}
          {/* hit area */}
          <rect x={PAD.l} y={PAD.t} width={PLOT_W} height={PLOT_H} fill="transparent"
                onMouseLeave={() => setHover(null)}
                onMouseMove={(e) => {
                  const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
                  const rel = (e.clientX - r.left) / r.width;
                  setHover(Math.max(0, Math.min(geom.n - 1, Math.round(rel * (geom.n - 1)))));
                }} />
        </svg>

        {hp && (
          <div className="rank-chart__tip" style={{ left: `${(geom.x(hover!) / W) * 100}%` }}>
            <div className="rank-chart__tip-date mono">{hp.date}</div>
            <div className="mono">rank <b style={{ color: RANK_COLOR }}>{hp.rank != null ? `#${hp.rank}` : '—'}</b>{hp.total ? <span className="rank-chart__tip-dim"> / {hp.total}</span> : null}</div>
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
      </div>
      <p className="rank-chart__foot mono">Derived from SEPA scan history · not investment advice</p>
    </div>
  );
}
