/* OllamaIcon — a private 🦙 in the nav that opens /ollama, for one person.
 *
 * Ajay 2026-09-14: "Give me a private icon for ajaykandakatl email for
 * chatting with ollama model."
 *
 * WHO SEES IT: exactly the primary admin — `is_primary_admin` from /auth/me,
 * a single address the server resolves. NOT `is_admin`, which every house
 * owner carries (Vineetha would see it). Everyone else renders nothing, so
 * the nav gives away no hint that the page exists — the same stealth posture
 * as the route (PrimaryAdminRoute) and the API (404).
 *
 * The address itself is never in this file; the server says yes or no.
 *
 * WHERE: beside the IV badge in the top-right cluster on desktop, and in the
 * mobile action row. It is a NavLink so the active page outlines it, like
 * the IV badge does.
 */
import { NavLink } from 'react-router-dom';
import { useCurrentUser } from '../hooks/useUser';

export const OLLAMA_ICON = '🦙';
export const OLLAMA_ICON_TITLE = 'Ollama — private chat with the local model';

export function OllamaIcon({ compact = false }: { compact?: boolean }) {
  const { user } = useCurrentUser();
  if (!user?.is_primary_admin) return null;
  return (
    <NavLink
      to="/ollama"
      className={({ isActive }) =>
        `ollama-icon${isActive ? ' is-active' : ''}${compact ? ' ollama-icon--compact' : ''}`}
      title={OLLAMA_ICON_TITLE}
      aria-label={OLLAMA_ICON_TITLE}
      data-testid="ollama-icon"
    >
      <span className="ollama-icon__glyph" aria-hidden="true">{OLLAMA_ICON}</span>
      {!compact && <span className="ollama-icon__label">Ollama</span>}
    </NavLink>
  );
}
