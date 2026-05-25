/* SignIn — two auth paths in one page.
 *
 *  Path 1: Google OAuth (existing, unchanged) — clicking "Sign in with
 *          Google" sends the browser to /oauth2/start, oauth2-proxy
 *          handles the dance, callback redirects to /.
 *  Path 2: Email + password (new, 2026-05-18) — POST /auth/local/login,
 *          backend sets pounce_local_session cookie, redirect to /.
 *
 *  Anyone signed in via Google can use this app via the existing path.
 *  Anyone allowlisted but without a Google account can use the password
 *  path. The same email allowlist (backend/oauth2-emails.txt) gates
 *  both — admin still controls who can use the app.
 */
import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { API } from '../lib/apiBase';

type Mode = 'choice' | 'password';

export default function SignInPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>('choice');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!email.trim() || !password) { setErr('Email and password required.'); return; }
    setBusy(true);
    try {
      const r = await fetch(`${API}/auth/local/login`, {
        method:      'POST',
        headers:     { 'Content-Type': 'application/json' },
        credentials: 'include',          // backend sets HttpOnly cookie
        body:        JSON.stringify({ email: email.trim(), password }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        if (r.status === 423) {
          setErr(`Account temporarily locked. ${j.detail || 'Try again in 5 minutes.'}`);
        } else if (r.status === 429) {
          setErr('Too many attempts from your network. Wait a minute and retry.');
        } else {
          setErr(j.detail || 'Sign-in failed.');
        }
        return;
      }
      // Cookie is set; SPA reload picks up the new auth state.
      navigate('/', { replace: true });
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{
      minHeight: '92vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1.2rem',
    }}>
      <div style={{
        width: '100%', maxWidth: 380,
        padding: '2.2rem 1.8rem 1.6rem',
        background: 'rgba(20, 20, 22, 0.85)',
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: 14,
        boxShadow: '0 20px 60px rgba(0,0,0,0.55), 0 0 0 1px rgba(212,175,55,0.04)',
        textAlign: 'center',
      }}>
        <div className="eyebrow" style={{ marginBottom: '0.5rem' }}>№ Pounce · invite only</div>
        <h1 style={{
          fontFamily: '"Times New Roman", Georgia, ui-serif, serif',
          fontStyle: 'italic',
          fontSize: '2.6rem',
          letterSpacing: '-0.01em',
          lineHeight: 1,
          margin: '0 0 0.35rem',
          color: '#f3e8c8',
        }}>
          Pounce
        </h1>
        <p style={{
          fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
          fontSize: '0.74rem',
          letterSpacing: '0.06em',
          color: '#9a9aa3',
          margin: '0 0 1.6rem',
        }}>
          wait · then · strike
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

        {mode === 'choice' ? (
          <>
            {/* Google button — same flow as before. /oauth2/start is
                served by oauth2-proxy regardless of our new
                skip-auth-routes config. */}
            <a
              href="/oauth2/start?rd=/"
              style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                gap: '0.65rem', width: '100%',
                padding: '0.7rem 1rem',
                background: '#ffffff', color: '#1f1f1f',
                border: '1px solid #dadce0', borderRadius: 999,
                fontSize: '0.95rem', fontWeight: 600,
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                cursor: 'pointer', textDecoration: 'none',
                marginBottom: '0.7rem',
              }}
            >
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" focusable="false">
                <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"/>
                <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.836.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/>
                <path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"/>
                <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"/>
              </svg>
              Sign in with Google
            </a>

            <div style={{ position: 'relative', margin: '0.9rem 0 0.7rem', color: 'var(--cm-slate)', fontSize: '0.7rem', letterSpacing: '0.08em' }}>
              <span style={{ background: 'transparent', padding: '0 8px', position: 'relative', zIndex: 1 }}>OR</span>
              <hr style={{ border: 0, borderTop: '1px solid var(--rule, #444)', margin: 0, position: 'absolute', top: '50%', left: 0, right: 0 }} />
            </div>

            {/* Password path — clicking expands the form inline. */}
            <button
              onClick={() => setMode('password')}
              style={{
                width: '100%',
                padding: '0.65rem 1rem',
                background: 'transparent',
                border: '1px solid var(--rule, #555)',
                color: 'var(--ink, inherit)',
                borderRadius: 999,
                fontSize: '0.92rem',
                fontWeight: 500,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              📧 Sign in with email + password
            </button>
          </>
        ) : (
          <form onSubmit={submit} style={{ display: 'grid', gap: '0.65rem', textAlign: 'left' }}>
            <label style={{ display: 'grid', gap: '0.2rem', fontSize: '0.78rem' }}>
              <span className="eyebrow">Email</span>
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
              <span className="eyebrow">Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
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
              {busy ? '…signing in' : 'Sign in'}
            </button>
            <button
              type="button"
              onClick={() => { setMode('choice'); setErr(null); }}
              style={{
                background: 'none', border: 0, color: 'var(--cm-slate)',
                cursor: 'pointer', fontSize: '0.74rem', padding: '0.3rem',
              }}
            >
              ← back to all sign-in options
            </button>
            <p style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', lineHeight: 1.55, margin: '0.4rem 0 0' }}>
              First time? <Link to="/signup" style={{ color: 'inherit', textDecoration: 'underline' }}>Set a password</Link> for your invited email.
            </p>
          </form>
        )}

        <p style={{ fontSize: '0.66rem', color: '#6a6a72', marginTop: '1.4rem', lineHeight: 1.55 }}>
          Access is invite-only. If your email isn't on the allowlist,
          sign-in will fail — contact the person who invited you.
        </p>
      </div>
    </div>
  );
}
