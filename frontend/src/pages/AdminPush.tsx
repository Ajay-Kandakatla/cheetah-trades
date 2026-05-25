/* AdminPush — admin-only "who has push set up for what" page.
 *
 * Read-only view. Renders one section per user with:
 *   - Device list (web / iPhone PWA / native macOS app)
 *   - Per-device label and pref toggles (informational only)
 *   - Category summary chips so you can see at a glance which
 *     notification kinds will actually deliver
 *
 * No bulk-edit UI here — to change anything, the user themself opens
 * /notifications on their device. This page exists for debugging
 * "Vineetha says she's not getting alerts" type questions — first
 * stop: does she even have a device subscribed?
 *
 * Stealth-gated 404 to non-admins (matches the backend).
 */
import { useEffect, useMemo, useState } from 'react';
import { API } from '../lib/apiBase';
import { useCurrentUser } from '../hooks/useUser';

type Device = {
  kind:           'web' | 'mac' | string;
  label:          string;
  endpoint_short: string;
  device_id?:     string | null;
  created_at?:    number;
  updated_at?:    number;
  prefs:          Record<string, boolean | string | undefined>;
};

type UserRow = {
  email:            string;
  /** Server-resolved display name (DISPLAY_NAME_OVERRIDES_JSON →
   *  Google profile → title-cased handle). Always populated by
   *  /admin/push/users — keeps personal-nickname overrides out
   *  of the JS bundle. */
  display_name:     string;
  device_count:     number;
  devices:          Device[];
  category_summary: Record<string, boolean>;
};

type Response = {
  users:           UserRow[];
  categories:      string[];
  store_available: boolean;
};

type AuditRow = {
  kind:           string;
  user_email:     string;
  label:          string;
  endpoint_short: string;
  device_id?:     string | null;
  created_at?:    number;
};

type Audit = {
  missing_user_email: AuditRow[];
  stale_user_email:   AuditRow[];
  allowlist_size?:    number;
  store_available:    boolean;
};

/** Friendly display label for category keys (matches the constants in
 *  Notifications.tsx — kept inline so the admin page stays self-contained
 *  and doesn't fight with that page's category list during code-split). */
const CATEGORY_LABELS: Record<string, string> = {
  sepa_new_candidate:        '🎯 New SEPA candidate',
  volume_breakout:           '🚀 Volume breakout',
  rising_momentum:           '📈 Rising momentum',
  watchlist_breakout:        '⭐ Watchlist breakout',
  juggernaut_watchlist:      '💪 Juggernaut watchlist',
  stage_breakdown:           '⚠️ Stage breakdown',
  watchlist_stage_breakdown: '🛑 Stage breakdown (watchlist)',
  price_alert:               '🔔 Price alerts',
  position_alert:            '💼 Position alerts',
  morning_brief:             '🌅 Morning brief',
  product_launch:            '🚀 Product launches',
  todo_reminder:             '📌 Todo reminders',
  todo_daily_digest:         '📋 Todo daily digest',
  user_signin:               '👋 New user sign-in',
};

/** Friendly display name with a defensive fallback. Backend's
 *  /admin/push/users now sends every row with a server-resolved
 *  ``display_name`` (DISPLAY_NAME_OVERRIDES_JSON → Google profile →
 *  title-cased handle). This helper falls back to the title-cased
 *  handle only if the row arrives without that field — a deploy
 *  transition guard. The personal-name override map that used to live
 *  here moved server-side to keep personal Gmail addresses out of the
 *  JS bundle. */
