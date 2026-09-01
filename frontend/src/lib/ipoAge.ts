// IPO-age callout label for the candidate detail page.
//
// The backend refuses to claim a listing date when the price frame is
// truncated at the provider's fetch cap (see backend/sepa/ipo_age.py,
// 2026-08-31): in that unknown state every field is null and the callout
// must not render at all — "IPO null · nully old" is worse than silence.

export interface IpoAge {
  first_trade_date: string | null
  years_since_ipo: number | null
  is_young: boolean | null
  is_recent_ipo: boolean | null
  source?: string | null
}

export function ipoAgeLabel(ipo: IpoAge | null | undefined): string | null {
  if (!ipo || !ipo.first_trade_date || ipo.years_since_ipo == null) return null
  let label = `IPO ${ipo.first_trade_date} · ${ipo.years_since_ipo}y old`
  if (ipo.is_young) label += ' · young ✓'
  if (ipo.is_recent_ipo) label += ' · recent IPO ✓'
  return label
}
