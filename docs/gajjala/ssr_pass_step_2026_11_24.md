# ⛔ SSR — the Gajjala pass step (2026-11-24)

Ajay, verbatim (2026-11-23): "No shorting at the bid (SEC short-sale restriction) Can we check or this for other stocks too?"

Spec: `…/scratchpad/ssr/spec.md` §3.9, work package W3 `gajjala-step`. The rule, the computed read and the words are W1's
(`backend/short_interest/ssr.py`, doc `docs/short_interest/ssr_rule_201_2026_11_24.md`).

## 2026-11-24 — what the pass does

The 5-minute Gajjala pass (`backend/chart_maps/gajjala/run.py`) hands what it already read to
`short_interest.ssr.record_pass`, the ONE writer of the computed short-sale-restriction read:

```python
deps.ssr(rows, frames, now, session, followed=names, good=good)
```

| Argument | What the pass hands over |
|---|---|
| `rows` | the pass's whole-market snapshot DICT `{SYM: row}`, as is (the same object `deps.snapshot()` returned) |
| `frames` | `{SYM: bars.Frames}` of the listed names that loaded (`.raw` = the 1-minute bars) |
| `now`, `session` | the pass clock (UTC) and its ET session date |
| `followed` | the listed names (`names`, sorted; narrowed by `--symbols` on a non-dry pass) |
| `good` | the snapshot answered HTTP 200 with rows |

- **Where:** after the 🧨 divergence step and before the 🌫️ day read, in its OWN `try`.
- **When:** only when `Deps.ssr` is set and the push gates are live (`not push_dry`): never on an on-open pass, never on a
  dry run, never in a test or replay that does not hand it in.
- **Never a key of `out`, never `out["errors"]`, never a gate.** A raising step logs `gajjala pass: the ⛔ SSR read
  failed` with the traceback and the pass goes on: the pass summary, the pass doc, the `/alerts` rows and every store
  write are byte-identical with and without the step (pinned). The result is logged on one line:
  `gajjala pass: ⛔ ssr {...}` (the `stale_bar`, `lo_under_minutes` and `disagree` counts live there).
- **Wiring:** `_cron_deps()` sets `d.ssr = SSR.record_pass` behind a FENCED import. A missing or broken module leaves
  the step off and logs ONE warning: `gajjala pass: the ⛔ SSR step is not wired: <ExceptionName>`; the rest of the cron
  Deps is built as before. The ⏱ bar-close child shares `_cron_deps`, so it runs the step too (`record_pass` is
  idempotent). `dry_deps()` and `main`'s on-demand `Deps(...)` are not given it.
- **No outside call rides the pass:** `run.py` imports neither `ssr_lists` nor `ssr_corp` (the exchange lists and the
  dividends / splits are read by the api container's worker, never here).

## Limits

- The step sits inside the pass's one big `try`: when an earlier step raises, the SSR step does not run for that pass and
  nothing is written; after `SSR_STALE_PASSES` missed passes a followed name reads `scan_stale` (unknown — never a stale
  off). The step's own `try` guards the pass FROM the step, not the step from the pass.
- The cron container runs the step only once deployed: the deploy block carries `cron`.
- A label only: the step pushes nothing, gates nothing, sorts nothing and enters no lane. UNMEASURED.

## Tests

`backend/tests/test_gajjala_ssr_step_2026_11_24.py` — the one call and its arguments (W1's frozen signature as the
stub, so a call that does not bind fails here); `good=False` on a failed snapshot; NEGATIVES: default / dry / on-open /
`main --on-demand` / `main --dry-run` never carry or call it; byte-identical summary, writes, docs and `/alerts` rows
with and without the step; a raising step leaves `errors`, `status` and `main`'s exit code unchanged; the fenced import
(missing module, module without `record_pass`) → `.ssr is None` + one warning; `RUN._cron_deps() == …["deps"]` still
holds; source guards (position after 🧨 and before 🌫️, its own `try`, no `out[` and no `errors` inside it, no
`ssr_lists` / `ssr_corp` in `run.py`, no `ssr` import in `alerts.py`, `potential.py`, `tab.py`, `ledger.py`).
