# `cloud_infra` — the cloud theme, RXT, and ZI → GTM (2026-09-18)

**Code:** `backend/sepa/universe.py` (`UNIVERSE`, `THEME_UNIVERSE`, `THEME_PRIORITY`) ·
`backend/sepa/symbols.py` (`RENAMES`) ·
`frontend/src/components/HottestSectors.tsx` (`THEME_LABELS`) ·
`frontend/src/lib/newFeatures.ts`
**Tests:** `backend/tests/test_cloud_infra_theme.py` ·
`backend/tests/test_symbols.py` · `backend/tests/test_theme_priority.py` ·
`backend/tests/test_biotech_theme.py` ·
`frontend/src/components/HottestSectors.test.tsx`

---

## 0. The ask, verbatim

Ajay approved three items with **"yes go"**:

1. Add `RXT` (Rackspace, ~$1.88B) to the curated list so it lands in `full` and
   gets zone bands. It is DOCN's closest direct hosting peer, currently in
   `broad` only, with **zero** `zone_store` docs — so it can never alert.
2. Create a cloud / SaaS theme so that class can reach the 🔥 Hot Sectors strip.
   None of the 16 themes was cloud/SaaS/devtools; `infosec` was the only
   software theme at all. Themes are a **strict partition**.
3. Add the `ZI → GTM` rename to `symbols.RENAMES`.

**What he said yes to for item 2 was an 8-name roster called `cloud_hosting`.
This ships a different 18-name roster called `cloud_infra`** — see §6.

---

## 1. The cut rule — how the roster was derived

**Steps 1–4 are mechanical and reproducible. Step 5 is judgment and is labelled
as such everywhere it appears** (the code comment, this doc, and
`test_the_cut_rule_rides_with_the_roster`, which greps the module source for the
word `JUDGMENT`).

### The exact query

Read-only, inside the api container:

```
docker exec -i -w /app cheetah-market-app-api-1 python -
```
```python
db.companies.find({"industry": "Software - Infrastructure"}, {"symbol": 1, "_id": 0})
```

**106 docs on 2026-09-17.** For each, the 50-bar average dollar volume and last
bar date came from `db.price_cache` (`bars[].date / close / volume`).

### The funnel

| Step | Rule | Left |
|---|---|---|
| 1. SOURCE | `companies.industry == "Software - Infrastructure"` — the **provider's own tag**, not taste, not training data | 106 |
| 2. PARTITION | drop anything already in another `THEME_UNIVERSE` roster (20 names). `_assert_themes_disjoint()` raises at import | 86 |
| 3. LIVENESS | last cached bar == the freshest session (2026-09-17). **Validated by DATE, never by bar count** — the SDIG trap (drops 6) | 80 |
| 4. LIQUIDITY | 50-bar avg dollar volume ≥ `20_000_000`, reused **by name** from `rotation.tracker.build(min_dollar_vol=…)`'s own default. **No price floor invented** — 26 of the 235 existing theme members trade under $10 | 52 |
| 5. **THESIS — JUDGMENT** | "Is the **product itself** hosted capacity that someone else's software or data runs on / is stored in — compute, storage, edge/CDN, DNS, database, developer platform, application delivery, communications transport?" | **18** |

### Step 5's discriminator, stated so it can be argued with

* **IN** even though sold as SaaS: `DBX`, `BOX` — the customer's bytes **live in
  the product** and are served from it. Who owns the metal underneath is not the
  test. `TDC` — a data platform others run workloads on; on-prem-heavy today,
  which is a *delivery-model* objection, not a *product* one. `TWLO`, `BAND` —
  communications transport; the product is the pipe.
* **OUT** by the same test: `AVPT` — governance/backup **tooling** that manages
  data living in Microsoft 365. The capacity is Microsoft's; AVPT sells the
  management layer. **That is the discriminator.** `FIVN`, `APPN`, `AI`, `RZLV`,
  `ZETA`, `RAMP`, `YEXT` — applications.

This is the same line `infosec` drew at "pure-play security only". A defensible
stricter roster drops `DBX`/`BOX`/`TDC` → **15 names**, still 7 over
`MIN_COHORT_N`. `test_NEGATIVE_the_step5_judgment_line_is_applied_consistently`
exists so that reversal is a one-line edit.

---

## 2. The roster (18)

Every name: industry `Software - Infrastructure`, last bar **2026-09-17**, not
delisted, no theme collision. Verified in the api container 2026-09-18.

