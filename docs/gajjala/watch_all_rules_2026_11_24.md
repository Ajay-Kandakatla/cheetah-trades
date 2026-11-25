# ✅ All rules met → 👀 Watch, kept across sessions (2026-11-24)

Spec: watchall rev 2 (planner, 2026-11-24 ~23:30 ET). Tag 🟡 — display / tracking only. No rule, gate, threshold, push,
A+ logic, 🧠 list or board change. UNMEASURED.

## The ask (Ajay, verbatim, 2026-11-24 ~22:45 ET, in order)

> "Also Add every potential with all rules broke move to watch list.." · "That should be my watch list" · "Gajjals rules
> are really good at finding good stocks but his entry logic has not been working out for maximum profits.. It takes a
> while to reach profile the 100% 200% he is taking about" · "Anytime stocks qualify all his rules should be auto added
> to the Watch list so I can keep tracking them later"

## The rule in plain words

A name goes onto 👀 Watch's ✅ **All rules met** list on the minute the loop sees that it met every one of Gajjala's
rules:

- its 🚩 card reached **trigger armed** — the 🧠 tracker's `state_path` turned into (`forming`, `armed`): every rule met,
  only the break missing (the same test as the 💧 push and the 🧠 armed push), **and** that session's volume is at or
  over GG's K11 floor (`C.RULES_MIN_VOLUME = GC.K11_MIN_SESSION_VOLUME`, 1,000,000 shares; the scan row, else the
  tracker's own number);
- **or** it is a 🎯 A+ (an A+ seat on the 🤖 list, or any A+ the minute classified — also the ones with no free 🤖 seat).
  No extra volume floor for an A+.

