/* AdminAccess — admin-only access-control matrix.
 *
 * Layout (changed 2026-05-15 — pivoted from users-as-rows):
 *   PAGES as rows  (left column, sticky so it stays visible while
 *                   scrolling horizontally)
 *   USERS as cols  (top header row, sticky so it stays visible while
 *                   scrolling vertically)
 *
 * Page-name column is horizontal-readable; user-name header is
 * horizontal-readable too because there are far fewer users than
 * pages. Earlier rotated-label hack is gone.
 *
 * Owners are now FULLY EDITABLE (also 2026-05-15). The admin can save
 * a custom feature set against their own row or Vineetha's row to
 * declutter their navs. Backend resolution: saved doc wins; absence
 * of saved doc still defaults to "everything" for owners, so first-
 * time UX is unchanged.
 *
 * Saves are optimistic with rollback on failure. No save button —
 * each click is a write.
 */
import { useEffect, useMemo, useState } from 'react';
import { API } from '../lib/apiBase';
import { useCurrentUser } from '../hooks/useUser';

type FeatureDef = {
  id:      string;
  label:   string;
  group:   string;
  default: boolean;
};

type UserRow = {
  email:      string;
  /** Server-resolved display name (DISPLAY_NAME_OVERRIDES_JSON →
   *  Google profile → title-cased handle). Backend always populates
   *  this — see backend/access/api.py admin_access_users. */
  display_name: string;
  features:   string[];
  is_owner:   boolean;
  updated_at?: number | null;
  updated_by?: string | null;
  has_saved:  boolean;
};

/** Switch-style toggle button — replaces native checkboxes throughout
 *  the matrix for a more touch-friendly affordance.
 *
 *  Visual states:
 *    - on:           filled track + knob on the right
 *    - off:          outlined track + knob on the left
 *    - mixed:        partial fill + knob centered (used by masters)
 *    - disabled:     half-opacity, no pointer
 *
 *  Variants:
 *    - 'cell':       compact, used per (page, user) intersection.
 *                    Green on-state to read as a "grant".
 *    - 'master':     wider, used at row + column heads. Gold on-state
 *                    so masters are visually distinct from per-cell
 *                    grants and the user notices "this fires for many".
 */
type ToggleVariant = 'cell' | 'master';

function Toggle(props: {
  on: boolean;
  mixed?: boolean;
  disabled?: boolean;
  onClick: () => void;
  variant?: ToggleVariant;
  title?: string;
  ariaLabel?: string;
}) {
  const variant: ToggleVariant = props.variant || 'cell';
  const isMaster = variant === 'master';
  const w = isMaster ? 34 : 28;
  const h = isMaster ? 18 : 16;
  const knob = h - 4;
  const onColor = isMaster ? 'var(--warn, #d97706)' : 'var(--positive, #10b981)';
  const offBg  = 'transparent';
  const offBorder = 'var(--rule, #555)';
  // Knob position: left when off, right when on, centered for "mixed"
  // (only the master uses mixed; cell never sets it).
  const knobLeft = props.mixed
    ? (w - knob) / 2
    : props.on
      ? (w - knob - 2)
      : 2;

  return (
    <button
      type="button"
      onClick={props.disabled ? undefined : props.onClick}
      aria-pressed={props.on}
      aria-label={props.ariaLabel || props.title}
      disabled={props.disabled}
      title={props.title}
      style={{
        position: 'relative',
        display: 'inline-block',
        width: w, height: h,
        padding: 0,
        background: props.on || props.mixed ? onColor : offBg,
        border: props.on ? `1px solid ${onColor}` : `1px solid ${offBorder}`,
        borderRadius: h,
        cursor: props.disabled ? 'not-allowed' : 'pointer',
        opacity: props.disabled ? 0.45 : 1,
        transition: 'background 120ms ease, border-color 120ms ease',
        verticalAlign: 'middle',
      }}
    >
      <span
        aria-hidden
        style={{
          position: 'absolute',
          top: 1,
          left: knobLeft,
          width: knob,
          height: knob,
          borderRadius: '50%',
          background: props.on || props.mixed ? '#fff' : 'var(--cm-slate, #888)',
          transition: 'left 140ms ease, background 120ms ease',
          boxShadow: props.on ? '0 1px 2px rgba(0,0,0,0.3)' : 'none',
        }}
      />
    </button>
  );
}


