/* installAuthRedirect — patch window.fetch for two cross-cutting concerns:
 *
 *   1. AUTO-INJECT credentials='include' for backend API calls
 *      (added 2026-05-20 after user reported "push notifications stopped").
 *      Root cause: the frontend (served on :80 / :5173) and the API
 *      (served on :8000) are technically different origins. Without
 *      credentials='include', the browser does not send the
 *      pounce_local_session cookie on cross-origin requests — every
 *      authenticated POST returned 401 silently, breaking push
 *      subscribe, notification prefs, breakout dismiss, etc. ~80 call
 *      sites had `fetch()` without credentials; patching once here is
 *      cheaper than touching all of them.
 *
 *   2. Auto-redirect on 401 (original purpose). Any unauthenticated
 *      response routes the user to /signin, with the previous URL
 *      stashed in sessionStorage so we can return there post-login.
 *
 * Why patch window.fetch instead of wrapping individual call sites?
 * The codebase has ~80 places calling fetch directly. Wrapping each
 * would be invasive and would inevitably miss new code. A global
 * monkeypatch at app bootstrap catches every call without touching
 * existing files.
 *
 * Caveats:
 *  - Only patches the SPA's runtime fetches; service-worker fetches
 *    handle 401 separately (push subscription paths) — they already
 *    have their own error handling.
 *  - We do nothing on 401 if the user is already on /signin or
 *    /signup so the auth pages themselves don't infinite-loop.
 *  - The original Response is still returned to the caller, so any
 *    component handling its own errors keeps working — the redirect
 *    runs alongside, not instead.
 *  - We only inject credentials for OUR backend (matches the resolved
 *    API base or relative paths); third-party fetches (e.g. yfinance,
 *    Massive — if the frontend ever calls them directly, which it
 *    doesn't today) are left untouched.
 */
import { API } from './apiBase';

const ALREADY_AUTH_PATHS = ['/signin', '/signup'];

let _installed = false;

/** Should `credentials: 'include'` be auto-injected for this URL? */
function _isOurApiUrl(url: string): boolean {
  if (!url) return false;
  // Relative paths (`/foo`, `foo`) — same origin as the SPA, harmless to add.
  if (url.startsWith('/') || !/^[a-z]+:\/\//i.test(url)) return true;
  // Absolute URL — must match our backend.
  try {
    return url.startsWith(API);
  } catch {
    return false;
  }
}

export function installAuthRedirect() {
  if (_installed) return;          // idempotent — handle hot-reload
  _installed = true;

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args: Parameters<typeof fetch>) => {
    // ── (1) Auto-inject credentials='include' for backend calls.
    //
    // fetch() accepts (input, init). `input` is either a string URL,
    // a URL object, or a Request — we mutate the `init` arg to add
    // credentials if it matches our backend AND the caller hasn't
    // already set credentials explicitly.
    const input = args[0];
    const init = (args[1] || {}) as RequestInit;
    const url = typeof input === 'string'
      ? input
      : (input instanceof URL ? input.href : (input as Request).url);
    if (_isOurApiUrl(url) && init.credentials === undefined) {
      // Note: if `input` is a Request, its credentials are set at
      // construction time and we can't override via init — but the
      // codebase doesn't use Request() construction, so this branch
      // is a no-op for the common string-url path. Still safe.
      args[1] = { ...init, credentials: 'include' };
    }

    const response = await originalFetch(...args);
    // Bail out fast on the common case (200s and other success codes)
    // — avoid touching the response state.
    if (response.status !== 401) return response;

    // Don't redirect if the caller hit one of the auth endpoints
    // themselves — POST /auth/local/login returning 401 is expected
    // (wrong password) and the SignIn page handles it inline.
    // (Re-using `url` from the credentials-injection step above.)
    if (url && (url.includes('/auth/local/') || url.includes('/oauth2/'))) {
      return response;
    }

    // Don't redirect from the auth pages themselves.
    if (ALREADY_AUTH_PATHS.some((p) => window.location.pathname.startsWith(p))) {
      return response;
    }

    // Capture where the user was so we could redirect back after sign-in
    // (the backend's /oauth2/start supports an `rd` param; the local
    // path doesn't yet but could). Stored in sessionStorage so a
    // hard reload of the signin page doesn't lose it.
    try {
      sessionStorage.setItem('pounce_return_to', window.location.pathname + window.location.search);
    } catch { /* private-mode browsers — ignore */ }

    // Navigate via location.href (not React Router) — at this point
    // we don't know if React Router is mounted yet, and a full nav
    // ensures we cleanly land on /signin without stale React state.
    window.location.href = '/signin';
    return response;
  };
}
