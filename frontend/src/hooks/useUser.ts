import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type CurrentUser = {
  email: string;
  display_name: string;
  given_name: string | null;
  picture: string | null;
  is_default_user: boolean;
  /** Server-side admin flag (replaces hardcoded ADMIN_EMAIL bundle
   *  constants). True iff the user's email is in HOUSE_OWNER_EMAILS on
   *  the backend. The previous frontend pattern leaked the admin email
   *  into the JS bundle — anyone could curl the static assets to grep
   *  out a personal Gmail address. */
  is_admin: boolean;
};

let _cached: CurrentUser | null = null;

export function useCurrentUser() {
  const [user, setUser] = useState<CurrentUser | null>(_cached);
  const [loading, setLoading] = useState(_cached === null);

  useEffect(() => {
    if (_cached) return;
    let alive = true;
    fetch(`${API}/auth/me`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j: CurrentUser | null) => {
        if (!alive) return;
        if (j) _cached = j;
        setUser(j);
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  return { user, loading };
}
