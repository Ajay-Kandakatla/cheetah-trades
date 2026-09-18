# Index membership change tracking

`backend/sepa/universe_changes.py` · endpoint `GET /universe/changes` ·
cron `30 6 * * 0` (Sunday 06:30) in `backend/crontab`.

Cited from `main.py` since 2026-08-16; written 2026-09-18.

---

## What it is for

Ajay 2026-08-16: *"we have too keep updating. 1. Latest tickers as they change
like getting added to SP 500 or Russel 3000 and Nasdaq."*

`universe.py` re-fetches each constituent list on a **30-day disk cache**
(`UNIV_CACHE_TTL_SEC`) and keeps no history, so a name added to the S&P 500
could take a month to enter the scan and nothing anywhere said it was new. This
module forces past that cache, diffs each list against the last snapshot, and
records the adds and drops.

It **never edits the universe.** `universe.py` stays the single source of truth
for who gets scanned; this only observes. A diff that looks wrong is always safe
to ignore.

**An index add is a liquidity event, not a setup.** Measured 2026-09-01: index
adds give no buyable growth, and Russell adds lose ~10pp against peers between
announcement and effective date. Nothing here gates, alerts or enters.

---

## The seven tracked indices

`TRACKED`, in refresh order:

| Index | Source |
|---|---|
| `sp500` | Wikipedia / datahub ladder (`_resolve_index`) |
| `sp400` | same |
| `sp600` | same |
| `nasdaq100` | same, `on_exhausted="empty"` — never the curated fallback |
| `russell1000` | local iShares IWB export → IWB CSV URL → curated fallback |
| `russell3000` | local iShares IWV export → IWV CSV URL → curated fallback |
| `russell2000` | **DERIVED** — see `docs/sepa/russell2000_derived.md` |

`russell2000` is **last on purpose**: it is derived from the other two Russell
lists (FTSE's own definition), so both parents must have been refreshed in the
same run before it is asked for.

---

## The guards

### The churn gate

`is_sane_churn(d)` is `churn <= max(MIN_ABS_CHURN, n_before * SANE_CHURN_FRACTION)`
with `SANE_CHURN_FRACTION = 0.35` and `MIN_ABS_CHURN = 8`.

A parse that loses a column returns a handful of names and a naive differ reports
"488 companies left the S&P 500". An insane diff is **neither snapshotted nor
logged** — storing it as the baseline would turn one bad fetch into two bogus
diffs, the drop and then the re-add.

Russell's annual June reconstitution is the one legitimately large event and
still lands well under the gate (~8% of a 3,000-name index).

### The wrong-universe refusal

A list whose `source` is `curated`, `empty` or `stale-cache` is refused outright:
diffing it would invent adds and drops. Since 2026-09-18 the Russell fetchers
record provenance on every branch (`cache`, `ishares-local`, `ishares-network`,
`derived-r3000-minus-r1000`, `curated`, `empty`), so this refusal now protects
them too — before that their `source` was `None` and a fresh read was
indistinguishable from a stale one.

**First-run side effect of that backfill:** the first cron run after it ships
sees `source` change from `None` to a real label on `russell1000` and
`russell3000`, which is a source change (below) — so both re-baseline once,
silently, with no change rows. Their previous snapshots were unattributed, so
that is the correct outcome.

### The source-change re-baseline (2026-09-18)

**A file copy must never publish as a corporate event.**

The day an iShares IWM export lands on disk, `russell2000` stops being a
1,560-name derivation and becomes a ~1,970-name real list. That churn — about
410 names — sits well inside the sane window (`max(8, 1560 × 0.35) = 546`), so
without a guard `/universe/changes` would answer **"410 additions to the Russell
2000"** about a file that someone downloaded. A fresh IWV lifting `russell3000`
from 2,559 to ~2,900 is the same fabricated event.

So `refresh_one` compares the previous snapshot's stored `source` with this
run's:

```python
prev_source = (prev or {}).get("source")
rebaselined = bool(prev is not None and prev_source != source)
```

When the source changed:

* the **snapshot is still written** — the new list IS the new baseline;
* the `db.universe_changes` insert is **skipped entirely**;
* the returned dict carries `rebaselined: True`, empty `added` / `removed`, the
  raw counts under `raw_diff_not_published` (a key whose name says it was not
  published), and a `reason` naming both sources.

`run()` needs no change: its `changed` filter reads `added or removed`, and both
are empty.

No new constant and no new threshold: the snapshot document has always stored
`source`.

### Non-attributable diffs

A change row for a **derived** index carries `attributable: False`, an
`attribution_note` naming both parents, and the measured `derived_from` counts.
A name leaving the derived Russell 2000 may have entered the Russell 1000, or
may only have moved in one of the two exports — `CBC` and `FRMI` were measured
sitting in our Russell 1000 and not our Russell 3000 on 2026-09-18, which FTSE
guarantees cannot happen, so the two files are demonstrably out of step. The row
says it cannot tell which, rather than guessing.

---

## The endpoint

`GET /universe/changes?days=90&limit=50`

```json
{
  "days": 90,
  "n": 3,
  "changes": [ { "index": "...", "added": [], "removed": [], "attributable": true } ],
  "tracked": ["sp500","sp400","sp600","nasdaq100","russell1000","russell3000","russell2000"],
  "tracked_labels": {
    "russell2000": "russell2000 (derived: russell3000 2559 - russell1000 1001 = 1560)"
  },
  "coverage": { "russell2000": { "n": 1560, "complete": false, "attributable": false } }
}
```

`tracked` stays a list of plain strings — it is the shape any existing reader
expects. The qualifier arrives beside it in `tracked_labels`, built from counts
measured at call time, never from literals. `coverage` is `{}` when the universe
module cannot answer; the endpoint still returns 200.

**No frontend reads this endpoint today** (grep of `frontend/src`, 2026-09-18).

---

## Tests

* `backend/tests/test_universe_changes.py` — the diff, the churn gate, the
  refusals, the cron schedule, and the source-flip exception named in
  `test_a_sane_diff_reaches_the_change_log_UNLESS_the_source_flipped`.
* `backend/tests/test_russell2000_derived_2026_09_18.py` — the derivation, the
  coverage payload, and the four re-baseline negatives.
