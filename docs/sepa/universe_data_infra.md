# `data_infra` — 🗄️ Data infra, the data-layer theme (2026-09-28)

**Code:** `backend/sepa/universe.py` (`THEME_UNIVERSE["data_infra"]`, the
`cloud_infra` roster, `THEME_PRIORITY`) ·
`frontend/src/components/HottestSectors.tsx` (`THEME_LABELS`) ·
`frontend/src/lib/chartMaps.ts` (`THEME_LABEL`) ·
`frontend/src/lib/newFeatures.ts` · `frontend/scripts/contracts.mjs`
**Tests:** `backend/tests/test_data_infra_theme.py` ·
`backend/tests/test_cloud_infra_theme.py` · `backend/tests/test_theme_priority.py` ·
`backend/tests/test_energy_universe_2026_09_21.py` ·
`frontend/src/components/HottestSectors.test.tsx` · `frontend/src/lib/chartMaps.test.ts`

---

## 0. The ask, verbatim

> Ajay, 2026-09-28: *"Can you create a new sector for DATA driven companies like
> DATA DOG, Mongo DB and Snow flake in to the add them accross board where we
> have sectors"*

"Sector" here is a **theme roster**: the one list every sector surface he reads
enumerates live (🔥 Hottest theme rows, the Hot-sectors strip, `/rotation`,
the Chart Maps tile badge and the opt-in "Themes first" sort).

---

## 1. The cut rule — how the roster was derived

| Step | Rule |
|---|---|
| 1. ANCHORS | his three: `DDOG`, `MDB`, `SNOW` |
| 2. **THESIS — JUDGMENT, mine, not a rule** | "Is the **product itself** the layer where a customer's data is stored, queried, searched or observed — database, data warehouse / data cloud, observability telemetry, search, event analytics, data-integration platform?" |
| 3. SEGMENT | a conglomerate where the data layer is one segment is OUT — `cloud_infra`'s own rule (`MSFT`/`ORCL`/`PLTR` line in its block), applied evenly |
| 4. PARTITION | a ticker lives in exactly one roster; `_assert_themes_disjoint()` raises at import. `MDB` and `TDC` **moved** from `cloud_infra`; nothing else moved |
| 5. LIVENESS | last cached bar == the freshest session **2026-09-28**. **Validated by DATE, never by bar count** (the SDIG trap) |
| 6. LIQUIDITY | 50-bar **average** dollar volume ≥ `20_000_000` — reused **by name** from `rotation.tracker.build(min_dollar_vol=…)` and `trading.safety_floor.MIN_DOLLAR_VOL`; the same metric `cloud_infra` used |

### The exact probe (read-only, api container)

```
docker exec -i -w /app -e PYTHONPATH=/app cheetah-market-app-api-1 python -
```
```python
from sepa import prices, universe as U, symbols as S
full = set(U.load_universe("full"))                       # 2730 on 2026-09-28
frames = prices.bulk_cached_frames(cands)                 # cache only, never fetches
for s in cands:
    df = frames.get(s)
    last = df.index[-1].date() if df is not None and len(df) else None
    avg50 = (df["close"] * df["volume"]).tail(50).mean()
    print(s, last, avg50, s in full, S.is_delisted(s), U.theme_for(s))
db.companies.find({"symbol": {"$in": cands}}, {"symbol": 1, "industry": 1, "_id": 0})
```

No write, no fetch. The freshest session is SPY's last bar, 2026-09-28.

---

## 2. The roster (8)

| Sym | last bar | avg50 $/d | med20 $/d | provider industry | theme before | what it is |
|---|---|---|---|---|---|---|
| SNOW | 2026-09-28 | 1575.1M | 1444.5M | Software - Application | — | data cloud / warehouse — **his anchor** |
| DDOG | 2026-09-28 | 1053.2M | 832.4M | Software - Application | — | observability platform — **his anchor** |
| MDB | 2026-09-28 | 752.3M | 662.6M | Software - Infrastructure | cloud_infra | database (Atlas) — **his anchor, MOVED** |
| DT | 2026-09-28 | 342.2M | 384.0M | Software - Application | — | observability |
| ESTC | 2026-09-28 | 201.8M | 178.7M | Software - Application | — | search / observability (Elasticsearch) |
| TDC | 2026-09-28 | 69.0M | 43.1M | Software - Infrastructure | cloud_infra | data warehouse — SNOW's direct competitor, **MOVED** |
| AMPL | 2026-09-28 | 22.6M | 20.7M | Software - Application | — | product / event analytics (13% over the avg50 floor) |
| PLTR | 2026-09-28 | 5781.5M | 4278.7M | Software - Infrastructure | — | data-integration / analytics platform (Foundry) — **HIS CALL** |

