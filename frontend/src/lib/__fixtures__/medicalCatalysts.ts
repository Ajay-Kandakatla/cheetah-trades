/* 🧬 Medical catalysts — HAND-WRITTEN fixture in the spec §3.10 shape.
 *
 * Rows: KOD (DAYBREAK Phase 3 positive, 2026-09-28), MIRM (FDA approval +
 * AZURE-1 Phase 3 on the same session — two events, one observation), MNOV
 * (topline, direction not stated, $0.1M/day), HUMA ($0.56 prior close),
 * Elevar (issuer unresolved — Massive tagged RLAY, never attributed) and MRNA
 * (ESMO data, upcoming). Prices are the §1.6 prod frame numbers.
 *
 * The main session REPLACES this with the real captured payload
 * (GET /catalysts/medical?days=7 and /catalysts/medical/KOD, spec §5 step 3)
 * and re-runs the MedicalCatalysts / MedicalEventsPanel tests on it.
 */
import type { MedBoard, MedEventRow, MedSymbolPayload } from '../medicalCatalysts';

export const UNMEASURED_NOTE =
  'UNMEASURED — nothing here has been measured. Events are classified by fixed word rules; '
  + 'moves are what the stock did, not a prediction. Setup: pending study. Not a buy or sell signal.';

const LABELS = { measured: false, status: 'unmeasured', setup: 'pending study', note: UNMEASURED_NOTE };

const links = (t: string) => ({ supply: `/sepa/${t}?tab=supply`, timeline: `/sepa/${t}?tab=catalyst` });

export const KOD_ROW: MedEventRow = {
  event_key: 'KOD|topline_positive|2026-09-28',
  ticker: 'KOD', company: 'Kodiak Sciences Inc.',
  event_type: 'topline', family: 'trial', type_dir: 'topline_positive',
  label: 'Phase 3 topline positive', subtype: null, direction: 'positive', phase: '3',
  regulator: null, trials: ['DAYBREAK'], impact: 'high',
  modality: ['antibody_bispecific'], modality_primary: 'antibody_bispecific',
  areas: ['ophthalmology'], area_primary: 'ophthalmology',
  headline: 'Kodiak Sciences Announces Positive Topline Results From Phase 3 DAYBREAK Study; Both Primary Endpoints Met',
  published_at_et: '2026-09-28T02:34:00-04:00', first_seen_at_et: '2026-09-28T04:05:31-04:00',
  latency_min: 91.5, session_date: '2026-09-28', released: 'premarket',
  sources: [
    { provider: 'finnhub', source: 'Benzinga', title: 'Kodiak Sciences Announces Positive Topline Results From Phase 3 DAYBREAK Study',
      url: 'https://www.benzinga.com/news/26/09/kodiak-daybreak', published_et: '2026-09-28T02:34:00-04:00' },
    { provider: 'sec', source: 'SEC 8-K EX-99.1', title: 'Kodiak Sciences Inc. 8-K (items 8.01, 9.01)',
      url: 'https://www.sec.gov/Archives/edgar/data/1468748/000146874826000050/0001468748-26-000050-index.htm', published_et: '2026-09-28T08:53:56-04:00' },
    { provider: 'finnhub', source: 'Yahoo', title: 'Kodiak Sciences Shares Rise After DAYBREAK Phase 3 Trial Results',
      url: 'https://finance.yahoo.com/news/kodiak-daybreak', published_et: '2026-09-28T06:30:00-04:00' },
  ],
  n_sources: 3,
  push: { state: 'pushed', reason: null, at_et: '2026-09-28T04:05:40-04:00' },
  reaction: {
    at_detection: { as_of: '2026-09-28T04:05:31-04:00', session: 'premarket', price: 55.64, base_close: 32.35,
      base_basis: 'frame', move_pct: 72.0, volume_so_far: 412_000, rvol_so_far: null, latency_min: 91.5, post_session: false },
    at_close: { open: 71.2, high: 94.5, low: 68.1, close: 89.92, volume: 38_360_000, gap_pct: 120.1, day_pct: 178.0,
      rvol: 57.1, dollar_volume: 3_449_331_200, close_loc: 0.83, basis: 'closed_bar' },
    fwd: { ret_5d_pct: null, ret_21d_pct: null, drift_5d_pct: null, matured_5d: false, matured_21d: false },
  },
  liquidity: { base_close: 32.35, base_basis: 'frame', adv50_usd: 22_700_000, avg_vol50: 672_000,
    pre_ret_20d_pct: 4.1, market_cap: 1_710_000_000 },
  dilutive: null, links: links('KOD'),
};

