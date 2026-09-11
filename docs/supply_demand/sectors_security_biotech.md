# Security + Biotech sectors (2026-09-10)

Ajay:

> *"Can you add another sector security like AI securty and internet security like
> CROWD Strike, NTSK and Robotic software security like BB is an examaple"*

> *"also bio tech and personal medicine and diruptive research companies related to
> medicine"*

Two entries added to `backend/supply_demand/sectors.py` (21 → 23). They render on the
`/supply-demand` Sectors tab and drive `sector_exposures` on every ticker. **No frontend
change was needed** — that board iterates whatever the API sends.

## The rosters

| | id | ETF | n | Tickers |
|---|---|---|---|---|
| Security | `cybersecurity` | CIBR | 13 | CRWD · PANW · ZS · **NTSK** · S · FTNT · NET · OKTA · SAIL · RBRK · VRNS · TENB · **BB** |
| Biotech | `biotech` | XBI | 14 | VRTX · ALNY · RVMD · MRNA · NTRA · BBIO · ARWR · KRYS · IONS · GH · ILMN · TEM · CRSP · NTLA |

His three security anchors set the shape, so the roster covers all three legs: AI-native
endpoint/SOC (CRWD), the internet/cloud edge — SSE, zero trust, identity (NTSK, ZS, OKTA),
and embedded software inside robots and vehicles (BB, QNX). NET is the least pure name —
it is a CDN and developer platform as well as an internet-security business; drop it if a
strict pure-play roster is wanted.

Biotech covers his three: biotech proper, personalized/precision medicine, and the
disruptive platforms — gene editing (CRSP, NTLA), RNA/antisense (ALNY, ARWR, IONS),
targeted therapy (RVMD, BBIO, KRYS), and the read layer that decides who gets which drug
(ILMN, TEM, GH, NTRA).

**Every one of the 27 names printed a bar on 2026-09-10**, checked against `price_cache`
before being typed in, not taken from a model's memory.

## Three things here are load-bearing and invisible in the entries

### 1. The ids are wiring keys, not labels

`sepa/macro_risk.py:73,75` already reserved the exact strings `"cybersecurity"` and
`"biotech"` in its `id → bucket` map, before either sector existed. Using them verbatim
means every roster ticker inherits its macro-event risk bucket for free:

```
CRWD → software_growth   NTSK → software_growth
VRTX → healthcare        CRSP → healthcare
```

A prettier id (`security_software`, `precision_medicine`) would have silently dropped the
whole roster to `"broad"` with no error anywhere. Pinned by
`test_sector_ids_are_the_strings_macro_risk_reserves` plus a NEGATIVE that swaps the id in
and asserts the bucket collapses.

### 2. `sp_tickers` does NOT feed the scan universe

`supply_demand/sectors.py` and `sepa/universe.py` share no code path — verified in both
directions. `sp_tickers` is consumed only by `supply_demand/api.py`, `tracker.py`,
`sepa/breakout.py` and `macro_risk.py`. **Listing a ticker in a sector does not make it
scannable.** A roster ticker outside the universe is a chip that never scans, never charts
and never alerts.

**NTSK was exactly that.** He holds it *and* watches it, and it was in no index layer:
no SEPA card, no `zone_store` doc, and therefore no demand / bounce / supply-break alert
and no paper entry. Fixed in the same commit by adding it to the curated list in
`sepa/universe.py` — the escape hatch that exists for names no index carries. `full` went
2,650 → 2,651.

`test_every_roster_ticker_is_actually_scannable` keeps the two files honest.

### 3. `gap_economics` is omitted on purpose

That field renders a dollar demand-vs-supply bar with a sources line. Neither of these
sectors is a physical bottleneck and no filing supports a supply/demand split, so the
field stays **off** rather than carrying invented numbers — the same choice `ai_software`
and `optical_interconnect` already make. The thesis says it in words instead ("Not a
supply gap — …"). Pinned, together with its negative: any sector that *does* carry
`gap_economics` still has to carry its sources.

## The biotech warning, stated on the board

These names resolve on dated binary events — PDUFA actions, advisory committees, phase-3
readouts. **They gap; they do not walk down into a demand band and bounce**, and a stop
parked at a band floor does not fill anywhere near it through a failed readout. The
thesis string says so, and `test_biotech_thesis_warns_that_these_names_gap` keeps it there.
Treat that board as a watchlist, not as a source of zone entries.

## Deliberately NOT done

**Neither id was added to `AI_SECTOR_PRIORITY`.** That list decides which names LEAD the
Breakouts board under his 2026-06-25 standing rule (chips → energy/nuclear → water/cooling
→ grid → AI software → DC REITs → optical). Security is arguably AI-ecosystem, but adding
it would re-rank every breakout board — a behaviour change, so it waits for his call.
`test_security_is_not_in_the_ai_priority_list_without_his_say` pins the current state so
the decision is explicit either way.

## Tests

`backend/tests/test_sectors_security_biotech.py` (12). Mutation-tested against four
mutants, each caught: renaming an id, removing NTSK from the curated list, fabricating a
`gap_economics` block, and putting a megacap pharma name in both medical sectors.

Also added: `test_no_roster_ticker_anywhere_is_known_dead_or_renamed`, which walks **every**
sector roster against `sepa/symbols.py` `DELISTED`/`RENAMES`. This is the SMAR/SQ failure
mode — SMAR sat dead in the universe for 19 months. The weekly liveness triage now fails
the build here instead of leaving a stale chip on a board he trades.
