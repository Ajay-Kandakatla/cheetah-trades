/* The zone chart, on lightweight-charts.
 *
 * Ajay 2026-08-16: *"is there any way we can use trading view charts? Or
 * configure them with formula.. I wanna be able to hover on the pricing at for
 * some points but too vague right now"*, then *"can you also add volume
 * please"*.
 *
 * He also assumed a trade-off — *"may be static makes sense I know it would
 * break the zones"*. It does not: this is the engine TradingView open-sourced,
 * and a band drawn through the series' own price scale stays glued to its
 * prices while the chart zooms and pans. The bands survive BECAUSE the chart is
 * live, not despite it.
 *
 * What it draws:
 *   candles + a volume histogram   ← the two things the SVG could not
 *   supply / demand bands          ← zoneBandsPrimitive.ts
 *   BUY band edges, STOP, TARGET, NOW as labelled price lines
 *   a hover readout: date, O/H/L/C, volume, % change
 *
 * Every number comes from lib/zoneChart.ts, which is pure and tested. This file
 * is wiring: lifecycle, refs and teardown, following LiveCandlesChart.tsx.
 *
 * Configured price-structure read — NOT a book method, NOT advice.
 */
import { useEffect, useRef, useState } from 'react';
import {
  ColorType, CrosshairMode, LineStyle, createChart,
  type IChartApi, type ISeriesApi, type MouseEventParams, type Time,
} from 'lightweight-charts';
import {
  DEMAND, NEUTRAL, SUPPLY, TARGET_C, bandsFor, gutterBars, hasOhlc, hasVolume,
  hoverRow, planGutterPx, planLines, toCandles, toVolumeBars,
  type Candle, type HoverRow, type SeriesBar,
} from '../lib/zoneChart';
import { ZoneBandsPrimitive } from './zoneBandsPrimitive';
import { PlanLabelsPrimitive } from './planLabelsPrimitive';
import type { ZoneMapPayload } from '../lib/zonePlan';

const UP = '#22c55e';
const DOWN = '#ef4444';

