/* 📅 The lazy host of the continuous runner chart (2026-11-26, spec runcharts rev 2 §3.8, package fe-mount).
 *
 * Ajay 2026-11-26: "I want you to have continous charts for previous day runners we have some examples with traderview
 * charts with couple of indicators can you set that up? I wanna able to horizontal scroll tp check continuity like he does"
 *
 * Mounted ONCE by pages/ChartMaps.tsx behind the existing `showRunners` flag (🚩, a loaded primary owner), right after the
 * 📅 strip. It draws no element in place: nothing while the open store (lib/ggRunChart.ts) is empty, then the chart, which
 * portals itself onto <body>. The chart (and its chart library with it) is fetched only when a chart opens —
 * lazyWithReload, never a static import. Leaving 🚩 unmounts this host and closes the store, so the chart never reopens
 * by itself on the way back. One usage tick per open (a ‹ › step inside an open is not a new open). Display only. */
import { Suspense, useEffect } from 'react';
import { closeGgRunChart, stepGgRunChart, useGgRunChartOpen } from '../lib/ggRunChart';
import { lazyWithReload } from '../lib/lazyWithReload';
import { trackFeature } from '../lib/usageTracker';

const GgRunChart = lazyWithReload(() => import('./GgRunChart'));

export default function GgRunChartHost() {
  const open = useGgRunChartOpen();
  const isOpen = open !== null;

  useEffect(() => () => closeGgRunChart(), []);
  useEffect(() => { if (isOpen) trackFeature('gg-run-chart:open'); }, [isOpen]);

  if (!open) return null;
  return (
    <Suspense fallback={null}>
      <GgRunChart symbol={open.symbol} list={open.list} onClose={closeGgRunChart}
                  onStep={open.list.length > 1 ? stepGgRunChart : null} />
    </Suspense>
  );
}
