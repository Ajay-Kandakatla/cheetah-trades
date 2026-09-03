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


/* --------------------------------------------------------------------------
   Self-healing (Ajay 2026-09-03: "my phone alerts are also not working").
   His phone's subscription died on 2026-09-02 10:50 ET: Google's push service
   answered 410 Gone to a Sell-signal push, the sender purged the endpoint
   (push/sender.py), and every alert since reached only the Mac. Push
   endpoints rotate; nothing re-registered the phone until he visited
   /notifications by hand. Two repairs:
     1. pushsubscriptionchange in sw.js re-subscribes the moment the browser
        rotates the endpoint (needs the API base — handed to the worker here);
     2. ensurePushSubscription() on every app load: permission already granted
        + no live subscription the SERVER knows about → subscribe again, never
        prompting (a prompt from nowhere is how permissions get denied).
   -------------------------------------------------------------------------- */
const CONFIG_CACHE = 'cheetah-config';
const CONFIG_KEY = '/__cheetah_config';
const RESYNC_STAMP = 'push.resync.ts';
const RESYNC_EVERY_MS = 6 * 60 * 60 * 1000;

export type EnsureResult = {
  ok: boolean;
  action: 'unsupported' | 'no-permission' | 'no-sw' | 'skipped' | 'kept' | 'subscribed' | 'resubscribed' | 'error';
  reason?: string;
};

/** Hand the API base to the service worker (postMessage now, Cache API for the
 *  next cold start) so pushsubscriptionchange can talk to the backend. */
export async function shareConfigWithServiceWorker(reg: ServiceWorkerRegistration | null): Promise<void> {
  const cfg = { api: API, label: 'Pounce · ' + navigator.userAgent.slice(0, 100) };
  try { reg?.active?.postMessage({ type: 'cheetah:config', ...cfg }); } catch { /* ignore */ }
  try {
    if ('caches' in window) {
      const c = await caches.open(CONFIG_CACHE);
      await c.put(CONFIG_KEY, new Response(JSON.stringify(cfg), { headers: { 'Content-Type': 'application/json' } }));
    }
  } catch { /* ignore */ }
}

async function serverKnownEndpoints(): Promise<Set<string> | null> {
  try {
    const r = await fetch(`${API}/push/subscriptions`);
    if (!r.ok) return null;
    const j: any = await r.json();
    const list: any[] = Array.isArray(j) ? j : (j?.subscriptions || j?.devices || j?.items || []);
    return new Set(list.map((d: any) => d?.endpoint).filter(Boolean));
  } catch {
    return null;
  }
}

async function subscribeWithServerKey(reg: ServiceWorkerRegistration): Promise<PushSubscription | null> {
  const keyResp = await fetch(`${API}/push/public-key`);
  const keyJson: any = await keyResp.json();
  if (!keyJson?.public_key) return null;
  return reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(keyJson.public_key) as BufferSource,
  });
}

async function registerOnServer(sub: PushSubscription, label: string): Promise<void> {
  await fetch(`${API}/push/subscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subscription: sub.toJSON(), label }),
  });
}

/**
 * Repair a device's push registration without ever prompting.
 * `force` skips the 6-hour throttle (the Notifications page passes it).
 */
export async function ensurePushSubscription(opts: { force?: boolean; now?: number; storage?: Storage | null } = {}): Promise<EnsureResult> {
  const now = opts.now ?? Date.now();
  const storage = opts.storage === undefined ? safeStorage() : opts.storage;
  if (!pushSupported()) return { ok: false, action: 'unsupported' };
  if (Notification.permission !== 'granted') return { ok: false, action: 'no-permission' };
  if (!opts.force) {
    const last = Number(storage?.getItem(RESYNC_STAMP) || 0);
    if (last && now - last < RESYNC_EVERY_MS) return { ok: true, action: 'skipped' };
  }
  try {
    const reg = await ensureServiceWorker();
    if (!reg) return { ok: false, action: 'no-sw' };
    await shareConfigWithServiceWorker(reg);
    const label = 'Pounce · ' + navigator.userAgent.slice(0, 100) + ' · self-heal';
    let sub = await reg.pushManager.getSubscription();
    let action: EnsureResult['action'] = 'kept';
    if (sub) {
      const known = await serverKnownEndpoints();
      if (known && !known.has(sub.endpoint)) {
        // The server purged it (410 Gone) — the local object is a corpse.
        try { await sub.unsubscribe(); } catch { /* ignore */ }
        sub = null;
        action = 'resubscribed';
      }
    } else {
      action = 'subscribed';
    }
    if (!sub) {
      sub = await subscribeWithServerKey(reg);
      if (!sub) return { ok: false, action: 'error', reason: 'no VAPID key' };
      await registerOnServer(sub, label);
    }
    try { storage?.setItem(RESYNC_STAMP, String(now)); } catch { /* ignore */ }
    return { ok: true, action };
  } catch (e: any) {
    return { ok: false, action: 'error', reason: e?.message || String(e) };
  }
}

function safeStorage(): Storage | null {
  try { return window.localStorage; } catch { return null; }
}
