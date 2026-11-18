/* ➕/➖ Watch — one click puts a card's name on 👀 Gajjala's Watch, or takes it off (2026-11-15).
 *
 * Ajay 2026-11-15: "can you add an add to watch list button on all the stocks to move them and also remove button from
 * watch list too."
 *
 * Mounted in PatternChart's action row, so every Chart Maps card carries it (🚩 5-min / 1-min / 🧪, 🥇 Luk and every
 * tile board). Owner only: anyone else is served `owner_only` and the button renders nothing. The cards sit inside a
 * <Link>: the click never bubbles into a navigation (preventDefault + stopPropagation, the SignalWatchButton rule).
 * Words and titles are SERVED. The last answer's sentence rides the title of the card that was clicked.
 *
 * 🔁 2026-11-18 — Ajay: "All the watch button are not working or not reacting" (at the cap ➕ was disabled with a
 * hover-only title; a phone has no hover) · "For watch list when I add new ones remove the ones that are not active in
 * the watch list" → "Oldest added". ➕ is NEVER disabled at the cap now: the server replaces the oldest name he added
 * (never a 🎯 A+) and answers `replaced`; every answer but a plain added / removed (replaced, the all-A+ `full`
 * refusal, an error…) is also SHOWN as a short line beside the clicked button — the served sentence, verbatim. */
import { ggwFold, ggwHas, ggwTitle, GGW_ROUTINE_STATES, toggleGgw, useGgwList } from '../lib/ggWatchList';
import '../styles/ggWatchButton.css';

export function GgWatchButton({ symbol }: { symbol: string }) {
  const st = useGgwList();
  const sym = typeof symbol === 'string' ? symbol.trim() : '';
  if (!sym || st.phase !== 'ok' || !st.labels) return null;
  const on = ggwHas(st.symbols, sym);
  const busy = st.busy != null;
  /* The last answer's sentence rides this card's title only while it still agrees with the list (an ➕ answer while
   * the name is on, an ➖ answer while it is off) — a later read that moves the name drops it. */
  const mine = st.msg && ggwFold(st.msg.sym) === ggwFold(sym) && st.msg.on === on ? st.msg : null;
  const said = mine ? mine.text : null;
  const shown = mine && !GGW_ROUTINE_STATES.includes(mine.state ?? '') ? mine.text : null;
  const title = said ?? ggwTitle(on ? st.labels.remove_title : st.labels.add_title, sym);
  const button = (
    <button type="button" className={`cm-tv ggw-card-btn${on ? ' is-on' : ''}`}
            data-testid={`ggw-card-btn-${sym}`}
            title={title}
            aria-label={ggwTitle(on ? st.labels.remove_title : st.labels.add_title, sym)}
            aria-pressed={on}
            disabled={busy}
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); void toggleGgw(sym); }}>
      {on ? st.labels.remove : st.labels.add}
    </button>
  );
  if (!shown) return button;
  return (
    <>
      {button}
      <span className="ggw-card-msg" role="status" data-testid={`ggw-card-msg-${sym}`}
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}>{shown}</span>
    </>
  );
}
