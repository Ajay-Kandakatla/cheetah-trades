/* Leveraged / inverse ETF guardrail (Ajay 2026-06-03).

   Minervini's SEPA framework is for individual leading STOCKS — earnings, sales,
   institutional sponsorship. Leveraged & inverse ETFs (TQQQ, TECL, USD, SOXL…)
   have none of that: no fundamentals, daily-rebalance volatility decay, and
   2–3× amplified drawdowns. The Trend Template can still "fire" on their price
   action (TECL showed up Primed/#2, USD Steady/100%), so we badge them wherever
   they surface so they're never mistaken for a Minervini buy signal.

   Detection = a curated ticker set (precise, zero false positives) + an issuer/
   name pattern for anything not in the set. Deliberately conservative on the
   name regex so real stocks ("Ultra Clean Holdings", "Ultragenyx") aren't
   flagged. */

const LEVERAGED_TICKERS = new Set<string>([
  // 3× equity index / sector (Direxion Daily, ProShares UltraPro)
  'TQQQ', 'SQQQ', 'SPXL', 'SPXS', 'SPXU', 'UPRO', 'UDOW', 'SDOW', 'TNA', 'TZA',
  'TECL', 'TECS', 'SOXL', 'SOXS', 'FAS', 'FAZ', 'LABU', 'LABD', 'RETL', 'NAIL',
  'DPST', 'CURE', 'DRN', 'DRV', 'WEBL', 'WEBS', 'PILL', 'MIDU', 'TPOR', 'UTSL',
  'FNGU', 'FNGD', 'BULZ', 'GUSH', 'DRIP', 'NUGT', 'DUST', 'JNUG', 'JDST', 'ERX',
  'ERY', 'YINN', 'YANG', 'KORU', 'BRZU', 'INDL', 'TMF', 'TMV', 'TYD', 'TYO',
  'EDC', 'EDZ', 'HIBL', 'HIBS', 'DUSL', 'CWEB',
  // 2× (ProShares Ultra, etc.)
  'QLD', 'SSO', 'DDM', 'UWM', 'ROM', 'USD', 'MVV', 'SAA', 'UYG', 'UGL', 'AGQ',
  'BIB', 'UBT', 'UST', 'SDS', 'QID', 'DXD', 'TWM', 'SCO', 'UCO', 'BOIL', 'KOLD',
  'UVXY', 'SVXY', 'UVIX', 'SVIX',
  // crypto-leveraged single-stock / index
  'BITX', 'BITU', 'ETHU', 'ETHT', 'MSTX', 'MSTU', 'NVDL', 'TSLL', 'TSLT', 'CONL',
]);

// Only matches obvious leveraged/inverse products — NOT bare "Ultra" (would hit
// Ultra Clean Holdings) and NOT "Ultra"-prefixed single words (Ultragenyx).
const LEVERAGED_NAME_RE =
  /\b[23]\s?x\b|ultrapro|ultrashort|\bleveraged\b|(?:direxion|proshares|microsectors|graniteshares)\b.*\b(?:bull|bear|ultra)\b/i;

export type LeverageInfo = { isLeveraged: boolean; label: string };

export function leveragedEtfInfo(symbol?: string | null, name?: string | null): LeverageInfo {
  const sym = (symbol || '').toUpperCase().trim();
  const nm = name || '';
  const hit = (!!sym && LEVERAGED_TICKERS.has(sym)) || (!!nm && LEVERAGED_NAME_RE.test(nm));
  if (!hit) return { isLeveraged: false, label: '' };
  const m = nm.match(/\b([23])\s?x\b/i);
  return { isLeveraged: true, label: m ? `${m[1]}× Leveraged ETF` : 'Leveraged ETF' };
}
