# 🩳 On-entry source check — the pure flags and fixes (2026-11-27)

Ajay 2026-11-27, verbatim: "Can you double check short interest for these two please?" · "Anytime something is in our
Gajjalas we need to initiate a flow checking these values" · "WHLR is too much".

Spec: `sicheck/spec.md` rev 2 §3.4, work package `si-pure`. Code: `backend/short_interest/source_check.py`,
`backend/short_interest/basis_math.py`, `backend/short_interest/read.py`. Tests:
`backend/tests/test_si_entry_flags_2026_11_27.py`. The entry flow that writes the `Entry check` row is a separate
package (`short_interest.entry_check`, its own doc).

**Display only. UNMEASURED.** Nothing here gates, sorts, counts, pushes or enters a lane. Short interest as a signal is
NULL on every prior study; nothing below is a signal.

## The rules, by constant name

| What | Rule | Switch |
|---|---|---|
| A1 `⚠️ sources disagree`, both ways, any tier | `rel_of(float, second) > SCK.min_rel()` AND `SR.tier_of(our %) != SR.tier_of(second %)` (the ladder BEFORE the shares-out cap, both rungs set, `SR._ladder_ok()`) AND `SR._float_suspect(short, second float, shares out) is None`. Only in step 10's NOT-contested branch: step 10 (the EXTREME contest) and `SCK.STATES` are unchanged. The `%` and the tier word are never changed. | `SCK.RUNG_FLAG` (`"on"` / `"off"`, any other word = off — HIS CALL #6), and `EXTREME_CONTEST != "off"`, and `EXTREME_CONTEST_BY == "not_older"` needs the second float dated on or after ours |
| A1 second float fails the house check | named in the Float sources row ("larger than the N shares outstanding on file" / "smaller than the N shares sold short") + "The second float fails the house float check — it is not used to flag the chip." Never flags. | — |
| A1 rung sentence | `SCK.TEXT_RUNG` with `SR._range(..)` of each rung — ranges, never a tier word | — |
| A2 `✂️ split filing M/D` | a 6-K in `sec.fts_split` (status `ok`) with NO splits row dated on or after it (splits read `ok`), filed on or after the verdict's existing `floor`; one flag after the ✂️ split flags. A 6-K also in the issuance list is listed once (under Split filing, "— it also matches issuance words"); its 📄 kind and count are unchanged. Words only. | the read itself (`sec_fts.FTS_SPLIT_WHEN`, package si-io) |
| A3 `Dates` line | a % of float shown, the float's date after the settlement, `BM.same_side(S, float date)`, growth `from <= S < to <= float date`, and no fresh proof filed on or before `S` | — |
| A3 `⚠️ dates apart` | only when `BM.stale_trigger(..)` is true — the existing `FLOAT_STALE_WHEN` cut, all on one split basis; the flag text and the rules sentence end with `BM.DATE_GAP_MODE_WORDS[FLOAT_STALE_WHEN]` | `BM.FLOAT_STALE_WHEN` |
| B1 days-to-cover split sentence | only for a split with `prevS < execution date <= S` (`BM.split_in_window`); the change % keeps its inclusive rule | — |
| B4 a lagged older count | a fall the on-file splits dated on or before the older count explain (`c > paired × f × SR.SUSPECT_MAX_SHARES_OUT_FRACTION`) AND a same-unit SEC cover dated before the split with the older count inside `cov × frac … cov ÷ frac` AND the NEW count inside the split-adjusted cover's band → a Note, no ❔ flag. Explained but not corroborated → the ❔ flag stays and names the split. Not explained → today's text. | — |
| B5 a split filing between the two float dates | always compared; ONE caveat sentence; when a rebase was applied only the A1 chip flag is held back | — |
| Entry line | `si_block(.., entry=)` → one `Entry check` row (last) + one title sentence; `si_map` reads it through `_entry_words` (lazy `entry_check.load` + `words`, `{}` on any failure) | `entry_check.EC_WHEN` (si-io) |

**2026-11-27 refix — `⚠️ dates apart` words.** The flag text and the rules sentence used `FLOAT_STALE_MODE_WORDS` ("more shares added since the float was read than the float itself held"), but the growth they date sits BEFORE the float read — the line contradicted itself. They now use `BM.DATE_GAP_MODE_WORDS`, one entry per `FLOAT_STALE_MODES` key (default: "more shares added between the count and the float read than the float holds"). The cut (`stale_trigger`) and `FLOAT_STALE_MODE_WORDS` (the stale-float sentence) are unchanged.

No new number: every % goes through `SR.pct_of`, every spread through `SCK.rel_of`; the one-division guard is unchanged
(21 divisions).

## The count on the frozen probe rows (the real engines)

`backend/tests/fixtures/si_float_probe_rows_2026_11_26.json`, 569 compared names (shares out derived from the probe's
rounded %), pinned by `test_the_engines_count_on_the_frozen_probe_rows_is_pinned`:

