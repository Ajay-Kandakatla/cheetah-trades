# 🥇 Luk — cards the latest pass did not re-read: tagged, and after the re-read ones · 🔄 right after the title (2026-11-11)

**Display only.** UNMEASURED, as the whole 🥇 tab is. No gate, rule, threshold, push, alert, ledger or count change.
Nothing is hidden: every card that was served before this change is still served (variant A — the cards a sub SHOWS
are the same set; only their order inside it moves). The names read each pass are unchanged.

## His words

Ajay 2026-11-11 ~15:35 ET, on the 🥇 Luk tab, verbatim (his spelling):

> "I do not see an ondeman scan button for Luks
>
> It still show HQ as the first ticker for me"

**The order (HIS CALL #1 below) was NOT answered by him.** Variant A (cut first, then the stable partition) was chosen
by the main session as the set-preserving default: at ~15:40 ET the main session told him "cards the latest pass did
not re-read get a 'not re-read since HH:MM' tag and drop below the fresh ones", and the house precedent
(`chart_maps/gajjala/tab.py` `broker_bottom`, `docs/gajjala/volume_sort_broker_bottom_2026_11_09.md`) cuts first and
never drops a card. Variant B (re-read first, then the cut) is **HIS CALL — not built**.

## Why HQ was first (the cause — NOT changed here)

- `backend/chart_maps/luk/run.py:71` `CARRY_STATES = ("forming", "triggered")` — an `aplus` read is not carried.
- `run.py:274-289` `_carried` = today's + the previous market day's reads in a CARRY_STATE; `run.py:396`
  `names, capped_n = SC.shortlist(lists, _carried(st, session))`.
- `backend/chart_maps/luk/screens.py:256-272` `shortlist`: a carried name on no screen gets change 0.0, the sort is
  `(-chg, symbol)`, the cut is `LC.LUK_SHORTLIST_MAX` → carried names sort last and are cut.
- `run.py:452` `st.upsert_read(...)` runs ONLY for names whose frames loaded this pass; every other read doc of the
  session keeps its old stamp. `luk/tab.py` serves every read of the session and cards each one whatever its age.
- The state order puts A+ first (`luk/tab.py` `_order_key`) → HQ (A+, break 09:45 ET, read 09:46 ET) was card 1 all
  afternoon although no pass after 09:46 ET read it again.

## Measured 2026-11-11 16:01 ET (read-only probes, the day's last cron pass)

Probes (each `docker exec -i -w /app -e PYTHONPATH=/app cheetah-market-app-api-1 python - < FILE`, single runs):
`reads_probe.py`, `pass_probe.py`, `boards_probe.py` in the session scratchpad `lukstale/probe/`.

**Cards stored vs re-read — pass 16:01:13 ET (583 read docs; 40 stamped == the pass `at`, 543 older, 0 newer):**

| sub | cards stored | re-read by the pass | not re-read | shown (limit `GC.TILE_LIMIT_DEFAULT`) |
|---|---|---|---|---|
| 🔔 opening_range_high | **252** | 39 | 213 | 24 |
| 📦 inside_day_pdh | 20 | 5 | 15 | 20 |
| ↩️ pullback_reversal | 8 | 6 | 2 | 8 |
| distinct names | **265** | 39 | 226 | — |

🔔 by state (stored, re-read): A+ 3, 0 · triggered 109, 15 · forming 14, 4 · listed 79, 8 · stopped 47, 12.

**🔔 Opening Range High — the three boards on the 16:01 ET reads (`boards_probe.py`):**

| | before the change | **A — cut first, then re-read first (BUILT)** | B — re-read first, then cut (NOT built) |
|---|---|---|---|
| first cards | HQ, IONR, NCEL, ASYS, DIOD, GFAI, OCC, VSH | DIOD, RSSS, HQ, IONR, NCEL, ASYS, GFAI, OCC | DIOD, RSSS, RES, NVTS, ARRY, AXGN, DK, LAW |
| the 24 shown | 3 A+ old · 2 triggered re-read · 19 triggered old | the SAME 24 names | 15 triggered · 4 forming · 5 listed — all re-read |
| re-read cards shown | 2 of 24 | 2 of 24 | 24 of 24 |
| re-read cards NOT shown | 37 | 37 | 15 (3 listed, 12 stopped) |
| HQ / IONR / NCEL (the 3 A+) | cards 1 / 2 / 3 | cards 3 / 4 / 5, tagged | not on the board |

📦 and ↩️ hold fewer cards than the limit → A and B are the SAME board there (📦: ERAS, COGT, MIR, TTEK, RGTI, then the
15 not re-read; ↩️: NAVN, ARRY, SHLS, MIR, RGTI, COGT, then TWST, LEGN). Over the 65 cron passes since 10:35 ET the 🔔
top 24 held 1–5 names of that pass's shortlist. On-demand 🥇 pass docs that day: 0.

## 1. The tag

Every card (`luk/tab.py` `tile_of`) carries two served keys:

- `not_reread` (bool) — `luk.tab.not_reread(read_at, latest_at)`: true iff BOTH raw stamps exist and the card's
  stored read stamp (`updated_at`, else `at`, through `GT._stamp_utc`) is **older** (`<`, never `!=`) than the latest
  pass's `at` (`GT._at_utc(latest)` — the same stamp behind the served `pass.at`). No display string is parsed.
- `not_reread_text` — `NOT_REREAD_TEXT = "not re-read since {hhmm} ET"`, `{hhmm}` = the card's OWN read time in ET
  (the clock `read_at_text` prints); null when not tagged. `read_at_text` stays served, unchanged.

| read stamp | latest pass `at` | `not_reread` | `not_reread_text` | group |
|---|---|---|---|---|
| == latest | datetime | false | null | re-read |
| < latest | datetime | **true** | "not re-read since HH:MM ET" | not re-read |
| > latest (pass running / not-ok on-demand) | datetime | false | null | re-read |
| any | none / not a datetime | false | null | re-read (nothing moves) |
| none | any | false | null | re-read (nothing moves) |

Naive (the live Mongo client) and aware stamps compare the same. An ok on-demand pass that moved "latest" is the
latest: the reads it wrote are not tagged, the cron-only reads are. A cron pass that failed still becomes "latest", so
every card is tagged and nothing moves (one group) — the pass line already says the failure.

FE (`frontend/src/components/LukCard.tsx`): a served `not_reread: true` with a served sentence prints the sentence as
an amber pill (`.luk-not-reread`, `data-testid="luk-not-reread-<SYM>"`) in the pills row beside the state pill, the
card root carries `data-not-reread="true"`, and the bottom "read at" line is dropped for that card (the pill carries the
same time). A blank sentence or a non-boolean flag → no pill, the plain line prints. The FE types no word.

## 2. The order — variant A BUILT (cut first)

`luk/tab.py` `build`, the ONE line:

```python
shown = {s: _reread_first(_clip_focus(t, focus, lim), focus) for s, t in tiles_by.items()}
```

`_reread_first(tiles, focus)` is a STABLE partition: the focused card stays first, then the cards the latest pass
re-read, then the cards it did not — each group in the `_order_key` order it came in. It runs AFTER the cut, so **of
the cards shown**, the re-read ones come first; the set of cards a sub shows is the same as before the change. On his
🔔 board at 16:01 ET: HQ goes from card 1 to card 3 with the amber pill, and **37 re-read 🔔 cards were not on the
board** (the cut keeps them off — exactly as before the change).

Served `order_note` (every sub, and `fault_payload`) = `ORDER_NOTE` = `REREAD_ORDER_TEXT` + " · in each group: " +
`STATE_ORDER_TEXT`:

- `REREAD_ORDER_TEXT` = "of the cards shown: the ones the latest pass re-read first, the ones it did not re-read after
  them"
- `STATE_ORDER_TEXT` = "A+ first, then triggered earlier, forming, listed, stopped — the newest break first within a
  state" (the pre-change `ORDER_NOTE`, byte for byte)

An old A+ sits below re-read triggered / forming / listed / stopped cards among the cards shown (state order holds
inside each group only — HIS CALL #4). A deep-linked (`focus`) card stays first and is never cut, tagged or not. The 🏁
Track record, the three screens and the 📓 Playbook are never partitioned. `subs[].n`, `counts`, `counts_text`, the pass
line and `resolve_sub` are unchanged. The FE never reorders by the flag — the served order is the only order.

**Variant B — NOT built (HIS CALL #1):** `_clip_focus(_reread_first(t, focus), focus, lim)` — the board fills with
re-read cards before any old one. On his 🔔 board at 16:01 ET: all 24 re-read (DIOD, RSSS, RES, NVTS, ARRY, AXGN…);
HQ, IONR, NCEL (the 3 A+ that rang) and 19 more of the cards shown before leave the default view — a focused link
(`?focus=HQ`) would still open them, first. `tests/test_luk_not_reread_2026_11_11.py::
test_NEGATIVE_the_other_variant_is_not_in_the_source` proves B's form is nowhere in `luk/tab.py`.

## 3. 🔄 right after the title

Built by WP-FE (`BUTTON_MOVE = yes`). `frontend/src/components/LukBoard.tsx`: a title row
`<div className="luk-topline" data-testid="luk-topline">` holds the title h2, then the owner's 🔄 button (the ONE
button JSX, unchanged: `gg-rescan`, `data-testid="luk-rescan"`, `isOwner && …`, one `onClick={() => void startScan()}`);
the four served answer lines (`luk-scanning`, `luk-scan-note`, `luk-scan-refused`, `luk-scan-err`) sit right under it;
then the honesty paragraph; the pass line (`.luk-passline`: badge, pass text, stale text) stays where it was and holds
no button. `frontend/src/styles/luk.css`: `.luk-topline` (flex, wrap, `min-width: 0`), `.luk-topline .luk-title`
(`flex: 0 1 auto; min-width: 0`), `.luk-topline .gg-rescan { margin-left: 0; }` — overrides 🚩's shared
`.gg-rescan { margin-left: auto }` (left untouched in `gajjala.css`) so the button sits right after the title, not at
the far right end of the row. 430 px: the title wraps inside the row, the button takes its own line at the row's
start, nothing overflows; no inline style.

**Why he did not see it is NOT established.** Facts (frontend access log, container started 13:55:08 ET; spec §1.8):
the button was in the deployed bundle (`ChartMaps-Dkl418-r.js` holds `luk-rescan`; owner `/auth/me` → `is_admin:
true`); his chartmaptrading.com tab loaded no new bundle from 13:55:08 ET to 15:31:29 ET (opened before the deploy);
after the 15:31:29 ET full load it showed the board for at most ~48 s with the button pinned to the far right end of
the pass line (below the title and the honesty paragraph); pounce.ajaykandakatla.dev at 15:34:24 ET asked that Chrome
profile to sign in. Likely a tab opened before the deploy, and the placement low and far right — not proven. The move
to the title row was built on that server-side evidence; it is not confirmed on his screen until he reloads once.

## What did NOT change

The names read each pass, `CARRY_STATES`, `LUK_SHORTLIST_MAX`, `LUK_PASS_BUDGET_SEC`, the card limit
(`GC.TILE_LIMIT_DEFAULT`; the FE still sends no `limit`), every gate, threshold, push, alert and the 🏁 ledger, the
counts and `counts_text`, `PAYLOAD_KEYS` (no new top-level key), `read_at_text` (still served — an old FE ignores the
two new keys, a new FE on an old api sees no keys → no pill), the ℹ️ Rules panel (no rule changed), every 🚩 Gajjala
file.

## Goldens moved (the actual diff, key for key)

`backend/tests/fixtures/luk/luk_board_golden_2026_11_01.json` — 9 changes, nothing else (every fixture read carries
the fixture pass's stamp, so no fixture card is tagged and no tile changes position):

- `default.order_note`, `premarket.order_note`, `track_record.order_note` → the variant A `ORDER_NOTE` above;
- `default.tiles[0]` (AAA), `default.tiles[1]` (CCC), `default.tiles[2]` (BBB): `+ "not_reread": false`,
  `+ "not_reread_text": null`.

Recipe: `LUK_WRITE_GOLDEN=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_luk_tab.py -q -k golden -p
no:cacheprovider` (from `backend/`).

## Tests

- Backend: `backend/tests/test_luk_not_reread_2026_11_11.py` (NEW — the TOY board under the limit and the LIVE SHAPE
  board over it, sizes from `GC.TILE_LIMIT_DEFAULT`; positives: the tag and its sentence, both groups keep the served
  order, the cut runs first, his board shape at the default limit, focus first, the order note, an ok on-demand pass,
  every setup sub; NEGATIVES: no pass, no read stamp, a fresh or newer read, naive vs aware stamps, a non-datetime pass
  `at`, the served set identical without the partition, no other card key changes, 🏁 / screens / playbook never
  partition, no internal or new top-level key, no b-word / "edge" / typed digit, the read rule untouched and nothing
  written, a previous-session pass, variant B not in the source); `backend/tests/test_luk_tab.py` (the four templates
  join the no-digit list; the golden).
- Frontend: `frontend/src/components/LukCard.notReread.test.tsx` (NEW), `LukBoard.test.tsx`,
  `LukBoard.scan.test.tsx`, `LukBoard.phone.test.tsx`.

## HIS CALL (nothing below is decided by this build)

1. **Cut first (A) or re-read first (B) — DEFAULTED, not answered by him.** The main session chose A as the
   set-preserving default (his words above; the main session's ~15:40 ET message; the 🚩 `broker_bottom` precedent).
   Measured on his 🔔 board, 16:01 ET: 252 cards, 39 re-read, 24 shown. **A** (BUILT) = the same 24 cards, re-read
   ones first: DIOD, RSSS, HQ, IONR, NCEL, ASYS… — HQ card 1 → 3, 37 re-read cards stay off the board. **B** (NOT
   built) = re-read first, then the 24: DIOD, RSSS, RES, NVTS, ARRY, AXGN… — all 24 re-read; HQ, IONR, NCEL (the 3 A+
   that rang) and 19 more of today's cards leave the default view. 📦 and ↩️ are the same board either way. B = his
   word.
2. **Carry A+ names and re-read every carded name each pass — NOT built.** At 16:01 ET **265** distinct names were
   carded (252 on 🔔 alone), 39 re-read, 226 not = 6.6 × `LUK_SHORTLIST_MAX` (40). A full re-read does NOT fit one
   5-minute pass as built: `LUK_PASS_BUDGET_SEC` = 120, today-minute fetches are sized ≤ 40 a pass
   (`docs/luk/luk_tab_2026_11_01.md` "Cost arithmetic"), the only stated minute ceiling is `GG1M_MAX_NAMES` = 60 a
   minute, and the Massive rate ceiling is stated nowhere in the repo. It is a budget change (both constants are HIS
   CALL #4 of the Luk build) AND a gate change (a carried, re-read name can ring).
   - **2026-11-12 — answered 2026-11-12 for the cards the board shows — see `realtime_cards_2026_11_12.md`; the
     not-re-read tag stays as the fallback.** His words: "Luks scan is not realtime I see all dated values can you make
     it realtime". Every card the board shows (≤ `LUK_REREAD_MAX`) + today's 🥇 alert cards are re-read each pass
     AFTER the push gate, so a re-read rings nothing and the shortlist is unchanged. Carded cards the board does NOT
     show are still not re-read (HIS CALL #7 there); letting a re-read ring is still a gate change (HIS CALL #2 there).
3. **The card limit on 🥇.** The FE sends no `limit`, so `GC.TILE_LIMIT_DEFAULT` (24) of 252 🔔 cards is all he can
   open; the route allows up to `GC.TILE_LIMIT_MAX` (80). A larger limit, a "show more", or a limit per sub = his
   word (a default).
4. **An old A+ sits below re-read triggered / forming / listed / stopped cards** (both variants). State order holds
   inside each group only. The alternative — partition inside each state — keeps A+ on top, and HQ stays card 1
   (tagged) whenever no A+ was re-read.
5. **Tagged, never hidden, state label unchanged.** An old read still says "A+ — every rule met…". Hiding
   not-re-read cards, or relabelling an old A+, is a semantic change.
6. **Stopped and listed cards are tagged and moved too** (the rule is every card). Exempting them = his word.
7. **A deep-linked (focus) card stays first even when not re-read** (tagged) — under B it would also be the only way
   an old card past the limit is opened.
8. **The 🔄 answer lines move up with the button; the pass line stays** under the honesty paragraph. Moving the pass
   line up too = his word.
9. **Words and placement are mine**: the pill sentence "not re-read since HH:MM ET" (from the brief, not his words),
   the order-note sentence of the built variant, the pill beside the state pill in place of the bottom "read at" line,
   and the button right after the title instead of at the row's far end.
10. **Why he did not see 🔄 is not established** (section 3): a pre-deploy tab until 15:31:29 ET, then ~48 s on the
    new bundle, then pounce asked him to sign in. The move was built on the server-side evidence; not confirmed on his
    screen.
