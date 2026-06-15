# Price-cache data hygiene

Reference for the integrity guards that keep the Mongo `price_cache` collection
(and its parquet fallback) clean. The SEPA detectors are book-faithful only if
the bars they read are real — a single bad daily bar silently poisons RS rank,
Stage classification, distribution counts, VCP geometry, `dist_200_pct`, and the
`day_change_pct` shown on every card. These guards live in
[`backend/sepa/prices.py`](../../backend/sepa/prices.py); each has a behavioral
test under `backend/tests/`.

## The series the scan reads

`scanner` computes `day_change_pct = last_close / prev_close - 1` and
`dist_200_pct = last_close / MA200 - 1` straight off `load_prices(SYMBOL)`, which
resolves **Mongo → parquet → fresh Massive fetch**. A full fetch
(`_fetch` → `_mongo_put`) *replaces the entire bars array*, so any TTL-miss read
heals the whole series. The cheaper `patch_latest_closes` path only touches the
trailing bar — which is where most corruption is introduced.

## Guards (newest first)

| Guard | Trigger | Response |
|---|---|---|
| **Scale-glitch / decimal-shift** (2026-06-15) | Today's snapshot close is ≥ `_SCALE_GLITCH_RATIO` (5×) discontinuous from the stored prior session | Expire `cached_at` → force a full clean refetch; skip the mismatched write |
| **Phantom-dup tail** (2026-06-02) | Trailing bar has byte-identical close **and** volume to the prior session | Drop at read time (`_drop_phantom_tail`); refuse to append in `patch_latest_closes` |
| **Weekend-dated bar** (2026-05-31) | Snapshot bar dated Sat/Sun | Skip — real sessions are Mon–Fri only |
| **Future-dated bar** (2026-05-27) | Bar dated after today (ET) | Refuse to store; `repair_cache_corruption.py` `$pull`s legacy ones |
| **Zero-price bar** | close/open/volume == 0 (holiday placeholder from Massive) | Drop at the source in `_fetch_massive` |

## Scale-glitch guard — why it exists

The latest scan on **2026-06-12** showed **KLAC** with `day_change_pct = -89.45%`
and `dist_200_pct = -81.83%` — not a real move (KLA does not drop 89% in a day).

Root cause: the stored history sat at **~10× decimal scale** (an earlier bad
full-history fetch — provider decimal glitch or an unreflected split). The last
real bar (6/12 close `254.54`) was correct, but its **prior session (6/11) was
stored at ≈ `2413`** instead of `241.16`. `patch_latest_closes` stacked the
correct snapshot onto the wrong-scale prior bar, so:

```
day_change_pct = 254.54 / 2413 - 1 ≈ -89.45%
MA200 inflated to ≈ $1400  →  dist_200_pct = 254.54 / 1400 - 1 ≈ -81.83%
```

A 20-hour TTL miss later did a full refetch and silently healed the cache, but
the **served `latest.json` stayed frozen** on the corrupt scan until the next run.

**The guard** (`_is_scale_glitch`, applied in `patch_latest_closes` before the
append/overwrite): compares today's snapshot close to the most recent stored bar
from a *prior* session. A ≥ 5× ratio in either direction is impossible for a
real session — even a limit move is < 2×. On a hit it does **not** stack a bar
onto a corrupt series; it expires `cached_at` so the next read does a full clean
refetch (which rewrites the whole array, healing `dist_200`/Stage/RS as well).

Why **5×** and why this is safe: it sits well clear of the most violent real
microcap squeeze, and the response is *force a refetch* — never drop or fabricate
a bar — so even a false positive costs only one extra full fetch that returns the
real series. A genuine unreflected split also lands here, and a clean
`adjusted=true` refetch is exactly the right fix for that too.

## If a served scan is already frozen on corrupt data

The cache self-heals on the next TTL-miss, but the persisted scan
(`~/.cheetah/scans/latest.json`) does not. Refresh it with a fast scan
(recomputes every row from the now-clean cache, ~20–30s):

```bash
docker compose exec api curl -s -X POST 'http://localhost:8000/sepa/scan?fast=true'
```

The next cron scan does the same automatically.
