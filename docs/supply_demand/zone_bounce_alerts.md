# Zone-bounce alerts (`zone_bounce_alert`) + the 9:20 zone store

**Ask (Ajay 2026-09-03):** *"NTAP did hit the demand zone in the morning and bounced
back immediately 20 point I am looking for those."*

Configured heuristic, S/D scope, **NOT a book method, no Minervini cites**. Decision
support, not a buy signal, not advice.

## What NTAP actually did (verified 1-min forensics, 2026-09-03)

| | |
|---|---|
| prev close | 180.77 |
| pre-market | 158.23–168.27 |
| 09:30 RTH bar | open 161.95 (−10.4% gap), **day low 161.00** in the first minute |
| 09:33 | 171.2 (+6.3% off the low) |
| 09:42 | 178.38 (+10.8%) · 09:57 ≥ 181 · 11:49 high 187.45 (+26.45, +16.4%) |

The engine has **no demand band at 161** — nearest daily demand tops are 157.2 (API
geometry) / 158.99 (board geometry). What the low hit is a **broken-supply shelf**: board
geometry (`demand_reentry.zone_geom()`, swing 5 / merge 4% / half-width 1.75%) supply band
**161.78–167.54, 1 touch, strength 18**. The open printed inside it, the low undercut its
floor by 0.48%, then price reclaimed it and the next broken-supply band 173.87–180.07
within twelve minutes. Old resistance acting as support (S/R flip) **must count**.

Every band involved has `touches=1` and strength 15–24. The demand board (`MIN_TOUCHES=2`,
`MIN_ZONE_STRENGTH=40`, demand bands only, scores the **close**) and the board-fed
`demand_alerts.py` pass (board-qualified bands + live print) are therefore structurally
blind to it. Hence two new pieces.

## 1. Zone store — `backend/supply_demand/zone_store.py` (9:20 ET weekdays)

