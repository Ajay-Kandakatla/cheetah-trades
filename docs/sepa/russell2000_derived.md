# The Russell 2000 we serve is DERIVED, and it is short

2026-09-18. `backend/sepa/universe.py::fetch_russell2000` /
`russell2000_coverage`.

Ajay 2026-09-18: *"Yes add it"* — answering my offer to track the Russell 2000
for index additions alongside the 1000 and 3000, after a refresh found zero
changes across the six tracked indices and I had to tell him the 2000 was not
tracked at all.

---

## Read this first

**We cannot produce a real Russell 2000 today.** What ships is FTSE's own
definition of the index — Russell 3000 minus Russell 1000 — computed off the two
iShares exports on disk. It is definitionally correct and materially incomplete.

| Measured 2026-09-18, api container | |
|---|---|
| `fetch_russell1000()` | **1,001** names |
| `fetch_russell3000()` | **2,559** names |
| derived `russell2000` | **1,560** names |
| share of a ~2,000-name index | **78%** |
| age of both iShares exports on disk | **107 days** (≈2026-06-03) |
| Russell 1000 names NOT in our Russell 3000 | **`CBC`, `FRMI`** |

The shortfall is the **source's**, not the parse's: the IWV export we hold lists
~2,570 tradeable holdings, not ~3,000, and the missing names land in the
small-cap tail — which is exactly this list's population.

**Treat it as part of the Russell 2000, never as the Russell 2000.**

---

## The ladder

```
1. backend/sepa/data/iShares-Russell-2000-ETF_fund.xls   (IWM)  -> ishares-local
2. set(fetch_russell3000()) - set(fetch_russell1000())          -> derived-r3000-minus-r1000
3. []                                                            -> empty
```

There is **no curated fallback** and **no network branch**.

* No curated fallback, because the curated list is large-cap leaders — the
  opposite population. Serving it under this name would invent membership.
* No network branch, because the iShares CSV endpoints serve a Cloudflare
  interstitial (see the comment above `_DATA_DIR` in `universe.py`); a product-id
  URL for IWM appears nowhere in the codebase and an untestable stub is worse
  than an honest absence.

Order in the derived list is the **Russell 3000's own order**, filtered, so the
result is deterministic run to run.

The derived branch writes **no disk cache**, deliberately: the only thing that
can write `russell2000`'s cache file is the local-xls branch, so a cache hit is
unambiguous provenance rather than an inference. A derivation re-runs from the
parents' own caches and is two set operations.

---

## `russell2000_coverage()`

Every number is read off the parents at call time — nothing in the served
payload is a literal, including the label, so a refreshed file moves the string
with the data.

```json
{
  "index": "russell2000",
  "n": 1560,
  "source": "derived-r3000-minus-r1000",
  "complete": false,
  "attributable": false,
  "derived_from": { "russell3000": 2559, "russell1000": 1001 },
  "parents_not_contained": ["CBC", "FRMI"],
  "label": "russell2000 (derived: russell3000 2559 - russell1000 1001 = 1560)",
  "note": "…"
}
```

`complete` is `true` **only** when an IWM export supplied the list.

---

## A derived diff cannot name the parent that moved

FTSE guarantees the Russell 1000 is a subset of the Russell 3000. Ours is not —
`CBC` and `FRMI` sit in our IWB export and not in our IWV export. The two files
are therefore already out of step, and an attribution built on them ("this name
left the 2000 because it entered the 1000") would be confidently wrong some of
the time.

So every change row on this index carries:

```
attributable:      false
attribution_note:  "Derived list (russell3000 minus russell1000). A name leaving
                    may have entered the Russell 1000 or may only have moved in
                    one parent export; this diff cannot tell which."
derived_from:      {"russell3000": 2559, "russell1000": 1001}
```

Best-effort attribution, labelled as such, is the alternative. It was rejected
for v1 and is a HIS CALL item.

---

## HIS CALL — the file only he can fetch

To turn this into the real list:

1. Open `https://www.ishares.com/us/products/239710/ishares-russell-2000-etf`
   in a browser. **Verify the product id on the page before saving.**
2. Click **Download Holdings** — it gives a SpreadsheetML `.xls`, not a CSV.
3. Save it as
   `/Users/ajay/clinet-test/cheetah-market-app/backend/sepa/data/iShares-Russell-2000-ETF_fund.xls`

`fetch_russell2000()` then reads it and `complete` flips to `true` **with no code
change**. I cannot download it — the page is Cloudflare/JS-gated.

While he is there: **IWB and IWV are 107 days old** and near the loader's
120-day warning, possibly predating the June 2026 reconstitution. Refreshing both
also lifts the Russell 3000 above 2,559 and shrinks this list's shortfall.

Any new or refreshed export in `sepa/data/` also needs the backend suite's
universe snapshot regenerated in the same commit (added 2026-09-24,
`docs/sepa/universe_test_snapshot.md`). `test_hermetic_universe_2026_09_24.py`
fails with the command until it is:
`.venv/bin/python scripts/refresh_universe_test_snapshot.py` from `backend/`.

**The file drop publishes no fabricated additions.** The source-change
re-baseline in `universe_changes.refresh_one` (documented in
`docs/sepa/universe_changes.md`) writes the new snapshot and skips the change
log, because a ~410-name jump caused by a file copy is not a corporate event.

---

## Not done

* `russell2000` is **not** in the scan-universe picker. A 78%-complete list must
  not become a scan universe. HIS CALL.
* Nothing here is measured, nothing claims an edge, nothing gates, alerts or
  enters. Index adds were measured on 2026-09-01 to give no buyable growth.
