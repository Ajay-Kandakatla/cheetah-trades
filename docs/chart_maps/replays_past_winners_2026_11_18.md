# 🏆 Past winners on 🎬 Replays (2026-11-18)

Ajay 2026-11-18 ~21:45 ET, verbatim: **"can you work on todays videos and also..  Winners in general from the past"**.

"Today's videos" of OUR rings stay with the nightly task (`videos/<date>/`). This section is **winners in general**:
market-wide big movers we may never have rung, today and in past sessions, plus the 15 multi-day runner reels.
**Owner only. Hand-picked winners (survivorship): descriptive, UNMEASURED, not a signal.** No rule, gate, threshold,
push or trade changes. Spec: scratchpad `pastwinners/spec.md` §3.5–§3.6 (WP-APP). The reels and the finder are WP-VID
(`eod-audits/replays/replay_winners.py`, `eod-audits/research/2026-11-18_past_winners/`).

## Placement (Rule #5)
~500 rows is long, so the section sits at the bottom of 🎬 Replays, collapsed, rows are text until tapped, one video at
a time. Nothing is fetched on the tab's mount; opening the section sets `?winners=1` and makes ONE GET.

## Routes (both `Depends(require_primary_admin)` — the ONE owner gate; anyone else → stealth 404, no header → 401)
| Route | Answer |
|---|---|
| `GET /chart-maps/replays/winners` | `store.winners_payload`, `Cache-Control: no-store` |
| `GET\|HEAD /chart-maps/replays/winners/video/{sub}/{name}` | the bytes of a LISTED mp4 under `videos/<sub>/`, Starlette `FileResponse` + `VIDEO_HEADERS` (identity + private) |

`sub` must be exactly `winners` or `multiday` (`C.WINNER_SUB_KEYS`); anything else (a date, `..`, `phone`, `_bars`,
`Winners`) → 404. The day routes (`/chart-maps/replays[?date=]`, `/chart-maps/replays/video/{day}/{name}`) and the day
listing are unchanged — a golden test pins `payload` / `dates` / the HTTP body byte-for-byte with both folders present.
`api.py` now declares FOUR routes.

## Accept rule (per `.json` in `videos/winners/` and `videos/multiday/`, non-recursive)
The day folder's rule (`_parse_day`) with the window decided by `winner_window_ok`:
- `winners/` → `window == FULL_DAY_WINDOW` ("04:00-20:00 ET", his 11-16 rule; one session).
- `multiday/` → `window` starts with `MULTI_WINDOW_PREFIX` = `FULL_DAY_WINDOW + " x "` ("04:00-20:00 ET x N sessions (…)"):
  every session of the reel runs 04:00–20:00.
- Else `skipped_window`. `jobs.json`, `runners.json`, `winners.json` are never read. `multiday/phone/` is never listed.
- `file` = the json's stem + `.mp4`, present in the same scandir (a `.part.mp4` render is not listed until the `mv`).
- Each card is built inside `try … except CARD_ERRORS` → one bad sidecar is one `skipped_bad`, never a 500. A card is
  refused when: `symbol` not a non-empty str; `day` / `days[]` not `YYYY-MM-DD`; `speed` / `minutes` not finite numbers;
  `close_gain_pct` not a finite number (NaN, a string, missing); `spike_print` not a bool; `spike_print` true without a
  finite `spike_x > 0`; a `winners/` `pick` not `plus100` / `today_top`; a `today_top` reel without a positive int
  `today_n` (judgement call: no sensible words without it).
- The 15 multi-day sidecars need WP-VID's `mbackfill` (adds `kind, day, close_gain_pct, high_pct, spike_print, spike_x`);
  until then they read `skipped_bad` (measured on the host folder 2026-11-18: 15 skipped_bad, 0 listed).

