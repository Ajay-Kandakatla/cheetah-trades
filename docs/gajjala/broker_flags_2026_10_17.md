# 🚫 Not eligible at Fidelity — a tag on Gajjala's tab (2026-10-17)

Code: `backend/chart_maps/gajjala/constants.py` (`BROKER_NAME`, `BROKER_FLAG_SEED`, `BROKER_SYMBOL_MAX_LEN`),
`backend/chart_maps/gajjala/store.py` (`BROKER_STATE_ID`, `broker_symbol`, `broker_flags`, `broker_doc`,
`GajjalaStore.set_broker_flag`), `backend/chart_maps/gajjala/tab.py` (`BROKER_FLAG_TEXT`, `BROKER_FLAG_ICON`, the other
served words, `broker_text_for`, `broker_block`, `editor_block`, `_broker_tag`, `build(…, owner=)`),
`backend/chart_maps/gajjala/ledger.py` (`served_block(…, broker_text_of=)`), `backend/chart_maps/gajjala/alerts.py`
(`compose(…, broker_text=)`, `run_pass`, `COUNT_KEYS` `"broker_flagged"`), `backend/chart_maps/gajjala/potential.py`
(`compose(…, broker_text=)`, `run_pass`), `backend/chart_maps/api.py` (the board GET + three owner routes),
`backend/supply_demand/rules_info.py` (the ℹ️ line), `frontend/src/lib/gajjala.ts`, `frontend/src/components/GajjalaBoard.tsx`,
`frontend/src/styles/gajjala.css`, `frontend/src/lib/newFeatures.ts`. Spec: `BUILD_SPEC12.md` + `AMENDMENTS12.md` (A1–A3,
F1–F11) + `DECISIONS12.md` D1–D9 (session scratchpad `gg_broker/`). Contracts: `frontend/scripts/contracts.mjs`
"🚫 Gajjala broker tag (2026-10-17)". SPECS: the "🚫 Not eligible at Fidelity" bullet under "Chart Maps — Gajjala's tab".
✨ `chart-maps-gajjala-broker-tag-2026-10-17`. Function names are the stable cite.

## READ THIS FIRST

1. **Nothing is hidden.** This is a TAG on his own list, never a filter. No scan, list, tile, row, count, gate or push is
   filtered, muted or counted-as-hidden anywhere; there is no hidden-count. His words chose it: "Or just add a tag that
   not eligible on Fidelity". Tested: the owner payload minus every `broker_text` / `broker_flags` /
   `graveyard_broker_text` key equals the non-owner payload byte for byte.
2. **His own list is the only honest source.** Fidelity publishes no per-ticker eligibility feed; its own order ticket
   is the source. A name goes on the list only when he adds it after Fidelity's ticket refused it. No surface guesses
   eligibility, and the chip never appears on a name that is not on the list.
3. **The seed is EMPTY.** `BROKER_FLAG_SEED = ()` (`# Ajay 2026-10-17`). WORX was the first example, then he withdrew
   it ("sorry I might be wrong about worx …"), so nothing is seeded and WORX is not tagged. The evidence that no price
   floor is the rule: he bought XLAB and XELB on 2026-10-16, and the read-only Mongo probe of 2026-10-17 ~02:50 ET reads
   `gajjala_scan` `2026-10-16|XLAB` `last.price 2.14` and `2026-10-16|XELB` `last.price 0.44` (XELB under a dollar went
   through). DECISIONS12 D6 wrote "(0.43)"; no source for that figure is on file, so the served words say "XELB under a
   dollar" and this doc cites the probe (BUILD_SPEC12 R5).
4. **Owner-only = the primary admin only** (AMENDMENTS12 F1). The list is HIS Fidelity list. The board GET's `owner` and
   the three routes gate on `ollama_chat.api.is_primary_admin(email)` of the forwarded `X-User-Email` — Ajay only. Every
   other reader, the second household email included, is served `broker_text: null` on every row and
   `broker_flags: null`, and gets 404 on the three routes.
5. **The pushes still ring.** A flagged name's 🎯 A+ and 🧠 potential pushes ring exactly as before; the title carries 🚫
   and the body says it in words before UNMEASURED (AMENDMENTS12 A1, DECISIONS12 D4). Nothing is muted (HIS CALL Q4).
6. **A store read fault is said, not disguised** (AMENDMENTS12 F5). The effective set falls back to the seed (fail-open
   to the seed — empty today, so no name is tagged during a fault); the 🚫 strip shows
   "your list could not be read this time — the tags are off until the next read" and no add box, never
   "none on your list yet …".
