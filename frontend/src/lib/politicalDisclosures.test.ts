/**
 * politicalDisclosures.test.ts — the 2026-09-19 critical-minerals additions
 * and the 🆕 highlight that carries them.
 *
 * Ajay 2026-09-19: *"Show me POTUS tickers there are some new ones like Green
 * Land eneregy or something"* then *"High light them in the page"*.
 *
 * The single most important assertion in this file is that GLND is NOT a
 * government investment. His question arrived as "show me the new POTUS
 * names", GLND rallied on an Arctic-policy headline, and the lazy answer is
 * to file it beside MP and USAR. It has no U.S. government agreement of any
 * kind. If that row ever flips to 'govt_investment' without an agency and a
 * percentage behind it, the chip stops meaning anything and this file fails.
 */
import { describe, it, expect } from 'vitest';
import {
  getPoliticalDisclosure,
  getPoliticalChipFlags,
  isNewDisclosure,
  recentDisclosures,
  NEW_DISCLOSURE_DAYS,
  POLITICAL_DISCLOSURE_TOTAL_COUNT,
  type DisclosureEntry,
} from './politicalDisclosures';

/** Pinned clock. A 14-day window tested against the real `new Date()` goes
 *  green for a fortnight and then silently red forever — the classic
 *  rots-by-calendar test. Every case below states its own date. */
const ADDED = '2026-09-19';
const SAME_DAY = new Date('2026-09-19T12:00:00Z');
const DAY_13 = new Date('2026-10-02T00:00:00Z');   // 13 days later — inside
const DAY_15 = new Date('2026-10-04T00:00:00Z');   // 15 days later — outside

const NEW_TICKERS = ['MP', 'USAR', 'LAC', 'TMQ', 'ALOY', 'CRML', 'GLND', 'UUUU'];

describe('the 2026-09-19 additions exist and resolve', () => {
  it.each(NEW_TICKERS)('%s is on the list', (t) => {
    expect(getPoliticalDisclosure(t)).not.toBeNull();
  });

  it('grew the list by exactly the eight names added', () => {
    // The 2026-05-28 seed list was 36 rows; these eight take it to 44. A
    // change to this number without a change to this test is someone editing
    // the curated file without saying why.
    expect(POLITICAL_DISCLOSURE_TOTAL_COUNT).toBe(44);
    expect(POLITICAL_DISCLOSURE_TOTAL_COUNT - NEW_TICKERS.length).toBe(36);
  });

  it('is case-insensitive on the new rows too', () => {
    expect(getPoliticalDisclosure('glnd')?.ticker).toBe('GLND');
    expect(getPoliticalDisclosure('  ')).toBeNull();
  });
});

describe('the equity-stake rows carry a named agency and a stated size', () => {
  it.each(['MP', 'USAR', 'LAC', 'TMQ'])('%s is govt_investment with a stake', (t) => {
    const e = getPoliticalDisclosure(t)!;
    expect(e.categories).toContain('govt_investment');
    expect(e.govtStake).toBeTruthy();
    // "<agency> <pct>%" — a stake with no percentage is not a stake.
    expect(e.govtStake).toMatch(/\d+%/);
    expect(e.govtStake!.replace(/[\d%\s]/g, '').length).toBeGreaterThan(2);
  });

  it('renders the size on the chip flags consumer', () => {
    const f = getPoliticalChipFlags('MP', SAME_DAY);
    expect(f.hasGovtInvestment).toBe(true);
    expect(f.entry?.govtStake).toBe('DoD 15%');
  });
});

describe('a federal AWARD is not an equity stake', () => {
  it('ALOY is govt_contractor, not govt_investment, and claims no stake', () => {
    const e = getPoliticalDisclosure('ALOY')!;
    expect(e.categories).toContain('govt_contractor');
    expect(e.categories).not.toContain('govt_investment');
    expect(e.govtStake ?? null).toBeNull();
  });
});

describe('THE GREENLAND TRAP — a headline mover is not an investment', () => {
  it('GLND is inferred and explicitly NOT a government investment', () => {
    const e = getPoliticalDisclosure('GLND')!;
    expect(e.categories).toEqual(['inferred']);
    expect(e.categories).not.toContain('govt_investment');
    expect(e.categories).not.toContain('govt_contractor');
    expect(e.categories).not.toContain('potus_family');
    expect(e.govtStake ?? null).toBeNull();
    // The note must SAY there is no deal, not merely omit one.
    expect(e.notes).toMatch(/NO U\.S\. government agreement/i);
  });

  it('GLND renders only the soft inferred chip', () => {
    const f = getPoliticalChipFlags('GLND', SAME_DAY);
    expect(f.isInferred).toBe(true);
    expect(f.hasGovtInvestment).toBe(false);
    expect(f.hasGovtContractor).toBe(false);
    expect(f.hasPotusFamily).toBe(false);
  });

  it('CRML records REPORTED interest and still claims no stake', () => {
    const e = getPoliticalDisclosure('CRML')!;
    expect(e.categories).toEqual(['inferred']);
    expect(e.govtStake ?? null).toBeNull();
    expect(e.notes).toMatch(/never a signed deal/i);
  });

  it('UUUU is inferred with no Greenland asset claimed', () => {
    const e = getPoliticalDisclosure('UUUU')!;
    expect(e.categories).toEqual(['inferred']);
    expect(e.govtStake ?? null).toBeNull();
  });
});

