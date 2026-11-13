import { describe, it, expect } from 'vitest';
import { cardLadder, FOLD_GROUPS, type Ladder } from './cardLadder';
import type { CmStat, CmTile } from './chartMaps';

/* 💎 Under Value — the served `Rev quarter` stat (2026-11-12).
 *
 * Ajay, verbatim: "We got wrong numbers for Joby in sales in the undervalye
 * can you verfy". The board now serves the fiscal quarter each growth % comes
 * from under the key `Rev quarter` (board.UV_QUARTER_STAT_KEY). The ladder
 * routes an unknown key to SETUP on the face; `Growth` is a FOLD key and would
 * hide the quarter under ▸ more — the reason the served key is not `Growth`.
 * Strings only: the value passes through untouched. */

const OLDER = 'FY2026 Q2 (to 2026-06-30) · older than the P/S revenue (to 2026-09-30)';
const STALE = 'FY2021 Q1 (to 2021-03-31) · a latest filing 4 or more quarters past due';

const uvStats = (k: string, v: string): CmStat[] => [
  { k: 'P/S', v: '11.9x' },
  { k: 'Rev YoY', v: '+109%' },
  { k, v },
  { k: 'PSG', v: '0.109' },
  { k: 'Mkt cap', v: '$745M' },
];

const tile = (stats: CmStat[]): CmTile => ({
  symbol: 'CHEAP', href: '/sepa/CHEAP',
  bars: [{ t: '2026-11-12', o: 1, h: 2, l: 0.5, c: 1.5, v: 1 }],
  bands: [], lines: [], markers: [], stats, why: '',
});

const folded = (l: Ladder) =>
  FOLD_GROUPS.flatMap((g) => l.more[g].map((it) => it.stat?.k).filter(Boolean));

describe('💎 Rev quarter — served stat on the card face', () => {
  it('lands in SETUP, string-identical, in served order', () => {
    const l = cardLadder(tile(uvStats('Rev quarter', OLDER)));
    expect(l.setup.stats).toEqual(uvStats('Rev quarter', OLDER));
    expect(l.setup.stats.find((s) => s.k === 'Rev quarter')!.v).toBe(OLDER);
  });

  it('the stale-filing words land in SETUP string-identical', () => {
    const l = cardLadder(tile(uvStats('Rev quarter', STALE)));
    const s = l.setup.stats.find((x) => x.k === 'Rev quarter');
    expect(s?.v).toBe(STALE);
    expect(l.setup.stats.map((x) => x.k)).toEqual(['P/S', 'Rev YoY', 'Rev quarter', 'PSG', 'Mkt cap']);
  });

  it('is in no ▸ more group, and not in PLAN or TIMING', () => {
    const l = cardLadder(tile(uvStats('Rev quarter', OLDER)));
    expect(folded(l)).not.toContain('Rev quarter');
    expect(l.plan.stats.map((s) => s.k)).not.toContain('Rev quarter');
    expect(l.timing.stats.map((s) => s.k)).not.toContain('Rev quarter');
    expect(l.dropped).not.toContain('Rev quarter');
  });

  it('NEGATIVE: the same words keyed `Growth` fold into more.reads', () => {
    const l = cardLadder(tile(uvStats('Growth', OLDER)));
    expect(l.setup.stats.map((s) => s.k)).not.toContain('Growth');
    const reads = l.more.reads.filter((it) => it.stat?.k === 'Growth');
    expect(reads).toHaveLength(1);
    expect(reads[0].stat!.v).toBe(OLDER);
  });
});
