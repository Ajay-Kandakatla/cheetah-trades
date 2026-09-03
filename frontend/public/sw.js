/* Cheetah service worker — handles incoming push notifications + click routing.
   Registered from src/lib/pushSubscribe.ts on app load. */

self.addEventListener('install', (event) => {
  // Activate immediately so updates take effect on next page load.
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (e) {
    payload = { title: 'Cheetah', body: event.data ? event.data.text() : '' };
  }

  const title = payload.title || 'Cheetah';
  const options = {
    body: payload.body || '',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    tag: payload.tag || 'cheetah',
    data: { url: payload.url || (payload.data && payload.data.url) || '/', ...payload },
    requireInteraction: payload.kind === 'volume_breakout' || payload.kind === 'rising_momentum',
    vibrate: [200, 100, 200],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientsArr) => {
      // If the app is already open, focus it and navigate
      for (const client of clientsArr) {
        if ('focus' in client) {
          client.focus();
          if ('navigate' in client) {
            try { client.navigate(url); } catch (e) { /* ignore */ }
          }
          return;
        }
      }
      // Otherwise open a new window
      if (self.clients.openWindow) return self.clients.openWindow(url);
    }),
  );
});

/* --------------------------------------------------------------------------
   Self-healing subscription (2026-09-03). Push endpoints rotate; when the
   browser fires pushsubscriptionchange we re-subscribe with the same VAPID
   key and re-register with the backend, so a rotation never turns into
   "my phone alerts are not working". The API base + device label are handed
   over by src/lib/pushSubscribe.ts (postMessage + the Cache API) because a
   worker cannot read the page's config.
   -------------------------------------------------------------------------- */
const CONFIG_CACHE = 'cheetah-config';
const CONFIG_KEY = '/__cheetah_config';

function defaultApiBase() {
  const host = self.location.hostname;
  if (host === 'localhost' || host === '127.0.0.1') return 'http://localhost:8000';
  return `${self.location.protocol}//${host}:8000`;
}

async function loadConfig() {
  try {
    const c = await caches.open(CONFIG_CACHE);
    const r = await c.match(CONFIG_KEY);
    if (r) return await r.json();
  } catch (e) { /* fall through */ }
  return { api: defaultApiBase(), label: 'Pounce · service worker' };
}

self.addEventListener('message', (event) => {
  const d = event.data || {};
  if (d.type !== 'cheetah:config') return;
  event.waitUntil((async () => {
    try {
      const c = await caches.open(CONFIG_CACHE);
      await c.put(CONFIG_KEY, new Response(JSON.stringify({ api: d.api, label: d.label }),
        { headers: { 'Content-Type': 'application/json' } }));
    } catch (e) { /* ignore */ }
  })());
});

async function resubscribe(oldSub) {
  const cfg = await loadConfig();
  let key = oldSub && oldSub.options && oldSub.options.applicationServerKey;
  if (!key) {
    const r = await fetch(`${cfg.api}/push/public-key`, { credentials: 'include' });
    const j = await r.json();
    if (!j.public_key) throw new Error('no VAPID key');
    const b64 = (j.public_key + '='.repeat((4 - (j.public_key.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(b64);
    key = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) key[i] = raw.charCodeAt(i);
  }
  const sub = await self.registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
  await fetch(`${cfg.api}/push/subscribe`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subscription: sub.toJSON(), label: `${cfg.label || 'Pounce'} · rotated` }),
  });
  return sub;
}

self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil(resubscribe(event.oldSubscription).catch((e) => {
    console.warn('cheetah sw: resubscribe failed', e);
  }));
});
