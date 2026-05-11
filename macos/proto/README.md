# Pounce Web Push prototype (Option 1)

A 250-line SwiftUI/AppKit + WKWebView shell that loads the production Pounce
URL and probes whether Web Push works inside a vanilla `WKWebView` on this
macOS / WebKit version, **without** the `aps-environment` entitlement (i.e.
without an Apple Developer Program account).

## What it does

1. Opens the production URL in a `WKWebView`.
2. Injects a JS probe at document end. The probe reports each capability check
   (presence of `Notification`, `ServiceWorker`, `PushManager`), the result of
   `Notification.requestPermission()`, the result of registering `/sw.js`, and
   finally calls `pushManager.subscribe({ userVisibleOnly, applicationServerKey })`
   with the real VAPID key fetched from `/push/public-key`.
3. Native code receives every probe message via `WKScriptMessageHandler` and
   appends it to `~/Desktop/pounce-probe.log` (and prints to stdout).

## Run it

```sh
cd cheetah-market-app/macos/proto
./build-and-run.sh
```

The script builds `Pounce.app`, launches it, and tails the log.

## Use it

1. The window opens and redirects to Google OAuth (oauth2-proxy).
2. Sign in. The probe likely failed its first run because `/push/public-key`
   was unauthenticated; that's expected.
3. After you land back on the dashboard, click **Run probe** in the top toolbar.
4. Click **Open log** to view `~/Desktop/pounce-probe.log`.

## Interpreting the log

The interesting lines are:

- `Notification.permission_initial: …` and `Notification.requestPermission_result: …`
  — if either is `denied` without a system permission prompt, that's a strong
  signal the WKWebView host can't surface notifications.
- `pushManager_present: yes/no` — whether the API surface even exists.
- `SUBSCRIBE_SUCCESS endpoint: …` — Web Push **works** in this WKWebView,
  which would let us go with Option 1 after all.
- `SUBSCRIBE_FAILED name=… msg=…` — Web Push fails. The error name/message
  will tell us why (typical: `NotAllowedError`, `AbortError`, missing
  entitlement).

Either outcome is useful and feeds the next decision.
