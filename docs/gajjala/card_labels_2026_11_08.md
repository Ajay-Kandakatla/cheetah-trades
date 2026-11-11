# 🎾 Short-interest label · 🧪 entry-zone card line — Gajjala cards (2026-11-08)

Spec: gg-zones, work package `fe-card`. Frontend only — no served byte changes for the label. UNMEASURED; nothing here
gates, filters, pushes or trades.

## The ask, verbatim (Ajay, 2026-11-07)
"Also for the reversal squeeze I need short interest to be show on all the 3 of his tab as a label."

## Why he could not see it (read-only probe, 2026-11-08)
Not a cache miss. The 30 most recent 🎾 symbols ALL had a short-interest doc (FINRA settlement 2026-10-15, fetched
10-27; `si_map` 14/14). The number was already on every card — as ONE muted grey `cm-badge` among six in the chip row
above the chart. The card body he reads (plan, criteria, chips) carried no SI.

## What changed
- New own module `frontend/src/components/GgShortInterestLabel.tsx` (the GgTraderChip precedent): the SAME hook
  `useShortInterest` and the SAME lib `siChip` as the house 🩳 chip. Words = the SERVED chip text
  (`short_interest/read.py chip_text`, e.g. "🩳 SI 21.9% float · 1.0d · 10/15") and the SERVED hover sentence
  (`title_text`), verbatim — the FE types none. A stale read carries its own served "· stale" word plus the
  `gg-si-stale` class. No record / not loaded / failed request → NOTHING, never a zero.
- Mount: `GajjalaBoard.tsx` `CardExtras`, right after the `gg-plan` line, before the 🔴 live line, gated on
  `read.setup === 'reversal_squeeze'`. One component draws all three tabs (🚩 Gajjala's, 🚩 1-min, 🧪 Audited), so the
  label is on all three; a 🧠 tile whose primary read is the squeeze gets it too.
- The 🎾-only chip skip [C7]: on a card whose read is `reversal_squeeze` the muted `ShortInterestChip` in the head row
  (`cm-tile-chips`) is skipped. Every other setup's head row is byte-identical (the four-house-chips pin on the bull_flag
  card PFAI is unchanged). `GG_OUTER_CHIPS` is unchanged, so PatternChart still skips its own copy.
  Rule #5: the same string twice on a 430 px card is clutter — the SI is MOVED to the label, not duplicated. Keeping
  both is HIS CALL #9.
- Cost: unchanged — the label and the chips share the module cache, so a board is still ONE bulk
  `GET /short-interest/map` for the whole grid (pinned).
- Short interest is a count of open short positions with its settlement date — a data label, not a signal, not a
  forecast. Names with no float/shares on file print the served share-count fallback ("🩳 SI 185.6K sh · …") —
  hiding them is HIS CALL #10.

## 🧪 Entry-zone card line [C1]
- Under the chart, for each served band with `kind === 'gg_entry'` and a non-empty string `note`, one line
  `cm-note gg-line gg-zone` (`data-testid="gg-zone-<SYM>"`) prints the band's SERVED `note` verbatim
  (e.g. "imminent — trigger armed, volume dry, no more than 3 red closes in a row · UNMEASURED").
- The band's short `label` ("entry zone") is NOT repeated in the line — the chart's `<title>` and crosshair readout
  carry it. The note is read through a local narrowing (`typeof === 'string'`), so a band without a note, a blank note,
  a non-string note or a band of any other kind prints nothing.
- 🚩 Gajjala's (GG5) serves `bands: []` → no line there. The bands are served by the 1-min and Audited tabs only
  (backend `chart_maps/gajjala/entry_zone.py`, doc `entry_zones_2026_11_08.md`).
- The line restates the ✓ K3 / K5a / K6 / K7 rows; it is kept because a phone has no hover and the gold band alone
  carries no words on touch — dropping it (band + readout only) is HIS CALL #11.

## CSS (`frontend/src/styles/gajjala.css`)
`.gg-si-label { font-weight: 600; }` and `.gg-zone { border-left: 2px solid var(--gold, #c9a227); padding-left: .4rem; }`.
Both lines ride `.gg-line`, which already wraps anywhere at 430 px; the two phone selector lists the phone test pins
are untouched.

