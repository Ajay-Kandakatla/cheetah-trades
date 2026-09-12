# AI Servers / Systems — a new AI-ecosystem sector — 2026-09-12

> Ajay, after the breakout board started ranking by recency and surfaced
> HPQ / HPE / DELL / SWKS breaking out on the same day with no AI tag between
> them: *"Add them please"*

## Why a new sector and not a line in an existing one

There was no home for the **integration layer**:

| bucket | what it actually is |
|---|---|
| `ai_chips` | the silicon (NVDA, AMD, AVGO, TSM, ASML…) |
| `memory_hbm` | the DRAM (MU, WDC, SNDK) |
| `cloud_infra` | the **hyperscalers who buy the racks** (MSFT, AMZN, GOOGL…) |
| `optical_interconnect` | the networking (ANET, CIEN, GLW…) |

Nothing covered the companies that put a GPU, its memory, its power and its
cooling into a sellable rack. So `ai_sector_for_ticker("DELL")` returned
**None**, and DELL / HPE / SMCI sank below every tagged name on the AI-first
lists he asked for on 2026-06-25.

## Members

`DELL`, `HPE`, `SMCI`.

**SMCI is included although he did not name it** — a server-OEM bucket without
the most GPU-levered server OEM in it is a bucket that misleads.

## Rank

```
ai_chips → memory_hbm → ai_servers → uranium → power_grid → oil_gas →
water_cooling → grid_equipment → ai_software → datacenter_reits → optical
```

Directly behind the silicon it integrates, ahead of the energy and buildings
that surround the data centre.

## Macro risk

`ai_servers → semis_ai` in `sepa/macro_risk.py`. These names ship
mostly-NVIDIA value, so a **chip export control hits them directly** — SMCI
most of all. Without the mapping they fall through to `broad` and stop
inheriting the one macro risk that actually moves them. Same reasoning as the
`semi_materials` mapping added 2026-09-11.

## It invents no supply gap

`gap_economics` renders a $ demand-vs-supply bar with a sources line, so the
field stays **off** — following the `cybersecurity` / `biotech` precedent. The
thesis says it in words instead:

> Assembly capacity is not the bottleneck — GPU allocation upstream is — and
> the layer earns thin, competitive margins on someone else's scarcity. Being
> adjacent to the shortage is not the same as owning it.

## What was deliberately NOT added

**SWKS and QRVO.** He named SWKS alongside DELL and HPE. Skyworks and Qorvo are
**RF front-end suppliers whose revenue is overwhelmingly handsets** — they broke
out on the same day as the server names, which is co-movement, not membership.
Tagging them AI would pollute the exact ranking this sector exists to fix.
Flagged to him rather than added; `test_NEGATIVE_the_RF_HANDSET_semis_were_deliberately_NOT_added`
records the decision so it cannot quietly reverse. Say the word and they go in.

**HPQ.** PCs and printers, not the enterprise/AI server business. One letter
from HPE and it broke out the same day, so there is an explicit test for it.

## The TER trap, guarded

`macro_risk._build_ticker_buckets` uses `setdefault` — **first sector wins**. A
member already sitting in another sector could be silently re-bucketed, which is
what moved Teradyne out of `semis_ai` on 2026-09-11. All three members are
single-membership, and a test asserts it.

## Measured effect

On the 2026-09-12 scan, the breakout board's top two went from `DHT` / `AVT`
(tankers) to **DELL (+83% sales, +144% EPS)** and **HPE (+34%, +405%)** — both
same-day breakouts that were previously untagged and ranked 3rd and 11th.

Sector membership is context, not a signal. Nothing here gates a scan or a lane.
