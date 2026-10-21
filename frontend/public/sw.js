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

  // The receipt (below) runs only AFTER the notification is on screen, and a
  // receipt failure never fails the push: the notification is what matters.
  event.waitUntil(
    self.registration.showNotification(title, options)
      .then(() => sendReceipt(payload).catch(() => { /* best-effort */ })),
  );
});

/* --------------------------------------------------------------------------
   Delivery receipts (2026-10-21). Ajay, on a 🚩 A+ push the server recorded as
   sent 3 / failed 0: "Oh man I did not get an A+ alert for it then today" —
   and "Yes POLA reached and SAIQ too" for the two pushes around it. `sent` is
   the push service accepting the message; nothing server-side knew whether
   the phone SHOWED it. Now, once showNotification has resolved, the worker
   echoes the `push_id` the sender stamped on the payload to POST /push/receipt
   together with its own subscription endpoint (the credential — only this
   device and the server know it) and a clock stamp. Nothing else: no title,
   no body, no key. A payload without push_id (an old sender, the Settings-page
   test ping) posts nothing. /alerts then prints "shown on 2 of 3 devices".
   -------------------------------------------------------------------------- */
function receiptBody(payload, endpoint) {
  if (!payload || typeof payload.push_id !== 'string' || !payload.push_id) return null;
  if (typeof endpoint !== 'string' || !endpoint) return null;
  return { push_id: payload.push_id, endpoint: endpoint, shown_at: Date.now() };
}

async function sendReceipt(payload) {
  if (!payload || !payload.push_id) return;
  const sub = await self.registration.pushManager.getSubscription();
  const body = receiptBody(payload, sub && sub.endpoint);
  if (!body) return;
  const cfg = await loadConfig();
  await fetch(`${cfg.api}/push/receipt`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

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
