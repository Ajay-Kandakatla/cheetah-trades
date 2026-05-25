/* InstallToHomeScreen — first-run onboarding for iPhone users only.
 *
 * Why this exists: on iOS Safari, web push notifications ONLY work when
 * the site has been added to the home screen (i.e. running as a PWA in
 * standalone mode). A Safari tab — no matter how often it's reloaded —
 * will not receive push. Apple shipped this restriction in iOS 16.4.
 *
 * Scope: iPhone-only. Android Chrome already delivers push to a regular
 * tab without an install, so dragging Android users through this flow
 * is friction with no payoff. Desktop is the same — no install needed.
 *
 * UX rules:
 *   • Only show on iPhone (iOS Safari, or iOS Chrome/Firefox with a
 *     "switch to Safari" message). Never on desktop, Android, or
 *     iPad-as-desktop.
 *   • Never show when already running in standalone — the user has
 *     already installed; nagging would be insulting.
 *   • Remember dismissal per-device. The "/notifications" page exposes a
 *     "show install help again" button so the user can re-trigger it if
 *     they tap "Got it" and change their mind.
 *   • Don't trigger Notification.requestPermission() here — that has to
 *     be a direct response to a user tap, in standalone mode, AFTER they
 *     come back. The Notifications page handles that next step. */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

const DISMISS_KEY = 'pounce.install_prompt_dismissed_v1';

/** Has the user already chosen "later" or "got it"? */
function isDismissed(): boolean {
  if (typeof window === 'undefined') return true;
  return window.localStorage.getItem(DISMISS_KEY) === '1';
}

/** Clear dismissal so the modal can be force-opened from /notifications. */
export function clearInstallDismissal() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(DISMISS_KEY);
}

type Platform = 'ios-safari' | 'ios-other' | 'other';

/** Coarse platform detect. We only care about iPhone — everything else
 *  (Android, desktop, iPad) collapses into 'other' and the modal won't
 *  auto-show. */
function detectPlatform(): Platform {
  if (typeof navigator === 'undefined') return 'other';
  const ua = navigator.userAgent || '';
  // iPad is excluded on purpose — modern iPadOS Safari reports a Mac UA
  // and behaves like desktop Safari for push purposes (no install
  // required). Phones-only is the rule here.
  const isIPhone = /iPhone|iPod/.test(ua);
  if (!isIPhone) return 'other';
  // Safari is the only iOS browser that exposes "Add to Home Screen"
  // via the share sheet AND can receive push from an installed PWA.
  // Chrome/Firefox on iOS are WebKit shells without that capability,
  // so we show a different message there.
  const isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
  return isSafari ? 'ios-safari' : 'ios-other';
}

/** Already installed as a PWA? Both iOS legacy + modern display-mode. */
function isStandalone(): boolean {
  if (typeof window === 'undefined') return false;
  // iOS-only legacy property
  if ((window.navigator as any).standalone === true) return true;
  // Cross-platform modern API
  return window.matchMedia?.('(display-mode: standalone)').matches === true;
}

/** Should we automatically show on app mount? */
export function shouldAutoShowInstallPrompt(): boolean {
  if (typeof window === 'undefined') return false;
  if (isDismissed()) return false;
  if (isStandalone()) return false;
  const p = detectPlatform();
  // iPhone only. Android Chrome delivers push to a plain tab — no
  // install needed. Desktop same. So we don't auto-prompt them.
  return p === 'ios-safari' || p === 'ios-other';
}

/** True iff the visitor is on iPhone — used to decide whether the
 *  "Show install instructions" button is visible on /notifications.
 *  Non-iPhone visitors don't need this guide, so we hide the affordance. */
export function isIPhone(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /iPhone|iPod/.test(navigator.userAgent || '');
}

type Props = {
  /** Force the modal open even if dismissed / standalone — used by the
   *  "show install help again" button on /notifications. */
  forceOpen?: boolean;
  onClose: () => void;
};

