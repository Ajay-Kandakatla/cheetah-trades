# 📅 Long Term — the list rules, notices and forward record (2026-11-12)

Package: `backend/long_term_list/` (WP-CORE: `constants.py`, `seed.py`, `criteria.py`, `notices.py`,
`forward.py`, `words.py`, `payload.py`). Spec: scratchpad `longterm/spec.md` revision 2, §3.2–3.7, §3.10–3.11.
UNMEASURED. The tab is primary-owner only (`OWNER_ONLY = True`). At save nothing rang a phone
(`DIGEST_PUSH_MODE = "off"`); since 2026-11-12 the digest and the 🔔 zone reach push LIVE under one kind `long_term`
(his calls — see "What is NOT done" below and `long_term_zone_alerts_2026_11_12.md`).

## His words (verbatim)

1. 2026-11-12 ~21:00 ET: "Save this entire list for me. In a New tab - Long Term - Remember this analays criteria I am asking you to for this tab and keep updating it from all the other tabs info.. Weekly and if something gets dropped let me know when to like is Sales drop or Stage 2 to Stage 3 or stage 4 changes."
2. 2026-11-12 ~21:20 ET: "Yeah I wanna find out the ones that are actually great in fundamentals and growth and sales and no debt but not growing in price action yet.."
3. In the seed's 🔄 `his_words`: "Also I would like us to find more of such Mid and small caps TBH in all fields that that are accelerating and have been down in the past (2026-11-12)"
4. In the seed's 🧭 `his_words`: "I have a long term tab already from Pankaj can you take a look at this again most them have been winner wondering since when we tracked those but lets use those tickerts too (2026-11-12); I need you to tell me whcih ones are at the zone to enter like C1 or Aggr"

## The seed

`backend/long_term_list/data/seed_2026_11_12.json` — his file, copied byte-identical from the scratchpad
(`cmp` identical), sha256 `74ecc4e36bb89f63715c2c65264e0d01a9e07d8a189218012b81cd593bbc1c00`
(`constants.SEED_SHA256`). Strict JSON (no NaN; blank zones are `null`), so no normalized copy was needed.
`seed.load()` parses with `parse_constant` refusing NaN / Infinity, checks the sha, refuses a category key
outside `CATEGORY_KEYS`, and refuses a 🧭 name whose zone keys differ from the first one's. Nothing in the
package writes it.

Nine categories (file order), **109 unique names** (74 screened + 40 🧭 − 5 overlap ANET GOOGL MA META NVDA).
The saved list never grows or shrinks; each screened list's weekly top is an unsaved strip.

## Legs and kinds (criteria.py)

Kinds: **F** fundamental (fail = ⚠️ on the tab, never rings by itself) · **M** market (a flip = neutral
"moved" line) · **S** stage · **I** info (never pass / fail). `None` or the tier string `"unknown"` is
always `unknown`, never a pass. `qualifies` = True only when every non-info leg passes.

| list | population | legs (kind) | rank (ties) | cap |
|---|---|---|---|---|
| 🚀 `s2_growth` | scan candidates | trend template (M) · Stage 2 (S) · tier strong/explosive, or steady + accelerating (F) · C EPS (F) · A EPS (F) | RS rank desc, scan score desc | 3/sector |
| 💎 `capital_quality` | scan candidates | trend template (M) · ROE ≥ 20 (F) · FCF margin > 0 (F) · net debt/EBITDA known and ≤ 1 (F) · 💎 grade on 🚀 (I) | moat score desc, scan score desc | 3 |
| 🏷️ `undervalue` | vs-peers tiles | TTM revenue ≥ $100M (F) · latest-q sales ≥ 20% (F) · TTM growth ≥ 20% (F) · on the list (M; unknown when off-list and the F legs pass) · `ok` floor (M) | P/S ratio asc | 3 |
| 📈 `bonde` | scan candidates | trend template (M) · Bonde tier strong/explosive (F) | Bonde score desc, scan score desc | 3 |
| 📉 `fallen_growers` | served 📉 page (`in_served_pool`) | ≥ 40% under high (M) · ≥ 10% over low (M) · sales ≥ 20% (F; blanked pair → unknown) · floor (M) | sales y/y desc | 3 |
| 🔥 `hot` | served Hottest top 25 per group (`served`) | tier strong/explosive (F) · q EPS y/y > 0 (F) · one-month return > 0 (M) · served (M) | ret_21d desc | **2** |
| 🌱 `quiet_strong` | long-term rows | Stage 1 (S) · score ranked and ≥ 70 (F; unranked → unknown) · net profit > 0 (F) · OCF > 0 (F) · sales CAGR ≥ 15 (F) · liabilities/equity known and ≤ 1 (F) · current tier steady/strong/explosive (F) [C2] · avg daily $vol ≥ $5M (M) · ≥ 10% under high (M) · net debt/EBITDA (I) [C3] | score desc; one share class (identical `SHARE_CLASS_KEYS` metrics, the saved symbol wins) | 3 |
| 🔄 `accel_after_fall` | research sales (full universe) | cap $300M–$10B (M) · tier strong/explosive (F) · accelerating (F) · prior y/y > 0 (F) · ≥ 30% under high (M) · ≥ 10% over low (M) · Stage 1 or 2 (S) · avg daily $vol ≥ $3M (M) · net profit (I) | (growth − prior) desc | 3 |
| 🧭 `pankaj` | his sheet's first 40 rows | Pankaj tier + ZT (I) · his zones (I) · zone read (I) | — (never screened, no strip) | — |

