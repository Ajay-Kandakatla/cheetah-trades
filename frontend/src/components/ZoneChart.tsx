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
  DEMAND, NEUTRAL, SUPPLY, bandsFor, hasOhlc, hasVolume, hoverRow, planLines,
  toCandles, toVolumeBars, type Candle, type HoverRow, type SeriesBar,
} from '../lib/zoneChart';
import { ZoneBandsPrimitive } from './zoneBandsPrimitive';
import type { ZoneMapPayload } from '../lib/zonePlan';

const UP = '#22c55e';
const DOWN = '#ef4444';

export function ZoneChart({ data, height = 340 }:
  { data: ZoneMapPayload; height?: number }) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const bandsRef = useRef<ZoneBandsPrimitive | null>(null);
  const [hover, setHover] = useState<HoverRow | null>(null);

  const series = (data.series || []) as SeriesBar[];
  const candles = toCandles(series);
  const volumes = toVolumeBars(series);
  const ohlc = hasOhlc(series);
  const withVol = hasVolume(series);
  const bands = bandsFor(data);
  const lines = planLines(data);

  // Re-keyed on the payload's own identity so a refresh rebuilds cleanly rather
  // than mutating a chart mid-zoom.
  const key = `${data.symbol}:${candles.length}:${candles[candles.length - 1]?.time ?? ''}`;

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
      });
      s.setData(candles);
      price = s;
    } else {
      const s = chart.addLineSeries({ color: '#cbd5e1', lineWidth: 2 });
      s.setData(candles.map((c) => ({ time: c.time as Time, value: c.close })));
      price = s;
    }

    if (withVol) {
      const vol = chart.addHistogramSeries({ priceScaleId: '', priceFormat: { type: 'volume' } });
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
        axisLabelVisible: true,
        title: l.title,
      });
    }

    chart.timeScale().fitContent();
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
      if (el) chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
    });
    ro.observe(el);

    return () => {
      chart.unsubscribeCrosshairMove(onMove);
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      bandsRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, height]);

  if (candles.length < 2) {
    return <div className="sepa-tab-help" style={{ opacity: 0.7 }}>Not enough history to draw zones.</div>;
  }

  return (
    <div className="zonechart">
      <div ref={wrapRef} className="zonechart__canvas" style={{ height }} />
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
        <span><i style={{ background: NEUTRAL }} /> now</span>
        {!ohlc && <span style={{ opacity: 0.6 }}>· line only (older cached payload)</span>}
        {!withVol && <span style={{ opacity: 0.6 }}>· no volume in this payload</span>}
      </div>
    </div>
  );
}

export default ZoneChart;
