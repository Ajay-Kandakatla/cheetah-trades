/* TradingView Charting Library — datafeed adapter.

   Implements the library's Datafeed API against our own UDF endpoints
   (backend/tv_datafeed.py → /tv/udf/*), so the licensed chart is backed by the
   same daily OHLCV the SEPA scanner uses. Used by TradingViewAdvancedChart once
   the proprietary library files are installed under /public/charting_library/.

   The library calls these methods — we don't import its types (they ship inside
   the licensed bundle, absent until installed), so the callbacks are loosely
   typed on purpose. See docs/tradingview_charting_library.md. */
import { API } from './apiBase';

type Cb = (...args: any[]) => void;

const getJson = (path: string) =>
  fetch(`${API}${path}`, { credentials: 'include' }).then((r) => r.json());

function tvResolution(r: string): string {
  if (r === 'W' || r === '1W') return '1W';
  if (r === 'M' || r === '1M') return '1M';
  return '1D';
}

export function createPounceDatafeed() {
  return {
    onReady(cb: Cb) {
      getJson('/tv/udf/config').then((c) => setTimeout(() => cb(c), 0));
    },

    searchSymbols(userInput: string, _exchange: string, _symbolType: string, onResult: Cb) {
      getJson(`/tv/udf/search?query=${encodeURIComponent(userInput)}`)
        .then(onResult)
        .catch(() => onResult([]));
    },

    resolveSymbol(symbolName: string, onResolve: Cb, onError: Cb) {
      getJson(`/tv/udf/symbols?symbol=${encodeURIComponent(symbolName)}`)
        .then((s) => (s && s.name ? onResolve(s) : onError('symbol not found')))
        .catch(() => onError('resolve failed'));
    },

    getBars(symbolInfo: any, resolution: string, periodParams: any, onResult: Cb, onError: Cb) {
      const { from, to, countBack } = periodParams;
      const qs =
        `symbol=${encodeURIComponent(symbolInfo.name)}` +
        `&resolution=${tvResolution(resolution)}&from=${from}&to=${to}&countback=${countBack}`;
      getJson(`/tv/udf/history?${qs}`)
        .then((h) => {
          if (h.s !== 'ok') { onResult([], { noData: true }); return; }
          const bars = h.t.map((t: number, i: number) => ({
            time: t * 1000,                       // library wants ms
            open: h.o[i], high: h.h[i], low: h.l[i], close: h.c[i], volume: h.v[i],
          }));
          onResult(bars, { noData: bars.length === 0 });
        })
        .catch((e) => onError(String(e)));
    },

    // Live last-candle updates land in a later pass (reuse the SSE last price the
    // native chart already consumes). EOD data is complete without it.
    subscribeBars() { /* no-op for now */ },
    unsubscribeBars() { /* no-op for now */ },
  };
}