| Sym | $vol/day | px | What it rents you |
|---|---|---|---|
| NET | 1005.1M | 333.94 | edge / CDN platform |
| MDB | 633.7M | 393.42 | managed database (Atlas) |
| NTAP | 461.3M | 196.92 | enterprise + cloud storage |
| TWLO | 458.8M | 246.24 | communications platform |
| AKAM | 383.6M | 107.08 | CDN / edge |
| DOCN | 355.4M | 132.98 | cloud compute — **the anchor of the ask** |
| FFIV | 239.4M | 434.62 | application delivery |
| VRSN | 212.6M | 302.05 | DNS registry infrastructure |
| GTLB | 203.9M | 50.27 | managed developer platform |
| GDDY | 179.4M | 98.15 | web hosting + domains |
| NTNX | 166.5M | 69.97 | hybrid-cloud platform |
| DBX | 131.6M | 37.61 | file / content cloud |
| BOX | 95.6M | 34.67 | content cloud |
| TDC | 77.5M | 29.27 | data platform |
| BAND | 53.6M | 50.51 | communications platform |
| BLZE | 42.6M | 13.79 | cloud storage — **net-new to `full`**, cap $874,646,976 |
| RXT | 41.1M | 3.92 | hybrid-cloud managed hosting — **net-new to `full`**, cap $1,876,645,504 |
| ATEN | 37.5M | 26.95 | application delivery |

**Rank 11**, directly behind `datacenter_build` (10) — it is the layer the
build-out *sells*. **The rank is mine, not his.** `defense`, `rare_earth`,
`infosec`, `crypto`, `biotech` each shift one rank; relative order unchanged.

**`ai_infra` vs `cloud_infra`:** `ai_infra` is the **physical box** — racks,
cooling, power distribution. `cloud_infra` is the **rented capacity** running on
top of it.

### The row, built through the real builder (no provider calls)

`rotation.tracker._load(ROSTER)` → `group_row("cloud_infra", …)`, api container,
2026-09-18, `freshest = 2026-09-17`, `start = 2026-06-01`:

```
n = 18   dropped = 0   dropped_symbols = []   pct_positive_1d = 88.9
median_1d +2.72   median_5d +6.75   median_21d +6.13
RSP       +0.49          +0.07          -2.95
```

`n` is **kept** members, not roster size (crypto prints `n=14` on a 17-name
roster). 18 leaves **10 names of headroom** over `MIN_COHORT_N = 8` before the
row prints `· thin`; the rejected 8-name roster had zero.

---

## 3. Exclusions — what did not make it, and why

**20 partition holds** (they stay where they are; nothing was restructured):
`PANW CRWD ZS S OKTA FTNT TENB QLYS VRNS RPD SAIL NTSK RBRK GEN OSPN` (infosec) ·
`ARQQ` (quantum) · `BKKT` (crypto) · `CORZ CRWV` (ai_power) · `PATH` (robotics).

**MSFT ($13.25B/day), ORCL ($4.50B/day), PLTR ($5.76B/day)** — conglomerates and
application platforms where cloud is a *segment*. Same call `space` made on
LMT/NOC/RTX/BA. **His call** — ORCL is the loudest AI-cloud story of 2026.

**SNOW, DDOG, DT, ESTC** — excluded **only** because the provider files them
under `Software - Application`, which step 1 does not read. **His call.**

**Payments filed under Software-Infrastructure by the provider** —
`XYZ TOST FOUR CPAY WEX RELY STNE PAGS PAYO PGY EEFT ACIW FLYW MQ EVTC IIIV
IMXI PAYS PRTH RPAY PSFE`. Admitting them makes this a fintech index wearing a
cloud label.

**Not hosted capacity (step-5 test)** — `AVPT` (see §1) · `SNPS` (EDA, provider
mis-tag) · `IOT` (telematics) · `CALX` (broadband hardware) · `AEVA` (lidar) ·
`NN` (PNT) · `BB` (IoT/QNX) · `GCT` (B2B marketplace) · `ZETA` `RAMP` (martech) ·
`FIVN` · `APPN` · `DOX` (telecom BSS) · `NTCT` (network monitoring) · `AI` `RZLV`
· `BLSH` (crypto exchange) · `PRGS` · `SABR` (travel GDS) · `TCX` `YEXT` `AIOT`
`CCSI`.

**Stale — validated by DATE, not bar count** — `INFQ` (2026-09-11, **144 bars —
bar count would have let it in**) · `XNDU` (2026-08-25, 104 bars) · `LIDR`
(2026-09-15) · `OLB` (2026-09-16) · `KPLT` (2026-09-14) · `SQ` (2026-09-14, and
superseded by `RENAMES["SQ"] → XYZ`).