None is in `DELISTED` or `RENAMES`.

**PLTR is IN on the thesis test, not on the count.** Its product IS the
data-integration and analytics platform (the ontology over the customer's
data); the provider files it under "Software - Infrastructure" and
`supply_demand/dependencies.py` tags it "Data analytics". `cloud_infra` called
it an "application platform" — an answer to a different question ("is it hosted
capacity?"). The consequence is stated, not used: **without PLTR the row is 7
and prints `· thin`.**

**Rank 12**, directly behind `cloud_infra` (11) — the same software story one
layer up. **The rank is mine, not his.** Everything below shifts one rank,
relative order unchanged: `defense 13, rare_earth 14, critical_minerals 15,
infosec 16, crypto 17, biotech 18`.

### The row, built through the real builder (cached bars, no provider calls)

`rotation.tracker.group_row`, api container, start 2026-06-01, freshest 2026-09-28:

| Row | n | dropped | thin? |
|---|---|---|---|
| data_infra (8) | 8 | 0 | no — exactly `MIN_COHORT_N`, **zero headroom** |
| data_infra without PLTR (7) | 7 | 0 | **yes, `· thin`** |
| cloud_infra after the move (16) | 16 | 0 | no — 8 headroom |

---

## 3. The move and the naming guard

`MDB` (database) and `TDC` (warehouse) **moved** from `cloud_infra` to
`data_infra`. Disjointness forces one roster per ticker, and he named MDB for
this one. `cloud_infra` drops 18 → **16**, still 8 over `MIN_COHORT_N`.

Three rosters, three businesses:

| Roster | What it is |
|---|---|
| `ai_infra` | the **physical box** — racks, cooling, power distribution |
| `cloud_infra` | the **rented capacity** — compute, file/object storage, edge/CDN, DNS, dev platform, delivery, comms |
| `data_infra` | the **data layer** running on that capacity — database, warehouse, observability, search |

`DBX`, `BOX` and `NTAP` stay in `cloud_infra` (bytes at rest, not a queried data
platform). `NTNX` and `GTLB` stay too. Any further move is HIS CALL.

---

## 4. Exclusions

| Name(s) | Reason |
|---|---|
| ORCL ($4.3B/day), IBM ($1.5B/day, owns Db2 and Confluent), MSFT | **SEGMENT** — the data layer is one segment of a conglomerate. Same call `cloud_infra` made on ORCL/MSFT. HIS CALL |
| PD | **APP** — an incident-response workflow application, not a data layer. It sits under the 50-bar floor ($18.8M) but clears the 20-day median ($21.7M), so the metric does not decide it; the thesis does |
| DOMO | STALE — last bar 2026-09-23 — and $7.2M/day, under the floor |
| CFLT | in `sepa.symbols.DELISTED` (last bar 2026-03-16, acquired by IBM) — never re-add |
| BASE | last bar 2025-09-23 (Couchbase, taken private) |
| FROG, KVYO | last bar 2026-08-31 |
| CWAN | last bar 2026-06-24 |
| INFA, SWI, PSTG | no cached bars |
| PRGS | mixed infrastructure-software portfolio (cloud_infra precedent) |
| SPGI, ICE, MSCI, FDS, VRSK | **data vendors** — they sell their own data; the customer's data does not live in them. HIS CALL |
| P (Everpure), QMCO | storage hardware — HIS CALL |
| CVLT | backup; its peer RBRK sits in `infosec` — HIS CALL |
| IOT, AI, AVPT, BRZE, RAMP, ZETA, OTEX, INOD, NTCT | applications / services / appliances — the product is not the data layer |
| FSLY | edge cloud — capacity-shaped, not data |
| NTAP, NTNX, GTLB, DBX, BOX | PARTITION holds — they stay in `cloud_infra` |

---

## 5. The cost — what actually changes

- **Net-new names to `full`: 0** (2730 → 2730), measured in the api container:
  every one of the 8 is already in sp1500 ∪ russell3000 (2,559) ∪ curated. No
  new name gets zone bands, no new push or paper-entry eligibility, no gate
  moved. On the host, `test_nothing_is_net_new_to_full` **skips**: without lxml
  `fetch_russell3000()` falls back to ~1,020 names, outside
  `_EXPECTED_COUNTS["russell3000"]` (1800, 3200), so reachability cannot be
  measured there.
- **Tile badge + heat side-read.** Chart Maps tiles for the 8 carry
  `theme: "data_infra"`; `rotation/heat.py` uses the theme only as a side read,
  never the headline.
- **Themes first + `MAX_PER_THEME`.** The sort is opt-in
  (`THEMES_FIRST_DEFAULT = False`). When ticked, `MAX_PER_THEME = 6` now covers
  the 6 previously untagged names (SNOW DDOG DT ESTC AMPL PLTR): a 7th+
  data_infra tile is demoted behind the other themes as a tail — never dropped,
  and never under an explicit sort. MDB and TDC free two `cloud_infra` slots.
- **Rotation history.** `cloud_infra`'s series changes composition on
  2026-09-28 (18 → 16). `data_infra` has no history before that date. **On day
  one it can read `＋ data_infra #N`** in the Changes line
  (`rotation/history.py`: no prior rank + top-6 above the benchmark = "entered").
  That is a **new row, not an inflow**.
- **Zero headroom.** A member leaves `n` only when its last bar is more than
  `MAX_STALE_DAYS` (10) calendar days behind the freshest bar, or it has no
  bars. One such member prints `· thin`. Liquidity drift does not drop a member
  (the admission floor is not re-checked).
- **Themes band.** 298 of the `(20, 300)` band. The next roster add needs the
  band moved — a guard change, his call.
- **Deploy `api cron frontend`.** The rotation doc is built in the cron
  container after the 16:30 fast-scan and by the 08:40 desk report; api-only
  would alternate old and new rosters. The row appears after the next build.

---

## 6. The S&D sector list (`supply_demand/sectors.py`) — untouched

It is a separate system (26 rows, no disjointness; `ai_software` already lists
SNOW and PLTR). It feeds the `/supply-demand` page, the Morning/Overnight
"Global supply / demand snapshot", the per-ticker S&D drill, the 📈 Bonde tab's
display-only "Theme (the app's map)" fact leg, breakout AI-first ordering (only
for ids in `AI_SECTOR_PRIORITY`) and the `macro_risk` bucket map.

Not touched because no theme precedent (cloud_infra, biotech, infosec, critical
minerals) touched it, and on 2026-09-11 he said *"i dont use supply deman page
at all.. I only been using chart maps"* (84df3cf). The counter-precedent is
165a060 (his "another sector security" ask did add rows there). HIS CALL.

---

## 7. HIS CALL

1. **PLTR and/or ORCL.** Default PLTR IN, ORCL OUT (8, not thin). PLTR out → 7,
   `· thin`. ORCL added → 9, 1 headroom, themes 299/300.
2. **Roster boundary.** TDC moved with MDB (default yes). NTAP/NTNX/GTLB/DBX/BOX
   stay in `cloud_infra`. CVLT and P stay untagged. Data vendors stay out.
3. **Name, label, rank.** `data_infra`; 'Data infra' on Hottest, '🗄️ Data infra'
   on Chart Maps tiles; rank 12 — the placement is mine.
4. **An S&D `sectors.py` row.** Default not built (§6). If yes: he picks the ETF
   (IGV / WCLD) and the narrative; the row stays out of `AI_SECTOR_PRIORITY`
   and the `macro_risk` map.
5. **Label backfill** on the strip / `/rotation` (raw keys) and the 8 themes
   missing from Chart Maps `THEME_LABEL`. Default not done.
6. **Day-one "＋ entered".** Default unchanged; requiring a prior-session row is
   a rotation-history semantic change.

---

## 8. No edge is claimed

Sector/industry heat measured **null** against demand outcomes on 2026-09-09
(−0.57pp, CI spans zero). This cohort has never been measured. The row is
context; it gates nothing.

---

## 9. Found, not done

- Host `test_cloud_infra_theme.py::test_the_universe_grows_by_exactly_the_two_declared_names`
  was already red at a2f6144 (host R3000 fallback, 1,020 names). It needs the
  same russell3000-band skip — the hermetic-suite branch owns that.
- CWAN is in `full` with a last bar of 2026-06-24 (a DELISTED candidate after a
  boundary-bar check).
- DOMO is 3 sessions stale while still in `full`.
- `P` ("Everpure, Inc.", bars from 2026-04-17) vs `PSTG` (no bars) looks like a
  PSTG → P rename missing from `symbols.RENAMES`. UNVERIFIED.
- BASE is dead since 2025-09-23 and not in `DELISTED` (harmless: not in `full`).
