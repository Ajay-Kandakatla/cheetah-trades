# 🔢 The float on every 👀 Watch row (2026-11-21)

Ajay 2026-11-21, verbatim: **"can you add the current float value also to the tickers on the watch list."**

Spec: `watchfloat` (scratchpad spec.md, revised per critique). Display only. **UNMEASURED, not a signal.**

## What it is

Every row on 👀 Gajjala's Watch (his names, 🤖 auto names, 🎯 A+ names, pending rows) now serves `row["float"]`:
the name's float as a plain fact chip, with a hover (`title`) that says where the number came from and when it was read.
Before this change only names carded on today's 🚩 board showed a float (through the 🏷️ tags block).

Served shape (None when no float read is on file — never invented):

```
{shares: number|null, src: "float"|"shares_out_yf"|"shares_out_massive"|null, text, as_of,
 suspect: bool, suspect_text: str|null, title: str|null, read_from: "pass"|"cache"|"memo"}
```

## Reads, in order (`backend/chart_maps/gajjala_watch/float_read.py`)

1. **pass**: a name carded on today's 🚩 board serves the 🏷️ tags chip (`tags.float`, the pass's own read). No cache
   read, except for a suspect chip, which takes ONE cache read to get the numbered words the 🚩 card prints.
2. **cache**: the 7-day `shares_cache` row through the ONE engine, `sepa.volume_movers.shares_status(sym, fetch off,
   coll=<the store's handle>)` + `context._yf_read`.
3. **memo**: ONE projected `_id $in` find on the 🚩 pass's `gajjala_daily` memo for the board session, misses only:
   the Yahoo refine `float`, else Massive's `float_massive` shares out (dated when Massive was asked, never serve
   time). A memo fault keeps steps 1-2 and logs ONE warning.
4. Nothing on file → the row serves `float: None`.

## Honesty line

**A float is not realtime: Yahoo's figure, kept up to 7 days; Massive shares out asked once a session.** Every
numeric chip's hover says so, e.g.:

