import type { GgBreakout } from '../lib/gajjala';

/**
 * ⏸ No-breakout line on Gajjala cards and today's 📈 Track rows (2026-11-12, no-breakout spec §3.3).
 *
 * Ajay 2026-11-12: "Most of our potentials are not having breakout, please write that on them that.. I need for an
 * additonal break out from the triggers Usually after that run up to tirgger point they are mostly just sitting there"
 *
 * Display only. Every word is SERVED (backend chart_maps/gajjala/breakout_state.py): the head, the detail, the full
 * text and the hint. The FE types none. No served head → nothing renders. UNMEASURED.
 */
const served = (x: unknown): x is string => typeof x === 'string' && x.trim() !== '';
const STATE_RE = /^[a-z_]+$/;

/** The card line: bold served head + the served detail verbatim; the served hint on hover. */
export function GgBreakoutLine({ breakout, sym }: { breakout: GgBreakout | null | undefined; sym: string }) {
  if (!breakout || typeof breakout !== 'object' || !served(breakout.head)) return null;
  const cls = typeof breakout.state === 'string' && STATE_RE.test(breakout.state) ? ` gg-brk-${breakout.state}` : '';
  const detail = typeof breakout.detail === 'string' ? breakout.detail : '';
  return (
    <div className={`cm-note gg-line gg-brk${cls}`} data-testid={`gg-brk-${sym}`}
         title={served(breakout.hint) ? breakout.hint : undefined}>
      <strong>{breakout.head}</strong>{detail}
    </div>
  );
}

/** The 📈 row word: " · " + the bold served head only (the dense row); the full served text on hover. */
export function GgBreakoutWord({ breakout, id }: { breakout: GgBreakout | null | undefined; id: string }) {
  if (!breakout || typeof breakout !== 'object' || !served(breakout.head)) return null;
  const title = served(breakout.text) ? breakout.text : served(breakout.hint) ? breakout.hint : undefined;
  return (
    <span className="gg-track-push gg-track-nobrk" data-testid={`gg-track-nobrk-${id}`} title={title}>
      {' · '}<strong>{breakout.head}</strong>
    </span>
  );
}
