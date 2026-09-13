/* OverlayLegend — the chart ledger, where every entry is also the switch.
 *
 * Ajay 2026-08-31: "Chart feel so clumsy can you give me a ledger and some
 * check boxes to toggle these off from the view."
 *
 * Shows one checkbox per overlay FAMILY present on the current view (a control
 * for an overlay the board never draws would do nothing), with the swatch in
 * the chart's own color. The choice persists per browser via localStorage —
 * a per-viewer convenience, so losing it must cost nothing.
 */
import { OVERLAY_GROUPS, type OverlayGroup } from '../lib/chartOverlays';

type Props = {
  present: OverlayGroup[];
  hidden: Set<string>;
  onToggle: (key: string) => void;
  /** Families the CURRENT TAB is about (2026-09-13). A board whose whole
   *  reason for existing is one overlay draws that overlay whatever the saved
   *  preference says, so its box shows ticked and disabled rather than
   *  unticked-but-drawn — a checkbox that contradicts the chart is worse than
   *  one that cannot be clicked, and the title says why. */
  locked?: Set<string>;
};

export default function OverlayLegend({ present, hidden, onToggle, locked }: Props) {
  if (!present.length) return null;
  return (
    <div className="olg" role="group" aria-label="Chart overlays">
      <span className="olg-head">Ledger</span>
      {present.map((g) => {
        const isLocked = Boolean(locked?.has(g.key));
        return (
        <label key={g.key} className={`olg-item${isLocked ? ' olg-locked' : ''}`}
               title={isLocked ? 'This tab is about this overlay — always shown here' : g.hint}>
          <input type="checkbox" checked={isLocked || !hidden.has(g.key)}
                 disabled={isLocked}
                 onChange={() => onToggle(g.key)} />
          <span className="olg-swatch" style={{ background: g.swatch }} />
          {g.label}
        </label>
        );
      })}
      {hidden.size > 0 && (
        <button type="button" className="olg-reset"
                onClick={() => { for (const g of OVERLAY_GROUPS) {
                  if (hidden.has(g.key) && !locked?.has(g.key)) onToggle(g.key);
                } }}>
          show all
        </button>
      )}
    </div>
  );
}
