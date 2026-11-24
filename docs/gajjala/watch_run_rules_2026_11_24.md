# ▶ Run Gajjala's rules on ONE Watch name — backend (2026-11-24)

Spec `ggrun` rev 2, work package `be-run`. The frontend half (button, slide-in panel) has its own doc:
`docs/gajjala/watch_run_rules_frontend_2026_11_24.md`.

## His words

Ajay, 2026-11-24, verbatim:

> On the Watch list I need a run button to run against Gajjalas rules of a stock to see for patterns of 5 patterns he
> has especially reversal squeeze.. so can check for patterns mid day when I can add a small slide in in the chart window
> for giving verbatim of passed rules and failed rules of that stock like you do in other tabs..

## What one tap does

`POST /chart-maps/gajjala-watch/run/{symbol}` (`constants.API_RUN_PATH`). Owner only (`require_primary_admin`: 404 for
another email, the auth layer's 401 with no email, both before the handler). The body is built inside ONE
`asyncio.to_thread` (`api._run_body`), and the engine is imported lazily (`C.RUN_MODULE`). Every served state is HTTP 200.

`chart_maps/gajjala_watch/run_rules.run(symbol, now)`, in this order (the first step that answers returns):

1. A malformed symbol → `bad_symbol` (`payload.store_text("bad_symbol", None)`). Nothing is read.
2. `C.RUN_RULES_ON` False → `off`. Nothing is read.
3. The Watch list: his names (`colls.owner_symbols(strict=True)`) + today's 🤖 names (`auto.current_symbols`; an auto
   fault → his names only). An unreadable list → `error`.
4. Not on the Watch → `not_listed`. No bar fetch, no read doc.
5. `on_demand._closed(now)` (a closed day, or outside `GC.PASS_OPEN_ET`–`GC.PASS_CLOSE_ET`) → `closed`. No fetch.
6. The memo (no lock taken): the same symbol and session, younger than `C.RUN_REUSE_SEC` (= `GC.ON_DEMAND_REUSE_SEC`,
   his K4 "60 s"), AND no newer 5-minute bar can have closed since (`closable_t5(now)`, the `closed_only` rule) → the
   same answer + `reused_text`. Only `ok` / `no_prints` / `no_bars` are kept; `failed` / `busy` never.
7. A per-symbol lock, `acquire(timeout=C.RUN_BUDGET_SEC)` (= `GC.ON_DEMAND_BUDGET_SEC`); not got → `busy`. Inside: the
   memo again (the run that held the lock just wrote it), then ONE read. Different names run at the same time; the same
   name twice = one fetch.
8. Anything unexpected → `error` with the exception's type name. The api's own fallback (import fault) is `error` with
   `C.RUN_TITLE_TEXT`, `C.RUN_ERROR_TEXT`, `C.RUN_NOTE_TEXT` — title and note are always strings.

## The five reads = the pass's engine

The read is the 🚩 pass's own per-symbol detect path (`chart_maps/gajjala/run.py:511-519`):

- `bars.frames_for([sym], session, now, load_day=run_rules.load_day, budget_sec=C.RUN_BUDGET_SEC, per_name=…)` —
  GG5 frames (closed 5m + 15m, the `BAR_SETTLE_SEC` rule, `bars.py:254-310`); the tile status rule `build.status_of`.
- `detectors.read_all(frames.detector_frames(), {"symbol", "float_read", K11_CTX_KEY})` (`detectors.py:1150-1175`).
- The words: `tab._setup_label`, `tab.state_label(read, tab._rang(entries…))`, `tab.plan_text`, `tab.variant_label`,
  `tab.grade_label`, `tab.vol_dried_text` (`tab.py:847-902, 1446-1479, 2158`); `tab._entry_times` (the no-ring
  tri-state). The rule rows are the detector's own, in its order, projected to `key, label, ok, value, need`.

Order: 🎾 Reversal Squeeze first (`sections.RS_SETUP`), then Bull Flag, Kiss & Fly, Horizontal Fade, VCP
(`GC.SETUPS`). Always five blocks on `ok`.

## The answer keys

`C.RUN_ANSWER_KEYS` = `state, symbol, title, text, as_of, reused_text, scanner, float_text, volume_text, note, setups`.
Each setup block = `run_rules.SETUP_KEYS` = `setup, label, state, state_label, gate_text, plan_text, variant_label,
grade_label, vol_dried_text, frame, as_of_bar_t, criteria, tally_text`. States: `run_rules.STATES` = ok, closed,
not_listed, bad_symbol, no_prints, no_bars, failed, busy, off, error. Every non-`ok` state: `text` = its one sentence,
`setups` = `[]`, the blocks null.

## What it never does

No push, no alert row, no 🧠 potential, no 🤖 seat, no tile doc, no read doc, no `intraday_cache` row (the loader is
`load_intraday`'s cache rule MINUS `_mongo_put_day`), no `shares_cache` row (the float lookup is always `fetch=False`;
Yahoo is never asked), no `gajjala_daily` memo (`floats_for(store=None)`). The tests pin every FakeColl at 0 writes, the
cache writer, the alert / push / potential / auto writers and Yahoo never reached, and an AST guard on `run_rules.py`
(imports and names; docstrings are not read).

Honest footnote: the 1-minute cache reader (`daytrading.data._get_mongo_coll`) runs `create_index` once per process —
an idempotent ensure of the EXISTING index, not a document write.

## Cost

PARTIAL timing (planner probe 2026-11-24 03:00 ET, n = 8, 4 Watch names × 2, completed session, `float_read: None`):

