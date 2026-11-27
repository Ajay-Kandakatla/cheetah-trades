# 🧘 GG-like on 👀 Gajjala's Watch — backend (2026-11-27)

Spec: gglike §3.8, work package `be-serve-watch`. Ajay 2026-11-27, verbatim: "find calmer and better setups.. Continue
to track the runners we might evolve and find patterns in the current runners too but I want to make sure we are
finding similar setups to Gajjala".

**The Watch prints what the 🚩 pass stored. It never works out a block itself.** Display only. Nothing is hidden,
sorted, rung or gated. UNMEASURED.

## What is served

| surface | key | value |
|---|---|---|
| 👀 Watch row | `rows[i].tags.setups[j].gg_like` | `gg_like.served(gg_like.from_stamp(read["gg_like"][setup]))`, or None |
| 📅 roster row | `runners.rows[i].gg_like` | `{setup, label, **gg_like.row_chip(blk, source="read")}`, or no key |

- **`tags.py`**: `TAGS_READ_FIELDS` gains `"gg_like": 1` (still never the tile bars). Each `setups` item gains
  `gg_like` from `tags.gg_like_of(doc, setup)`. That is the stored block when it passes `from_stamp` AND its `setup`
  equals the item's setup. Anything else is None: no stored block, a malformed one, a block of another setup, or an
  engine fault (one log line, and only that item goes None). No `keep` is passed, so `keep` is always False. Nothing is
  hidden on the Watch (HIS CALL #13).
- **`payload.py`**: `_roster_gg_like(roster, siso)` runs right after `runners_section`, only on the full board. It does
  ONE projected find on today's reads of the roster symbols (`ROSTER_GG_LIKE_FIELDS = {symbol, setups, gg_like}`,
  through `tags._find_reads`). For each row it uses `tags.carded_setups(doc)` (the board's own card rule) and takes
  🎾 (`sections.RS_SETUP`) when that is carded, otherwise the first carded setup. A name not carded today, or one with
  no valid stored block, gets no key. Every chip is worked out first and only then written onto the rows, so a fault
  adds no key to any row: the roster is served as it was before, with one log line.
- The `only` (pending) poll does not build the roster, so it reads nothing new.

## Tests

`backend/tests/test_gajjala_watch_gg_like_2026_11_27.py`:
- a carded name serves the stored block for each setup, with `keep` False even on a read that rang;
- NEGATIVE: no stored block gives None. The engine's computing functions are patched to raise, which proves the Watch
  never calls them;
- NEGATIVE: a malformed block gives None (a foreign verdict, a bool `v`, `ok = "yes"`, checks that are not a list, a
  block of another setup, a non-dict). A `gg_like` key that is not a dict also gives None;
- NEGATIVE: a raising `served` makes that one item None and leaves the rest of the tags alone. An uncarded name still
  gets `tags` None;
- neither projection holds a `tile` key;
- roster: a carded runner gets the chip from its 🎾 read first, otherwise from its first carded setup, using one
  projected find;
- NEGATIVE: uncarded, unread and block-less runners get no key. A raising read leaves every row byte-equal. A fault
  partway through the rows adds no key to any row. A roster with no rows reads nothing. The `only` poll never calls
  the roster step.

`backend/tests/test_gajjala_watch_tags_2026_11_18.py`: two pins updated, both predicted by the spec. The setups item
gains `"gg_like": None`, and the projection set gains `"gg_like"`.
