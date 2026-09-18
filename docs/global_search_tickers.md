# Tickers in the ⌘K global search field (2026-09-18)

Ajay, verbatim:

> can you make global search help find ickers also directly in the same field

## What shipped

One field. The ⌘K palette (`frontend/src/components/GlobalSearch.tsx`) now
returns **two kinds of row** from the same input — pages out of his own menu, and
tickers out of `/symbol-search`. No mode switch, no prefix character, no second
box. Typing `DOCN` puts DigitalOcean on screen; typing `notification` still puts
Notifications on screen; typing `digital` puts both.

**Nothing in this feature is measured, and nothing in it gates an alert, an
order, a lane or a threshold.** The ordering rules below are UX choices in the
same class as the existing `navSearch.ts` tier table. No edge is claimed
anywhere, and the ✨ card says so.

## The two halves

| | Pages | Tickers |
|---|---|---|
| source | `lib/navSearch.buildIndex` over the backend menu (`useMyMenu`) | `GET /symbol-search` (Finnhub proxy) via `hooks/useTickerSearch` |
| timing | synchronous | debounced + aborted, lands later |
| cap | `RESULT_LIMIT = 8` (unchanged) | `TICKER_RESULT_LIMIT = 4` |
| gate | the menu itself | only when `sepa` is in this user's menu |
| ranking | `searchNav` (untouched) | `lib/tickerSearch.rankTickers` (new) |

`lib/navSearch.ts` was **not modified**. Page results still come only from the
backend menu, so the palette's safe-by-construction property — a page row can
never point at something this user cannot reach — is exactly what it was.

## Row order, in plain words

1. **One pinned ticker**, when he typed a symbol EXACTLY and no page is named
   that word (see the pin rule below).
2. **Pages**, in `searchNav` order, unchanged.
3. **The remaining tickers.**

Appending rather than interleaving is deliberate: the two halves answer at
different times, and a row that arrives 300 ms late must never be able to move a
page row out from under his finger. Section headers (`Pages` / `Tickers`) appear
only when both kinds are on screen, so a pure-page query renders exactly as it
did before this change and a pure-ticker query renders a bare list.

### Ticker ordering key (a UX choice, nothing measured)

Inside the ticker section, lower wins and provider order breaks the tie:

| tier | rule | why |
|---|---|---|
| 0 | the symbol IS the query | he typed a ticker |
| 1 | the symbol starts with the query | `doc` → DOCN |
| 2 | the company name starts with the query | see below |
| 3 | anything else that survived the relevance filter | |

Tier 2 exists because of his own worked example. Measured provider order for
`digital` on 2026-09-18 was WDC, DLR, GEN, **DOCN**, … — DOCN sat at rank 4 of a
4-row budget and one provider reshuffle from vanishing. With tier 2 the list
reads **DLR, DOCN, DBRG, WDC**: names that START with what he typed above names
that merely contain it.

Finnhub's free-tier search is not prefix-filtered, so a **relevance filter** runs
first: a row is kept only when the query prefixes the symbol or prefixes some
word of the company name. Measured, that drops IBKR / ISRG / PGR / VRT for `iv`
(making `iv` render no ticker section at all) and drops Camden Property /
Camden National for `amd` while keeping Amdocs.

## The pin rule, and the five collisions it saves

An exact symbol takes row 0 **unless a page label contains that word as a whole
token**.

The obvious rule — block the pin when a page label EQUALS the query — measured
**false on 5 of 5** real collisions on 2026-09-18, because every menu label is
multi-word. Whole-token containment blocks all five:

| he types | the symbol that would have hijacked it | the page he meant |
|---|---|---|
| `maps` | MAPS (WM Technology) | 🗺️ Chart Maps |
| `lab` | LAB (Standard BioTools) | ⚡ Signal Lab |
| `path` | PATH (UiPath) | 📚 Learning Path |
| `copa` | COPA (Themes Copper Miners ETF) | Kell (CoPA) |
| `ravi` | RAVI (NT Ultrashort FI ETF) | Ravi's Strategy |

It also pre-emptively blocks `board`, `orb`, `gex` and the other single-token
labels in his menu, and it still pins `amd`, `docn` and `gnt`. The blocked
symbol is never hidden — it just sits in the Tickers section under the pages.

