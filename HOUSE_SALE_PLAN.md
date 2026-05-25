# House Sale Plan — 4505 Sovereignty Dr, McKinney TX 75070

**Status:** Listed and active.
**Owner-only dashboard:** `/house` (https://ajays-macbook-pro.tailb3dc79.ts.net/house)
**Co-owner access:** ajaykandakatla@gmail.com, gandurivineetha@gmail.com
**Last updated:** 2026-05-07

---

## ▶ For the next chat session — read this first

**Who you're helping:** Ajay Kandakatla (and co-owner Vineetha). They are selling their primary residence at **4505 Sovereignty Dr, McKinney TX 75070**. Ajay also runs a personal trading dashboard called Pounce / Cheetah; the house module lives inside that app at `/house` but the house topic is **independent** of any trading work.

**What this document is:**
The full strategy + execution plan for selling this specific house. Built collaboratively over a previous chat session. Treat it as the source of truth — the work that came before is consolidated here so nothing has to be re-derived.

**Owner's communication preferences (important — they've explicitly said this):**
- **Terse > verbose.** They've called out long responses as "too much info." Cut every paragraph by half before sending.
- **Concrete deliverables > explanations.** Give them paste-ready text, exact numbers, exact actions. Skip the why unless they ask.
- **Don't re-prove premises.** If they say a fact (e.g. "it's 5 bed 4 bath"), don't fact-check it; trust them and update the artifacts.
- **Markdown formatting can break things.** When they're going to paste into MLS / Redfin / Zillow / agent emails, give them **plain text without `**` bold or `#` headers** — those don't render in real-estate listing fields.

**What's in scope for this thread:**
- Refining the listing description and "What's Special" tags
- Pricing decisions (current floor: Zestimate $665K)
- Organic outreach tactics (LinkedIn, Nextdoor, FB groups, corporate relo, door-knocking, school pickup, etc.)
- Open-house planning
- Reading the daily metrics and recommending price/strategy adjustments
- Drafting agent messages or buyer-agent / mortgage-broker outreach copy
- Differentiation vs new-construction competitors (KB, Lennar, David Weekley)
- Helping decide between price cut, rate buy-down credit, withdraw+relist, or rent

**What's NOT in scope unless they explicitly ask:**
- The Pounce trading app code (separate concern — don't go reading the codebase or rebuilding things; that's a different chat)
- The dashboard's backend implementation (it works; only touch if they report a bug)
- Architectural changes to the `/house` module
- Adding new auth/email gates (the gate is already correct: stealth 404 to non-owners; co-owners are ajay + vineetha)

