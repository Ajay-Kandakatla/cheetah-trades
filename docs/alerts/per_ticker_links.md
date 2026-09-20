# Per-ticker links on every alert row — 2026-09-20

## The ask, verbatim

> "I need the stock tickers to be clickables in alerts individually if there are
> multiple in one alert by command click"

A digest push names many symbols in one body. Until today the /alerts page, the
notification bell and the /notifications history panel linked the row to ONE
place: the push's `url`, plus the single `ticker` when the push had one. A
"🧲 Demand zone — DYN +5 more" row gave him no way to open FLL.

## The payload key

Each of the five digest builders now carries `tickers` — the names the BODY
lists, **in the order the body lists them** — beside the existing `ticker`
(which stays `None` on a digest, because a digest names nobody in particular).

| builder | file | `tickers` |
|---|---|---|
| 🚀 growth at demand | `growth/alerts.py::digest_message` | every item's `row.symbol` (the body lists them all) |
| 🧲 demand / nearing demand | `supply_demand/demand_alerts.py::digest_message` | `items[:DIGEST_MAX]` after the `dist_pct` sort |
| 🪃 reversal off demand | `supply_demand/zone_bounce_alerts.py::digest_message` | `items[:DIGEST_MAX]` after the `bounce_pct` sort (strongest first) |
| 🔥 hot pullbacks | `supply_demand/hot_pullback_alerts.py::digest_message` | `rows[:12]` |
| 📐 patterns confirmed | `patterns/pattern_alerts.py::digest_message` | `rows[:10]` |

The `+N more on the board` tail line names nobody, so it contributes nothing.
Singles are **not** edited: they already carry `ticker`, and the feed falls back
to it.

## The storage

`push/history.py::record` stores `tickers` on the history row:

* a list of strings only — upper-cased, order preserved, capped at
  `MAX_TICKERS = 25` (a digest body never names more; the cap is the guard);
* anything else — absent, a bare string, a list with a non-string in it — is
  stored as `None`, never a guess.

The row shape in the module docstring was updated. The key is additive: every
other stored field is byte-for-byte what it was.

## The derivation (old rows only)

`push/recent.py::derive_tickers(row, known)` serves a list on **every** feed
row, in this order:

1. a stored `tickers` list wins (upper, deduped, order kept) — the builder knew
   the names at push time, so nothing is re-parsed;
2. else the single push's own `ticker` → `[ticker]`;
3. else, **and only when `row["kind"] in DIGEST_KINDS`**, the body is read:
   for each line of `body.split("\n")`, for each item of `line.split(", ")`,
   the LEADING token `item.strip().split(" ")[0].split("(")[0].rstrip(",:;")`
   is kept when it matches `_TOKEN` **and** is in `known`;
4. else `[]`.

`DIGEST_KINDS` = `growth_demand_alert`, `demand_alert`, `zone_bounce_alert`,
`hot_pullback_alert`, `pattern_alert`, `board_arrival`, `earnings_reaction`.

`_TOKEN = ^[A-Z]{1,5}(?:[.-][A-Z])?$` — upper case only, with an optional
single-letter class suffix. `load_universe("full")` spells class shares with a
**hyphen** (BRK-B, HEI-A, MOG-A, UHAL-B, BF-B, LEN-B, GEF-B); the dot form is
accepted by the shape so a Massive-spelled body still resolves, but it must
still be a known symbol.

`known_symbols()` = `universe.load_universe("full")` ∪ `symbols.RENAMES` keys
(the OLD symbol, still spelled in a 90-day-old body) ∪ each rename's NEW symbol
(`value[0]` — `RENAMES` is `{OLD: (NEW, effective, evidence)}`) ∪
`symbols.DELISTED` keys (a name can die inside the 90-day TTL). Cached at module
level for `KNOWN_TTL_SEC = 3600` and injectable; a loader that raises leaves the
rename tables standing rather than emptying the set.

A breakout row (`sepa_breakouts`) serves `[ticker]`, or `[]` when it has none.

## The limits — read these before trusting a derived row

<!-- 2026-09-20: the flash-card feature was DELETED from the tree ("Delete
     Flashcards please"). The `minervini_flashcards` KIND survives only as a
     label for old push_history rows, which push/recent.py hides at serve
     time. The rule below is unchanged — it was never flashcard-specific. -->

* **Digest kinds only.** The regex NEVER runs over a non-digest body. A morning
  brief or a lesson is prose: "NEW: AT vs ET, the lesson…"
  would otherwise read as three tickers.
* **Leading position only.** `"NVDA, AVGO · pushed 08:15 ET · NEW AT"` derives
  `["NVDA", "AVGO"]` even when ET, AT and NEW are all real symbols — they do not
  lead a comma/newline item.
* **Universe-validated.** A leading token the universe does not know is dropped,
  so a prose fragment that happens to look like a ticker is silent.
* **Lower case is never a ticker** — `nvda` in prose does not link.
* The derivation is a best-effort read of rows stored BEFORE 2026-09-20. Every
  row stored from today carries the list, so the parse retires itself as the
  90-day TTL rolls.

## The contract sentence

> For a digest kind, a token is read ONLY from the leading position of a
> comma/newline item, and only when the universe knows it; every other kind's
> body is never parsed at all.

Pinned in `backend/tests/test_push_tickers.py` (30 tests), which also pins each
builder's `tickers` against its own body, the storage cap and coercion, the
rename both ways (SATS → ECHO, a stub universe carrying neither), the caching,
and that the `/notifications/recent` row gains exactly one key.

Nothing about WHICH alerts fire changed. No gate, threshold or level was
touched — this is a link, not a rule.