7. **No guessed pre-screen** (HIS CALL Q2). A rule-based screen from Fidelity's PUBLISHED restrictions is NOT built.

## The ask (Ajay, verbatim, in order — 2026-10-17 ~02:00 ET)

> "There are certain tickers that I am unable buy online.. like WORX was one of them.. In Fidelity.. Should I move my money to others?"
> "ok then avoid showing me names that are not eligible in Fidelity then."
> "Or just add a tag that not eligible on Fidelity"
> "I was able to buy Xlab and XELB btw"
> "sorry I might be wrong about worx actually take a look at fidelity rules yourself sorry"

Reading: line 3 is the design (a TAG, not a hide). Line 5 empties the seed. Line 4 is the evidence that no price floor
is the rule.

## What he sees

- **The 🚫 strip** — one line right under the Gajjala header, on every sub, owner only: the served
  `🚫 not eligible at Fidelity`, each name on his list as a chip with ✕ (take it off the list), and a one-field add box
  (type a ticker, Enter or "add"). With an empty list it reads "none on your list yet — add a ticker when its order
  ticket refuses it" + the add box. After any change the board re-reads once.
- **The 🚫 card toggle** — an icon-only 🚫 button in every card's footer (setup, ☀️, 🌙, 🧠 cards; BUILD_SPEC12 R9);
  title and label = the served `🚫 not eligible at Fidelity`; pressed when the card's name is on the list; a click adds
  or removes that name.
- **The chip** `🚫 not eligible at Fidelity` — a muted badge beside the symbol, on every surface where a flagged name
  appears:

| Surface | Served key path |
|---|---|
| the five setup cards · 🧠 cards · ☀️ premarket movers · 🌙 post-market movers | `tiles[i].broker_text` |
| 🧠 strip in each setup sub | `potential.rows[i].broker_text` |
| 📈 Track (today + yesterday) on 🧠 Potential | `track.today.rows[i].broker_text`, `track.yesterday.rows[i].broker_text` |
| 👀 watch line on 🧠 Potential | `watch.symbols[i].broker_text` |
| 🎯 A+ line (every sub) | `enterable.rows[i].broker_text` |
| 🌙 A+ recap | `postmarket.recap.rows[i].broker_text` |
| 🪦 graveyard | `graveyard_broker_text` (present only beside `graveyard_text`): `🚫 not eligible at Fidelity: ABCD` |
| 🏁 Track record + the 🕰️ timeline | `track_record.days[d].rows[i].broker_text` (`ledger.served_block`; `rows_for` untouched — history stays) |
| the list itself | `broker_flags` (owner `broker_block`; anyone else null) |

Not tagged (BUILD_SPEC12 R8, HIS CALL Q9): `awaiting` (no symbol), the situational strip's `best_symbol`, and the push
`items[].text` line.

`.` and `-` are one ticker (AMENDMENTS12 F8): the list keeps the typed form, every membership check folds
`upper().replace(".", "-")` on both sides, so `MOG.A` on the list tags a served `MOG-A` row and the reverse.

## The served words (tab.py — the only place; the FE types none)

| Name | Text |
|---|---|
| `BROKER_FLAG_TEXT` | `🚫 not eligible at Fidelity` (= `f"🚫 not eligible at {GC.BROKER_NAME}"`) |
| `BROKER_FLAG_ICON` | `🚫` (the card toggle; the push title suffix) |
| `BROKER_LIST_TEXT` | `{text}: {symbols}` (the 🪦 graveyard line) |
| `BROKER_EMPTY_TEXT` | `none on your list yet — add a ticker when its order ticket refuses it` |
| `BROKER_FAULT_TEXT` | `your list could not be read this time — the tags are off until the next read` |
| `BROKER_ADD_LABEL` | `add` |
| `BROKER_ADD_PLACEHOLDER` | `ticker` |
| `BROKER_REMOVE_TITLE` | `take it off the list` |
| `BROKER_BAD_SYMBOL` | `Not a ticker — letters, digits, “.” or “-”, starting with a letter, at most 10 characters.` (the 10 = `GC.BROKER_SYMBOL_MAX_LEN`) |
| `BROKER_WRITE_FAULT` | `The list could not be saved this time — nothing changed; try again.` |

