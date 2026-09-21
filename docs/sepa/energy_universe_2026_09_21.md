# Energy, nuclear and critical minerals added to the theme rosters (2026-09-21)

Ajay, three asks in one sitting:

> "can you add x energy and then other small energy companies in to our list please"
> "Do we have critical minerals in our list?"
> "Also greenland minerals or greenland related mineral companies"

**39 names added** across `nuclear` (+9), `energy` (+11) and a new
`critical_minerals` roster (19). `THEME_UNIVERSE` goes 253 → 292 names,
17 → 18 themes. Nothing was removed and `rare_earth` is untouched.

## What was wrong before

| roster | before | the gap |
|---|---|---|
| `nuclear` | 9 names, reactors only | no fuel cycle at all — CCJ, the largest Western uranium producer, could not be tagged |
| `energy` | 20 names, every one a major, refiner or midstream | no small end, so a small-cap energy move could never tag as energy |
| critical minerals | `rare_earth`, 4 names | no lithium, copper, titanium or antimony anywhere |

`supply_demand/sectors.py` does carry `lithium` / `copper` / `rare_earths`
narratives, but their `sp_tickers` are a dependency read (TSLA, F, GM, ALB,
FCX) — not a roster. None of those names was tagged.

## Validation — every candidate, 2026-09-21, in the api container

A name is added only if it **resolves**, is **not delisted**, carries a bar
dated **2026-09-19 or later**, and clears the boards' own tradeable floor on
50-day median dollar volume. Bar COUNT is never the test — the SDIG lesson.

### Added

| roster | names |
|---|---|
| `nuclear` | XE, CCJ, UEC, DNN, NXE, URG, EU, LTBR, ASPI |
| `energy` | SM, MGY, CRGY, GPOR, NOG, TALO, REPX, VTS, EGY, WTI, REI |
| `critical_minerals` | CRML, ALB, SQM, LAC, SGML, ABAT, FCX, SCCO, TECK, HBM, ERO, IE, NAK, PPTA, UAMY, TROX, IPX, NB, IDR |

**XE is X-Energy Inc**, the SMR / TRISO-fuel name, listed **2026-04-24**. It
carries ~103 daily bars, so every window longer than five months reads as
unknown rather than flat. $6.9B, ~$93M/day.

### Rejected, with the reason

| name | why |
|---|---|
| VTLE, CIVI, BRY | last bar 2025-12-12 / 2026-01-29 / 2025-12-17 — dead in the price cache, would read as a flat 0% (the MRO / HES / CTRA rule) |
| TMRC, PLL, LITM, ARMN | same, last bars 2026-08-10 / 2025-08-29 / 2026-03-13 / 2026-02-18 |
| AMPY, KGEI, NPWR | $2.6M / $0.7M / $1.1M a day — under the tradeable floor |
| KRO, USAU, WWR, GPHOF | $2.7M / $2.9M / $0.4M / $0.1M a day |
| SRUUF | Sprott Physical Uranium Trust — a commodity vehicle, not an operating company |
| PEN | reads like a uranium ticker; it is **Penumbra**, a medical-device company |
| TLNE | no bars (TLN, the real name, was already on the roster) |

## Greenland — measured, not assumed

**CRML (Critical Metals Corp) is the only liquid US-listed Greenland name**:
the Tanbreez rare-earth project, $1.3B, ~$38M/day, full two-year history.

Everything else in the Greenland complex fails for a structural reason, not a
quality one:

| name | result |
|---|---|
| AMRQ / AMQ (Amaroq Minerals) | no US bars — lists in London and Toronto |
| BLUJ (Bluejay), EGDFF, TANB | no US bars |
| GLND | named "Greenland Energy Co" and it is a $52M shell at ~$1.0M/day, under the floor — and an energy shell, not a miner |

**UUUU stays in `rare_earth`.** It is the third name in the Greenland headline
cohort on the 🏛️ POTUS tab, but a ticker lives in exactly one roster and
`THEME_BY_TICKER` is last-wins — a duplicate would silently retag it and move
its sort priority. `_assert_themes_disjoint()` fails at import if that ever
happens.

## Rank

`critical_minerals` sits at **14**, directly behind `rare_earth` (13), because
it is the same story one layer wider: the reactors, batteries and grid all
bottleneck on these inputs. Everything below shifts one rank and relative
order is unchanged — the same rule used for `semi_materials`,
`datacenter_build` and `cloud_infra`. **The rank is mine, not his**; he asked
for the names, not the placement.

## What this does and does not do

A theme roster is a **tag and a measurement cohort**. It decides which label a
name carries on the boards and which theme row it groups under. It is **not**
a signal, not a gate, and not an endorsement — NAK is on the list as a
permitting story with no production, exactly as FRMI sits in `ai_power`.

`_EXPECTED_COUNTS["themes"]` moved from (20, 300) to (20, 320): the roster is
292 and the old ceiling had 8 names of headroom left.

Tests: `backend/tests/test_energy_universe_2026_09_21.py` — 19, including a
negative for every rejected name above.
