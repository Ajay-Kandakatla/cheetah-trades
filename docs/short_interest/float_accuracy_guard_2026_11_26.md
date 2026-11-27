# 🩳 Float accuracy guard — one division, a second dated float beside the one we divide by (2026-11-26)

## The ask, verbatim

Ajay 2026-11-26 ~21:20 ET: "Also the Float share count issue and SI discrepancy happened too many times need to do something about it"

Rule #9 class (≥ 3 of a kind → a rule). Spec: scratchpad `floatguard/spec.md` rev 2. This page covers the backend verdict
package (be-verdict): `short_interest/read.py`, `short_interest/basis_math.py`, the new pure `short_interest/source_check.py`.
The second float's I/O (Massive `/stocks/vX/float`, the `mfloat` sub-doc) is in `massive_float_source_2026_11_26.md`; the
frontend in `float_accuracy_guard_frontend_2026_11_26.md`. The nightly audit (spec §3.6, package be-audit) is built:
`short_interest/source_audit.py`, documented in `source_audit_2026_11_26.md` (corrected 2026-11-27; see "Re-run" below).

## The incidents

| # | Name, day | What went wrong | Where it stands |
|---|---|---|---|
| 1 | AKAN 11-18 | "EXTREME 36.4% float" on a stale Yahoo float 531,210 (10-22) vs 2.39M shares; true ~8.1% of shares | fixed 11-18 (the 10%-of-shares confirmation) |
| 2 | SMTK 11-24 | 79% "EXTREME" on Yahoo float 546,875 after a 50:1 split + ~8.6× dilution + 1-for-5 | fixed 11-24 (float stale / across a split) |
| 3 | GMEX 11-24 | an older float used while a newer dated Yahoo float existed (62.9% vs 3.5%) | fixed 1ae5f1b0 |
| 4 | AKAN 11-24/26 | no 📄 chip: a same-day filing dropped by strict `filed > anchor` | fixed 5f22536f |
| 5 | WHLR 11-26 | "📄 +18": each 8-K re-filed as three 424B3 copies | fixed 5f22536f |
| 6 | POM 11-26 | a post-issuance float called stale; the 11-04 6-K invisible | fixed 047acbb4 |
| 7 | NCPL 11-26 | Yahoo 4.39M vs Finviz 2.09M float (10.6% vs 22.2%) | THIS build: a second DATED float is shown beside Yahoo's (Finviz is not read — its terms could not be fetched) |

## The resolver order (NOT changed)

The record's Yahoo float → a newer dated Yahoo float replaces it (`basis_math.newer_float`) → refused when stale or across a
split → % of shares outstanding on the newest dated count. The second float is NEVER a denominator.

## The one division — `read.pct_of`

`pct_of(count, shares, digits=2)` = `count / shares × 100`, rounded (None = unrounded); None when `shares` is None / zero /
negative or `count` is None. It sits ABOVE `EXTREME_WORD` in read.py (the slice from `EXTREME_WORD` to `def si_block`
holds no numeric literal and no `round(`). The seven read.py / basis_math.py sites keep their own guards and call it:

| Site | Before | After |
|---|---|---|
| `read.si_block` (2) | `round(si / fl * 100.0, 2)`, `round(si / so * 100.0, 2)` | `pct_of(si, fl)`, `pct_of(si, so)` |
| `basis_math.stale_trigger` (2, mode `tier_moves`) | `round(s / base * 100, 2)`, `round(s / den * 100, 2)` | `SR.pct_of(s, base)`, `SR.pct_of(s, den)` |
| `basis_math.verdict` (3) | `pct_so`, `float_update.pct`, `float_pct_on_file` | `SR.pct_of(si, …)` |

Bit-identical: every one of the 16 captured blocks served by main 047acbb4 is reproduced key for key with no `mfloat`; a
sweep pins `pct_of == round(c / s * 100.0, 2)` and the old `tier_moves` branch. The three `client.py` sites and
`high_si.card_pct` are other packages (`one_division_2026_11_26.md`).

## The comparison — `source_check.compare(block, basis_doc)`

Only when the basis doc holds a dict `mfloat`. First match:

| State | When | Contested? |
|---|---|---|
| `no_float` | the block shows no % of float | never — the second float is listed, nothing compared |
| `unread` | `mfloat` not ok / none, or a junk leaf (bool / NaN / string / ≤ 0 count, undated) | never |
| `none` | Massive's complete answer listed no row (JZ) | never — "one source only" |
| `units` | listing type not in `SEC_COVER_SAME_UNIT_TYPES` (CS / OS) | never |
| `no_splits` | the splits read is not held | never |
| `window` | `splits.since` is not a date, or EITHER float is dated before it | never |
| `split_day` | a split executed ON either float's date (`BM._rb` is None) | never |
| `compared` | both floats on one split basis | — |
| `contested` | the block reads EXTREME, the two differ by more than `SAME_VALUE_REL` (= `CARRY_REL_TOL`, or `CONTEST_MIN_REL` when set), and the second float's tier — THE tier engine `SR.si_tier` on the same block with the second % — ranks below EXTREME (`rank(None) = -1`) | yes |

Why `window`: the splits sub-doc only lists splits on or after `splits.since`, and Massive does not re-date a float on a
split (SMX float 08-13 with a split 11-09; DKI 10-20 with a 1-for-50 on 10-22). A second float older than the window
cannot be rebased, so it is not compared until the window reaches its date (share_basis widens it). DKI as captured:
un-rebased it reads 2,317× apart — a blind compare would warn on an artefact; it is `window`. With the real wider splits
read (`splits_widened` in the fixture) DKI is contested at 46× (5.1% vs 238.2%).

## What the chip and hover show

- Every compared name — ONE neutral sentence in the hover (`Float sources — …`) and ONE `Float sources` panel row, right
  after `Share counts`: both counts, both dates, both %, the spread. NCPL:
  `float: Yahoo 4,387,760 (read 11/18) = 10.6% · Massive 4,246,497 (as of 8/14) = 10.9% · 3% apart. The % shown uses Yahoo's.`
- A rebased second float: `Massive 587,276 (as of 10/20; 29,363,802 as published, split-adjusted)`; one above the share
  count on file: `— larger than the 752,439 shares outstanding on file` (GMEX).
- A 📄 filing on file dated after a count's date: `Massive's count is dated before the 📄 F-1/A 11/20 on file.` (AKAN), or
  `Both counts are dated before …`. A same-day filing never counts.
- Contested, built default `flag`: the chip ends `· ⚠️ sources disagree` (flag appended LAST, so the EXTREME note's short
  carries it too); the hover says `Massive's float puts it under 20%, where EXTREME starts — the word is not changed.`; the
  Float-check sentence gains ` A second dated float disagrees — see Float sources.` so it never says "confirmed" alone.
- Never the words "agree", "the same count", "inside the cut", "confirmed by". Every % through `SR._pct_tier`.

### What it does NOT change (built default)

The word EXTREME, the tier, the 🩳 list, every sort (`high_si.ssr_new_rank` reads the tier — unchanged), the 🏁 series, any
gate, push or lane. A doc with no `mfloat` is served byte-identical to before (`SOURCE_KEYS` absent; `BASIS_KEYS` unchanged).

## The modes — HIS CALL

