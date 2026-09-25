/* ⚡ MomentumBurstToggle — the Chart Maps checkbox (Ajay 2026-09-24: "Can you
 * add this as a check box in our filters please" → "Pin + badge, hide
 * nothing").
 *
 * Default OFF. Ticked, the ⚡ names move to the top of the board in their own
 * order and wear the badge; NOTHING is hidden. The count beside the label is
 * the number of names the pin moves — the same partition the grid draws, so
 * the two can never disagree. Two honest suffixes, each only when it is not
 * zero:
 *   · N unknown   — the server could not read them yet (pre-market, no print,
 *                   too little history); the served note says why;
 *   · N behind 🎯 — ⚡ names the 🎯 Enterable filter is holding back. ⚡ never
 *                   hides a name, so it says where the missing ones are.
 * The rule sentence in the hover is SERVED (momentum_burst.rule_text()).
 */
import { BURST_DISAMBIGUATION } from '../lib/momentumBurst';

export function MomentumBurstToggle({ checked, onChange, count, unknown, behind, rule, note, tiles }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  count: number;
  unknown: number;
  behind: number;
  rule?: string | null;
  note?: string | null;
  tiles: number;
}) {
  return (
    <label className="cm-ctl cm-ctl-check mb-toggle"
           title={`${rule ?? ''} ${BURST_DISAMBIGUATION} Counted over the ${tiles} tiles on this page — it re-orders, it hides nothing.`.trim()}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      ⚡ Momentum burst
      <span className="mb-count"> · {count}</span>
      {unknown > 0 ? <span className="mb-unknown" title={note ?? undefined}> · {unknown} unknown</span> : null}
      {behind > 0 ? (
        <span className="mb-behind" title="BLOCKED by 🎯 Enterable only — untick it to see them. ⚡ never hides a name.">
          {' · '}{behind} behind 🎯
        </span>
      ) : null}
    </label>
  );
}