function displayName(row: { email: string; display_name?: string }): string {
  if (row.display_name && row.display_name.trim()) return row.display_name;
  const local = row.email.split('@')[0] || row.email;
  return local
    .split(/[._]/)
    .map((s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : s)
    .join(' ');
}

function categoryLabel(key: string): string {
  return CATEGORY_LABELS[key] || key;
}

function fmtTime(epoch?: number): string {
  if (!epoch) return '—';
  return new Date(epoch * 1000).toLocaleString();
}

export default function AdminPushPage() {
  const { user } = useCurrentUser();
  const isAdmin = !!user?.is_admin;

  const [data,  setData]  = useState<Response | null>(null);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [err,   setErr]   = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState<Record<string, 'idle' | 'sending' | 'ok' | 'err'>>({});
  const [accessDenied, setAccessDenied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // Fetch the user list + the audit in parallel — both are cheap
    // and informative on first paint.
    Promise.all([
      fetch(`${API}/admin/push/users`).then(async (r) => {
        if (r.status === 404) { if (!cancelled) setAccessDenied(true); return null; }
        if (!r.ok) throw new Error(`users HTTP ${r.status}`);
        return r.json() as Promise<Response>;
      }),
      fetch(`${API}/admin/push/audit`).then(async (r) => {
        if (r.status === 404) return null;
        if (!r.ok) throw new Error(`audit HTTP ${r.status}`);
        return r.json() as Promise<Audit>;
      }),
    ])
      .then(([u, a]) => {
        if (cancelled) return;
        if (u) setData(u);
        if (a) setAudit(a);
      })
      .catch((e) => { if (!cancelled) setErr(String(e?.message || e)); });
    return () => { cancelled = true; };
  }, []);

  /** Send a test push to ONE user's devices.
   *
   *  This is the primary affordance for "convince myself that scoping
   *  works before I trust intimate content." If the test lands on the
   *  selected user's phone and ONLY their phone, the scoping path is
   *  proven end-to-end. */
  const sendTest = async (target: string) => {
    setTestStatus((s) => ({ ...s, [target]: 'sending' }));
    try {
      const r = await fetch(`${API}/admin/push/test`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          user_email: target,
          // Deliberately neutral text so a curious admin click doesn't
          // ship anything private through the test path.
          title: '🔬 Pounce scoping test',
          body:  'If you see this only on YOUR devices, per-user push is working.',
        }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) {
        setErr(`Test send failed for ${target}: ${j.error || r.status}`);
        setTestStatus((s) => ({ ...s, [target]: 'err' }));
        return;
      }
      setTestStatus((s) => ({ ...s, [target]: 'ok' }));
      // Clear the 'ok' state after 4s so the row goes back to idle.
      setTimeout(() => {
        setTestStatus((s) => {
          const next = { ...s };
          if (next[target] === 'ok') delete next[target];
          return next;
        });
      }, 4000);
    } catch (e: any) {
      setErr(`Test send error for ${target}: ${e?.message || e}`);
      setTestStatus((s) => ({ ...s, [target]: 'err' }));
    }
  };

  // Sort users: those with at least one device first (most useful to
  // see) so the "missing setup" rows surface at the bottom.
  const sortedUsers = useMemo<UserRow[]>(() => {
    if (!data?.users) return [];
    return [...data.users].sort((a, b) => {
      if (a.device_count !== b.device_count) return b.device_count - a.device_count;
      return a.email.localeCompare(b.email);
    });
  }, [data]);

  if (accessDenied || (user && !isAdmin)) {
    return (
      <div style={{ padding: '4rem 1.5rem', textAlign: 'center', color: 'var(--cm-slate)' }}>
        <h1 style={{ fontSize: '1.4rem', fontFamily: 'serif', fontStyle: 'italic' }}>404</h1>
        <p>Not found.</p>
      </div>
    );
  }

  const totalSubscribed = sortedUsers.filter((u) => u.device_count > 0).length;
  const totalUsers = sortedUsers.length;

  return (
    <div className="cm-page" style={{ padding: '1.2rem 1.4rem', maxWidth: 1100, margin: '0 auto' }}>
      <header className="cm-pagehead" style={{ marginBottom: '1rem' }}>
        <div className="eyebrow">№ Admin · push subscriptions</div>
        <h1 className="display cm-pagehead__title" style={{ margin: '0.25rem 0 0' }}>
          Who has push set up
        </h1>
        <p className="lede" style={{ marginTop: '0.4rem' }}>
          Read-only audit. <strong>{totalSubscribed}</strong> of <strong>{totalUsers}</strong> users
          have at least one device subscribed. Tap into each row to see which categories will
          actually deliver to which device.
        </p>
      </header>

      {err && (
        <div style={{
          padding: '0.5rem 0.8rem', marginBottom: '0.9rem',
          background: 'rgba(239,68,68,0.08)',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 4, color: 'var(--negative)', fontSize: '0.85rem',
        }}>
          {err}
        </div>
      )}

      {/* Audit banner — surface push_subscriptions rows that COULD mis-
          route a user-scoped notification (empty user_email = silent
          black-hole; user_email not in OAuth allowlist = stale device).
          Hidden when both lists are empty so the banner doesn't add
          noise on clean systems. */}
      {audit && (audit.missing_user_email.length > 0 || audit.stale_user_email.length > 0) && (
        <div style={{
          padding: '0.65rem 0.85rem', marginBottom: '0.9rem',
          background: 'rgba(217,119,6,0.08)',
          border: '1px solid rgba(217,119,6,0.35)',
          borderRadius: 5, color: 'var(--ink, inherit)',
          fontSize: '0.84rem',
        }}>
          <div style={{ fontWeight: 700, color: 'var(--warn, #d97706)', marginBottom: '0.3rem' }}>
            ⚠ Subscription audit
          </div>
          {audit.missing_user_email.length > 0 && (
            <div style={{ marginBottom: audit.stale_user_email.length > 0 ? '0.4rem' : 0 }}>
              <strong>{audit.missing_user_email.length}</strong> subscription
              {audit.missing_user_email.length === 1 ? ' has' : 's have'} no <code>user_email</code> —
              they're a silent black-hole for per-user pushes. Drop via Mongo
              (<code>db.push_subscriptions.deleteOne({"{"}endpoint: …{"}"})</code>) or have the device re-subscribe.
              <details style={{ marginTop: '0.3rem' }}>
                <summary style={{ cursor: 'pointer', fontSize: '0.74rem', color: 'var(--cm-slate)' }}>show rows</summary>
                <ul style={{ margin: '0.3rem 0 0', paddingLeft: '1.2rem', fontSize: '0.74rem', color: 'var(--cm-slate)' }}>
                  {audit.missing_user_email.map((r, i) => (
                    <li key={i}>{r.kind} · {r.label || '(no label)'} · …{r.endpoint_short || r.device_id}</li>
                  ))}
                </ul>
              </details>
            </div>
          )}
          {audit.stale_user_email.length > 0 && (
            <div>
              <strong>{audit.stale_user_email.length}</strong> subscription
              {audit.stale_user_email.length === 1 ? ' is' : 's are'} tied to <code>user_email</code>
              {' '}not in the OAuth allowlist — they could still receive system-wide
              broadcasts. Review and drop if obsolete.
              <details style={{ marginTop: '0.3rem' }}>
                <summary style={{ cursor: 'pointer', fontSize: '0.74rem', color: 'var(--cm-slate)' }}>show rows</summary>
                <ul style={{ margin: '0.3rem 0 0', paddingLeft: '1.2rem', fontSize: '0.74rem', color: 'var(--cm-slate)' }}>
                  {audit.stale_user_email.map((r, i) => (
                    <li key={i}>{r.user_email} · {r.kind} · {r.label || '(no label)'} · …{r.endpoint_short || r.device_id}</li>
                  ))}
                </ul>
              </details>
            </div>
          )}
        </div>
      )}

      {audit && audit.missing_user_email.length === 0 && audit.stale_user_email.length === 0 && (
        <div style={{
          padding: '0.5rem 0.8rem', marginBottom: '0.9rem',
          background: 'rgba(16,185,129,0.06)',
          border: '1px solid rgba(16,185,129,0.25)',
          borderRadius: 4, color: 'var(--positive)', fontSize: '0.78rem',
        }}>
          ✓ Subscription audit clean — every device has a valid <code>user_email</code> in the OAuth allowlist. Per-user scoping should route correctly.
        </div>
      )}

      {!data && !err && <div style={{ color: 'var(--cm-slate)' }}>Loading…</div>}

      {data && data.users.length === 0 && (
        <div style={{ color: 'var(--cm-slate)', textAlign: 'center', padding: '2rem' }}>
          No users found.
        </div>
      )}

      <div style={{ display: 'grid', gap: '0.9rem' }}>
        {sortedUsers.map((u) => (
          <section
            key={u.email}
            style={{
              border: '1px solid var(--rule, #333)',
              borderRadius: 6,
              background: 'var(--bg-raised, #181818)',
              padding: '0.85rem 1rem',
            }}
          >
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.55rem' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: '1rem' }}>{displayName(u)}</div>
                <div style={{ fontSize: '0.74rem', color: 'var(--cm-slate)' }}>{u.email}</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <div style={{ fontSize: '0.78rem', color: u.device_count > 0 ? 'var(--positive)' : 'var(--cm-slate)' }}>
                  {u.device_count === 0 ? '◯ no devices subscribed'
                    : `● ${u.device_count} device${u.device_count === 1 ? '' : 's'}`}
                </div>
                {/* Test push — fires a NEUTRAL "scoping test" message at
                    this user's devices only. Lets the admin prove that
                    private content (love notes, household pings) will
                    route correctly before trusting it. The endpoint
                    rejects custom title/body for this button so a
                    misclick can't fire anything embarrassing. */}
                {u.device_count > 0 && (() => {
                  const st = testStatus[u.email] || 'idle';
                  const label =
                    st === 'sending' ? '…sending' :
                    st === 'ok'      ? '✓ sent' :
                    st === 'err'     ? '× failed' :
                                       '🔬 Test push';
                  return (
                    <button
                      onClick={() => sendTest(u.email)}
                      disabled={st === 'sending'}
                      style={{
                        background: st === 'ok' ? 'rgba(16,185,129,0.1)' :
                                    st === 'err' ? 'rgba(239,68,68,0.1)' :
                                    'transparent',
                        color: st === 'ok' ? 'var(--positive)' :
                               st === 'err' ? 'var(--negative)' :
                               'var(--ink, inherit)',
                        border: '1px solid var(--rule, #555)',
                        padding: '3px 10px',
                        borderRadius: 4,
                        cursor: st === 'sending' ? 'wait' : 'pointer',
                        fontSize: '0.74rem',
                        fontFamily: 'inherit',
                      }}
                      title={`Fire a neutral test push at ${displayName(u)}'s devices only — should NOT land on any other user's phone.`}
                    >
                      {label}
                    </button>
                  );
                })()}
              </div>
            </header>

            {/* Device list — one card per subscription */}
            {u.devices.length > 0 ? (
              <div style={{ display: 'grid', gap: '0.5rem', marginBottom: '0.7rem' }}>
                {u.devices.map((d, i) => (
                  <div
                    key={`${d.endpoint_short}-${i}`}
                    style={{
                      padding: '0.45rem 0.65rem',
                      border: '1px solid var(--rule, #2a2a2a)',
                      borderRadius: 4,
                      background: 'rgba(255,255,255,0.02)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <div style={{ fontWeight: 600, fontSize: '0.86rem' }}>
                        <span style={{
                          display: 'inline-block',
                          marginRight: '0.5rem',
                          padding: '1px 6px',
                          fontSize: '0.62rem',
                          borderRadius: 3,
                          background: d.kind === 'mac' ? 'rgba(212,175,55,0.15)' : 'rgba(59,130,246,0.15)',
                          color: d.kind === 'mac' ? 'var(--warn, #d97706)' : '#3b82f6',
                          textTransform: 'uppercase',
                          letterSpacing: '0.06em',
                        }}>
                          {d.kind === 'mac' ? 'macOS' : 'Web / iPhone'}
                        </span>
                        {d.label || <span style={{ color: 'var(--cm-slate)', fontWeight: 400 }}>(no label)</span>}
                      </div>
                      <div className="mono" style={{ fontSize: '0.66rem', color: 'var(--cm-slate)' }}>
                        …{d.endpoint_short || d.device_id || 'unknown'}
                      </div>
                    </div>
                    <div style={{ fontSize: '0.68rem', color: 'var(--cm-slate)', marginTop: '0.3rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                      {d.created_at && <span>created {fmtTime(d.created_at)}</span>}
                      {d.updated_at && d.updated_at !== d.created_at && <span>· updated {fmtTime(d.updated_at)}</span>}
                    </div>
                    {/* Per-device prefs — show only the ones that are ON,
                        so a busy device with 14 toggles doesn't dominate.
                        OFF state is implicit by absence. */}
                    {Object.keys(d.prefs).filter((k) => d.prefs[k] === true).length > 0 ? (
                      <div style={{ marginTop: '0.4rem', display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                        {Object.entries(d.prefs)
                          .filter(([_k, v]) => v === true)
                          .map(([k]) => (
                            <span
                              key={k}
                              title={k}
                              style={{
                                fontSize: '0.66rem',
                                padding: '1px 6px',
                                background: 'rgba(16,185,129,0.1)',
                                color: 'var(--positive)',
                                border: '1px solid rgba(16,185,129,0.3)',
                                borderRadius: 3,
                              }}
                            >
                              {categoryLabel(k)}
                            </span>
                          ))}
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: '0.4rem' }}>
                        All categories OFF on this device.
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: '0.8rem', color: 'var(--cm-slate)', margin: '0 0 0.5rem' }}>
                User is in the OAuth allowlist but has never registered a push device.
                They need to sign in, install the PWA on iPhone (Add to Home Screen),
                and tap "Subscribe this device" on /notifications.
              </p>
            )}

            {/* Aggregated category summary — what will deliver to this
                user on at least one device. Useful when scanning down
                the page: "Who would get the morning brief if it fired?" */}
            {u.device_count > 0 && (
              <details style={{ marginTop: '0.4rem' }}>
                <summary style={{ cursor: 'pointer', fontSize: '0.74rem', color: 'var(--cm-slate)' }}>
                  Category summary (any device on)
                </summary>
                <div style={{ marginTop: '0.4rem', display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                  {Object.entries(u.category_summary).map(([k, v]) => (
                    <span
                      key={k}
                      title={k}
                      style={{
                        fontSize: '0.66rem',
                        padding: '1px 6px',
                        background: v ? 'rgba(16,185,129,0.1)' : 'rgba(120,120,120,0.08)',
                        color:      v ? 'var(--positive)' : 'var(--cm-slate)',
                        border: v ? '1px solid rgba(16,185,129,0.3)' : '1px solid var(--rule, #444)',
                        borderRadius: 3,
                        opacity: v ? 1 : 0.6,
                      }}
                    >
                      {v ? '✓' : '·'} {categoryLabel(k)}
                    </span>
                  ))}
                </div>
              </details>
            )}
          </section>
        ))}
      </div>

      <p style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: '1rem', lineHeight: 1.6 }}>
        Read-only. Users manage their own devices + categories at <code>/notifications</code> when signed in.
        To unsubscribe a stale device on someone else's behalf, you'd need to delete it via
        Mongo directly (<code>db.push_subscriptions.deleteOne({"{"}endpoint: …{"}"})</code>) —
        intentionally not exposed as an admin button to keep the surface small.
      </p>
    </div>
  );
}
