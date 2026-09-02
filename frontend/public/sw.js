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