describe('structural guard — govtStake may only appear on an equity row', () => {
  it('no non-govt_investment row anywhere carries a govtStake', () => {
    const offenders: string[] = [];
    for (const t of NEW_TICKERS) {
      const e = getPoliticalDisclosure(t)!;
      if (e.govtStake && !e.categories.includes('govt_investment')) {
        offenders.push(e.ticker);
      }
    }
    expect(offenders).toEqual([]);
  });

  it('every row added after the seed states its basis and both dates', () => {
    for (const t of NEW_TICKERS) {
      const e = getPoliticalDisclosure(t)!;
      expect(e.addedOn, `${t} addedOn`).toBe(ADDED);
      expect(e.asOf, `${t} asOf`).toBeTruthy();
      // The BASIS. A political chip with no stated reason is the thing this
      // whole file exists to prevent.
      expect((e.notes || '').length, `${t} notes`).toBeGreaterThan(40);
    }
  });
});

describe('isNewDisclosure — the 14-day window', () => {
  const row = (over: Partial<DisclosureEntry> = {}): DisclosureEntry => ({
    ticker: 'TEST', company: 'Test', sector: 'Test', categories: ['inferred'],
    ...over,
  });

  it('is true on the day it was added', () => {
    expect(isNewDisclosure(row({ addedOn: ADDED }), SAME_DAY)).toBe(true);
  });

  it('is still true inside the window', () => {
    expect(isNewDisclosure(row({ addedOn: ADDED }), DAY_13)).toBe(true);
  });

  it('is FALSE once the window has passed', () => {
    expect(isNewDisclosure(row({ addedOn: ADDED }), DAY_15)).toBe(false);
  });

  it('is false at exactly one day past the window', () => {
    const justOut = new Date(Date.parse(`${ADDED}T00:00:00Z`)
      + (NEW_DISCLOSURE_DAYS + 1) * 86_400_000);
    expect(isNewDisclosure(row({ addedOn: ADDED }), justOut)).toBe(false);
  });

  // ── negatives ──────────────────────────────────────────────────────
  it('a seed row with no addedOn is never new', () => {
    expect(isNewDisclosure(row(), SAME_DAY)).toBe(false);
    expect(getPoliticalChipFlags('NVDA', SAME_DAY).isNew).toBe(false);
  });

  it('null entry is never new', () => {
    expect(isNewDisclosure(null, SAME_DAY)).toBe(false);
  });

  it('an unparseable date is never new', () => {
    expect(isNewDisclosure(row({ addedOn: 'tomorrow' }), SAME_DAY)).toBe(false);
    expect(isNewDisclosure(row({ addedOn: '' }), SAME_DAY)).toBe(false);
  });

  it('a FUTURE date does not mint a highlight', () => {
    // A typo'd year must not light the chip up for the next decade.
    expect(isNewDisclosure(row({ addedOn: '2036-09-19' }), SAME_DAY)).toBe(false);
  });

  it('a ticker that is not on the list is not new and has no entry', () => {
    const f = getPoliticalChipFlags('ZZZZ', SAME_DAY);
    expect(f.entry).toBeNull();
    expect(f.isNew).toBe(false);
    expect(f.hasPotusFamily).toBe(false);
    expect(f.hasGovtInvestment).toBe(false);
    expect(f.hasGovtContractor).toBe(false);
    expect(f.isInferred).toBe(false);
  });
});

describe('recentDisclosures', () => {
  it('returns exactly the eight new rows inside the window', () => {
    const got = recentDisclosures(SAME_DAY).map((e) => e.ticker).sort();
    expect(got).toEqual([...NEW_TICKERS].sort());
  });

  it('returns nothing once the window has passed', () => {
    expect(recentDisclosures(DAY_15)).toEqual([]);
  });

  it('never includes a seed row', () => {
    const tickers = recentDisclosures(SAME_DAY).map((e) => e.ticker);
    expect(tickers).not.toContain('NVDA');
    expect(tickers).not.toContain('INTC');
  });
});
