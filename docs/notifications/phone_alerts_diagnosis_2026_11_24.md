# 📬 Phone alerts — read-only diagnosis (2026-11-24)

Ajay, verbatim (2026-11-24): "also i am not getting the alerts on phone"

Spec ggrun rev 2 §1.5 + §4 `phone-diag`. **Nothing was changed**: no push sent (no test ping), no pref written, no
registration removed, no edit to `push/*`, `sw.js`, a gate or the keep-set.

- Probe: `backend/scripts/push_receipts_by_device_probe.py` (pure `summarize` / `summarize_watch` / `render` + a read-only
  `main`). Tests: `backend/tests/test_push_receipts_by_device_probe_2026_11_24.py` (15).
- Run ONCE, 2026-11-24 03:44 ET, in the api container (origin/main), script piped on stdin:
  `docker exec -i -w /app cheetah-market-app-api-1 python - < backend/scripts/push_receipts_by_device_probe.py`
- Window: 7 days (11-17 04:00 … 11-23 19:36 ET), the nine `OWNER_KEEP_SET` kinds, his rows + broadcasts only.
- A registration is printed as an ordinal letter (by `created_at`) + device word + registration date. No endpoint, key,
  hash, push id or email is printed.
- One exception to "reads only through `push.subs`": the probe never calls `list_subscriptions`, because its one-time
  backfill can write a pref. "Targetable now" is read straight off each registration's `prefs.<kind>`. `_get_db()` may
  create its two subscription indexes once per process. That is an index, not a row.

## The numbers

His four Web Push registrations. All have quiet hours off, and all had prefs last written 11-13 01:29 ET:

| reg | device | registered | accepted (7 d) | rejected | receipts | newest receipt ever |
|---|---|---|---|---|---|---|
| A | iPhone | 10-08 | 377 | 0 | **0 / 377 (0 %)** | **10-23 16:05 ET** |
| B | iPhone | 10-26 | 377 | 0 | 222 / 377 (59 %, CI 54–64 %) | 11-23 18:31 ET |
| C | Mac Chrome | 11-06 | 377 | 0 | 310 / 377 (82 %, CI 78–86 %) | 11-23 19:36 ET |
| D | Mac Chrome | 11-12 | 377 | 0 | 377 / 377 (100 %) | 11-23 19:36 ET |

The push service accepted every one of 1,508 targets (sent = total on every row; failed 0). No row in the window
predates receipts, no row had zero targets, and no target pointed at a registration that has since been removed.

## Q1. Is one iPhone registration dead?

**Yes, as far as receipts can show.** Registration A (iPhone, registered 10-08) has posted **0 receipts on 377 accepted
targets** (Wilson 95 % CI 0–1 %), on every day and every kind. Its newest receipt in all of `push_history` (90-day TTL) is
**10-23 16:05 ET**. Apple's push service still accepts it: 0 rejected, and no 410 since, so the sender has never removed it.

## Q2. The other iPhone (B): which hours and kinds lose receipts?

- **By hour (ET).** The 09h hour is the worst: **67 / 143 (47 %, CI 39–55 %)**. All other hours together: **155 / 234
  (66 %, CI 60–72 %)**. The two intervals do not overlap. Also low: 17h 7 / 18, 18h 7 / 13, 19h 0 / 4, 21h 0 / 2.
  For comparison: 10h 27 / 49, 11h 17 / 22, 13h 15 / 17, 15h 10 / 12.
- **By kind (7 d).**

  | kind | B | Mac C |
  |---|---|---|
  | `luk_setup` | 43 / 107 (40 %, CI 31–50 %) | 81 / 107 |
  | `gajjala_potential` 🧠 | 98 / 167 (59 %, CI 51–66 %) | 139 / 167 |
  | `long_term` | 27 / 36 | 34 / 36 |
  | `gajjala_setup` 🚩 A+ | 21 / 27 (78 %, CI 59–89 %) | 22 / 27 |
  | `gajjala_1m_*` | 21 / 23 | 21 / 23 |

- **🚩 A+ is not worse than 🧠 over the week**: 78 % vs 59 %, though the intervals overlap. On 11-23 alone it was A+ 2 / 6
  (CI 10–70 %) vs 🧠 19 / 32. Six rows is too few to call.
- **By day**: 11-17 61 / 88 · 11-18 21 / 57 · 11-19 47 / 82 · 11-20 50 / 82 · 11-22 3 / 3 · 11-23 40 / 65.
- **Delay** (receipt `shown_at` minus row `ts`): median 0 s, max **7,162 s**, which is longer than the 3,600 s TTL.
  Mac C max 74 s, Mac D max 87 s.
- **Missing receipts are not iPhone-only.** Mac Chrome C misses 18 % (67 / 377). Mac Chrome D misses none.

## Q3. What a missing receipt can and cannot prove on iOS

`frontend/public/sw.js:38-40` calls `showNotification(...)`, and only after it resolves does it call `sendReceipt`
(`:62-74`). A failed receipt is swallowed.

