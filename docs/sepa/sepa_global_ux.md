# SEPA Global — the beginner scanner (UX + gate mapping)

A minimal, jargon-free view over the **same** Minervini SEPA scan, for friends
with little trading experience. The admin `/sepa` page stays the full power
tool; `/sepa-global` is the dumbed-down sibling.

**Route:** `/sepa-global` · **Feature:** `sepa-global` (default ON for everyone;
`sepa` stays owner-only) · **Page:** `frontend/src/pages/SepaGlobal.tsx`
**Transform:** `frontend/src/lib/sepaGlobal.ts` (pure, tested).

## It invents nothing — it relabels the same gates

SEPA Global reads the identical `/sepa/scan` feed and computes **no new
signals**. It maps the scanner's own gates into plain words + a traffic light:

| Backend gate (unchanged) | Verdict | Plain wording |
|---|---|---|
| `entry_exit.decision == AVOID` / `distribution_selling` / climax | 🔴 **Avoid** | "Big investors look to be selling — stay away." |
| `is_buyable` (confirmed breakout, p.203) | 🟢 **Buy zone** | "Confirmed breakout — in the buy zone now." |
| `setup_ready` (base, not yet triggered) | 🟡 **Watch** | "Setting up — wait for the breakout." |
| `is_candidate` (Trend-Template qualifier, p.79) | ⚪ **Leader** | "Strong stock in a confirmed uptrend." |

Avoid is checked **first**, so a climax/distribution name can never read "buy"
— exactly as the admin page's gate behaves.

- **Strength** = the same momentum-led `conviction` rank, bucketed High (≥70) /
  Medium (≥45) / Low; a suppressed (climax/exhaustion) name is always Low.
- **Ordering** = buyable-first, then conviction — byte-identical to the admin
  SEPA default sort, so the best ideas float up the same way.

## UX decisions (for minimal-experience users)

- **Three filters only:** Buy now (`is_buyable`) / Watch (`setup_ready`) / Top
  leaders (`is_candidate`) + a ticker search. No VCP / ADR / stage / CMF /
  whales / political chips.
- **Risk-first, like the book:** every card shows the **buy range**, the **"sell
  if it falls to"** price (the stop), and the **% you'd risk** — Minervini's #1
  rule (cut losses early) made unavoidable.
- **Default tab = Top leaders** so the page is always populated; the verdict
  badge tells the beginner which are actually buyable. The empty Buy-now state
  teaches patience ("patience is free") rather than showing a blank screen.
- **Hostile-market banner:** when `market_context.safe_to_long === false`, a
  one-line warning — don't fight a falling tape even with strong stocks.
- **Educational framing:** a "How it works" explainer + an explicit
  *"educational only — not financial advice"* note (this is a public page, so
  the disclaimer belongs here, unlike the owner's `/chat` agent).

## Tests

- `frontend/src/lib/sepaGlobal.test.ts` — verdict mapping for every gate,
  strength bands + suppression, risk-% computation + fallbacks, the tab filters
  and buyable-first ordering, and negatives (bare row never crashes / no plan).
- `frontend/src/components/SepaGlobalCard.test.tsx` — renders verdict / price /
  buy range / risk-first sell line; omits the plan block when absent.
- `backend/tests/test_owner_auto_grant.py::test_sepa_global_is_default_on_for_all_users`
  — granted to everyone while the full `sepa` page stays owner-only.
