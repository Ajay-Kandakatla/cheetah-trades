/* AllowlistManager — the owner's self-service control for WHO CAN SIGN IN.
 *
 * Lives at the top of the /admin/access page. Distinct from the feature
 * matrix below it: the matrix grants PAGES to people already allowed in;
 * this panel controls the oauth2-proxy front door (backend/oauth2-emails.txt).
 *
 * Add a brand-new Gmail here → they can reach the sign-in screen and log in.
 * Remove one → they're locked out at the door. Owner emails are protected
 * (the Remove button is disabled) so you can't lock yourself out.
 *
 * Reload caveat surfaced honestly: oauth2-proxy does NOT hot-reload the file,
 * so after any change we show the exact restart command. Until that runs, the
 * edit is saved but the sign-in gate still uses the old list.
 *
 * Endpoints (all admin-gated, 404 to anyone else):
 *   GET    /admin/access/allowlist
 *   POST   /admin/access/allowlist          body { email }
 *   DELETE /admin/access/allowlist/{email}
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

type AllowEntry = {
  email: string;
  protected: boolean;
  is_owner: boolean;
  has_saved: boolean;
};

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function AllowlistManager({ onChanged }: { onChanged?: () => void }) {
  const [entries, setEntries] = useState<AllowEntry[] | null>(null);
  const [restartCmd, setRestartCmd] = useState<string>(
    'docker compose --profile oauth restart oauth2-proxy',
  );
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [pendingRestart, setPendingRestart] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = () => {
    fetch(`${API}/admin/access/allowlist`)
      .then((r) => {
        if (r.status === 404) return null; // not admin — page already guards this
        if (!r.ok) throw new Error(`allowlist ${r.status}`);
        return r.json();
      })
      .then((j) => {
        if (!j) return;
        setEntries(j.emails || []);
        if (j.restart_cmd) setRestartCmd(j.restart_cmd);
      })
      .catch((e) => setErr(String(e?.message || e)));
  };

  useEffect(load, []);

  const add = async () => {
    const email = draft.trim().toLowerCase();
    if (!email) return;
    if (!EMAIL_RE.test(email)) { setErr('That doesn’t look like a valid email address.'); return; }
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${API}/admin/access/allowlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      setDraft('');
      if (j.needs_restart) setPendingRestart(true);
      load();
      onChanged?.();
    } catch (e: any) {
      setErr(`Couldn’t add ${email}: ${e?.message || e}`);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (email: string) => {
    if (!confirm(`Remove ${email} from sign-in? They'll be locked out at the door (their saved feature grants are kept in case you re-add them).`)) return;
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${API}/admin/access/allowlist/${encodeURIComponent(email)}`, { method: 'DELETE' });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      if (j.needs_restart) setPendingRestart(true);
      load();
      onChanged?.();
    } catch (e: any) {
      setErr(`Couldn’t remove ${email}: ${e?.message || e}`);
    } finally {
      setBusy(false);
    }
  };

  const copyCmd = async () => {
    try {
      await navigator.clipboard.writeText(restartCmd);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch { /* clipboard blocked — the command is visible to copy by hand */ }
  };

  return (
    <section
      style={{
        marginBottom: '1.1rem',
        border: '1px solid var(--rule, #333)',
        borderRadius: 8,
        background: 'var(--bg-raised, #181818)',
        padding: '0.85rem 1rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 700 }}>Approved sign-in emails</h2>
        <span style={{ fontSize: '0.72rem', color: 'var(--cm-slate)' }}>
          who can log in at all — the oauth2 front door
        </span>
        {entries && (
          <span style={{ marginLeft: 'auto', fontSize: '0.72rem', color: 'var(--cm-slate)' }}>
            {entries.length} {entries.length === 1 ? 'address' : 'addresses'}
          </span>
        )}
      </div>

      {/* Add row */}
      <div style={{ display: 'flex', gap: 8, marginTop: '0.7rem', flexWrap: 'wrap' }}>
        <input
          type="email"
          inputMode="email"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          placeholder="name@gmail.com"
          value={draft}
          disabled={busy}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') add(); }}
          style={{
            flex: '1 1 240px', minWidth: 0,
            padding: '0.5rem 0.7rem',
            background: 'var(--bg, #0f0f0f)',
            border: '1px solid var(--rule, #444)',
            borderRadius: 6,
            color: 'var(--ink, #eee)',
            fontSize: '0.9rem',
          }}
        />
        <button
          type="button"
          onClick={add}
          disabled={busy || !draft.trim()}
          style={{
            flex: '0 0 auto', padding: '0.5rem 1rem',
            background: draft.trim() ? 'var(--cm-amber, #d4af37)' : 'var(--bg, #0f0f0f)',
            color: draft.trim() ? '#161616' : 'var(--cm-slate)',
            border: '1px solid var(--cm-amber, #d4af37)',
            borderRadius: 6, fontWeight: 700, fontSize: '0.86rem',
            cursor: busy || !draft.trim() ? 'not-allowed' : 'pointer',
            opacity: busy ? 0.6 : 1,
          }}
        >
          {busy ? '…' : '+ Add'}
        </button>
      </div>

      {err && (
        <div style={{
          marginTop: '0.6rem', padding: '0.4rem 0.7rem',
          background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 4, color: 'var(--negative, #ef4444)', fontSize: '0.82rem',
        }}>
          {err} · <button onClick={() => setErr(null)} style={{ background: 'none', border: 0, color: 'inherit', textDecoration: 'underline', cursor: 'pointer' }}>dismiss</button>
        </div>
      )}

      {/* Pending-restart banner */}
      {pendingRestart && (
        <div style={{
          marginTop: '0.6rem', padding: '0.55rem 0.75rem',
          background: 'rgba(217,119,6,0.10)', border: '1px solid rgba(217,119,6,0.45)',
          borderRadius: 6, fontSize: '0.82rem', color: 'var(--ink, #eee)',
        }}>
          <strong style={{ color: 'var(--warn, #d97706)' }}>⚠ Not live yet.</strong>{' '}
          Saved to the allowlist, but oauth2-proxy must re-read it. Run this on the host:
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
            <code style={{
              flex: '1 1 auto', minWidth: 0, padding: '0.35rem 0.55rem',
              background: 'var(--bg, #0f0f0f)', border: '1px solid var(--rule, #444)',
              borderRadius: 4, fontSize: '0.8rem', overflowX: 'auto', whiteSpace: 'nowrap',
            }}>{restartCmd}</code>
            <button
              type="button"
              onClick={copyCmd}
              style={{
                flex: '0 0 auto', padding: '0.35rem 0.7rem', fontSize: '0.76rem',
                background: 'none', color: 'var(--ink, #ddd)',
                border: '1px solid var(--rule, #555)', borderRadius: 4, cursor: 'pointer',
              }}
            >{copied ? '✓ copied' : 'copy'}</button>
            <button
              type="button"
              onClick={() => setPendingRestart(false)}
              style={{
                flex: '0 0 auto', padding: '0.35rem 0.7rem', fontSize: '0.76rem',
                background: 'none', color: 'var(--cm-slate)',
                border: '1px solid var(--rule, #444)', borderRadius: 4, cursor: 'pointer',
              }}
              title="Hide this note once you've restarted"
            >I’ve run it</button>
          </div>
        </div>
      )}

      {/* List */}
      <div style={{ marginTop: '0.8rem', display: 'flex', flexDirection: 'column', gap: 4 }}>
        {entries === null && <div style={{ color: 'var(--cm-slate)', fontSize: '0.84rem' }}>Loading…</div>}
        {entries && entries.length === 0 && (
          <div style={{ color: 'var(--cm-slate)', fontSize: '0.84rem' }}>No emails on the allowlist.</div>
        )}
        {entries && entries.map((e) => (
          <div
            key={e.email}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '0.4rem 0.6rem',
              border: '1px solid var(--rule, #2a2a2a)',
              borderRadius: 6,
              background: e.is_owner ? 'rgba(212,175,55,0.05)' : 'var(--bg, #0f0f0f)',
            }}
          >
            <span style={{ fontSize: '0.88rem', wordBreak: 'break-all' }}>{e.email}</span>
            {e.is_owner && (
              <span style={{ fontSize: '0.64rem', color: 'var(--warn, #d97706)', fontWeight: 700, letterSpacing: '0.04em' }}>OWNER</span>
            )}
            {!e.is_owner && e.has_saved && (
              <span style={{ fontSize: '0.62rem', color: 'var(--cm-slate)' }} title="Has saved per-user feature grants below">· custom access</span>
            )}
            <button
              type="button"
              onClick={() => remove(e.email)}
              disabled={e.protected || busy}
              title={e.protected ? 'Owner email — protected from removal' : `Remove ${e.email} from sign-in`}
              style={{
                marginLeft: 'auto', flex: '0 0 auto',
                padding: '0.25rem 0.6rem', fontSize: '0.74rem',
                background: 'none',
                color: e.protected ? 'var(--cm-slate)' : 'var(--negative, #ef4444)',
                border: `1px solid ${e.protected ? 'var(--rule, #333)' : 'rgba(239,68,68,0.4)'}`,
                borderRadius: 4,
                cursor: e.protected || busy ? 'not-allowed' : 'pointer',
                opacity: e.protected ? 0.5 : 1,
              }}
            >
              {e.protected ? 'protected' : 'remove'}
            </button>
          </div>
        ))}
      </div>

      <p style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: '0.7rem', lineHeight: 1.6 }}>
        Adding an email only lets the person <em>sign in</em> — by default they land on the minimal feature set.
        Grant them specific pages in the matrix below. Removing an email locks them out at the door but keeps
        their saved page grants, so re-adding them later restores their access.
      </p>
    </section>
  );
}
