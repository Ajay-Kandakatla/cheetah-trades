import { useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { useSepaScanStream } from '../hooks/useSepaScanStream';
import { useCurrentUser } from '../hooks/useUser';
import { SepaScanProgress } from './SepaScanProgress';

/* ==========================================================================
   FullScanModal — a self-contained "Full Scan" button + modal that triggers a
   full-universe SEPA scan WITHOUT navigating to the SEPA page. Drop <FullScanModal/>
   into any page header (Leaderboard, Portfolio). Owner-only — a full scan is heavy
   (~3–15 min), so non-admins never see the button. Reuses the existing scan-stream
   hook + progress component; no scan logic is duplicated. (2026-06-09)
   ========================================================================== */

export function FullScanModal() {
  const { user } = useCurrentUser();
  const [open, setOpen] = useState(false);
  const [catalyst, setCatalyst] = useState(true);
  const stream = useSepaScanStream();

  if (!user?.is_admin) return null;            // owner-only

  const inFlight = stream.scanning;
  const started = stream.phase !== 'idle';
  const done = stream.phase === 'done';

  const close = () => {
    if (inFlight) return;                       // don't close mid-scan (keeps the SSE alive)
    setOpen(false);
    stream.reset();
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="Rescan the entire universe (~3–15 min) without leaving this page"
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '0.4rem 0.8rem', borderRadius: 8, cursor: 'pointer', fontWeight: 600,
          fontSize: '0.8rem', background: 'var(--gold, #c9a227)', color: '#1a1a1a', border: 'none',
        }}
      >
        ⚡ Full Scan
      </button>

      {open && createPortal(
        <div
          onClick={close}
          style={{
            position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.6)',
            display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
            padding: '6vh 1rem', overflowY: 'auto',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%', maxWidth: 560, background: 'var(--bg-raised, #16181d)',
              border: '1px solid var(--hairline, #2a2a2a)', borderRadius: 12, padding: '1rem 1.1rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <strong style={{ fontSize: '1rem' }}>⚡ Full Universe Scan</strong>
              <button
                onClick={close} aria-label="Close" disabled={inFlight}
                style={{ background: 'transparent', border: 'none', color: 'inherit',
                         fontSize: '1.1rem', cursor: inFlight ? 'not-allowed' : 'pointer', opacity: inFlight ? 0.4 : 1 }}
              >✕</button>
            </div>

            {!started && (
              <>
                <p style={{ fontSize: '0.85rem', color: 'var(--ink-muted, #94a3b8)', marginTop: 0 }}>
                  Rescan the <strong>entire universe</strong> (~3–15 min). Live progress streams below;
                  results land on the SEPA page when it finishes.
                </p>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', margin: '0.6rem 0 1rem' }}>
                  <input type="checkbox" checked={catalyst} onChange={(e) => setCatalyst(e.target.checked)} />
                  Include catalyst (news + analyst revisions — slower)
                </label>
                <button
                  onClick={() => stream.start({ mode: 'broad', with_catalyst: catalyst })}
                  style={{ padding: '0.55rem 1.1rem', fontWeight: 700, borderRadius: 8, cursor: 'pointer',
                           background: 'var(--gold, #c9a227)', color: '#1a1a1a', border: 'none' }}
                >
                  Run Full Scan
                </button>
              </>
            )}

            {started && <SepaScanProgress {...stream} />}

            {done && (
              <div style={{ marginTop: 12, display: 'flex', gap: 10, alignItems: 'center' }}>
                <Link
                  to="/sepa" onClick={() => setOpen(false)}
                  style={{ fontWeight: 600, color: 'var(--gold, #c9a227)' }}
                >
                  View results on the SEPA page →
                </Link>
                <button
                  onClick={() => stream.reset()}
                  style={{ background: 'transparent', border: '1px solid var(--hairline, #2a2a2a)',
                           color: 'inherit', borderRadius: 6, padding: '0.25rem 0.6rem', cursor: 'pointer', fontSize: '0.78rem' }}
                >
                  Run another
                </button>
              </div>
            )}
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