## The card (every word composed from constants + sidecar NUMBERS)
`file, sub, src (…/winners/video/<sub>/<file>), symbol, kind (from the FOLDER), kind_text (single-day / multi-day),
date, label_date ("Thu 2026-11-12"), days, days_text (single: the day; multi: "A → B · N sessions"), close_gain_pct,
gain_text ("+120% on the close" / "+300% best close vs the day before" — U+2212 minus), high_pct (null when not finite),
high_text ("+180% high" / "+492% run high"), spike_print, spike_text ("⚠ high more than 2× the close — a spike print?",
only when spike_print is true), pick_text ("top N mover of its day (high under +100%)" for a today_top reel; "your
example — not a +100% run" for a forced multi-day reel), speed, speed_text, minutes, length_text`.

The headline is ALWAYS the close (`close_gain_pct`). The multi-day sidecars' legacy `gain_pct` is HIGH-based and is
never read. Sidecar free text (`label`, `ask`, `why`, `category`, the `forced` sentence) is never served.

Payload: `title, tab, state (no_folder / empty / ready), text, note (WINNERS_NOTE, built from GC.SA_BIG_RUNNER_PCT,
GC.SCAN_MIN_VOLUME, GC.SCAN_MIN_PRICE, GC.SCAN_MAX_PRICE), window, window_note, summary_text ("N videos · a single-day ·
b multi-day"), counts {videos, single_day, multi_day, skipped_window, skipped_bad, no_sidecar}, groups [{date, label,
videos}]` — groups by date DESC; inside a date by close gain DESC, then symbol, sub, file. NaN scrubbed (`_scrub`).

## Frontend
`lib/replays.ts`: `RP_WINNERS_PATH`, `RP_WINNERS_PARAM` (`winners`), `RP_WINNERS_TITLE` (== backend `WINNERS_TITLE`),
the payload types, `rpWinnerSrc` (only `…/winners/video/` srcs), `rpWinnersParams` (keeps `tab` / `date`).
`components/ReplaysPastWinners.tsx`: the collapsed header button (the one FE word), the lazy GET, states loading /
failed (`FETCH_FAILED`) / no_folder · empty (served text) / ready (served note, window note, summary, per-date served
label, one text row per card: ticker + served chips + ▶). Exactly one video element (`controls preload="metadata"
playsInline`; never autoplay / muted / poster / download) under the tapped row. `ReplaysBoard.tsx` mounts the section
AFTER `.rp-board` in every state, so the board's one GET and its text are unchanged. `styles/replays.css`: `.rpw-*`
rows wrap, `min-width: 0` on every flex child (430 px).

## Tests
- `backend/tests/test_replays_winners_2026_11_18.py` (103).
- `frontend/src/lib/replays.winners.test.ts`, `src/components/ReplaysPastWinners.test.tsx`,
  `src/components/ReplaysPastWinners.phone.test.tsx`.

## HIS CALL (defaults built; nothing decided as a rule)
1. Winner = the day's HIGH ≥ +100% (`GC.SA_BIG_RUNNER_PCT`) over the prior close — or on the CLOSE?
2. Floors reused from GG's scanner: volume ≥ `SCAN_MIN_VOLUME`, prior close in [`SCAN_MIN_PRICE`, `SCAN_MAX_PRICE`].
3. `WINNERS_CAP = 480` and `TODAY_TOP_N = 5` are MINE.
4. Spike flag = high > 2 × that day's close (it also flags real fades).
5. Placement: bottom of 🎬 Replays, collapsed, text rows, one video at a time, no paging.
6. The 10 phone copies in `videos/multiday/phone/` are not listed.

## 2026-11-22 — 🏆 past-winner tag on the cards

Ajay 2026-11-22, verbatim: **"MEDS was a part winner that went up after hours.. Please actually add a past winner tag in
our new ones looks for past winnings please if found again.."** (MEDS: 🏆 single-day 09-15 +87% and 09-16 +275% on the
close; multi-day run 09-14 → 09-16.)

- **ONE pure index** — `store.past_winner_index(cards)` over the ACCEPTED 🏆 cards from `read_winner_sub` (the same accept
  rule; malformed / window-skipped / mp4-less sidecars, `jobs.json` / `winners.json` / `runners.json` and the
  `multiday/phone/` copies never feed it). symbol (exact, upper-case as served) → `{day, kind, close_gain_pct, file, sub}`
  newest first. The headline number is `close_gain_pct`; the legacy HIGH-based `gain_pct` is never read.
