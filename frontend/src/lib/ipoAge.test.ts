import { describe, expect, it } from 'vitest'
import { ipoAgeLabel } from './ipoAge'

describe('ipoAgeLabel', () => {
  it('renders a young recent IPO with both badges', () => {
    expect(
      ipoAgeLabel({
        first_trade_date: '2025-11-03',
        years_since_ipo: 0.82,
        is_young: true,
        is_recent_ipo: true,
        source: 'history',
      }),
    ).toBe('IPO 2025-11-03 · 0.82y old · young ✓ · recent IPO ✓')
  })

  it('renders an old company with no badges', () => {
    expect(
      ipoAgeLabel({
        first_trade_date: '2013-09-16',
        years_since_ipo: 12.96,
        is_young: false,
        is_recent_ipo: false,
        source: 'profile',
      }),
    ).toBe('IPO 2013-09-16 · 12.96y old')
  })

  it('returns null for the backend unknown state (truncated history)', () => {
    expect(
      ipoAgeLabel({
        first_trade_date: null,
        years_since_ipo: null,
        is_young: null,
        is_recent_ipo: null,
        source: null,
      }),
    ).toBeNull()
  })

  it('returns null when the block is missing entirely', () => {
    expect(ipoAgeLabel(null)).toBeNull()
    expect(ipoAgeLabel(undefined)).toBeNull()
  })

  it('never prints badges off null flags on a partially known block', () => {
    const label = ipoAgeLabel({
      first_trade_date: '2020-01-02',
      years_since_ipo: 6.66,
      is_young: null,
      is_recent_ipo: null,
    })
    expect(label).toBe('IPO 2020-01-02 · 6.66y old')
  })
})
