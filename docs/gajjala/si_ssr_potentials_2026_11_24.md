# ⛔🔒🩳 SI / SSR / Reg SHO names → 🧠 potential (2026-11-24)

SPEC sissr rev 2, WP be-pass. Tag 🔴: SI, SSR and Reg SHO are not GG's playbook. GG's own detectors and the existing 🧠
gate decide every potential. **UNMEASURED.**

## The ask (Ajay, verbatim)
- ~23:20 ET: "Make this new routine 1. Scan Short interest tabs sotkcs that become potentials also and also look for new
  SSR stocks 2. Then potentials to be alerts sooner - add them to watch list and give them a time stamp of the day"
- ~23:35 ET: "Days past little bit like AKAN is what I am mainly looking for many were so confident on SSR.."

## What the 5-minute pass does now
`chart_maps/gajjala/si_ssr_names.py` is a third add source on the 🚩 pass (the 🎪 pattern). Each cron pass reads
stored Mongo data only, never an outside call:
- ⛔ SSR today and ⛔ SSR on a recent session come from `ssr.recent_triggers`. The window is
  `SSR_RECENT_TRIGGER_DAYS = SSR_FOLLOWING_TRADING_DAYS` (HIS CALL #1).
- 🔒 past close-out comes from `reg_sho.payload(kick=False)` + `reg_sho.past_closeout_text`. Any item the engine
  reads `state "on"` counts, a stale list's item included (refix 2026-11-24: the earlier "not stale" filter was not in
  the spec; 0 stale items on 11-24).
- 🩳 High SI comes from `high_si.classify` on this pass's floats.

