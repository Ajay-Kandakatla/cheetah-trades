/**
 * politicalDisclosures.ts — curated list of stocks with disclosed
 * positions held by public officials / their immediate family AND
 * stocks with direct U.S. government involvement (equity stakes,
 * major contracts, eligible-asset designations).
 *
 * Added 2026-05-28 per user request: surface a chip when "Trump or
 * U.S. government investments go into a stock". The user provided the
 * seed list as a table of disclosed bands ($1M-$5M etc), with a
 * subset of inferred / scan-classified rows at the bottom.
 *
 * ───────────────────────────────────────────────────────────────────
 * IMPORTANT — this is INFORMATIONAL, not a buy or sell signal.
 *
 * Disclosed positions don't predict outcomes. The chip flags context
 * the user wants to be aware of when evaluating a name; it does not
 * imply the disclosure caused performance or that the official's
 * family has private information. Cross-reference with Minervini gates
 * + volume + whales before any allocation decision.
 *
 * Sources (per user 2026-05-28):
 *   1. U.S. Office of Government Ethics public disclosures (OGE.gov)
 *   2. Reputable news-aggregation reporting (NYT, Bloomberg, WSJ)
 *
 * Maintenance: edit the entries below to add/remove tickers. Match is
 * case-insensitive on the ticker string. Confidence levels:
 *   - 'disclosed' — directly reported in OGE form / news coverage
 *   - 'inferred'  — scan-classified subset; not directly disclosed,
 *                   softer chip treatment
 */

/** Category of political signal. Multiple categories can apply to one
 *  ticker — e.g. INTC has both family-disclosed AND govt-investment
 *  context, so it renders both chips. */
export type DisclosureCategory =
  | 'potus_family'       // POTUS or immediate family disclosed position
  | 'govt_investment'    // U.S. govt holds equity / CHIPS Act / Treasury
  | 'govt_contractor'    // major govt contractor or program participant
  | 'inferred';          // scan-classified — not directly disclosed

export type DisclosureEntry = {
  ticker:    string;
  company:   string;
  sector:    string;
  /** One or more categories. Drives which chip(s) render. */
  categories: DisclosureCategory[];
  /** Disclosed value band when known (e.g. "$1M-$5M"). null when the
   *  source named the position but didn't include a band. */
  disclosureBand?: string | null;
  /** For 'govt_investment' rows ONLY: the holder and the size of the
   *  government's EQUITY position, in the form "<agency> <pct>" (e.g.
   *  "DoD 15%"). Renders on the 🇺🇸 chip so the size is readable without
   *  opening the drill. Added 2026-09-19 — the 2025-26 critical-minerals
   *  wave is the first time the size varies enough to matter; before it,
   *  every govt row was CHIPS-Act-shaped and the chip said enough.
   *
   *  A row without a NAMED agency and a STATED percentage leaves this
   *  null and does not get to imply one. "The administration is weighing
   *  a stake" is not a stake. */
  govtStake?: string | null;
  /** Source note from the original table — appears in the tooltip. */
  notes?: string;
  /** When the list-row was last verified or sourced (informational). */
  asOf?: string;
  /** ISO date this row was ADDED to the list. Drives the 🆕 highlight so a
   *  name that arrived this week is distinguishable from one that has sat
   *  here since the seed list. Omitted on the 2026-05-28 seed rows. */
  addedOn?: string;
};

/** How long a row keeps its 🆕 highlight after `addedOn`. Fourteen days —
 *  long enough that a name added on a Friday is still flagged the
 *  following weekend, short enough that the highlight means something. */
export const NEW_DISCLOSURE_DAYS = 14;

/** Seed list compiled 2026-05-28 from user-supplied table. To add /
 *  remove a ticker, edit this array directly. Ordering doesn't matter
 *  — lookups are O(1) via the map built below. */
