/**
 * Balance/debt read for the 🚀 Explosive Growth board.
 *
 * Ajay 2026-09-14: "I do not want them to have any debt."
 *
 * The load-bearing tests are the ones that stop this from becoming either
 * useless (a literal zero-debt filter returns an empty board) or wrong
 * (a mortgage REIT graded "levered" for doing exactly its job).
 */
import { describe, it, expect } from 'vitest';
import {
  balanceRead, passesDebtFilter, DEBT_FREE_RATIO, DEBT_TIER_ORDER,
} from './balanceRead';

// Real rows off the live board on 2026-09-14.
const CRDO = { cash: 764e6, debt: 26e6, cash_minus_debt: 738e6, balance_meaningful: true };
const ALAB = { cash: 1253e6, debt: 44e6, cash_minus_debt: 1209e6, balance_meaningful: true };
const NVDA = { cash: 62469e6, debt: 38860e6, cash_minus_debt: 23609e6, balance_meaningful: true };
const BE   = { cash: 2720e6, debt: 2820e6, cash_minus_debt: -98e6, balance_meaningful: true };
const ECHO = { cash: 496e6, debt: 17580e6, cash_minus_debt: -17084e6, balance_meaningful: true };
const NLY  = { cash: 480e6, debt: 125220e6, cash_minus_debt: -124740e6, balance_meaningful: false };

describe('balanceRead', () => {
  it('grades CRDO — his own reference name — as debt-free', () => {
    const b = balanceRead(CRDO);
    expect(b.tier).toBe('debt-free');
    expect(b.label).toBe('No debt');
    expect(b.debtPctOfCash).toBeCloseTo(3.4, 1);
  });

  it('grades ALAB debt-free and NVDA only net cash', () => {
    expect(balanceRead(ALAB).tier).toBe('debt-free');
    // NVDA holds $23.6B more cash than debt but the debt is 62% of cash — real.
    expect(balanceRead(NVDA).tier).toBe('net cash');
  });

  it('grades a name with slightly more debt than cash as modest, not levered', () => {
    expect(balanceRead(BE).tier).toBe('modest');
  });

  it('grades a genuinely levered name as levered', () => {
    expect(balanceRead(ECHO).tier).toBe('levered');
  });

  it('NEGATIVE: a mortgage REIT is NOT graded levered — debt is its product', () => {
    // NLY's numbers are the most levered on the board by a mile. Grading it
    // "levered" would be like grading a bank levered: true and meaningless.
    const b = balanceRead(NLY);
    expect(b.tier).toBe('n/a');
    expect(b.label).toMatch(/business/i);
    expect(b.hint).toMatch(/lender|mortgage|BDC/i);
  });

  it('NEGATIVE: balance_meaningful is checked BEFORE any arithmetic', () => {
    // Even with numbers that would otherwise read debt-free, an unmeaningful
    // balance sheet must not be graded.
    expect(balanceRead({ cash: 1000, debt: 1, balance_meaningful: false }).tier).toBe('n/a');
  });

  it('NEGATIVE: missing numbers read unknown, never debt-free', () => {
    expect(balanceRead({ cash: null, debt: null }).tier).toBe('unknown');
    expect(balanceRead({ cash: 100, debt: null }).tier).toBe('unknown');
    expect(balanceRead({}).tier).toBe('unknown');
  });

  it('NEGATIVE: zero cash with debt is not debt-free (no divide-by-zero pass)', () => {
    // PROP on the live board: $0 cash, $441M debt. Dividing would give
    // Infinity, and a naive `< ratio` test on NaN/Infinity could let it pass.
    const b = balanceRead({ cash: 0, debt: 441e6, cash_minus_debt: -441e6, balance_meaningful: true });
    expect(b.tier).toBe('levered');
    expect(b.tier).not.toBe('debt-free');
  });

  it('a company with neither cash nor debt is debt-free', () => {
    expect(balanceRead({ cash: 0, debt: 0, cash_minus_debt: 0 }).tier).toBe('debt-free');
  });

  it('the debt-free ratio is the documented 5%', () => {
    expect(DEBT_FREE_RATIO).toBe(0.05);
    expect(balanceRead({ cash: 1000, debt: 49 }).tier).toBe('debt-free');
    expect(balanceRead({ cash: 1000, debt: 51 }).tier).toBe('net cash');
  });
});

describe('passesDebtFilter', () => {
  it('the strictest tier keeps CRDO and drops NVDA', () => {
    expect(passesDebtFilter(CRDO, 'debt-free')).toBe(true);
    expect(passesDebtFilter(NVDA, 'debt-free')).toBe(false);
  });

  it('widening to net cash admits NVDA and still drops the levered', () => {
    expect(passesDebtFilter(NVDA, 'net cash')).toBe(true);
    expect(passesDebtFilter(ECHO, 'net cash')).toBe(false);
  });

  it('NEGATIVE: a lender is excluded at every tier — debt IS its funding model', () => {
    for (const worst of ['debt-free', 'net cash', 'modest', 'levered'] as const) {
      expect(passesDebtFilter(NLY, worst)).toBe(false);
    }
  });

  it('NEGATIVE: an UNGRADEABLE row always passes — never a silent data drop', () => {
    // "I do not want them to have any debt" is an instruction about debt, not
    // a licence to hide names whose filing did not report it. Those pass
    // carrying a "Not reported" chip so he can see the gap.
    for (const worst of ['debt-free', 'net cash', 'modest', 'levered'] as const) {
      expect(passesDebtFilter({ cash: null, debt: null }, worst)).toBe(true);
      expect(passesDebtFilter({}, worst)).toBe(true);
    }
  });

  it('the tier order is best-to-worst with the ungradeable last', () => {
    expect(DEBT_TIER_ORDER.slice(0, 4))
      .toEqual(['debt-free', 'net cash', 'modest', 'levered']);
    expect(DEBT_TIER_ORDER.slice(4)).toEqual(['n/a', 'unknown']);
  });

  it('REGRESSION: a literal zero-debt rule would empty the board', () => {
    // 0 of 29 live rows carried debt === 0. This test documents WHY the top
    // tier is relative; if someone makes it absolute, the board goes blank.
    const live = [CRDO, ALAB, NVDA, BE, ECHO];
    expect(live.filter((r) => r.debt === 0)).toHaveLength(0);
    expect(live.filter((r) => balanceRead(r).tier === 'debt-free').length)
      .toBeGreaterThan(0);
  });
});