**Current ground truth (don't second-guess these):**
- Beds / baths: **5 / 4** (MLS still incorrectly shows 4/3 — agent has been informed of the correction; pending propagation)
- List price: **$683,000** (already had one cut from $698K on 5/5)
- Zestimate: **$665,100** — pricing floor is here, not below
- McKinney ISD (NOT Frisco — owner corrected me on this, don't re-introduce Frisco angle)
- 2024 brand-new build (biggest weapon vs resale competition)

**Where to look for state:**
- Live snapshot data + checklist + comps + events: `/house` dashboard at `https://ajays-macbook-pro.tailb3dc79.ts.net/house` (owner-only)
- API endpoints: `GET /house/dashboard` returns config + latest snapshot + history + comps + events + auto-generated playbook
- Mongo collections: `house_config`, `house_snapshots`, `house_comps`, `house_events`

**Suggested first move when they open the next chat:**
1. Ask for the latest dashboard numbers (saves / tours / showings) so recommendations are grounded in the current state, not stale data.
2. If they ask for help, default to giving them paste-ready text or a 5-line action list. Resist the urge to explain.

**The single highest-leverage observation in this whole plan:** the MLS bath/bed correction. If that propagates and saves still don't move within 7-10 days, the next lever is the description rewrite. If that also doesn't move it, then pricing.

---


## 1. Property facts (the truth, not what MLS says)

| Field | Value |
|---|---|
| Address | 4505 Sovereignty Dr, McKinney, TX 75070 |
| Subdivision | Lake Forest |
| **Beds / Baths** | **5 bed / 4 bath**  ← MLS currently shows 4/3 — both wrong |
| Sqft | 2,764 |
| Lot | 4,835 sqft (~0.11 acre) |
| Year built | 2024 (brand-new) |
| Property type | Single Family Residence |
| MLS # | 21154375 |
| List price | $683,000 ($247/sqft) |
| Zestimate | $665,100 (list is +2.7% over) |
| HOA | $73/mo |
| School district | **McKinney ISD** — Glen Oaks Elementary → Dowell Middle → McKinney Boyd HS (A-rated) |
| Listed | early May 2026 |
| Price history | Initial $698K → $683K (-$15K, -2.1%) on 5/5 |
| Builder warranty | 10-yr structural / 2-yr systems — transfers to buyer |

**Listing URL:** https://www.redfin.com/TX/McKinney/4505-Sovereignty-Dr-75070/home/187708948

---

## 2. The single highest-ROI action: Fix the MLS bath/bed count

The MLS field shows **4 bed / 3 bath**. Reality is **5 bed / 4 bath**. This means buyers filtering "5+ beds" or "4+ baths" on Redfin/Zillow/Realtor.com **never see this listing** — that's roughly 30% of the target buyer pool invisible.

**Action:** Agent submits MLS correction. Status: ✅ informed agent.

The MLS feed propagates to Redfin / Zillow / Realtor in 24-48 hours after correction.

---

## 3. Listing description (final, plain text — paste into MLS)

```
Brand-new 2024 build in Lake Forest — 5 bed, 4 bath, 2,764 sq ft. McKinney ISD: Glen Oaks → Dowell → McKinney Boyd (A-rated). Move-in ready with builder warranty transferring to buyer.

Step out your door to a 2.5-mile radius most McKinney addresses can't match: Walmart Supercenter steps away, Costco 5 min, Market Street 1.7 mi, Allen Premium Outlets (120+ stores) 2.5 mi, The Village at Allen and Fairview Town Center 3 mi for dining (Cheesecake Factory, P.F. Chang's) and Cinemark Allen for movies.

EōS Fitness Signature opens adjacent — pool, recovery suite, outdoor Backyard training. Life Time McKinney athletic resort 2.2 mi.

Sam Rayburn Tollway at the doorstep — 12 min Toyota HQ Plano, 15 min Legacy West, 25 min DFW airport. Historic downtown McKinney and Adriatica Village in 10.

Inside: flexible 5-bedroom layout — ground-floor bedroom + ensuite works as guest suite, home office, or in-law space. Four bedrooms upstairs plus a game room / media flex. Engineered hardwood through the main floor.

Kitchen: Level 6 quartz countertops, built-in stainless appliances, Shaker cabinetry, oversized island.

Owner's suite: spa bath, dual vanities, frameless glass shower, walk-in closet.

Already done: window treatments throughout, full sod + sprinkler, fenced yard, garage epoxy, smart-home package (thermostat, doorbell, locks). $73/mo HOA. Builder warranty: 10-yr structural / 2-yr systems.
```

---

## 4. "What's Special" tags (replace all existing on Redfin/Zillow)

```
2024 New Construction
McKinney ISD — Boyd HS (A-rated)
5 bed / 4 bath
Walk to Walmart · 5 min to Costco
Cinemark Allen + Allen Premium Outlets 2.5 mi
EōS Fitness Signature opening adjacent
Life Time McKinney 2.2 mi
12 min to Toyota HQ Plano
Builder warranty transfers
```

These tags drive **search-filter visibility**, not just feel. Buyers filter by these on Redfin/Zillow — if you don't have a tag, you don't appear when buyers filter for it.

---

## 5. Pricing decision tree

```
Day 0–14 (current window):
   Hold $683K. Ship the bath fix + new description + outreach.
   Recovery window for the 30% of buyers previously invisible to.

Day 15–21 if no strong offer:
   Drop to $674,900 (psychological under $675K).
   Refreshes Redfin/Zillow "Just reduced" badge — bumps top of saved-search emails.

Day 22–28 if still nothing:
   Drop to $664,900 (matches Zestimate exactly — comparable demand zone).

Day 29+:
   Strategic pivot — three options:
   (a) $10K rate buy-down credit instead of price cut
       (keeps comp price up, helps buyer monthly payment)
   (b) Withdraw + relist fresh in 60 days (DOM resets)
   (c) Rent it (DFW rents ~$3.2-3.5K/mo for this profile —
       covers mortgage; re-list spring 2027)
```

**Don't cut twice in a row.** The 5/5 cut is currently driving Zillow saves via "Price improved" badge — burning that with another immediate cut wastes the signal. Hold $683K for 10–14 days post bath fix.

---

## 6. Organic outreach playbook

Ranked by realistic impact. Many overlap with what agents do — these are the things **owners can do that agents typically don't**.

### Highest-ROI moves

| Channel | Effort | Action |
|---|---|---|
| **Door-knock 30 immediate neighbors** | 2 hours, Saturday | Knock with open-house flyer: *"Hi, I'm selling 4505 — know anyone who'd love to be your neighbor?"* Highest-conversion organic channel that exists. |
| **LinkedIn personal post** | 10 min | *"Selling our McKinney home — 5bd/4ba/2764sqft 2024 build, McKinney ISD, 12 min to Toyota HQ Plano. DM if you know anyone relocating to DFW."* + 3 photos. Your network = corporate buyers. |
| **Corporate relo HR teams** | 30 min | Email 3-line note + listing link to HR/relo at: **Toyota North America HQ Plano**, **Liberty Mutual Plano**, **JPMorgan Plano**, **FedEx Frisco**, **Keurig Dr Pepper Frisco**. Relo packages close in 30 days. |
| **Nextdoor — Lake Forest + adjacent neighborhoods** | 5 min | Post photos + open house date in Lake Forest feed AND adjacent Stonebridge/Eldorado/Crestmont feeds. |
| **Facebook groups** | 15 min | Cross-post: *"McKinney TX Buy/Sell/Trade"*, *"DFW Relocators"*, *"Frisco/McKinney Living"*, *"Toyota Plano Newcomers"*. |

### Medium-ROI

| Channel | Action |
|---|---|
| **r/McKinneyTX, r/Dallas** | Post once: *"Selling our 2024 build in Lake Forest — open this Saturday"* |
| **School-pickup-line flyer** | Print 50 simple flyers, hand out at Glen Oaks Elementary pickup for one week. Hits parents wanting to move *into* the school zone. |
| **Yard sign with QR code** | Replace generic agent sign with QR → one-page Notion site (photos, video, $/sqft, "request showing" button). Walk-by traffic converts ~3%. |
| **Drone reel for IG/TikTok/YouTube Shorts** | 30-second drone-out + interior walkthrough. Tag #mckinneytx #frisco #dfwhomes #lakeforestmckinney. McKinney/Frisco hashtags have low creator density = organic reach. |
| **Mortgage broker outreach** | Email 5–10 local brokers. They have pre-approved buyers actively looking. *"Closed on a 2024 5bd/4ba in Lake Forest. $683K. Open to 5% buy-down credit. Anyone in your funnel match?"* |
| **Reverse-prospect Zillow saves** | Ask agent to use Zillow Premier Agent system to pull people who saved comparable Lake Forest listings in last 14 days, send them yours. ~5x conversion vs cold buyer's-agent emails. |
| **Corporate relocation agent partners** | Email a one-pager to one DFW relo agent at each of: **Cartus, Sirva, BGRS, Weichert Workforce Mobility**. Three replies = next 30 days of activity. |

### Open house — the real move

Open houses for 2024 builds in McKinney still draw 15-30 visitors when promoted. Pre-market Friday:
- Sandwich-board sign at Lake Forest entrance (HOA permission)
- Nextdoor + FB groups Thursday evening
- $50 broker-open listing on Compass/Coldwell open-house calendar
- Free coffee + breakfast tacos = doubles foot traffic in DFW

---

## 7. Differentiation against new construction

Real competition isn't other resales — it's KB / Lennar / David Weekley still building in McKinney/Frisco offering buyer incentives (rate buy-downs, $15-20K closing credits). Counter-message:

- **"Move-in ready — no 6-month build wait"**
- **"$XX,000+ in finished upgrades vs builder base"** (window treatments, blinds, appliances, fence, landscape, garage epoxy, smart-home)
- **"Mature settled lot"** (vs builder mud)
- **"HOA only $73/mo"** (most new builds are $100-150)
- **"Active builder warranty transfers — 10yr structural / 2yr systems"** (counters "but it's resale" objection)

---

## 8. Daily monitoring routine

Three numbers, in order, every morning:

1. **Save count delta on Zillow** (yesterday vs today) — leading indicator
2. **Tour requests on Redfin** — direct buy signal
3. **Showings scheduled by agent** — closes the loop

**Read the signal:**
- Saves climbing but no tours → photo / description problem
- Saves flat AND no tours → price problem
- Tours but no offers → in-house friction (smell, layout, road noise) — ask agent for showing feedback

The dashboard `/house` tracks all of this with a 14-day timeline.

---

## 9. Bonus angles (not yet shipped)

- **Pre-listing inspection report** — Pay $400 for a full inspection, post on listing as *"Inspection report available — already complete."* Listings with this close 8-12 days faster on average.
- **Rate buy-down instead of price cut** — When time comes for next cut, offer **"$10,000 buyer rate buy-down"** instead of $10K off price. Comp price stays high, buyer's monthly payment improves. Same dollars, better optics.
- **Builder warranty transfer disclosure** — actively call out in description (✅ already in the rewrite)
- **3D Matterport tour** — $200-400 add-on. Specifically helps relo buyers who can't fly in. Massive engagement bump.
- **Video walkthrough** — if not already on listing, $300-500 to add. Zillow data: video listings get 2-3× engagement.
- **Twilight exterior photos** — only ~20% of McKinney listings have it. Doubles click-through rate.

---

## 10. Status checklist

### Already done
- [x] House dashboard built at `/house`, owner-gated to ajay + vineetha
- [x] Daily snapshot cron at 8am ET captures view/save counts
- [x] Best-effort Redfin/Zillow/Realtor scraper wired
- [x] Config pre-populated from Redfin scrape
- [x] Initial price reduction logged in events ($698K → $683K, 5/5)
- [x] Agent informed of the bath/bed correction + new description + tags

### Pending agent
- [ ] MLS correction submitted (5 bed / 4 bath)
- [ ] New description published on MLS
- [ ] "What's Special" tags replaced on Redfin and Zillow

### Pending owner
- [ ] LinkedIn personal post
- [ ] Nextdoor + FB group cross-post
- [ ] Corporate relo HR cold-emails (Toyota, Liberty Mutual, JPMorgan, KDP)
- [ ] Open house Saturday — flyers + sandwich board + breakfast tacos
- [ ] Door-knock 30 neighbors Saturday afternoon
- [ ] r/McKinneyTX post
- [ ] (Optional) Pre-listing inspection ordered
- [ ] (Optional) Drone reel + 3D Matterport scheduled

---

## 11. References

- **Listing URL:** https://www.redfin.com/TX/McKinney/4505-Sovereignty-Dr-75070/home/187708948
- **Dashboard:** `/house` on the Pounce app (owner-only)
- **MLS #:** 21154375
- **Pricing floor:** $664,900 (Zestimate match) — anything below is leaving money
- **DFW rent profile:** ~$3,200-3,500/mo for comparable 5bd/4ba — covers mortgage, fallback option

---

*This plan was generated 2026-05-07 in conversation with the Pounce app's house module. Update timestamp + status checklist as items ship.*