const ENTRIES: DisclosureEntry[] = [
  // ── Disclosed POTUS-family positions with explicit bands ───────────
  { ticker: 'NVDA',  company: 'Nvidia',                     sector: 'Semiconductors',         categories: ['potus_family'],                       disclosureBand: '$1M–$5M',         notes: 'Est. $1.8M–$6.6M total; timing overlapped chip-deal news' },
  { ticker: 'MSFT',  company: 'Microsoft',                  sector: 'Big Tech / Software',    categories: ['potus_family'],                       disclosureBand: '$1M–$5M',         notes: 'Est. $2.4M–$8.1M; also large sales same period' },
  { ticker: 'AVGO',  company: 'Broadcom',                   sector: 'Semiconductors',         categories: ['potus_family'],                       disclosureBand: '$1M–$5M',         notes: 'New / added semiconductor position' },
  { ticker: 'AMZN',  company: 'Amazon',                     sector: 'Big Tech / E-commerce',  categories: ['potus_family'],                       disclosureBand: '$1M–$5M',         notes: 'Est. $2.5M–$8.3M; also large sales same period' },
  { ticker: 'AAPL',  company: 'Apple',                      sector: 'Big Tech / Hardware',    categories: ['potus_family'],                       disclosureBand: '$1M–$5M' },
  { ticker: 'ORCL',  company: 'Oracle',                     sector: 'Software',               categories: ['potus_family'],                       disclosureBand: '$1M–$5M',         notes: 'Est. $2.2M–$10.6M total' },
  { ticker: 'DELL',  company: 'Dell Technologies',          sector: 'Hardware',               categories: ['potus_family'],                       disclosureBand: '$1M–$5M',         notes: 'New position preceded a public endorsement' },
  { ticker: 'ADBE',  company: 'Adobe',                      sector: 'Software',               categories: ['potus_family'],                       disclosureBand: '$1M–$5M' },
  { ticker: 'TXN',   company: 'Texas Instruments',          sector: 'Semiconductors',         categories: ['potus_family'],                       disclosureBand: '$1M–$5M' },
  { ticker: 'MSI',   company: 'Motorola Solutions',         sector: 'Communications',         categories: ['potus_family'],                       disclosureBand: '$1M–$5M' },
  { ticker: 'NOW',   company: 'ServiceNow',                 sector: 'Software',               categories: ['potus_family'],                       disclosureBand: '$1M–$5M',         notes: 'Listed as SRVC in source; correct ticker is NOW' },
  { ticker: 'META',  company: 'Meta Platforms',             sector: 'Big Tech',               categories: ['potus_family'],                       disclosureBand: '$1,001–$500K (buys)', notes: 'Net seller; small buys alongside large sales' },
  { ticker: 'AMD',   company: 'Advanced Micro Devices',     sector: 'Semiconductors',         categories: ['potus_family'],                       disclosureBand: '$500K–$1M',       notes: 'Reportedly 100%+ profit on later marks' },
  { ticker: 'GS',    company: 'Goldman Sachs',              sector: 'Financials',             categories: ['potus_family'],                       disclosureBand: '$500K–$1M',       notes: 'Overlaps deregulatory posture' },
  { ticker: 'GOOGL', company: 'Alphabet',                   sector: 'Big Tech',               categories: ['potus_family'],                       disclosureBand: '$500K–$1M' },
  { ticker: 'ABNB',  company: 'Airbnb',                     sector: 'Consumer / Travel',      categories: ['potus_family'],                       disclosureBand: '$500K–$1M' },
  { ticker: 'DASH',  company: 'DoorDash',                   sector: 'Consumer',               categories: ['potus_family'],                       disclosureBand: '$500K–$1M' },
  { ticker: 'MU',    company: 'Micron',                     sector: 'Semiconductors',         categories: ['potus_family'],                       disclosureBand: '$500K–$1M' },
  { ticker: 'BE',    company: 'Bloom Energy',               sector: 'Clean Energy',           categories: ['potus_family'],                       disclosureBand: '$500K–$1M',       notes: 'Reportedly 100%+ profit on later marks' },

  // ── Disclosed family positions, no band on file ────────────────────
  { ticker: 'BAC',   company: 'Bank of America',            sector: 'Financials',             categories: ['potus_family'],                       disclosureBand: null,              notes: 'Listed among purchases' },
  { ticker: 'PG',    company: 'Procter & Gamble',           sector: 'Consumer Staples',       categories: ['potus_family'],                       disclosureBand: null,              notes: 'Listed among purchases' },
  { ticker: 'BA',    company: 'Boeing',                     sector: 'Industrials / Defense',  categories: ['potus_family'],                       disclosureBand: null,              notes: 'Listed among purchases' },
  { ticker: 'LLY',   company: 'Eli Lilly',                  sector: 'Pharma / GLP-1',         categories: ['potus_family'],                       disclosureBand: null,              notes: 'Anti-obesity drug exposure' },
  { ticker: 'COIN',  company: 'Coinbase',                   sector: 'Crypto',                 categories: ['potus_family'],                       disclosureBand: null,              notes: 'Pro-crypto policy window' },
  { ticker: 'SOFI',  company: 'SoFi',                       sector: 'Fintech',                categories: ['potus_family'],                       disclosureBand: null },
  { ticker: 'WMT',   company: 'Walmart',                    sector: 'Consumer Staples',       categories: ['potus_family'],                       disclosureBand: null },
  { ticker: 'INTU',  company: 'Intuit',                     sector: 'Software',               categories: ['potus_family'],                       disclosureBand: null },
  { ticker: 'WDAY',  company: 'Workday',                    sector: 'Software',               categories: ['potus_family'],                       disclosureBand: null },

  // ── Multi-category: family + govt-investment / contractor ──────────
  { ticker: 'INTC',  company: 'Intel',                      sector: 'Semiconductors',         categories: ['potus_family', 'govt_investment'],    disclosureBand: '$500K–$1M',       notes: 'Increased holdings followed U.S. govt investment (CHIPS Act)' },
  { ticker: 'PLTR',  company: 'Palantir',                   sector: 'Software / Defense',     categories: ['potus_family', 'govt_contractor'],    disclosureBand: '~$260K (Q1 cum.)', notes: 'Govt contractor' },
  { ticker: 'HOOD',  company: 'Robinhood',                  sector: 'Fintech',                categories: ['potus_family', 'govt_contractor'],    disclosureBand: null,              notes: "Initial trustee of 'Trump Accounts' program" },

  // ── Inferred / scan-classified subset (softer chip) ────────────────
  { ticker: 'QBTS',  company: 'D-Wave Quantum',             sector: 'Quantum / Speculative',  categories: ['inferred'],                            disclosureBand: null,              notes: 'Scan-classified subset — not directly disclosed' },
  { ticker: 'RGTI',  company: 'Rigetti Computing',          sector: 'Quantum / Speculative',  categories: ['inferred'],                            disclosureBand: null,              notes: 'Scan-classified subset — not directly disclosed' },
  { ticker: 'INFQ',  company: 'Infleqtion',                 sector: 'Quantum / Speculative',  categories: ['inferred'],                            disclosureBand: null,              notes: 'Scan-classified subset — not directly disclosed' },
  { ticker: 'NN',    company: 'NextNav',                    sector: 'Communications',         categories: ['inferred'],                            disclosureBand: null,              notes: 'Scan-classified subset — not directly disclosed' },
  { ticker: 'PLUG',  company: 'Plug Power',                 sector: 'Clean Energy',           categories: ['inferred'],                            disclosureBand: null,              notes: 'Scan-classified subset — not directly disclosed' },

  // ── The 2025-26 CRITICAL-MINERALS WAVE (added 2026-09-19) ───────────
  //
  // Ajay 2026-09-19: *"Show me POTUS tickers there are some new ones like
  // Green Land eneregy or something"* — his name was GLND, and chasing it
  // surfaced that the seed list above stops at 2026-05-28 and missed the
  // entire wave in which the U.S. government stopped subsidising companies
  // and started OWNING them. Public trackers (CSIS, CFR) count ~39 federal
  // direct-ownership deals worth ~$27.7B announced since January 2025; the
  // seed list carries exactly one of them (INTC).
  //
  // These five are separated from the three below ON PURPOSE. A signed
  // equity stake and a stock that merely rallied on an Arctic headline are
  // not the same fact, and the entire value of this file is that the chip
  // means something when it renders.
  { ticker: 'MP',    company: 'MP Materials',             sector: 'Rare Earths / Materials', categories: ['govt_investment'], disclosureBand: null, govtStake: 'DoD 15%',
    notes: 'Department of Defense holds ~15% and is the largest shareholder \u2014 the deal that set the template for everything below it.',
    asOf: '2026-09-19', addedOn: '2026-09-19' },
  { ticker: 'USAR',  company: 'USA Rare Earth',           sector: 'Rare Earths / Materials', categories: ['govt_investment'], disclosureBand: null, govtStake: 'Commerce 10%',
    notes: '$1.6B debt-and-equity package from the Department of Commerce for ~10% (announced Jan 2026), funding a domestic mine and magnet facility.',
    asOf: '2026-09-19', addedOn: '2026-09-19' },
  { ticker: 'LAC',   company: 'Lithium Americas',         sector: 'Lithium / Materials',     categories: ['govt_investment'], disclosureBand: null, govtStake: 'DOE 5%',
    notes: 'Energy Department took ~5% while renegotiating the Biden-era $2.3B loan for the processing facility beside Thacker Pass, Nevada.',
    asOf: '2026-09-19', addedOn: '2026-09-19' },
  { ticker: 'TMQ',   company: 'Trilogy Metals',           sector: 'Copper / Materials',      categories: ['govt_investment'], disclosureBand: null, govtStake: 'Federal 10%',
    notes: '$35.6M federal investment for ~10%, to secure access to critical-mineral projects in Alaska.',
    asOf: '2026-09-19', addedOn: '2026-09-19' },
  { ticker: 'ALOY',  company: 'REalloys',                 sector: 'Rare Earths / Materials', categories: ['govt_contractor'], disclosureBand: null, govtStake: null,
    notes: 'NOT an equity stake. The U.S. Army selected REalloys to build and operate the first commercial critical-minerals processing and metallization facility on a U.S. military base (Euclid, Ohio). Also holds an offtake for 15% of phase-one output from Critical Metals\u2019 Tanbreez project.',
    asOf: '2026-09-19', addedOn: '2026-09-19' },

  // ── The GREENLAND HEADLINE COHORT — no government agreement ─────────
  //
  // These three are on the list so the chip can say "we looked, and there
  // is no deal". Each rallied when the administration renewed its Arctic
  // push; none has a stated U.S. government agreement. Filing one of them
  // as 'govt_investment' would be the exact failure the split above exists
  // to prevent — 'inferred' renders the softer dashed chip instead.
  { ticker: 'CRML',  company: 'Critical Metals Corp',     sector: 'Rare Earths / Materials', categories: ['inferred'], disclosureBand: null, govtStake: null,
    notes: 'Holds 92.5% of the Tanbreez rare-earth project in southern Greenland. The administration was REPORTED (Oct 2025) to be weighing an equity stake \u2014 reported interest, never a signed deal. Promote to govt_investment only once an agency AND a percentage are actually named.',
    asOf: '2026-09-19', addedOn: '2026-09-19' },
  { ticker: 'GLND',  company: 'Greenland Energy Company', sector: 'Arctic Energy',           categories: ['inferred'], disclosureBand: null, govtStake: null,
    notes: 'Ajay\u2019s "Green Land energy". Exclusive exploration rights to ~2M acres in the Jameson Land Basin, eastern Greenland, drilling with Halliburton. NO U.S. government agreement of any kind \u2014 it moves on the Arctic policy headline, which is a different thing from being invested in.',
    asOf: '2026-09-19', addedOn: '2026-09-19' },
  { ticker: 'UUUU',  company: 'Energy Fuels',             sector: 'Uranium / Rare Earths',   categories: ['inferred'], disclosureBand: null, govtStake: null,
    notes: 'No Greenland asset and no stated government deal; grouped with the Greenland trade for expanding domestic rare-earth processing. Headline relevance only.',
    asOf: '2026-09-19', addedOn: '2026-09-19' },
];