| | names |
|---|---|
| the A1 rule (spread above `min_rel()`, different `tier_of` rungs, second float passes `_float_suspect`) | **52 of 569** |
| …of the 52: floats within 10% / 5% / 2% | 13 / 8 / 2 |
| …of the 52: second float OLDER than ours | 27 |
| …of the 52 at a spread cut of 10% / 25% / 50% (NOT built — HIS CALL #6) | 39 / 29 / 16 |
| A1 chip flag (`rung_flag`, not contested) | 43 |
| the existing EXTREME contest (unchanged) | 11 (9 of them also meet the A1 rule) |
| names carrying `⚠️ sources disagree` after the build | 54 |
| second float differs and fails the house float check (named "not usable", never flags) | 22 |

Re-run (writes nothing):

```
cd backend && .venv/bin/python -B -c "from tests.test_si_entry_flags_2026_11_27 import probe_counts; print(probe_counts())"
```

## The four names, before → after (capture 2026-11-27, `backend/tests/fixtures/si_entry_docs_2026_11_27.json`)

| Name | Chip after | Float sources / notes |
|---|---|---|
| WHLR | unchanged: `… · ⚠️ float updated · ✂️ split due 11/30 · 📄 8-K 3.02 11/20 +4` — no `⚠️ sources disagree` | Massive 39,974 = 1100.5% "— smaller than the 439,892 shares sold short" + the not-usable sentence; the days-to-cover split sentence is gone (its 10/30 split IS the prior settlement day); `Dates:` 1,788,532 (SEC 10-Q cover, 11/3) → 2,220,906 (Yahoo, 11/25); no `dates apart` (432,374 added ≤ the 1,667,144 float) |
| BDMD | `… · 11/13 · ✂️ split filing 11/16 · ⚠️ sources disagree` (without the split read: `… · 11/13 · ⚠️ sources disagree`) | "Yahoo's float puts it at 20% or more of the float, Massive's at 10% to under 20%." + the nothing-rebased caveat (6-K 11/16) |
| POM | no `⚠️ sources disagree` with the split read (rebased ÷18 + the 10/19 6-K between the dates → held back); no `✂️` (its filings sit before the floor) | compared, both %, the rebased caveat. **Without the split read it WOULD flag (R5)** |
| NXAT | `… · ✂️ split filing 11/23 +1 · 📄 6-K 10/5 +1` — no `❔ shares fell 21×` | Note: Yahoo's 68,476,338 (9/10) predates its own adjustment for the 1-for-30 reverse split on 8/3 (on file) — split-adjusted 2,282,545 vs 3,236,567; status ok; the rebased caveat names 11/13 |

## Every surface the tokens reach (one chip engine)

`read.chip_text` puts flag shorts LAST, so `✂️ split filing M/D`, `⚠️ dates apart` and `⚠️ sources disagree` on more
names ride: the 🩳 chip, its hover and panel, the EXTREME note; the 🩳 sub label and ⛔ names text (`high_si.si_flags` →
`tier_chip`); the ⛔ row `si_text`; the 📋 SI column; the stored 🩳📒 `flag_shorts`; the 🩳 cross push body (mode `off`
today). Pinned NOT to move: `high_si.classify` (who is listed), `si_track.filing_facts` `dilution` / `split` /
`dilution_before` / `split_before`, `si_track._ladder_tier`. NXAT loses its `❔ shares fell 21×` token on every one of
those surfaces (B4).

**Corrected 2026-11-27 (refix): the tokens also ride a LIVE push title.** `tier_chip` feeds `si_ssr_names.hsi_tags`
(`si_ssr_names.py:175-178`) → the tag's `text` → `potential.title_lead` → the 🧠 potential push TITLE, sent under
`POTENTIAL_PUSH_KIND` (live, owner-only). So the new words ring on his phone, not only in the cross-push body that is
`off`. BDMD on the fixture: today `🧠 BDMD · 🩳 30.1% short interest · High (float unconfirmed) · …` → with this build
`🧠 BDMD · 🩳 30.1% short interest · High (float unconfirmed) · ✂️ split filing 11/16 · ⚠️ sources disagree · …`.
Only the title words move: the trigger, the push tag / dedupe key (`gg-pot-{setup}-{sym}`), the kind, the link, the
body and the one-time claim are identical (pinned: `test_the_live_potential_push_title_gains_exactly_the_new_tokens_on_bdmd`;
negatives: WHLR's title unchanged, `RUNG_FLAG = "off"` without the split read gives today's title). Names the 🩳 rule
does not list (NXAT, POM, WETO on the fixture) carry no 🩳 words in the title at all. Keeping the three new shorts out
of `tier_chip` (so off the sub label, the ⛔ text and this title) is NOT built — HIS CALL #21.

## UNMEASURED

No ground truth: the two float providers were not checked against filings beyond the names above. The split-word read
matches mentions (a proposal, a vote notice and an executed split read the same). The 43 new chip flags are counted,
not graded.
