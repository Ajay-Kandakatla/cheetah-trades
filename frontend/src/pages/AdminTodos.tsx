/* AdminTodos — admin-only page for adding todos to another user's list.
 *
 * Use case: Ajay sends a todo to Vineetha's phone with one tap, with an
 * optional due date and reminder time. The recipient gets a push the
 * moment it's submitted (assuming they have a registered device and
 * haven't disabled the `todo_reminder` category).
 *
 * Backend gate: /admin/todos and /admin/todos/recipients are both
 * stealth-404'd for non-admins. The frontend hides the entry in the
 * Profile dropdown too, but the backend is the real gate.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { useCurrentUser } from '../hooks/useUser';

type CreatedTodo = {
  _id:        string;
  user_email: string;
  text:       string;
  created_at: number;
  due_at:     number | null;
  notify_at:  number | null;
  important:  boolean;
};

/** Friendly display name for a recipient email — strips the @gmail.com
 *  tail and Title-Cases the local part. Only used for UI labels; the
 *  email itself is what gets POSTed. */
function recipientLabel(email: string): string {
  const local = email.split('@')[0] || email;
  // 'gandurivineetha' → 'Vineetha' if we can tell what to keep.
  // Special-cases first because the heuristic below over-applies.
  const known: Record<string, string> = {
    'gandurivineetha':    'Vineetha',
    'ajaykandakatla':     'Ajay',
  };
  if (known[local.toLowerCase()]) return known[local.toLowerCase()];
  return local.charAt(0).toUpperCase() + local.slice(1);
}

/** Convert a local-time <input type="datetime-local"> value into an
 *  epoch-seconds integer that the backend expects. Empty input → null. */
function dtLocalToEpoch(s: string): number | null {
  if (!s) return null;
  const ms = new Date(s).getTime();
  if (Number.isNaN(ms)) return null;
  return Math.floor(ms / 1000);
}

