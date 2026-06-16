# Macro-event overlay — methodology

_Added 2026-06-16. Ajay: "add a macro into my portfolio analysis — consider macro
news that would impact the stock in the advice. If tomorrow is FOMC readout, with
our FRED access consider it, and allude to it in the Market Gauge hold vs sell."_

## What it is (and isn't)

An **informational binary-event heads-up** — the exact same discipline as the
Minervini Ch.8 earnings-quality overlay (`eq_sell_risk`):

> Minervini sells on **PRICE** (broken trend / stops, Ch.12-13), not on a calendar.
> So an imminent macro event does **NOT** change the price-based hold/sell verdict.
> It's surfaced so a tape-wide move (a FOMC/CPI readout can gap everything) isn't a
> surprise and stops/sizing get the attention they deserve.

We never predict the event's outcome or how the market will react — only that a
high-impact event is **near**.

## The single source — `macro_calendar.imminent_events()`

```
imminent_events(within_days=5, max_tier=1) -> [{date, kind, tier, label, days_until, when_label}]
```

- Reuses the **cached** macro calendar (FRED `/releases/dates`, the same free key
  the gauge uses) — **no extra FRED calls**. Soft-fails to `[]`.
- Tier 1 = market movers only: **FOMC decision, CPI, jobs report (NFP), Core PCE**.
- `days_until` / `when_label` ("today" / "tomorrow" / "in N days") computed in
  **ET** (events are ET-scheduled: FOMC 2pm, CPI 8:30am).

Both surfaces below read from this one function, so they can never disagree.

## Surface 1 — holding diagnosis (`portfolio/diagnosis.py`)

- `_macro_events_heads_up(events, sector)` → list of plain-text heads-ups
  (mirrors `_earnings_quality_sell_risk`). Adds a sector line when the holding's
  sector is rate/inflation-sensitive (financials, REITs, homebuilders, semis,
  utilities, growth) **and** the event is FOMC/CPI/PCE.
- New output field **`macro_events`** (list of strings), informational — sits
  next to `eq_sell_risk`, does not touch `position.verdict`.
- The LLM write-up payload gets `upcoming_macro_events`, and the system prompt
  now weaves in ONE clause naming the nearest event as binary event risk (never
  predicting its outcome). Grounding/citation rules are unchanged.
- Rendered in `HoldingDiagnosis.tsx` as a blue **📅 Macro event ahead** box,
  labelled "binary event risk, not a sell signal (Minervini sells on price)".

## Surface 2 — Market Gauge hold-vs-add (`sepa/market_gauge.py`)

`_outlook()` now **leads its watch list** with imminent tier-1 events:

> 📅 FOMC decision tomorrow (2026-06-17) — binary macro event; reduce NEW risk
> into it and let the readout confirm before adding.

This is the gauge's "hold vs add" guidance (the exposure-band context). It is
**presentational only** — the gauge **score, pillars and exposure band are
unchanged** (SEPA contracts + gauge tests still green). It renders on the Market
Gauge page's next-day-outlook section automatically.

## "FRED alerts"

The user's "fred alerts" = the FRED-backed scheduled-release calendar we already
have (next FOMC/CPI/jobs/PCE dates). A threshold-crossing alert system ("CPI YoY
> 6% → notify") does **not** exist yet — that would be a separate feature.

## Tests

- `backend/tests/test_macro_events.py` — window/tier filtering + day labels +
  soft-fail; heads-up strings + sector sensitivity; gauge outlook surfaces /
  omits the event.
- `frontend/src/components/HoldingDiagnosis.test.tsx` — the 📅 box renders when
  events present, omitted when not.
