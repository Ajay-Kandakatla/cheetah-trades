/* SepaRankCompare — multi-stock rank-trend comparison (portfolio page).
   Compares several names' SEPA rank over a date window without the spaghetti
   problem, two ways (research-backed):
     • Overlay (bump chart) — all on one axis, with FOCUS+CONTEXT (hover a name
       → it pops, the rest fade) + DIRECT END-LABELS, and a per-DATE hover/pin
       readout (date · each name's rank & volume).
     • Small multiples — one mini panel per name; never tangled.
   Multi-select from the leaderboard; rank inverted (#1 top). Custom SVG. */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';

type Pt = { t: number; date: string | null; rank: number | null; total: number | null;
            score: number | null; volume: number | null; price: number | null };
type Series = { points: Pt[]; best_rank: number | null; worst_rank: number | null; current_rank: number | null };
type Batch = { symbols: string[]; days: number; granularity: string; series: Record<string, Series> };

const COLORS = ['#10b981', '#38bdf8', '#fbbf24', '#a78bfa', '#f472b6', '#fb923c',
                '#34d399', '#60a5fa', '#facc15', '#c084fc', '#f87171', '#4ade80'];
const W = 760, H = 300;
const PAD = { l: 34, r: 60, t: 14, b: 24 };
const PLOT_W = W - PAD.l - PAD.r;
const PLOT_H = H - PAD.t - PAD.b;
const xPct = (x: number) => (x / W) * 100;
const yPct = (y: number) => (y / H) * 100;
const fmtDate = (tSec: number) => { const d = new Date(tSec * 1000); return `${d.getMonth() + 1}/${d.getDate()}`; };
const fmtVol = (n: number | null) =>
  n == null ? '—' : n >= 1e9 ? `${(n / 1e9).toFixed(1)}B` : n >= 1e6 ? `${(n / 1e6).toFixed(1)}M`
  : n >= 1e3 ? `${(n / 1e3).toFixed(0)}K` : String(n);