const MIRM_APPROVAL: MedEventRow = {
  event_key: 'MIRM|fda_approval|2026-09-28',
  ticker: 'MIRM', company: 'Mirum Pharmaceuticals, Inc.',
  event_type: 'fda_approval', family: 'fda', type_dir: 'fda_approval',
  label: 'FDA approval', subtype: 'approval', direction: 'positive', phase: null, regulator: 'FDA',
  trials: [], impact: 'high',
  modality: ['small_molecule'], modality_primary: 'small_molecule',
  areas: ['rare_disease'], area_primary: 'rare_disease',
  headline: 'Mirum Pharmaceuticals Announces FDA Approval of Atebrioz',
  published_at_et: '2026-09-28T07:00:00-04:00', first_seen_at_et: '2026-09-28T07:05:12-04:00',
  latency_min: 5.2, session_date: '2026-09-28', released: 'premarket',
  sources: [{ provider: 'massive', source: 'GlobeNewswire', title: 'Mirum Pharmaceuticals Announces FDA Approval of Atebrioz',
    url: 'https://www.globenewswire.com/news-release/2026/09/28/mirum-atebrioz', published_et: '2026-09-28T07:00:00-04:00' }],
  n_sources: 1,
  push: { state: 'pushed', reason: null, at_et: '2026-09-28T07:05:20-04:00' },
  reaction: {
    at_detection: { as_of: '2026-09-28T07:05:12-04:00', session: 'premarket', price: 91.1, base_close: 89.7,
      base_basis: 'frame', move_pct: 1.6, volume_so_far: 8_000, rvol_so_far: null, latency_min: 5.2, post_session: false },
    at_close: { open: 90.5, high: 92.0, low: 86.9, close: 87.96, volume: 1_220_000, gap_pct: 0.9, day_pct: -1.9,
      rvol: 1.9, dollar_volume: 107_311_200, close_loc: 0.21, basis: 'closed_bar' },
    fwd: { ret_5d_pct: null, ret_21d_pct: null, drift_5d_pct: null, matured_5d: false, matured_21d: false },
  },
  liquidity: { base_close: 89.7, base_basis: 'frame', adv50_usd: 57_700_000, avg_vol50: 642_000, pre_ret_20d_pct: 2.3, market_cap: 4_400_000_000 },
  dilutive: null, links: links('MIRM'),
};

const MIRM_TOPLINE: MedEventRow = {
  ...MIRM_APPROVAL,
  event_key: 'MIRM|topline_positive|2026-09-28',
  event_type: 'topline', family: 'trial', type_dir: 'topline_positive',
  label: 'Phase 3 topline positive', subtype: null, phase: '3', regulator: null, trials: ['AZURE-1'],
  headline: 'Mirum Announces Positive Topline Results from Phase 3 AZURE-1 Study of Volixibat',
  published_at_et: '2026-09-28T07:01:00-04:00',
  push: { state: 'blocked:claimed_elsewhere', reason: 'claimed_elsewhere', at_et: null },
};

const MNOV_ROW: MedEventRow = {
  event_key: 'MNOV|topline_unknown|2026-09-28',
  ticker: 'MNOV', company: 'MediciNova, Inc.',
  event_type: 'topline', family: 'trial', type_dir: 'topline_unknown',
  label: 'Topline results (direction not stated)', subtype: null, direction: 'unknown', phase: null,
  regulator: null, trials: [], impact: 'low',
  modality: ['unclassified'], modality_primary: null, areas: ['unclassified'], area_primary: null,
  headline: 'MediciNova Announces Topline Results',
  published_at_et: '2026-09-28T08:00:00-04:00', first_seen_at_et: '2026-09-28T08:05:02-04:00',
  latency_min: 5.0, session_date: '2026-09-28', released: 'premarket',
  sources: [{ provider: 'massive', source: 'GlobeNewswire', title: 'MediciNova Announces Topline Results',
    url: 'https://www.globenewswire.com/news-release/2026/09/28/medicinova-topline', published_et: '2026-09-28T08:00:00-04:00' }],
  n_sources: 1,
  push: { state: 'not_eligible', reason: 'not_high_impact', at_et: null },
  reaction: {
    at_detection: { as_of: '2026-09-28T08:05:02-04:00', session: 'premarket', price: 2.4, base_close: 2.58,
      base_basis: 'frame', move_pct: -7.0, volume_so_far: 20_000, rvol_so_far: null, latency_min: 5.0, post_session: false },
    at_close: { open: 2.45, high: 2.5, low: 2.05, close: 2.1, volume: 230_000, gap_pct: -5.0, day_pct: -18.6,
      rvol: 4.8, dollar_volume: 483_000, close_loc: 0.11, basis: 'closed_bar' },
    fwd: null,
  },
  liquidity: { base_close: 2.58, base_basis: 'frame', adv50_usd: 100_000, avg_vol50: 48_000, pre_ret_20d_pct: -3.0, market_cap: 103_000_000 },
  dilutive: null, links: links('MNOV'),
};

