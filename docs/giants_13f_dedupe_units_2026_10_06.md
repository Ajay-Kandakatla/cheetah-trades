# Giants 13F flows — four data-hygiene defects fixed (2026-10-06)

Surfaces: 🏦 *Where the giants are buying* (`GET /giants/flows`) and the
🧭 rotation modal (`GET /giants/rotation/{sym}`). Code: `backend/giants/`
(`edgar.py`, `flows.py`, `cusips.py`). Tests:
`backend/tests/test_giants_13f_dedupe_units_2026_10_06.py`,
`frontend/src/components/GiantsRotationModal.test.tsx`.

No threshold that decides a flow changed: `_MIN_COUNT_MOVE_USD` ($2M),
`_MIN_ROTATION_MOVE_USD` ($1M) and `_TOP_ROWS` (40) are untouched.

## 1. One canonical filing per (fund, period)

**Defect.** `edgar.cached_filings` returned every cached doc for a CIK.
Citadel has a 13F-HR (filed 2026-08-14, 6,354 positions) and a 13F-HR/A
RESTATEMENT (filed 2026-09-02, 6,351) for Q2-2026, so `symbol_rotation`'s
`[:2]` diffed Q2 against Q2 and Citadel fell out of every ticker's rotation.
The network path kept only the LAST-FILED doc per period, so a NEW HOLDINGS
amendment became the fund's whole book: JANA's Q1-2026 /A (1 position,
$61.5M) and Berkshire's Q1-2025 /A (4 positions) replaced 10- and 39-position
portfolios.

**Fix.** `edgar.filing_index` keeps every 13F-HR and 13F-HR/A for the newest
periods; the amendment type is read off the filing's cover page
(`primary_doc.xml` → `amendmentType`) and stored as `amendment_type` (cached
/A docs from before today are backfilled by the next network refresh).
`edgar.canonical_period`: RESTATEMENT replaces; NEW HOLDINGS is merged into
the original (summed per CUSIP); an amendment of unknown type is ignored
while a complete original exists; a period with only a NEW HOLDINGS or
unknown amendment has NO canonical portfolio (a partial book diffed as a
whole one invents exits). `cached_filings` returns canonical docs by default
(`raw=True` for the stored docs), so every path — network, cache-only,
network-failure fallback, rotation — sees one portfolio per period.

## 2. VALUE reported in thousands

**Defect.** T. Rowe Price Associates files VALUE in thousands (Q2-2026:
3,241 positions totalling 999,124,702). Its deltas were ~1000× too small and
fell under the $1M rotation floor: the VST add 2,643,274 → 2,851,055 sh
(+7.9%) read ~$33k and was dropped.

**Fix.** `flows.normalize_value_units`, per period across the curated funds:
each filing's implied price (value / shares) is compared with the SAME
CUSIP's implied price in the other funds' filings for that period (an exact
period-end reference; matching the same CUSIP also covers bonds' principal
amounts). Median log10 ratio within 0.5 of 0 → dollars; within 0.5 of −3 →
thousands, scaled ×1000; fewer than 10 shared priced CUSIPs or any other
ratio → `undetermined`, logged and left as filed — never guessed. A second
pass rebuilds the reference from full-dollar filings only. Docs carry
`value_units`.

## 3. Stale funds mixed in as current

**Defect.** Greenlight last filed Q4-2023, Scion Q3-2025, Pershing Square
filed a 13F-NT for Q2-2026 (ignored), ValueAct has no XML-era 13F-HR. The
rotation diffed each fund's latest two filings with no period check, so old
moves read as current buyers/sellers, and the header compared quarter labels
as strings — "Q4 2023" > "Q2 2026" — so it read **Q4 2023**. The flows
timeline carried 2023 buckets from Greenlight, and a diff across a missing
quarter landed in one quarter's bucket.

**Fix.** Quarter P = `flows.dominant_period` (the most common latest period;
ties → newer). Rotation and the board's P use only funds with canonical
filings for P and P−1; a diff counts only between consecutive quarters, and
buckets outside the `_QUARTERS`-wide window ending at P are not built. The
rest are listed in `stale_funds` with the reason (`not filed for Q2 2026
(latest Q4 2023)`, `filed a 13F-NT …`, `no Q1 2026 filing to compare
against`), shown as one muted line on both surfaces.

## 4. "HONZZZZ" in the money-out list

**Cause.** The CUSIP map comes from SEC fails-to-deliver files, where NSCC
marks a RETIRED CUSIP by appending `ZZZZ`: Honeywell's pre-spin CUSIP
438516106 reads `HONZZZZ`, the live line is 438516205 = HON. Every fund
"exited" HONZZZZ (−$7.1B) and opened a "new" HON position (+$2.7B).