- **No look-ahead.** A win's `day` is the session it ENDED (single-day: its day; multi-day: the run's LAST session). A
  day-folder card is tagged only by wins that ended strictly before the folder's session; a 🏆 card only by wins that
  ended strictly before its own FIRST session ("won before"). Same day or later → never.
- **Served fields** (only when there is at least one such win — no key otherwise): `past_winner` (at most
  `PAST_WIN_MAX` = 3, each with a served `text`, e.g. "🏆 past winner 09-16 +275%", a multi-day entry adds "multi-day";
  on a 🏆 card "🏆 won before 09-15 +87%"), `past_winner_count`, `past_winner_more_text` ("+N more" or null).
- **Cache:** the index is cached per root by the identity of the two cached sub listings (it rebuilds only when a
  winners / multiday folder key moves); the cached day listing and winner listings are never mutated (the tag is added
  to copies at serve time).
- **Frontend:** `rpPastWinChips` (lib/replays.ts) → served chips on the day card (`.rp-chips`) and the 🏆 row
  (`.rpw-chips`), class `.rp-pastwin` (min-width 0, wrapping, 430 px). **Since 2026-11-22 the day-card chip is a
  link** to that win's reel in the 🏆 section (`?winners=1&sym=<SYM>&reel=<sub>/<file>`, opened at the served peak
  minute; see `replays_past_winner_jump_2026_11_22.md`). "+N more" and the "🏆 won before" chips on a 🏆 row stay text.
- The 11-18 day-listing GOLDEN was re-pinned: byte-identical with the `past_winner*` keys stripped; only the cards whose
  symbol won before carry them.
- A tag, not a gate: no push, no rank, no filter, nothing on 🚩 Gajjala's tab. Descriptive, UNMEASURED.
- **Review fixes (2026-11-22, same day):** ONE entry per run — a single-day win whose day sits inside a LISTED
  multi-day run's days (same symbol) is that run's move, so only the run is listed (MEDS 09-15 / 09-16 inside 09-14 →
  09-16, RETO 09-15, GP 11-12 inside 11-11 → 11-17); the same reel twice lists once; `past_winner_count` and "+N more"
  count runs. A run that has not ended before the card's session is not listed and absorbs nothing. Order: newest first
  by the run's last day, a same-day tie by the higher close gain. Dates `MM-DD`, `YYYY-MM-DD` when the win is from
  another calendar year than the card's day. The renderer's frame tag (`eod-audits/replays/replay_video.py`
  `past_wins`) applies the same accept rule, the same one-per-run rule, order and dates, and `close_gain_pct` (never
  the HIGH-based `gain_pct`).
- Tests: `backend/tests/test_replays_past_winner_tag_2026_11_22.py` (43); `frontend/src/lib/replays.pastwin.test.ts`,
  `frontend/src/components/ReplaysPastWinTag.test.tsx`.

## 2026-11-22 — 🏆 by setup (🎾 first) and by time of the peak

