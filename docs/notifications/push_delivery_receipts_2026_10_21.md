# Push delivery receipts — did the device actually show it? (2026-10-21)

## The ask, verbatim

Ajay 2026-10-21 ~16:05 ET, on the 15:36:15 ET 🚩 `gajjala_setup` push for NIXX:
**"Oh man I did not get an A+ alert for it then today"** — and, asked about the
two 🧠 `gajjala_potential` pushes around it (SAIQ 15:11:20, POLA 16:01:09):
**"Yes POLA reached and SAIQ too"**.

`push_history` recorded all three as `sent 3 / failed 0`: two Mac Chrome
subscriptions (fcm.googleapis.com) and one iPhone (web.push.apple.com), every
one with `gajjala_setup` and `gajjala_potential` prefs on, every one accepted
by its push service (`push/sender._send_one` returns True when pywebpush raises
nothing, TTL 3600). The payloads were ~670 bytes, the tags differed
(`{kind}-{ticker}`), the service worker shows every push with
`showNotification`. **Nothing server-side distinguished a notification the
phone showed from one it dropped.** `sent` was only ever the push SERVICE's
acceptance.

This is **bookkeeping, not an edge**. No gate, threshold, kind, pref or
schedule changes. No push is retried. UNMEASURED.

## What changed

One chain, five hops, one new fact per row:

1. **`push/sender.py`** — `_fan_out` stamps a `push_id` (uuid4 hex, one per
   `send_to_all` / `send_to_user` call) onto a **copy** of the device payload
   (the caller's dict, which history records, is never mutated — the existing
   `items`-stripping rule is unchanged) and records, per subscription tried,
   `targets: [{sub: sha1(endpoint), device: word, ok: bool}]`.
2. **`push/history.py`** — `record(..., push_id=, targets=)` stores both **only
   when given**; a legacy caller stores neither, so a row without `push_id`
   reads as "before receipts", never as "nobody showed it". New sparse index on
   `push_id`.
3. **`frontend/public/sw.js`** — after `showNotification` resolves, the worker
   POSTs `{push_id, endpoint, shown_at}` to `<api>/push/receipt` with its own
   subscription endpoint (`pushManager.getSubscription()`), `credentials:
   'include'`, through the API base the page shared (Cache API, as resubscribe
   does). A payload without `push_id` (an older sender, the Settings test ping)
   posts nothing. A receipt failure never fails the push event; a failed
   `showNotification` posts no receipt. `lib/pushSubscribe.ensurePushSubscription`
   now hands the API base to the worker on EVERY app load, before its 6-hour
   throttle, so a cleared Cache API never leaves the worker posting receipts to
   its host:8000 fallback.
4. **`push/receipts.py`** — `POST /push/receipt` (new router, included in
   `main.py`; the path is on `_PUBLIC_API_PATHS` because a worker runs with the
   page closed and its session cookie may be gone — **the credential is the
   subscription endpoint**, an unguessable per-device URL only that device and
   the server know). Validates the endpoint against `push_subscriptions`,
   scopes the row to that subscription's owner (a broadcast row takes any
   registered user's receipt), and appends **one receipt per device**
   (`update_one({"push_id", "receipts.sub": {"$ne": hash}}, {"$push": …})` —
   idempotent on re-delivery and on a retried POST). An unknown endpoint, an
   unknown `push_id`, another user's row and a `kind=mac` row all answer the
   same `404 {"reason": "unknown"}`. Malformed body → 400. Store down → 503.
   **`sent` / `failed` / `total` are never written.**
5. **`push/recent.py`** — every push row served by `GET /notifications/recent`
   carries `shown_on`:
   `{shown, total, devices, missing, text}` or `null` (row stored before
   receipts, or `total` 0 — the delivery line already says "not delivered").
   `receipts`, `targets` and `push_id` are popped before serving. **`/alerts`
   prints `text` verbatim** (amber while a targeted device has not reported,
   dim once every one has); a null prints nothing.

### The served sentence (`push/receipts.shown_on`)

```
shown on 2 of 3 devices (Mac Chrome ×2); no receipt from iPhone Safari
shown on 3 of 3 devices (Mac Chrome ×2, iPhone Safari)
shown on 0 of 3 devices; no receipt from Mac Chrome ×2, iPhone Safari
shown on 0 of 1 device; no receipt from iPhone Safari
```

