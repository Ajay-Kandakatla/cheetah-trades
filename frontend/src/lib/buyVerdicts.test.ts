import { describe, it, expect } from 'vitest';
import { verdictsKey } from './buyVerdicts';

describe('verdictsKey', () => {
  it('uppercases, de-dupes and sorts so the fetch key is stable', () => {
    expect(verdictsKey(['nvda', 'AAPL', 'nvda'])).toBe('AAPL,NVDA');
    expect(verdictsKey(['AAPL', 'nvda'])).toBe(verdictsKey(['NVDA', 'aapl']));  // order-independent
  });

  it('empty / junk inputs give an empty key (no fetch)', () => {
    expect(verdictsKey([])).toBe('');
    expect(verdictsKey(['', '  '])).toBe('');
  });
});