**Fix.** `cusips.resolve` maps a `…ZZZZ` placeholder to its base symbol only
when that base is live in the map under another CUSIP (HONZZZZ → HON, used
as an IDENTITY only); otherwise it is unmapped and shown by issuer name.
Ordinary symbols (incl. preferreds like BACPRB) are untouched.

**Corrected in the critic round (same day).** The first version NETTED the
old and new Honeywell lines into one HON row. That broke the Δshares × price
convention: the spin retired 438516106 for 438516205 HON + 43849R105 HONA
(Primecap: 488,200 old → 244,100 HON + 244,100 HONA, no trade), so the row
carried the VALUE change and read as "exit −100%" — Wellington −$2.45B while
still holding 5.85M HON, 12 such sellers, HON −$4.65B on the money-out list.
Now `flows.split_cusip_changes`: when ONE fund's rows for a ticker pair an
exit of a retired (`…ZZZZ`) CUSIP with a position in a live CUSIP of that
ticker, the fund/ticker leaves every flow (aggregate, per-fund top moves,
rotation) and is listed in `cusip_changes` as "CUSIP change / corporate
action, not a decision" — the conversion ratio is not in the filing, so the
real decision cannot be separated. A fund that held the retired line and
nothing after is still a real exit; ADR/ordinary pairs (no retired CUSIP)
still net as before.

## Live evidence (read-only probe, 2026-10-06, branch code vs main)

| | before (main) | after (branch) |
|---|---|---|
| VST rotation header | Q4 2023 | **Q2 2026** |
| Citadel VST | missing | **trim −$63.9M (−50.7%)** |
| T. Rowe VST | missing (~$33k) | **add +$33.0M (+7.9%)** |
| stale funds | mixed in | Pershing Sq (13F-NT), Greenlight (Q4 2023), Scion (Q3 2025), ValueAct (13F-NT) |
| funds used for Q2 2026 | — | 34 / 38 |
| timeline quarters | Q4 2022 … Q2 2026 (13) | Q2 2025 … Q2 2026 (5) |

Money-out top 5 (rebuild, network path):

| # | before | after |
|---|---|---|
| 1 | MU −$34.65B | MU −$24.48B (T. Rowe +$10.19B now counted) |
| 2 | MRVL −$24.63B | MRVL −$21.02B |
| 3 | SNDK −$20.35B | SNDK −$19.34B |
| 4 | META −$8.18B | MSFT −$18.04B (T. Rowe −$11.17B now counted) |
| 5 | HONZZZZ −$7.12B | META −$9.41B |

Honeywell: on main HONZZZZ −$7.12B + HON +$2.71B (bogus "new"); the first
branch version one HON row −$4.65B (12 false exits); now (critic round, cache
probe) no HON row in the top 40 — the HON rotation shows only the two real
exits (RenTech −$84.8M, Point72 −$10.2M) and names 12 CUSIP changes
(Wellington, Capital Research, FMR, T. Rowe, Two Sigma, AQR, D.E. Shaw,
Citadel, Primecap, Soros, Millennium, Dodge & Cox). Top-5 money-out is
unchanged (MU, MRVL, SNDK, MSFT, META).

## Critic round (2026-10-06): two small hygiene fixes + one surface mark

- **13F-NT carried forward.** Notices come only from the submissions index,
  so a cache-only rebuild (or a failed submissions fetch) saved
  `notice_periods = []` and Pershing read "not filed for Q2 2026" instead of
  "13F-NT". `_fund_filings` now carries the last rebuild's notices on those
  paths; a successful index read still replaces them. (The doc on main has
  no `notice_periods` yet, so the first NETWORK rebuild seeds them.)
- **Untagged amendment cover stored as `UNKNOWN`.** An /A whose cover page
  was read but names neither RESTATEMENT nor NEW HOLDINGS (or has no
  primary_doc) never got `amendment_type`, so every daily refresh re-fetched
  index.json + primary_doc for it. `edgar.AMEND_UNKNOWN` is now stored and
  treated as unknown (never replaces or merges); a FAILED read still stores
  nothing so it is retried.
- **`units?` mark.** A filing whose VALUE unit is `undetermined` (Trian,
  Scion, Greenlight today) shows a muted `units?` tag next to the fund in the
  rotation modal and the board's top buyer/seller cell.

Not fixed (his call): Honeywell's spin also shows as HONA "new" +$3.43B from
10 funds — a distribution received, not a buy. Nothing in the 13F links the
HONA line to the retired HON line, so it is left as filed.
