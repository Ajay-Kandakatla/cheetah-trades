# Strong VCP gates — what a chart must clear to reach the study board

**Code:** `backend/chart_maps/board.py::strong_vcp_reject` ·
**Guard:** `test_sepa_contracts.py::test_chart_maps_vcp_gate_constants_locked` ·
**Tests:** `test_chart_maps.py`

> Ajay 2026-08-16, looking at AVGO on the board: *"our SEPA VCP has a problem..
> We are not differentiating between Institution selling vs not selling.. Its
> not stage 2 now. Make sure it also has a base formed not institutions selling.
> Make sure it qualifies other Minervinis principles look at AVGO now, its
> breaking a bunch of rules of Minervini."*

He was right, and the miss was mine. The first version of this board asked only
**two** questions — is the entry setup named VCP, and is the base tight — and
treated that as "Strong VCP".

## What AVGO actually looked like

Straight from the scan row that put it on the board:

| Field | Value | Verdict |
|---|---|---|
| `vcp.tightness` | 85 | passes — and this alone got it on the board |
| `is_candidate` | **False** | fails the trend template |
| `rs_rank` | **43** | book wants ≥ 70, "preferably in the 90s" |
| `base_count` | **6**, `is_avoid_stage: True` | late-stage |
| `volume.up_down_vol_ratio` | **0.91** | more volume on down days |
| `up / dn days on avg vol` | **10 up vs 11 down** | fails the Stage 2 volume test |
| `volume.accumulation` | **False** | — |

It was down 5.8% on the day he looked at it.

## The blast radius of the old filter

Re-run against the same scan, of the 265 names that passed the old two-condition
filter:

| Outcome | Count |
|---|---|
| Failed the trend template | **209** |
| Late-stage base | 23 |
| Not Stage 2 | 11 |
| Distributing | 5 |
| **Actually qualified** | **17** |

**94% of that board was wrong by the book's own standard.**

## The gates now, each with its source

1. **Trend Template first.** *"Stocks must first meet my Trend Template to be
   considered a potential SEPA candidate"* — **TLSW p.34**. That is exactly what
   `is_candidate` encodes (`trend.pass_all AND liquidity.liquid`, **p.79**).

2. **RS ≥ 70.** *"The relative strength (RS) ranking … is no less than 70, but
   preferably in the 90s"* — **TTLAC §6 (ebook p.106)** criterion 7; same list
   at **TLSW p.79**. Carried separately from the template so a rejection can
   name it — RS 43 is *why* AVGO was there.

3. **Stage 2 only.** *"Stage 2 — Advancing phase: accumulation / Stage 3 —
   Topping phase: distribution"* — **TLSW p.66**, **TTLAC §6 (ebook p.104)**.
   Institutions selling **is** Stage 3 by definition, which is the
   differentiation Ajay asked for.

4. **Not a late-stage base.** *"By the time a fourth or fifth base occurs (if it
   gets that far), the trend is becoming extremely obvious and is definitely in
   its late stages. By this point, abrupt base failures…"* — **TLSW p.81**.
   `base_count.is_avoid_stage` encodes it.

5. **Institutions not net sellers.** Stage 2 requires *"more up days and up weeks
   on above-average volume than down days and down weeks on above-average
   volume"* — **TLSW p.71-72**. Checked **directly** on `up_down_vol_ratio` and
   the day counts, not via the coarse label (see the gap below).

6. **The base is tight.** Contractions *"correct less and less from left to right
   on successively lower volume as the supply diminishes"* — **TTLAC §6 (ebook
   p.110)**; volume dry-up at **TLSW p.226**.

`strong_vcp_reject()` returns the **reason** rather than a bool, so a rejection
is inspectable: *"AVGO — fails the trend template"* beats *"AVGO → False"*.

## Why the coarse label was not enough

`volume.accumulation_strength` only reads `"distributing"` when the up/down
volume ratio is **≤ 0.70** (`DIST_RATIO_THRESHOLD`) or CMF ≤ −0.10. AVGO sits at
**0.91** — so the label said `"neutral"` while the tape failed the book's own
Stage 2 test (11 down days vs 10 up days on above-average volume).

That gap is why gate 5 checks the ratio and the day counts itself instead of
trusting the summary label.

## Open — the stage classifier has the same gap, and I have NOT changed it

`sepa/stage.py` downgrades Stage 2 → Stage 3 only when
`accumulation_strength == "distributing"` or `cmf_signal == "outflow"`. By the
same arithmetic, **AVGO stays labelled Stage 2** despite failing p.71-72's
verbatim up-days-vs-down-days test. That is very likely why Ajay expected S3.

I left it alone deliberately: `stage.py` feeds the scanner **and Auto-Pilot's
entry gate**, so tightening it changes what the engine will buy with real money.
That is a decision to take explicitly, not a side effect of fixing a study
board. The proposal, if wanted:

```
Stage 2 by MA geometry
  AND (accumulation_strength == "distributing"
       OR cmf_signal == "outflow"
       OR dn_days_on_avg_vol > up_days_on_avg_vol)   # <- the book's own test
  -> downgrade to Stage 3
```

## Not advice

These gates decide which charts appear as **study examples**. They are not a buy
signal — `is_buyable` remains the strict entry gate, and `is_candidate` is the
watchlist tier (**p.79**), never a buy.
