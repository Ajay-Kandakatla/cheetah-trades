/* SignUp — set a password for an allowlisted email.
 *
 *  Used by users who don't want to sign in via Google. Signup is
 *  gated by the same oauth2-emails.txt allowlist as Google sign-in,
 *  so random strangers can't create accounts. On success the backend
 *  auto-logs the user in (sets the session cookie) and we redirect
 *  to /.
 */
import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { API } from '../lib/apiBase';

export default function SignUpPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    const em = email.trim().toLowerCase();
    if (!em || !password) { setErr('Email and password required.'); return; }
    if (password.length < 8) { setErr('Password must be at least 8 characters.'); return; }
    if (password !== confirm) { setErr('Passwords don\'t match.'); return; }
    setBusy(true);
    try {
      const r = await fetch(`${API}/auth/local/signup`, {
        method:      'POST',
        headers:     { 'Content-Type': 'application/json' },
        credentials: 'include',
        body:        JSON.stringify({ email: em, password }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        if (r.status === 403) {
          setErr('That email isn\'t on the allowlist. Ask the admin to invite you first.');
        } else if (r.status === 409) {
          setErr('That email already has a password set. Use sign-in instead.');
        } else if (r.status === 429) {
          setErr('Too many signup attempts. Wait a minute and retry.');
        } else {
          setErr(j.detail || 'Signup failed.');
        }
        return;
      }
      // Auto-login on signup — backend set the cookie, just navigate.
      navigate('/', { replace: true });
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ minHeight: '92vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.2rem' }}>
      <div style={{
        width: '100%', maxWidth: 380,
        padding: '2.2rem 1.8rem 1.6rem',
        background: 'rgba(20, 20, 22, 0.85)',
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: 14,
        boxShadow: '0 20px 60px rgba(0,0,0,0.55)',
        textAlign: 'center',
      }}>
        <div className="eyebrow" style={{ marginBottom: '0.5rem' }}>Pounce · set password</div>
        <h1 style={{
          fontFamily: '"Times New Roman", Georgia, ui-serif, serif',
          fontStyle: 'italic', fontSize: '2.2rem',
          margin: '0 0 0.35rem', color: '#f3e8c8',
        }}>
          Set a password
        </h1>
        <p style={{
          fontFamily: 'ui-monospace, SFMono-Regular, monospace',
          fontSize: '0.72rem', color: '#9a9aa3',
          margin: '0 0 1.4rem',
        }}>
          for your invited email
        </p>

        {err && (
          <div style={{
            padding: '0.5rem 0.7rem',
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 4,
            color: 'var(--negative)',
            fontSize: '0.82rem',
            marginBottom: '0.8rem',
            textAlign: 'left',
          }}>
            {err}
          </div>
        )}

        <form onSubmit={submit} style={{ display: 'grid', gap: '0.65rem', textAlign: 'left' }}>
          <label style={{ display: 'grid', gap: '0.2rem', fontSize: '0.78rem' }}>
            <span className="eyebrow">Email (must be on allowlist)</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              autoFocus
              placeholder="you@example.com"
              style={{
                padding: '0.55rem 0.75rem',
                background: 'var(--bg, #0f0f0f)', color: 'inherit',
                border: '1px solid var(--rule, #444)', borderRadius: 6,
                fontFamily: 'inherit', fontSize: '0.95rem',
              }}
            />
          </label>
          <label style={{ display: 'grid', gap: '0.2rem', fontSize: '0.78rem' }}>
            <span className="eyebrow">Password (8+ characters)</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              style={{
                padding: '0.55rem 0.75rem',
                background: 'var(--bg, #0f0f0f)', color: 'inherit',
                border: '1px solid var(--rule, #444)', borderRadius: 6,
                fontFamily: 'inherit', fontSize: '0.95rem',
              }}
            />
          </label>
          <label style={{ display: 'grid', gap: '0.2rem', fontSize: '0.78rem' }}>
            <span className="eyebrow">Confirm password</span>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
              style={{
                padding: '0.55rem 0.75rem',
                background: 'var(--bg, #0f0f0f)', color: 'inherit',
                border: '1px solid var(--rule, #444)', borderRadius: 6,
                fontFamily: 'inherit', fontSize: '0.95rem',
              }}
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            style={{
              marginTop: '0.4rem',
              padding: '0.65rem',
              background: 'var(--accent, #3b82f6)',
              color: '#fff', border: 0, borderRadius: 999,
              fontSize: '0.92rem', fontWeight: 700,
              cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            {busy ? '…creating account' : 'Create account & sign in'}
          </button>
        </form>

        <p style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: '1.2rem' }}>
          Already have a password? <Link to="/signin" style={{ color: 'inherit', textDecoration: 'underline' }}>Sign in</Link>.
        </p>
      </div>
    </div>
  );
}
