/* 🎯 EnterableOnlyToggle — the global "Enterable only" checkbox (2026-09-15).
 *
 * Ajay: "I do not want to see not enterable alerts or stocks in any of the
 * chart maps." So it is ON by default on Chart Maps — the page owns that
 * default and writes `?show=all` when he turns it off, which is the ONLY place
 * the state lives (no localStorage: a filter he cannot see the state of is a
 * filter that quietly eats a board tomorrow).
 *
 * It hides the SERVED BLOCKED verdict and nothing else. What "hidden" means,
 * and how many rows it cost, is never implied — <HiddenCount> renders beside it
 * on every board, even when the count is zero.
 *
 * On an `n/a` tab (rows that are not demand reversals at all) the checkbox is
 * DISABLED rather than hidden, and its title is the backend's own sentence
 * saying why. A control that vanishes reads like a bug; one that explains
 * itself does not.
 */
import type { EnterableKind } from '../lib/enterable';

export function EnterableOnlyToggle({
  checked,
  onChange,
  kind = 'demand',
  naText,
  label = '🎯 Enterable only',
  className = 'en-toggle',
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  /** The SERVED kind for this tab (payload `enterable_kind`). */
  kind?: EnterableKind | string | null;
  /** The backend's own "no demand read for this tab" sentence. */
  naText?: string | null;
  label?: string;
  className?: string;
}) {
  const inert = kind === 'n/a';
  return (
    <label className={className} title={inert ? (naText || undefined) : undefined}>
      <input
        type="checkbox"
        checked={checked}
        disabled={inert}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  );
}