const HUMA_ROW: MedEventRow = {
  event_key: 'HUMA|fda_approval|2026-09-28',
  ticker: 'HUMA', company: 'Humacyte, Inc.',
  event_type: 'fda_approval', family: 'fda', type_dir: 'fda_approval',
  label: 'FDA approval', subtype: 'approval', direction: 'positive', phase: null, regulator: 'FDA',
  trials: [], impact: 'high',
  modality: ['unclassified'], modality_primary: null, areas: ['unclassified'], area_primary: null,
  headline: 'Humacyte 8-K: FDA approval of supplemental application',
  published_at_et: '2026-09-28T16:10:00-04:00', first_seen_at_et: '2026-09-28T16:15:04-04:00',
  latency_min: 5.1, session_date: '2026-09-29', released: 'afterhours',
  sources: [{ provider: 'sec', source: 'SEC 8-K EX-99.1', title: 'Humacyte, Inc. 8-K',
    url: 'https://www.sec.gov/Archives/edgar/data/1818382/000181838226000077/0001818382-26-000077-index.htm', published_et: '2026-09-28T16:10:00-04:00' }],
  n_sources: 1,
  push: { state: 'blocked:blocked_price', reason: 'blocked_price', at_et: null },
  reaction: {
    at_detection: { as_of: '2026-09-28T16:15:04-04:00', session: 'afterhours', price: 0.56, base_close: 0.55,
      base_basis: 'snapshot_day_close', move_pct: 1.8, volume_so_far: 90_000, rvol_so_far: null, latency_min: 5.1, post_session: true },
    at_close: null, fwd: null,
  },
  liquidity: { base_close: 0.55, base_basis: 'snapshot_day_close', adv50_usd: 2_300_000, avg_vol50: 4_100_000, pre_ret_20d_pct: -12.0, market_cap: 88_000_000 },
  dilutive: null, links: links('HUMA'),
};

const ELEVAR_ROW: MedEventRow = {
  event_key: 'UNRESOLVED:elevar-therapeutics|fda_approval|2026-09-26',
  ticker: null, company: 'Elevar Therapeutics',
  event_type: 'fda_approval', family: 'fda', type_dir: 'fda_approval',
  label: 'FDA approval', subtype: 'approval', direction: 'positive', phase: null, regulator: 'FDA',
  trials: [], impact: 'high',
  modality: ['small_molecule'], modality_primary: 'small_molecule', areas: ['oncology'], area_primary: 'oncology',
  headline: 'Elevar Therapeutics Receives FDA Approval for Rivoceranib in Combination with Camrelizumab',
  published_at_et: '2026-09-26T09:00:00-04:00', first_seen_at_et: '2026-09-26T09:05:10-04:00',
  latency_min: 5.2, session_date: '2026-09-26', released: 'premarket',
  sources: [{ provider: 'massive', source: 'PR Newswire', title: 'Elevar Therapeutics Receives FDA Approval',
    url: 'https://www.prnewswire.com/news-releases/elevar-fda-approval', published_et: '2026-09-26T09:00:00-04:00' }],
  n_sources: 1,
  push: { state: 'not_eligible', reason: 'unresolved_ticker', at_et: null },
  reaction: null, liquidity: null, dilutive: null, links: null,
};