**Below the $20M/day floor** — `GRRR` 15.0M · `MQ` 15.4M · `EVTC` 12.1M ·
`IIIV` 8.3M · `PAYS` 8.4M · `IMXI` 7.5M · `CCSI` 5.8M · `TCX` 1.1M · `VHC` 0.7M,
and every sub-$1M name (`REKR USIO AISP AUID CSAI FATN AIFA AIFC XBP`).
**If the floor ever moves, `GRRR` and `MQ` come in first** — said here so a later
session does not "discover" them.

**Delisted — never re-add** — `CFLT` (last bar 2026-03-16) and `SMAR`
(2025-01-21) are in `sepa.symbols.DELISTED`; `GREE` and `SDIG` failed validation
in the crypto work. No `companies` doc at all: `WIX FROG PSTG INFA MNDY`.

**The seven handed names that failed the thesis test** — `PDYN` (robotics) ·
`LIDR` (lidar, stale) · `ZENA` (drones) · `OLB` (payments, stale) · `TLS`
(cyber/cloud **security** — it would belong in `infosec`) · `VERI` (AI
applications) · `GRRR` (mixed, and under the floor). `BLZE` was the one of the
eight that passed, and it is in.

---

## 4. The cost: what "+2 names" actually means

**`full` grew by exactly two**, measured in the api container (where `traders` is
not degraded): **2689 → 2691**. Every other roster member already reaches `full`
via `sp1500` / `russell3000` / curated — which is normal. A theme roster is a
**measurement cohort** for the rotation board's median, not a coverage
mechanism: `infosec` has 15 of 15 already in `full`, `biotech` 31 of 32,
`ai_semis` 20 of 22.

`full` is the scanning universe for five S/D modules, so those two names are now
scanned by all of them:

| Module | Cite | What RXT and BLZE now become |
|---|---|---|
| `supply_demand/zone_store.py` | `:58, :120-124` | zone bands built (both clear `MIN_CAP_USD` / `MIN_BARS`) |
| `supply_demand/demand_reentry.py` | `:1925` | demand-board rows, **reversal** reads |
| `supply_demand/hot_pullback.py` | `:502` | 🔥 Hot Pullback rows |
| `supply_demand/quick_bounce.py` | `:679-680` | 🪃 same-day-turn rows |
| `supply_demand/lid_break.py` | `:463-464` | lid-break rows |

From a board row a **push** requires `alert_gates.room_gate` +
`demand_proximity_gate`; a **paper entry** requires `trading/entries._evaluate`
→ `safety_floor.check`.

### They pass the floors — measured, not assumed

`trading.safety_floor.check` in the api container, 2026-09-18:

```
SF.check("RXT",  price=3.92,  dollar_vol=41_060_000)
  -> {'blocked': [], 'warnings': [], 'market_cap': 1876645504.0}
SF.check("BLZE", price=13.79, dollar_vol=42_600_000)
  -> {'blocked': [], 'warnings': [], 'market_cap': 874646976.0}
```

| Floor | Value | RXT | BLZE |
|---|---|---|---|
| `safety_floor.MIN_SHARE_PRICE` | 2.00 (HARD) | 3.92 ✅ | 13.79 ✅ |
| `safety_floor.MIN_CAP_USD` | 700M (HARD) | 1.877B ✅ | 874.6M ✅ |
| `safety_floor.MIN_DOLLAR_VOL` | 20M (WARN) | 41.1M ✅ | 42.6M ✅ |
| `zone_store.MIN_CAP_USD` | 700M | ✅ | ✅ (1.25×) |
| `zone_store.MIN_BARS` | 120 | 502 ✅ | 503 ✅ |

**NO GATE IS TOUCHED BY THIS CHANGE.** The gates are identical; the population
they run over grew by two. `test_no_gate_moved` pins every one of those
constants as a negative.

Two things to say out loud rather than let him find:

* **RXT at $3.92 is a $4 stock the paper lanes may now buy.** It is above the
  $2.00 hard floor, and theme rosters carry no price floor (26 of 235 existing
  members are under $10). The board's *sector* grain uses `min_price=10.0`,
  which is a different layer.
* **BLZE's cap is 1.25× the $700M floor.** A 20% drawdown puts it under
  `zone_store.MIN_CAP_USD` and its bands silently stop being built. Not a bug.

---

## 5. `ZI → GTM`

`ZI` is **in no universe component**, has **no `companies` doc** and **no bars**
at either provider (re-probed 2026-09-18). So this heals nothing today; it is
prophylaxis against a future index parse returning the old ticker.