export default function AdminTodosPage() {
  const { user } = useCurrentUser();
  const isAdmin = (user?.email || '').toLowerCase() === 'ajaykandakatla@gmail.com';

  const [recipients,  setRecipients]  = useState<string[]>([]);
  const [recipient,   setRecipient]   = useState<string>('');
  const [text,        setText]        = useState('');
  const [dueLocal,    setDueLocal]    = useState('');     // <input type="datetime-local">
  const [notifyLocal, setNotifyLocal] = useState('');
  const [important,   setImportant]   = useState(false);

  const [busy,        setBusy]        = useState(false);
  const [err,         setErr]         = useState<string | null>(null);
  const [sent,        setSent]        = useState<CreatedTodo[]>([]);
  const [accessDenied, setAccessDenied] = useState(false);

  // Load recipient allowlist. 404 here means non-admin — flip the
  // access-denied flag so the body renders the "Not Found" stealth state
  // (matching the backend's stealth gate).
  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/admin/todos/recipients`)
      .then(async (r) => {
        if (r.status === 404) {
          if (!cancelled) setAccessDenied(true);
          return null;
        }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((j) => {
        if (cancelled || !j) return;
        const list: string[] = j.recipients || [];
        // Hide the admin's own email — they don't need this UI to ping
        // themselves; the regular /todos page handles that.
        const filtered = list.filter(e => e.toLowerCase() !== (user?.email || '').toLowerCase());
        setRecipients(filtered);
        if (filtered.length && !recipient) setRecipient(filtered[0]);
      })
      .catch(() => { if (!cancelled) setErr('Failed to load recipient list.'); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.email]);

  // Stealth render — same shape the backend uses.
  if (accessDenied || (user && !isAdmin)) {
    return (
      <div style={{ padding: '4rem 1.5rem', textAlign: 'center', color: 'var(--cm-slate)' }}>
        <h1 style={{ fontSize: '1.4rem', fontFamily: 'serif', fontStyle: 'italic' }}>404</h1>
        <p>Not found.</p>
      </div>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!recipient) { setErr('Pick a recipient.'); return; }
    if (!text.trim()) { setErr('Add some text.'); return; }
    setBusy(true);
    try {
      const r = await fetch(`${API}/admin/todos`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          user_email: recipient,
          text:       text.trim(),
          due_at:     dtLocalToEpoch(dueLocal),
          notify_at:  dtLocalToEpoch(notifyLocal),
          important,
        }),
      });
      const j = await r.json();
      if (!r.ok || !j.ok) {
        setErr(j.error || `HTTP ${r.status}`);
        return;
      }
      // Prepend the new todo to our local "recently sent" list. Cap at
      // 10 so the list stays scannable; older entries roll off — they
      // still exist on the recipient's /todos page if needed.
      setSent((prev) => [j.todo as CreatedTodo, ...prev].slice(0, 10));
      // Reset the form but keep the recipient selected — typical flow
      // is sending several todos to the same person in a row.
      setText('');
      setDueLocal('');
      setNotifyLocal('');
      setImportant(false);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="cm-page" style={{ padding: '1.2rem 1.4rem', maxWidth: 720, margin: '0 auto' }}>
      <header className="cm-pagehead" style={{ marginBottom: '1.2rem' }}>
        <div className="eyebrow">Admin · cross-user todos</div>
        <h1 className="display cm-pagehead__title" style={{ margin: '0.25rem 0 0' }}>
          Add a todo {recipient && <span style={{ color: 'var(--cm-slate)', fontSize: '0.7em', marginLeft: '0.5rem' }}>for {recipientLabel(recipient)}</span>}
        </h1>
        <p className="lede" style={{ marginTop: '0.4rem' }}>
          Drops a todo onto the selected user's list and pushes a
          notification to their phone (if they have web push set up and
          haven't disabled the todo_reminder category).
        </p>
      </header>

      <form onSubmit={submit} style={{ display: 'grid', gap: '0.9rem', marginBottom: '1.6rem' }}>
        {/* Recipient picker — only one option today (Vineetha), but the
            dropdown stays in case we expand HOUSE_OWNER_EMAILS later. */}
        <label style={{ display: 'grid', gap: '0.25rem', fontSize: '0.8rem' }}>
          <span className="eyebrow">Recipient</span>
          <select
            value={recipient}
            onChange={(e) => setRecipient(e.target.value)}
            style={{
              padding: '0.55rem 0.7rem',
              background: 'var(--bg-raised, #181818)',
              color: 'inherit',
              border: '1px solid var(--rule, #444)',
              borderRadius: 4,
              fontFamily: 'inherit',
              fontSize: '0.92rem',
            }}
          >
            {recipients.length === 0 && <option value="">— loading —</option>}
            {recipients.map((r) => (
              <option key={r} value={r}>{recipientLabel(r)} · {r}</option>
            ))}
          </select>
        </label>

        <label style={{ display: 'grid', gap: '0.25rem', fontSize: '0.8rem' }}>
          <span className="eyebrow">Todo text</span>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            maxLength={300}
            placeholder="e.g., Pick up dry cleaning before 5pm"
            style={{
              padding: '0.6rem 0.75rem',
              background: 'var(--bg-raised, #181818)',
              color: 'inherit',
              border: '1px solid var(--rule, #444)',
              borderRadius: 4,
              fontFamily: 'inherit',
              fontSize: '0.95rem',
              resize: 'vertical',
              minHeight: 72,
            }}
          />
          <span style={{ fontSize: '0.66rem', color: 'var(--cm-slate)' }}>
            {text.length} / 300
          </span>
        </label>

        {/* Optional scheduling block — datetime-local renders a native
            picker on mobile (great UX on iPhone). Both inputs are
            optional; leave blank for "no due date" / "no reminder". */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.7rem' }}>
          <label style={{ display: 'grid', gap: '0.25rem', fontSize: '0.8rem' }}>
            <span className="eyebrow">Due (optional)</span>
            <input
              type="datetime-local"
              value={dueLocal}
              onChange={(e) => setDueLocal(e.target.value)}
              style={{
                padding: '0.5rem 0.65rem',
                background: 'var(--bg-raised, #181818)',
                color: 'inherit',
                border: '1px solid var(--rule, #444)',
                borderRadius: 4,
                fontFamily: 'inherit',
                fontSize: '0.9rem',
              }}
            />
          </label>
          <label style={{ display: 'grid', gap: '0.25rem', fontSize: '0.8rem' }}>
            <span className="eyebrow">Reminder push at (optional)</span>
            <input
              type="datetime-local"
              value={notifyLocal}
              onChange={(e) => setNotifyLocal(e.target.value)}
              style={{
                padding: '0.5rem 0.65rem',
                background: 'var(--bg-raised, #181818)',
                color: 'inherit',
                border: '1px solid var(--rule, #444)',
                borderRadius: 4,
                fontFamily: 'inherit',
                fontSize: '0.9rem',
              }}
            />
          </label>
        </div>

        <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', fontSize: '0.86rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={important}
            onChange={(e) => setImportant(e.target.checked)}
            style={{ width: 18, height: 18 }}
          />
          Mark as important (pinned to top of their list + included in Morning Brief)
        </label>

        {err && (
          <div style={{
            padding: '0.5rem 0.7rem',
            border: '1px solid rgba(239,68,68,0.4)',
            background: 'rgba(239,68,68,0.08)',
            color: 'var(--negative)',
            borderRadius: 4,
            fontSize: '0.84rem',
          }}>{err}</div>
        )}

        <div>
          <button
            type="submit"
            disabled={busy || !recipient || !text.trim()}
            className="sepa-btn sepa-btn--primary"
            style={{ minHeight: 44, padding: '0.7rem 1.4rem', fontSize: '0.95rem' }}
          >
            {busy
              ? '…sending'
              : recipient ? `📩 Send to ${recipientLabel(recipient)}` : 'Send'}
          </button>
        </div>
      </form>

      {/* Recently sent — local-only ledger so the admin can see what
          they've fired off this session. Backend doesn't expose a
          per-admin audit feed (yet); this is a UX confirmation, not
          authoritative state. */}
      {sent.length > 0 && (
        <section>
          <div className="eyebrow" style={{ marginBottom: '0.5rem' }}>Sent this session ({sent.length})</div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '0.5rem' }}>
            {sent.map((t) => (
              <li
                key={t._id}
                style={{
                  padding: '0.55rem 0.7rem',
                  border: '1px solid var(--rule, #333)',
                  borderRadius: 4,
                  background: 'rgba(255,255,255,0.02)',
                }}
              >
                <div style={{ fontSize: '0.92rem' }}>
                  {t.important && <span style={{ color: 'var(--warn, #d97706)', marginRight: '0.4rem' }}>★</span>}
                  {t.text}
                </div>
                <div style={{ fontSize: '0.68rem', color: 'var(--cm-slate)', marginTop: '0.25rem', display: 'flex', gap: '0.7rem', flexWrap: 'wrap' }}>
                  <span>→ {recipientLabel(t.user_email)}</span>
                  {t.due_at && <span>due {new Date(t.due_at * 1000).toLocaleString()}</span>}
                  {t.notify_at && <span>ping {new Date(t.notify_at * 1000).toLocaleString()}</span>}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