const MRNA_ROW: MedEventRow = {
  event_key: 'MRNA|conference_data|2026-09-24',
  ticker: 'MRNA', company: 'Moderna, Inc.',
  event_type: 'conference_data', family: 'conference', type_dir: 'conference_data',
  label: 'ESMO data (upcoming)', subtype: 'esmo', direction: 'unknown', phase: null, regulator: null,
  trials: [], impact: 'low',
  modality: ['mrna', 'vaccine'], modality_primary: 'mrna', areas: ['oncology'], area_primary: 'oncology',
  headline: 'Moderna to Present Individualized Neoantigen Therapy Data at ESMO 2026',
  published_at_et: '2026-09-24T07:30:00-04:00', first_seen_at_et: '2026-09-24T07:35:03-04:00',
  latency_min: 5.0, session_date: '2026-09-24', released: 'premarket',
  sources: [{ provider: 'finnhub', source: 'Business Wire', title: 'Moderna to Present Data at ESMO 2026',
    url: 'https://www.businesswire.com/news/home/moderna-esmo-2026', published_et: '2026-09-24T07:30:00-04:00' }],
  n_sources: 1,
  push: { state: 'not_eligible', reason: 'not_high_impact', at_et: null },
  reaction: {
    at_detection: { as_of: '2026-09-24T07:35:03-04:00', session: 'premarket', price: 191.0, base_close: 188.4,
      base_basis: 'frame', move_pct: 1.4, volume_so_far: 55_000, rvol_so_far: null, latency_min: 5.0, post_session: false },
    at_close: { open: 190.2, high: 199.9, low: 189.1, close: 198.88, volume: 6_100_000, gap_pct: 1.0, day_pct: 5.6,
      rvol: 0.9, dollar_volume: 1_213_168_000, close_loc: 0.9, basis: 'closed_bar' },
    fwd: null,
  },
  liquidity: { base_close: 188.4, base_basis: 'frame', adv50_usd: 1_191_000_000, avg_vol50: 6_300_000, pre_ret_20d_pct: 9.0, market_cap: 76_000_000_000 },
  dilutive: null, links: links('MRNA'),
};

export const MED_EVENTS: MedEventRow[] = [HUMA_ROW, KOD_ROW, MIRM_APPROVAL, MIRM_TOPLINE, MNOV_ROW, ELEVAR_ROW, MRNA_ROW];

const roll = (over: Partial<import('../medicalCatalysts').RollRow> & { key: string; label: string }) => ({
  n_events: 1, n_high: 0, n_positive: 0, n_negative: 0, n_obs: 1,
  median_day_pct: null, n_day: 0, median_ret_5d_pct: null, n_5d: 0, median_ret_21d_pct: null, n_21d: 0,
  n_tickers: 1, small_n: true, tickers: [], ...over,
});

export const ROLLUP_NOTE = 'Descriptive and UNMEASURED: medians of what these names did after their news in this window, '
  + 'one observation per name per session. No placebo, no twins, not a signal.';

