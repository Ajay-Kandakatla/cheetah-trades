/**
 * API base URL — auto-detected so the app works correctly when accessed
 * from any host (localhost during dev, Tailscale IP from your phone, LAN
 * IP, custom domain, etc).
 *
 * Resolution order:
 *   1. VITE_API_BASE env at build time — explicit override wins
 *   2. If page was served from localhost → talk to localhost:8000
 *   3. Else → talk to the SAME hostname the page came from, port 8000
 *      (so http://100.83.x.x:5173 calls http://100.83.x.x:8000)
 *
 * Why this exists: previously every fetch was hardcoded to
 * `http://localhost:8000`. From a phone hitting the Mac via Tailscale,
 * "localhost" means the PHONE's localhost — which has no API. Using
 * window.location.hostname makes the API URL portable.
 */
function resolveApiBase(): string {
  const explicit = (import.meta as any).env?.VITE_API_BASE;
  if (explicit) return explicit;

  if (typeof window === 'undefined') return 'http://localhost:8000';
  const host = window.location.hostname;
  const proto = window.location.protocol === 'https:' ? 'https:' : 'http:';

  // Localhost dev path
  if (host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0') {
    return 'http://localhost:8000';
  }

  // Any other host (LAN, Tailscale 100.x.x.x, *.ts.net, custom DNS) →
  // talk to the same host on the API port.
  return `${proto}//${host}:8000`;
}

export const API = resolveApiBase();