| | |
|---|---|
| Universe | `sepa.universe.load_universe("full")` filtered to a **known** market cap ≥ $1B from the weekly shares cache (`sepa.volume_movers._shares_coll()` docs carry `market_cap`). Measured 2026-09-03: 1,751 → **1,124** names. No provider call per symbol. |
| Bars | `sepa.prices.load_prices(sym, "2y")` (shared Mongo price cache). **Rows dated today ET are dropped** before anything is computed — the frame may carry a partial today bar via `patch_latest_closes`, and a band drawn from today's own low would be instantly "touched". `prev_close` and `atr14` come from the truncated frame. |
| Bands | `price_zones.compute(df, max_zones=None, **zone_geom())` → **demand AND supply** `{kind, lo, hi, touches, strength}`. `max_zones=None` keeps every cluster (the shelf price meets *first*, not the four strongest). Never `price_zones.for_symbol` (overlays today's live bar = one snapshot HTTP call per symbol) and never `promo_live._zones_compute`. |
| Doc | Mongo `zone_store`: `{_id: "NTAP:2026-09-03", symbol, date (ET session), geom: "board", bands, atr14, prev_close, computed_at}` via `portfolio.store._get_db()`. `load(symbols, date)` reads them; `python -m supply_demand.zone_store` warms and reports count / seconds. |
| Cron | `20 9 * * 1-5` — five minutes before the demand board's 9:25 warm. 6 workers, 240 s budget. A symbol whose frame is `None` is counted as skipped, never raised. |

## 2. The 5-min pass — `backend/supply_demand/zone_bounce_alerts.py`

Session gate weekdays **9:33–16:00 ET**. Data: `sepa.prices.bulk_snapshot(syms)` **directly**
(250-per-call chunks) — it carries the day **low**, `last_trade_price`, `last_trade_ts_ms`
(ns), `prev_day_close`; `bulk_live_prices` drops the low.

**Print** = `last_trade_price` when its stamp is within `STALE_PRINT_SEC = 600` of now; else
the print is STALE and the bounce leg is skipped for that name (`stale_print` counted).
On 2026-09-03 Massive aggregates lagged ~3 h after 13:13 ET — an old price is not a bounce.

### The rule — `read(day_low, print, prev_close, band, atr14)` (pure)

| step | condition | constant · rationale |
|---|---|---|
| eligible | demand bands, **plus supply bands with `hi < prev_close`** (broken supply = support) | a supply band still overhead is resistance |
| TOUCH | `day_low <= hi·(1+1%)` **and** `day_low >= lo·(1−1.5%)` | `TOUCH_TOL_PCT=1.0` a wick that stopped just short · `WICK_PCT=1.5` NTAP undercut by 0.48% |
| ARRIVAL | `prev_close > hi·(1+3%)` | `ARRIVAL_PCT=3.0` yesterday was outside — residence never fires (demand_alerts' 58-push lesson, same day) |
| BOUNCE | `print > hi` **and** `print >= day_low·(1 + max(3%, ATR14/day_low))` | `BOUNCE_MIN_PCT=3.0`; the ATR term scales the bar to the name's own volatility. Gap-through-and-keep-falling never fires (`print <= hi`). |
| STRONG | `bounce_pct >= max(5%, 2·ATR14/day_low)` | `STRONG_PCT=5.0` → its own push |

Cap gate: `catalysts.promo_circuit.market_caps_for(syms, prints)` + `demand_alerts.passes_cap`
— unknown cap is **skipped and counted** (`unknown_cap`). Dedupe once per **(symbol, band, ET
day)** — Mongo `zone_bounce_state`, `_id = SYM:lo-hi:YYYY-MM-DD`; written only on a terminal
send (delivered, or nobody targeted → muted pref / no device); a transport failure retries.

### Pushes per pass

* STRONG → individual pushes, strongest first, at most `MAX_SINGLES_PER_PASS = 3`.
* Everything else fresh (weak bounces + strong overflow) → **one digest**, ≤ 6 names, `+N more`.

| | example |
|---|---|
| single title | `🪃 NTAP bounced +6.3% off demand $161.78-167.54` |
| single body | `$171.2 · low $161 -> +$10.2 · broken supply -> support (tested 1x) \| demand (tested 3x) · 2.3x ATR · $37.4B · NetApp` |
| single url | `/sepa/NTAP?tab=supply` |
| digest title | `🪃 Bouncing off demand - NTAP +6.3% +4 more` → `/chart-maps?tab=zones` |

Payload carries `"kind": "zone_bounce_alert"` (push/history.py records `payload["kind"]`; the
same fix was applied to `demand_alerts.py`'s payloads, which had logged `kind=None`). Owner via
`portfolio.alerts._resolve_owner`; sent with `push.sender.send_to_user(owner, payload, kind=KIND)`.
Default pref **on** (`push/subs.py`), in the *Essentials* preset, mutable at /notifications.
Cron: `4-59/5 9-16 * * 1-5` (demand_alerts 3-58/5, gabbar 6-56/10).

## Measured — 5-session replay, 281 deterministic $1B+ names (read-only, api container, 2026-09-03)

Every 4th name of the sorted $1B+ universe + NTAP (282 asked, 281 frames). Per session D: bands
from the frame truncated **before D** (board geometry, `max_zones=None`); `day_low_D` vs the
eligible bands (touch incl. broken supply); **close_D vs low_D as the bounce proxy** (the live pass
reads the 5-min print, so an intraday bounce that faded by the close is not counted here).
Compute: 1.7 s for 281 names × 5 sessions.

| session | names | touched a band | touched + bounce ≥3% | ≥5% | **would fire** (bounce rule + ARRIVAL gate) | of which STRONG | bounce but residence (suppressed) |
|---|---|---|---|---|---|---|---|
| 2026-08-28 | 280 | 198 | 8 | 2 | **0** | 0 | 3 |
| 2026-08-31 | 279 | 195 | 12 | 3 | **1** (CDP) | 1 | 3 |
| 2026-09-01 | 279 | 199 | 11 | 0 | **0** | 0 | 4 |
| 2026-09-02 | 279 | 193 | 29 | 6 | **0** | 0 | 16 |
| 2026-09-03 | 279 | 187 | 24 | 7 | **2** (DOCN, NTAP) | 1 | 4 |

Fires: `CDP 08-31 demand 32.56–33.72 (1 touch) low 33.27 close 36.0 +8.2%` ·
`DOCN 09-03 broken supply 97.49–100.97 (1 touch) low 101.73 close 109.67 +7.8%, ATR 7.63` ·
`NTAP 09-03 broken supply 161.78–167.54 (1 touch) low 161.0 close 185.81 +15.4%, ATR 6.91`.

Reading: with every 1-touch band kept, ~70% of names "touch" some band on any day — the
touch alone is noise. The bounce floor cuts that to 8–29 per 280, and the **ARRIVAL gate** is
what makes it a phone kind: 0–2 fires per 280 names per session → roughly **0–8 per day** across
the 1,124-name universe, digest-first. The 16 residence suppressions on 09-02 are exactly the
"58 names already in a band" failure mode demand_alerts hit the same day.

### NTAP itself on 2026-09-03 (stored bands, prev close 180.77, **measured ATR14 = 6.907**)

| band | kind | touches | strength | touch | arrival | 09:33 print 171.2 |
|---|---|---|---|---|---|---|
| 161.78–167.54 | supply (broken) | 1 | 18 | **yes** (undercut 0.48%) | yes | bounce **+6.34%** ≥ floor 4.29% → **fires** |
| 153.53–158.99 | demand | 1 | 15 | no (top+1% = 160.58 < 161) | — | — |
| 146.66–151.88 | demand | 1 | 17 | no | — | — |

**Measured deviation from the design brief:** the brief assumed ATR14 ≈ 4.5 (floor 3%, strong
5.59% → the 09:33 print is a STRONG single). The real ATR14 as of the 09-02 close is **6.907**
(NTAP had just run 20 points), so the floor is 4.29% and the strong floor 8.58%: at 09:33 NTAP
**fires as a digest item**, and the 09:42 print (178.38, +10.8%) would have been strong — but the
once-per-band-per-day dedupe means the 09:33 digest is the one notification. The rule is
implemented exactly as designed; only the tier at 09:33 differs from the brief's example. Both
ATR cases are locked in `test_zone_bounce_alerts.py`.

## Traps

* `zone_store` cold (warm failed / first day) → the pass reports `zone store empty for today` and
  does nothing. Check `docker logs cheetah-market-app-cron-1 | grep ZONE-STORE`.
* The band a low "touches" with `max_zones=None` is often a 1-touch shelf — that is the point
  (NTAP), not a bug. Strength is displayed, never gated here.
* `last_trade_ts_ms` is **ns** on current Massive payloads; `print_from_snapshot` normalises ns /
  ms / s.
* Universe count: the brief said ~1,269 $1B+ names; the shares cache has 1,278 ≥ $1B overall
  but only **1,124** of them are in the full universe.

## Verify in the container (read-only)

```
docker cp backend/supply_demand/zone_store.py cheetah-market-app-api-1:/tmp/zs.py
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -c "
import importlib.util as u; s=u.spec_from_file_location(\"zs\",\"/tmp/zs.py\"); m=u.module_from_spec(s); s.loader.exec_module(m)
from sepa import prices; import datetime
print(m.build_doc(\"NTAP\", prices.load_prices(\"NTAP\"), datetime.date(2026,9,3)))"'
```

Tests: `backend/tests/test_zone_store.py`, `backend/tests/test_zone_bounce_alerts.py`
(+ `test_demand_alerts.py` for the payload `kind`).
