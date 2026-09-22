/* 🔥 Hottest — the WIDTH story of the 🌀 AMD column (2026-09-22).
 *
 * Ajay: *"last column is hidded"*. The column moved out of last place the same
 * day. The move shipped with an arithmetic width model in the `visibleCols`
 * comment and in both docs — a table "floor", a box width, a per-column width
 * for Next ER — computed from MEASURED character counts and ASSUMED
 * per-character advances, with no browser ever opened. Rule #1 does not take a
 * model for a measurement. The same paragraph then used those numbers to
 * decide that Next ER was the column he could afford to lose.
 *
 * Two things are wrong with that and both are pinned here:
 *
 *  1. A number nobody measured does not get printed with a tilde in front of
 *     it. The character counts stay — they came off the live payload — and so
 *     do `styles.css`'s own `min-width` declarations, because those are source.
 *     Every figure from the model is gone.
 *  2. Which of HIS columns gives way on a narrow window is a board decision.
 *     The move changed the scroll POSITION, not the scroll: the table has up to
 *     twelve columns against a 900px floor and it ran off the right edge before
 *     🌀 shipped too. The question is his, and it is open.
 *
 * And the phone: 🌀 now sits between the name and the ranked legs, so on the
 * ≤720px layout every ranked leg is one column further right than it was.
 * Which columns a phone shows is his call as well — so the media block may
 * adjust this cell's SIZE and nothing else. A `display: none` or a
 * `white-space: normal` landing there is the silent pick this file catches.
 *
 * The same guards run on the docs from `backend/tests/test_hottest_amd.py` §24.
 */
import { describe, expect, it } from 'vitest';
import { HS_COLS, PRE_COL, visibleCols } from './HottestSectors';
import { AMD_COL } from '../lib/hottestAmd';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const TSX = 'src/components/HottestSectors.tsx';
const CSS = 'src/styles.css';

/** Every figure the arithmetic model produced. None was measured. */
const MODELLED = ['1,074px', '1074px', '943px', '131px', '107px',
                  '176px', '151px', '~25px', '19% of the deficit'];

/** Sentences that hand one of HIS columns to the bin. */
const WRITES_OFF_A_COLUMN = ['right one to sacrifice', 'one to sacrifice',
                             'look up on the ticker page', 'second-widest',
                             'takes the clip'];

/** The `@media (max-width: 720px)` block that owns the 🔥 table. */
function media720(css: string): string {
  const anchor = css.indexOf('.hs-table { min-width: 760px');
  expect(anchor, 'the 🔥 table lost its 720px override').toBeGreaterThan(-1);
  const start = css.lastIndexOf('@media (max-width: 720px) {', anchor);
  expect(start, 'no 720px media block around the 🔥 override').toBeGreaterThan(-1);
  let depth = 0;
  for (let i = start; i < css.length; i += 1) {
    if (css[i] === '{') depth += 1;
    else if (css[i] === '}') {
      depth -= 1;
      if (depth === 0) return css.slice(start, i + 1);
    }
  }
  throw new Error('the 720px media block is unterminated');
}

describe('🌀 AMD column — the width story carries no invented number', () => {
  it('NEGATIVE: no modelled px figure survives in the component', async () => {
    const tsx = await readSource(TSX);
    for (const fig of MODELLED) {
      expect(tsx, `HottestSectors.tsx still quotes the modelled ${fig}`)
        .not.toContain(fig);
    }
  });

  it('NEGATIVE: the component writes off none of his columns', async () => {
    const tsx = (await readSource(TSX)).toLowerCase();
    for (const phrase of WRITES_OFF_A_COLUMN) {
      expect(tsx, `HottestSectors.tsx still writes off a column: ${phrase}`)
        .not.toContain(phrase);
    }
  });

  it('says what the move actually bought, and hands the rest to him', async () => {
    const tsx = await readSource(TSX);
    const start = tsx.indexOf('/** The columns actually printed');
    const comment = tsx.slice(start, tsx.indexOf('export function visibleCols'));
    expect(comment).toContain('THIS DOES NOT MAKE THE TABLE FIT');
    expect(comment).toContain('SCROLL POSITION');
    // the numbers it IS allowed to state are styles.css's own
    expect(comment).toContain('min-width: 900px');
    expect(comment).toContain('TWELVE columns');
    // and both open questions go to the his-call list, not to a decision here
    expect(comment).toContain('HIS decision');
    expect(comment).toContain('docs/rotation/hottest_expand_all_2026_09_22.md');
    expect(comment).toContain('his-call list');
  });

  it('names the PRE-OPEN day header as the widest state, and is right', async () => {
    const tsx = await readSource(TSX);
    const start = tsx.indexOf('/** The columns actually printed');
    const comment = tsx.slice(start, tsx.indexOf('export function visibleCols'));
    // the model never accounted for it, and it is the state the board is in
    // every time he opens it before the open
    expect(comment).toContain('Last close YYYY-MM-DD');
    expect(comment).toContain('d1.live');
    // the claim has to be true of the code it cites
    expect(tsx).toContain("if (d?.d1?.live) return 'Today';");
    expect(tsx).toContain('Last close ${day}');
  });
});

describe('🌀 AMD column — the phone layout was not picked silently', () => {
  it('NEGATIVE: the 720px block only resizes the cell', async () => {
    const block = media720(await readSource(CSS));
    expect(block).toContain('.hs-amd { font-size: 0.70rem; }');
    const rules = block.match(/\.hs-amd[^{]*\{[^}]*\}/g) || [];
    expect(rules.length, 'the 720px block lost its .hs-amd rule')
      .toBeGreaterThan(0);
    for (const rule of rules) {
      const body = rule.slice(rule.indexOf('{')).toLowerCase();
      expect(body, `a phone layout was picked silently: ${rule}`)
        .not.toContain('display');
      expect(body, `a phone layout was picked silently: ${rule}`)
        .not.toContain('white-space');
      expect(body, `a phone layout was picked silently: ${rule}`)
        .not.toContain('visibility');
    }
  });

  it('NEGATIVE: the 720px block hides no column of this table', async () => {
    const block = media720(await readSource(CSS));
    expect(block).not.toContain('display: none');
    expect(block).not.toContain('display:none');
  });

  it('pins the structural cost the comment claims: every ranked leg moves one right',
     () => {
    const amd = { amd_summary: { available: true } } as any;
    const withAmd = visibleCols(amd).map((c) => c.key);
    const without = visibleCols(null).map((c) => c.key);
    expect(withAmd[0]).toBe(AMD_COL.key);
    expect(without[0]).toBe(HS_COLS[0].key);
    // one column, uniformly, for every leg — that is the whole phone finding
    for (const c of HS_COLS) {
      expect(withAmd.indexOf(c.key)).toBe(without.indexOf(c.key) + 1);
    }
    // and with ☀️ Pre-mkt drawn too, the ranked legs stay contiguous
    const both = visibleCols({ pre: { show: true }, ...amd } as any).map((c) => c.key);
    expect(both).toEqual([AMD_COL.key, PRE_COL.key, ...HS_COLS.map((c) => c.key)]);
  });
});
