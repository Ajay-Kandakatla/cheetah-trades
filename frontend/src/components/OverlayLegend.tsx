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
};

export default function OverlayLegend({ present, hidden, onToggle }: Props) {
  if (!present.length) return null;
  return (
    <div className="olg" role="group" aria-label="Chart overlays">
      <span className="olg-head">Ledger</span>
      {present.map((g) => (
        <label key={g.key} className="olg-item" title={g.hint}>
          <input type="checkbox" checked={!hidden.has(g.key)}
                 onChange={() => onToggle(g.key)} />
          <span className="olg-swatch" style={{ background: g.swatch }} />
          {g.label}
        </label>
      ))}
      {hidden.size > 0 && (
        <button type="button" className="olg-reset"
                onClick={() => { for (const g of OVERLAY_GROUPS) {
                  if (hidden.has(g.key)) onToggle(g.key);
                } }}>
          show all
        </button>
      )}
    </div>
  );
}
