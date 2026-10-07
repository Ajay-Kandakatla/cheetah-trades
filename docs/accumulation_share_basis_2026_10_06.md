# 13F accumulation flow — shares, not price-drifted dollars (2026-10-06)

## Defect

`backend/supply_demand/accumulation_changes.py::compare_maps` subtracted dollar
VALUES: today's top-10 holder picture (`whales_cache`) minus our stored
prior-quarter picture (`whales_snapshots`). The provider values every holder at
the price on the day the picture was fetched, so the two pictures sat at two
different prices and the "flow" moved with the price.

VST: the 2026-08-23 snapshot was valued at $158.51 a share, today's picture at
$148.38. The old read was **-$1,156,781,846 (-6.02%) "distributing"** across 8
overlapping funds. On shares the same 8 funds net **bought ~+481,500 shares
(+0.40%)**. Vanguard Capital held exactly 21,393,858 shares in both, yet its
value fell $3.391B -> $3.174B. The Sunday 07:00 `accumulation_change` push
(`MIN_NET_CHANGE_USD` $25M) could fire on a price move with no shares traded.

## Fix

- `share_map` / `snapshot_price`: per fund shares, and the ONE price a picture
  was valued at (median value / shares).
- `compare_maps(before_shares, after_shares, price)`: per overlapping fund
  Δshares; every $ figure is Δshares × today's snapshot price. `basis:
  "shares"` travels with the result.
- A row with no share count is `unknown_funds` — never compared, never
  rebuilt from its dollars.
- Funds joining / leaving the top-10 are valued at the same common price and
  labelled list changes ("joined top-10" / "left top-10"), not proven exits.
- `is_significant` accepts only `basis == "shares"`. Thresholds unchanged.
- `take_snapshot` now banks `shares` and `price` beside the display dollars.
- `sepa/position_lens.py`: the 13F distribution trigger said "Top exit"; the
  name is the deepest share TRIM (`pct_change` < -10%) of a fund still holding
  -> "Top seller (trim)". That read counts funds by share change (whales.py),
  so the price-drift defect does not reach it.

## Consequence until the next 13F roll

Every snapshot banked before today holds dollars only, so every current
comparison reads "not comparable — snapshot predates share counts". Live
whales cache: 1,341 comparable / 1,119 significant before -> 0 / 0 after.
Comparisons resume on shares when the 09-30 quarter rolls in.

Evidence only (not in code): rebuilding the old snapshots' shares from each
fund's 13F `pct_change` (implied prior price agreed within 1% across funds on
1,029 of 1,341 tickers) flips 358 "distributing" reads and 191 "accumulating"
reads, and changes 416 push decisions. VST -> +481,494 sh, accumulating.

Tests: `backend/tests/test_accumulation_share_basis_2026_10_06.py`.
