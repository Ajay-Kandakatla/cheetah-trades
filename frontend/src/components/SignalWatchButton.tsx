/* SignalWatchButton — one click, the name is on the ⚡ Signals tab.
 *
 * Ajay 2026-09-07: "One click and add to signals tab ... signals is like my
 * watch list." Mounted on every Chart Maps card (Back in Demand, Deep Demand,
 * Quick Bounce, Gabbar, Strong VCP, Breaking, …) next to the TV button, and in
 * the Catalysts ▸ promo list's ticker cell. Reads/writes useSignalWatchlist,
 * the same store the Signals board renders — so the tab already has the name
 * when he opens it.
 *
 * Three states:
 *   + Signals   not on the list → click adds (POST). Past 12 names the oldest
 *               drops off (server and client agree); the title says so.
 *   ✓ Signals   on the list → click removes (DELETE).
 *   💼 Signals  in his portfolio: rides the board by default and leaves with
 *               the position, never from here — static, no request.
 * The cards are wrapped in a <Link>, so the click must never bubble into a
 * navigation: preventDefault + stopPropagation, like the TV button.
 *
 * `chrome` REPLACES the look class, it does not append to it (Ajay 2026-09-10:
 * "add a signals button in individual ticket page, I am using it as a watch
 * list page"). The ticker page's action column styles its controls
 * `sepa-btn sepa-btn--ghost`, and appending would not work: `.cm-tv`
 * (styles.css:11573) sits BELOW `.sepa-btn--ghost` (3641) and both are
 * single-class, so cm-tv's 10px font and 3px padding would win and the button
 * would render as a tiny chip beside full-size siblings. `cm-watch` is never
 * swappable — it is the anchor for `.cm-watch.is-on` (the green "already on
 * the list" state), `.cm-watch.is-held` (dimmed) and `.pcw__links .cm-watch`,
 * and those are the only rules that paint the states at all. BOTH branches
 * take the chrome: the held branch is a <span>, and leaving it on cm-tv would
 * print 💼 as a 10px chip in a column of 0.78rem buttons.
 */
import { MAX_SYMBOLS, normalizeSymbol, useSignalWatchlist } from '../hooks/useSignalWatchlist';

export const WATCH_CHROME_CARD = 'cm-tv';

export function SignalWatchButton(
  { symbol, compact = false, chrome = WATCH_CHROME_CARD }:
  { symbol: string; compact?: boolean; chrome?: string },
) {
  const wl = useSignalWatchlist();
  const sym = normalizeSymbol(symbol);
  if (!sym) return null;
  const held = wl.isHeld(sym);
  const on = held || wl.has(sym);
  const stop = (e: { preventDefault(): void; stopPropagation(): void }) => {
    e.preventDefault();
    e.stopPropagation();
  };
  if (held) {
    return (
      <span className={`${chrome} cm-watch is-held`} data-testid={`watch-${sym}`}
            title={`${sym} is in your portfolio — it rides the Signals board by default and leaves with the position`}
            aria-label={`${sym} is in Signals via your portfolio`}
            onClick={stop}>
        💼{compact ? '' : ' Signals'}
      </span>
    );
  }
  const label = on ? '✓' : '+';
  const title = on
    ? `${sym} is on your Signals watchlist — click to remove it`
    : wl.full
      ? `Add ${sym} to Signals — the list holds ${MAX_SYMBOLS}, so the oldest name drops off`
      : `Add ${sym} to Signals (your watchlist)`;
  return (
    <button type="button" className={`${chrome} cm-watch${on ? ' is-on' : ''}`}
            data-testid={`watch-${sym}`}
            title={title}
            aria-label={on ? `Remove ${sym} from Signals` : `Add ${sym} to Signals`}
            aria-pressed={on}
            onClick={(e) => { stop(e); if (on) wl.remove(sym); else wl.add(sym); }}>
      {label}{compact ? '' : ' Signals'}
    </button>
  );
}
