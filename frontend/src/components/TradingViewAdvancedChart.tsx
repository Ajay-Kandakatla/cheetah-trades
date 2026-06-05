/* TradingView Charting Library — editable chart that CAN carry custom studies.

   Ajay 2026-06-04 (for Ravi): the only way to bake custom CANSLIM indicators into
   a TradingView-grade chart in-app. Loads the licensed library from
   /public/charting_library/ (installed after the TradingView license is granted)
   and renders it against our own UDF datafeed (lib/tvDatafeed.ts → /tv/udf/*).

   Until the proprietary files are present it shows a tidy placeholder instead of
   a broken chart. The custom CANSLIM studies are wired in a follow-up pass via
   `custom_indicators_getter`. See docs/tradingview_charting_library.md. */
import { useEffect, useRef, useState } from 'react';
import { createPounceDatafeed } from '../lib/tvDatafeed';

const LIB_SRC = '/charting_library/charting_library.js';

function tvGlobal(): any {
  return (window as any).TradingView;
}

let libLoading: Promise<boolean> | null = null;
function loadLibrary(): Promise<boolean> {
  if (tvGlobal()?.widget) return Promise.resolve(true);
  if (libLoading) return libLoading;
  libLoading = new Promise<boolean>((resolve) => {
    const s = document.createElement('script');
    s.src = LIB_SRC;
    s.async = true;
    s.onload = () => resolve(!!tvGlobal()?.widget);
    s.onerror = () => resolve(false);
    document.head.appendChild(s);
  });
  return libLoading;
}

export function TradingViewAdvancedChart({
  symbol,
  tvSymbol,
}: {
  symbol: string;
  tvSymbol?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'missing'>('loading');

  useEffect(() => {
    let widget: any;
    let alive = true;
    loadLibrary().then((ok) => {
      if (!alive) return;
      if (!ok || !ref.current) {
        setStatus('missing');
        return;
      }
      try {
        widget = new (tvGlobal().widget)({
          container: ref.current,
          symbol: tvSymbol || symbol,
          interval: 'D',
          datafeed: createPounceDatafeed(),
          library_path: '/charting_library/',
          theme: 'dark',
          autosize: true,
          timezone: 'America/New_York',
          // custom_indicators_getter: cansLimStudies,  ← wired in the studies pass
        });
        setStatus('ready');
      } catch {
        setStatus('missing');
      }
    });
    return () => {
      alive = false;
      try { widget?.remove?.(); } catch { /* noop */ }
    };
  }, [symbol, tvSymbol]);

  return (
    <div className="tv-adv">
      <div ref={ref} className="tv-adv__host" style={{ width: '100%', height: '100%' }} />
      {status === 'missing' && (
        <div className="tv-adv__missing">
          <strong>TradingView Advanced chart — not installed yet</strong>
          <p>
            This becomes a full TradingView-grade chart (with the custom CANSLIM studies baked in)
            once the licensed Charting Library files are dropped into <code>/public/charting_library/</code>.
            The data feed is already live. Setup steps: <code>docs/tradingview_charting_library.md</code>.
          </p>
        </div>
      )}
    </div>
  );
}
