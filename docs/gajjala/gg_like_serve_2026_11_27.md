# 🧘 GG-like calm check — pass, ring and board wiring (2026-11-27)

Ajay 2026-11-27: "Yes please, I think we are in bear market and looking at bad setups and make them work, forcing them
to work honestly... Can you update them please.. find calmer and better setups.. Continue to track the runners we might
evolve and find patterns in the current runners too but I want to make sure we are finding similar setups to Gajjala".

Spec: SPEC gglike REV 2 §3.6, work package `be-serve-board`. The engine and its bounds live in
`chart_maps/gajjala/gg_like.py` (see `docs/gajjala/gg_like_2026_11_27.md`). This page covers only where the block is
computed, frozen and served. Observed on GG's example charts, not his rule. UNMEASURED.

## 2026-11-27 — what moved

Display and record only. No gate, detector constant, alert, push, sort or list membership moves.

| where | what | when the key is there |
|---|---|---|
| `run.py` `_gg_like_of(rdoc, sym, logged)` | `gg_like.doc_blocks(rdoc)` once per name, after the read doc is built and before `upsert_read` → `rdoc["gg_like"] = {setup: block}` | only when at least one setup is judged. Any fault → `{}`, one log line per pass, the pass status and every other write unchanged |
| `run.py` → `alerts.run_pass` / `potential.run_pass` | `**({"gg_like": gl_by} if gl_by else {})` — `gl_by` = `{SYM: {setup: block}}` | only when non-empty. Nothing goes into `ctx` / `alert_ctx` / `pot_ctx` |
| `alerts.py` `_gl_fields` | `base.update(...)` right after the 📶 stamp → `gg_like` on the A+ claim, refusal and shadow record | only when `gg_like.from_stamp` holds and the block's `entry_bar_t` is the claim's. `compose`, `refusal` and the counts never read it |
| `potential.py` `_gl_claim` | the 🧠 claim dict gains `gg_like` → `push.gg_like` | only when `from_stamp` holds and the block's `as_of` is the read's `as_of_bar_t`. The settle (a dotted `$set` of state / result / at_et) never touches it |
| `tab.py` | `_soft("gg like", GL.tag, out, reads_by, v=v, pots=pot_docs)`, after the ⏸ breakout line, before `_strip_private` | GG5 only, the five setup subs and 🧠 only. `pots` is what the keep rule reads: a card in `MARKED_STATES`, or one whose 🧠 push rang today, serves `keep: true` |

The 1-minute page and the 🧪 Audited overlay call both push gates without the keyword, so their records do not
change. ☀️ / 🌙 / 📋 / 🏁 / playbook / 🧨 / 🌱 / 🩳 boards carry no `gg_like` key.

## Tests

`backend/tests/test_gajjala_gg_like_serve_2026_11_27.py`, on the house run day (`tests/test_gajjala_run.py`) and the GG5
identity scenario:
- the read doc's `gg_like` equals `doc_blocks` of the stored doc. NEGATIVE: a name with no judged read has no key.
- NEGATIVE: with the engine raising, every write, payload, count and /alerts row equals the real pass with every
  `gg_like` key stripped (both modes). With an empty answer, neither gate gets the keyword.
- the A+ claim / shadow record and the 🧠 push carry the block of their own bar. NEGATIVE: another entry bar or
  as_of bar freezes nothing, and dry, on-open and held passes write none.
- the card subs carry `gajjala.gg_like` and the board `gg_like`. NEGATIVE: the board minus the key equals a build with
  `GL.tag` as a no-op (same order, same counts). Other subs, 🧪 and 1-minute builds carry no key.
- keep: true for the A+ card and for a forming card whose 🧠 push rang. NEGATIVE: false with no push, `held`,
  `failed`, a non-dict push, or no tracker doc. Keep changes nothing else on the block.
- a stored block with another `as_of` / `entry_bar_t` is recomputed. A fresh one is served as stored.

The GG5 identity goldens (`tests/test_gajjala_variant_gg5_identity.py`) go red by design: ADDED leaves only. The
regen belongs to the main session.

## Push-path sha pins (refix, 2026-11-27)

The one kwarg on `alerts.run_pass` / `potential.run_pass`, the one `base.update(_gl_fields(...))` line and the one
`**_gl_claim(...)` splat move the source sha of both functions, so two older pins go red:
`test_gajjala_pot_all_2026_11_24.py::test_push_path_sources_are_byte_identical_to_the_untouched_tree`
(`PUSH_PATH_SHA["alerts.run_pass"]`, `PUSH_PATH_SHA["potential.run_pass"]`) and
`test_gajjala_si_ssr_potential_2026_11_24.py::test_the_engines_the_c1_hold_never_edits_are_byte_unchanged`
(`alerts.run_pass`). Those files are not this package's; the main session re-pins the three shas with a dated note.
`test_gajjala_gg_like_serve_2026_11_27.py` now proves the edit is additive: both sources with exactly the fenced 🧘
edits undone hash to the 2026-11-25 values (`PRE_GG_LIKE_SHA`); any other change breaks that pin (NEGATIVE).
New shas: `alerts.run_pass` `e3bd70e8dc89477f2f3b8868baa135280e40a3ad7715a70c6a5812d8abb3a6fc`,
`potential.run_pass` `28d202c297eb453817cc61ffc81f2d76d5faf80b664b2ecf7a04aacf728628c6`.
