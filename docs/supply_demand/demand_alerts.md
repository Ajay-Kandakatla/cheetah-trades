# Demand-zone approach alerts (`demand_alert`) + the Gabbar "nearing" tier

**Ask (Ajay 2026-09-03):** *"I need a notifications when Gabbar levels are
reaching Demand zone like NTAP today.. Also other big companies billion or
atleast bigger than a billion coming close to Demand zones."*

Two halves, one discipline. Configured price-structure method, **not a book
method** — decision support, not a buy signal, not advice.

## 1. Universe half — `backend/supply_demand/demand_alerts.py`

| | |
|---|---|
| Names | every row of the demand board: `approaching_rows` (falling toward a tested band — `demand_reentry.approaching_read`) and `rows` (back inside one). The board already applied MIN_TOUCHES / MIN_ZONE_STRENGTH, the falling-knife guard, `trend_ok` and the 5-bar drift predicate ([demand_reentry_methodology.md](demand_reentry_methodology.md)). |
| Source | the board **over HTTP** from the api container (`INTERNAL_API_BASE`, default `http://api:8000`, header `X-User-Email: cron@internal`) — its cache is process-local, see the 2026-08-15 crontab note. Warming or unreachable = "nothing to watch", never an error. Same pattern as `orderflow/trade_flash.py`. |
| Live read | `sepa.prices.bulk_live_prices` (price + `change_pct`) against each band, every 5 min in RTH. |
| Cap gate | `catalysts.promo_circuit.market_caps_for` (weekly shares cache × live print). **Unknown cap is skipped** — "big companies" means a *known* $1B+; an ETF or a name the shares cache never saw does not qualify. (The promo board keeps unknowns *visible* for the opposite reason.) |
| Kind | `demand_alert` — new kind, default on (`push/subs.py`), separately mutable at /notifications; in the *Essentials* preset. |

### Tiers (`read(last, band, change_pct)` — pure)

| tier | condition | push |
|---|---|---|
| **AT** | inside the band, or ≤ `AT_PCT` = 1% above its top | one push per (symbol, band, ET day): `🧲 NTAP 0.6% above demand $180–183.5` → `/sepa/NTAP?tab=supply` |
| **NEAR** | 1–3% (`NEAR_PCT`) above the top **and down on the day** | read, listed in `hits`, counted in `near` — **no longer pushed since 2026-09-05** (the phone gate below: NEAR is by definition more than 1% above the band; `skipped_proximity`). The digest now carries only AT spill-over. |
| — | below the band (breakdown), flat/up on the day at 1–3%, unknown day change | silent |
| — | **not an arrival**: yesterday's close was already inside that tier's ring (≤1% / ≤3% above the top), or prev close unknown | silent (`unknown_prev` counted) |

**Arrivals only** — the first dry run (2026-09-03, after the close) found **58** names already
inside a band (the reached board's whole population) and 18 nearing: 58 pushes at 9:33. A name that
closed in the band yesterday is the board's business; the phone gets the day it *arrives*
(`prev_day_close` from `bulk_live_prices`). A reclaim from under the floor counts as an arrival.

Dedupe: Mongo `demand_alert_state`, `_id = SYM:lo-hi:YYYY-MM-DD:tier` (**fixed 2 dp since
2026-09-05**, `NTAP:180.00-183.50:2026-09-05:at`; `:g` collapsed two bands on a $10,000+ name; the key
is shared with `zone_edge`'s near-demand side, so both changed together — a weekend deploy, no
same-day re-push). Written only on a *terminal* outcome (delivered, or nobody targeted — muted pref /
no device); a transport failure retries next pass.

Session gate: 9:32–16:00 ET on NYSE trading days — weekends AND the house holiday calendar
(`market_hours.reminder.is_market_day`, fix 2026-09-05), module refuses outside. Cron:
`3-58/5 9-16 * * 1-5 python -m supply_demand.demand_alerts` (`backend/crontab`).

### Phone gate (2026-09-05)

> **2026-09-06 — proven lids + the plan line.** The room half of the gate skips
> a lid with < 2 touches or strength < 40 (`alert_gates.is_proven_band`) and
> the push body ends with the plan (`alert_gates.plan_txt`): buy = the band,
> stop = 0.5% under its floor, target = the first proven lid. See
> `docs/supply_demand/proven_lids.md`.


**Ajay 2026-09-05 (verbatim, mid-fix):** *"When alert I need the same logic. Need only alerts on
stocks that have atleast 5% to Supply and also <1% bounce from demand zone"*. Shared module
`backend/supply_demand/alert_gates.py` (also called by `zone_edge` and `zone_bounce_alerts`).
**Boards unchanged** — the demand board and `hits` list as before; only the phone tightens.

| owner setting | value | from his sentence |
|---|---|---|
| `ALERT_MIN_ROOM_PCT` | **5.0** | "atleast 5% to Supply" |
| `ALERT_MAX_ABOVE_DEMAND_PCT` | **1.0** | "<1% bounce from demand zone" |

* Distance: `AT_PCT` was already **1.0** (inside / ≤ 1% above the top), so the AT tier's distance is
  unchanged; `demand_proximity_gate(print, band)` is applied to every push candidate and by
  construction only the NEAR tier (1–3% above) fails it → NEAR stops pushing (`skipped_proximity`).
  One sliver (review 2026-09-05): the tier measures `(px − hi) / px`, the gate `px <= hi × 1.01`
  (`(px − hi) / hi`), so an AT hit between 0.99% and 1.0% on the print basis — about 1¢ on a $100
  name — is counted `skipped_proximity`. Silence, never a wrong push; pinned by
  `test_an_AT_hit_is_measured_on_the_print_but_the_phone_gate_on_the_band_top`.
* Room: `room_gate(print, bands, prev_close)` against the name's **`zone_store` doc** (loaded once per
  pass for the candidate names; injectable as `store=`) — at least 5% from the print to the first
  **unbroken** supply band overhead (supply with `hi >= print` and not `hi < prev_close`, plus demand
  bands above the print). CLEAR passes, `IN_BAND` fails, `< 5%` fails (`skipped_room`). A name with **no
  store doc** has an unknown room and stays silent (`unknown_room`): "at least 5% to supply" cannot be
  asserted about supply nobody measured. The board's own demand bands come from the demand-reentry
  engine, not the store, so this is the only place supply enters this module.