export function SepaRankCompare() {
  const [universe, setUniverse] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [mode, setMode] = useState<'overlay' | 'multiples'>('overlay');
  const [windowDays, setWindowDays] = useState(30);
  const [data, setData] = useState<Batch | null>(null);
  const [focus, setFocus] = useState<string | null>(null);   // hovered series (end-label)
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);  // hovered date column
  const [pinIdx, setPinIdx] = useState<number | null>(null);      // date-picker pin
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/sepa/leaderboard?n=14`)
      .then((r) => r.json())
      .then((d) => {
        if (!alive) return;
        const syms: string[] = (d.leaders || []).map((l: { symbol: string }) => l.symbol);
        setUniverse(syms);
        setSelected((cur) => cur.length ? cur : syms.slice(0, 5));
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [reloadKey]);

  useEffect(() => {
    if (!selected.length) { setData(null); return; }
    let alive = true;
    fetch(`${API}/sepa/rank-history-batch?symbols=${selected.join(',')}&days=${windowDays}&granularity=daily`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error())))
      .then((d: Batch) => { if (alive) { setData(d); setPinIdx(null); setHoverIdx(null); } })
      .catch(() => {});
    return () => { alive = false; };
  }, [selected, windowDays, reloadKey]);

  const colorOf = (sym: string) => COLORS[Math.max(0, selected.indexOf(sym)) % COLORS.length];
  const toggle = (sym: string) =>
    setSelected((s) => s.includes(sym) ? s.filter((x) => x !== sym) : s.length >= 8 ? s : [...s, sym]);

  // All selected series share the SAME run dates (one point per scan day), so
  // index i lines up across symbols — this is the canonical date axis.
  const dates: Pt[] = useMemo(() => {
    if (!data) return [];
    for (const sym of selected) { const s = data.series[sym]; if (s?.points?.length) return s.points; }
    return [];
  }, [data, selected]);
  const activeIdx = pinIdx != null ? pinIdx : hoverIdx;

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
  const cur = activeIdx != null && dates[activeIdx] ? dates[activeIdx] : null;
  const readout = cur
    ? selected.map((sym) => ({ sym, p: data?.series[sym]?.points[activeIdx!] }))
        .filter((r) => r.p)
        .sort((a, b) => (a.p!.rank ?? 1e9) - (b.p!.rank ?? 1e9))
    : [];

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
          <span className="rank-cmp__sep" />
          <select className="rank-cmp__date" value={pinIdx ?? ''} title="Pin a date"
                  onChange={(e) => setPinIdx(e.target.value === '' ? null : Number(e.target.value))}>
            <option value="">Jump to date…</option>
            {dates.map((p, i) => p.date ? <option key={i} value={i}>{p.date}</option> : null)}
          </select>
          <button className="rank-cmp__reload" title="Reload" onClick={() => setReloadKey((k) => k + 1)}>⟳</button>
        </div>
      </div>
      <p className="rank-cmp__sub">Pick names to compare how their rank moved (hover for a date readout · pick a name to focus). Up to 8.</p>

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
              const dim = focus && focus !== sym;
              return <path key={sym} d={path(s.points, geom.yRank, geom.x)} fill="none"
                           stroke={dim ? '#475569' : colorOf(sym)} strokeWidth={focus === sym ? 2.6 : 1.8}
                           opacity={dim ? 0.45 : 1} vectorEffect="non-scaling-stroke"
                           style={{ transition: 'opacity .12s' }} />;
            })}
            {/* date cursor + dots at the active column */}
            {cur && (
              <>
                <line x1={geom.x(cur.t)} x2={geom.x(cur.t)} y1={PAD.t} y2={PAD.t + PLOT_H} className="rank-cmp__cursor" />
                {readout.map(({ sym, p }) => p!.rank != null ? (
                  <circle key={sym} cx={geom.x(cur.t)} cy={geom.yRank(p!.rank!)} r={2.8} fill={colorOf(sym)} />
                ) : null)}
              </>
            )}
            {/* hit area — snap to nearest date column */}
            <rect x={PAD.l} y={PAD.t} width={PLOT_W} height={PLOT_H} fill="transparent"
                  onMouseLeave={() => setHoverIdx(null)}
                  onMouseMove={(e) => {
                    if (!dates.length) return;
                    const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
                    const targetT = geom.tMin + ((e.clientX - r.left) / r.width) * geom.span;
                    let bi = 0, bd = Infinity;
                    dates.forEach((p, i) => { const dd = Math.abs(p.t - targetT); if (dd < bd) { bd = dd; bi = i; } });
                    setHoverIdx(bi);
                  }} />
          </svg>

          {rankTicks.map((r) => <span key={r} className="rank-cmp__ylabel mono" style={{ top: `${yPct(geom.yRank(r))}%` }}>#{r}</span>)}
          {geom.ticks.map((t, i) => (
            <span key={i} className="rank-cmp__xlabel mono"
                  style={{ left: `${xPct(geom.x(t))}%`, top: `${yPct(PAD.t + PLOT_H + 9)}%`,
                           transform: i === 0 ? 'none' : i === 5 ? 'translateX(-100%)' : 'translateX(-50%)' }}>{fmtDate(t)}</span>
          ))}
          {selected.map((sym) => {
            const s = data.series[sym]; if (!s) return null;
            const last = [...s.points].reverse().find((p) => p.rank != null); if (!last) return null;
            const dim = focus && focus !== sym;
            return (
              <span key={sym} className="rank-cmp__endlabel mono"
                    style={{ top: `${yPct(geom.yRank(last.rank!))}%`, left: `${xPct(PAD.l + PLOT_W) + 0.6}%`,
                             color: dim ? '#64748b' : colorOf(sym), fontWeight: focus === sym ? 700 : 500 }}
                    onMouseEnter={() => setFocus(sym)} onMouseLeave={() => setFocus(null)}>
                {sym} #{last.rank}
              </span>
            );
          })}

          {/* per-date readout tooltip */}
          {cur && (
            <div className="rank-cmp__tip"
                 style={{ left: `${xPct(geom.x(cur.t))}%`,
                          transform: xPct(geom.x(cur.t)) > 58 ? 'translateX(-100%) translateX(-10px)' : 'translateX(10px)' }}>
              <div className="rank-cmp__tip-date mono">{cur.date}{pinIdx != null ? ' · pinned' : ''}</div>
              {readout.map(({ sym, p }) => (
                <div key={sym} className="rank-cmp__tip-row mono">
                  <span className="rank-cmp__tip-dot" style={{ background: colorOf(sym) }} />
                  <span className="rank-cmp__tip-sym" style={{ color: colorOf(sym) }}>{sym}</span>
                  <span className="rank-cmp__tip-rank">{p!.rank != null ? `#${p!.rank}` : 'out'}</span>
                  <span className="rank-cmp__tip-vol">{fmtVol(p!.volume)}</span>
                </div>
              ))}
            </div>
          )}
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