const SOURCE_NOTE =
  'Sources: U.S. Office of Government Ethics public disclosures (OGE.gov) + ' +
  'reputable news reporting (NYT, Bloomberg, WSJ). User-curated 2026-05-28. ' +
  'Edit src/lib/politicalDisclosures.ts to update.';

/** Lazy-built lookup map — ticker (uppercase) → entry. */
let _map: Map<string, DisclosureEntry> | null = null;
function getMap(): Map<string, DisclosureEntry> {
  if (_map) return _map;
  _map = new Map();
  for (const e of ENTRIES) _map.set(e.ticker.toUpperCase(), e);
  return _map;
}

export function getPoliticalDisclosure(ticker: string): DisclosureEntry | null {
  if (!ticker) return null;
  return getMap().get(ticker.toUpperCase()) ?? null;
}

/** True when `addedOn` is within NEW_DISCLOSURE_DAYS of `now`.
 *
 *  `now` is injectable so the tests pin a date instead of drifting into a
 *  pass-by-calendar — a 14-day window tested against the real clock goes
 *  green for two weeks and then silently red forever.
 *
 *  A row with no `addedOn` (every seed row) is never new. An unparseable or
 *  FUTURE date is never new either: a typo must not mint a highlight.
 */
export function isNewDisclosure(e: DisclosureEntry | null,
                                now: Date = new Date()): boolean {
  if (!e?.addedOn) return false;
  const added = Date.parse(`${e.addedOn}T00:00:00Z`);
  if (!Number.isFinite(added)) return false;
  const ageDays = (now.getTime() - added) / 86_400_000;
  if (ageDays < 0) return false;
  return ageDays <= NEW_DISCLOSURE_DAYS;
}