The broker's name lives only in `constants.py`: `BROKER_NAME = "Fidelity"   # Ajay 2026-10-17 ("In Fidelity")`. The
words "not eligible at" appear exactly once in the backend sources (case-sensitive; the ℹ️ line keeps its capital
"Not eligible at"). `GajjalaBoard.tsx` and `lib/gajjala.ts` contain no "Fidelity" and no "not eligible".

Owner `broker_flags` block, as served:

```json
{"editable": true, "symbols": ["ABCD"], "text": "🚫 not eligible at Fidelity", "broker": "Fidelity", "toggle": "🚫",
 "empty_text": "none on your list yet — add a ticker when its order ticket refuses it", "fault_text": null,
 "add_label": "add", "add_placeholder": "ticker", "remove_title": "take it off the list"}
```

On a store read fault the block carries `editable: false` and `fault_text` (the fault sentence above), never
`empty_text`; the strip renders the fault sentence and hides the add box.

## The pushes (DECISIONS12 D4 + AMENDMENTS12 A1)

The list is read ONCE per pass (`store.broker_flags(store)` at the top of `alerts.run_pass` and `potential.run_pass`).
For a flagged name the clause `🚫 not eligible at Fidelity` (the served word, `tab.broker_text_for`) goes right before
the UNMEASURED tail, and the title gains ` · 🚫` (`tab.BROKER_FLAG_ICON`). An unflagged title and body are byte-identical
to 2026-10-16. Refusals, claims, the window and the send path are unchanged; a flagged name rings like any other.

🎯 A+ (E1 / E2 of `docs/gajjala/entry_live_2026_10_16.md`, widened):

```
title   💋 GGA · EMA Kiss & Fly A+ entry · 🚫
body    broke 11.00 on the 5m bar closing 10:35 ET · stop 10.81 (−1.7%) · Kissed and honored the 9 EMA; entry = the kiss bar's high · 🧠 potential rang 10:05 ET · Float 3.2M · 🚫 not eligible at Fidelity · UNMEASURED — his setup, not a buy signal
```

The after-hrs variant: `… · after-hrs · he uses limit orders and less size outside RTH (S8 1:16:35) · 🚫 not eligible at
Fidelity · UNMEASURED — his setup, not a buy signal`.

🧠 potential (armed / building):

```
title   🧠 GGA · 💋 EMA Kiss & Fly — trigger armed · UNMEASURED · 🚫
body    trigger 10.97 · stop 10.81 (−1.4%) · 🚫 not eligible at Fidelity · UNMEASURED — a potential, not an entry; GG enters on the reclaim of the highs · {session} · first seen {HH:MM} ET · {float} · {rotation}
```

Building: `{reason} · trigger {T} (not armed yet) · stop {S} (−{r}%) · 🚫 not eligible at Fidelity · UNMEASURED — a
potential, not an entry; GG enters on the reclaim of the highs · …`.

Lock screen (~180 characters, `push/sender.py`): on a typical A+ body the clause lands past the cut, so the title's 🚫
is what the lock screen always shows; on a 🧠 body the clause lands early.

`alerts.COUNT_KEYS` gains `"broker_flagged"` (last) — how many flagged names the pass saw; informational, never a gate.
/alerts prints no chip for it (HIS CALL Q8). `potential.COUNT_KEYS` is unchanged. ITEM_KINDS stays 14.

## The routes (owner = the primary admin; everyone else 404)

| Route | Answer |
|---|---|
| `GET /chart-maps/gajjala?sub=…` | the board; owner → `broker_text` on every listed row + `broker_flags`; anyone else null (no 401 path added — `maybe_current_user`) |
| `GET /chart-maps/gajjala/broker-flags` | `{symbols, seed, added, removed, text, broker, fault_text}` — `fault_text` is the fault sentence when the list could not be read (the seed alone is served and said so), else null; every write answers the same block |
| `POST /chart-maps/gajjala/broker-flags` `{"symbol": "…"}` | adds (and takes it out of `removed` if there) → 200 + the list; adding twice → the same body |
| `DELETE /chart-maps/gajjala/broker-flags/{symbol}` | removes; a SEEDED name goes to `removed` (the seed can be overridden without a deploy); a name not on the list → 200, unchanged |

Order inside each route (BUILD_SPEC12 R12): owner gate first → the symbol → the write, so a non-owner never learns a 400
or a 503 exists. The POST reads the raw request body (AMENDMENTS12 F3): a non-owner gets 404 whatever the body (never
422); the owner with bad or absent JSON, or a symbol failing `^[A-Z][A-Z0-9.\-]{0,9}$` after upper-casing, gets 400
`BROKER_BAD_SYMBOL`; a read fault before the write → 503 `BROKER_WRITE_FAULT`, nothing written. Writes are serialised by
a module-level lock around the read + the `$set` (AMENDMENTS12 F2); the FE disables every broker button and the input
while a write is in flight.