Ajay 2026-11-22, verbatim: **"can you categorize past winners like some are kiss and fly based and some might be VCP
based some might be horizontal faded.. Do we have those metrics? also reversal squeeze is mainly what I look for."** →
**"yes please"** (group / filter the 🏆 list by setup, 🎾 first). On the first-hour runners (peak 09:30–10:30, "drop
right after first hours it very volatile"): **"dont't remove but add a tag but sort by EOD and Intraday ones on the
top"**.

- **Source = the labeller, read only.** Each single-day sidecar carries two optional keys written by
  `eod-audits/research/2026-11-22_winner_setup_labels/label_winners.py` (`setups`: primary, class, chips,
  stopped_before_peak, …) and the time-of-day study (`timing`: bucket `eod` 15:00–20:00 / `intraday` 10:30–15:00 /
  `first_hour` 09:30–10:30 of the 09:30–20:00 peak minute ET, `null` when no 09:30–20:00 bars). The server computes no
  setup and no bucket (one engine). Multi-day reels carry no label (the labeller writes none; a stray key is ignored).
- **Defensive parse** (`store._setup_fields` / `_timing_fields`): an unknown primary, an unknown class, a primary on a
  no-setup class (e.g. 🎾 on "🎾 float-gated") or a setup class without a primary, a chip that is not a house setup, a
  chip on a no-setup class, a non-bool `stopped_before_peak` (NaN included), `stopped_before_peak: true` with no primary,
  an unknown bucket, a bucket without an `HH:MM` peak, or a bucket that disagrees with its own peak minute
  (`C.WIN_TIMING_BUCKETS` == the labeller's `TIMING_BUCKETS`, lower bound in, upper out; a test pins equality with
  `label_winners.py`) → that label is served ABSENT and counted in `counts.skipped_label` (one per bad label). The card is never dropped, never a 500,
  never NaN. A missing key, or a labelled `bucket: null`, is absent but NOT counted.
- **Served per card:** `setup` (the primary key, `"none"` for a labelled reel with no Gajjala primary — 🎾
  float-gated / none / no peak — or `null` when unlabelled), `setup_text` (the 🚩 `GC.SUBS` words, never retyped:
  "🎾 Reversal Squeeze", "🌀 Intraday VCP", "💋 EMA Kiss & Fly", "🚩 Bull Flag", "➖ Horizontal Fade"; "no Gajjala
  setup"), `setup_class` + `setup_class_text` (`WIN_CLASS_WORDS`; null for "none" — the setup words already say it),
  `setup_chips`, `setup_chips_text` (the OTHER setups armed / A+ that day, "also 🎾 Reversal Squeeze"),
  `stopped_before_peak` + `stopped_text` ("⛔ stopped before the peak", only when true), `timing` + `timing_text`
  ("🌙 end of day (peak 16:02)", "☀️ intraday (peak 11:00)", "🌅 first hour (peak 09:41)").
- **🎾 float-gated is never a 🎾 count** — the labeller serves it with `primary: null`; it files under "no Gajjala
  setup" and its class words say "not a 🎾 label".
- **Order:** superseded the same day by one row per stock (below) — the timing order now orders the ROWS.
- **Filter row:** served `setups` = `[All, 🎾, 🌀, 💋, 🚩, ➖, no Gajjala setup]` with counts of ROWS (below). The FE
  disables a 0-count chip and remembers the pick in `localStorage` (`rp_winners_setup`, try/catch; a key the server no
  longer serves, or serves with count 0 → All). 📱 430 px: `.rpw-filter` wraps, `.rpw-fchip` min-width 0 + wrapping text.
- **Judgement calls (MINE, flagged):** the setup words are the existing `GC.SUBS` words (the house rule "setup words
  never retyped", pinned by `test_NEGATIVE_setup_words_are_never_retyped_in_constants`) rather than the spec's
  sentence-case spellings; the class words and the "also …" chip words are mine.
- **Review fixes (same day):** (a) the 🎾 filter also passes a reel whose `setup_chips` hold `reversal_squeeze` beside
  another primary (16 reels; `C.WIN_CHIP_MATCH` — 🎾 only); a float-gated reel carries no chip, so never a 🎾 count.
  (b) every label word says "peak", never "high": the card's "+X% high" chip is the 09:30–16:00 day bar and differs from
  the 09:30–20:00 peak minute on 63 cards. (c) the parser rejects `stopped_before_peak: true` with no primary and a
  bucket that disagrees with its `peak_t` (measured on the host folder 2026-11-22: 0 such labels). (d) a remembered
  filter pick the server serves with count 0 falls back to All.
- A LABEL, descriptive, UNMEASURED: no gate, no push, no rank of setups, no win rate.
- Tests: `backend/tests/test_replays_winners_setup_timing_2026_11_22.py`; `frontend/src/lib/replays.setup.test.ts`,
  `frontend/src/components/ReplaysPastWinnersSetup.test.tsx`, `frontend/src/lib/newFeatures.replays_winners_setup_timing.test.ts`,
  `frontend/src/lib/newFeatures.replays_past_winner_tag.test.ts`. The 11-18 listing pin
  (`test_both_kinds_listed_groups_date_desc_close_gain_desc`) and card pin were re-pinned for the new order / keys.

## 2026-11-22 — 🏆 one row per stock (multi-day runs grouped with the single days)

Ajay 2026-11-22, verbatim: **"Just AKAN can you please bring its past winner session to like from MAY multiday when ever
a stock has multiday group it in the same role for past winners please."** then **"CLRO another example add all the
videos may be click them together"**.

- **Payload:** `groups` is gone; the 🏆 listing serves `rows` (`store.winner_rows`), ONE per symbol (exact match — two
  symbols never merge), each holding every accepted reel of that symbol, single-day AND multi-day, newest first by the
  reel's last session (a same-day tie: the multi-day run first, then close gain desc).
- **Row fields (server words):** `key` (`sym-<SYM>`), `symbol`, `wins` + `wins_text` ("1 win" / "3 wins"), `newest_date`
  + `newest_text` ("newest Fri 2026-10-23"), `setup` + `setup_text` (the first key in the ask's order — 🎾 first — that
  any reel passes), `timing` + `timing_text` (the NEWEST single-day reel's), `best_close_gain_pct`, `filter_keys` (the
  setup keys at least one reel passes, ask order), `videos`.
- **Wins = the past-winner index's one-per-run rule** (`past_winner_index` + `_one_per_run`, one engine): a multi-day
  run counts once and absorbs the single-day reels whose day falls on its days; a separate single day before or after
  the run is another win. `newest_date` = the newest win's last session.
- **Row order (server):** the newest single-day reel's timing `eod` → `intraday` → `first_hour` → unknown (a row with
  only multi-day reels is unknown — the labeller writes no multi-day timing, and a stray key stays ignored), then
  `newest_date` desc, then the best close gain desc, then the symbol.
- **Filter on ROWS:** a row shows when any reel passes (its served `filter_keys`); counts = rows; 'All' = every row.
- **Frontend:** each row is a collapsed header button (served chips only); a tap lists its reels (the card with its
  player, setup / class / also / ⛔ / timing chips; a multi-day reel shows its session span). Still ONE `<video>` in the
  whole section. `?winners=1&sym=AKAN` opens that row expanded (that row only; a tap still toggles it). 📱 430 px:
  `.rpw-stock` / `.rpw-reels` min-width 0 + max-width 100%; `.rpw-stock-head` wraps; the symbol and chips wrap their text.
- **Real data (host folder, read-only, 2026-11-22 ~02:00 ET):** 317 reels (301 single-day, 16 multi-day) → 227 rows;
  filter rows (before AKAN's run landed) All 227 · 🎾 84 · 🌀 34 · 💋 11 · 🚩 15 · ➖ 0 · none 131; `skipped_label` 0.
  CLRO = 1 row, 3 reels (10-23, 07-07, 07-02), 3 wins, 🎾, 🌅 first hour (peak 10:13). AKAN = the FIRST row, 3 reels
  (11-18, 11-13, the multi-day 2026-04-21 → 2026-05-01 · 9 sessions run), 3 wins, 🌀, 🌙 end of day (peak 15:23).
- Descriptive, UNMEASURED: no gate, no push, no rank of setups, no win rate.
- Tests: `backend/tests/test_replays_winners_setup_timing_2026_11_22.py` (rows section),
  `backend/tests/test_replays_winners_2026_11_18.py` (re-pinned for `rows`), `frontend/src/components/ReplaysPastWinnersSetup.test.tsx`,
  `frontend/src/components/ReplaysPastWinners.test.tsx` + `ReplaysPastWinTag.test.tsx` (re-pinned for `rows`),
  `frontend/src/lib/replays.setup.test.ts`.