export function InstallToHomeScreen({ forceOpen, onClose }: Props) {
  const [platform] = useState<Platform>(() => detectPlatform());

  // Close on Escape — keyboard users on phones often have a paired keyboard.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') dismiss(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // "Got it" — store dismissal and close. "Later" does the same; the
  // distinction is purely tonal in the button label.
  const dismiss = () => {
    try { window.localStorage.setItem(DISMISS_KEY, '1'); } catch { /* ignore */ }
    onClose();
  };

  // Don't render the modal at all if the conditions for showing it
  // aren't met — unless caller explicitly forced it open. This is the
  // belt-and-suspenders gate (parent already checks via shouldAutoShow).
  // Non-iPhone visitors fall through to `other` and we render nothing.
  if (!forceOpen) {
    if (isStandalone()) return null;
    if (platform === 'other') return null;
  }

  return createPortal(
    <div
      onClick={dismiss}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
        zIndex: 1100, padding: '0.8rem',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-raised, #1a1a1a)', color: 'var(--ink, inherit)',
          border: '1px solid var(--rule, #333)', borderRadius: 12,
          width: '100%', maxWidth: 460, maxHeight: '92vh', overflow: 'auto',
          padding: '1.1rem 1.2rem 1.3rem',
          boxShadow: '0 -20px 60px rgba(0,0,0,0.5)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '0.4rem' }}>
          <div>
            <div className="eyebrow">Set up · push notifications</div>
            <h2 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1.2rem' }}>
              Install Cheetah to your home screen
            </h2>
          </div>
          <button onClick={dismiss} aria-label="Close" style={{ background: 'none', border: 0, color: 'var(--cm-slate)', cursor: 'pointer', fontSize: '1.6rem', lineHeight: 1 }}>×</button>
        </div>

        <p style={{ fontSize: '0.86rem', color: 'var(--cm-slate)', lineHeight: 1.5, margin: '0.4rem 0 0.9rem' }}>
          {platform === 'ios-safari' && (
            <>Adding Cheetah to your home screen turns it into a native-feeling app and
            <strong> unlocks push notifications</strong> for price alerts and breakouts. Apple
            requires this step on iPhone — the browser tab itself can't receive push.</>
          )}
          {platform === 'ios-other' && (
            <>On iPhone, only <strong>Safari</strong> can install Cheetah to your home screen
            with push notifications. Open this page in Safari first, then come back to these
            instructions.</>
          )}
          {platform === 'other' && (
            <>This walkthrough is iPhone-specific. On Android and desktop, push notifications
            work directly in your browser — just tap <strong>“Subscribe this device”</strong> on
            the Notifications page.</>
          )}
        </p>

        {/* ────────────── iOS Safari steps ────────────── */}
        {platform === 'ios-safari' && (
          <ol style={{ paddingLeft: '1.1rem', margin: 0, fontSize: '0.92rem', lineHeight: 1.55, display: 'grid', gap: '0.45rem' }}>
            <li>
              Tap the <strong>Share</strong> button{' '}
              <span aria-hidden style={{ fontSize: '1rem' }}>⬆️</span>{' '}
              at the bottom of Safari (square with up-arrow icon).
            </li>
            <li>
              Scroll down in the share sheet and tap <strong>“Add to Home Screen”</strong>{' '}
              <span aria-hidden>➕</span>.
            </li>
            <li>
              Tap <strong>Add</strong> in the top-right of the popup.
            </li>
            <li>
              Close Safari. Open Cheetah from its new icon on your home screen.
            </li>
            <li>
              On the <strong>Notifications</strong> tab, tap <em>“Enable push notifications”</em>{' '}
              and accept the permission prompt — this only works inside the installed app.
            </li>
          </ol>
        )}

        {platform === 'ios-other' && (
          <ol style={{ paddingLeft: '1.1rem', margin: 0, fontSize: '0.92rem', lineHeight: 1.55, display: 'grid', gap: '0.45rem' }}>
            <li>Copy this page's URL.</li>
            <li>Open <strong>Safari</strong> on your iPhone.</li>
            <li>Paste the URL into the Safari address bar and load Cheetah.</li>
            <li>Tap the <strong>Share</strong> button → <strong>“Add to Home Screen”</strong>.</li>
            <li>Open Cheetah from its new home-screen icon and enable notifications from the Notifications tab.</li>
          </ol>
        )}

        {/* 'other' branch (non-iPhone) intentionally renders no step list —
            push works without install on those platforms, so there are
            no steps to show. The intro paragraph above tells them where
            to go instead. */}

        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1.1rem' }}>
          <button
            onClick={dismiss}
            style={{
              flex: 1,
              background: 'var(--accent, #3b82f6)',
              color: '#fff',
              border: 0,
              borderRadius: 6,
              padding: '0.65rem',
              fontSize: '0.92rem',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Got it
          </button>
        </div>

        <p style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: '0.9rem', lineHeight: 1.5 }}>
          You can re-open this guide any time from the <strong>Notifications</strong> page → “Show install instructions”.
        </p>
      </div>
    </div>,
    document.body,
  );
}
