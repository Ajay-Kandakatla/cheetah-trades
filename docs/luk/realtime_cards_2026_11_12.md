# 🥇 Luk — every card the board shows is re-read each pass · live price every 30 s · the board re-reads when a pass lands (2026-11-12)

**Display only. UNMEASURED**, as the whole 🥇 tab is. No gate, threshold, push condition, alert, ledger or count change:
what rings stays exactly the same; only freshness and latency move. PAPER only. `chart_maps/luk/constants.py` is the
only number source; `luk/ledger.py` (walk / stop-R) and `luk/alerts.py` are not touched; the 🏁 goldens are not touched.

## His words

Ajay 2026-11-12, verbatim (his spelling):

> "Luks scan is not realtime I see all dated values can you make it realtime
>
> SMCI actually failed from the notification this morning I entered it and now I lost"

The main session reads the first line as his word on HIS CALL #2 of 2026-11-11 ("re-read every carded name each pass",
`docs/luk/not_reread_cards_scan_top_2026_11_11.md`) — answered here for the cards the board SHOWS, not for every carded
name (see "Rejected").

## SMCI

**SMCI: this build would NOT have changed his loss.** SMCI was on the shortlist and its card was fresh. Both its A+ rang
(ORH trigger 27.47 at 09:36 ET, pullback trigger 27.69 at 09:41 ET) with the same stop 26.961, and both were stopped. A
fresher board does not change a ring, a stop or a fill. Whether 🥇 pushes stay LIVE, and the Rule #9 autopsy of the
class, are HIS CALL #0 below.

## Measured 2026-11-12 (read-only probes, single runs, cron container)

Probes in the session scratchpad `lukrt/probe/`: `passes_probe.py`, `shown_probe.py`, `refresh_probe.py`,
`smci_probe.py`, `aplus_today_probe.py`. The re-runnable form of `refresh_probe.py` is
`backend/scripts/luk_reread_measure.py --probe` (read-only; `--report` reads the pass docs).

| what | number | source |
|---|---|---|
| ok Luk passes today to 11:46 ET | 93 | `passes_probe.py` over `luk_passes` |
| pass wall p50 / p90 / max | **8.44 s / 11.64 s / 24.24 s** (max = an on-demand pass) | same |
| `bars.over_budget` in any pass today | **0** (every RTH pass loaded 37–40 of 40) | same |
| session reads 11:46 ET | 577 docs, **98 carded names**, 70 of them carded but not on the shortlist | `shown_probe.py` |
| cards SHOWN (default limit) | ↩️ 20 (9 tagged) · 🔔 24 (22 tagged) · 📦 5 (3 tagged) → **46 distinct, 32 not on the shortlist** | same |
| re-read of those 32 (prior days from the minute cache; today fetched WITHOUT a write) | **frames 4.77 s, detectors 0.02 s, 0.15 s/name, 0 failed** | `refresh_probe.py` 11:52 ET |
| cards whose state CHANGES on that re-read | **8**: FLD A+→stopped, LFTO A+→stopped, MBIO / GAUZ / FLNT / OESX triggered→stopped, FPS forming→listed, DPC forming→none | same |
| 2026-11-11 16:01 ET (the prior doc) | 265 carded, 39 re-read, 24 shown on 🔔 | `not_reread_cards_scan_top_2026_11_11.md` |
| 1-minute A+ push latency today (bar CLOSE stamp → `claimed_at`) | 1.4–4.4 min (ASX 09:32 → 09:36:23; SMCI ORH 09:35 → 09:36:26; SMCI pullback 09:37 → 09:41:26) | `smci_probe.py` over `luk_alerts` |
| SMCI | both A+ rang (ORH trigger 27.47 / pullback 27.69, stop 26.961); both read `stopped` now; SMCI WAS on the shortlist, so its card was fresh | same |
| today's 🥇 A+ pushes | **18 pushed** (09:32–09:50 ET; 13 on the 1-minute frame, 5 on the 5-minute) + 1 `late` refusal. Stored reads at 12:13 ET: 7 `stopped`, 9 `triggered`, 2 `aplus` (LFTO, FLD — both rang; stored reads dated 09:36 / 09:51 ET). After the 11:52 re-read probe (FLD, LFTO, MBIO → stopped), **≥ 10 of 18 read stopped**. **UNGRADED** (the 🏁 grades nightly). **A count, NOT a rate** — no CI, no placebo | `aplus_today_probe.py` 12:13 ET |