It stays while it met them within the last `C.RULES_KEEP_SESSIONS = GC.LEDGER_SPAN_SESSIONS` (5) market sessions,
today included (the ledger's own "5d" window). ↩️ back under / ✖️ stop printed never remove it. It leaves when:

- 5 sessions pass without it meeting the rules again ("aged");
- it joins your 🚫 list ("not_eligible");
- you × it ("dismissed") — that holds for the rest of that session even if it re-arms; a later session's new
  qualification seats it again.

Never added: your own names, a name on your 🚫 list, a name you ×'d that session (on the ✅ list **or** anywhere on the
Watch — the 🤖 list's × record counts too). No cap: nothing is ever evicted from 👤 / 🎯 / 🤖. **This list never rings**
(`C.RULES_PUSH_MODE = "off"`, its own switch — not tied to the 🤖 one); the board's 🧠 / 💧 / 🎯 pushes are unchanged.

Engine: `backend/chart_maps/gajjala_watch/allrules.py` (one doc `{_id: "rules"}` in `gajjala_watch_list`), run once a
minute right after the 🤖 step under the same lease. The loop reads the 🤖 doc **before** the 🤖 step (`auto_prior`) so
the previous session's × record is still there; a fault reading it writes nothing (an unknown × never seats a name).
✅ names join the minute frames **last** (`manual + auto + rules`), so the 35 s budget falls on them first.

## Bounded back-fill

On the first step of a new session the 🤖 doc still carries yesterday (its × record intact), so **yesterday's** trackers
are read once more — a pass after 20:05, a missed evening or tonight's post-close deploy is not lost
(`backfilled: ["<yesterday>"]` in the state doc's `rules` block). **Older sessions are never back-filled**: their ×
records are gone (the 🤖 doc resets at 04:00), so a full back-fill would re-seat names you removed. After this deploy the
first step (11-25 04:00) back-fills 11-24 only; 11-18..11-23 are not read.

## ▶ Rules on a ✅ tile (2026-11-24)

Every ✅ tile carries the ▶ Rules button, so the ▶ Rules listing (`run_rules.watch_names`) is the loop's own listing
(`levels._listed`): your names, then today's 🤖 names, then the ✅ all-rules names **last** (fold-de-duplicated). Before
this fix a ✅ name answered "is not on your Watch — add it first". A fault reading the ✅ list skips only the ✅ names
(one log line); your names and 🤖 still run. A name on none of the three lists still answers "not on your Watch".

**2026-11-24 refix — once per session.** The ✅ doc records each back-filled session in `backfilled_sessions` (pruned to
the window, written with the step's one compare-and-set). A session already recorded is never read again. Before this,
a 🤖 doc left on yesterday (no entries, removals or × yesterday and none yet today, so the 🤖 step wrote nothing) made
every minute re-read yesterday's trackers and `backfilled` read `[yesterday]` all day. A read fault records nothing,
so the next minute retries; a dry step records nothing.

## Today's store (read-only container probes, 2026-11-24 ~22:50 ET)

| | n |
|---|---|
| GG5 🧠 tracker docs / distinct names | 83 / 59 |
| names armed at any time today | 31 |
| … with session volume ≥ K11 | 27 |
| … and not on your 🚫 list | 22 (6 of them your own names) |
| … of those ×'d by you today (🤖 doc `dismissed`) | 2 — BAK, GLXG |
| on 👀 at day end (🤖 9 + 👤 8) | 17 of 31 |
| never seated | 8 — 🚫 6 (HUHU MRM MEDS SCAG STAK BDMD) · under K11 1 (AMCI 171k) · BAK (armed 09:41, ×'d) |
| seated then gone | 6 — ↩️/✖️ ABTS CUE DWTX · "made_room" VIVS UCL · GLXG (➕ then you ×'d it) |
| armed for ONE 5-min pass only | 5 (AMCI, IVVD, STAK, WETO, ONFO→A+) |
| first armed outside RTH | 13 |
| armed with NO 🧠 push record | 3 — ABTS, KITT, VIVS |
| A+ `aplus_skipped` today | 0 |

Expected at the first step 11-25 04:00 (back-fill of 11-24): ≈ 14 = 22 − your 6 − ×'d BAK, GLXG (your list at 04:00
decides the 6). Steady state at N = 5: ≈ 45–56 names minus your own and your ×.

Prior measurement (the only number bearing on N): multiday study
`eod-audits/research/2026-11-18_multiday_runners/runners.csv` — median sessions_to_peak = 4; 64 of 165 runs (38.8 %) peak
after session 5 (winners only, cut at 10 sessions → a lower bound). No edge is claimed.

## HIS CALL

1. N = `GC.LEDGER_SPAN_SESSIONS` (5, today included) — or `GC.LEDGER_SPAN_SESSIONS_LONG` (10), or until GG's "fade"
   (not built). GG's words "2 or 3 days and sometimes 2 weeks" sit closer to 10.
2. 🚫 names are not seated (today 6) — shown as a count in ℹ️.
3. K11 judged on the session's LATEST volume (the 🤖 rule) — looser than the A+ (entry pass) and 💧 (its own pass).
4. × blocks the rest of that session even if it re-arms; a later session seats it again.
5. Order 👤 → 🎯 → 🤖 → ✅ (built).
6. A 🤖 seat that is also ✅ is shown once (in 🤖 while seated) and still counts toward the 🤖 18.
7. ✅ folded by default on the phone; desktop shows it after 🤖 with no fold.
8. `RULES_PUSH_MODE` "off": ✅ names never ring the 1-min cross, independent of the 🤖 switch.
9. "Anytime they qualify" also seats names that armed then failed the same day, armed for one 5-min pass, first armed
   outside RTH, or never rang a 🧠 push. Any filter on these is a rule change.
10. Live-tick cap 80 per tab: the refused tail is ✅; on the phone ✅ ticks only while open.
11. Every served word (section title, hints, ✅ chip, × title).
12. His queued multi-day "track until they fade" ask is answered only for all-rules names and only by a session count.
13. 1-min page retired → GG1 armed names do not qualify while it is off.
14. 🎯 A+ also enter ✅ (carry past the session), kind "aplus", no extra volume floor.
15. Back-fill: only the session before the deploy is read; a full 5-session back-fill would re-seat names you removed.