Examples against the api (the owner header is the one oauth2-proxy forwards):

```bash
curl -s -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8000/chart-maps/gajjala/broker-flags"
```

```bash
curl -s -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8000/chart-maps/gajjala?sub=bull_flag" | python3 -c "import json,sys; print(json.load(sys.stdin)['broker_flags'])"
```

Adds ABCD to his list (a real write):

```bash
curl -s -X POST -H "X-User-Email: ajaykandakatla@gmail.com" -H "Content-Type: application/json" -d '{"symbol":"ABCD"}' "http://127.0.0.1:8000/chart-maps/gajjala/broker-flags"
```

Takes ABCD off his list (a real write):

```bash
curl -s -X DELETE -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8000/chart-maps/gajjala/broker-flags/ABCD"
```

A bad ticker → 400, nothing written:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "X-User-Email: ajaykandakatla@gmail.com" -H "Content-Type: application/json" -d '{"symbol":"1BAD"}' "http://127.0.0.1:8000/chart-maps/gajjala/broker-flags"
```

Any other reader → 404:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "X-User-Email: doug@example.com" "http://127.0.0.1:8000/chart-maps/gajjala/broker-flags"
```

## The doc shape and the effective-set rule

One `gajjala_state` doc (`store.STATE`), no new collection (`ST.ALL` and the REPLAY-last pin do not move):

```json
{"_id": "broker_flags", "added": ["ABCD"], "removed": [], "updated_at": "<aware UTC>", "by": "<the owner's email>"}
```

Effective set `store.broker_flags(store)` = (`GC.BROKER_FLAG_SEED` ∪ `added`) − `removed`, upper-cased, deduped, sorted;
junk entries (failing `store.broker_symbol`) dropped. Store None, no `get_state`, a raise, a fault or a junk field → the
seed alone (fail-open to the seed). It never raises and never writes. The only write is `GajjalaStore.set_broker_flag`,
reached only by the owner's own POST / DELETE through the api: a fault-aware read (`_find_or_none`; None = fault → no
write) then ONE `$set` of `added` / `removed` (sorted) + `updated_at` + `by`, upsert. On: `removed` −= {sym}, and
`added` ∪= {sym} unless it is seeded. Off: `added` −= {sym}, and `removed` ∪= {sym} if it is seeded.

## What it does NOT do

- It hides nothing, mutes nothing and gates nothing: `run.py` and `scanner.py` name no broker; no `if …broker…` line in
  either `run_pass` (contracts check 3–4).
- It guesses nothing: no pre-screen from price, OTC tier, Caveat Emptor, Expert Market or delisting notices (HIS CALL
  Q2). A name is tagged only when it is on his list.
- It measures nothing and scores nothing about eligibility, and it is not advice.
- Other app users see no chip and no list (HIS CALL Q3); the second household email is a non-owner here.
- One broker, one constant (HIS CALL Q5); no per-broker lists.

## ℹ️ Rules panel

`supply_demand/rules_info.py`, the Gajjala section's last `stops` line (built from `GC.BROKER_NAME` and
`GC.BROKER_FLAG_SEED`, no typed number): "🚫 Not eligible at Fidelity — your own list of names Fidelity would not let you
buy online; a tag only — nothing is hidden, the pushes still ring and carry the tag. Nothing is seeded." The `note` adds
"🚫: XLAB and XELB (XELB under a dollar) went through at Fidelity on 2026-10-16, so a price floor is not the rule."

## Verification