### Measured after deploy (the main session fills these; single checks, never a loop)

| measurement | value | when |
|---|---|---|
| first 3 cron passes after deploy: `refresh.read_n == refresh.asked_n`, `refresh.skipped` None | pending | pending |
| pass wall p50 / p90 after (before: 8.44 s / 11.64 s) — `luk_reread_measure.py --report` | pending | pending |
| `refresh.asked_n` / `refresh.board_n` per pass (expected ≈ 32 / ≈ 46 on a board like 11:46 ET) | pending | pending |
| `refresh.not_read` length; owner GET tiles with `not_reread: true` (0, or ≤ that length) | pending | pending |
| `refresh.aplus_not_rung` (expected [] for LFTO / FLD — both rang) | pending | pending |
| `pass.next_read_sec` in [`LUK_NEXT_READ_SEC`, cadence] on one owner GET | pending | pending |
| one POST `/chart-maps/live` with the shown 🥇 symbols + their `live_level`s → every quote with a `vs` carries `vs.pct_text` | pending | pending |
| summed `calls.minute_today` per pass after vs before | pending | pending |

## Why a card was dated (the root cause — three layers)

- `run.py` `SC.shortlist(lists, _carried(st, session))` is the ONLY set of names a pass read; frames load and
  `st.upsert_read` runs for those names only. Carried names get change 0.0, sort last and are cut at
  `LC.LUK_SHORTLIST_MAX` (40) — ~170 names were cut on every RTH pass today, so a carried card was in practice never
  re-read. `CARRY_STATES = ("forming", "triggered")`: an `aplus` / `listed` / `stopped` card was never carried at all.
- `luk/tab.py` serves every read of the session; the 11-11 `not_reread` tag marked a card older than the latest pass —
  a display-only fallback.
- The board re-GET ran on a random-phase `setInterval` of `GC.PASS_CADENCE_SEC` (300 s), so the screen could show the
  previous pass for up to ~5 min after a new one landed; and `LukBoard` had no `useCardLive`, so the price on a 🥇 card
  did not move between GETs.

## Decision (BUILT)

