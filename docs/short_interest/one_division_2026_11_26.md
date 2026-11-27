# One division for short interest ÷ shares, and where the SEPA card chip gets its share count (2026-11-26)

Ajay 2026-11-26 ~21:20 ET: "Also the Float share count issue and SI discrepancy happened too many times need to do something about it".
Spec: floatguard rev 2, §3.1 (the one division), §3.8 (the SEPA card chip), §4.6 (the guard).

## 2026-11-26 — what this package changed (`backend/short_interest/client.py`)

- `short_interest_for` (GET `/short/{sym}/interest`, the SEPA card chip in RealtimeChips.tsx) now always returns two more keys:
  `shares_source` (which share count the % divides by) and `shares_asof` (its date; `None` = the provider gives none).
- `SI_CARD_COUNT_FROM = "massive_ref"` (built default) in `SI_CARD_COUNT_MODES = ("massive_ref", "resolver")`. Any other word behaves as `massive_ref`.
  - `massive_ref`: today's numbers to the digit (Massive ticker details' UNDATED shares outstanding); `shares_source = MASSIVE_REF_SHARES_SOURCE`, `shares_asof = None`.
  - `resolver` — BUILT, OFF (his call #9; no list yet of which cards would move): when `read.si_map([sym])` holds a block for the SAME settlement date with a `pct_of_shares_out`, the card takes that block's `shares_outstanding`, `pct_of_shares_out`, `shares_source`, `shares_asof`, and `squeeze = _squeeze_signal(that %, dtc)`. No block, another settlement, no %, or a raise -> `massive_ref`.
- The per-name warm (`warm_short_interest`) writes an explicit key list, so the two new keys never reach `short_interest_latest`.
- The two change-% lines (`short_interest_for` `chg`, `_build_doc` `chg`) are changes across settlements, not short ÷ shares: they keep their own division and are NOT routed through `pct_of`.
- 2026-11-27 refix: client.py's three short ÷ shares sites now call `read.pct_of` (lazy `from short_interest import read as SR`, read imports client): `pct = SR.pct_of(si, shares, digits=None) if (si and shares) else None` in `short_interest_for` (the `si and shares` guard stays: a zero count is None, as before), `pf = SR.pct_of(si, fl) if fl else None` / `ps = SR.pct_of(si, so) if so else None` in `_build_doc`. Outputs unchanged to the digit on the sweep in `backend/tests/test_si_card_count_2026_11_26.py`; that file also pins client.py's `pct_of` call count at 3, no `Div` left in those three assignments, a spy that sees each call, and NEGATIVES that a zero / missing count or share count never reaches `pct_of`. One difference by construction: a NEGATIVE share count now gives None (before: a negative %); `_build_doc`'s `_pos_int` never yields one; `short_interest_for`'s `_shares_outstanding` passes Massive's raw value through, so only a negative count from Massive would show the difference.

## The eleven divisions (ten lines, four files)

| # | file (function) | what | served to |
|---|---|---|---|
| 1-2 | read.py (`si_block`) | `pf`, `ps` | every 🩳 chip / panel / table |
| 3-4 | basis_math.py (`stale_trigger`) | `s / base`, `s / den` (mode `tier_moves`) | the refusal cut |
| 5 | basis_math.py (`verdict`) | `pct_so` on the newer dated count | % of shares outstanding |
| 6 | basis_math.py (`verdict`) | `float_update.pct` (the newer Yahoo float) | % of float |
| 7 | basis_math.py (`verdict`) | `float_pct_on_file` (the "would read" %) | hover |
| 8 | client.py (`short_interest_for`) | live SI / Massive UNDATED count | SEPA card chip |
| 9-10 | client.py (`_build_doc`) | stored `pct_of_float`, `pct_of_shares` at warm | `pct_of_shares` shown by the 📈 Bonde DTC leg; `pct_of_float` never served |
| 11 | chart_maps/gajjala/high_si.py (`card_pct`) | SI / the CARD's float | 🩳 list membership (`floats_disagree`) |

All eleven have one shape, `x / y * 100[.0]` then `round(…, 2)` (client.py `short_interest_for` unrounded). After the build every one calls `read.pct_of(count, shares, digits=2)` — the ONE division (`digits=None` = unrounded; None when the count is None or the shares are None / zero / negative). Each site keeps its own guard; every output is bit-identical.

## The guard (spec §4.6, phase 3 — `backend/tests/test_si_one_division_guard_2026_11_26.py`)

AST only; no variable name is read by (a) or (b).
- File set: every `*.py` in `backend/short_interest/` + `chart_maps/gajjala/high_si.py`, `si_ssr_names.py`, `si_track.py`, `si_follow.py` + `sepa/bonde_picks.py`.
- (a) Exact inventory of every `Div` by (file, enclosing function) == a frozen dict of 21 after the build: `read.pct_of` 1 (the ONE), `read._human_shares` 1, `read.dtc_computed` 1; `basis_math` `_factor` 1, `rebase` 1, `change_across_split` 1, `verdict` 3; `borrow._per_day` 1; `client` `_squeeze_signal` 1, `short_interest_for` 1, `_build_doc` 1; `reg_sho._age_min` 1; `ssr` `_drop_pct` 1, `trigger_line` 1; `source_check.rel_of` 1; `si_track` `_rate` 1, `session_facts` 1, `shuffle_share` 1; `bonde_picks._ipo_leg` 1. No entry for `read.si_block`, `basis_math.stale_trigger`, `high_si.card_pct`, `source_audit`. (client's `short_interest_for` 1 and `_build_doc` 1 are the change-% lines.)
- (b) Percent shape: a `Div` under a multiplication by 100 / 100.0 is allowed only in `read.pct_of`, `basis_math.change_across_split`, `client.short_interest_for`, `client._build_doc`, `ssr._drop_pct`.
- (c) Repo tripwire outside the set (every `*.py` under `backend/` but `tests/`, `.venv/`, `__pycache__/`; `float(…)` / `int(…)` stripped): a short-interest name divided by a float / shares name. Allowed by name: `scripts/si_cradle_squeeze_study.py`, `scripts/si_share_basis_probe.py`. Expected hits: zero.
- (d) `pct_of` call counts: read.py 2, basis_math.py 5, client.py 3, high_si.py 1, source_check.py >= 1.

## Every surface and what it reads

| Surface | Path | Own math? |
|---|---|---|
| 🩳 chip on every Chart Maps tab + ticker header | GET /short-interest/map -> `read.si_map` -> `si_block` -> `basis_math.verdict` | no |
| 🎾 card label + EXTREME note, 👀 Watch tile note | same hook, served `chip` / `extreme` | no |
| ShortInterestPanel | same hook, served `rows` | no |
| 📋 All-strategies SI cell | `SR.si_map` | no |
| 🩳 High-SI sub, its card chip, the cross-push text | `HS.si_blocks` -> `SR.si_map`; tier from the block | YES — `card_pct` |
| ⛔🩳🔒 SI/SSR names | `HS.si_blocks` + `HS.classify` | through `card_pct` |
| ⛔ new-today fold order | `high_si.ssr_new_rank` sorts by the block's `tier`, then % | reads the tier |
| 🏁 si_track rows / 🔭 si_follow | block fields; `tier` stored per row | no |
| 👀 Watch tile Float chip | `shares_cache` (float + date, no %) | no division; a SEPARATE float read |
| 🚩 card Float chip + the K8 float gate | `shares_cache` / Massive shares out | no SI math; a GATE |
| SEPA card chip (RealtimeChips) | `client.short_interest_for` | YES — on Massive's undated count (`massive_ref`) |
| 📈 Bonde DTC leg | stored `pct_of_shares` (`_build_doc`) | stored at warm, unchecked |

## Still NOT routed / NOT changed

- The 👀 Watch Float chip and the 🚩 card Float chip — carry none of the resolver's flags (other workflow's files; follow-up).
- The K8 float gate and the 🩳 float cap — read Yahoo alone. A gate change = his call.
- The 📈 Bonde DTC leg — shows the % of shares stored at warm, unchecked.
- The SEPA card count — still Massive's undated count; `resolver` is built and OFF (his call #9). The hover now names the source.

## 2026-11-27 — guard hole closed: `/=` and `operator.truediv` now count

The guard (`backend/tests/test_si_one_division_guard_2026_11_26.py`) used to count only `a / b`. Two spellings slipped
past it: `p = si; p /= fl; return round(p * 100.0, 2)` and `operator.truediv(si, fl) * 100.0` both counted ZERO
divisions. One helper, `_div_parts`, now reads all three forms — `a / b`, `a /= b`, and a call to `operator.truediv` /
`operator.itruediv` (also a bare `truediv(…)` after `from operator import …`) — and all three checks use it: the exact
inventory, the percent shape and the repo tripwire. The short-interest files hold none of the new forms, so the frozen
21 divisions did not change. Elsewhere in the backend there are three `/=` lines (timestamps to seconds in
`chart_maps/fallen_catalysts.py` and `supply_demand/zone_bounce_alerts.py`); the tripwire does not flag them. NOT
covered: `x.__truediv__(y)`, `numpy.divide`, and `/` hidden inside `eval` or a string.