**When the pin lands and pages already matched**, the highlight **follows the
pin** — Enter opens the ticker.

This was the other way round until 2026-09-18, and it was a defect, not a trade.
Measured against his real 18-symbol menu, the pages answered first for **9 of
18** — AMD, LLY, ANET, MU, TSM, CRDO, SPY, VRT, ARM — so the highlight seeded on
a page, the exact-symbol row then landed *above* it, and the old seed-once rule
kept the highlight where it was. He typed `AMD`, saw `📈 AMD` on top, pressed
Enter, and got Supply/Demand. `LLY` went to `/volleyball`.

The rule is now narrower and says what was actually meant: **a late row never
moves a highlight HE placed.** A `touched` flag flips the moment he presses ↑/↓,
and resets when he types again. Until he touches it the highlight is ours and
follows the pin; after he touches it nothing may take it — pinned row included.
Both directions are pinned by test, along with the reset between queries.

`iv` resolves itself: 2 characters, no fuzzy page match below 3, zero page hits,
and the relevance filter drops every Finnhub row — so the palette looks exactly
as it does today.

## Fail-open contract

The ticker lookup is a network call to a third-party proxy, so:

- Pages render **instantly and synchronously** and are never blanked, delayed or
  replaced by the ticker half.
- Every failure path — `!ok`, network error, malformed JSON, timeout, junk body,
  bare array, `{results:'nope'}` — ends at `status:'error'` with no rows, and the
  pages stay on screen with one muted line under them.
- Typing is never blocked: changing the query re-renders the page rows before
  any lookup answers.
- A stale response can never overwrite a newer query. The hook uses the
  `SupportLevels.tsx:175-189` idiom — a `seq` generation ref plus an
  `AbortController` per run — not a third invention. (The older
  `GlobalStockSearch` typeahead has no AbortController and CAN be overwritten by
  a stale response. It is untouched and still mounted on `Sepa` and
  `SepaCandidate`; that bug was deliberately not copied here.)

### What the palette says

| state | copy |
|---|---|
| blank query | `Nothing in your menu yet.` (unchanged) |
| lookup in flight, no page matches | `Looking up tickers…` |
| lookup failed, no page matches | `No page matches for “docn” — ticker lookup unavailable` |
| lookup failed, pages present | the page list + a muted `Ticker lookup unavailable — pages only` |
| otherwise | `No matches for “docn”` (unchanged) |

"No matches" while a lookup is in flight would be a lie he reads for 60–290 ms
on a cold call and forever on a timeout, which is why the loading and error
lines exist. There is still exactly ONE `role="status"` node at a time.

## First token only

Finnhub does not phrase-match. Measured 2026-09-18:
`?q=digital ocean` → `{"results":[]}`, while `?q=digital` returns DOCN. So the
lookup asks the **first token** of what he typed. Typing `digital ocean` searches
`digital`; the DOCN row is there the whole time and never blinks out mid-word.
HIS CALL #1.

## Request count — what 300 ms does and does not fix

`TICKER_DEBOUNCE_MS = 300`, raised from the 180 ms the existing typeahead uses.
The endpoint caches per distinct prefix (`main.py:1135`), so every prefix that
escapes the debounce is its own cold provider call.

| typing cadence | requests for an 8-character ticker |
|---|---|
| 220 ms/key at 300 ms debounce | **1** |
| 400 ms/key at 300 ms debounce | **7** (one per character from length 2) |
| any cadence ≥180 ms at 180 ms debounce | 7 |

A debounce does not bound the request count — no interval does. 300 ms is a
trade, not a fix, and both numbers above are pinned by tests so the trade stays
visible. HIS CALL #6.

Separately, keying the effect on the **effective** query (first token,
length-gated) removes the duplicates a raw-query effect would fire: typing a
trailing space, or walking `digital` out to `digital ocean` one key at a time, is
still ONE request.

## Constants, by name

| constant | value | where |
|---|---|---|
| `RESULT_LIMIT` | 8 (pages, unchanged) | `components/GlobalSearch.tsx` |
| `TICKER_RESULT_LIMIT` | 4 | `lib/tickerSearch.ts` |
| `TICKER_DEBOUNCE_MS` | 300 | `hooks/useTickerSearch.ts` |
| `TICKER_TIMEOUT_MS` | 4000 | `hooks/useTickerSearch.ts` |
| `MIN_TICKER_QUERY_LEN` | 2 | `hooks/useTickerSearch.ts` |