export function ZoneChart({ data, height = 340 }:
  { data: ZoneMapPayload; height?: number }) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const bandsRef = useRef<ZoneBandsPrimitive | null>(null);
  const labelsRef = useRef<PlanLabelsPrimitive | null>(null);
  const [hover, setHover] = useState<HoverRow | null>(null);
  /* Ajay 2026-08-17: "Can you make these charts to be full screened or
   * something, The zones are hard to figure out properly". A 340px pane over a
   * year of bars puts several bands within a few pixels of each other, so the
   * fix is vertical room, not a redraw. */
  const [full, setFull] = useState(false);

  const series = (data.series || []) as SeriesBar[];
  const candles = toCandles(series);
  const volumes = toVolumeBars(series);
  const ohlc = hasOhlc(series);
  const withVol = hasVolume(series);
  const bands = bandsFor(data);
  const lines = planLines(data);

  // Re-keyed on the payload's own identity so a refresh rebuilds cleanly rather
  // than mutating a chart mid-zoom.
  //`full` is part of the key: the overlay is a different DOM box, so the chart
  // is rebuilt into it rather than resized across a remount it never saw.
  const key = `${data.symbol}:${candles.length}:${candles[candles.length - 1]?.time ?? ''}:${full ? 'F' : 'n'}`;

  // Escape closes, and the page behind is scroll-locked so a stray wheel does
  // not move the article under the overlay while the chart eats the gesture.
  useEffect(() => {
    if (!full) return undefined;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setFull(false); };
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [full]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el || candles.length < 2) return;

    const chart = createChart(el, {
      width: el.clientWidth,
      height: el.clientHeight,
      layout: { background: { type: ColorType.Solid, color: 'transparent' },
                textColor: '#94a3b8', fontSize: 11 },
      grid: { vertLines: { color: 'rgba(148,163,184,0.07)' },
              horzLines: { color: 'rgba(148,163,184,0.07)' } },
      rightPriceScale: { borderColor: 'rgba(148,163,184,0.2)', scaleMargins: { top: 0.06, bottom: withVol ? 0.20 : 0.06 } },
      timeScale: { borderColor: 'rgba(148,163,184,0.2)', timeVisible: false, secondsVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
    });

    // A payload cached before 2026-08-16 has closes only. Drawing those as
    // candles would render 130 identical dojis, which looks like a broken
    // chart rather than an old one — so fall back to the line it can support.
    let price: ISeriesApi<'Candlestick', Time> | ISeriesApi<'Line', Time>;
    if (ohlc) {
      const s = chart.addCandlestickSeries({
        upColor: UP, downColor: DOWN, borderVisible: false,
        wickUpColor: UP, wickDownColor: DOWN,
        // The series draws its OWN last-price rule AND its own axis chip by
        // default, both duplicating our NOW line exactly — two rules at one
        // price and two chips reading 64.40, verified in the browser. Ours is
        // the one that says which it is. Two flags, because `priceLineVisible`
        // only removes the rule; the chip is `lastValueVisible`.
        priceLineVisible: false, lastValueVisible: false,
      });
      s.setData(candles);
      price = s;
    } else {
      const s = chart.addLineSeries({ color: '#cbd5e1', lineWidth: 2,
                                      priceLineVisible: false,
                                      lastValueVisible: false });
      s.setData(candles.map((c) => ({ time: c.time as Time, value: c.close })));
      price = s;
    }

    if (withVol) {
      const vol = chart.addHistogramSeries({
        priceScaleId: '', priceFormat: { type: 'volume' },
        // Volume's own last-value chip and its dotted rule across the whole
        // pane are pure noise on a price chart: the chip lands in the same
        // stack as the plan's prices reading "9.78M", and the line crosses the
        // bands. The HUD already reports volume for the hovered bar.
        priceLineVisible: false, lastValueVisible: false,
      });
      vol.priceScale().applyOptions({ scaleMargins: { top: 0.84, bottom: 0 } });
      vol.setData(volumes);
    }

    // Bands attach to the PRICE series, so they follow its scale exactly.
    const prim = new ZoneBandsPrimitive(bands);
    price.attachPrimitive(prim);
    bandsRef.current = prim;

    for (const l of lines) {
      price.createPriceLine({
        price: l.price,
        color: l.color,
        lineWidth: l.bold ? 2 : 1,
        lineStyle: l.dashed ? LineStyle.Dashed : LineStyle.Solid,
        // LOAD-BEARING once the pane title is gone: the axis chip becomes the
        // only place the library still prints this price.
        axisLabelVisible: true,
        // The clumsy box. v4 hard-codes its placement, and `showPaneLabel =
        // options.title !== ''` in the library is exactly this switch — an
        // empty title removes the plate and nothing else. PlanLabelsPrimitive
        // redraws it, de-clumped, in the gutter reserved below.
        title: '',
      });
    }

    // Plates on top of the candles, and a blank right margin for them to sit
    // in. `fitContent()` puts the newest candle flush against the axis, which
    // is why every plate landed on the tape; `rightOffset` is added by
    // fitContent itself, so the two compose rather than fight.
    const labels = new PlanLabelsPrimitive(lines);
    price.attachPrimitive(labels);
    labelsRef.current = labels;

    const applyGutter = () => {
      const w = el.clientWidth || 0;
      const bars = gutterBars(candles.length, w, planGutterPx(lines, w));
      chart.applyOptions({ timeScale: { rightOffset: bars } });
      chart.timeScale().fitContent();
    };
    applyGutter();
    chartRef.current = chart;

    // The hover readout. `param.time` is absent when the pointer leaves the
    // pane, which is the signal to clear rather than freeze the last bar.
    const byTime = new Map<string, Candle>(candles.map((c) => [c.time, c]));
    const volByTime = new Map<string, number>(volumes.map((v) => [v.time, v.value]));
    const idxByTime = new Map<string, number>(candles.map((c, i) => [c.time, i]));
    const onMove = (param: MouseEventParams<Time>) => {
      const t = param.time as string | undefined;
      if (!t || !byTime.has(t)) { setHover(null); return; }
      const i = idxByTime.get(t) ?? 0;
      setHover(hoverRow(byTime.get(t), volByTime.get(t) ?? null,
                        i > 0 ? candles[i - 1].close : null));
    };
    chart.subscribeCrosshairMove(onMove);

    const ro = new ResizeObserver(() => {
      if (!el) return;
      chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
      // The gutter is a fraction of the width, so it has to be recomputed —
      // a margin sized for 900px leaves a plate hanging off a 400px pane.
      applyGutter();
    });
    ro.observe(el);

    return () => {
      chart.unsubscribeCrosshairMove(onMove);
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      bandsRef.current = null;
      labelsRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, height, full]);

  if (candles.length < 2) {
    return <div className="sepa-tab-help" style={{ opacity: 0.7 }}>Not enough history to draw zones.</div>;
  }

  const body = (
    <div className={`zonechart${full ? ' zonechart--full' : ''}`}>
      <div className="zonechart__bar">
        <span className="zonechart__title mono">
          {data.symbol}{data.name ? ` · ${data.name}` : ''}
        </span>
        <button type="button" className="zonechart__expand"
                onClick={() => setFull((v) => !v)}
                aria-label={full ? 'Exit full screen' : 'Expand chart to full screen'}
                title={full ? 'Exit full screen (Esc)' : 'Expand — more room between the bands'}>
          {full ? '✕ Close' : '⤢ Expand'}
        </button>
      </div>
      <div ref={wrapRef} className="zonechart__canvas"
           style={{ height: full ? undefined : height }} />
      <div className="zonechart__hud mono" aria-live="off">
        {hover ? (
          <>
            <span className="zonechart__hud-date">{hover.date}</span>
            <span>O {hover.open}</span>
            <span>H {hover.high}</span>
            <span>L {hover.low}</span>
            <span style={{ color: hover.up ? UP : DOWN }}>C {hover.close}</span>
            {hover.changePct && (
              <span style={{ color: hover.up ? UP : DOWN }}>{hover.changePct}</span>
            )}
            <span style={{ opacity: 0.75 }}>Vol {hover.volume}</span>
          </>
        ) : (
          <span style={{ opacity: 0.55 }}>Hover the chart for that day’s open, high, low, close and volume.</span>
        )}
      </div>
      <div className="zonechart__legend">
        <span><i style={{ background: SUPPLY }} /> supply</span>
        <span><i style={{ background: DEMAND }} /> demand</span>
        <span><i style={{ background: DEMAND, outline: `1px solid ${DEMAND}` }} /> buy band</span>
        <span><i style={{ background: TARGET_C }} /> target</span>
        <span><i style={{ background: NEUTRAL }} /> now</span>
        {!ohlc && <span style={{ opacity: 0.6 }}>· line only (older cached payload)</span>}
        {!withVol && <span style={{ opacity: 0.6 }}>· no volume in this payload</span>}
        {full && <span style={{ opacity: 0.6 }}>· Esc to close</span>}
      </div>
    </div>
  );

  // Rendered in place normally; as a fixed overlay when expanded. Deliberately
  // NOT the browser Fullscreen API: that hides the HUD's own styling context on
  // some platforms and cannot be entered without a user gesture chain, and an
  // overlay keeps the hover readout and legend where they already are.
  if (!full) return body;
  return (
    <div className="zonechart__backdrop" role="dialog" aria-modal="true"
         aria-label={`${data.symbol} supply and demand zones, full screen`}
         onClick={(e) => { if (e.target === e.currentTarget) setFull(false); }}>
      {body}
    </div>
  );
}

export default ZoneChart;
