# Every item on a consolidated push, each ticker its own link (2026-09-29)

## The ask

> "I am unable to see the other that are hiddedn her
>
> Can you show them all and make all the tickers clicable individually?"

His screenshot was the /alerts card "⚡ Tape burst at a zone — CRWV +7 more" (`trade_flash`). It showed 4 lines.
The push row never stored the other 4, but every burst is still a document in `trade_flash_events` (the dedupe
store the push was built from), so the card now lists all 8 (see "Old ⚡ tape-burst rows" below).

## The seam: log-only `items`, stripped at the sender

- Every in-scope composer adds `payload["items"] = [{"symbol", "text"}, …]`. It covers EVERY entry, in body order,
  and `text` is exactly the line the composer prints. The body, the title, `tickers` and every other key are
  byte-identical to before.
- `push/sender.py` strips `LOG_ONLY_KEYS = {"items"}` (`device_payload`) before `_send_one`. The phone payload is
  exactly what it was. Why: Web Push caps a payload at about 4 KB, 44 items × ~100 B would blow it, and pywebpush
  would then fail the whole notification silently (counted as `failed`).
- `push/history.record` still receives the FULL dict.

## Stored shape (`push_history`)

- `items`: `[{symbol: str|None, text: str}]`. `text` is stripped and trimmed to `ITEM_TEXT_MAX = 300`. `symbol` is
  stripped and upper-cased, or None. Every other key is dropped. The list is capped at `MAX_ITEMS = 100`, keeping
  the head in order.
- `items_total`: the count of valid entries before the cap.
- Anything invalid (not a list, empty, no entry with a non-blank `text`) is stored as `None` / `None`.

## Served shape (`GET /notifications/recent`)

`push/recent.served_items` adds these keys to a push row, and only when the row lists at least one linkable line:

- `items`: `[{symbol, text, url, pushed}]`. The body's own lines come first, verbatim (`pushed: true`). The stored
  entries the body never printed follow (`pushed: false`).
- `items_not_stored`: how many entries the push had that were never stored.
- `items_total` is never served. Rows without items carry neither key.

A body line is matched to the next stored entry POSITIONALLY when it IS that entry's text, or its leading token
equals that entry's symbol case-insensitively, so a None symbol or a lower-case body never stalls the walk into
repeated lines. Otherwise its leading token links only when it is in `known_symbols()` (universe "full" ∪ RENAMES ∪
DELISTED).

With stored items, the body's own pure tail ("+N more", "+N more on the board", "+N more on /watchlist", "+N more on
Chart Maps ▸ …") is not served: the entries below the divider ARE those names, so the card never says "more" twice.
A session tag riding on the tail ("+3 more · pre-mkt") is kept as its own line ("pre-mkt"). The key-level
"Unmeasured — a close through a level, not a signal." footer is a disclaimer, not a tail marker, and is kept.

## `ITEM_URL_BY_KIND` (one map, pinned against the composers' own URL functions)

| kind | per-ticker page |
|---|---|
| `trade_flash` | `/sepa/{sym}?tab=tape&from=supply-demand` |
| `demand_alert` | `/sepa/{sym}?tab=supply` |
| `zone_bounce_alert` | `/sepa/{sym}?tab=supply` |
| `supply_break_alert` | `/sepa/{sym}?tab=supply` |
| `key_level_alert` | `/chart-maps?tab=support&symbol={sym}` |
| `med_catalyst` | `/sepa/{sym}?tab=catalyst` |
| `juggernaut_watchlist` | `/sepa/{sym}?tab=supply` |
| `leaderboard_breakout` | `/sepa/{sym}?tab=supply` |
| `accumulation_change` | `/sepa/{sym}?tab=supply` |

On /alerts, a `/sepa/` url renders as `TickerLink` with that tab and `from=alerts`, so Back returns to /alerts.
Any other internal url is linked as-is.

## Legacy rows (stored before 2026-09-29, no `items`)

- Only a kind in the table above qualifies, and never a single (a row with a non-blank `ticker`).
- The body is parsed per line: the leading token after any emoji or marker, kept only when it is in the known
  universe. Lower case never matches.
- `items_not_stored`:
  - the first body line `+N more …` gives N;
  - else the title's `+N more` gives `max(0, N + 1 − printed lines)`, where every non-tail line counts, linked or
    not, so an unknown symbol never inflates the claim;
  - else 0.
- His CRWV row, without the events store: 4 links (CRWV ×3, KLAC) and "+4 more not stored in this push".

### Old ⚡ tape-burst rows (2026-09-29, critic fix)

`push/recent.tape_items_for_legacy` rebuilds an old `trade_flash` row from `trade_flash_events`:

- Only an old row (no stored items, no `ticker`) whose title says `+N more` and whose body printed fewer than N+1
  lines (`tape_recon_want`).
- ONE ranged read for the whole page: `recorded_at` in [oldest ts − 240 s, newest ts + 5 s], projected to the
  headline fields, sorted newest first, capped at `TAPE_RECON_MAX_DOCS = MAX_LIMIT × 24` (the measured p99 per
  push) and `TAPE_RECON_MAX_MS = 2000`. No row on the page needs it → no read at all.
- Per row, the window [ts − 240 s, ts + 5 s] must hold EXACTLY the title's N+1 events (1,672 of 1,677 old rows
  on prod). The events are sorted dollars-desc (the builder's order) and each line is `trade_flash.headline(e)`,
  so the rebuilt lines equal the lines the phone showed.
- A count mismatch, no events, Mongo down, a failed read, a malformed event or a window cut by the doc cap → the
  honest "+N more not stored in this push" path.
- His CRWV card: CRWV, CRWV, CRWV, KLAC (on the phone), then CRWV, CSGP, CRWV, PSKY.

## Rendering (/alerts)

- `AlertItems` renders one line per entry, and only the SYMBOL inside each line is a link.
- Rows that list items hide the header chip strip. The bell and /notifications keep it.
- Up to `ITEMS_FOLD_AT = 20` entries are fully open. Above that, the first 20 show plus a "show all N" toggle.
- A "+N more not in the notification:" divider sits before the first entry the phone never showed.

## Measured (read-only probe of prod `push_history`, 2026-09-29)

- `trade_flash` events per push over 90 days (1,671 rows): **p50 9 · p90 16 · p99 24 · max 44**.
- Legacy `trade_flash` lines linkable with the known-universe gate: **6,220 / 6,540 (95.1%)**. The misses are ETFs
  outside the universe (`PPA`, `ITA`); they stay plain text.
- Tail-vs-title disagreements on the not-stored count: 0 across trade_flash, demand, break and bounce.

## Out of scope

The comma-list digests that also cap names: 🔥 hot pullback (first 12), 📐 pattern confirmed (first 10) and
🚀 new VCP setups (first 5 + "+N more"). They are HIS CALL 1.

See also [per_ticker_links.md](per_ticker_links.md) (the 2026-09-20 header chips).
