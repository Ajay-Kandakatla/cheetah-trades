# Pounce.app integration — backend + macOS rollout

Three-step rollout. Backend changes are strictly **additive** — existing web
and iPhone push paths are unchanged.

## 1. Deploy the backend changes

Files touched in this change (all additive):

```
backend/push/mac_stream.py          NEW   SSE channel + Mongo outbox + drain task
backend/push/subs.py                EDIT  add kind=mac helpers; existing list_subscriptions excludes mac
backend/sepa/notify.py              EDIT  _send_push also enqueues for Mac
backend/main.py                     EDIT  /push/mac-{register,unregister,stream,test}; lifespan starts drain
```

No schema migrations needed. Existing `push_subscriptions` rows (no `kind`
field) keep working because `list_subscriptions` matches `kind != "mac"`,
which Mongo's `$ne` operator treats as "not mac OR field absent".

```sh
cd cheetah-market-app
docker compose build api
docker compose up -d api cron        # cron picks up the same image
```

Sanity-check the new endpoints from the Mac mini:

```sh
# Should 401 (no auth) — confirms route is reachable through nginx + oauth2-proxy
curl -i https://ajays-macbook-pro.tailb3dc79.ts.net/api/push/mac-stream?device_id=test

# Should be 200 in api container logs:
docker compose logs api --tail 50 | grep mac_stream
# Expect to see:
#   mac_stream: drain task started (poll=200ms)
```

## 2. Build & install Pounce.app

```sh
cd cheetah-market-app/macos/app
./build.sh install
```

That will:
- compile `Pounce.swift` into `/Applications/Pounce.app`
- launch it
- tail `~/Library/Logs/Pounce/pounce.log`

First launch:
1. Window opens → redirects to Google OAuth → log in.
2. macOS prompts for notification permission — grant it.
3. Login Item registration may show a separate macOS prompt — approve.
4. Watch the log: you should see `[sse] connected (200)` followed by
   `[sse] stream live`. That means the channel is open.

## 3. End-to-end smoke test

From any browser logged in as the same Google account:

```sh
# Discover your device_id
DEVICE_ID=$(cat ~/Library/Application\ Support/Pounce/device_id)
echo "$DEVICE_ID"

# Pump a test event through the Mac path
curl -i -X POST https://ajays-macbook-pro.tailb3dc79.ts.net/api/push/mac-test \
    -H "Content-Type: application/json" \
    -b "_oauth2_proxy=<your cookie>" \
    -d "{\"device_id\":\"$DEVICE_ID\"}"
```

Easier: open `/notifications` in the Pounce window and click any **Test**
button there — the new `/push/mac-test` reaches every Mac client for the
authenticated user, so you'll see a native macOS banner regardless of which
device's "Test" button you clicked.

Expected timeline:
```
T=0ms      backend writes to mac_outbox
T=~100ms   api drain task picks it up
T=~110ms   SSE event: alert flushes to Pounce.app
T=~120ms   UNUserNotificationCenter banner appears
T=~150ms   user clicks → window comes to front, WebView navigates
```

## What's intentionally NOT changed

- `frontend/src/pages/Notifications.tsx` — existing renderer iterates
  unknown fields and ignores `kind`, so Mac devices show up in the
  registered-devices list automatically with their hostname label and
  `mac:<short>` endpoint. Adding per-row Test buttons + Mac-specific
  affordances is a future polish item.
- `frontend/public/sw.js` — service worker is unchanged; web/iPhone push
  is unchanged.
- `/push/subscribe`, `/push/unsubscribe`, `/push/prefs`, `/push/test`,
  `/push/public-key`, `/push/subscriptions` — all existing endpoints
  preserve their request/response shapes. `/push/subscriptions` adds an
  optional `kind` field per row.

## Known limitations / follow-ups

- **App must be running** for notifications to fire. The Login Item entry
  + window-close-keeps-running design covers most cases, but if you `⌘Q`,
  reboot, or kill the process, you'll miss alerts until next launch.
- **Quiet hours / pref toggling** for Mac devices requires the existing
  `/push/prefs` endpoint with a `mac:<device_id>` "endpoint" string — the
  /notifications UI doesn't expose this yet (you'd update via API or
  directly in Mongo).
- **The oauth2-proxy http-redirect bug** (302 → http://) is worked around
  in `WKNavigationDelegate.decidePolicyFor` (upgrade in-flight). Real fix
  is a separate task — already flagged.
