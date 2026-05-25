import { API } from './apiBase';

/* ==========================================================================
   pushSubscribe — register / unregister Web Push subscriptions.
   --------------------------------------------------------------------------
   iOS Safari note: web push requires the site to be installed as a PWA
   (Add to Home Screen) first. Until that's done, Notification.permission
   stays denied even after requestPermission().
   ========================================================================== */

const SW_PATH = '/sw.js';

function urlBase64ToUint8Array(b64: string): Uint8Array {
  const padding = '='.repeat((4 - (b64.length % 4)) % 4);
  const base64 = (b64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

export async function ensureServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!('serviceWorker' in navigator)) return null;
  try {
    const existing = await navigator.serviceWorker.getRegistration();
    if (existing) return existing;
    return await navigator.serviceWorker.register(SW_PATH);
  } catch (e) {
    console.warn('SW register failed', e);
    return null;
  }
}

export function pushSupported(): boolean {
  return 'serviceWorker' in navigator
    && 'PushManager' in window
    && 'Notification' in window;
}

export function isStandalone(): boolean {
  // PWA mode (iOS Add to Home Screen, Android install)
  return (window.matchMedia('(display-mode: standalone)').matches)
    || (navigator as any).standalone === true;
}

export async function getCurrentSubscription(): Promise<PushSubscription | null> {
  const reg = await ensureServiceWorker();
  if (!reg) return null;
  return reg.pushManager.getSubscription();
}

export async function subscribePush(label?: string): Promise<{ ok: boolean; reason?: string; endpoint?: string }> {
  if (!pushSupported()) return { ok: false, reason: 'browser does not support push' };

  const perm = await Notification.requestPermission();
  if (perm !== 'granted') return { ok: false, reason: `permission ${perm}` };

  const reg = await ensureServiceWorker();
  if (!reg) return { ok: false, reason: 'service worker unavailable' };

  // Pull VAPID public key from backend
  const keyResp = await fetch(`${API}/push/public-key`);
  const keyJson = await keyResp.json();
  if (!keyJson.public_key) return { ok: false, reason: 'no VAPID key' };

  let sub: PushSubscription;
  try {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(keyJson.public_key) as BufferSource,
    });
  } catch (e: any) {
    return { ok: false, reason: `subscribe failed: ${e.message}` };
  }

  // POST to backend
  const subJson = sub.toJSON();
  await fetch(`${API}/push/subscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      subscription: subJson,
      label: label || navigator.userAgent.slice(0, 100),
    }),
  });

  return { ok: true, endpoint: sub.endpoint };
}

export async function unsubscribePush(): Promise<{ ok: boolean }> {
  const sub = await getCurrentSubscription();
  if (!sub) return { ok: true };
  const endpoint = sub.endpoint;
  await sub.unsubscribe();
  await fetch(`${API}/push/unsubscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ endpoint }),
  });
  return { ok: true };
}

export async function updatePrefs(endpoint: string, prefs: Record<string, any>): Promise<void> {
  await fetch(`${API}/push/prefs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ endpoint, prefs }),
  });
}

export async function testPush(endpoint: string): Promise<{ ok: boolean }> {
  const r = await fetch(`${API}/push/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ endpoint }),
  });
  return r.json();
}
