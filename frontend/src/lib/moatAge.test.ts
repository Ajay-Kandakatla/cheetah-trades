import { describe, expect, it } from 'vitest';
import { moatAsOfLine } from './moatAge';

// 2026-10-04 16:00 ET = 20:00 UTC
const AS_OF = Date.UTC(2026, 9, 4, 20, 0, 0) / 1000;
const DAY = 86_400_000;

describe('moatAsOfLine', () => {
  it('prints the read date and its age in days', () => {
    expect(moatAsOfLine(AS_OF, AS_OF * 1000 + 7 * DAY + 5)).toBe('Moat data as of Oct 4, 2026 (7d old)');
  });

  it('omits the age on the day it was read', () => {
    expect(moatAsOfLine(AS_OF, AS_OF * 1000 + 3_600_000)).toBe('Moat data as of Oct 4, 2026');
  });

  it('dates in New York time, not UTC', () => {
    // 2026-10-05 02:00 UTC is still Oct 4 in New York
    const lateEvening = Date.UTC(2026, 9, 5, 2, 0, 0) / 1000;
    expect(moatAsOfLine(lateEvening, lateEvening * 1000)).toBe('Moat data as of Oct 4, 2026');
  });

  it('a future stamp (clock skew) prints no negative age', () => {
    expect(moatAsOfLine(AS_OF, AS_OF * 1000 - 3 * DAY)).toBe('Moat data as of Oct 4, 2026');
  });

  it.each([
    ['undefined', undefined],
    ['null', null],
    ['zero', 0],
    ['negative', -5],
    ['NaN', Number.NaN],
    ['Infinity', Number.POSITIVE_INFINITY],
    ['a string', '1791000000'],
    ['milliseconds by mistake', AS_OF * 1000],
  ])('prints nothing for %s', (_label, v) => {
    expect(moatAsOfLine(v, AS_OF * 1000)).toBe('');
  });
});
