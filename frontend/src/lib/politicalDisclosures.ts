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
  /** Source note from the original table — appears in the tooltip. */
  notes?: string;
  /** When the list-row was last verified or sourced (informational). */
  asOf?: string;
};

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

/** Convenience — returns one boolean per chip the card should render. */
export function getPoliticalChipFlags(ticker: string): {
  hasPotusFamily:    boolean;
  hasGovtInvestment: boolean;
  hasGovtContractor: boolean;
  isInferred:        boolean;
  entry:             DisclosureEntry | null;
} {
  const e = getPoliticalDisclosure(ticker);
  if (!e) {
    return {
      hasPotusFamily:    false,
      hasGovtInvestment: false,
      hasGovtContractor: false,
      isInferred:        false,
      entry:             null,
    };
  }
  return {
    hasPotusFamily:    e.categories.includes('potus_family'),
    hasGovtInvestment: e.categories.includes('govt_investment'),
    hasGovtContractor: e.categories.includes('govt_contractor'),
    isInferred:        e.categories.includes('inferred'),
    entry:             e,
  };
}

export const POLITICAL_DISCLOSURE_SOURCE_NOTE = SOURCE_NOTE;
export const POLITICAL_DISCLOSURE_TOTAL_COUNT = ENTRIES.length;
