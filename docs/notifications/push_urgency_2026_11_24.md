# Web Push `Urgency: high` for the kinds he keeps — 2026-11-24

**Ask (Ajay, 2026-11-24, verbatim):** "also i am not getting the alerts on phone"

## What the record showed (push_history + delivery receipts, read-only)

| Device (endpoint hash) | 11-10 | 11-11 | 11-17 | 11-18 | 11-20 | 11-23 |
|---|---|---|---|---|---|---|
| iPhone `f9fda3` shown / sent | 138/143 | 123/126 | 62/93 | 22/58 | 53/86 | 44/70 |
| iPhone `fc0a3a` shown / sent | 0/143 | 0/126 | 0/93 | 0/58 | 0/86 | 0/70 |
| Mac Chrome `33be7a` | — | — | 93/93 | 58/58 | 86/86 | 70/70 |

- The server **accepted** every 🚩 / 🧠 push for all 4 devices (sent 4 / failed 0).
- On 11-23 the iPhone's receipts came back in **batches, 10–33 minutes late** (lags 601 s, 1,201 s, 1,996 s; two
  shown together at 13:34 and two at 16:56), and **whole stretches never arrived** (14:11–15:14: 7 pushes in a row,
  including the 🚩 A+ for NXAT and PDSB).
- `fc0a3a` has never sent one receipt since receipts shipped. It is a dead / orphaned registration (Apple still
  accepts pushes for it). Removing it is his call.

## Cause

`push/sender._send_one` set `ttl=3600` and **no `Urgency` header**, so every push went out as `normal`
(RFC 8030 §5.3). Apple's push service may hold a normal push back on a locked / low-power iPhone and coalesce on
reconnect; older pending pushes are dropped.

## Change

- `push/sender.URGENT_KINDS = subs.OWNER_KEEP_SET` (derived, never retyped). For those kinds `webpush(...)` gets
  `headers={"Urgency": "high"}`.
- Every other kind is sent byte-for-byte as before: no kwarg, `headers=None`.
- No gate, pref, kind, count, TTL or payload change. The device payload never carries the header.

Tests: `backend/tests/test_push_urgency_2026_11_24.py` (incl. negatives: other kinds get no header, case and
whitespace variants are not kept kinds, the payload is untouched).

## How to tell if it worked

The `/alerts` row's "shown on N of M devices" line, and the per-device shown/sent count above, re-read after a full
session (11-24). If the iPhone still drops pushes with `Urgency: high`, the remaining causes are on the phone
(Low Power Mode, Focus, the home-screen app removed and re-added), not the server.
