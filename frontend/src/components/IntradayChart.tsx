import { useMemo, useRef, useEffect, useState, useCallback } from 'react';
import type { DayBars, DaySignal } from '../hooks/useDayTrading';
import {
  VOLUME_SMA_COLOR, VOLUME_SMA_LEN, volumeColor, volumePaneLayout, volumeSma, volumeSmaTitle,
  volumeSmaWindow,
} from '../lib/volumePane';

type Props = {
  data: DayBars;
  signals?: DaySignal[];
  height?: number;
};

type HoverInfo = {
  idx: number;
  x: number;
  y: number;
} | null;

type ZoomRange = { start: number; end: number } | null;

/**
 * IntradayChart — interactive SVG candlestick + VWAP + ORB overlay.
 *
 * Interactions:
 *  - Hover: crosshair + tooltip with OHLCV + VWAP + ATR + session
 *  - Click+drag: select a range to zoom into
 *  - Double-click: reset zoom
 *  - Mouse wheel: zoom in/out around cursor (10% per tick)
 *  - 'Reset' button when zoomed
 */
export function IntradayChart({ data, signals = [], height = 420 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [width, setWidth] = useState(900);
  const [hover, setHover] = useState<HoverInfo>(null);
  const [zoom, setZoom] = useState<ZoomRange>(null);
  const [dragStart, setDragStart] = useState<number | null>(null);
  const [dragEnd, setDragEnd] = useState<number | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 900;
      setWidth(Math.max(400, Math.floor(w)));
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Reset zoom if the symbol changes (data prop swap)
  useEffect(() => { setZoom(null); }, [data.symbol]);

  // Slice bars based on zoom
  const visibleBars = useMemo(() => {
    if (!zoom) return data.bars;
    return data.bars.slice(zoom.start, zoom.end + 1);
  }, [data.bars, zoom]);

  /* 📊 The 50-bar volume average runs over the FULL frame, then is sliced
   * with the zoom — a zoomed view does not restart the warm-up. */
  const volSma = useMemo(() => {
    const vols = data.bars.map((b) => volOf(b.v));
    return volumeSma(vols, volumeSmaWindow(data.bars.length));
  }, [data.bars]);

  const { plot } = useMemo(
    () => computePlot({ ...data, bars: visibleBars }, signals, width, height, zoom?.start ?? 0,
                      volSma, data.bars.length),
    [data, visibleBars, signals, width, height, zoom, volSma],
  );

  const xToIdx = useCallback((px: number): number => {
    if (!plot || visibleBars.length === 0) return -1;
    const ratio = (px - plot.padL) / plot.plotW;
    const idx = Math.round(ratio * (visibleBars.length - 1));
    return Math.max(0, Math.min(visibleBars.length - 1, idx));
  }, [plot, visibleBars.length]);

  const onMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!plot || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const idx = xToIdx(x);
    if (idx < 0) return setHover(null);
    setHover({ idx, x, y });
    if (dragStart != null) setDragEnd(idx);
  };
  const onMouseLeave = () => { setHover(null); setDragStart(null); setDragEnd(null); };
  const onMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!plot || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    setDragStart(xToIdx(x));
    setDragEnd(xToIdx(x));
  };
  const onMouseUp = () => {
    if (dragStart == null || dragEnd == null) return;
    const lo = Math.min(dragStart, dragEnd);
    const hi = Math.max(dragStart, dragEnd);
    if (hi - lo >= 5) {
      const offset = zoom?.start ?? 0;
      setZoom({ start: offset + lo, end: offset + hi });
    }
    setDragStart(null);
    setDragEnd(null);
  };
  const onDoubleClick = () => setZoom(null);
  const onWheel = (e: React.WheelEvent<SVGSVGElement>) => {
    if (!plot || visibleBars.length < 10) return;
    e.preventDefault();
    const rect = svgRef.current!.getBoundingClientRect();
    const cursorIdx = xToIdx(e.clientX - rect.left);
    const offset = zoom?.start ?? 0;
    const focus = offset + cursorIdx;
    const currentLen = visibleBars.length;
    const newLen = e.deltaY > 0
      ? Math.min(data.bars.length, Math.round(currentLen * 1.2))
      : Math.max(20, Math.round(currentLen / 1.2));
    if (newLen === currentLen) return;
    const half = Math.round(newLen / 2);
    let start = Math.max(0, focus - half);
    let end = Math.min(data.bars.length - 1, start + newLen - 1);
    start = Math.max(0, end - newLen + 1);
    if (newLen >= data.bars.length) setZoom(null);
    else setZoom({ start, end });
  };

  if (!plot || plot.bars.length === 0) {
    return <div className="day-chart day-chart--empty" ref={containerRef}>No bars available for {data.symbol}.</div>;
  }

  const hoveredBar = hover != null ? visibleBars[hover.idx] : null;
  // A pointer down in the volume pane is not on a price — no price pill there.
  const overPrice = hover != null && hover.y <= plot.padT + plot.plotH;
  const vol = plot.vol;
  // Shading, the drag overlay and the vertical crosshair run down through the
  // volume pane, so a column reads in its session.
  const fullBot = vol ? vol.bot : plot.padT + plot.plotH;
  const hoveredSignal = hover != null
    ? signals.find((s) => visibleBars[hover.idx]?.ts === s.entry_ts)
    : undefined;

  // Drag overlay rect
  let dragRect: { x: number; w: number } | null = null;
  if (dragStart != null && dragEnd != null && plot && visibleBars.length > 1) {
    const lo = Math.min(dragStart, dragEnd);
    const hi = Math.max(dragStart, dragEnd);
    if (hi - lo >= 1) {
      const x1 = plot.padL + (lo / (visibleBars.length - 1)) * plot.plotW;
      const x2 = plot.padL + (hi / (visibleBars.length - 1)) * plot.plotW;
      dragRect = { x: x1, w: x2 - x1 };
    }
  }

  return (
    <div className="day-chart" ref={containerRef}>
      {zoom && (
        <button type="button" className="day-chart__reset-btn" onClick={() => setZoom(null)}>
          ↺ Reset zoom
        </button>
      )}
      <svg
        ref={svgRef}
        width={width} height={height}
        className="day-chart__svg"
        role="img"
        aria-label={`${data.symbol} 1m chart, interactive`}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
        onMouseDown={onMouseDown}
        onMouseUp={onMouseUp}
        onDoubleClick={onDoubleClick}
        onWheel={onWheel}
        style={{ cursor: dragStart != null ? 'crosshair' : 'crosshair' }}
      >
        {/* y-axis grid + labels */}
        {plot.yTicks.map((t, i) => (
          <g key={i}>
            <line x1={plot.padL} x2={width - plot.padR} y1={t.y} y2={t.y} className="day-chart__grid" />
            <text x={plot.padL - 6} y={t.y + 3} textAnchor="end" className="day-chart__yLabel mono">{t.label}</text>
          </g>
        ))}
        {plot.xTicks.map((t, i) => (
          <text key={i} x={t.x} y={height - 6} textAnchor="middle" className="day-chart__xLabel mono">{t.label}</text>
        ))}
        {/* RTH session shading */}
        {plot.rthBands.map((b, i) => (
          <rect key={i} x={b.x1} y={plot.padT} width={b.x2 - b.x1} height={fullBot - plot.padT} className="day-chart__rth-band" />
        ))}
        {/* 📊 volume pane (2026-10-13) — the bottom ~22%: one column per bar,
            green when the close is at or above the open (the candle above it),
            red otherwise, plus the thin grey 50-bar simple average. Bars with
            no `v` draw no pane. Display only. */}
        {vol && (
          <g className="day-chart__vol-pane">
            <title>{vol.paneTitle}</title>
            <line x1={plot.padL} x2={width - plot.padR} y1={vol.top - 2} y2={vol.top - 2}
                  stroke="var(--rule, #2a2f3a)" strokeWidth={0.6} opacity={0.55} />
            {vol.cols.map((c) => (
              <rect key={`vol-${c.i}`} className="day-chart__vol" data-vol={c.v}
                    x={c.x} y={c.y} width={c.w} height={c.h} fill={c.fill}
                    opacity={hover != null && hover.idx !== c.i ? 0.82 : 1} />
            ))}
            {vol.segs.map((d, si) => (
              <path key={`vsma-${si}`} className="day-chart__vol-sma" d={d} fill="none"
                    stroke={VOLUME_SMA_COLOR} strokeWidth={1}>
                <title>{vol.title}</title>
              </path>
            ))}
            {vol.flatY != null && (
              <path className="day-chart__vol-sma day-chart__vol-sma-flat"
                    d={`M${plot.padL},${vol.flatY} L${width - plot.padR},${vol.flatY}`} fill="none"
                    stroke={VOLUME_SMA_COLOR} strokeWidth={1} strokeDasharray="3,3">
                <title>{vol.title}</title>
              </path>
            )}
            <text x={plot.padL - 6} y={vol.top + 7} textAnchor="end"
                  className="day-chart__vol-max day-chart__yLabel mono">{fmtVol(vol.max)}</text>
          </g>
        )}
        {/* ORB */}
        {plot.orb && (
          <>
            <line x1={plot.padL} x2={width - plot.padR} y1={plot.orb.yHigh} y2={plot.orb.yHigh} className="day-chart__orb-line day-chart__orb-line--hi" />
            <line x1={plot.padL} x2={width - plot.padR} y1={plot.orb.yLow}  y2={plot.orb.yLow}  className="day-chart__orb-line day-chart__orb-line--lo" />
            <text x={width - plot.padR - 4} y={plot.orb.yHigh - 3} textAnchor="end" className="day-chart__orb-label day-chart__orb-label--hi mono">ORB H {data.indicators.opening_range?.high.toFixed(2)}</text>
            <text x={width - plot.padR - 4} y={plot.orb.yLow + 11} textAnchor="end" className="day-chart__orb-label day-chart__orb-label--lo mono">ORB L {data.indicators.opening_range?.low.toFixed(2)}</text>
          </>
        )}
        {/* Premarket */}
        {plot.pre && (
          <>
            <line x1={plot.padL} x2={width - plot.padR} y1={plot.pre.yHigh} y2={plot.pre.yHigh} className="day-chart__pre-line" />
            <line x1={plot.padL} x2={width - plot.padR} y1={plot.pre.yLow}  y2={plot.pre.yLow}  className="day-chart__pre-line" />
          </>
        )}
        {/* VWAP */}
        {plot.vwapPath && <path d={plot.vwapPath} className="day-chart__vwap" fill="none" />}
        {/* Candles */}
        {plot.bars.map((b, i) => (
          <g key={i}>
            <line x1={b.cx} x2={b.cx} y1={b.yH} y2={b.yL} className={`day-chart__wick day-chart__wick--${b.up ? 'up' : 'down'}`} />
            <rect x={b.cx - plot.candleW / 2} y={b.yTop} width={plot.candleW} height={Math.max(1, b.yBottom - b.yTop)} className={`day-chart__body day-chart__body--${b.up ? 'up' : 'down'}`} />
          </g>
        ))}
        {/* Signal markers */}
        {plot.signals.map((m, i) => (
          <g key={`s-${i}`}>
            <circle cx={m.cx} cy={m.cy} r={6} className={`day-chart__sig day-chart__sig--${m.side}`} />
            <text x={m.cx + 9} y={m.cy + 3} className={`day-chart__sig-label day-chart__sig-label--${m.side} mono`}>
              {m.side === 'long' ? '↑ long' : '↓ short'} {m.entry.toFixed(2)}
            </text>
            <line x1={m.cx} x2={width - plot.padR} y1={m.yStop}   y2={m.yStop}   className="day-chart__sig-stop" />
            <line x1={m.cx} x2={width - plot.padR} y1={m.yTarget} y2={m.yTarget} className="day-chart__sig-target" />
            <text x={width - plot.padR - 4} y={m.yStop - 2}   textAnchor="end" className="day-chart__sig-stop-label mono">stop {m.stop.toFixed(2)}</text>
            <text x={width - plot.padR - 4} y={m.yTarget - 2} textAnchor="end" className="day-chart__sig-target-label mono">target {m.target.toFixed(2)}</text>
          </g>
        ))}

        {/* Drag-to-zoom overlay */}
        {dragRect && (
          <rect x={dragRect.x} y={plot.padT} width={dragRect.w} height={fullBot - plot.padT} className="day-chart__drag" />
        )}

        {/* Crosshair */}
        {hover && (
          <>
            <line x1={plot.padL + (hover.idx / Math.max(1, visibleBars.length - 1)) * plot.plotW}
                  x2={plot.padL + (hover.idx / Math.max(1, visibleBars.length - 1)) * plot.plotW}
                  y1={plot.padT} y2={fullBot} className="day-chart__crosshair" />
            <line x1={plot.padL} x2={width - plot.padR} y1={hover.y} y2={hover.y} className="day-chart__crosshair" />
            {/* y-axis hover label — over the price pane only */}
            {overPrice && (
              <>
                <rect x={plot.padL - 50} y={hover.y - 9} width={50} height={18} className="day-chart__hover-pill" />
                <text x={plot.padL - 6} y={hover.y + 4} textAnchor="end" className="day-chart__hover-y mono">
                  {plot.priceAt(hover.y).toFixed(2)}
                </text>
              </>
            )}
          </>
        )}
      </svg>

      {/* Tooltip */}
      {hover && hoveredBar && (
        <div
          className="day-chart__tooltip"
          style={{
            left: hover.x > width - 220 ? hover.x - 220 : hover.x + 14,
            top: hover.y > height - 180 ? hover.y - 180 : hover.y + 10,
          }}
        >
          <div className="day-chart__tt-row mono day-chart__tt-row--head">
            {new Date(hoveredBar.ts + 'Z').toLocaleString(undefined, { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })}
            <span className={`day-chart__tt-session day-chart__tt-session--${hoveredBar.session}`}>{hoveredBar.session}</span>
          </div>
          <div className="day-chart__tt-grid mono">
            <span>O</span><span className={hoveredBar.c >= hoveredBar.o ? 'pos' : 'neg'}>${hoveredBar.o.toFixed(2)}</span>
            <span>H</span><span>${hoveredBar.h.toFixed(2)}</span>
            <span>L</span><span>${hoveredBar.l.toFixed(2)}</span>
            <span>C</span><span className={hoveredBar.c >= hoveredBar.o ? 'pos' : 'neg'}>${hoveredBar.c.toFixed(2)}</span>
            <span>Δ</span><span className={hoveredBar.c >= hoveredBar.o ? 'pos' : 'neg'}>
              {((hoveredBar.c / hoveredBar.o - 1) * 100).toFixed(2)}%
            </span>
            <span>V</span><span>{fmtVol(hoveredBar.v)}</span>
            {hoveredBar.vwap != null && <><span>VWAP</span><span>${hoveredBar.vwap.toFixed(2)}</span></>}
            {hoveredBar.atr14 != null && <><span>ATR<sub>14</sub></span><span>${hoveredBar.atr14.toFixed(2)}</span></>}
          </div>
          {hoveredSignal && (
            <div className="day-chart__tt-sig">
              <strong className={`day-chart__tt-sig-label day-chart__tt-sig-label--${hoveredSignal.side}`}>
                {hoveredSignal.side === 'long' ? '↑ ' : '↓ '}{hoveredSignal.strategy}
              </strong>
              <div className="mono">Stop ${hoveredSignal.stop.toFixed(2)} · Target ${hoveredSignal.target.toFixed(2)} · {hoveredSignal.r_multiple_potential}R</div>
            </div>
          )}
        </div>
      )}

      <div className="day-chart__legend">
        <span className="day-chart__legend-key day-chart__legend-key--vwap">VWAP</span>
        <span className="day-chart__legend-key day-chart__legend-key--orbH">ORB high</span>
        <span className="day-chart__legend-key day-chart__legend-key--orbL">ORB low</span>
        <span className="day-chart__legend-key day-chart__legend-key--pre">Premarket H/L</span>
        <span className="day-chart__legend-key day-chart__legend-key--rth">RTH session</span>
        <span className="day-chart__legend-help">Hover · drag-to-zoom · scroll · double-click reset</span>
      </div>
    </div>
  );
}

