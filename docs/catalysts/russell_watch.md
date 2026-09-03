# Russell inclusion watch — add dates (2026-09-02)

Ajay: *"Can you add the dates of these candidates additions please."*

The board (`backend/catalysts/russell_watch.py`, `/catalysts/russell-watch`)
screens caps against the current member bands; this adds **when** a candidate
would actually go in, and **how long** the screen has been flagging it.

## FTSE's published 2026 calendar (held as data in `SCHEDULE`)

| Event | Rank day | Preliminary list | Effective (after close) | In the index | IPO window |
|---|---|---|---|---|---|
| June 2026 reconstitution | 2026-04-30 | 2026-05-22 | 2026-06-26 | 2026-06-29 | — |
| Q3 2026 IPO additions | 2026-07-31 | 2026-08-21 | 2026-09-18 | 2026-09-21 | 2026-05-01 → 2026-07-31 (start inferred) |
| December 2026 reconstitution | 2026-10-30 | 2026-11-13 (updates 11-20, 11-27, 12-04; lock-down 11-30) | 2026-12-11 | 2026-12-14 | 2026-08-03 → 2026-10-30 |

Sources, read 2026-09-02:

1. FTSE Russell notice *Russell US Semi-Annual Reconstitution — Schedule
   Update*, 05 Nov 2025: the Q4 cycle moved from the second Friday of
   November to **after the close Friday 11 December 2026** (open of 14 Dec);
   cap cut-off 30-Oct-26; IPO review period 3 Aug–30 Oct 2026; indicative
   products 13-Nov-26; lock-down 30-Nov-26.
   <https://research.ftserussell.com/products/index-notices/home/getnotice/?id=2617649>
2. LSEG *Russell Reconstitution* page: June 2026 prelim lists from 22 May,
   effective after the close 26 June; December 2026 rank day 30 Oct, prelim
   13 Nov, updates 20 Nov / 27 Nov / 4 Dec, effective 11 Dec.
   <https://www.lseg.com/en/ftse-russell/russell-reconstitution>
3. EMAT (Evolution Metals & Technologies) release, GlobeNewswire 24 Aug 2026:
   included on the preliminary lists of the *third-quarter 2026 IPO additions
   process*, published 21 Aug 2026, addition effective 21 Sep 2026.
   <https://www.globenewswire.com/news-release/2026/08/24/3349659/0/en/>
4. FTSE Russell FAQ, Russell US Equity Indexes 2026: quarterly IPO rank date
   is the last business day of Jan/Apr/Jul/Oct; from 2026 the December IPO
   inclusion is folded into the December reconstitution.

**Correction shipped with this**: the board's method note used to call the
EMAT 2026-09-21 date "the second 2026 reconstitution". It is the quarterly
IPO add; the second reconstitution is effective 2026-12-11.

## Decision table — `add_event(board, listed, today)`

| Candidate | Rule | Result today (2026-09-02) |
|---|---|---|
| Promotion (R2000 → R1000) | only at a reconstitution | Dec 14 (recon) |
| Add, listed inside an upcoming IPO window | rides that IPO add | listed 2026-06-10 → Sep 21 (IPO add, **list out**) |
| Add, listed in the December window (Aug 3 – Oct 30) | December reconstitution | Dec 14 |
| Add, old listing / unknown listing date | next reconstitution | Dec 14 |
| Any, after the last loaded event | `None` → "schedule n/a" | never a guess at 2027 |

`lists_published` flips true once the event's preliminary list date has
passed: from then on the cap screen is a guess at a list that already exists,
and the row says so (amber date, "list out", tooltip). Listing dates come from
`sepa.ipo_age.listing_date` (profile provider, cached forever; None → the
reconstitution path).

## "On list since" — `stamp_first_seen`

Mongo ledger `russell_watch_seen` (`_id = board:symbol`, `first_seen`,
`last_seen`). The ledger starts 2026-09-02, so names already on the prior
cached board are seeded with that board's `as_of` — the earliest we can
prove — never with "now". Mongo down → `first_seen = None` → a dash.

## Tests

`backend/tests/test_russell_watch.py` (schedule dates + order, the decision
table incl. past-Q3 fall-through and the past-calendar refusal, ledger seeding
/ stickiness / no-Mongo), `frontend/src/components/RussellWatch.test.tsx`
(per-row date + path + list-out flag, since-date and dash, cycle line,
schedule-n/a row, old payload without the fields).