/** Friendly display name with a tiny safety fallback.
 *
 *  Backend's /admin/access/users now sends every row with a
 *  server-resolved ``display_name`` (via DISPLAY_NAME_OVERRIDES_JSON →
 *  Google profile → title-cased handle). This helper is only used as
 *  a defensive fallback in case a row arrives without that field
 *  during a deploy transition. The personal-name override map that
 *  used to live here was moved to the backend env config to keep
 *  personal Gmail addresses out of the JS bundle. */
function displayName(row: { email: string; display_name?: string }): string {
  if (row.display_name && row.display_name.trim()) return row.display_name;
  const local = (row.email.split('@')[0] || row.email);
  return local
    .split(/[._]/)
    .map((s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : s)
    .join(' ');
}

export default function AdminAccessPage() {
  const { user } = useCurrentUser();
  const isAdmin = !!user?.is_admin;

  const [catalog, setCatalog] = useState<FeatureDef[] | null>(null);
  const [users,   setUsers]   = useState<UserRow[] | null>(null);
  const [err,     setErr]     = useState<string | null>(null);
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [accessDenied, setAccessDenied] = useState(false);

  // The pages×users matrix is unusable on a phone (sticky columns overlap).
  // On narrow screens we render a single-user editor instead. (2026-05-30)
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' && window.matchMedia('(max-width: 680px)').matches,
  );
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(max-width: 680px)');
    const on = () => setIsMobile(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  // Which user the mobile editor is showing.
  const [mobileUserEmail, setMobileUserEmail] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch(`${API}/admin/access/catalog`).then((r) => {
        if (r.status === 404) { setAccessDenied(true); return null; }
        if (!r.ok) throw new Error(`catalog ${r.status}`);
        return r.json();
      }),
      fetch(`${API}/admin/access/users`).then((r) => {
        if (r.status === 404) { setAccessDenied(true); return null; }
        if (!r.ok) throw new Error(`users ${r.status}`);
        return r.json();
      }),
    ])
      .then(([cat, u]) => {
        if (cancelled || !cat || !u) return;
        setCatalog(cat.catalog || []);
        setUsers(u.users || []);
      })
      .catch((e) => { if (!cancelled) setErr(String(e?.message || e)); });
    return () => { cancelled = true; };
  }, []);

  // Compute the visual ordering of pages, with one synthetic "section
  // header" row inserted before each new group. The renderer treats
  // section rows specially (no checkboxes, just a label spanning the
  // user columns).
  type Row =
    | { kind: 'section'; group: string }
    | { kind: 'feature'; feature: FeatureDef };
  const rows: Row[] = useMemo(() => {
    if (!catalog) return [];
    const out: Row[] = [];
    let lastGroup: string | null = null;
    for (const f of catalog) {
      if (f.group !== lastGroup) {
        out.push({ kind: 'section', group: f.group });
        lastGroup = f.group;
      }
      out.push({ kind: 'feature', feature: f });
    }
    return out;
  }, [catalog]);

  if (accessDenied || (user && !isAdmin)) {
    return (
      <div style={{ padding: '4rem 1.5rem', textAlign: 'center', color: 'var(--cm-slate)' }}>
        <h1 style={{ fontSize: '1.4rem', fontFamily: 'serif', fontStyle: 'italic' }}>404</h1>
        <p>Not found.</p>
      </div>
    );
  }

  const toggleFeature = async (row: UserRow, featureId: string, on: boolean) => {
    const pendingKey = `${row.email} ${featureId}`;
    setPending((s) => new Set(s).add(pendingKey));

    const nextFeatures = on
      ? Array.from(new Set([...row.features, featureId]))
      : row.features.filter((f) => f !== featureId);
    setUsers((prev) => (prev || []).map((u) =>
      u.email === row.email ? { ...u, features: nextFeatures, has_saved: true } : u,
    ));

    try {
      const r = await fetch(`${API}/admin/access/users/${encodeURIComponent(row.email)}`, {
        method:  'PUT',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ features: nextFeatures }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.detail || `HTTP ${r.status}`);
      }
      const j = await r.json();
      setUsers((prev) => (prev || []).map((u) =>
        u.email === row.email ? { ...u, features: j.features || nextFeatures, updated_at: j.updated_at } : u,
      ));
    } catch (e: any) {
      setUsers((prev) => (prev || []).map((u) =>
        u.email === row.email ? { ...u, features: row.features } : u,
      ));
      setErr(`Save failed for ${row.email}: ${e?.message || e}`);
    } finally {
      setPending((s) => {
        const next = new Set(s);
        next.delete(pendingKey);
        return next;
      });
    }
  };

  /** Bulk-toggle every feature for one user. Click semantics:
   *    - all-on  → none
   *    - mixed   → all-on   (so an intermediate state always settles
   *                          on a fully-granted view — users complained
   *                          that "click once, all granted" was the
   *                          expected behavior coming from spreadsheet
   *                          column-select muscle memory)
   *    - none-on → all-on
   *
   * Single network call: PUT with the full target feature list. The
   * row updates optimistically and rolls back on failure. */
  const toggleAllForUser = async (row: UserRow, allFeatureIds: string[]) => {
    const allOn = row.features.length === allFeatureIds.length;
    const nextFeatures = allOn ? [] : [...allFeatureIds];
    const pendingKey = `${row.email} *`;
    setPending((s) => new Set(s).add(pendingKey));

    setUsers((prev) => (prev || []).map((u) =>
      u.email === row.email ? { ...u, features: nextFeatures, has_saved: true } : u,
    ));
    try {
      const r = await fetch(`${API}/admin/access/users/${encodeURIComponent(row.email)}`, {
        method:  'PUT',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ features: nextFeatures }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.detail || `HTTP ${r.status}`);
      }
      const j = await r.json();
      setUsers((prev) => (prev || []).map((u) =>
        u.email === row.email ? { ...u, features: j.features || nextFeatures, updated_at: j.updated_at } : u,
      ));
    } catch (e: any) {
      // Rollback to the state captured at click-time.
      setUsers((prev) => (prev || []).map((u) =>
        u.email === row.email ? { ...u, features: row.features } : u,
      ));
      setErr(`Bulk toggle failed for ${row.email}: ${e?.message || e}`);
    } finally {
      setPending((s) => {
        const next = new Set(s);
        next.delete(pendingKey);
        return next;
      });
    }
  };

  /** Flip one feature on/off for EVERY user at once (row-master).
   *  Fans the writes out as parallel PUTs — one per user — so the
   *  whole bulk change goes through with a single click. Optimistic
   *  update reflects the target state immediately; on failure we
   *  roll back only the users whose write failed (others stay updated). */
  const toggleFeatureForAllUsers = async (featureId: string) => {
    if (!users) return;
    // Decide target state: if ANY user is missing it, click grants to all.
    // Only when every user already has it does the click revoke from all.
    // (Matches the "click intermediate state → all on" UX from the
    // column master.)
    const everyoneHas = users.every((u) => u.features.includes(featureId));
    const targetOn   = !everyoneHas;

    const pendingKey = `* ${featureId}`;
    setPending((s) => new Set(s).add(pendingKey));

    // Snapshot before optimistic update so we can selectively roll back.
    const prevByEmail = new Map(users.map((u) => [u.email, u.features]));

    // Optimistic update.
    setUsers((prev) => (prev || []).map((u) => {
      const has = u.features.includes(featureId);
      if (has === targetOn) return u;          // no change for this user
      const next = targetOn
        ? Array.from(new Set([...u.features, featureId]))
        : u.features.filter((f) => f !== featureId);
      return { ...u, features: next, has_saved: true };
    }));

    // Fan-out PUTs in parallel — small N (handful of users), each
    // payload is tiny, server handlers are non-blocking (asyncio.to_thread).
    const results = await Promise.allSettled(users.map(async (u) => {
      const has = u.features.includes(featureId);
      if (has === targetOn) return { email: u.email, ok: true, skipped: true };
      const next = targetOn
        ? Array.from(new Set([...u.features, featureId]))
        : u.features.filter((f) => f !== featureId);
      const r = await fetch(`${API}/admin/access/users/${encodeURIComponent(u.email)}`, {
        method:  'PUT',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ features: next }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.detail || `HTTP ${r.status}`);
      }
      return { email: u.email, ok: true, skipped: false };
    }));

    // Roll back any failures.
    const failed: string[] = [];
    results.forEach((res, i) => {
      if (res.status === 'rejected') {
        const email = users[i].email;
        failed.push(email);
        const prev = prevByEmail.get(email) || [];
        setUsers((cur) => (cur || []).map((u) =>
          u.email === email ? { ...u, features: prev } : u,
        ));
      }
    });
    if (failed.length) {
      setErr(`Bulk-toggle "${featureId}" failed for: ${failed.join(', ')}`);
    }

    setPending((s) => {
      const next = new Set(s);
      next.delete(pendingKey);
      return next;
    });
  };

  const resetUser = async (row: UserRow) => {
    if (!confirm(`Reset ${displayName(row)} to default features?`)) return;
    try {
      const r = await fetch(`${API}/admin/access/users/${encodeURIComponent(row.email)}`, { method: 'DELETE' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const u = await fetch(`${API}/admin/access/users`).then(r => r.json());
      setUsers(u.users || []);
    } catch (e: any) {
      setErr(`Reset failed: ${e?.message || e}`);
    }
  };

  // ── Sticky-pane style helpers ────────────────────────────────────
  // Encoded as inline style maps so the values stay co-located with
  // the column layout decisions and the table doesn't depend on a new
  // CSS file. zIndex tiering:
  //   3 = top-left corner (sticky both axes, must beat everything)
  //   2 = sticky top header row
  //   2 = sticky left column
  //   1 = group-section row when scrolled under the header
  //
  // Background colors match the surrounding theme so sticky cells
  // don't appear transparent over scrolled rows beneath them.
  const stickyHeaderBg = 'var(--bg-raised, #181818)';
  const stickyColBg    = 'var(--bg-raised, #181818)';

  const labelColStyle: React.CSSProperties = {
    position: 'sticky',
    left: 0,
    background: stickyColBg,
    zIndex: 2,
    borderRight: '1px solid var(--rule, #333)',
    borderBottom: '1px solid var(--rule, #2a2a2a)',
    padding: '0.4rem 0.7rem',
    whiteSpace: 'nowrap',
    fontWeight: 500,
    fontSize: '0.86rem',
    // Min-width so the row-master + label + per-row count line up
    // without crowding the page label.
    minWidth: 230,
    textAlign: 'left',
  };

  const cornerStyle: React.CSSProperties = {
    position: 'sticky',
    top: 0, left: 0,
    background: stickyHeaderBg,
    zIndex: 3,
    borderRight: '1px solid var(--rule, #333)',
    borderBottom: '1px solid var(--rule, #333)',
    padding: '0.5rem 0.7rem',
    fontSize: '0.7rem',
    color: 'var(--cm-slate)',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
  };

  const userHeaderStyle: React.CSSProperties = {
    position: 'sticky',
    top: 0,
    background: stickyHeaderBg,
    zIndex: 2,
    borderBottom: '1px solid var(--rule, #333)',
    padding: '0.4rem 0.45rem',
    textAlign: 'center',
    minWidth: 100,
    whiteSpace: 'nowrap',
  };

  return (
    <div className="cm-page" style={{ padding: '1.2rem 1.4rem', maxWidth: 1400, margin: '0 auto' }}>
      <header className="cm-pagehead" style={{ marginBottom: '0.9rem' }}>
        <div className="eyebrow">№ Admin · per-user access</div>
        <h1 className="display cm-pagehead__title" style={{ margin: '0.25rem 0 0' }}>
          User access matrix
        </h1>
        <p className="lede" style={{ marginTop: '0.4rem' }}>
          Rows are pages; columns are users. Toggle to grant/revoke — saves immediately.
          You can hide pages from your own nav (and Vineetha's) here too.
          Scroll the matrix horizontally to see more users; the page-name column stays in place.
        </p>
      </header>

      {err && (
        <div style={{
          padding: '0.5rem 0.8rem', marginBottom: '0.8rem',
          background: 'rgba(239,68,68,0.08)',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 4, color: 'var(--negative)', fontSize: '0.85rem',
        }}>
          {err} · <button onClick={() => setErr(null)} style={{ background: 'none', border: 0, color: 'inherit', textDecoration: 'underline', cursor: 'pointer' }}>dismiss</button>
        </div>
      )}

      {(!catalog || !users) && <div style={{ color: 'var(--cm-slate)' }}>Loading…</div>}

      {/* ── Desktop: the full pages×users matrix ────────────────────────── */}
      {catalog && users && !isMobile && (
        <div
          style={{
            overflow: 'auto',
            maxHeight: '78vh',                                  // vertical scrollport for sticky-top to anchor against
            border: '1px solid var(--rule, #333)',
            borderRadius: 6,
            background: 'var(--bg-raised, #181818)',
            position: 'relative',
          }}
        >
          <table style={{ borderCollapse: 'separate', borderSpacing: 0, fontSize: '0.84rem', width: 'max-content' }}>
            <thead>
              <tr>
                <th style={cornerStyle}>Page</th>
                {users.map((u) => {
                  // Master checkbox state for this column.
                  const allIds = (catalog || []).map((f) => f.id);
                  const onCount = u.features.filter((f) => allIds.includes(f)).length;
                  const allOn   = onCount > 0 && onCount === allIds.length;
                  const mixed   = onCount > 0 && onCount < allIds.length;
                  const bulkPending = pending.has(`${u.email} *`);
                  return (
                    <th key={u.email} style={userHeaderStyle}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                        <span style={{ fontWeight: 700, fontSize: '0.86rem' }}>{displayName(u)}</span>
                        <span style={{ fontSize: '0.66rem', color: 'var(--cm-slate)' }}>
                          {u.email}
                          {u.is_owner && <span style={{ marginLeft: 4, color: 'var(--warn, #d97706)' }}>· owner</span>}
                        </span>
                        {/* Master toggle: flips every feature for this
                            user at once. Gold "master" variant so it
                            reads as a high-impact action, not a routine
                            per-cell tick. Count shows current/total. */}
                        <div style={{
                          marginTop: 4,
                          display: 'flex', alignItems: 'center', gap: 6,
                          fontSize: '0.62rem', color: 'var(--cm-slate)',
                        }}>
                          <Toggle
                            on={allOn}
                            mixed={mixed}
                            disabled={bulkPending}
                            onClick={() => toggleAllForUser(u, allIds)}
                            variant="master"
                            title={allOn
                              ? `Clear all features for ${displayName(u)}`
                              : `Grant all features to ${displayName(u)}`}
                          />
                          <span>{onCount}/{allIds.length}</span>
                        </div>
                        {u.has_saved && (
                          <button
                            onClick={() => resetUser(u)}
                            style={{
                              marginTop: 2,
                              background: 'none',
                              border: '1px solid var(--rule, #555)',
                              color: 'var(--cm-slate)',
                              padding: '0px 6px',
                              borderRadius: 3,
                              cursor: 'pointer',
                              fontSize: '0.62rem',
                            }}
                            title="Reset to defaults"
                          >
                            ↺ reset
                          </button>
                        )}
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => {
                if (row.kind === 'section') {
                  return (
                    <tr key={`grp-${row.group}-${i}`}>
                      <th
                        style={{
                          ...labelColStyle,
                          textTransform: 'uppercase',
                          letterSpacing: '0.1em',
                          fontSize: '0.66rem',
                          color: 'var(--cm-slate)',
                          fontWeight: 600,
                          background: 'var(--bg, #0f0f0f)',
                          borderTop: '1px solid var(--rule, #333)',
                        }}
                      >
                        {row.group}
                      </th>
                      {users.map((u) => (
                        <td
                          key={u.email}
                          style={{
                            background: 'var(--bg, #0f0f0f)',
                            borderTop: '1px solid var(--rule, #333)',
                            borderBottom: '1px solid var(--rule, #2a2a2a)',
                          }}
                        />
                      ))}
                    </tr>
                  );
                }
                const f = row.feature;
                // Row-master state — count how many users have THIS
                // feature, decide all/mixed/none for the master toggle.
                const usersWith = users.filter((u) => u.features.includes(f.id)).length;
                const rowAllOn  = usersWith > 0 && usersWith === users.length;
                const rowMixed  = usersWith > 0 && usersWith < users.length;
                const rowBulkPending = pending.has(`* ${f.id}`);
                return (
                  <tr key={f.id}>
                    <th style={labelColStyle} title={f.id}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                        {/* Row-master toggle — flips this feature on/off
                            for every user. Same gold "master" variant as
                            the column header so the two pair visually. */}
                        <Toggle
                          on={rowAllOn}
                          mixed={rowMixed}
                          disabled={rowBulkPending}
                          onClick={() => toggleFeatureForAllUsers(f.id)}
                          variant="master"
                          title={rowAllOn
                            ? `Revoke "${f.label}" from all users`
                            : `Grant "${f.label}" to all users`}
                        />
                        <span>{f.label}</span>
                        <span style={{ fontSize: '0.62rem', color: 'var(--cm-slate)', marginLeft: 'auto' }}>
                          {usersWith}/{users.length}
                        </span>
                      </span>
                    </th>
                    {users.map((u) => {
                      const checked = u.features.includes(f.id);
                      const pendingKey = `${u.email} ${f.id}`;
                      const isPending = pending.has(pendingKey) || rowBulkPending || pending.has(`${u.email} *`);
                      return (
                        <td
                          key={u.email}
                          style={{
                            padding: '0.35rem 0.4rem',
                            borderBottom: '1px solid var(--rule, #2a2a2a)',
                            textAlign: 'center',
                            background: u.is_owner ? 'rgba(212,175,55,0.04)' : undefined,
                          }}
                        >
                          <Toggle
                            on={checked}
                            disabled={isPending}
                            onClick={() => toggleFeature(u, f.id, !checked)}
                            variant="cell"
                            title={`${displayName(u)} · ${f.label} — ${checked ? 'ON' : 'OFF'}`}
                          />
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Mobile: single-user editor (the matrix can't fit a phone) ─────── */}
      {catalog && users && isMobile && (() => {
        const activeEmail = mobileUserEmail ?? users[0]?.email ?? null;
        const u = users.find((x) => x.email === activeEmail) ?? users[0];
        if (!u) return null;
        return (
          <div>
            {/* User picker — horizontally scrollable chips. */}
            <div style={{
              display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 6,
              marginBottom: '0.6rem', WebkitOverflowScrolling: 'touch',
            }}>
              {users.map((x) => {
                const on = x.email === u.email;
                return (
                  <button
                    key={x.email}
                    type="button"
                    onClick={() => setMobileUserEmail(x.email)}
                    style={{
                      flex: '0 0 auto', padding: '5px 12px', borderRadius: 999,
                      fontSize: '0.8rem', fontWeight: on ? 700 : 500, cursor: 'pointer',
                      whiteSpace: 'nowrap',
                      background: on ? 'var(--ink, #eee)' : 'var(--bg-raised, #181818)',
                      color: on ? 'var(--bg, #111)' : 'var(--ink, #ddd)',
                      border: `1px solid ${x.is_owner ? 'var(--cm-amber, #d4af37)' : 'var(--rule, #333)'}`,
                    }}
                  >
                    {displayName(x)}{x.is_owner ? ' ★' : ''}
                  </button>
                );
              })}
            </div>

            {/* Selected user header + reset. */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              gap: 8, padding: '0.5rem 0.7rem', marginBottom: '0.5rem',
              border: '1px solid var(--rule, #333)', borderRadius: 6,
              background: u.is_owner ? 'rgba(212,175,55,0.06)' : 'var(--bg-raised, #181818)',
            }}>
              <div>
                <div style={{ fontWeight: 700 }}>{displayName(u)}{u.is_owner ? ' ★ owner' : ''}</div>
                <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)' }}>
                  {u.features.length}/{catalog.length} features · {u.email}
                </div>
              </div>
              <button
                type="button"
                onClick={() => resetUser(u)}
                style={{
                  flex: '0 0 auto', padding: '4px 10px', fontSize: '0.74rem', cursor: 'pointer',
                  background: 'none', color: 'var(--cm-slate)',
                  border: '1px solid var(--rule, #444)', borderRadius: 6,
                }}
              >↺ reset</button>
            </div>

            {/* Feature list for the selected user — grouped by section. */}
            <div style={{ border: '1px solid var(--rule, #333)', borderRadius: 6, overflow: 'hidden' }}>
              {rows.map((row, i) => {
                if (row.kind === 'section') {
                  return (
                    <div key={`m-grp-${row.group}-${i}`} style={{
                      padding: '0.4rem 0.7rem', fontSize: '0.62rem', fontWeight: 600,
                      textTransform: 'uppercase', letterSpacing: '0.1em',
                      color: 'var(--cm-slate)', background: 'var(--bg, #0f0f0f)',
                      borderTop: i > 0 ? '1px solid var(--rule, #333)' : undefined,
                    }}>{row.group}</div>
                  );
                }
                const f = row.feature;
                const checked = u.features.includes(f.id);
                const isPending = pending.has(`${u.email} ${f.id}`) || pending.has(`${u.email} *`) || pending.has(`* ${f.id}`);
                return (
                  <div key={`m-${f.id}`} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    gap: 10, padding: '0.55rem 0.7rem',
                    borderTop: '1px solid var(--rule, #222)',
                  }}>
                    <span style={{ fontSize: '0.9rem' }}>{f.label}</span>
                    <Toggle
                      on={checked}
                      disabled={isPending}
                      onClick={() => toggleFeature(u, f.id, !checked)}
                      variant="cell"
                      title={`${displayName(u)} · ${f.label} — ${checked ? 'ON' : 'OFF'}`}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      <p style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: '0.9rem', lineHeight: 1.6 }}>
        <strong>Defaults:</strong> non-owner users start with food, kids, notifications, todos, and glossary on; everything else off.
        Owners (gold-tinted columns) default to all features but you can save overrides — toggling a page off for yourself here will hide it from your nav.
        <br />
        <strong>Lockout note:</strong> /admin/access stays reachable even if you turn off every other feature for yourself, because the admin gate is on your email, not your feature flags. Worst case, come back here and toggle features back on.
        <br />
        <strong>Data scoping caveat:</strong> granting a friend access to /food or /kids today means they see your family's shared content (data is partitioned under the primary owner). Per-user scoping for friends is a separate change.
      </p>
    </div>
  );
}