export const MED_BOARD: MedBoard = {
  as_of: '2026-09-29T00:50:00-04:00',
  window_days: 30,
  labels: LABELS,
  taxonomy: {
    event_types: [
      { key: 'fda_approval', label: 'FDA approval', family: 'fda', emoji: '🏛️' },
      { key: 'fda_crl', label: 'FDA complete response / rejection', family: 'fda', emoji: '🏛️' },
      { key: 'topline', label: 'Topline results', family: 'trial', emoji: '🧪' },
      { key: 'conference_data', label: 'Conference data', family: 'conference', emoji: '🎤' },
      { key: 'designation', label: 'Designation', family: 'regulatory', emoji: '🏷️' },
      { key: 'clinical_hold', label: 'Clinical hold', family: 'hold', emoji: '⚠️' },
      { key: 'financing', label: 'Financing', family: 'financing', emoji: '💵' },
    ],
    families: [
      { key: 'fda', label: 'FDA decisions', emoji: '🏛️' },
      { key: 'trial', label: 'Trial readouts', emoji: '🧪' },
      { key: 'conference', label: 'Conference data', emoji: '🎤' },
      { key: 'regulatory', label: 'Designations, filings & dates', emoji: '🏷️' },
      { key: 'hold', label: 'Holds & safety', emoji: '⚠️' },
      { key: 'deal', label: 'Deals', emoji: '🤝' },
      { key: 'financing', label: 'Financing — dilution', emoji: '💵' },
      { key: 'scheduled', label: 'Scheduled & milestones', emoji: '📅' },
    ],
    modalities: [
      { key: 'mrna', label: 'mRNA' }, { key: 'gene_editing', label: 'Gene editing' },
      { key: 'antibody_bispecific', label: 'Antibodies & bispecifics' }, { key: 'vaccine', label: 'Vaccine' },
      { key: 'small_molecule', label: 'Small molecule' }, { key: 'unclassified', label: 'unclassified' },
    ],
    areas: [
      { key: 'oncology', label: 'oncology' }, { key: 'ophthalmology', label: 'ophthalmology' },
      { key: 'rare_disease', label: 'rare disease' }, { key: 'unclassified', label: 'unclassified' },
    ],
    high_impact_text: 'FDA approval (not tentative or generic); complete response letter, refuse-to-file or rejection; '
      + 'Phase 3 / pivotal topline positive or negative; Breakthrough Therapy designation; clinical hold placed.',
  },
  events: MED_EVENTS,
  rollup: {
    by_modality: [
      roll({ key: 'small_molecule', label: 'Small molecule', n_events: 3, n_high: 3, n_positive: 3, n_obs: 1,
        median_day_pct: -1.9, n_day: 1, n_tickers: 1, tickers: ['MIRM'] }),
      roll({ key: 'unclassified', label: 'unclassified', n_events: 2, n_high: 1, n_positive: 1, n_obs: 2,
        median_day_pct: -18.6, n_day: 1, n_tickers: 2, tickers: ['MNOV', 'HUMA'] }),
      roll({ key: 'antibody_bispecific', label: 'Antibodies & bispecifics', n_events: 1, n_high: 1, n_positive: 1,
        median_day_pct: 178.0, n_day: 1, tickers: ['KOD'] }),
      roll({ key: 'mrna', label: 'mRNA', median_day_pct: 5.6, n_day: 1, tickers: ['MRNA'] }),
    ],
    by_area: [
      roll({ key: 'rare_disease', label: 'rare disease', n_events: 2, n_high: 2, n_positive: 2, n_obs: 1,
        median_day_pct: -1.9, n_day: 1, n_tickers: 1, tickers: ['MIRM'] }),
      roll({ key: 'unclassified', label: 'unclassified', n_events: 2, n_high: 1, n_positive: 1, n_obs: 2,
        median_day_pct: -18.6, n_day: 1, n_tickers: 2, tickers: ['MNOV', 'HUMA'] }),
      roll({ key: 'oncology', label: 'oncology', n_events: 2, n_high: 1, n_positive: 1, n_obs: 1,
        median_day_pct: 5.6, n_day: 1, n_tickers: 1, tickers: ['MRNA'] }),
      roll({ key: 'ophthalmology', label: 'ophthalmology', n_events: 1, n_high: 1, n_positive: 1,
        median_day_pct: 178.0, n_day: 1, tickers: ['KOD'] }),
    ],
    note: ROLLUP_NOTE,
    window_days: 30,
  },
  counts: { events: 7, high_impact: 5, unclassified_modality: 2, unresolved_ticker: 1 },
  pass: { as_of: '2026-09-29T00:45:00-04:00', reason: null,
    counts: { roster: 362, sliced: 36, articles_new: 4, events_new: 2, errors: 0 } },
  sources: [
    { key: 'finnhub', label: 'Finnhub company news' }, { key: 'sec', label: 'SEC 8-K EX-99.1' },
    { key: 'massive', label: 'Massive market-wide news' }, { key: 'fda_rss', label: 'FDA press releases' },
  ],
  push: { kind: 'med_catalyst',
    gate_text: 'high-impact types only; prior close ≥ $2 and 50-session median dollar volume ≥ $5M; once per event. UNMEASURED.' },
};

export const MED_SYMBOL_KOD: MedSymbolPayload = {
  symbol: 'KOD', as_of: '2026-09-29T00:50:00-04:00', labels: LABELS,
  events: [KOD_ROW], tracking_since: '2026-09-29',
};

export const MED_SYMBOL_EMPTY: MedSymbolPayload = {
  symbol: 'AAPL', as_of: '2026-09-29T00:50:00-04:00', labels: LABELS, events: [], tracking_since: '2026-09-29',
};
