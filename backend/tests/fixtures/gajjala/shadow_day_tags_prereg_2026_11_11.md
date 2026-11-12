# Shadow day tags — pre-registration (2026-11-11 study, forward from 2026-11-12) — FROZEN 2026-11-12

Frozen 2026-11-12, before the first forward record (session 2026-11-12, written after its close). Its sha256
is in `shadow_day_tags_prereg_2026_11_11.md.sha256` beside this file; any byte changed after the freeze breaks
that pin and voids the read.

## His words (as relayed 2026-11-11)

Ajay said "Do your receommendations" to the line "say yes to 1, 5 and 7 now. The first fixes a wrong number you read,
and the other two are what let this study give a real answer later." Proposal 5 of STUDY/REPORT.md: "No day word on
any surface yet. Instead, record GD3w, GD4, GD6b, GD7, LD3i, LD9 forward as shadow day tags under a prereg; re-read at
30 weeks."

STUDY = /Users/ajay/clinet-test/eod-audits/research/2026-11-11_track_record_patterns/. Frozen sources (sha256):
- day_indicators.py 9bef2f1b8462aa5252664ae87cce862c501828cf11f02de327dae1e86530dcbc
- analyze.py 2bbf60f7fd3a52dd3e4de2dc60c696dd314e8e6a5165acab5d251dc44e20d233
- days.csv 795c43775f4bab2d01e071b56991037817cef9d77f6b476a6fe938ecc99ecaeb

## The eight tag-forms (recorded by backend/scripts/shadow_day_tags*.py; formulas = the study's, line numbers of day_indicators.py)

