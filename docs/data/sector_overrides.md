# Sector / industry overrides

**Shipped 2026-09-19.** Ajay, on a screenshot of WULF's Chart Maps tile:

> "They are all wrongle categorizerd OKLO is nuclear power, IREN is mining.."

## What was wrong

Audited all **253** themed names against the provider label the app serves.
The label does not merely mislabel a few tickers — it **fragments every theme**:

| theme | how the provider scatters it |
|---|---|
| `ai_power` (20) | Technology 7 · **Financial Services 6** · Industrials 4 · Utilities 1 |
| `nuclear` (9) | Industrials 4 · Utilities 4 · Energy 1 |
| `crypto` (17) | **Financial Services 10** · Technology 3 · Comm Services 1 · none 3 |
| `robotics` (19) | Technology 8 · Industrials 8 · Consumer Cyclical 2 · Healthcare 1 |
| `space` (12) | Industrials 7 · Comm Services 3 · Technology 2 |

**16 names** arrived as `Financial Services / Capital Markets`. Only **COIN**
and **HOOD** belong there.

## Why — the root cause, not a careless vendor

TeraWulf's own EDGAR filer header carries **SIC 6199 "Finance Services",
CF Office 09 Crypto Assets**. That is a filing-ROUTING code, not a business
descriptor. Every vendor mapping SIC → sector inherits it.

**GICS disagrees**: miners sit in Sector 45 **Information Technology**
(45103010 Application Software), and the S&P DJI / MSCI consultation of
2026-07-17 proposes moving them to 45102030 Internet Services & Infrastructure
— still IT, never Financials.

The provider already ignores the SIC for **APLD, CIFR and CORZ** (same trap,
correctly Technology), so this table makes the treatment *consistent* rather
than inventing a taxonomy.

## What it was breaking

Two surfaces rank **peer-relative** and both read this label:

- `/sepa/longterm/{symbol}` scored WULF **19.6 against 406 "Financial
  Services" peers** — a loss-making data-centre build-out graded against banks
  on ROCE, ROE and D/E.
- The rotation grid takes sector and industry **medians**. WULF's served badge
  read `🧊 cold Capital Markets −2.5% vs RSP`.

## Where it is applied

`backend/companies/sector_overrides.py` — `SECTOR_OVERRIDES` (ticker →
sector, industry, **basis**) and `apply(doc)`.

Healed at **four** read points, because `companies.store` is not the only door:

| reader | why it needs its own call |
|---|---|
| `companies/store.py` `get()` ×2 paths | the documented front door |
| `companies/store.py` `get_many_cached()` | the BATCH path every board uses |
| `sepa/longterm.py::_sector_map` | queries Mongo directly; **builds the peer pool** |
| `growth/tracker.py`, `growth/api.py` | query Mongo directly |

A test scans for `db.companies.find` + `sector` and fails if a new reader
appears without the override — comments excluded, so documented queries don't
trip it.

## Invariants

- **The provider's answer survives** as `sector_provider` / `industry_provider`.
  A wrong correction is visible and reversible, never destructive.
- **Never written back to Mongo.** The cache keeps the provider's answer, so
  the table can be edited or removed and the data is still true.
- `apply()` is **idempotent** — `get()` and `get_many_cached()` can both touch
  one doc.
- Every row carries a **citable basis** (filing, SIC or GICS). Pinned: a basis
  that cites nothing fails the suite. *Rule #1 — no invented classification.*
- **No decision module reads it.** Zero files under `supply_demand/` or
  `trading/` reference it, pinned by test. This moves a **label and a peer
  group** — it gates no alert, sizes no position and enters no lane.
- Themes (`universe.THEME_BY_TICKER`) are a **separate axis** and deliberately
  not mirrored. A diversified industrial that also makes robots genuinely is
  Industrials.

## The 14 corrections

| ticker | from | to |
|---|---|---|
| WULF, IREN, MARA, RIOT, HUT, CLSK, HIVE, ARBK, BTBT, SLNH | Financial Services / Capital Markets | Technology / Information Technology Services |
| OKLO | Utilities / Independent Power Producers | Industrials / Specialty Industrial Machinery |
| MIR | Industrials / Specialty Industrial Machinery | Technology / Scientific & Technical Instruments |
| FLNC | Utilities / Renewable | Industrials / Electrical Equipment & Parts |
| NXT | Technology / Solar | Industrials / Electrical Equipment & Parts |

**OKLO is the shape of the whole bug**: a pre-revenue reactor developer sitting
in the peer group of VST (~44,000 MW) and CEG ($7.50B quarterly revenue). VST,
CEG and TLN keep their IPP label — they were never the defect.

## Reviewed and deliberately NOT changed

`REVIEWED_NO_CHANGE` records the reason for 16 more, so a later pass does not
"discover" them: COIN, HOOD, GLXY (genuinely financial), SMR, LEU, BWXT, CEG,
TLN, VST, AGX, APLD, BE, CIFR, CORZ, BTDR, NNE.

## Open — his call, not a fact a filing settles

| ticker | the fork |
|---|---|
| **BTCS · SBET · DFDV** | crypto **treasury vehicles**. P&L is a levered coin proxy, not an operating business. "Financial Services" is arguably *right*; the industry string is the real question. |
| **FRMI** | pre-revenue with a REIT election (SIC 6798) — election argues Real Estate, intended business argues data centres, no revenue to test. |
| **NNE** | provider already right; at $214K of nine-month revenue a peer score is noise whatever the label. |

Related: a separate finding, **not** actioned — for pre-revenue names (SMR
$75K/quarter, NNE $214K/nine months) a peer-relative fundamental score is noise
regardless of sector. Suppressing rather than ranking those is a **scoring**
change and needs its own sign-off.
