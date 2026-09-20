import { describe, expect, it } from 'vitest';
import {
  IPO_NO_UPCOMING, blankIfRecycled, ipoCorroborationLine, ipoText, isRecycled,
  upcomingRows,
} from './ipoTab';

/* 🆕 IPO tab reading rules (2026-09-20).
 *
 * The defect these guard is a RECYCLED ticker printing another company's
 * day-one move as an IPO pop. The backend already blanks those stats; these
 * blank them again on the way to the screen, because the failure mode is one
 * he would act on. */

describe('isRecycled', () => {
  it('reads the served flag', () => {
    expect(isRecycled({ symbol: 'RECYC', recycled: true })).toBe(true);
  });

  it('reads the status too — either alone is enough', () => {
    expect(isRecycled({ symbol: 'RECYC', ipo_status: 'recycled' })).toBe(true);
  });

  it('is FALSE on a confirmed tile', () => {
    expect(isRecycled({ symbol: 'GOODCO', recycled: false, ipo_status: 'confirmed' }))
      .toBe(false);
  });

  it('is false, never a throw, on junk', () => {
    expect(isRecycled(null)).toBe(false);
    expect(isRecycled(undefined)).toBe(false);
    expect(isRecycled({} as any)).toBe(false);
    expect(isRecycled('RECYC' as any)).toBe(false);
  });

  it('does NOT treat uncorroborated as recycled — they are different facts', () => {
    expect(isRecycled({ symbol: 'SILENT', ipo_status: 'uncorroborated' })).toBe(false);
  });
});

describe('blankIfRecycled', () => {
  const recyc = { symbol: 'RECYC', recycled: true };
  const good = { symbol: 'GOODCO', recycled: false };

  it('blanks a price-derived stat on a recycled tile even when one arrived', () => {
    expect(blankIfRecycled(recyc, '+312.0%')).toBe('—');
  });

  it('passes a confirmed tile straight through', () => {
    expect(blankIfRecycled(good, '+20.0%')).toBe('+20.0%');
  });

  it('turns a missing stat into an em dash rather than printing nothing', () => {
    expect(blankIfRecycled(good, null)).toBe('—');
    expect(blankIfRecycled(good, '')).toBe('—');
    expect(blankIfRecycled(good, undefined)).toBe('—');
  });
});

describe('upcomingRows', () => {
  const rows = [
    { symbol: 'AMRO', date: '2026-09-23', status: 'expected' },
    { symbol: 'BMB', date: '2026-09-23', status: 'expected' },
    { symbol: 'PTT', date: '2026-09-30', status: 'expected' },
  ];

  it('accepts a bare array', () => {
    expect(upcomingRows(rows).map((r) => r.symbol)).toEqual(['AMRO', 'BMB', 'PTT']);
  });

  it('accepts the whole board payload', () => {
    expect(upcomingRows({ upcoming: rows }).map((r) => r.symbol))
      .toEqual(['AMRO', 'BMB', 'PTT']);
  });

  it('keeps the SERVED order — the backend already sorted by date', () => {
    const shuffled = [rows[2], rows[0], rows[1]];
    expect(upcomingRows(shuffled).map((r) => r.symbol)).toEqual(['PTT', 'AMRO', 'BMB']);
  });

  it('is an empty array, never a throw, on nothing or junk', () => {
    expect(upcomingRows(null)).toEqual([]);
    expect(upcomingRows(undefined)).toEqual([]);
    expect(upcomingRows({} as any)).toEqual([]);
    expect(upcomingRows({ upcoming: null })).toEqual([]);
    expect(upcomingRows('rows' as any)).toEqual([]);
  });

  it('drops rows with no usable symbol', () => {
    expect(upcomingRows([null, 7, {}, { symbol: '  ' }, rows[0]] as any)
      .map((r) => r.symbol)).toEqual(['AMRO']);
  });
});

describe('ipoText', () => {
  it('prints a price RANGE verbatim — a range is not a price', () => {
    expect(ipoText('18.00-20.00')).toBe('18.00-20.00');
  });

  it('prints a share count exactly as served, commas and all', () => {
    expect(ipoText('5,000,000')).toBe('5,000,000');
  });

  it('never invents a value for a missing or non-finite field', () => {
    expect(ipoText(null)).toBe('—');
    expect(ipoText(undefined)).toBe('—');
    expect(ipoText('')).toBe('—');
    expect(ipoText(Number.NaN)).toBe('—');
    expect(ipoText({} as any)).toBe('—');
  });
});

describe('ipoCorroborationLine', () => {
  it('says the calendar could not be read, and why, on an outage', () => {
    const line = ipoCorroborationLine({ available: false, reason: 'rate limit' });
    expect(line).toContain('could not be read');
    expect(line).toContain('rate limit');
    expect(line).toContain('uncorroborated');
  });

  it('names the forward window when the pass ran', () => {
    expect(ipoCorroborationLine({ available: true, forward_to: '2026-10-20' }))
      .toContain('2026-10-20');
  });

  it('says the state is unknown rather than implying it was fine', () => {
    expect(ipoCorroborationLine(null)).toContain('unknown');
  });

  /* 2026-09-20 — Ajay answered the owner's-call: "Yes for #1 and #2 and #3
   * and #4 and #5", #3 being "DROP the IPO tab's uncorroborated rows". The
   * drop must never be silent, so the count rides on the basis line he is
   * already reading. The live board held 22 of them. */
  it('names how many uncorroborated listings the board dropped', () => {
    const line = ipoCorroborationLine({ available: true, forward_to: '2026-10-20' },
                                      { dropped_uncorroborated: 22 });
    expect(line.endsWith(
      '22 uncorroborated dropped — spin-offs and re-listings the calendar does not carry',
    )).toBe(true);
    expect(line).toContain('2026-10-20');
  });

  it('says nothing at all when nothing was dropped', () => {
    expect(ipoCorroborationLine({ available: true }, { dropped_uncorroborated: 0 }))
      .not.toContain('dropped');
    expect(ipoCorroborationLine({ available: true }, {})).not.toContain('dropped');
    expect(ipoCorroborationLine({ available: true }, null)).not.toContain('dropped');
    expect(ipoCorroborationLine({ available: true })).not.toContain('dropped');
  });

  it('NEVER claims a drop on an outage build — nothing is dropped there', () => {
    const line = ipoCorroborationLine({ available: false, reason: 'rate limit' },
                                      { dropped_uncorroborated: 22 });
    expect(line).not.toContain('dropped');
    expect(line).not.toContain('22');
    expect(line).toContain('could not be read');
  });

  it('refuses a junk count instead of printing NaN at him', () => {
    for (const bad of [null, undefined, Number.NaN, -3, '22' as any]) {
      expect(ipoCorroborationLine({ available: true },
                                  { dropped_uncorroborated: bad as any }))
        .not.toContain('dropped');
    }
  });
});

describe('the empty sentence', () => {
  it('names the FEED, so "none" cannot be read as a claim about the market', () => {
    expect(IPO_NO_UPCOMING).toContain('Finnhub calendar');
    expect(IPO_NO_UPCOMING).toContain('30 days');
  });
});
