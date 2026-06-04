/* LiveCandlesChart — a native candlestick chart fed by the app's OWN data, so
   it's genuinely live instead of the ~15-min-delayed TradingView embed.

   Ajay 2026-06-04: "is the TradingView not live? I have a paid account." The
   embed can't use his subscription (anonymous cross-origin iframe), so this
   renders candles from price_cache (daily) / the intraday minute bars, and
   ticks the CURRENT candle in real time off the same SSE last-price the page
   header uses. Built on TradingView's free open-source Lightweight Charts. */
import { useEffect, useRef } from 'react';
import {
  createChart, ColorType, CrosshairMode,
  type IChartApi, type ISeriesApi, type CandlestickData, type UTCTimestamp,
} from 'lightweight-charts';
import { API } from '../lib/apiBase';
import { useLiveQuote } from '../hooks/useLiveQuote';

const UP = '#22c55e';
const DOWN = '#ef4444';

export type ChartInterval = 'D' | '1m';

type Candle = CandlestickData & { volume?: number };

async function fetchBars(symbol: string, interval: ChartInterval): Promise<Candle[]> {
  if (interval === 'D') {
    const r = await fetch(`${API}/sepa/price-bars/${encodeURIComponent(symbol)}?days=300`, { cache: 'no-store' });
    if (!r.ok) return [];
    const j = await r.json();
    return (j.bars ?? []).map((b: any) => ({
      time: b.time, open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume,
    }));
  }
  // Intraday 1-minute bars (today + prior session) from the day-trading feed.
  const r = await fetch(`${API}/day/bars/${encodeURIComponent(symbol)}?days=2`, { cache: 'no-store' });
  if (!r.ok) return [];
  const j = await r.json();
  return (j.bars ?? []).map((b: any) => ({
    time: (Date.parse(b.ts) / 1000) as UTCTimestamp,
    open: b.o, high: b.h, low: b.l, close: b.c, volume: b.v,
  }));
}

export function LiveCandlesChart({ symbol, interval }: { symbol: string; interval: ChartInterval }) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const lastBarRef = useRef<Candle | null>(null);

  const live = useLiveQuote(symbol);

  // Build the chart once; rebuild data when symbol/interval changes.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const chart = createChart(el, {
      width: el.clientWidth,
      height: el.clientHeight,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#94a3b8', fontSize: 11 },
      grid: { vertLines: { color: 'rgba(148,163,184,0.07)' }, horzLines: { color: 'rgba(148,163,184,0.07)' } },
      rightPriceScale: { borderColor: 'rgba(148,163,184,0.2)' },
      timeScale: { borderColor: 'rgba(148,163,184,0.2)', timeVisible: interval !== 'D', secondsVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
    });
    const candle = chart.addCandlestickSeries({
      upColor: UP, downColor: DOWN, borderVisible: false, wickUpColor: UP, wickDownColor: DOWN,
    });
    const vol = chart.addHistogramSeries({ priceScaleId: '', priceFormat: { type: 'volume' } });
    vol.priceScale().applyOptions({ scaleMargins: { top: 0.84, bottom: 0 } });

    chartRef.current = chart;
    candleRef.current = candle;
    volRef.current = vol;

    let alive = true;
    fetchBars(symbol, interval).then((bars) => {
      if (!alive || !bars.length) return;
      candle.setData(bars);
      vol.setData(bars.map((b) => ({
        time: b.time, value: b.volume ?? 0,
        color: b.close >= b.open ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)',
      })));
      lastBarRef.current = bars[bars.length - 1];
      chart.timeScale().fitContent();
    });

    const ro = new ResizeObserver(() => {
      if (el) chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
    });
    ro.observe(el);

    return () => {
      alive = false;
      ro.disconnect();
      chart.remove();
      chartRef.current = null; candleRef.current = null; volRef.current = null; lastBarRef.current = null;
    };
  }, [symbol, interval]);

  // Tick the CURRENT candle from the live SSE price — this is what makes it live.
  useEffect(() => {
    const price = live?.last_price;
    const candle = candleRef.current;
    const last = lastBarRef.current;
    if (price == null || !candle || !last) return;
    const updated: Candle = {
      time: last.time,
      open: last.open,
      high: Math.max(last.high, price),
      low: Math.min(last.low, price),
      close: price,
      volume: last.volume,
    };
    lastBarRef.current = updated;
    candle.update(updated);
  }, [live?.last_price]);

  return <div ref={wrapRef} className="livechart" />;
}