| what | min | median | max |
|---|---|---|---|
| frames + detectors + words (NOT the whole run) | 0.81 s | 0.86 s | 0.99 s |
| Massive minute fetch (one day) | 0.79 s | 0.84 s | 0.95 s |

This is a floor, not a tap. The whole run in the pass window — an on-scanner name AND an off-scanner name (the Massive
shares-out lookup, 10 s timeout) — is re-run with `backend/scripts/gajjala_watch_run_rules_probe.py` after the deploy.

Measured live: _owed — the main session fills this line after the deploy (both names, n, min / median / max)._

Scripts (both read-only):

```bash
docker exec -i -w /app cheetah-market-app-api-1 python - --symbol AKAN --n 5 < backend/scripts/gajjala_watch_run_rules_probe.py
docker exec -i -w /app cheetah-market-app-api-1 python - --date 2026-11-23 < backend/scripts/gajjala_watch_run_rules_equality_probe.py
```

The equality probe compares the run's engine with every stored 🚩 read of a session (state, state label, every rule
row) and prints the K11 ratio (minute sum ÷ the stored scan-row volume) with its n. The 11-23 baseline (critic, 55
setups of 11 names): 0 state and 0 label differences, 6 setups with a row difference (the re-fetched bars).

## What he will see on 🎾

Rule rows only when the structure is there AND the float gate passes — about 6 of his 15 names on 11-23. Otherwise ONE
sentence in GG's own words:

- the missing structure — "none — no tennis ball action today (…)" — no gate sentence;
- the float gate — "none — Float 14.7M > 10,000,000" — and `gate_text` says the setup's structure IS on the chart and
  the detector keeps no rule rows behind a failed float gate. When the gate read Massive's shares outstanding (or
  nothing), `gate_text` adds that it is not a float figure and that the 🚩 pass would ask Yahoo first; a run never does.

This is the detector's design (structure first, float gate last). `gate_text` is null on the four other setups, on a
🎾 block with rows, and on a 🎾 `none` with no structure.

## Honesty notes

- **Off the 🚩 pass's list.** A Watch name the pass did not read today still gets the five setups; the `scanner` line
  says "not on the 🚩 pass's list today — these are the setup rules alone". His scanner floors are not judged by the
  detectors. (Main session 2026-11-24: worded "the 🚩 pass's list", not "GG's scanner list", because the pass also
  reads 📌 trader adds whose floors are waived — verifier finding: 11-23 had 7 of 64 rows with source 'trader'.)
- **K11 volume.** The run's K11 number is `bars.session_volume(frames)` — today's 1-minute bars before the last closed
  5-minute bar (the Watch's own 1M-floor number). The 🚩 pass uses the scanner's day volume. Direction (critic,
  re-measure with the equality probe before quoting): minute sum ÷ scanner volume 0.987–0.9999, n = 6 — the run's
  number is the LOWER one, so a broke read near 1,000,000 can read "broke — not A+" here and A+ on the next pass.
- **Bars are re-fetched.** A run reads Massive's bars as they are now; rows can differ from the 🚩 card for the same bar.
- **Float.** The 🚩 pass's stored read when today's read doc has one ("pass"); else the pass's chain steps 1–2 now
  ("run": the shares cache, then Massive shares outstanding — nothing stored). A run-asked Massive read says "asked by
  this server for a run — nothing stored", never "asked once a session". `yahoo_could_admit` is pinned to
  `context.refine_order`'s group.
- **Class shares.** A dot-form Watch name misses the 🚩 store's spelling → "not on GG's scanner" and "no alert rang"
  for a listed name — the same blind spot as the tile's 🚩 chips (`tags.py`). Not widened.
- No `rules_info.py` line: no new rule. UNMEASURED.

## HIS CALLs (spec §7)

1. K11 on a run = the minute sum (keep, or "not judged on a run")? 2. Off-scanner names graded (or refused)?
3. Closed market = one sentence (or grade the last session)? 4. 60 s reuse on the same bar (0 = always re-fetch)?
5. Order after 🎾. 6. Rows in the card's order (or failed first)? 7. Panel from the left, 24rem. 8. "▶ Rules" (two ▶
in the ⤢ row). 9. The panel's own sentences are mine. 10. One Yahoo float ask per run (writes the shares cache) — not
built. 11. The K3 "no bar yet" ✓ prints as on the card. 12. Any ring from a run — not built. 13. The stored read beside
the run — not built. 14. Auto re-run per bar — not built. 15. Class shares spelling. 16. 🎾 rows behind a failed float
gate — a detector change, not built.

## Files

- `backend/chart_maps/gajjala_watch/run_rules.py` (new — the engine and its words)
- `backend/chart_maps/gajjala_watch/api.py` (the route + `_run_body`)
- `backend/chart_maps/gajjala_watch/constants.py` (`API_RUN_PATH`, `RUN_RULES_ON`, `RUN_REUSE_SEC`, `RUN_BUDGET_SEC`,
  `RUN_MODULE`, `RUN_ANSWER_KEYS`, `RUN_TITLE_TEXT`, `RUN_NOTE_TEXT`, `RUN_ERROR_TEXT`)
- `backend/tests/test_gajjala_watch_run_rules_2026_11_24.py` (new); `backend/tests/test_gajjala_watch_api_2026_11_15.py`
  (the route pin, WIDENED 2026-11-24)
- `backend/scripts/gajjala_watch_run_rules_probe.py`, `backend/scripts/gajjala_watch_run_rules_equality_probe.py` (new,
  read-only)