- **A receipt proves the notification was shown.**
- **No receipt proves only that the POST did not land.** It does NOT prove "not shown". On iOS the worker can be stopped
  after `showNotification` resolves and before the `fetch` finishes. `getSubscription()` or `loadConfig()` can also fail.
  If the Cache-API config entry is gone, `loadConfig` falls back to `https://<host>:8000` (`:109-122`), which may not be
  reachable from the phone. Any of these gives "shown, no receipt".
- For A (0 of 377), "not shown" is **not proven**. A could be a second, abandoned web-app instance on the same phone
  whose subscription Apple still accepts. A could also be a live instance whose receipts never post. Only HIS CALL 17
  tells these apart.

## Q4. `gajjala_si_cross` (🩳, the ninth keep-set kind)

All four registrations have it OFF: **0 targetable**, while the other eight kinds have 4 each. No `gajjala_si_cross` row
exists in the window, so no claim has fired yet. The first one would settle `no_target`. Fixing this is the main
session's runbook step (spec §4 `main-session`, `scripts.owner_prefs_apply` dry, then `--apply`, then dry again). This
package did not do it.

## Q5. Transport as it is (read, cited, not changed)

`backend/push/sender.py:56-86` (`_send_one`):
- `webpush(..., ttl=3600)`.
- No `Urgency` header is passed, so the push service applies its default.
- Any exception carrying "410" or "expired" removes the registration.

Nothing has removed A, because Apple has not refused it.

## Q6. The Watch's 1-min cross pushes (ride `gajjala_potential`, `gajjala_watch/constants.py` `PUSH_KIND`)

Last session, 2026-11-23:
- `gajjala_watch_alerts` claims by state: cross_claimed 0 · **cross_pushed 6** · cross_no_target 0 · cross_failed 0.
- The tiles' held reasons that session: under_floor 3 · suppressed_auto 25 · pushed 6. Another 68 held marks on the tiles
  are from older sessions.
- The Watch loop's `latest` state: 11-23 20:00 ET, 30 names, reason None.

None of the six pushes were held for `no_target` or `failed`. Each rode `gajjala_potential` to all four registrations.

## Q7. Is today's session writing keep-set rows since 04:00 ET?

**Not answerable from this run.** The probe ran at 03:44 ET, before the 04:00 ET pass opens (`GC.PASS_OPEN_ET`), so
"today 11-24: none" is expected and proves nothing. The last session wrote up to the end:
- the last keep-set row was `gajjala_setup` at 11-23 19:36 ET;
- the last `gajjala_potential` row was at 19:31;
- the Watch loop ran until 20:00.

The `gajjala_1m_*` kinds last wrote on 11-17, which is expected: the 1-min page was retired on 11-18.

## PROVEN

1. The server side delivers. The push service accepted 1,508 of 1,508 targets in 7 days. No gate, pref (apart from 🩳)
   or quiet hours stops a keep-set push from reaching his four registrations.
2. iPhone registration A (10-08) has posted no receipt since **10-23 16:05 ET**: 0 of 377 accepted targets this week.
3. iPhone registration B (10-26) reports 59 % (222 / 377). It is worst in the 09h ET hour (47 % vs 66 % for the other
   hours, non-overlapping intervals) and on `luk_setup` (40 %).
4. 🩳 `gajjala_si_cross` targets 0 devices.
5. The same rows reach Mac Chrome D 100 %, so payloads and the sender are fine for a device that reports.

## NOT PROVEN

1. Whether A's pushes are shown on the phone. "No receipt" is not "not shown" (Q3).
2. Why B misses 41 %. Possible causes: shown with the receipt POST lost, the phone offline or asleep past the TTL,
   iOS throttling a burst at the open, or replacement by `tag`. None is proven.
3. Whether A and B are the same physical phone.
4. Whether today's session (11-24) writes rows (Q7: probe ran before 04:00 ET).
5. The cause of the 7,162 s maximum delay on B. It could be device clock or delivery after the TTL.

## Candidate remedies (none applied here)

| # | remedy | tag |
|---|---|---|
| 1 | Run `scripts.owner_prefs_apply` dry, then `--apply`, then dry again, to turn ON `gajjala_si_cross` on the four registrations (expect `False→True` ×4 and nothing else) | **runbook (main session)** |
| 2 | After 04:00 ET, one count of today's keep-set rows, to answer Q7 | **runbook (main session)** |
| 3 | One test push to each registration while he watches the phone: tells a dead registration (A) from a missing receipt | **HIS CALL 17** |
| 4 | Remove registration A (no receipt since 10-23) once #3 shows nothing arrives on it | **HIS CALL 18** |
| 5 | An `Urgency: high` header and/or another TTL than 3,600 s on the keep-set kinds | **HIS CALL 19** |
| 6 | Re-send / escalate a push no device showed | **HIS CALL 20** |
| 7 | On his side, a question rather than code: is the Pounce Home-Screen app installed once or twice on the iPhone? Is Focus / notification summary on for it at 09:00? | **HIS CALL** |
