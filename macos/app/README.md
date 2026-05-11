# Pounce.app — native macOS app for the Pounce dashboard

A `~600`-line Swift/AppKit shell that wraps the production Pounce frontend in
a `WKWebView` and delivers push notifications via a backend SSE channel +
`UNUserNotificationCenter` — no Apple Developer account required.

## Why not Web Push directly?

Web Push inside `WKWebView` requires the `com.apple.developer.aps-environment`
entitlement, which only paid Apple Developer Program accounts can sign for.
The probe at `../proto/Pounce.swift` confirmed `Notification.requestPermission()`
returns `denied` silently without it. So instead the native app holds an SSE
connection open to `GET /push/mac-stream` and fires native local notifications
when alerts arrive on the stream — same UX, zero entitlement requirements.

## Requirements

- macOS 13 (Ventura) or newer — `SMAppService`, `WKWebView.isInspectable`,
  `URLSession.bytes(for:)` all need `≥ 13`.
- Xcode Command Line Tools (`swiftc`) — already present on most dev Macs.
- Be on the same Tailnet as `ajays-macbook-pro.tailb3dc79.ts.net`.

## Build & install

```sh
cd cheetah-market-app/macos/app
./build.sh           # build into ./Pounce.app and launch it
./build.sh install   # also copy to /Applications/Pounce.app
./build.sh clean     # delete ./Pounce.app
```

The script kills any running `Pounce` process before rebuilding, strips the
quarantine xattr (so the unsigned bundle launches without a Gatekeeper
prompt), and tails the log at `~/Library/Logs/Pounce/pounce.log`.

## What the app does on first launch

1. Opens a 1280×880 window with a `WKWebView` pointing at the production URL.
2. Generates a stable `device_id` UUID, persists it to
   `~/Library/Application Support/Pounce/device_id`.
3. Triggers the macOS notification permission prompt for `Pounce` (grant it).
4. Registers itself as a Login Item via `SMAppService.mainApp.register()` so
   it auto-launches on login. macOS may show a one-time approval prompt in
   System Settings → General → Login Items.
5. Calls `POST /push/mac-register` with `{device_id, label}` (auto-fired on
   the first SSE connect via the auto-registration code in `mac_stream`).
6. Holds a `GET /push/mac-stream` SSE connection open — reconnects with
   exponential backoff (1s → max 30s) if the network drops or the server
   restarts.
7. On every `event: alert` from the stream, fires a local
   `UNUserNotificationCenter` notification. Click → focuses the app and
   navigates the WebView to the URL the backend supplied.

## Files

| File | Purpose |
|---|---|
| `Pounce.swift` | Single-file app. Logger, DeviceID, CookieBridge, SSEListener, NotificationDispatcher, LoginItem, AppDelegate. |
| `Info.plist` | Bundle id `com.pounce.mac`, min macOS 13, ATS exemption for the http→https redirect from oauth2-proxy. |
| `build.sh` | Build into `Pounce.app`, kill running instance, launch, tail log. |

## Logs

```sh
tail -F ~/Library/Logs/Pounce/pounce.log
```

Tags:

- `[app]` lifecycle
- `[sse]` SSE listener (connect / disconnect / payload arrival)
- `[noti]` UNUserNotificationCenter (permission grant, dispatch errors)
- `[nav]` WebView navigation events including the http→https redirect upgrade
- `[login]` Login Item registration

## Window-close behavior

Closing the window with the red traffic-light **hides** the window but keeps
the app running so the SSE channel stays open and notifications keep firing.
Re-clicking the dock icon brings the window back. ⌘Q (or **Pounce → Quit
Pounce**) is the only way to fully exit.

## Debugging the WebView

`isInspectable = true` in code → in Safari, enable **Settings → Advanced →
Show features for web developers**, then **Develop → Ajays-MacBook-Pro →
Pounce → \[page\]**. You get full Web Inspector (Console, Network, Storage,
Service Workers).

## Uninstalling

```sh
pkill -x Pounce
rm -rf /Applications/Pounce.app
rm -rf ~/Library/Application\ Support/Pounce
rm -rf ~/Library/Logs/Pounce
# Also unregister as Login Item (the build script does NOT do this for you):
osascript -e 'tell application "System Events" to delete login item "Pounce"' 2>/dev/null || true
```

The backend will still have a `kind=mac` row in `push_subscriptions` — to
delete it, hit:
```sh
curl -X POST "https://.../api/push/mac-unregister" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"<uuid from ~/Library/Application Support/Pounce/device_id>"}'
```
(must be authenticated as the same Google account.)
