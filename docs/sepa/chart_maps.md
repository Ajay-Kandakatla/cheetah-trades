# Chart Maps — the charts-only study board

**Route:** `/chart-maps` · **API:** `GET /chart-maps` · **Code:**
`backend/chart_maps/`, `frontend/src/pages/ChartMaps.tsx`,
`frontend/src/components/PatternChart.tsx`, `frontend/src/lib/chartMaps.ts`

> Ajay 2026-08-15: *"I need just maps that you are pulling show… The goal for me
> is to look at patterns and learn them day by day… Also with then that page
> show me a previously winning stocks with similar patterns."*

A study surface, not a fourth scanner. The scans already exist; this page shows
their output as **charts with the qualifying geometry drawn on** so the shape is
what you remember, and every tile clicks through to that ticker's SEPA detail.

---

## The three tabs

| Tab | Source | What a tile draws |
|---|---|---|
| 📐 **Strong VCP** | the persisted SEPA scan (`scanner.load_latest()`) | base box (`base_low`→`base_high`), solid PIVOT line, dashed STOP |
| 🟢 **Back in Demand** | the demand-reentry board cache | demand band + up to 2 supply bands, BUY / STOP / TARGET |
| 🏆 **Past Winners** | `pattern_observations` (Mongo) | BREAKOUT / TARGET / STOP levels + a dated confirmation marker |

All three return the **same tile shape**, so the frontend has one rendering path:

```
symbol, name, href, bars[{t,o,h,l,c,v}], bands[{kind,lo,hi,label}],
lines[{price,label,tone}], markers[{date,label,kind}], stats[{k,v}],
why, theme, badges[{text,tone}]
```

### Selection rules

**Strong VCP** — `entry_setup.type == "VCP"` **AND** `vcp.tightness >= 70`.

Both halves are load-bearing. `entry_setup.type` is the scanner's read of what
the chart *is*; `tightness` (banded in `vcp.py` as tight ≥70 / developing 40-69
/ early <40) says the contractions have actually converged. Either alone admits
charts that do not teach the pattern. Tiles carry the tier badge verbatim —
**Qualifier** (watchlist tier: trend + liquidity, Minervini p.79) is never
rendered as **Buyable**.

**Back in Demand** — `is_reentry == true`, which is already the composite
(`band.is_reentry AND trend_ok AND quality_ok`). Rows arrive sorted by `-plan.rr`.
Note `trend_ok` is literally `not is_knife`; they are not two independent signals.

**Past Winners** — `{kind: "pattern", status: "confirmed", outcome: "target_first"}`.
The ledger's grader (`patterns/history.py::_grade_pattern`) races the measure-rule
target against the stop over 21 bars, and **counts a same-bar touch of both as the
stop**, so `target_first` is already the pessimistic reading.

---

## Honesty rules, and why each exists

1. **The losses ship with the wins.** Every winners payload carries
   `record.overall` (wins, stop-firsts, n) and a per-pattern breakdown. A
   winners-only wall is a highlight reel.

2. **Observations already past target when recorded are excluded.** If
   `obs_close >= target`, the move had happened before the ledger saw it, so the
   chart teaches nothing about the entry. Measured 2026-08-15: **8 of 117**
   raced observations. The count is reported as
   `excluded_already_past_target`, not silently dropped.

3. **Patterns are never ranked against each other by win rate.** Their stop
   brackets differ roughly 2x — a double bottom's stop sits far below entry, a
   cup's handle stop is tight — so a higher win rate does not mean a better
   pattern. `by_pattern` is ordered by **sample size**, and the payload carries
   the caveat string. This is the exact comparison the 2026-07-10 pattern audit
   found broken; `test_winners_record_never_ranks_patterns_against_each_other`
   locks it.

4. **Small samples stay labelled.** Under 20 resolved observations the frontend
   shows a `small n` chip (`isThinSample`).

As of 2026-08-15 the ledger holds **109 usable raced observations** — 57 target
hits, 52 stop-outs. Per pattern: double bottom 28W/13L, triple bottom 12W/4L,
cup-with-handle 17W/32L, inverse H&S 0W/3L. Read each against its own bracket.

---

## The theme universe

`sepa/universe.py::THEME_UNIVERSE` — five hand-kept rosters (42 names):
`quantum`, `nuclear`, `robotics`, `ai_semis`, `ai_infra`.

> Ajay 2026-08-15: *"make sure the new companies like Quantum based and Power
> based and robotics based and then Semis all are considered."*