* Push bodies gain the read before the cap: `$211 · tested 3x · room: clear runway · $3.0T · AAPL Inc`
  / `· room +5.2% -> $222 ·` (the wording `zone_bounce_alerts` already used); digest lines likewise.
* Counters ride in the pass result and the `DEMAND-ALERTS:` log line: `skipped_room`,
  `skipped_proximity`, `unknown_room`.

### Why the board, not a fresh zone scan
The board *is* the app's definition of a demand zone worth the phone. Re-deriving zones
per symbol here would be a second definition, and a cold full-universe zone pass is
minutes. Cost per pass: one HTTP read + one bulk price call + cached caps.

## 2. Curated half — `catalysts/gabbar_watch.py` NEAR tier

The watcher (2026-08-27) already pages **inside or within 1% of a band, either side**,
kind `pivot_alert`, once per (ticker, band, day). Added 2026-09-03:

* `NEAR_PCT = 3.0`: price **above** a band, within 3% of its top **and down on the day**
  → `🎯 Nearing a Gabbar level · NTAP $186.9 2.4% above Gabbar aggressive ($180–183) · down 1.1% today`.
* Above-only + falling on purpose: from below is a fade into supply, flat/up is departing.
  `change_pct` unknown → the tier stays silent (the 1% touch still fires).
* Tier-aware dedupe (`gabbar_watch_state.tier`): the 10:00 heads-up never eats the 14:00
  arrival. Pre-09-03 docs have no `tier` and count as "at".
* Still `pivot_alert` — the curated list gains no new kind (standing 2026-06-24 keep-set).

## Traps

* **NTAP has no Gabbar level** (`gabbar_levels.get_bands("NTAP")` → None) and on 2026-09-03
  its engine read was INTO_SUPPLY with the nearest demand band 16% below — the ask
  generalised from what he saw on a chart, so both halves were built rather than a
  one-name fix.
* Import-side `demand_reentry.cached_or_warm` from the cron container is always cold —
  use HTTP.
* `pankaj_alert` re-fires every 5 min with `sent=0` (muted) — unrelated noise in
  `push_history`, not this module.

## Verify in the container

```
docker cp backend/supply_demand/demand_alerts.py cheetah-market-app-api-1:/tmp/da.py
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -c "
import importlib.util as u; s=u.spec_from_file_location(\"da\",\"/tmp/da.py\"); m=u.module_from_spec(s); s.loader.exec_module(m)
import os; os.environ[\"INTERNAL_API_BASE\"]=\"http://127.0.0.1:8000\"
o=m.check_once(push=False, force=True); print({k:v for k,v in o.items() if k!=\"hits\"})"'
```

Tests: `backend/tests/test_demand_alerts.py`, `backend/tests/test_gabbar_watch.py`.
