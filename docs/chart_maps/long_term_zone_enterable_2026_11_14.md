# 📅 Long Term — 🎯 Enterable (zones): the served zone read (backend, 2026-11-14)

Ajay 2026-11-14, verbatim: "Make a enterable check box in longterm stocks with zone and filters please"

Spec: scratchpad `ltenter/spec.md` revision 2, §3.1–3.4, §3.6, §3.9 (WP-BE). The FE half (checkbox, Zone column, filter
chips, hidden count) is documented in `long_term_tab_frontend_2026_11_12.md`.

**A display filter only. It rings nothing, gates nothing, reorders nothing. UNMEASURED** — no study says a name inside
or just above one of these zones does anything afterwards (prior: NULL; the house 🎯 ENTERABLE and 🧱 1% pad reads are
no_signal).

## What is served (owner payload only)

`GET /chart-maps/long-term`, owner only (unchanged gate). Non-owners still get exactly `{state, reason, title}`.

- Top key `zone_rules`, right after `zones`:
  `{pad_pct, above_pct, snapshot_date, ls_key, text, sources, levels, reasons, words}`.
  - `sources`: `both` / `pankaj` / `gabbar` with their labels.
  - `levels`: Pankaj's zone keys in zone order (Agg, C1, C2, C3), then the Gabbar level keys **derived from the bands**
    (`zones.gabbar_level_keys(seed)` — today aggressive, conservative 1, conservative 2+).
  - `reasons`: the hidden-count reasons in `ZONE_REASON_CODES` order (below, above, no_zone, no_price, filtered).
  - `words`: every word the FE prints (incl. `dash`); the FE types none of its own.
- Every saved row gets `zone` right after `pankaj`: `{bands, gabbar_text, close}`.
  - `bands`: Pankaj's pairs in zone order, then Gabbar's bands top first; each `{source, key, level, label, lo, hi}`.
  - `gabbar_text`: "Gabbar bands from the 05-17 snapshot" (+ " · ÷25 split-adjusted (04-06)" for BKNG), or
    "Gabbar tracks TSM but has drawn no level" for a `TRACKED_NO_LEVELS` name, or null.
  - `close`: `{basis:"close", price, date (ISO), state, enterable, band, pct, text}` at the latest closed cached bar.
- The owner-only rules list gains `zone_enterable` ("🎯 Enterable (zones)") right after `zone_alert`, source MINE,
  his_call true. The public ℹ️ Rules panel is unchanged (the line names Pankaj).

## The engine chain

`zones.band_state` → `sepa.pankaj_picks.setup_status({"kind":"pullback","zone":{lo,hi}}, price)` — the same engine
`criteria.zone_read` already uses for the 🧭 column and the 🔔 pass. Only its `state` and `dist_pct` are read.

`zones.read(bands, price, date)`:
1. no bands → `no_zone` (checked first, whatever the price);
2. price None / NaN / inf / ≤ 0 → `no_price`;
3. first band read in-zone → `inside` (pct 0.0);
4. else the smallest `above` pct ≤ `ENTERABLE_ABOVE_PCT` → `near`;
5. else the nearest band by |pct| → `above` or `below` (not enterable).

`zones.row_block` guards a `None` close first (66 saved names have no band and no cached close is read for them).

## Constants (by name, `long_term_list/constants.py`)