`pick_top`: qualifies AND in population → rank → 🌱 share-class dedupe → sector cap (a name with no sector
is not capped) → first 10.

**🌱 reproduction (11-12 dumps):** 29 names pass every other leg; with the tier leg the top 10 is exactly
HLNE NVDA META GOOGL NXT MPWR XPEL EPRT MGY CTRE (AEM unknown tier, LULU declining, ZM weak, GOOG = the
GOOGL share class). Fixture: `backend/tests/fixtures/long_term_list/quiet_pass_2026_11_12.json`.

### `values` keys each list reads (WP-DATA maps the sources to these)
- 🚀 `qualifier, stage, sales_tier, sales_accelerating, c_strong_q_eps, a_strong_y_eps, rs_rank, scan_score`
- 💎 `qualifier, roe_pct, fcf_margin_pct, net_debt_ebitda, cq_grade, moat_score, scan_score`
- 🏷️ `ttm_revenue, q_yoy_pct, ttm_growth_pct, on_list, floor_ok, ratio`
- 📈 `qualifier, bonde_tier, bonde_score, scan_score`
- 📉 `pct_below_high, pct_above_low, sales_yoy_pct, pair_blanked, floor_ok, in_served_pool`
- 🔥 `sales_tier, q_eps_yoy, ret_21d, served`
- 🌱 `stage, score, score_ranked, net_profit, ocf, opm, sales_cagr, profit_cagr, liab_to_equity, sales_tier, dollar_vol_50, pct_below_high, net_debt_ebitda`
- 🔄 `market_cap, sales_tier, sales_accelerating, growth_yoy_pct, prior_yoy_pct, pct_below_high, pct_above_low, stage, dollar_vol_50, net_profit`
- 🧭 `close, close_date, zones, tier, zt` (the zone read is computed from these)

`pct_below_high` / `pct_above_low` are positive percentages (14.3 = 14.3% under the high).

## 🧭 Pankaj's list
His picks with his zones (Agg, C1, C2, C3), not re-screened. `criteria.zone_read` runs every readable
zone (both edges, lo ≤ hi) through the /pankaj page's own engine `pankaj_picks.setup_status` (its 0.5%
`ZONE_PAD_PCT` counts as in) and reads only `state` + `dist_pct`. 11-12 close: TSM in Agg (405.49 in
400–410), META in C1 (623.61), NVDA in C2 (166.19); INTU 23.7% over its Agg top. The zone column is the ONE
request-time read on the owner's GET. **Not served:** his "Possible Action" column (`pankaj_entries`
never copies it — HIS CALL §7 #22), the "Class" the seed criteria promises (no data).