**`effective = 2025-05-13`, and it is NOT a provider `list_date`.** The Massive
reference returns `list_date 2020-06-04` for GTM — ZoomInfo's **original IPO** —
and `main.py` renders `effective` to him verbatim as "ZI now trades as GTM
(since …)". Writing the IPO date there would have passed
`test_every_rename_entry_carries_evidence`, which only regex-checks the shape.

The date comes from **our own `price_cache`**, measured the same day, same
collection:

```
GTM   339 bars   first 2025-05-13
RXT   502 bars   first 2024-09-17
BLZE  503 bars   first 2024-09-16
NET / ECHO / XYZ / PPLI   503 bars   first 2024-09-16
```

The window reaches **2024-09-16** for every comparison name, so GTM's series
starting 2025-05-13 sits **eight months inside** it with nothing before —
a first print, not a window edge.

**Live reference lookup, 2026-09-18 (one read-only call, no aggregates):**

```
ZI   -> HTTP 404  {"status":"NOT_FOUND","message":"Ticker not found."}
GTM  -> HTTP 200  active, XNAS, "ZoomInfo Technologies Inc Common Stock"
```

**PARTIAL EVIDENCE — the first entry in the file where this was accepted.** The
usual boundary check (last `ZI` bar, consecutive session, continuous price)
**could not be run**: there is no `ZI` series anywhere. The evidence string says
so explicitly.

**It is not free.** `former_names("GTM") == ["ZI"]` makes `sepa/prices.py
_fetch` spend one dead Massive miss plus one dead yfinance call per **uncached**
GTM load. `CACHE_TTL_SEC = 20h`, so that is roughly **one wasted pair per day,
not per scan**, plus the three `force=True` callers (`demand_history.py:316`,
`rotation/backtest.py:147`, `sepa/cli.py:318`). Nothing crashes:
`splice_history` returns the new frame on an empty old.

**No duplicate.** `_resolve_fates(["GTM","ZI","NVDA"])` and
`_resolve_fates(["ZI","GTM","NVDA"])` both return `["GTM","NVDA"]` — the
IAC/PPLI case its own docstring cites.

---

## 6. What is HIS call

1. **The roster swap itself.** He approved a cloud theme; the 8-name
   `cloud_hosting` list put to him was rejected (**1 of 8 is cloud
   infrastructure**; six are under $7M/day; two were already stale) and replaced
   with these 18. **That is a different list than the one he said yes to.**
2. **The key** `cloud_infra` vs the original `cloud_hosting`.
3. **Rank 11** — mine, not his.
4. **The $20M/day floor and no price floor.** At $15M, `GRRR` and `MQ` join.
5. **MSFT / ORCL / PLTR** — out as conglomerates. ORCL's absence will be noticed.
6. **SNOW / DDOG / DT / ESTC** — out only on the provider's industry tag.
7. **`ZI → GTM`** — shipped with the partial-evidence line; skip it instead?
8. **The `themes` size band `(20, 300)`** now sits at **253**. Not touched —
   47 names of headroom before `_record_count` logs an ERROR that says the scan
   is on the wrong universe when nothing is wrong.
9. **`supply_demand/sectors.py`** got no matching sector (he does not use that
   page).
10. **The 🔥 Hot Sectors strip prints `cloud_infra` with the underscore.**
    `HotSectors.tsx` has no label map at all; `infosec`, `crypto` and `biotech`
    already print raw there. Labelling it would re-label 12 existing chips and
    break two pinned hover strings — out of scope by default.
11. **RXT and BLZE are now push- and paper-entry eligible** (§4).

---

## 7. No edge is claimed

**This cohort has never been measured.** It claims no accuracy and borrows no
other roster's number — least of all `infosec`'s +8.00pp morning.

Sector and industry heat measured **null** against demand outcomes on
**2026-09-09**: −0.57pp with a CI spanning zero, and "cold sector sits there"
came back **inverted** — the cold cohort beat the hot one by 2.55pp at five
sessions. A rotation row is **context, never a gate**.

**Trap:** a deploy alone will not put the row on the board.
`GET /rotation/hottest` never builds — it reads the persisted `scan_context` doc
`_id: rotation`. The row appears only after the next rotation build writes a
fresh doc (end of scan, `sepa.context_refresh`). Until then the tab shows 16
themes and nothing is broken. Same class as the "cron alone doesn't rebuild"
trap.

**Trap:** the provider's `industry` tag is not stable — `SNPS` (EDA) and the
whole payments block sit in `Software - Infrastructure` today. **Re-run the
funnel query before quoting this roster in a later session.**