| name | value | source |
|---|---|---|
| `ENTERABLE_ABOVE_PCT` | `alert_gates.ALERT_MAX_ABOVE_DEMAND_PCT` (1.0) | HIS — his 2026-09-05 demand-alert proximity |
| `PANKAJ_ZONE_PAD_PCT` | `pankaj_picks.ZONE_PAD_PCT` (0.5) | APP — the /pankaj in-zone pad (already the tab's rule) |
| `GABBAR_SNAPSHOT_DATE` | `gabbar_levels.BAND_ATTRIBUTION["snapshot_date"]` | APP |
| `ZONE_SOURCES` | ("pankaj", "gabbar") | APP |
| `GABBAR_DEEP_LEVEL_KEY` | "conservative 2+" | MINE — one chip for every band from index `GABBAR_DEEP_FROM` on |
| `GABBAR_DEEP_FROM` | 2 | MINE — band index (0 aggressive, 1 conservative 1) |
| `ZONE_REASON_CODES` | below, above, no_zone, no_price, filtered | MINE |
| `ZONE_FILTER_LS_KEY` | "lt_zone_filter_v1" | MINE — per-viewer localStorage key |

Pad coupling: `band_state` follows `PK.ZONE_PAD_PCT` (the engine's own number); `pad_pct` is served from
`C.PANKAJ_ZONE_PAD_PCT`, the same object, so the FE and BE agree. A test documents it.

## Case table (pinned on both sides)

| case | lo–hi | price | state | pct | enterable |
|---|---|---|---|---|---|
| VRT inside C1 | 195–205 | 200.00 | inside | 0.0 | yes |
| pad edge, 0.4% above hi | 100–110 | 110.44 | inside | 0.0 | yes |
| 0.6% above hi | 100–110 | 110.66 | near | +0.6 | yes |
| 1.0% above hi | 100–110 | 111.10 | near | +1.0 | yes |
| META 1.9% above C1 | 620–630 | 641.97 | above | +1.9 | no |
| NFLX 3.6% above Gabbar cons. 2 | 55–60 | 62.16 | above | +3.6 | no |
| pad edge, 0.4% under lo | 100–110 | 99.60 | inside | 0.0 | yes |
| 0.6% under lo (fell through) | 100–110 | 99.40 | below | -0.6 | no |
| GOOGL 4.6% under C1 | 310–315 | 295.74 | below | -4.6 | no |
| BKNG Gabbar aggressive ÷25 | 148–156 | 150.00 | inside | 0.0 | yes |
| price null | 195–205 | — | no_price | — | — |
| no bands | — | 200.00 | no_zone | — | — |
| two bands, inside the second | 100–110, 120–130 | 125.00 | inside (band 2) | 0.0 | yes |
| two bands, 0.8% above band 1 | 100–110, 150–160 | 110.88 | near (band 1) | +0.8 | yes |
| 2.0% above band 1, 1.0% under band 2 | 100–110, 113.33–120 | 112.20 | below (band 2) | -1.0 | no |

Cell text examples: "inside Pankaj C1 195–205 · close 11-13", "just above Gabbar aggressive 180–190 · +0.8% · close
11-13", "below the zone Pankaj C1 310–315 · -4.6% · close 11-13", "no zone on either sheet".

## Coverage (measured 2026-11-14 in the worktree venv)

109 saved names; 37 carry a Pankaj pair, 22 a Gabbar band, 16 both → **43** names with at least one band, **66** with
none (they read `no_zone`). Tests derive the list from the seed and never type the count.

## The one closes read

`api.owner_payload` makes ONE `sources.pankaj_closes` call over Pankaj's names ∪ `zones.zone_symbols(seed)` (one
`bulk_cached_frames` find, never a fetch). The Pankaj subset feeds the 🧭 strip / 🔔 block exactly as before
(byte-identical — a test builds both ways); the full set feeds the per-row `zone` block (`build_payload(...,
zone_closes_all=...)`). A failing read → `{}` → every row `no_price` / `no_zone`, HTTP 200.

## Gabbar notes

Gabbar's bands come from the 2026-05-17 snapshot (last verified 2026-08-27), split-adjusted only where a split was
verified from data (BKNG ÷25, 2026-04-06 → 148–156 / 128–136 / 108–116; the pre-split levels are never served). The LT
tab applies the 0.5% pad to Gabbar bands too (one engine); the Gabbar tab and `gabbar_watch` use no pad and a 1%/3%
either-side read, so a name 0.4% above a Gabbar band reads "inside" here and "near" there (HIS CALL #2).

## What it is NOT

No push, no keep-set kind, no gate, no sort, no change to `supply_demand/*` or `sepa/pankaj_picks.py`. The engine's
1-dp rounding makes the effective proximity ≤ 1.04% (HIS CALL #12).

## Words rule

Served strings never carry the house's banned trading verbs, never the rebound b-word (letter-level over every
`long_term_list/*.py`), never "buy zone" (the Gabbar module's own docstring wording). Pankaj's name stays off the public
panel.

## HIS CALLs (spec §7)

1 proximity constant · 2 pad on Gabbar bands · 3 default OFF · 4 label "(zones)" · 5 ⚠️ changed rows hidden too ·
6 no-zone / no-price rows hidden under their own reasons · 7 localStorage persistence · 8 one "conservative 2+" chip ·
9 no public ℹ️ line · 10 `pankaj.zone_text` duplicate · 11 pre/after-hours prints count as live · 12 1-dp rounding ·
13 no zone push · 14 co-owners · 15 two bases on one row · 16 chips hidden while OFF.
