# Breakout Breadth — methodology

Requested by Ajay 2026-07-10: *"we need at least a few breakouts in a day for
the best entry and gauge the market — lmk if I am going against Minervini."*
Book check (brain RAG, both books) said: **aligned as a market gauge, against
the book as an entry gate** — so this feature reads the market and guides
**exposure only**. His explicit constraint: "don't do anything against
Minervini, do per him."

Module: `backend/sepa/breakout_breadth.py` · UI: Breakouts page strip ·
Endpoint: `GET /sepa/breakout-breadth` · Cron: 17:12 ET weekdays.

## Book anchors (retrieved verbatim from the brain RAG 2026-07-10)

| Claim | Cite |
|---|---|
| Expanding waves of breakouts = strength | TLSW p.164 "multiple waves of stocks emerging into new high ground"; TTLAC §7 (p.131) "your list of leaders expands… a sign of strength" |
| Failing breakouts = hostile tape | TLSW p.303 "getting stopped out… the general market environment is hostile"; TTLAC §6 (p.117) "Rarely does a correct pivot point fail… in a healthy market"; TTLAC §1 (p.37) failed follow-through = "a major sell signal" |
| Breadth governs EXPOSURE, stepped up on wins | TLSW p.307 "pilot buys… require that at least a few trades work out"; TTLAC §5 (p.91-92) "On the heels of each win, I double my position size" |
| Never an entry gate | TLSW p.165 "if you concentrate on the general market solely for timing your individual stock purchases, you're likely to miss many of the really great selections"; TTLAC §7 (p.131) "buy in order of breakout"; §7 (p.124) lone leader without confirming names is "normal" |

**No passage in either book gates an entry on a same-day breakout count** —
searched explicitly; the confirmation Minervini describes accrues via the
leader list and your own positions over days, not a daily quota.

## What is computed

- **Count** — distinct symbols per ET day with the scanner's volume-confirmed
  breakout flag (`volume.days_since_breakout == 0`; detection itself is
  close > 21-bar high on >1.5× 50-day volume, book p.203).
- **Grade** (once the window completes, vs daily closes):
  - `failed` — any close back **below the level it broke**
    (`volume.recent_high`) — the §6 p.117 / §1 p.37 failure signature
  - `followed_through` — no undercut AND the window-end close is above the
    breakout-day close (§1 p.29 "multiple days of followthrough action")
  - `stalled` — held the level, went nowhere
- **Read** — `exposure_read(today, avg10, failure_rate, graded_n)`:
  HOSTILE / EXPANDING / HEALTHY / MIXED, each with guidance text quoting its
  book anchor. HOSTILE requires ≥5 graded breakouts (no p.303 calls off two
  data points).

## House values (NOT book numbers — configured, honesty-notes convention)

| Constant | Value | Note |
|---|---|---|
| `FT_WINDOW_BARS` | 5 | book quantifies no day count for follow-through |
| `EXPANDING_MIN_RATIO` | 1.25× the 10-day mean | "expanding" is the book's word, the ratio is ours |
| `FAILURE_RATE_HOSTILE` | ≥50% (min n=5) | "failing wholesale" quantified |
| `FAILURE_RATE_HEALTHY` | ≤25% | |

## Hard boundary (contract)

Exposure guidance ONLY. Not consumed by the scanner, the auto-entry funnel,
or the Market Gauge score (adding it to the gauge would change live engine
behavior — that needs a separate signed-off decision). The API payload and
the UI both carry the boundary sentence verbatim.
