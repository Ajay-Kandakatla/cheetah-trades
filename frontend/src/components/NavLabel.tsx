/* NavLabel — a nav menu item's label plus a ✨ "new here" dot when that route
 * has an unseen newly-shipped feature. Drop-in for `{item.label}` in NavBar.
 * Ajay 2026-06-18. */
import type { MenuItem } from '../hooks/useMyMenu';
import { useNewFeatures } from '../hooks/useNewFeatures';

export function NavLabel({ item }: { item: MenuItem }) {
  const { isNewRoute } = useNewFeatures();
  return (
    <>
      {item.label}
      {isNewRoute(item.to) && (
        <span className="nav-new-dot" aria-label="new feature here" title="Something new here">✨</span>
      )}
    </>
  );
}