- `Float 1.8M — not realtime: Yahoo's float figure, kept up to 7 days, read 2026-11-20 04:06 ET`
- `… Massive's shares outstanding, asked once a session, read 09:01 ET`
- a Yahoo read whose own `as_of` is 7 days old or more: `… Yahoo's float figure, older than 7 days, …` (the exact
  complement of `shares_status`'s fresh rule; a Massive read is never stale-worded).

"7" is `timedelta(seconds=VM._SHARES_TTL_SEC).days`, never typed.

## No network, no new client

- Never a network call: no Yahoo, no Massive, no `floats_for`, no fetch at serve time (tests trap every path).
- Never a new Mongo client: `shares_status` gained `coll=None` (2026-11-21). `None` is today's `_shares_coll()` path,
  byte-for-byte; `float_read` passes `st.coll(VM.SHARES_COLL)`, the process-wide `portfolio.store._get_db()` handle,
  and never passes None (no handle → the section serves {} + one warning). `VM.SHARES_COLL = "shares_cache"`.
- Never a clock (the payload's `now` is handed in), never a write.
- `payload.py` imports it lazily (`FLOAT_MODULE`); a raising / missing module → every row `float: None`, the board
  answers `ok`.

## Two floats on one tile

The 🩳 chip's "% of float" divides by the float **snapshotted at SI-warm time** (`short_interest_latest`). It can
differ from this chip, which is the current `shares_cache` read. The hover's read time tells them apart.

## What it does NOT change

Row order, `symbols`, `full`, every other row key, the 🏷️ tags block (its pins stay green), `auto.py`, `loop.py`,
`cross_alerts.py`, `build.py`, `tags.py`, `broker.py`, `context.py`, `tab.py`, any gate, any push, any rule. Every other
`shares_status` caller is unchanged (the kwarg defaults to None).

## Measured (read-only probe, throwaway container, Sat 2026-11-21, board session 2026-11-20)

Script: `backend/scripts/watch_float_probe.py --build` (worktree mounted `:ro`, `PYTHONPATH=/repo/backend`; never
the live api).

| quantity | value |
|---|---|
| Watch names | 29 (13 his + 16 🤖) |
| served | **23 / 29** — pass 17, cache 6, memo 0 |
| blank | 6: BKR, FANG, MGY, NVT, CLS, CRMN |
| `FR.section` vs the re-implementation (same engine calls) | **EQUAL** on all 29 |
| `FR.section` time | 1.8 ms (cache reads 1.2 ms, daily find 0.1 ms) |
| 3× `FR.section`: new threads / ResourceWarnings | **0 / 0** |
| contrast: 36× default-path `shares_status` (no handle) | 107 new threads / 36 unclosed-client warnings |
| `PL.build` median (3×) with floats / without | 28.4 ms / 24.0 ms → **+4.4 ms** |

### Cache age table (days; left = 7 − age)

Status is blank for names served by the pass (not looked up).

| SYM | age | left | status |
|---|---|---|---|
| FANG | 92.2 | −85.2 | stale |
| CLS | 81.2 | −74.2 | stale |
| MGY | 81.2 | −74.2 | stale |
| BKR | 71.7 | −64.7 | stale |
| NVT | 61.3 | −54.3 | stale |
| CRMN | 8.0 | −1.0 | stale |
| DBGI | 5.0 | 2.0 | (pass) |
| GMM | 4.8 | 2.2 | cached |
| GDHG | 4.7 | 2.3 | cached |
| BRNX | 2.8 | 4.2 | (pass) |
| CUE | 2.7 | 4.3 | (pass) |
| NCPL | 2.7 | 4.3 | cached |
| STIM | 2.7 | 4.3 | cached |
| SKYA | 2.7 | 4.3 | (pass) |
| LABT | 2.6 | 4.4 | (pass) |
| RMIX | 2.5 | 4.5 | cached |
| INHD | 2.5 | 4.5 | (pass) |
| VWAV | 1.9 | 5.1 | (pass) |
| LASE | 1.8 | 5.2 | cached |
| MRKR | 1.7 | 5.3 | (pass) |
| BAER | 1.6 | 5.4 | (pass) |
| MEDS | 1.0 | 6.0 | (pass) |
| SVRE | 1.0 | 6.0 | (pass) |
| NXAT | 0.9 | 6.1 | (pass) |
| SEGG | 0.8 | 6.2 | (pass) |
| SRTM | 0.8 | 6.2 | (pass) |
| AKAN | 0.7 | 6.3 | (pass) |
| MSS | 0.6 | 6.4 | (pass) |
| MRM | 0.4 | 6.6 | (pass) |

**The blank set grows by itself.** Nothing refreshes a name outside the 🚩 scan (`floats_for` refines scan names
only), so his large, slow names go blank one by one as their cache row passes 7 days. DBGI / GMM / GDHG are within
~2 days of the cliff today.

## HIS CALLs (nothing below is built)

1. **Names whose float is older than 7 days print nothing, and the set grows.** Default built: blank. Options:
   (b) **offer first**: add his Watch names to the 20:15 nightly float step (`floats_for`: paced Yahoo, stops at the
   first 429) — no serve-time network; (a) print the expired figure labelled "(stale, read DATE)" — a house-engine
   semantic change for every caller; (c) warm them in the Watch minute loop (new Yahoo calls during the day);
   (d) fall back to the SI doc's stored float, dated — covers 5 of 6 today (BKR 09-10, FANG 08-21, MGY 09-01,
   NVT 09-21, CLS 09-01; CRMN none), 2-3 months old.
2. **"float unknown"** when the 🚩 pass asked Massive and got nothing. Default: print it. Alternative: nothing.
3. **Hover wording** as above. Optional extra line "the 🩳 % of float uses the float as of <SI date>". Default: not
   added.
4. **Phone has no hover**: the read date is not visible on the phone. Default: hover only. Alternative:
   "Float 1.8M · 11-20" on the chip.
5. **Suspect float** (float on file > shares out) prints a second warn chip with the numbered words the 🚩 card
   prints when the cache row shows them, else the generic words. Default: shown. Alternative: hover only.
6. **Implausibly small floats print as fact**: VWAV "Float 1.9K" (0.06 % of 3.2M shares out), GMM "Float 559.9K"
   (1.0 %). The house suspect check fires only when float > shares out; a lower-bound rule and its threshold would be
   a NEW rule — his number if he wants one. Same today on the 🚩 card.

## Tests

- `backend/tests/test_gajjala_watch_float_2026_11_21.py` — cache / pass / memo, stale boundary, no network, zero new
  clients, read counts, faults, suspect, NaN, row key set, static source checks.
- `backend/tests/test_volume_movers_coll_2026_11_21.py` — the `coll` kwarg; the default path unchanged.
- `backend/tests/test_gajjala_watch_aplus_2026_11_17.py` — row-key pin moved (+ `"float"`).