**Tags.** Every name the pass reads gets `ctx["si_ssr"]` = {keys, lead, text, glyphs, ssr_day, triggered_on, sho_text,
hsi_text, add}. The lead order is ⛔ recent > 🔒 > ⛔ today > 🩳 (HIS CALL #9). An untagged name gets no key, so its doc is
byte-unchanged.

**Lead order — open, HIS CALL #9 (refix 2026-11-24).** A trigger dated today is `ssr_today`, so it sorts AFTER 🔒. DBGI
on 11-24 (⛔ 11/24 day 1 + 🔒) therefore reads "🔒 day 10 past close-out · ⛔ SSR 11/24 · day 1" (live probe). The spec's
verification line expected "⛔ SSR 11/24 · day 1 · 🔒 …", which the spec's own `SOURCE_KEYS` order cannot give. The code
follows `SOURCE_KEYS` and the HIS CALL #9 words; flipping DBGI means moving `ssr_today` ahead of `sho_past` in
`SOURCE_KEYS` (or counting a re-trigger as recent), and that is his call. Nothing was changed for it.

**Adds.** An off-list ⛔ / 🔒 name is added only if it passes two checks:
- GG's add check (`trader_names.candidate_row`: snapshot, dated print, prior close, instrument rule, price band);
- `ADD_MIN_VOLUME = GC.SCAN_MIN_VOLUME` on the snapshot.

The bound is `ADD_MAX_NEW_PER_PASS = GC.FLOAT_MAX_NEW_PER_PASS` new adds per cron pass, with `ADD_ON_OPEN = False`
(HIS CALL #10). Order: source rank, then volume (desc), then symbol. Names past the bound are counted `queued` and land
on a later pass. A name already on the list is only tagged, never given a second row. An add stays listed for the
3-session carry and stays an add (held) for all of it.

**C1 — adds never ring.** Every add failed GG's own ≥25% scanner rule, so:
- run.py hands the 🎯 A+, 🧪, 💧, 🔀 and 🩳🔀 engines the reads / frames WITHOUT the adds. With no add read, they get the
  same dict objects.
- 🧠 tracks an add, stamps it and holds it `si_ssr_add` at any volume (`potential.SI_SSR_HELD`, counted `si_ssr_held`).
  The 📈 row says "held: added ⛔🔒 name — not on GG's list".
- An add that later becomes GG's own name rings once, only while its structure is unbroken (eligible's ADD_HELD branch,
  unchanged).
- Ringing adds is HIS CALL #6.

**GG's own tagged names.** These ring through the UNCHANGED 🧠 gate, at the same minute as before, with the source
right after the ticker in the title (2026-11-25 review, below): "🧠 AKAN · ⛔ SSR 11/23 · day 2 · ➖ Horizontal Fade —
trigger armed · UNMEASURED".

**The stamp (the Watch's day stamp).** `potential.track` writes `si_ssr` ONCE, at the first pass where the name is tagged
AND a potential. It holds the tag plus first_at, first_at_et, first_kind, setup, session and potential_first_seen_et
(the tracker's earlier 🧠 time, C4). An add also gets `si_ssr_add: True` on insert only.

**Pass doc.** `si_ssr` = {added, tagged, kept, queued, skips, names, on_open, faults, push_held}, plus the counts
`si_ssr_*`. With `Deps.si_ssr_names` None (tests, replays, dry runs) no key appears anywhere.

## The open (judgement call, 2026-11-24)
The cron path is wired (`_cron_deps`). `main()`'s on-open Deps line is unchanged: three pins in other WPs' tests freeze
that literal. So an open pass reads no tag source and adds nothing. Instead it CARRIES each read doc's last
`ctx["si_ssr"]` forward, so a tag never blinks off between cron passes and the open's 45 s stays GG's. Wiring the reader
on the open is a pin widening for the main session.

## Measured / approximate
`backend/scripts/gajjala_si_ssr_replay.py --date D --out F` is read-only and APPROXIMATE (the 20:30 snapshot at every
clock, no Yahoo float, fresh tape not modelled). The plan's estimate for 2026-11-24 is ~12 reach a 🧠 potential and ~5
arm. Never quote it as measured.

## Guards widened (dated reasons in each file)
- `test_reg_sho_closeout_day_2026_11_24.py` `DISPLAY_READERS` += si_ssr_names.py
- The potall `PUSH_PATH_SHA` gets new hashes for `potential.run_pass` / `track` / `compose`. `eligible`,
  `potential_kind`, `alerts.run_pass` and `stages.steps` are unchanged (re-pinned in
  `test_gajjala_si_ssr_potential_2026_11_24.py`, plus `vol_dried.run_step` / `audited_pass.run_step`).
- Refix 2026-11-25 (verifier HIGH, five new reds) — each widened with a dated reason and a NEGATIVE pin:
  - `test_gajjala_all_table_si_2026_11_16.py` S10 allow-list += si_ssr_names.py (it imports only `short_interest.ssr`
    / `.reg_sho`, lazily, and reads the 🩳 block only through `HS.si_blocks`).
  - `test_reg_sho_threshold_2026_11_22.py` display-only list += `REG_SHO_READERS_2026_11_24` (si_ssr_names.py; its
    `RSH` calls are only `payload(kick=False)` and `past_closeout_text`).
  - `test_gajjala_bar_close_2026_11_09.py` cron Deps += `si_ssr_names=SSN.default_reader`.
  - `test_gajjala_promo_names_2026_10_29.py` `ADD_HELD == TRADER_HELD + PROMO_HELD + SI_SSR_HELD`.
  - (`test_gajjala_watch_hook_2026_11_15.py` is back to main's list on 2026-11-25: with the interlock dropped,
    si_ssr_names.py no longer names the Watch at all.)
  - potall `PUSH_PATH_SHA` (`test_gajjala_pot_all_2026_11_24.py`, re-pinned 2026-11-25 after the rebase onto
    7b7b2117 and the 🩳 title lead):
    `potential.run_pass` 629c24a61435d57743a7be44ed6f30ad15adde584b3d674ae9d99397354f49a0,
    `potential.track` 6fb63d1f722d8ad7aba6753c746edbc1128708fc2b275e4179eab5f0c20c5fe5,
    `potential.compose` 26e821c4be8243d23882e8b3b8ecfc4ad881cfb57ec24102f80d53d13a3ca9a6.

## Land-order interlock (refix, 2026-11-24 late)
The critic found a shipping blocker: the live 👀 Watch 🤖 auto (`gajjala_watch/auto.py`) seats every 🧠 potential and
🎯 A+ of a LISTED read, and an added ⛔ / 🔒 name is listed and read. If this package lands before be-watch's C2 filter
(`auto.py` `_si_ssr_adds` via `si_ssr_names.is_add`), an add would take 🤖 / 🎯 seats, and an added A+ would evict GG's
oldest potential. So `si_ssr_names.watch_keeps_adds_out()` reads `auto.py`'s source (static `ast`, never an import:
auto imports run) and opens only when `_si_ssr_adds` is defined at module level AND called. Until then `run_step` adds
nothing: every eligible name is counted `queued`, the block carries `adds_held: "watch_filter_missing"`, and the tags
on GG's own listed names still serve (their 🧠 rings with the source lead as designed). A missing, unreadable or
unparsable file keeps the adds held (fails closed). It flips by itself when be-watch lands, with no switch to forget.
The replay script calls `resolve` directly, so it still shows the post-be-watch landing clocks.

**2026-11-25 — DROPPED.** be-pass and be-watch now ship in ONE commit (the branch is rebased onto 7b7b2117 with the
Watch's C2 filter `auto.py` `_si_ssr_adds` in the same tree), so the static `auto.py` read, `watch_keeps_adds_out`,
`WATCH_FILTER_PATH` / `WATCH_FILTER_FN` / `WATCH_HELD`, `resolve(adds_on=)` and `run_step(watch_ready=)` are removed,
with their tests. The C2 filter is pinned by `test_gajjala_watch_si_ssr_2026_11_24.py`; a test pins the interlock gone.

## 🩳 in every 🧠 alert title (2026-11-25)
Ajay 2026-11-25 ~00:25 ET, verbatim: "I do need a mention of High SI stock when alerting for potential though..".
Before, the 🧠 title led with the name's FIRST source only (`tag_block` "lead"), so a ⛔ or 🔒 name that was also 🩳
lost its 🩳 from the title (it sat in the body). Now `potential.title_lead(tag)` hands `compose` the tag's "text":
EVERY source's words, joined by `si_ssr_names.LEAD_JOIN` in `SOURCE_KEYS` order (⛔ recent · 🔒 · ⛔ today · 🩳). The 🩳
words are `high_si.tier_chip` (tier + short-interest %). Examples (from `test_gajjala_si_ssr_title_hsi_2026_11_25.py`):
- ⛔ + 🩳 (AKAN-like): `🧠 AKAN · ⛔ SSR 10/12 · day 2 · 🩳 32.4% short interest · High · 🚩 Bull Flag — trigger armed · UNMEASURED`
- 🔒 + 🩳: `🧠 AKAN · 🔒 day 6 past close-out · 🩳 32.4% short interest · High · …`
- 🩳 only: `🧠 AKAN · 🩳 32.4% short interest · High · 🚩 Bull Flag — trigger armed · UNMEASURED`
- no tag: `🧠 AKAN · 🚩 Bull Flag — trigger armed · UNMEASURED` — byte-identical to before.
The body no longer repeats the sources (the title carries them). `compose` was unchanged here (it moved the lead after the ticker in the review fixes below); only `run_pass` hands the
fuller lead. The gate, the ring minute, the add hold and the one-ring-per-name rule are unchanged; an unread or
unclassifiable SI block is never tagged 🩳. **No title cap:** the ask said to shorten ⛔ / 🔒 rather than drop 🩳 when
over the house push-title cap, but no named title cap exists in `push/` or `potential.py`, so none was invented and
nothing is clipped — 🩳 is never dropped. A test fails if a `*TITLE*_MAX/CAP/LIMIT/LEN/CHARS` constant is ever added
there, so the shortening rule gets built against it then. UNMEASURED.

## Review fixes (2026-11-25)
The verifier's three medium defects and one low/medium, on this branch:
- **⚡ break watch never follows an add.** `store.break_watch_docs` now drops tracker docs with
  `si_ssr_names.TRACKER_ADD_FIELD` (`si_ssr_add: True`). Before, an armed ⛔🔒 add was recorded "⚡ break seen (shadow)",
  would ring if `GAJJALA_BREAK_PUSH_MODE` went live, and competed for the `WATCH_MAX` seats with GG's own plans.
- **The ticker leads the 🧠 title.** A 119-character lead (⛔ + 🔒 + 🩳 with float words) in FRONT pushed "🧠 AKAN" off
  the lock screen. `compose` now writes `🧠 {sym} · {lead} · {setup} — {kind} · UNMEASURED`; every source, 🩳 included,
  is still in the title. The examples above read with the ticker first, e.g.
  `🧠 AKAN · ⛔ SSR 10/12 · day 2 · 🩳 32.4% short interest · High · 🚩 Bull Flag — trigger armed · UNMEASURED`.
  **Where the lead sits is HIS CALL.**
- **Fail-open closed.** On an unreadable scan window, `run.py` read this pass's rows only, so an add carried from an
  earlier pass (listed, no row this pass) went un-held to 🎯 / 🧠 / 💧 / 🧪. `run._carried_adds` now also holds a listed
  name with no row this pass whose stored read doc is an add (`si_ssr_names.is_add`). An unreadable read doc is not an
  add, so GG's own names are never held by a fault.
- **NOT fixed — HIS CALL:** no cap on the TOTAL number of added names. The bound of `ADD_MAX_NEW_PER_PASS` is per pass;
  adds stay listed `STAY_LISTED_SESSIONS`. The number is his; none was typed. Also open (low): an add that becomes GG's
  armed qualifier the same session lands in ⛔🩳🔒, not ✅ (`allrules._is_add_doc` reads the insert-only tracker flag).
Tests: `backend/tests/test_sissr_review_fixes_2026_11_25.py`.

## Integration (2026-11-25)
- Rebased onto origin/main 7b7b2117 (🧠 all-tabs 7540094b, 🔕 clean alerts fc2c3d44, ✅ watch-all-rules 7b7b2117).
- contracts.mjs: the sissr block strips `#` comments before reading `RULES_KINDS` (the live tuple's comments carry
  parentheses); the ✨ sits past index 100, right above the ✅ entry (the 💧 / ✅ way), so no index pin moves; the ✅
  block's `SECTIONS_FOLDED_DEFAULT` pin allows `("rules", "sissr")`.


## 2026-11-25 — off-list adds ship paused (`ADD_ON = False`)

The review found no TOTAL cap on live adds: the bound is `GC.FLOAT_MAX_NEW_PER_PASS` new adds per pass, and an add stays
listed for `GC.STAY_LISTED_SESSIONS` sessions, so a heavy SSR day could put hundreds of names on the pass. A total cap is
Ajay's number, so `si_ssr_names.ADD_ON` ships `False`: eligible off-list names are counted as `queued` and not read.
GG's own listed names keep every tag (⛔ / 🔒 / 🩳), the 🩳 mention in every 🧠 title, and the 👀 Watch stamp. Turning
adds on = `ADD_ON = True` plus his cap. Pinned by `tests/test_gajjala_si_ssr_adds_off_2026_11_25.py`.