**Why a hand list and not a bigger index.** S&P's index committee requires
positive GAAP earnings and US domicile. Measured 2026-08-15: `fetch_sp1500()`
resolves to **1,506** names and misses **12 of the 22** theme tickers Ajay
named:

| Theme | Absent from sp1500 |
|---|---|
| Quantum | IONQ, RGTI, QBTS, QUBT, ARQQ — *no quantum name is in any S&P tier* |
| Power / nuclear | OKLO, SMR, NNE (VST, CEG are in sp500; TLN only via the sp400 layer) |
| Robotics | SERV, RR, SYM (TER, ISRG are in sp500) |
| Semis | ARM, ALAB, CRDO — ARM is structurally excluded from every S&P *and* Russell list, being a UK-domiciled ADR |
| AI infra | CRWV, NBIS, APLD, MOD |

That is not a bug in the fetchers to fix; it is what an index *is*. So the names
arrive by hand, tagged with the theme that earned them the slot.

**These names bypass nothing.** They enter the same trend, falling-knife and
liquidity filters as every other symbol. The list decides who gets *looked at*,
never who passes. They are pre-profit, thin and high-beta by construction —
which is exactly why the knife guard and liquidity tier stay on.

New universe keys:

- `sepa.universe`: `fetch_themes()`, `theme_for(symbol)`, plus `themes` /
  `sp600` / `sp1500` registered in `_fetch_component` (see the bug note below)
- `demand_reentry.UNIVERSES`: `sp1500_plus` (= sp500 + sp400 + sp600 + themes,
  **1,525** names, deduped) and `themes`. `DEFAULT_UNIVERSE` stays `sp1500` so
  no existing caller widens silently.

**Ordering.** `themes_first=true` (the default) leads with theme names, then the
tab's own metric — Ajay's standing rule that a board leads with the AI-ecosystem
winners. The page has a checkbox to turn it off.

---

## Two bugs found and fixed alongside this

**`load_universe("sp1500")` silently returned the curated ~158 names.**
`fetch_sp1500` and `fetch_sp600` existed but were absent from `_fetch_component`'s
`fetchers` map, so `SEPA_UNIVERSE_MODE="curated,sp1500"` logged one warning line
and quietly scanned a twentieth of the intended universe. Both keys are now
registered.

**The 16:55 demand-board cron warm warmed the wrong process.**
`demand_reentry`'s cache is a process-local dict, so
`python -c "…demand_reentry.scan()"` inside the **cron** container filled a cache
that nothing ever reads and that died with the process — the **api** container
still cold-started on the first page view. The entry now calls the endpoint over
HTTP (`http://api:8000`, internal to the compose network), so the API warms its
own memory. A second entry at 16:57 does the same for `sp1500_plus`.

---

## Performance

The board **never scans**. It reads the scan file, the demand-board cache and
the Mongo ledger. The demand tab returns `warming: true` immediately and the
page polls every 10s — a cold 1,500-name pass outlives Cloudflare's ~100s cut,
which was the 2026-08-14 524.

Tiles are **ranked on metadata first, and only then** do the top `limit + 6`
load price frames, concurrently (8 workers). Ranking after fetching meant
loading 265 frames to display 24; on a cold price cache that is minutes.
Measured warm: **0.23s** for 24 VCP tiles, **0.15s** for 24 winners.

---

## Tests

- `backend/tests/test_chart_maps.py` — 27 tests on synthetic frames with the
  price loader, scan file and Mongo collection stubbed. Negatives: missing price
  frame, non-trading confirmation date, frame without OHLC, `vcp: null`,
  `tightness: null` (<2 contractions), `entry_setup: null`, `plan: null`, the
  `warming` envelope, an unavailable ledger, and NaN/Inf coercion.
- `backend/tests/test_demand_reentry.py` — theme-universe layering, dedupe of a
  name in both the index and a roster, a failing theme layer, and a regression
  that plain `sp1500` is unchanged.
- `frontend/src/lib/chartMaps.test.ts` — 44 tests on geometry and formatting.
- `frontend/src/components/PatternChart.test.tsx` — 11 render tests, including
  that a tile with no bars renders nothing and an off-window marker is skipped.
- `frontend/src/pages/ChartMaps.test.tsx` — 10 page tests whose fixtures are
  copied from the REAL endpoint response, so they double as a contract test: a
  renamed field in `board.py` fails here instead of silently rendering blank
  tiles. Locks that the winners tab always shows its stop-first losses and that
  the demand tab says "scanning" rather than "nothing matched" while warming.

---

**Not advice.** The winners tab shows a measured sample of what happened to past
setups. It is a study aid — position sizing and stops still decide the result.
