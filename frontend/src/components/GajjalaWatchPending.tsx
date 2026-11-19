/* GgwPendingPanel — the 👀 Watch tile's BODY while the name's first read has not landed (2026-11-19, watchnew2 spec
 * §3.5, WP-FE-tile). Ajay 2026-11-19: "When I add a new ticket they are gettinf added in to que but not active" /
 * "charts are not loading I amhaving to click on the chips again".
 *
 * Before: a pending row printed its served words in the tile HEAD only, so a fitted grid showed a big empty dark box
 * where the charts go. Now the served words (`row.text` — the board may have swapped in the served `late_text`) are
 * printed ONCE, in the body, and the head skips them (ggwPendingPanelShown is the one predicate both sides read).
 * Card rows ('ok' / 'loading' / 'error') and any row with frames never draw it. Every word is served; the FE composes
 * none. Display only — UNMEASURED. */
import type { GgwRow } from '../lib/gajjalaWatch';

/** True when the tile body prints the served pending words (and the head therefore does not). */
export function ggwPendingPanelShown(row: GgwRow): boolean {
  return row.state === 'pending' && row.frames.length === 0 && !!row.text;
}

export function GgwPendingPanel({ row }: { row: GgwRow }) {
  if (!ggwPendingPanelShown(row)) return null;
  return (
    <div className="ggw-dark ggw-charts ggw-pending" data-testid={`ggw-pending-${row.symbol}`} aria-busy="true">
      <p className="ggw-line ggw-pending-text">{row.text}</p>
    </div>
  );
}
