/* 🧨 first — the opt-in ordering checkbox (2026-09-15).
 *
 * Default OFF, on every board. Each of these tabs has a served order that was
 * chosen and tested for it (Catalysts room-first, Bonde's sections, the
 * Hottest legs), and the explosive read is — until the study says otherwise —
 * a FALLBACK ordering (floor held, then room). Making it the default would
 * quietly replace a tested order with an unmeasured one.
 *
 * Same shape as the Bonde 🎯 checkbox (BondeBoard.tsx, 2026-09-14): one box,
 * a title that says exactly what the order is, and no hidden filtering — the
 * rows are reordered, never removed.
 */
export function ExplosiveFirstToggle({ checked, onChange, className = 'ex-toggle', title, label }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  className?: string;
  title?: string;
  label?: string;
}) {
  return (
    <label className={className}
           title={title || 'Reorder these rows by the 🧨 explosive read: the measured score when the study separates, otherwise the fallback — band floor held first, then CLEAR (no supply overhead), then the most room to the first supply band. Names with no read sort last. Nothing is hidden and nothing here is a buy signal.'}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label || '🧨 explosive first'}
    </label>
  );
}