## Tests
- `frontend/src/components/GgShortInterestLabel.test.tsx` — served text + title, stale class, share-count fallback,
  one bulk GET for three labels; NEGATIVES: no_record, empty chip, absent symbol (never a 0), failed fetch, loading.
- `frontend/src/components/GajjalaBoard.cardLabels.test.tsx` — does NOT mock `./ShortInterestChip`, stubs `fetch`:
  label under the plan; SI text exactly ONCE per 🎾 card and no 🩳 in its head row; the bull_flag card on the same
  board keeps its chip and gets no label; one SI GET per grid; stale; 1-min and Audited boards; 🧠 sub; zone line prints
  `note` not `label`, under the chart. NEGATIVES: no_record, absent, failed fetch, other setup, no read, `bands: []`,
  band without / blank / non-string note, other band kind, absent `bands`.

## NOT built
No served key, no new chip, no FE word, no sort, no filter, no push. The ✨ entry is the main session's.

## 2026-11-11 — a triggered card whose alert never rang (formulas audit D10, K11 words)
Ajay 2026-11-11 08:18 ET, verbatim: "Can you fix the defects please" (audit
`eod-audits/research/2026-11-10_formulas_audit.md` §3 D10). Words only — no gate, no threshold, no new served key.

- **The defect.** K11 is judged on each pass's own session volume. Demo (`L3/k8_edges.py` §8): the pass that reads the
  🎾 break bar sees 900,000 shares → partial, no alert; the next pass sees 1,050,000 → the read is re-judged A+ and served
  as `triggered`. The card said "triggered 1 bar ago — A+ on the 10:20 bar" and the 🌙 recap "A+ (triggered)" for an
  alert that never rang.
- **The served words now** (module constants in `chart_maps/gajjala/tab.py`, `NO_RING_TEXT` / `NO_RING_RECAP`; the FE
  types none):
  - triggered pill: `triggered 1 bar ago — broke on the 10:20 bar, no alert rang · UNMEASURED`;
  - 🌙 recap row: `broke (no alert rang)` for a triggered read, `broke, then stopped (no alert rang)` for a stopped one;
  - 🧠 Track row: the "now …" word and every triggered timeline step read `broke (no alert rang)`; a 🧠 tile carrying a
    triggered read gets the pill above.
- **When.** Only when the 🏁's own read of the rang alerts (`store.alert_rows` classified by `ledger.alert_of`,
  `tab._entry_times`, ONE read per build) came back fine AND holds no live A+ entry for that (session, symbol, setup).
  An alert that rang → today's words ("A+ on the 10:20 bar", "A+ (triggered)", "A+, then stopped"). A read fault / no
  ledger → unknown → today's words (never "no alert rang" on a guess).
- **Where.** Live-push pages only: 🚩 Gajjala's (GG5) and the 1-minute page (GG1). 🧪 Audited (shadow) keeps today's
  words. `aplus`, `stopped` pills, `potential.STATE_WORDS` and its pin are untouched.
- **Who.** The SAME words for every reader — the 🏁 already shows non-owners which alerts rang, and owner-only words
  would break the nothing-hidden rule (HIS CALL #4: confirm, or non-owners keep today's words).
- **Not said.** "Volume came later" is not printed — no-ring also comes from the window, a missed pass, the no-risk guard
  or the dedupe, and stored data cannot tell them apart. The chart's "A+" marker on that bar is unchanged (HIS CALL #5).
  Luk's 🥇 triggered card ("A+ on the …", `chart_maps/luk/tab.py`) is NOT fixed here (HIS CALL #11).
- **Tests.** `backend/tests/test_gajjala_defects_k11_words_2026_11_11.py` — the §8 frames end to end (pill, recap,
  🧠 track, 1-minute page), owner = non-owner, ONE `alert_rows` read per build (0 on 🧪 setup subs, ☀️, 📖); NEGATIVES:
  key present, entries unknown (None / raises / no ledger), another key's alert, 🧪 shadow, bare `_track_row`, every
  other state. Pin moved by design: `test_gajjala_potential_tab.py::test_one_alert_rows_read_per_potential_build_and_none_on_another_sub`
  (setup subs and 🌙 now read the same ONE alert_rows on a live page).