## Constants (constants.py — HIS / APP / MINE)
| constant | value | source |
|---|---|---|
| `FALLEN_MIN_PCT_BELOW` | `fallen_tab.THRESHOLD_PCT` (40) | HIS |
| `UV_*` | `undervalue_peers` P/S ≤ 0.50 of peers, q y/y ≥ 20, TTM growth ≥ 20, TTM revenue ≥ $100M | HIS (that file's calls) |
| `QUIET_SALES_TIERS` | `sales.BONDE_PASS_TIERS` (steady, strong, explosive) | tuple APP, as a gate MINE |
| `PANKAJ_ZONE_PAD_PCT` | `pankaj_picks.ZONE_PAD_PCT` (0.5) | APP |
| `HOT_PAGE`, `FALLEN_PAGE`, `FLOOR_TIER`, `RUN_AFTER_ET`, `FORWARD_MIN_SESSIONS`, `BENCHMARK(_ALT)` | Hottest 25, board 80, "ok", 16:30, `REBALANCE` 21, RSP / SPY | APP |
| `STAGE_DROP_PAIRS` | `stage_transitions.TRANSITIONS` with prior 2 → ((2,3),(2,4)) | MINE (filter) |
| every other cut-off (ROE 20, FCF > 0, net debt ≤ 1, 10% off low, sales 20%, 🔥 tiers/EPS/return, 🌱 70/15/1/$5M/10%, 🔄 caps/30/10/$3M, 10 per list, 3 per sector, 2 for 🔥) | see the file | MINE = HIS CALL |
| `RING_KINDS`, `DIGEST_PUSH_MODE "off"`, `DIGEST_BODY_LINES 6`, forward CI 95 / 2,000 boot / 1,000 placebo / seed 20261112 | | MINE |

`CONSTANT_SOURCES` maps every numeric constant (pinned by a test) and is served in `rules` (`his_call` = MINE).

## Notices (notices.py)
Per-name flags: `last_stage`, `last_stage2_on`, `stage_drop_on`, `stage_drop_active`, `sales_drop_active`,
`fundamental_failing`, `started_moving_on`, `zone_in`, `absent`. Week 1 starts from
`notices.initial_flags(notices.at_save(sym, baseline))` (WP-DATA writes these into the baseline).

| kind | when | rings | on the tab |
|---|---|---|---|
| `stage_drop` | stage now 3 or 4 AND read at Stage 2 at save or at any run since the last drop (None weeks skipped) | **yes** | ⚠️ changed |
| `sales_drop` | tier below its tier at save on `declining < weak < steady < strong < explosive`; unknown either side → nothing; once until it recovers | **yes** | ⚠️ changed |
| `started_moving` | a 🌱 name, last non-None read Stage 1, now Stage 2 | **yes** | 🌱 → 🚀 strip |
| `fundamental` | an F leg pass (last week, else save) → fail; cleared when every F leg passes | no | ⚠️ changed |
| `moved` | an M leg (or a 🌱/🔄 stage leg outside a drop / start) flips either way | no | plain line on its list |
| `zone` | a 🧭 zone newly in | no | plain line |
| `absent` | missing from a source it was read in | no | "not read, not dropped" |

Never events: 3 → 4, 2 → 1, a non-🌱 1 → 2, unknown legs. A stage or sales leg failing for the same cause
folds into that event (one stage_drop listing every chip). `digest.rings` = any RING_KINDS event.

## Forward record (forward.py)
Base = the OPEN of the first open day after 2026-11-12 (2026-11-13), frozen once. Missing bar → last close
≤ at (`n_stale`); missing frame → last stored price, else the base price (`n_carried`); no base price →
`no_base`, listed and counted. Headline = the 74 screened names, equal weight; 🧭 is its own per-category
line. `n_sessions` counts RSP closed bars from the base; below 21 the line says "Too early" and carries no
number; from 21 it carries a by-name bootstrap CI and a random-names placebo band (mid-rank percentile)
from the same universe, "One window — a tracking line, not a test." Calendar helpers
(`is_open_day`, `base_session`, `last_trading_day_of_week`) read `market_hours.gate.closed_reason` at noon.

## Payload (payload.py)
`build_payload(seed, baseline, runs, forward_docs, zone_closes, *, now, owner)`. `owner=False` → exactly
`{state: "owner_only", reason, title}`. No run → `seed_only` (every saved row, the 🧭 zone read,
"first weekly read … after 4:30 PM ET"). Seed sha mismatch → `error` + reason. One row per symbol (in
`changed` when flagged, else its first list), strip rows carry no fields, NaN scrubbed by `growth.api._scrub`.
Golden key set: `backend/tests/fixtures/long_term_list_payload_golden.json`.

## Words (words.py)
Every served sentence; numbers only through f-strings over constants / `bonde.MEASURED` / facts values.
The ONE allowed sentence is `NOT_A_SIGNAL`; the seed caveat carrying the same sentence without the
period is served as `NOT_A_SIGNAL`. "Liabilities / equity", never "debt".

## What is NOT done
- ~~No phone push (WP-PUSH held; `DIGEST_PUSH_MODE "off"`).~~ **2026-11-12:** both phone pushes are LIVE under ONE owner keep-set kind `long_term` — the weekly digest (`DIGEST_PUSH_MODE = "live"`, Ajay: "Weekly and if something gets dropped let me know …") and a 🧭 name reaching one of Pankaj's zones (`ZONE_PUSH_MODE = "live"`, Ajay: "add an alert list when stocks reach Pankaj's zones …"). Both mode constants are now tagged HIS in `CONSTANT_SOURCES`; `RING_KINDS` unchanged (a zone line never rings the digest). See `long_term_zone_alerts_2026_11_12.md`.
- Nothing auto-saved; strips are unsaved.
- No historical replay of the lists (fundamentals are latest-only → look-ahead).
- No sources / facts / weekly / API in this package piece (WP-DATA, WP-RUN).

## HIS CALL (spec §7)
1 digest push as an 8th keep-set kind · 2 every MINE cut-off · 3 which "no debt" gates (liabilities/equity
vs net debt/EBITDA: EPRT 5.07, CTRE 3.02, MGY 1.67 would fail ≤ 1) · 4 stage notices 2→3 / 2→4 only ·
5 weekly strips vs auto-save · 6 🏷️ sector cap · 7 sales drop = tier below save · 8 forward base / weights /
21-session gate / method · 9 missed week · 10 what rings · 11 owner-only · 12 label + slot · 13 📉 one
session behind on Friday · 14 nine lists · 15 🔄 cached caps · 16 share-class rule · 17 a 🌱 starter is not
moved into 🚀 · 18 one stage per name · 19 house chips · 20 digest cap · 21 🧭 = first 40 of 128 rows ·
22 serve "Possible Action" · 23 0.5% zone pad vs strict · 24 🧭 notices · 25 Enterable chip wording ·
26 leg kinds · 27 🌱 → Stage 3/4 = moved, not ⚠️.
