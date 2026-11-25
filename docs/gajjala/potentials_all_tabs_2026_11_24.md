# 🧠 from every tab — one list of every Gajjala tab's forming names (2026-11-24)

Ajay 2026-11-24 ~22:00 ET, verbatim, in order: "Also I see some stocks stay intraday and some stay in Reversal Squeeze.."
· "I need all the potentials moving to the potentials tab real time.." · "I noticed its not happening today" · "I need a
common place to see all the potnetials from all tabs" · "I mean all Gajjala's tabs".
Earlier that day: "On the potential tab the Intraday VCP like BENF and LVWR are supposed to show up but they are not..
They are only in Intraday why?"

Display only (🟡). Nothing here rings a phone, writes a tracker doc, or moves a rule, gate, threshold, A+ logic, sort
default, the 🧠 cards, the 🧠 chip count, 📈 Track or the 👀 line. UNMEASURED — nothing measured says these names win.
Spec: SPEC potall REV 2 (WP be-potall backend, WP fe-potall frontend — its own doc,
`potentials_all_tabs_frontend_2026_11_24.md`).

## Diagnosis — today, 2026-11-24 (read-only probes, container on 5dec3c6b)

**No real bug found.** Cron passes 193 / 193 (04:01–20:01, no gap), 12 on-open passes, 0 potential-gate errors. 🧠 list
size per cron pass averaged 2.5 (max 11 at 09:56) — the prior sessions read 1.2–2.5, so today was not anomalous. Every
tracker sighting matches `potential.potential_kind`; all 83 tracker names were on today's list.

| Sub | Shown forming / partial today | Reached 🧠 (first seen ET) | The rest — exact reason |
|---|---|---|---|
| 🚩 Bull Flag | 20:01: 7 cards, all `partial` | PDC 10:11 armed, invalid 10:16 | partial is not a potential (his K1) |
| 💋 EMA Kiss & Fly | 20:01: 18 cards — 15 partial, GLXG + PDSB forming, BAK stopped | 21 pairs; GMM 12:21 → A+ 12:26 | GLXG / PDSB: forming with no sideways bar (P0, Cheetah default); BAK stopped with **no A+** |
| ➖ Horizontal Fade | 20:01: 3 forming (APUS, FFR, GMEX) | 36 pairs; FFR + GMEX on 🧠 at the close | APUS: no sideways bar (P0) |
| 🌀 Intraday VCP | 20:01: 8 carded, 30 counted not carded (< 2 contractions) | 12 pairs; LVWR 14:26 → A+ 14:36; BENF 14:31 → A+ 14:41; ONFO 13:21 → A+ 13:31 | after the break: triggered / partial → off 🧠; B grade never a potential; < 2 contractions = his 2026-10-20 rule |
| 🎾 Reversal Squeeze | 20:01: 32 cards — 31 partial (mostly K3 volume), JZ forming | 13 pairs, all first seen armed | each went armed → partial in 5–75 min (K3 failed) → off 🧠, still carded on 🎾 |
| 🌱 Diverging | 0 at 20:01 | never — 🧠 read the five setups only | no path to 🧠 until now |
| 🧨 Divergence | 5 records, all exited | n/a | a record of names that already rang, not a forming read |
| 🩳 High SI | 17 names; JZ the only one with a forming 🎾 read | JZ (via 🎾) | a membership list; its state is the 🎾 read |
| ☀️ / 🌙 | 24 / 0 movers, no structure yet | n/a | on 🧠 only as the 👀 watch line |
| 📋 All strategies | 68 rows = the five setup subs | its 🧠 tier = the 🧠 list | not a source of its own |

By design: partial is never a potential (K1); a potential that breaks leaves 🧠 at the next pass; forming with no
sideways bar (P0) and 🌀 < 2 contractions are never potentials; 🌱 / 🧨 / 🩳 / ☀️ / 🌙 had no path to 🧠.

**Plainly: the "stays in Reversal Squeeze" names are `partial` (31 of 32 🎾 cards at 20:01 — a rule failed, mostly K3
volume). With the shipped default they stay OFF the new list too. That part of the ask is NOT addressed unless you say
yes to HIS CALL #1.**

## What ships

`backend/chart_maps/gajjala/pot_all.py` (NEW, pure — no store, fetch, clock, write or push) serves ONE block,
`all_potentials`, on the 🧠 sub, GG5 only (the 1-minute page and 🧪 Audited carry no key). The rows, below the 🧠 cards:

1. every card the five setup subs show in the `forming` state (`LIST_STATES`) that the served 🧠 cards do not already
   show (`pot_all.covered` reads each card's setup + every 🧩 also setup). Tier "potential" when `potential_kind` calls it
   one — only when a card fault, the card cut or a tracker fault kept it off the cards (normally empty); else "forming";
2. every 🌱 Diverging row (build's ONE `diverging_tab.evaluate`), tier "forming";
3. `KEEP_BROKE`: every setup whose 🧭 stages (`stages.steps` — the ONE "when did it reach A+" engine: the tracker's A+
   step, or a live A+ alert that rang) show a 🎯 A+ this session, with "✅ broke HH:MM" (the FIRST A+ clock — the same
   clock as the card's 🧭 tag). A current `triggered` / `stopped` read with no A+ step is **never** a ✅ (BAK).

Each row: `SYM · emoji sub · state` in that sub's own words; "listed · no 🧠 alert" when the 🧠 push never rings for its
state; the card's own "read at the HH:MM ET pass" when the read is older than the shown pass; a 🩳 tag on a 🎾 row that
🩳 also lists; a link to the source card ONLY when that card exists (a GMM-like invalid read or a BENF-like 🌀 with
< 2 contractions is plain text). Order: other forming (trigger armed, then highest volume — `potential.order_key`), then
✅ broke newest first, your 🚫 names last in each group, cut at the transport cap with a "more" line. The title / order
/ rule / as-of words are served for the 🧠 ⓘ fold; `live` needs an `ok` pass, in the window, not stale or warming; the
as-of words never print "None". A tracker read fault says "the 🧠 tracker could not be read — ✅ broke may be missing".

`tab.py`: the 🧠 branch adds the key under `_soft` (a raising block → `null`, the rest of the board byte-identical), and
the three tag walks (🚫 broker / 📌 trader / 🎪 promo) include `all_potentials`. Nothing else in tab.py moved.

Expected at the 2026-11-24 close (10 rows): forming — APUS ➖, GLXG 💋, PDSB 💋, each "listed · no 🧠 alert"; ✅ broke —
GLXG 🎾 17:01, BENF 🌀 14:41, LVWR 🌀 14:36, ONFO 🌀 13:31, GMM 💋 12:26, BENF 🎾 12:11, AAOI 🌀 08:01. Not rows: JZ 🎾,
GMEX ➖, FFR ➖ (the three 🧠 cards); BAK 💋 (stopped, no A+).

## Cost

🧠 GET at the 20:01 store = 384,180 bytes, built in 0.16 s. The block adds ≈ 7 KB (+2%) at today's close, ≤ ~50 KB at
the 80-row cap. No new store read: reads, cards, trackers, 🌱, 🩳 and the rang A+ entries are build's own.

## Goldens (regenerated in the hermetic container, diff key for key)

- `backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json`: 15289 → 15349 leaves, 60 ADDED, 0 changed, 0 removed — all
  under `<mode>/potential/all_potentials` (GGA 🚩 "✅ broke 10:41").
- `frontend/src/components/__fixtures__/gajjala_potential_golden_2026_10_15.json`: 3836 → 3883 leaves, 47 ADDED, 0
  changed, 0 removed — all under `boards/potential/all_potentials` (GGG 🚩 forming, no sideways bar; BBB 💋 ✅ 10:31).

## Push path pinned

`tests/test_gajjala_pot_all_2026_11_24.py` pins the sha256 of `potential.run_pass / potential_kind / eligible / track /
compose`, `alerts.run_pass` and `stages.steps` to the untouched tree, re-runs both push paths over their fixtures, proves
a 🧠 build writes nothing, and checks by AST that pot_all imports no store / push / alerts / run module.

## HIS CALL (none decided here)

1. List `partial` cards too? Default NO (K1 "partial is not a potential"). ≈ 55 more rows at today's close (31 from 🎾).
   **With NO, the "stays in Reversal Squeeze" names stay off the list.**
2. Keep A+ names with "✅ broke HH:MM" — shipped ON as offered; HH:MM = the 🧭 🎯 A+ clock (the pass that first saw it,
   or the rang alert), not the card pill's entry bar. Keep or drop; the clock choice is yours.
3. 🧨 records, 🩳 names with no forming read, ☀️ / 🌙 movers as rows? Default no; 🩳 only tags a 🎾 row.
4. The 🧠 chip count stays "names with a 🧠 potential" — or count the list rows?
5. Order: other forming by highest volume → ✅ newest first, 🚫 last per group.
6. A visible as-of / closed-day stamp on the list? Default none (in the ⓘ fold); stale / warming keep the board's lines.
7. GG5 only — not on 🧪 Audited or the retired 1-minute page.
8. The 🧠 push stays armed-only, one ring per name; P0, 🌀 < 2 contractions and partial stay off the push.
9. Fence each 🧠 card on its own (one raising card blanks the 🧠 grid today) — not built; the list catches those
   potentials as tier "potential" rows.
10. Placement: under the 🧠 cards, the cards' potentials not repeated — or above / repeated.
