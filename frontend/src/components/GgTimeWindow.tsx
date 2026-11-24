/**
 * ⏰ GgTimeWindow (2026-11-24) — a reminder line that glows on the 🚩 Gajjala page while the ET clock is inside one of
 * the served time windows (backend chart_maps/gajjala/time_windows.py; study eod-audits/research/
 * 2026-11-22_winner_time_of_day). Ajay 2026-11-24, verbatim: "can you add a reminder of that somwhere for me like
 * radiating when we enter those timings".
 *
 * Inside a window: the served window text + the served source line, with a soft radiating glow (gajjala_time_window.css
 * keyframes); prefers-reduced-motion → a static highlight, no animation. Outside every window, on a closed day, on a
 * fault or a failed GET: NOTHING (the quieter option — the page is dense). Every word and number is served; this file
 * types none (source-guarded in GgTimeWindow.test.tsx). Display only — never a gate, sort or filter.
 */
import { useGgTimeWindows } from '../hooks/useGgTimeWindows';
import '../styles/gajjala_time_window.css';

const REDUCE_QUERY = '(prefers-reduced-motion: reduce)';

function reducedMotion(): boolean {
  try {
    return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      && window.matchMedia(REDUCE_QUERY).matches;
  } catch {
    return false;
  }
}

export function GgTimeWindow({ enabled = true }: { enabled?: boolean } = {}) {
  const { block, active } = useGgTimeWindows(enabled);
  if (!active) return null;
  const still = reducedMotion();
  const src = typeof block?.source_text === 'string' && block.source_text.trim() ? block.source_text : null;
  return (
    <div className={`gg-tw ${still ? 'gg-tw-static' : 'gg-tw-glow'}`} role="status" data-testid="gg-time-window"
         data-window={active.key} data-motion={still ? 'reduce' : 'glow'}>
      <span className="gg-tw-text" data-testid="gg-time-window-text">{active.text}</span>
      {src ? <span className="gg-tw-src" data-testid="gg-time-window-src">{src}</span> : null}
    </div>
  );
}

export default GgTimeWindow;
