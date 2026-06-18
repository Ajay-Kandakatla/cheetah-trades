/* NewBadge — an in-place "✨ NEW" highlight for a freshly-shipped feature.
 * Renders nothing once the user has seen it. Place it next to any new element:
 *   <NewBadge id="breakouts-beta" label="Beta column + low-vol sort" />
 * Clicking it (or visiting the feature's page) clears it. Ajay 2026-06-18. */
import { useNewFeatures } from '../hooks/useNewFeatures';

export function NewBadge({ id, label }: { id: string; label?: string }) {
  const { isNew, markSeen } = useNewFeatures();
  if (!isNew(id)) return null;
  return (
    <span
      className="new-badge"
      role="status"
      title={label ? `New: ${label} — click to dismiss` : 'New — click to dismiss'}
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); markSeen(id); }}
    >
      ✨ NEW
    </span>
  );
}