| Constant | Built | Other values |
|---|---|---|
| `EXTREME_CONTEST` (#1) | `flag` — word stays, chip warns | `off` (hover only) · `hold` (word stops at High: `High — 43.2% of the float, held below EXTREME: another dated float on file puts it under 20%.`; no EXTREME note) · `supported` (the second float's own word, High at most: GMEX → Low, DKI → Moderate). Unknown word = `off`. |
| `EXTREME_CONTEST_BY` (#3) | `any_dated` | `not_older` — only a second float dated on or after ours (GMEX drops out, CHWY stays). Unknown = `any_dated`. |
| `CONTEST_MIN_REL` (#4) | `None` = any difference above rounding | a number, e.g. 0.5 (GENI 2% apart → compared; CHWY stays). |

## The counts — one read, 11-26, NO GROUND TRUTH

Over the 569 comparable names of the 693 that hold both floats (`tests/fixtures/si_float_probe_rows_2026_11_26.json`;
124 are `window`, 22 of them EXTREME). Pinned by `test_cut_table_on_the_probe_rows_is_pinned` through `SCK.cut_table`.

| A flip counts when the two floats are | names that differ by more | EXTREME names the second float puts under the cut |
|---|---|---|
| any difference above rounding | 564 of 569 | 11: AVBP AVTX CHWY GENI GMEX LRMR NKTR PRTA TSHA VERA VOR |
| more than 10% apart | 148 | 8: AVTX CHWY GMEX NKTR PRTA TSHA VERA VOR |
| more than 25% apart | 58 | 4: AVTX CHWY GMEX TSHA |
| more than 50% apart | 24 | 2: CHWY GMEX |

| Name | Float we divide by | Massive free float | State on the captured doc |
|---|---|---|---|
| NCPL | 4,387,760 (read 11-18) 10.6% High | 4,246,497 (8-14) 10.9% High | compared |
| AKAN | 709,911 (11-20) 22.6% High · unconfirmed | 540,841 (8-13) 29.6% | compared |
| SMX | 282,748 (11-24) 68.6% EXTREME | 893,747 (8-13) = 319,195 rebased, 60.7% | compared |
| INLF | 876,064 (11-19) 111.8% EXTREME | 190,023 (8-21) 515.5% | compared |
| CHWY | 53,363,881 (9-11) 46.8% EXTREME | 223,848,331 (9-22) 11.2% High | contested |
| GMEX | 361,428 (11-19) 43.2% EXTREME | 940,677,978 (10-31) <0.1% Low — larger than the 752,439 shares on file | contested |
| DKI | 12,671 (11-24) 238.2% EXTREME | 29,363,802 (10-20) | `window` (splits from 10-30); contested at 46× once widened |
| WHLR, BETR | 26.4% / 40.3% EXTREME | 239,842 (10-08) / 8,302,619 (10-16) | `window` |
| POM, SMTK | no % of float shown | 10,373,225 / 739,250 | no_float |
| JZ | 31.3% EXTREME (ADRC) | no row | none |
| CLRO | 35.8% EXTREME | 886,631 (8-25), under 1% apart | no basis doc at capture; CLRO-shape test: compared, untouched |

NONE of the contested names was checked against a filing. 9 of the 11 read 17.6–19.9% on the second float. GMEX's second
float divided by this year's four reverse splits (8·7·9·9 = 4,536) is ~207K — the order of Yahoo's 361K — so it looks
pre-split although dated 10-31. DKI's own Yahoo pair looks broken (float 12,671, shares 51,333, ADV 5.2M). Which side is
wrong is NOT known for either. A count of two providers differing — not a signal, not a forecast, UNMEASURED.

## NOT built here (spec §7)

DKI and GMEX are NOT fixed (both still print their % and stay on the 🩳 list, now with the warning). High names the second
float calls Low get no chip words (#5, #12). The K8 float gate / 🩳 float cap read Yahoo alone (#6). StockAnalysis / Finviz /
Nasdaq are not read (#8). The SEPA card chip's count (#9), the 📈 Bonde DTC leg (#10), share-count differences on the chip
(#11), the 👀 Watch / 🚩 card Float chips (#13).

## Tests and the mutation check

`backend/tests/test_si_source_check_2026_11_26.py` (180; the last four pin this page: no page or module it names is missing, and its re-run block prints the counts table). Fifteen mutants of `source_check.py` (each §3.4 condition flipped:
steps 1–7, the spread test, the tier / rank / not_older legs of the contest, `rank(None)`, the `hold` target) were run
with caches purged, the original kept in a scratch backup — all 15 RED (runner:
scratchpad `floatguard/mutants/run_mutants.py`; the file is restored and byte-checked after).

## Re-run

```bash
cd backend && rm -rf ~/Library/Caches/com.apple.python; /usr/bin/find . -name __pycache__ -type d -prune -exec rm -rf {} + ; .venv/bin/python -m pytest tests/test_si_source_check_2026_11_26.py -q -p no:cacheprovider
```

The counts table above re-runs from the frozen rows (prints n / compared / window, then cut, differ, contested, names —
the same numbers `test_cut_table_on_the_probe_rows_is_pinned` pins):

```bash
cd backend && .venv/bin/python -B -c "import json; from short_interest import source_check as SCK; R=json.load(open('tests/fixtures/si_float_probe_rows_2026_11_26.json'))['rows']; t=SCK.cut_table([{'symbol':r['s'],'state':'window' if r['md']<r['since'] else 'compared','tier':r['t'],'other':{'tier':r['tm']},'float_rel':r['rel']} for r in R]); print(t['n'],t['compared'],t['window']); [print(c['cut'],c['differ'],c['contested'],' '.join(c['names'])) for c in t['cuts']]"
```

The 693 rows above are one read on 11-26 (the planner's probe, not shipped) and stay frozen. A fresh read over every
checked name re-runs with the be-audit dry run (spec §3.6 / §5.4; writes nothing; doc `source_audit_2026_11_26.md`):

```bash
cd backend && .venv/bin/python -m short_interest.source_audit --dry --all --cuts
```

Correction 2026-11-27: this paragraph and the header first said the nightly was not built and the re-read was owed by
be-audit. It landed; both now point at `source_audit_2026_11_26.md` and the command above.