Minimum length 2 because one character measured as unrelated large caps
(`?q=d` → D, NVDA, AVGO, LLY) and `?q=""` is a 422, not an empty envelope.

## The measurements behind the tables

`/symbol-search`, live on this box, 2026-09-18:

```bash
for q in digital docn DOCN amd iv gnt maps lab path copa ravi zzzzz; do
  rtk proxy curl -s -H "X-User-Email: ajaykandakatla@gmail.com" \
    "http://127.0.0.1:8000/symbol-search?q=$q"
done
```

| query | result |
|---|---|
| `""` | HTTP 422 `string_too_short` |
| `d` | 11 unrelated large caps — not prefix-filtered |
| `digital` | WDC, DLR, GEN, DOCN, GLXY, IDCC, APLD, CIFR, IOND, AD, DBRG |
| `digital ocean` | `{"results":[]}` — no phrase match |
| `DOCN` / `docn` | DOCN, DigitalOcean Holdings Inc |
| `amd` | AMD, CPT, DOX, CAC |
| `iv` | IBKR, ISRG, PGR, VRT, CL, … none relevant |
| `gnt` | GNT, type `Closed-End Fund` |
| `maps` / `lab` / `path` / `copa` / `ravi` | MAPS / LAB / PATH (twice) / COPA / RAVI |
| `zzzzz` | `{"results":[]}` |
| latency | 2 ms cached, 60–290 ms cold |

The real nav engine against the real 52-label menu, same day:

```bash
rtk proxy curl -s -H "X-User-Email: ajaykandakatla@gmail.com" \
  http://127.0.0.1:8000/me/menu > /tmp/menu.json
cd frontend && npx esbuild src/lib/navSearch.ts --bundle --format=esm \
  --outfile=/tmp/navSearch.bundle.mjs && node /tmp/probe_nav.mjs
```

| query | page rows |
|---|---|
| `docn` `nvda` `tsla` `pltr` `gnt` `digital` `iv` | **0** |
| `amd` | 3 (all fuzzy) |
| `maps` | 8, 🗺️ Chart Maps first |
| `lab` / `path` / `copa` / `ravi` | 2 / 1 / 1 / 2 |

Zero page rows on every pure-ticker query is why the list gate had to move from
`results.length` to `rows.length`: without that, the headline ask rendered
"No matches for “docn”" with the list unmounted.

## Not touched

- `backend/main.py` `/symbol-search` — unchanged. It is a free-tier Finnhub
  proxy with a 6 h cache, no fuzzy matching, no phrase matching, returns ETFs and
  closed-end funds, and returned PATH twice on 2026-09-18. Phrase search or a
  first-party symbol list is a backend change on its own branch (HIS CALL #8).
- `frontend/src/lib/navSearch.ts` and its test suite.
- `frontend/src/components/GlobalStockSearch.tsx` (mounted at `Sepa.tsx:1207`
  and `SepaCandidate.tsx:782`).
- `frontend/src/test/setup.ts`.

## Tests

| file | covers |
|---|---|
| `frontend/src/lib/tickerSearch.test.ts` | ranking on the live payloads, the five pin negatives, merge ordering, 11 malformed-body negatives |
| `frontend/src/hooks/useTickerSearch.test.tsx` | debounce, request counts at 220/400 ms per key, abort on change / unmount, out-of-order responses, 500 / rejection / bad JSON / timeout, the no-fetch negatives |
| `frontend/src/components/GlobalSearch.test.tsx` | the whole palette — every keyboard path unchanged, plus the ask itself, the hijack negatives, the highlight-stability pin, the copy matrix, the fail-open matrix and the `sepa` gate |

## HIS CALL

Eight open items are listed in the spec's section 7 and reported with this
change. In short: the first-token rule, the 4-row ticker budget, the highlight
behaviour when the pin lands, the `sepa` menu gate, the 2-character minimum, the
300 ms / 4 s numbers, the loading/error copy, and whether `/symbol-search`
itself should ever grow phrase search.
