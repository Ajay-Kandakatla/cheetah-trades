/* LiveCandlesChart — a native candlestick chart fed by the app's OWN data, so
   it's genuinely live instead of the ~15-min-delayed TradingView embed.

   Ajay 2026-06-04: "is the TradingView not live? I have a paid account." The
   embed can't use his subscription (anonymous cross-origin iframe), so this
   renders candles from price_cache (daily) / the intraday minute bars, and
   ticks the CURRENT candle in real time off the same SSE last-price the page
   header uses. Built on TradingView's free open-source Lightweight Charts. */
import { useEffect, useRef, useState } from 'react';
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
  // Throws on HTTP failure so the caller can show a retry state — a silent []
  // here meant a 10s API restart during a deploy left the chart permanently
  // blank (2026-06-12 "live chart broken" report).
  if (interval === 'D') {
    const r = await fetch(`${API}/sepa/price-bars/${encodeURIComponent(symbol)}?days=300`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`bars HTTP ${r.status}`);
    const j = await r.json();
    return (j.bars ?? []).map((b: any) => ({
      time: b.time, open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume,
    }));
  }
  // Intraday 1-minute bars (today + prior session) from the day-trading feed.
  const r = await fetch(`${API}/day/bars/${encodeURIComponent(symbol)}?days=2`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`bars HTTP ${r.status}`);
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
  // 'loading' -> 'ok' | 'empty' | 'error'; retryKey remounts the data effect.
  const [state, setState] = useState<'loading' | 'ok' | 'empty' | 'error'>('loading');
  const [retryKey, setRetryKey] = useState(0);

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
    let retryTimer: number | null = null;
    setState('loading');
    const load = (attempt: number) => {
      fetchBars(symbol, interval).then((bars) => {
        if (!alive) return;
        if (!bars.length) { setState('empty'); return; }
        candle.setData(bars);
        vol.setData(bars.map((b) => ({
          time: b.time, value: b.volume ?? 0,
          color: b.close >= b.open ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)',
        })));
        lastBarRef.current = bars[bars.length - 1];
        chart.timeScale().fitContent();
        setState('ok');
      }).catch(() => {
        if (!alive) return;
        // One automatic retry after 3s rides out an API-restart blip
        // (deploys recreate the api container for ~10s).
        if (attempt < 1) {
          retryTimer = window.setTimeout(() => { if (alive) load(attempt + 1); }, 3000);
        } else {
          setState('error');
        }
      });
    };
    load(0);

    const ro = new ResizeObserver(() => {
      if (el) chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
    });
    ro.observe(el);

    return () => {
      alive = false;
      if (retryTimer != null) window.clearTimeout(retryTimer);
      ro.disconnect();
      chart.remove();
      chartRef.current = null; candleRef.current = null; volRef.current = null; lastBarRef.current = null;
    };
  }, [symbol, interval, retryKey]);

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

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={wrapRef} className="livechart" />
      {state !== 'ok' && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                      alignItems: 'center', justifyContent: 'center', gap: 8, pointerEvents: 'none' }}>
          <span style={{ color: '#8a93a6', fontSize: '0.78rem' }}>
            {state === 'loading' && 'Loading candles…'}
            {state === 'empty' && (interval === '1m'
              ? `No intraday bars for ${symbol} yet — the 1m feed only covers tracked symbols. Try D.`
              : `No daily bars cached for ${symbol}.`)}
            {state === 'error' && 'Couldn’t load candles (server busy or restarting).'}
          </span>
          {state === 'error' && (
            <button onClick={() => setRetryKey((k) => k + 1)}
                    style={{ pointerEvents: 'auto', background: 'transparent', color: '#c9a227',
                             border: '1px solid #c9a22766', borderRadius: 6, padding: '3px 14px',
                             fontSize: '0.74rem', cursor: 'pointer' }}>
              Retry
            </button>
          )}
        </div>
      )}
    </div>
  );
}