| form | formula | read time | THEIRS / MINE (IND note) | MISSING when |
|---|---|---|---|---|
| GD3w_pre | gd3_week :266-276 over pd_counts :239-252; ON = failed share > 0.5 | prior 5 sessions | 5 sessions + 50 % MINE | < 5 prior sessions; held + failed == 0; GG5 rows unread |
| GD4_pre | gd4 :296-303 (risk_after fold, GG_LOSS_RISK_CUT) | exits STRICTLY before 09:30 ET (= ET_RTH_OPEN) | halving THEIRS; win reset MINE (lane HIS CALL #18) | GG5 rows unread |
| GD4_by1030 | gd4 | exits strictly before T2_FIRST_HOUR_END_ET 10:30 | halving THEIRS; win reset MINE | GG5 rows unread |
| GD6b_pre | gd6(n_population) :329-342; ON = v < upper median of ≤ 10 prior sessions (sorted(h)[len(h)//2]) | last pass AT OR BEFORE PRE_CUT 09:29 | median + window MINE | no pass; pass > 30 min old; no n_population; < 5 history values |
| GD6b_by1030 | the same | last pass at or before 10:30 | median + window MINE | the same |
| GD7_by1030 | gd7 :360-364; ON = QQQ and IWM both red open → 10:30 | bars closed by 10:30 | both red MINE | QQQ or IWM bars absent (BEST-EFFORT: the minute cache fills lazily) |
| LD3i_pre | ld3(IWM) :393-395; ON = IWM 9 EMA < 21 EMA at the previous session's close | prior session | 9/21 THEIRS | no IWM bar for the previous session |
| LD9_pre | ld9 :466-481; ON = ≥ 4 of the 8 pillars under 9 & 21 with the 9 falling | prior session | 9/21 THEIRS; list + 4 MINE | < 6 pillars with a row |

## Hypothesis

Per tag-form: the trader's own word — an ON day is a WORSE day (gap = ON mean R − OFF mean R < 0). In-sample every GD
read was inverted (STUDY/REPORT.md §3): an opposite-sign forward result is reported as INVERTED, never as positive.

## Cohort

Forward sessions only, from FORWARD_FROM = 2026-11-12; the 22 measured sessions (2026-10-13 → 2026-11-11) never enter
the read. Rows = the row keys present in the LATEST WP-3 dump at the read (track_record_snapshot.latest_rows), each at
its latest stored version with the TTL blocks carried from the store; rows kept in the store but absent from that dump
are reported, not counted. Counted trades as the study counts them (trade_of, analyze.py:48-74; Luk rows with R from
the fill, WP-1's stop_r). The "by 10:30" forms count only trades that rang at or after 10:30 (from_1030). Late records
(a session recorded after a later one, `late: true`) count; their number is reported.

## Outcome and test

Mean R per counted trade, ON days vs OFF days, per (tag-form, page) — split_test (:705-768): trade-pooled mean R, gap =
ON − OFF, day-cluster bootstrap 95 % CI (NBOOT 2000), seed SEED 20261111.

Placebos — BOTH must pass, each NPERM_FWD = 20000 draws (the study's 2,000 raised; MINE), p two-sided exactly as
split_test (abs(g) >= abs(gap)); the direction is checked separately (gap < 0):
1. the study's free shuffle of the day labels;
2. a run-order permutation: in session order the labels form maximal runs; one draw shuffles the ON runs among the ON
   slots and the OFF runs among the OFF slots (alternation and the first label kept), re-lays the labels on the same
   ordered days, recomputes the gap. Its p cannot be below 1 / (distinct run arrangements); the read prints that floor
   and the ON / OFF run counts beside p; a floor above alpha reads TOO FEW RUNS, never a pass.

## Reads and correction

The (tag-form, page) reads, every form on its study pages (the IND rows of day_indicators.py :620-663, and the lib's
READS tuple; luk adds lukx):
GD3w_pre, GD4_pre, GD4_by1030, GD6b_pre, GD6b_by1030, GD7_by1030 on gg5 and gg1 (6 × 2 = 12);
LD3i_pre, LD9_pre on luk, lukx, gg5, gg1 (2 × 4 = 8). Total 20 reads.

Correction: Bonferroni over the 20 reads, alpha = 0.05 / 20 = 0.0025 (the study's own instrument, analyze.py:504).
Settled 2026-11-12 by the main session: the spec's "5 GD forms × 2 + 2 LD forms × 4 = 18" (alpha 0.05 / 18 = 0.0028)
miscounted the GD forms — the eight forms it names hold six GD forms. The circular-shift placebo stays rejected: its
p cannot be below 1 / n ≈ 0.0067 at the 30-week floor, above alpha 0.0025, so a POSITIVE would be impossible by
construction. At NPERM_FWD = 20000 the Monte Carlo standard error of a p near 0.0025 is about 0.0004.
gg1 is NOT independent of gg5 (same names, same days), nor lukx of luk; reported as such — a pass on both is one
finding.

## Read date

ONCE, on ONE date: the first closed session at which EVERY page of the 20 reads (gg5, gg1, luk, lukx) holds
MEASURE_FLOOR_WEEKS (by name; audited_rules.py:88 = luk/constants.py:31) distinct ISO weeks with a recorded forward
session and a filled counted row on that page (the entry_weeks rule, luk/ledger.py:851). No peeking read counts; no page
is read early. The read script is built at read time from this file; nothing reads the store before then.

## POSITIVE

Both sides ≥ MIN_SIDE_DAYS (5) sessions and ≥ MIN_SIDE_TRADES (= analyze.MIN_N, 30) decided trades, the gap in the
hypothesised direction with its 95 % day-cluster CI excluding 0, and BOTH placebo p < 0.05 / 20 = 0.0025. Anything else
= no_signal / too small / too few runs / inverted.

A positive read ships NOTHING: it is a HIS CALL for a PAPER variant — never a gate, a mute, a push or a page word
without Ajay's word.

## Runs

Read-only Mongo through one docker exec per run, no broker import, no provider fetch, no Mongo write. Store:
/Users/ajay/clinet-test/eod-audits/shadow-day-tags/ (append-only JSONL + gzip inputs), run daily by a Claude scheduled
task the main session creates; a refused run (exit 2) is surfaced, never retried silently.