/** Convenience — returns one boolean per chip the card should render. */
export function getPoliticalChipFlags(ticker: string, now?: Date): {
  hasPotusFamily:    boolean;
  hasGovtInvestment: boolean;
  hasGovtContractor: boolean;
  isInferred:        boolean;
  /** Added 2026-09-19 — drives the 🆕 highlight. */
  isNew:             boolean;
  entry:             DisclosureEntry | null;
} {
  const e = getPoliticalDisclosure(ticker);
  if (!e) {
    return {
      hasPotusFamily:    false,
      hasGovtInvestment: false,
      hasGovtContractor: false,
      isInferred:        false,
      isNew:             false,
      entry:             null,
    };
  }
  return {
    hasPotusFamily:    e.categories.includes('potus_family'),
    hasGovtInvestment: e.categories.includes('govt_investment'),
    hasGovtContractor: e.categories.includes('govt_contractor'),
    isInferred:        e.categories.includes('inferred'),
    isNew:             isNewDisclosure(e, now),
    entry:             e,
  };
}

/** Every row added within the window, newest first — the "what's new"
 *  read for a page that wants to highlight the arrivals rather than test
 *  one ticker at a time. */
export function recentDisclosures(now: Date = new Date()): DisclosureEntry[] {
  return ENTRIES
    .filter((e) => isNewDisclosure(e, now))
    .sort((a, b) => (b.addedOn || '').localeCompare(a.addedOn || ''));
}

export const POLITICAL_DISCLOSURE_SOURCE_NOTE = SOURCE_NOTE;
export const POLITICAL_DISCLOSURE_TOTAL_COUNT = ENTRIES.length;