**The re-read runs INSIDE the existing Luk pass, AFTER the push gate, as a display-only refresh. It covers every card
the board shows (computed by the board's own engine) plus today's 🥇 alert cards. The house 30 s card poll carries the
live price. The pass serves a next-read time so the board re-GETs right after each pass lands. Nothing that can ring
changes.**

1. **Re-read — step 13b of `run_pass`** (`backend/chart_maps/luk/run.py`), after `AL.run_pass` and before the 🏁 grade
   step, ONE helper `_board_reread` inside ONE whole-step `try`:
   - Board names = the shown set — `luk.tab.tiles_for` cut by `luk.tab._clip_focus` at `GC.TILE_LIMIT_DEFAULT` per
     `LC.SETUPS` sub, interleaved by position, cut to `LC.LUK_REREAD_MAX` — computed over today's docs with THIS pass's
     ring reads overlaid in memory (`_overlay`); then today's alert symbols; then the ring set removed.
   - ONE `BA.frames_for` call with budget `LUK_PASS_BUDGET_SEC − LUK_GRADE_BUDGET_SEC − elapsed`, then `DT.read_all`
     with the SAME previous 1-minute bars-through.
   - Each re-read doc carries `refresh_only: True` + `cron_setups` (the 11-11 on-demand rule), so `_carried` — and
     therefore the shortlist and what can ring — is identical to before. A re-read is never handed to `AL.run_pass` and
     never moves the 1-minute clock.
   - A re-read that fails keeps its old doc, so the 11-11 "not re-read since HH:MM ET" tag shows on it. `_Superseded`
     (the on-demand stop) is re-raised; any other fault becomes `refresh.skipped = "error"` and the pass, the 🏁 grade
     and the clock still run.
   - Switch `LC.LUK_REREAD_SHOWN` (his words in its comment): False = no re-read; the pass doc then carries
     `refresh` with `skipped = "off (LUK_REREAD_SHOWN)"`. A `--symbols` pass skips with `"--symbols"`.
2. **Live price** — `LukBoard` rides `useCardLive` (POST `/chart-maps/live`, poll only, NEVER `stream`: LUK is not in
   GG's variant registry, so a stream POST would answer `on: false`) with the served per-card `live_level`s. `LukCard`
   splices the quote with `cardLive.patchTile` and prints the served `vs.text` and `vs.pct_text`. The served footer
   "live · HH:MM:SS ET" sits in the pass line.
3. **Board freshness** — `luk.tab.pass_block` serves `next_read_sec`; the FE arms a one-shot timer at it, re-armed
   after every GET (success or error); absent → the old interval, byte for byte.
4. **Faster trigger: NOT built** (HIS CALL #3). What "realtime" meant to him is HIS CALL #0b.

### Rejected (one line each)

- **Shown / carried names onto the SHORTLIST** ("shown first, then new"): re-read names would reach the push gate — more
  names could ring — and on a slow pass a re-read would starve the shortlist. Violates "what rings stays exactly the same".
- **Re-read every carded name** (98 today, 265 on 11-11): ≈ 40 s worst case, mostly on cards nobody sees; the board
  shows ≤ 72.
- **A second `frames_for` BEFORE the gate**: delays every A+ push by the re-read wall (~5–11 s).
- **Stream prices / a pass nudge through the 🛰 hub**: needs "luk" in `live_hub` / `live_events` (the 🚩 live stack,
  shared with a concurrent workflow) + 1 more Mongo read a second = HIS CALL #5. The 30 s poll is the house overlay
  and needs no backend change.
- **A shorter fixed board interval** (e.g. 60 s): 5× the GETs (each reads ~580 read docs), still up to 60 s late.
- **Percent computed in the FE**: the FE types no number.
- **The pill keyed off `st.alert_rows`**: `alert_rows` keeps only shadow / pushed, so a live claim that settled
  `failed` / `no_target` would print "did not ring" on a push that was attempted.
- **The pill via `GA._exists`**: it fails OPEN (a read fault → "did not ring").
- **A second re-read round** for cards that enter the cut only because a RE-READ re-sorted others: another fetch path
  for a one-pass tag; the next pass reads them.
- **Names of every card not re-read in the cost line**: up to ~90 tickers on a 430 px strip, and each card already
  carries its own tag.

## The served words

Every number is a constants name read at call time; no digit is typed into a template.

| key | words | where |
|---|---|---|
| `pass.text` tail (only when the latest pass doc has `refresh.on` True) | ` · {read} of {board} board cards re-read` | `tab.PASS_REREAD_TAIL` |
| `strip.cost_text` (switch on) | ` Then, after the push gate, every card the board shows (at most {most}) and every card a 🥇 alert opened today is re-read with the pass budget left — a re-read rings nothing.` — `{most}` = `LC.LUK_REREAD_MAX` | `tab.COST_REREAD_TEXT` |
| `strip.cost_text` last-pass clause | ` Re-read last pass: {read} of {asked}{missed}.` | `tab.COST_REREAD_LAST_TEXT` |
| the missed part (only when `not_read` is non-empty) | ` — {n} not re-read (each says so on its card)` — **a COUNT, never a name list** | `tab.COST_MISSED_TEXT` |
| `strip.push_text` tail (live mode only) | ` A card re-read only for the board rings nothing — its A+ says so on the card.` | `tab.PUSH_REREAD_TAIL` |
| card `not_rung_text` | `A+ on a board re-read — it did not ring (pushes come from the pass's shortlisted names)` | `tab.NOT_RUNG_TEXT` |
| card `live_level` | `{trigger, stop, tf}` for `aplus` / `triggered` / `forming` / `listed`; None for `stopped` (the VS words say "the read moves when the bar closes", untrue for a stopped Luk read) | `tab.tile_of` |
| `vs.pct_text` | `{pct} vs the trigger` · `{pct} vs the stop`, trigger first, joined by ` · `, on the broker grid the words print | `live_card.VS_PCT_TEXT` / `VS_PCT_JOIN` |
| 📓 cadence line (switch on) | `; then every card the board shows (at most %d) and every card a 🥇 alert opened today is re-read — a re-read rings nothing.` | `playbook.py` |

- **The cost line prints a count.** "{n} not re-read" with n = `len(refresh.not_read)`; no ticker of `not_read` is ever
  printed there. Each such card already names itself with the 11-11 "not re-read since HH:MM ET" tag.
- **The "did not ring" pill comes from the gate's OWN claim ids.** The pass writes `not_rung: [setup]` on a re-read doc
  only when that setup reads `aplus` and BOTH `GA.shadow_key(session, sym, setup, LUK)` and
  `GA.claim_key(session, sym, setup, LUK)` are absent — ONE `find_one` over both ids (`run._rang`). A claim doc in any
  state (shadow, claimed, pushed, failed, no_target) = it rang → no pill. A `#late` / `#state` refusal never matches the
  ids → the pill shows. A missing collection or a find that raises = unknown → no pill (fails CLOSED). A ring-read doc
  never carries `not_rung`; a re-read doc without the key (written before this build) → no pill.
- **`vs.pct_text` exists only with a `vs`.** `live_card.live_vs` returns None exactly where it did before (no price, no
  level, an unparsable level, one level with the price on its other side); `text` is byte-identical.
- **The next-read time and its fallback.** `next_read_sec` is None outside the window or with no CRON pass this session.
  Else `due = cron at + cadence + its wall_s`, `over = now − due`:
  - `over > cadence` (passes stopped: a skipped pass writes no doc — host sleep, kill switch, lease held) → the cadence;
  - else `min(cadence, max(LUK_NEXT_READ_SEC, ceil(−over) + LUK_NEXT_READ_SEC))`.
  So the board re-reads `LUK_NEXT_READ_SEC` after a pass is due, every `LUK_NEXT_READ_SEC` while it is overdue by up to
  one cadence, then falls back to the cadence — never every 30 s for the rest of the window. At most
  `cadence / LUK_NEXT_READ_SEC` extra GETs per late or skipped pass.

## Cost arithmetic

| item | per pass |
|---|---|
| board names re-read | ≤ `LUK_REREAD_MAX` = `len(SETUPS) × TILE_LIMIT_DEFAULT` = 3 × 24 = **72**, + today's alert names not already shown (18 today, most already shown) |
| Massive today-minute fetches added | **≤ 72 + alerted** per pass (prior sessions are minute-cache hits for names read earlier today); ≈ ≤ 14–18 a minute on average |
| wall added, worst case | 72 × 0.15 s/name ≈ **11 s**; today's 32 names measured **4.77 s** frames + 0.02 s detectors |
| budget left after a p90 pass | ≈ 120 (`LUK_PASS_BUDGET_SEC`) − 30 (`LUK_GRADE_BUDGET_SEC`) − 12 ≈ **78 s** |
| Mongo | today's reads (~580 docs) read ONCE per pass (before: 1× by `_carried`, 2× on-demand) + one `alert_rows` read + one `find_one` per re-read A+ setup |
| live price | one `/chart-maps/live` POST (one snapshot REST call) per 30 s per open, visible 🥇 tab — the house overlay, no WS |
| board GETs | one per pass when on time; at most `cadence / LUK_NEXT_READ_SEC` extra per late or skipped pass |

- The repo states NO Massive REST rate ceiling (plan: "unlimited calls", `docs/realtime/massive_ws_feed.md`; Luk HIS
  CALL #30). "≤ 60 minute fetches a minute" is `GC.GG1M_MAX_NAMES`, a 🚩 cost choice, not a Massive limit. The only
  hard Massive limit is ONE stocks WebSocket per account — 🥇 opens none. The budget that binds is wall time.
- `calls.minute_prior` counts minute-CACHE reads too (`load_day` calls), not only Massive calls.
- Budget order: the shortlist (what can ring) reads first with its own budget; the re-read gets what is left. A name it
  cannot reach is counted in `refresh.not_read` (`bars.over_budget`) and tagged on its card.

## HIS CALL (nothing below is decided by this build)

0. **SMCI — this build does not fix it.** SMCI's card was fresh. Both A+ rang (ORH 27.47 at 09:36, pullback 27.69 at
   09:41, same stop 26.961; the same stock rang twice within 5 minutes) and both stopped. Today: 18 🥇 A+ pushed and ≥ 10
   read stopped by 12:13 ET (ungraded, a count not a rate). Luk 11-02→11-06: 68 A+, 9 W / 33 L, −0.08R; stops are
   booked at −1R while real stops ran −1.58R per trade. Two decisions are his:
   - (a) whether 🥇 pushes stay LIVE (today `luk_setup` is the keep-set's seventh kind);
   - (b) a Rule #9 autopsy of the "1-minute A+ in the first 10 minutes stopped the same morning" class: 8 of today's 13
     1-minute A+ read stopped (≥ 3, so Rule #9 applies). Any rule from it (one ring per stock per day across setups, no
     1-minute ring before a time) is a gate change.
   - 0b. **"By realtime do you mean the cards stay current (built) or the push reaching you sooner after the bar closes
     (today 1.4–4.4 min, not built — #3)?"**
1. **Budget order when the pass budget binds.** BUILT: the shortlist reads first; the re-read runs after the push gate
   with what is left, and the cost line counts any card it could not reach. The brief's "shown cards first" would let a
   re-read starve the shortlist on a slow pass (= fewer names can ring). Measured: 0 over-budget names in 93 passes
   today; the re-read adds ~5 s (≤ ~11 s).
2. **Should a re-read card ring?** BUILT: no. Re-reads never reach the gate; a re-read A+ with no claim says "did not
   ring". Letting them pass the SAME gate = more names can ring (6 forming cards shown at 11:46 ET, ≥ 4 off the
   shortlist) = a gate change.
3. **Faster 1-minute trigger: NOT built.** Today 1-minute A+ pushes rang 1.4–4.4 min after their bar closed. Options:
   (a) a Luk 1-minute loop child for 09:30–09:46 ET (the 🚩 1-minute page pattern): ≤ 40 names × 15 minutes ≈ 600 more
   Massive minute fetches a day, a push ~30–60 s after the close; (b) the hub's bar clock spawning a Luk pass from the
   api. Both change when and where a push can ring.
4. **A "stopped" push for an A+ that rang** (his SMCI loss) — a new push kind (an eighth keep-set kind). Today only the
   live line ("🔴 … under the stop") shows it, every 30 s.
5. **Sub-second prices + an instant pass nudge on 🥇 via the 🛰 hub** — adds "luk" to `live_hub` / `live_events`, + 1
   Mongo read a second and ≤ 80 more symbols on the ONE socket's watch set. Built instead: the 30 s REST poll + the
   served next-read time.
6. **Mine (defaults + words):** `LUK_NEXT_READ_SEC` 30 (= `live_card.CARD_LIVE_SEC`, a test pins equality) and the
   fallback to the cadence after one overdue cadence; today's alert cards join the re-read; the interleaved order of the
   shown set; stopped cards get no live words; the pass-line tail, cost words (a count, not names), push tail, the
   "did not ring" pill and the pct words; the pill reads the claim ids, not `alert_rows`.
7. **Still open from 11-11:** carded cards the board does NOT show (52 today, 200+ on 11-11) are still not re-read;
   variant B; the 24-card limit; an old A+ under fresh cards; tag-not-hide.
8. **The % on 🚩 cards** — `pct_text` is served there too (every 🚩 live answer and the stream path) but not printed.
   Printing it on 🚩 = his word.

## Traps

- A re-read can REMOVE a card (DPC forming → none today; `none` is never carded) or re-sort it (A+ → stopped drops below
  the cut) — the detector's own read, as for a shortlisted name. A card that enters the shown set only because a RE-READ
  re-sorted others is tagged for one pass and re-read on the next.
- A re-read A+ (a forming card that broke while off the shortlist) did not ring: its pill shows only while it reads
  `aplus` and no claim id exists. The next pass reads it "triggered earlier" with no note.
- The vs words say "the read moves when the 5-minute bar closes (HH:MM ET)"; for 🥇 the read moves at the next pass
  (~1–2 min after that close), the same approximation 🚩 carries.
- The container runs `origin/main`: verify pre-deploy only in a throwaway container off the branch (never the live api,
  never `docker cp`); after deploy, read the pass's own `refresh` block.

## Deploy

The Luk pass is a DETACHED child of the 🚩 cron pass and runs in the **cron** container, so the deploy needs `cron` (between
ticks :x2–:x4 — a cron deploy restarts supercronic). `api` serves the words and `/chart-maps/live`; `frontend` carries the
poll and the timer.

```bash
./deploy-cheetah-main.sh api frontend cron
```
