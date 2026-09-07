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
 */
import { MAX_SYMBOLS, normalizeSymbol, useSignalWatchlist } from '../hooks/useSignalWatchlist';

export function SignalWatchButton({ symbol, compact = false }: { symbol: string; compact?: boolean }) {
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
      <span className="cm-tv cm-watch is-held" data-testid={`watch-${sym}`}
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
    <button type="button" className={`cm-tv cm-watch${on ? ' is-on' : ''}`}
            data-testid={`watch-${sym}`}
            title={title}
            aria-label={on ? `Remove ${sym} from Signals` : `Add ${sym} to Signals`}
            aria-pressed={on}
            onClick={(e) => { stop(e); if (on) wl.remove(sym); else wl.add(sym); }}>
      {label}{compact ? '' : ' Signals'}
    </button>
  );
}
