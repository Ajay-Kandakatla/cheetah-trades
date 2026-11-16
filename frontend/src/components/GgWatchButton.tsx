/* ➕/➖ Watch — one click puts a card's name on 👀 Gajjala's Watch, or takes it off (2026-11-15).
 *
 * Ajay 2026-11-15: "can you add an add to watch list button on all the stocks to move them and also remove button from
 * watch list too."
 *
 * Mounted in PatternChart's action row, so every Chart Maps card carries it (🚩 5-min / 1-min / 🧪, 🥇 Luk and every
 * tile board). Owner only: anyone else is served `owner_only` and the button renders nothing. The cards sit inside a
 * <Link>: the click never bubbles into a navigation (preventDefault + stopPropagation, the SignalWatchButton rule).
 * Words and titles are SERVED; at the cap ➕ is disabled with the served full sentence. The last answer's sentence
 * rides the title of the card that was clicked. */
import { ggwFold, ggwHas, ggwTitle, toggleGgw, useGgwList } from '../lib/ggWatchList';
import '../styles/ggWatchButton.css';

export function GgWatchButton({ symbol }: { symbol: string }) {
  const st = useGgwList();
  const sym = typeof symbol === 'string' ? symbol.trim() : '';
  if (!sym || st.phase !== 'ok' || !st.labels) return null;
  const on = ggwHas(st.symbols, sym);
  const blocked = !on && st.full;
  const busy = st.busy != null;
  /* The last answer's sentence rides this card's title only while it still agrees with the list (an ➕ answer while
   * the name is on, an ➖ answer while it is off) — a later read that moves the name drops it. */
  const said = st.msg && ggwFold(st.msg.sym) === ggwFold(sym) && st.msg.on === on ? st.msg.text : null;
  const title = said ?? (blocked ? st.full_text ?? undefined
    : ggwTitle(on ? st.labels.remove_title : st.labels.add_title, sym));
  return (
    <button type="button" className={`cm-tv ggw-card-btn${on ? ' is-on' : ''}`}
            data-testid={`ggw-card-btn-${sym}`}
            title={title}
            aria-label={ggwTitle(on ? st.labels.remove_title : st.labels.add_title, sym)}
            aria-pressed={on}
            disabled={busy || blocked}
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); void toggleGgw(sym); }}>
      {on ? st.labels.remove : st.labels.add}
    </button>
  );
}
