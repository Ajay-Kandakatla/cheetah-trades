/* 🐛 2026-11-22 — Ajay: "There is a bug, I added WETO as new one to watch list everything got de activated from watch
 * list". ggwPrunePick keeps only the pick's names still kept (the list + names a × is still hiding), in pick order;
 * none left → null (the pages). ggwJoinPick is unchanged (a stale pick still comes back as-is from it). */
import { describe, expect, it } from 'vitest';
import { ggwJoinPick, ggwLivePick, ggwPrunePick } from './gajjalaWatch';

describe('ggwPrunePick', () => {
  it('NEGATIVE: no pick → null', () => {
    expect(ggwPrunePick(null, ['A', 'B'])).toBeNull();
  });
  it('NEGATIVE: an all-stale pick → null (never an empty array)', () => {
    expect(ggwPrunePick(['OMH', 'GIPR', 'WETO'], ['SVRE', 'GMM'])).toBeNull();
    expect(ggwPrunePick([], ['SVRE'])).toBeNull();
    expect(ggwPrunePick(['A'], [])).toBeNull();
  });
  it('a mixed pick keeps the listed names in PICK order (not list order)', () => {
    expect(ggwPrunePick(['C', 'GONE', 'A'], ['A', 'B', 'C'])).toEqual(['C', 'A']);
  });
  it('a name a × is still hiding (kept, though off the list) stays in the pick', () => {
    const list = ['A', 'B'];
    const removing = ['X'];
    expect(ggwPrunePick(['X', 'A', 'GONE'], [...list, ...removing])).toEqual(['X', 'A']);
  });
  it('NEGATIVE: the input is not mutated and a fully-kept pick is a new copy', () => {
    const pick = ['A', 'B'];
    const out = ggwPrunePick(pick, ['A', 'B']);
    expect(out).toEqual(['A', 'B']);
    expect(out).not.toBe(pick);
    expect(pick).toEqual(['A', 'B']);
  });
  it('pruned first, a stale pick can no longer be revived by a fresh join; ggwJoinPick itself is unchanged', () => {
    expect(ggwJoinPick(['GONE'], ['N1'], ['N1'])).toEqual(['GONE']);   // the existing pin
    expect(ggwJoinPick(ggwPrunePick(['GONE', 'WETO'], ['SVRE', 'WETO']), ['SVRE', 'WETO'], [])).toEqual(['WETO']);
    expect(ggwJoinPick(ggwPrunePick(['GONE'], ['SVRE', 'WETO']), ['SVRE', 'WETO'], ['WETO'])).toBeNull();
  });
});

describe('ggwLivePick — the review residual', () => {
  it('a pick of only names added after pickAt → null (the pages)', () => {
    expect(ggwLivePick(['WETO'], ['WETO'])).toBeNull();
    expect(ggwLivePick(['WETO', 'X'], ['WETO', 'X'])).toBeNull();
  });
  it('NEGATIVE: any older name keeps the pick as it is (order kept); nothing after → unchanged; null/empty → null', () => {
    expect(ggwLivePick(['WETO', 'SVRE'], ['WETO'])).toEqual(['WETO', 'SVRE']);
    expect(ggwLivePick(['A', 'B'], [])).toEqual(['A', 'B']);
    expect(ggwLivePick(null, ['A'])).toBeNull();
    expect(ggwLivePick([], [])).toBeNull();
  });
});