Hermetic backend (network none, `cheetah-tmp-pytest-gb-<wp>-<n>`): `backend/tests/test_gajjala_broker_flags.py` — the
effective-set math (seed ∪ added − removed, a removed seed, every fault → the seed), the writes (idempotent add, seeded
remove, read fault → no write, interleaved writes keep both names), `broker_symbol` (and its NEGATIVES), every §3.4
surface tagged for the owner and no other row, the non-owner walk (every tag null), the nothing-hidden invariant, the
board GET with the owner / Doug / the second household email / no email, the routes (non-owner 404 on all three
whatever the body, never 422; owner 400 / 503; round trip), the push bodies and titles flagged and unflagged (both
kinds), one list read per pass, the fault sentence vs the empty sentence (on the board block AND on the editor block —
the owner's GET on a faulting store is 200 with the seed alone and `fault_text`, never a silent empty list), `.` / `-`
folding, the ℹ️ line. The three goldens are regenerated with `GG_WRITE_GOLDEN=1` as the owner (every row
`broker_text: null`, the owner block with `symbols: []`), never hand-edited.

Contract NEGATIVES (AMENDMENTS12 F11, run by the main session on 2026-10-17 with every file restored byte-for-byte): a
filter on the list inside `alerts.run_pass` / `potential.run_pass` (a `reads` rebinding that drops flagged names), the
tag call removed from the pass, `run.py` naming the list, `store.broker_flags` dropping the seed, the board GET deciding
`owner=` through `is_admin_email`, the POST answering 403 instead of the stealth 404, the DELETE losing its gate — eight
mutations, each turned `contracts.mjs` red; the FE-side mutations (a broker word typed in the board, a dropped chip
testid, the ✨ entry moved) were run by WP-B the same way. The pass may name the list ONLY on its binding line, the tag
call and the count — any other line that names it fails the contracts.

Frontend: `frontend/src/components/GajjalaBoard.broker.test.tsx` — the strip renders served text only, ✕ → ONE DELETE
then ONE board re-read, add → ONE POST, a 400 shows the served `detail` with no re-read, a 404 does nothing, a second
click during a pending write sends ONE request, every surface's chip == the served string, the toggle, the non-owner
payload renders nothing, the card toggle lights from the SERVED tile tag (a list entry `MOG.A` tags and toggles the tile
`MOG-A`; the list alone never lights a toggle); `tsc`; `contracts.mjs` "🚫 Gajjala broker tag (2026-10-17)" (served word in tab.py only, no
"Fidelity" in `GajjalaBoard.tsx`, ✨ first with his second and third lines verbatim).

Branch proof (BUILD_SPEC12 §5.4, READS ONLY): a throwaway api `cheetah-tmp-gb-api` on :8008 with an IN-PROCESS seed
(`GC.BROKER_FLAG_SEED = ("<SYM>",)` in its start string — no Mongo write); owner GET → the `<SYM>` rows tagged, every
other row null; a Doug email → null + no tag; Doug GET / POST / DELETE → 404; owner `POST {"symbol": "1BAD"}` → 400; no
valid POST / DELETE. The preview (Vite :5177, `vite.local.config.ts`) answers POST and DELETE on
`/api/chart-maps/gajjala/broker-flags*` with 204 before the proxy (AMENDMENTS12 F10), so a stray click writes nothing.

LIVE proof after the deploy, as the owner: https://pounce.ajaykandakatla.dev/chart-maps?tab=gajjala — the strip reads
"🚫 not eligible at Fidelity" + "none on your list yet …" + the add box; no chip anywhere (the list is empty). The add /
remove round trip is proved hermetically only; the first real name is his own add.

Deploy (alerts.py / potential.py are cron code):

```bash
./deploy-cheetah-main.sh api frontend cron
```

## HIS CALL

- **Q1 Tag vs hide** — he chose the TAG (his third line); nothing is hidden anywhere (built).
- **Q2 A rule-based pre-screen from Fidelity's PUBLISHED restrictions** (OTC Expert Market / Caveat Emptor / delisting
  notices …) that tags a name BEFORE he tries to buy — a follow-up once those rules are on file; this build ships his
  exact list only.
- **Q3 Other app users never see the chip or the list** (DEFAULT, D3; AMENDMENTS12 F1: the primary admin only) vs
  everyone sees his tags.
- **Q4 A flagged name's A+ and 🧠 pushes keep ringing** with the clause (DEFAULT, tag only) vs muted.
- **Q5 One broker name, one constant** (DEFAULT) vs per-broker lists.

Resolved by the main session or shipped at the planner's default (BUILD_SPEC12 §7, each revertible in one place):

- **Q6 Where the push says it** — RESOLVED (AMENDMENTS12 A1): both — the clause before UNMEASURED AND ` · 🚫` on the
  title, so the lock screen always shows it.
- **Q7 The 🚫 strip on every sub, also while empty** — RESOLVED (AMENDMENTS12 A2): one line on every sub; revisit only
  if he says it clutters (Rule #5).
- **Q8 /alerts prints nothing for `broker_flagged`** (DEFAULT, an informational pass count) vs a "🚫 N on your list" chip.
- **Q9 Untagged**: the situational strip's best runner and the push item line (BUILD_SPEC12 R8, DEFAULT) vs tagged too.
