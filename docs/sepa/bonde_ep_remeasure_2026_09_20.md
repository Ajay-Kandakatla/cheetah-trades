# Episodic Pivot, re-measured at Bonde's PUBLISHED numbers — 2026-09-20

**Status: script shipped, replay pending.** The table below is EMPTY except for
the 50-name synthetic smoke. The main session fills it after the in-container
replay; nothing here reaches a board until Ajay says so.

## The ask

Ajay, 2026-09-20, his-call #5: **"RE-MEASURE the Episodic Pivot at Bonde's
published numbers before any gate talk."**

The 2026-09-13 audit (`backend/scripts/bonde_audit/lane1.py`,
`docs/sepa/bonde_board.md`) reconstructed Episodic Pivots at **our** detector's
thresholds — an 8% open gap on 5× the 50-day volume — and measured the
EP × sales-gate cohort **−3.11pp** against a date-matched placebo at 21 days
(95% CI −5.28 to −1.16). Those thresholds are ours, not his. His published
entry is a different, looser gate, so the inverted headline was never a test of
*his* rule.

## The two rules, side by side

| | Bonde, published | shipped (`setups/episodic_pivot.py`) |
|---|---|---|
| price leg | `c/c1 > 1.04` — **close vs prior close**, +4% | `(open − prior close)/prior close ≥ _MIN_GAP_PCT` (8%) — an **open gap** |
| volume leg | `v > 3 × avgv50.1` (the 50-day average **excluding** the day itself) | `v / avg50 ≥ _MIN_VOL_MULT` (5×), same exclusion |
| liquidity leg | `v >= 300000` shares | none (the SEPA score is the quality filter) |
| cite | `stockbee.blogspot.com`, quoted at `docs/sepa/sales_confidence_methodology.md:40` | the module's own constants, imported by name |

A third rule is measured as a named **sensitivity**: `published_gap_variant`
reads his 4% as a **gap** (the paraphrase in the 2026-09-20 ask) with his volume
and share legs unchanged, so gap-vs-close is isolated as a number instead of an
argument. **It is not his rule** and its cite says so.

The three rules live once, in `backend/scripts/bonde_audit/ep_rules.py`. The
shipped rule is *imported* from `setups.episodic_pivot`, never retyped — a
threshold change there changes the measurement (pinned by
`backend/tests/test_bonde_ep_published_rule.py`).

## Method

Identical machinery to the audit's headline, on the identical cached panel, so
the only thing that varies is the entry rule:

- **Panel** — `/root/.cheetah/audit_px_v1.pkl` + `audit_fin_v1.json.gz`, closed
  bars 2024-09-13 → 2026-09-11, SPY/QQQ/IWM excluded.
- **Cells** — `A` = rule **and** Bonde's point-in-time sales gate passed,
  `B` = rule, gate failed, `AB` = **the rule alone** (every event, classified or
  not). Sales state is `core.state_asof(..., align="period")`: availability =
  filing date, derived Q4s at end+90d.
- **Placebo** — the audit's own seeded, date-matched draw (`default_rng(11)`,
  700-name pool, 3 draws per event, any name with an event within 21 bars
  excluded) → `C` / `D` / `CD` mirroring `A` / `B` / `AB`.
- **CIs** — 95%, **symbol-clustered** (`core.boot`) *and* **date-clustered**
  (`core.boot_dates`; the date cluster is the binding one on this panel —
  `attack.py` measured it 3.67× wider than iid). Horizons 3 / 5 / 10 / 21 days,
  forward closes from the bar after the event.
- **Reproduction gate** — the `shipped` rule must reproduce lane1.py on this
  panel (780 classified events, A n = 376, 21d lift −3.11pp ±0.05, CI
  −5.28 / −1.16 ±0.10). If it does not, the script prints `PANEL MOVED` and the
  comparison below is on different data — say so here rather than quoting it.

## Results

| rule | cell | n | symbols | 21d median | win % | lift vs placebo (symbol CI) | (date CI) |
|---|---|---|---|---|---|---|---|
| shipped (8% gap · 5×) | rule alone | | | | | | |
| shipped (8% gap · 5×) | rule × sales gate | | | | | | |
| bonde_published (`c/c1>1.04` · 3× · 300k) | rule alone | | | | | | |
| bonde_published | rule × sales gate | | | | | | |
| published_gap_variant (4% **gap** · 3× · 300k) | rule alone | | | | | | |
| published_gap_variant | rule × sales gate | | | | | | |

Reproduction gate: _pending_. Events / classified / unclassified per rule:
_pending_.

**50-name smoke (synthetic bars, no panel)** — the only numbers verified so far,
from `backend/tests/test_bonde_ep_published_rule.py`: on one 50-symbol synthetic
panel his published rule fires on **35** names, the 4%-gap paraphrase on **25**,
the shipped detector on **15**; the 15 flat names fire nothing. That is a
mechanics check, not a market measurement.

## Commands

Inside the api container only — the Massive key and the caches live there, and a
throwaway container falls back to Yahoo and produces false negatives. Outside
RTH (09:30–16:00 ET); minutes on the cached panel.

```
cd /Users/ajay/clinet-test/cheetah-market-app
docker compose exec -T api mkdir -p /root/.cheetah/aud
docker compose cp backend/scripts/bonde_audit/core.py api:/root/.cheetah/aud/core.py
docker compose cp backend/scripts/bonde_audit/ep_rules.py api:/root/.cheetah/aud/ep_rules.py
docker compose exec -T api python - < backend/scripts/bonde_audit/lane1_published.py
```

Heredoc/stdin, never `python /tmp/x.py`. If the caches are gone, run
`fetch.py` first (~80s). The run writes
`/root/.cheetah/aud/lane1_published.json`; paste its markdown table above.

## Caveats — read before quoting any row

Every limit in `backend/scripts/bonde_audit/README.md` applies unchanged,
because it is the same panel:

- **Delisting survivorship is unmeasured** — `load_universe()` is today's
  membership, so anything that went to zero in the window is absent from every
  cell. His rule is looser than ours and therefore fires on *more* small,
  fragile names, so this bias is **larger** here, not smaller.
- **One bull regime**, 24 cross-sections; the date-clustered CI is the honest
  floor.
- **The derived-Q4 availability date is an assumption** (end + 90 days, the 10-K
  deadline); 24.3% of quarterly rows carry `filing_date: None`.
- **~24.6% of EP events are unclassifiable** on fundamentals and the dropout is
  structural (recent IPOs and de-SPACs) — which is why `AB` (the rule alone) is
  reported beside `A`.
- **Gross returns** — no commissions, slippage or borrow.
- **Catalyst type could not be split**; Bonde's own EP taxonomy is
  catalyst-named.

## What did NOT change

**No gate, threshold, detector or rule was changed by this package** (Rule #10).
`setups/episodic_pivot.py`, `sepa/sales.py` and the Bonde board are untouched;
`attack.py` keeps its own inline date-clustered resampler. Whether any number
from the replay reaches a surface — and whether the shipped EP detector should
move toward his published numbers — is **Ajay's call**, after the table is
filled and the CIs are read.