function fmtVol(v: number | null | undefined): string {
  if (typeof v !== 'number' || !Number.isFinite(v) || v < 0) return '—';
  if (v >= 1e6) return (v / 1e6).toFixed(2) + 'M';
  if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
  return v.toFixed(0);
}

// --- plot computation -------------------------------------------------------

/** A usable volume: a finite number >= 0, else null (never a fake zero). */
function volOf(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v : null;
}

type PlotBar = { cx: number; yH: number; yL: number; yTop: number; yBottom: number; up: boolean };
type VolCol = { i: number; v: number; x: number; w: number; y: number; h: number; fill: string };
type VolPane = {
  top: number; bot: number; max: number; cols: VolCol[]; segs: string[];
  flatY: number | null; title: string; paneTitle: string;
};
type PlotSignal = { cx: number; cy: number; yStop: number; yTarget: number; side: 'long'|'short'; entry: number; stop: number; target: number };

function computePlot(data: DayBars, signals: DaySignal[], width: number, height: number,
                            idxOffset: number, fullSma: ReadonlyArray<number | null> = [],
                            fullLen: number = data.bars.length) {
  const padL = 60, padR = 100, padT = 14, padB = 30;
  const plotW = width - padL - padR;
  const bars = data.bars;
  if (!bars.length) return { plot: null };
  /* 📊 The volume pane takes the bottom of the chart when any visible bar
   * carries a positive `v`; the price mapping runs on the shorter pane. With
   * no volume the price pane keeps the whole height, exactly as before. */
  const vols = bars.map((b) => volOf(b.v));
  const volMax = vols.reduce<number>((m, v) => (v != null && v > m ? v : m), 0);
  const pane = volumePaneLayout(height, padB, volMax > 0);
  const plotH = pane.priceH - padT - padB;

  let lo = Infinity, hi = -Infinity;
  for (const b of bars) { if (b.l < lo) lo = b.l; if (b.h > hi) hi = b.h; }
  if (data.indicators.opening_range) { lo = Math.min(lo, data.indicators.opening_range.low); hi = Math.max(hi, data.indicators.opening_range.high); }
  if (data.indicators.premarket) { lo = Math.min(lo, data.indicators.premarket.low); hi = Math.max(hi, data.indicators.premarket.high); }
  for (const s of signals) {
    const inWindow = bars.some((b) => b.ts === s.entry_ts);
    if (!inWindow) continue;
    lo = Math.min(lo, s.stop, s.target);
    hi = Math.max(hi, s.stop, s.target);
  }
  const range = (hi - lo) || 1;
  const padPx = range * 0.04;
  lo -= padPx; hi += padPx;

  const yOf = (p: number) => padT + (1 - (p - lo) / (hi - lo)) * plotH;
  const priceAt = (y: number) => lo + (1 - (y - padT) / plotH) * (hi - lo);
  const xOf = (i: number) => padL + (bars.length === 1 ? plotW / 2 : (i / (bars.length - 1)) * plotW);
  const candleW = Math.max(1, Math.min(8, plotW / bars.length * 0.7));

  const yTicks: { y: number; label: string }[] = [];
  const stepCount = 5;
  for (let i = 0; i <= stepCount; i++) {
    const v = lo + (hi - lo) * (i / stepCount);
    yTicks.push({ y: yOf(v), label: v.toFixed(2) });
  }

  const xTicks: { x: number; label: string }[] = [];
  for (let i = 0; i < 4; i++) {
    const idx = Math.min(bars.length - 1, Math.floor(i / 3 * (bars.length - 1)));
    const ts = new Date(bars[idx].ts + 'Z');
    const lbl = `${ts.getUTCMonth()+1}/${ts.getUTCDate()} ${String(ts.getUTCHours()).padStart(2,'0')}:${String(ts.getUTCMinutes()).padStart(2,'0')}`;
    xTicks.push({ x: xOf(idx), label: lbl });
  }

  const rthBands: { x1: number; x2: number }[] = [];
  let runStart = -1;
  for (let i = 0; i < bars.length; i++) {
    const isRth = bars[i].session === 'rth';
    if (isRth && runStart === -1) runStart = i;
    if ((!isRth || i === bars.length - 1) && runStart !== -1) {
      const end = isRth ? i : i - 1;
      rthBands.push({ x1: xOf(runStart), x2: xOf(end) });
      runStart = -1;
    }
  }

  let orb: { yHigh: number; yLow: number } | null = null;
  if (data.indicators.opening_range) orb = { yHigh: yOf(data.indicators.opening_range.high), yLow: yOf(data.indicators.opening_range.low) };
  let pre: { yHigh: number; yLow: number } | null = null;
  if (data.indicators.premarket) pre = { yHigh: yOf(data.indicators.premarket.high), yLow: yOf(data.indicators.premarket.low) };

  let vwapPath = ''; let started = false;
  bars.forEach((b, i) => {
    if (b.vwap == null) return;
    const x = xOf(i); const y = yOf(b.vwap);
    vwapPath += (started ? ' L' : 'M') + x.toFixed(1) + ',' + y.toFixed(1);
    started = true;
  });

  const plotBars: PlotBar[] = bars.map((b, i) => {
    const cx = xOf(i);
    const up = b.c >= b.o;
    const yTop = yOf(Math.max(b.o, b.c));
    const yBottom = yOf(Math.min(b.o, b.c));
    return { cx, yH: yOf(b.h), yL: yOf(b.l), yTop, yBottom, up };
  });

  const plotSignals: PlotSignal[] = [];
  for (const s of signals) {
    const idx = bars.findIndex((b) => b.ts === s.entry_ts || b.ts.startsWith(s.entry_ts.slice(0, 16)));
    if (idx === -1) continue;
    plotSignals.push({
      cx: xOf(idx), cy: yOf(s.entry_price),
      yStop: yOf(s.stop), yTarget: yOf(s.target),
      side: s.side, entry: s.entry_price, stop: s.stop, target: s.target,
    });
  }

  let vol: VolPane | null = null;
  if (volMax > 0) {
    const paneH = pane.volBot - pane.volTop;
    const yV = (v: number) => pane.volBot - (v / volMax) * paneH;
    const cols: VolCol[] = [];
    bars.forEach((b, i) => {
      const v = vols[i];
      const fill = volumeColor(b.o, b.c);
      if (v == null || v <= 0 || !fill) return;
      const y = yV(v);
      cols.push({ i, v, x: xOf(i) - candleW / 2, w: candleW, y, h: Math.max(pane.volBot - y, 0.6), fill });
    });
    const off = Math.max(0, Math.floor(idxOffset) || 0);
    const segs: string[] = [];
    let cur: string[] = [];
    bars.forEach((_, i) => {
      const a = fullSma[off + i];
      if (typeof a !== 'number' || !Number.isFinite(a)) {
        if (cur.length > 1) segs.push('M' + cur.join(' L'));
        cur = [];
        return;
      }
      cur.push(`${xOf(i).toFixed(1)},${yV(Math.min(a, volMax)).toFixed(1)}`);
    });
    if (cur.length > 1) segs.push('M' + cur.join(' L'));
    // Fewer bars than the window in the whole frame: the average exists at
    // ONE bar only, drawn flat and dashed with a title that says so. With a
    // full window a lone valid point draws nothing.
    const win = volumeSmaWindow(fullLen);
    const lone = fullSma.find((a) => typeof a === 'number' && Number.isFinite(a));
    const flatY = !segs.length && fullLen < VOLUME_SMA_LEN && typeof lone === 'number'
      ? yV(Math.min(lone, volMax)) : null;
    const title = volumeSmaTitle(win, fullLen);
    const paneTitle = segs.length || flatY != null
      ? `${title} · tallest bar ${fmtVol(volMax)}`
      : `volume · tallest bar ${fmtVol(volMax)} · average not drawn (a bar in the window has no volume)`;
    vol = { top: pane.volTop, bot: pane.volBot, max: volMax, cols, segs, flatY, title, paneTitle };
  }

  return {
    plot: { padL, padR, padT, plotH, plotW, bars: plotBars, signals: plotSignals, yTicks, xTicks, rthBands, orb, pre, vwapPath, candleW, priceAt, vol },
  };
}
