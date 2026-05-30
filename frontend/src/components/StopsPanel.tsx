/* StopsPanel — compact "Entry + Stops menu" that replaces the old
   BUY/STOP/+1R/EXIT inline box in the card header's right column
   (user 2026-05-30: "remove this right side Buy, use that space for these
   buy and stops").

   Shows the buy point + every available stop method (Structure / Minervini /
   ATR×2 …) sorted tightest → widest, each with price + % from entry. The
   list is backend-assembled (entry_exit.exit.stops) so new stop methods
   appear automatically. Full basis + $ risk/share is in the row tooltip. */
import type { EntryExitPlan } from '../hooks/useSepa';

type ExitPlan = NonNullable<EntryExitPlan['exit']>;

const KIND_ICON: Record<string, string> = {
  structure: '🧱',
  minervini: '🛑',
  atr: '📡',
};

export function StopsPanel({ exit }: { exit: ExitPlan }) {
  const stops = exit.stops ?? [];
  if (!stops.length) return null;
  return (
    <div className="stops-panel">
      {exit.entry != null && (
        <div className="stops-panel__buy">
          <span className="stops-panel__buy-lab">BUY</span>
          <span className="stops-panel__buy-px">${exit.entry.toFixed(2)}</span>
        </div>
      )}
      <div className="stops-panel__hdr">STOPS · pick one</div>
      {stops.map((s) => (
        <div
          key={s.kind}
          className="stops-panel__row"
          title={`${s.label} stop — ${s.basis}\nRisk $${s.risk_per_share.toFixed(2)}/share from $${exit.entry?.toFixed(2)} entry`}
        >
          <span className="stops-panel__icon">{KIND_ICON[s.kind] ?? '•'}</span>
          <span className="stops-panel__label">{s.label}</span>
          <span className="stops-panel__px mono">${s.price.toFixed(2)}</span>
          <span className="stops-panel__pct mono">{s.pct}%</span>
          {s.tag && (
            <span className={`stops-panel__tag stops-panel__tag--${s.tag}`}>
              {s.tag === 'tightest' ? 'tight' : 'wide'}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
