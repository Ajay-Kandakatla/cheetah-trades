# Journal & Analytics Methodology — `backend/trading/journal.py` + `backend/trading/analytics.py`

The Auto-Pilot's **read layer**: a round-trip trade **journal** derived from
the raw event log, and the **analytics** that report Minervini's own
performance metrics over it. This layer adds **no trading side effects** — it
only reads the ledger, writes a derived journal collection, and computes
descriptive statistics. It changes none of the trading logic; the stop /
target / sizing / streak math stays in `trading/risk_rules.py` (**FROZEN**,
`docs/sepa/risk_management_methodology.md`).

All page cites trace to `backend/sepa/minervini.pdf`, *Trade Like a Stock
Market Wizard* (2013), Chapter 13 (printed page = PDF page − 15).

Companion docs:
- `docs/sepa/risk_management_methodology.md` — the FROZEN risk math the journal
  records and the analytics measure against.
- `docs/sepa/auto_entry_methodology.md` — the buy funnel whose decisions the
  decision-journal narrates.

---

## 1. The source of truth: `trade_ledger`

The ledger (`trade_ledger` Mongo coll, written by `exit_engine.ledger()`) is
**already the raw event log**. Every row is
`{ts, epoch, kind, symbol, detail, dry_run, cite}`. The journal **derives**
from it; it never duplicates trading state. Rows used to reconstruct a
round-trip:

| kind | written by | what it carries |
|------|-----------|-----------------|
| `entry` | `entries.py` | the entry **and its full plan**: price, qty, stop_price/pct, target_price/pct, reward_risk, breakeven_trigger, regime, size_multiplier, consecutive_losses |
| `auto_entry` | `auto_entry.py` | the funnel decision on an auto buy: path (`intraday`/`close_confirm`), pivot, live, relvol, score, cleared_at_frac — fires **right before** the entry |
| `ratchet_breakeven` | `exit_engine.py` (p.308) | stop moved to breakeven at +3R; presence **between** entry and exit ⇒ the trade reached +3R and was protected |
| `trade_closed` | `exit_engine.py` (p.299) | the exit with realized `gain_pct` and `leg` (`stop`/`take_profit`) |
| `flatten` / `flatten_all` | `exit_engine.py` (p.302) | a **manual** exit — also closes a trade (leg `flatten`) |
| `auto_entry_blocked` / `_disabled` / `_error` | `auto_entry.py` | decisions that did **not** enter (the decision journal) |

`dry_run=true` rows (a disarmed engine narrating what it *would* do) are
**excluded** from the round-trip reconstruction — they never represent a fill.

---

## 2. Reconstructing round-trips (`journal.reconcile`)

Walk the non-dry ledger rows **oldest-first**. For each `entry` row:

1. **Match the trigger.** The most-recent `auto_entry` row for the same symbol
   at/before the entry **on the same ET day** supplies the trigger context
   (`path / pivot / relvol / score / cleared_at_frac`). Manual entries have no
   such row ⇒ `trigger = null`.
2. **Find the exit.** Scan forward for the **next** `trade_closed` / `flatten`
   for that symbol (a symbol-less `flatten_all` closes any still-open symbol).
   No exit yet ⇒ status **`open`**, `realized = null`, `exit = null`.
3. **Note protection.** Any `ratchet_breakeven` for the symbol between entry
   and exit ⇒ `protected_to_breakeven = true`.

**Why next-after-entry pairing is reliable:** the deterministic
`client_order_id` (`cheetah-{SYM}-{etday}-entry`) enforces **at most one
same-symbol entry per ET day**, so an entry and the next same-symbol exit
cannot interleave with a second open lot of the same name.

One journal doc per round-trip, keyed by a **stable** `trade_id =
"{symbol}-{entry_epoch}"`:

```
{ trade_id, symbol, status: "open"|"closed",
  entry: { ts, epoch, price, qty, stop_price, stop_pct, target_price,
           target_pct, reward_risk, breakeven_trigger, regime,
           size_multiplier, mode, trigger: {path, pivot, relvol, score,
           cleared_at_frac} | null },
  protected_to_breakeven: bool,
  exit: { ts, epoch, price, leg: "stop"|"take_profit"|"flatten" } | null,
  realized: { gain_pct, gain_dollars (qty·(exit−entry)),
              r_multiple (gain_pct/stop_pct), holding_days, exit_reason } | null,
  narrative: <plain-English string>, cites: [...] }
```

`gain_pct` comes **straight from the `trade_closed` row** (the exit engine
computed it at fill time, p.299). For a manual `flatten` the row may carry a
fill price but no `gain_pct`; we derive `gain_pct` from `(fill/entry − 1)` when
both are present and otherwise leave it `null` — **never invent a number**.
`holding_days` is **calendar** days between entry and exit epochs (clearly
labelled; weekends/holidays included).