- `shown` = receipts on the row; `total` = the row's `total` (devices targeted,
  the same denominator as the delivery line).
- `devices` = the words of the devices that reported, first-seen order,
  duplicates as `×N`.
- `missing` = targets the push service **accepted** (`ok: True`) with no
  receipt. A target the service rejected (`ok: False`, counted in `failed`)
  can't have shown it and is never "no receipt".
- The device word comes from `push_subscriptions.label` ("Pounce · <user
  agent>"): OS iPhone-first (an iPhone UA says "like Mac OS X"), Edge before
  Chrome (an Edge UA carries "Chrome/"): `iPhone Safari`, `Mac Chrome`,
  `Android Chrome`, `Windows Edge`; a hand-typed label is itself (24 chars);
  nothing recognisable is `device`.

### Privacy

Never stored, served or logged: a subscription endpoint or a key. A target and
a receipt keep `sha1(endpoint)` and the device word. The hashes themselves stay
on the server (`push/recent` strips them); the test
`test_recent_serves_shown_on_and_never_the_hashes` pins it.

## How to read a row on /alerts

| line | means |
|---|---|
| `delivered to 3/3 devices` | the push SERVICE accepted the message for every targeted device (unchanged) |
| `shown on 2 of 3 devices (Mac Chrome ×2); no receipt from iPhone Safari` | two devices showed it; the phone has not reported — dropped, offline (the service holds it up to TTL 3600 s and the receipt lands when it wakes), or still on the old worker |
| no second line | the row was stored before receipts, or nobody was targeted |

**A device reports only after it has picked up the new `sw.js`** (nginx serves
it `no-cache`; the browser checks on the next app open). Until a device has
opened the app once after this deploy, its silence on a row means "old worker",
not "dropped". From then on, a 🚩 that reads `no receipt from iPhone` with the
two Macs shown is the NIXX case made visible.

## What this does NOT do

- It does not re-send, retry or escalate a push nobody showed. HIS CALL.
- It does not change `sent`/`failed`/`total`, any gate, pref, kind or cron.
- It does not explain WHY the iPhone dropped the 15:36 push — it makes the
  next drop visible per device, which is what was missing.
- It does not run for the native Mac app (`kind=mac`, SSE, no service worker).

## Contracts

- `backend/tests/test_push_receipts_2026_10_21.py` — hash, device word,
  the sender stamp (both paths, one id, the caller's dict untouched, ids differ
  per send, acceptance per target), history fields (+ NEGATIVE legacy call),
  the route (known/unknown/other-user/mac/malformed/503, idempotent per device,
  **NEGATIVE: a receipt never changes sent/failed/total**), `shown_on` (every
  wording branch, rejected target never "missing", NEGATIVE null cases),
  `/notifications/recent` serving `shown_on` and never a hash, the sw.js
  ordering pin, `main.py` wiring.
- `frontend/src/lib/swReceipt.test.ts` — the REAL `public/sw.js` evaluated in
  `node:vm`: receipt after `showNotification`, exactly three keys, no
  key/content, NEGATIVE: no push_id → no POST, no subscription → no POST, a
  failing receipt never rejects the event, a failing `showNotification` posts
  nothing, the config fallback.
- `frontend/src/pages/Alerts.receipts.test.tsx` — the served `text` printed
  verbatim (amber / dim), NEGATIVE: null and absent print nothing, the delivery
  line untouched.
- `frontend/scripts/contracts.mjs` "📬 Push delivery receipts (2026-10-21)" —
  pins every hop above, the ✨ entry FIRST with both quotes verbatim and no digit
  outside them.
- `SPECS.md` §2 — the `/push/receipt` row.

## Verify after deploy (api + frontend + cron — the sender runs in cron too)

1. Open the app once on each device so the new worker installs.
2. Wait for the next scheduled push (never a test push to his phone without his
   word). On `/alerts` the row shows `delivered to 3/3 devices` and, within
   seconds, `shown on …` naming each device as it reports.
3. Read-only probe: the newest `push_history` row carries `push_id`, `targets`
   (3 hashes) and `receipts` — never an endpoint.