### Perpetual — never pruned
`reconcile()` **upserts** by `trade_id` into `trade_journal` — **no TTL, no
deletes, kept forever**, the same rule as the pattern-accuracy ledger. A trade
history is the raw material every analytic reports on (Minervini's "mortality
tables of your gains", p.298); pruning it would silently corrupt the batting
average and expectancy. `reconcile()` is **idempotent** (stable `trade_id`) and
**cheap**, so it is safe to call at the top of every read handler and once per
engine tick.

---

## 3. Narratives

`narrate(doc)` produces deterministic, factual journal prose — every number
comes from the doc, nothing is invented. Example (winner):

> Bought NVDA — 12 sh @ $182.40. Auto-entry, intraday pivot clear at $181.90
> on 1.6x volume (score 82). Stop $169.63 (-7%, TLSW p.311); target $209.76
> (+15%, 2.14:1, p.301). Stop raised to breakeven at +3R (p.308). Exited via
> take-profit @ $209.80 on Jun 18 2026 — +15.02%, 2.14R, held 4 calendar days.

Losers say "Stopped out"; manual exits say "Manually flattened"; open trades
end at "Position open." `decisions(days=14)` narrates the **why-did/didn't-buy**
log — `auto_entry` / `auto_entry_blocked` / `auto_entry_disabled` /
`auto_entry_error` rows — most-recent-first, with the symbol, the trigger or
veto reason, and the values.

---

## 4. Analytics (`analytics.compute`) — Minervini's own prescription

Pure compute over the **closed** journal docs (open trades are excluded from
batting/expectancy — those are realized only; the journal stays historical).
Every divide guards `n = 0`; empty input returns a zeroed shape with
`provisional = true` and **never raises**.

| metric | formula | page |
|--------|---------|------|
| **batting_avg** | winners / closed trades | **p.298** ("correct … about 50 percent of the time") |
| **avg_gain_pct** | mean of winners' gain% | **p.299** |
| **avg_loss_pct** | \|mean of losers' gain%\| | **p.299** |
| **win_loss_ratio** | avg_gain_pct / avg_loss_pct | **p.301** (target ≥ 2:1, "shoot for 3:1") |
| **expectancy_pct** | batting·avg_gain_pct − (1−batting)·avg_loss_pct | **p.298** (positive expectation; Buffett quote) |
| **expectancy_dollars** | mean realized P&L per trade ($) | **p.298** |
| **avg_r** | mean realized R = gain_pct / initial stop_pct | **p.299** (loss as a function of expected gain) |
| **total_pnl_dollars** | Σ realized P&L | — |
| **total_pnl_pct_on_risk** | Σ realized R multiples | **p.299** |
| **equity_curve** | cumulative realized P&L, **exit-time order** | — |
| **by_trigger** | the above, split `intraday` / `close_confirm` / `manual` | — |
| **best / worst** | trade_id + symbol + gain% extremes | — |
| **open_risk_dollars** | Σ qty·(last − stop) over open positions when last > stop | **p.301-302** (a stop always rests; this is the still-at-risk $) |

### `vs_book` — targets + the half-average-gain stop + red flags
- `target_ratio = 2.0`, `stretch_ratio = 3.0` (**p.301**), `batting_ref = 0.5`
  (**p.298**).
- `half_avg_gain_stop_pct = avg_gain_pct / 2`, capped at 10 (**p.299**: "15%
  on average → 7.5%"; and "not allow any stock to fall more than 10 percent").
  This is the **same quantity** `risk_rules.initial_stop` consumes once there
  are ≥ 20 closed trades — surfaced here as **"your data says your stop should
  be X%"**.
- `flags` — page-cited strings:
  - **The cardinal sin (p.299):** `avg_loss_pct > avg_gain_pct` ⇒
    *"Average loss 8.1% exceeds average gain 6.9% — the cardinal sin (p.299)"*.
    "Never let a loss grow larger than your average gain."
  - **Below the floor (p.301):** `win_loss_ratio < 2.0` ⇒
    *"Win/loss 1.4:1 is below the 2:1 floor (p.301)"*.

### Small-sample rule
Under **`MIN_RECORD_N = 10`** closed trades, `provisional = true` — every
ratio is labelled provisional (n=X). A batting average / expectancy on a
handful of trades is noise and must not be presented as reliable. This mirrors
the app's existing `MIN_RECORD_N = 10` convention in
`sepa/chart_analysis.py`.

---

## 5. API surface (all admin-gated)

- **`GET /trading/journal?limit=&decisions=`** → `{trades: [...closed docs with
  narrative...], open: [...open docs mark-to-market via
  `sepa.prices.bulk_live_prices` (lazy), each with a `mark` block...],
  decisions: [...] when `decisions=1`, summary}`. The journal stays
  pure/historical; the live mark-to-market overlay lives only in the API
  response.
- **`GET /trading/analytics`** → `journal.reconcile()` then
  `analytics.compute(closed, open_marks)`. The open marks feed
  `open_risk_dollars` only.

Both handlers call `reconcile()` first (cheap + idempotent) so the journal is
current even between ticks.

---

## 6. Tick wiring

`exit_engine.tick()` calls `journal.reconcile()` **once at the very end**
(after `auto_entry.run`), inside its **own try/except** and **lazy-imported**,
so a journal failure can never break stop protection or entries, and
`exit_engine` stays import-light (the journal pulls no pandas).

---

## 7. Contracts (Rule #4)

These analytics **report** book metrics; they introduce no new gating formula.
But the cited targets and the cardinal-sin rule are book numbers, so they are
locked in `tests/test_trading_contracts.py`:

- `TARGET_RATIO = 2.0` / `STRETCH_RATIO = 3.0` / `BATTING_REF = 0.5` /
  `HALF_AVG_GAIN_CAP = 10.0` present verbatim in `analytics.py`;
- the **cardinal-sin** flag fires (and cites **p.299**) when
  `avg_loss > avg_gain`; the **2:1-floor** flag cites **p.301**;
- page cites **p.298 / p.299 / p.301** present in `analytics.py` source.

Behavior is locked in `tests/test_journal.py` and `tests/test_analytics.py`
(host `.venv`, FakeColl — no network, no Mongo, py3.9, no pandas/numpy).
