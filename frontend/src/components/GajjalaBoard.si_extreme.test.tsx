import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import type { GgVariantKey } from './ggVariant';

/* 🩳 EXTREME short-interest note on the 🎾 card, on the REAL board (2026-11-18, spec sinote WP fe-card).
 *
 * Ajay 2026-11-18: "When there are extreme cases of short interest make a not for them on reversal squeeze like
 * percentage of short interest on the tickers card and also on watch list"
 *
 * ONE line per card (Rule #5, critique C4): GgShortInterestLabel prints the SERVED `extreme.text` in place of the chip
 * when the read carries one — GajjalaBoard.tsx is not edited. The GajjalaBoard.cardLabels pattern: the real chip and
 * the real label both read the stubbed /short-interest/map (./ShortInterestChip is NOT mocked), boards are CLONES of
 * the frozen 2026-10-13 hand fixture. The threshold lives in read.py — nothing here compares a number. */

vi.mock('./PatternChart', () => ({
  PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} />,
}));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => {} }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const BOARDS: Record<string, any> = (fixture as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

const SQ = 'FCHL';
const BF = 'PFAI';
const SQ_CHIP = '🩳 SI 21.9% float · 1.0d · 10/15';            // byte-equal to the cardLabels pin
const BF_CHIP = '🩳 SI 4.2% float · 2.3d · 10/15';
const TITLE = '🩳 Short interest — FINRA settlement 2026-10-15 (published ~2026-10-24). A count of open short positions — not a forecast.';
const X_TEXT = '🩳 EXTREME SI 21.9% float · 1.0d · 10/15';
const X_TITLE = '🩳 EXTREME short interest — served hover sentence (SI_HIGH_PCT heuristic, SI-doc float). Not advice.';
const extreme = (text = X_TEXT) => ({ text, short: '🩳 EXTREME SI 21.9% float', title: X_TITLE, basis: 'si_doc_float' });

let SI: Record<string, unknown> = {};
const block = (sym: string, chip: string | null, status = 'ok', x: unknown = null) =>
  ({ symbol: sym, status, chip, title: TITLE, rows: [], extreme: x });

function board(patch: (b: any) => void = () => {}): any {
  const b = clone(BOARDS.reversal_squeeze);
  b.session = { ...b.session, refresh_sec: 0 };
  b.tiles = [clone(BOARDS.reversal_squeeze.tiles[0]), clone(BOARDS.bull_flag.tiles[0])];
  b.tiles[0].gajjala.plan_text = 'Entry above 3.42 · stop 3.18 · risk 7.0%';
  b.tiles[1].gajjala.plan_text = 'Entry above 4.12 · stop 3.95 · risk 4.1%';
  patch(b);
  return b;
}

let siCalls: string[] = [];
function stub(payload: any) {
  siCalls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/short-interest/map')) {
      siCalls.push(String(url));
      const q = (u.searchParams.get('symbols') || '').split(',');
      const items: Record<string, unknown> = {};
      for (const s of q) if (SI[s]) items[s] = SI[s];
      return ok({ items, n: Object.keys(items).length, max_symbols: 200 });
    }
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.includes('/chart-maps/gajjala')) return ok(payload);
    return ok({});
  }));
}

async function mount(payload: any, variant: GgVariantKey) {
  stub(payload);
  const r = render(
    <MemoryRouter initialEntries={[`/chart-maps?tab=${variant}&sub=reversal_squeeze`]}>
      <GajjalaBoard variant={variant} />
    </MemoryRouter>,
  );
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  await screen.findByTestId(`gg-tile-${SQ}`);
  return r;
}
const settleSi = () => waitFor(() => expect(siCalls.length).toBeGreaterThan(0)).then(() => new Promise((r) => setTimeout(r, 20)));
/** Elements in `root` whose OWN text starts with the 🩳 glyph (leaf-most: no descendant element also starts with it). */
function glyphLines(root: Element): Element[] {
  return Array.from(root.querySelectorAll('*')).filter((el) =>
    (el.textContent || '').trimStart().startsWith('🩳')
    && !Array.from(el.children).some((c) => (c.textContent || '').trimStart().startsWith('🩳')));
}

for (const variant of ['gajjala', 'gajjala_audited'] as const) {
  const pay = () => board((b) => { b.tab = variant; });

  describe(`🩳 EXTREME note on the 🎾 card — ${variant}`, () => {
    beforeEach(() => {
      _resetShortInterestCache();
      SI = { [SQ]: block(SQ, SQ_CHIP, 'ok', extreme()), [BF]: block(BF, BF_CHIP, 'ok', extreme('🩳 EXTREME SI 4.2% float · 2.3d · 10/15')) };
    });
    afterEach(() => { vi.unstubAllGlobals(); });

    it('the label prints the served extreme.text, bold-warn class, served title — and the 🩳 glyph ONCE in the card', async () => {
      await mount(pay(), variant);
      const el = await screen.findByTestId(`gg-si-label-${SQ}`);
      await waitFor(() => expect(el.textContent).toBe(X_TEXT));
      expect(el.className).toBe('cm-note gg-line gg-si-label gg-si-extreme');
      expect(el.getAttribute('title')).toBe(X_TITLE);
      expect(el.getAttribute('data-si-basis')).toBe('si_doc_float');
      const card = screen.getByTestId(`gg-tile-${SQ}`);
      expect(glyphLines(card)).toEqual([el]);
      expect((card.textContent || '').split('🩳').length - 1).toBe(1);
      expect(card.textContent).not.toContain(SQ_CHIP);
      expect(within(screen.getByTestId(`gg-chips-${SQ}`)).queryByTestId('si-chip')).toBeNull();
    });

    it('the card DOM order is unchanged — the label still sits right under the plan, above the K-rule list', async () => {
      await mount(pay(), variant);
      const el = await screen.findByTestId(`gg-si-label-${SQ}`);
      await waitFor(() => expect(el.className).toContain('gg-si-extreme'));
      const extras = within(screen.getByTestId(`gg-tile-${SQ}`)).getByTestId('gg-extras');
      expect(extras.contains(el)).toBe(true);
      expect(within(extras).getByTestId('gg-plan').nextElementSibling).toBe(el);
      expect(el.nextElementSibling?.getAttribute('data-testid')).toBe('gg-criteria');
    });

    it('NEGATIVE: the bull_flag card with an extreme block keeps its muted CHIP text — no note anywhere in it', async () => {
      await mount(pay(), variant);
      const card = screen.getByTestId(`gg-tile-${BF}`);
      const chip = await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
      expect(chip.textContent).toBe(BF_CHIP);
      expect(chip.className).toBe('cm-badge cm-badge-muted');
      expect(card.querySelector('.gg-si-extreme')).toBeNull();
      expect(card.textContent).not.toContain('EXTREME');
      expect(screen.queryByTestId(`gg-si-label-${BF}`)).toBeNull();
    });

    it('NEGATIVE: FCHL with extreme null → the label text === SQ_CHIP byte-equal, no gg-si-extreme', async () => {
      SI[SQ] = block(SQ, SQ_CHIP, 'ok', null);
      await mount(pay(), variant);
      const el = await screen.findByTestId(`gg-si-label-${SQ}`);
      expect(el.textContent).toBe(SQ_CHIP);
      expect(el.className).toBe('cm-note gg-line gg-si-label');
      expect(el.hasAttribute('data-si-basis')).toBe(false);
      expect(document.querySelector('.gg-si-extreme')).toBeNull();
    });

    it('NEGATIVE: FCHL stale carrying an extreme object → the stale chip, never the note', async () => {
      SI[SQ] = block(SQ, '🩳 SI 30.6% float · 5.0d · 8/31 · stale', 'stale', extreme());
      await mount(pay(), variant);
      const el = await screen.findByTestId(`gg-si-label-${SQ}`);
      expect(el.textContent).toBe('🩳 SI 30.6% float · 5.0d · 8/31 · stale');
      expect(el.className).toBe('cm-note gg-line gg-si-label gg-si-stale');
      expect(screen.getByTestId(`gg-tile-${SQ}`).querySelector('.gg-si-extreme')).toBeNull();
    });

    it('NEGATIVE: FCHL no_record → nothing on the card, never the note, never a 0', async () => {
      SI[SQ] = { symbol: SQ, status: 'no_record', chip: null, title: 'no FINRA record — not read.', rows: [], extreme: null };
      await mount(pay(), variant);
      await settleSi();
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
      expect(screen.queryByTestId(`gg-si-label-${SQ}`)).toBeNull();
      const card = screen.getByTestId(`gg-tile-${SQ}`);
      expect(card.textContent).not.toContain('🩳');
      expect(card.textContent).not.toMatch(/SI 0|(^|[^\d.])0(\.0)?%/);
    });

    it('ONE /short-interest/map GET for the whole board (label + chip share the hook)', async () => {
      await mount(pay(), variant);
      await waitFor(() => expect(screen.getByTestId(`gg-si-label-${SQ}`).className).toContain('gg-si-extreme'));
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
      expect(siCalls).toHaveLength(1);
      const syms = new URL(siCalls[0], 'http://x').searchParams.get('symbols')!.split(',').sort();
      expect(syms).toEqual([BF, SQ].sort());
    });
  });
}

/* Source guards — jsdom has no layout; the tsc-safe file read of GajjalaBoard.phone.test.tsx, inlined. */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const extremeRule = (src: string): string | null => {
  const m = src.match(/(^|\n)\s*\.gg-si-extreme\s*\{([^}]*)\}/);
  return m ? m[2] : null;
};
const ggCardRule = (src: string): string | null => {
  const m = src.match(/(^|\n)\s*\.gg-card\s*\{([^}]*)\}/);
  return m ? m[2] : null;
};
const wrapAnywhereRule = (src: string): string | null => {
  const m = src.match(/\n([^{}\n]*\.gg-criteria li[^{}\n]*)\{([^}]*overflow-wrap:\s*anywhere[^}]*)\}/);
  return m ? m[1] : null;
};
const PRE_FIX = `.gg-card { border-radius: 8px; }
.gg-line { margin: 0; }
.gg-si-label { font-weight: 600; }`;

describe('📱 🩳 EXTREME note on the phone — source guards on gajjala.css', () => {
  it('the .gg-si-extreme rule exists, bold 700 in the warn colour', async () => {
    const decl = extremeRule(await readSource('src/styles/gajjala.css'));
    expect(decl).not.toBeNull();
    expect(decl).toMatch(/font-weight:\s*700/);
    expect(decl).toMatch(/color:\s*var\(--warn/);
    expect(decl).not.toMatch(/white-space:\s*nowrap/);
  });

  it('.gg-line is still in the overflow-wrap: anywhere list and .gg-card still has min-width: 0', async () => {
    const src = await readSource('src/styles/gajjala.css');
    expect(wrapAnywhereRule(src)).toContain('.gg-line');
    expect(ggCardRule(src)).toMatch(/min-width:\s*0\b/);
  });

  it('NEGATIVE: a stylesheet without the rule fails the same matchers', () => {
    expect(extremeRule(PRE_FIX)).toBeNull();
    expect(wrapAnywhereRule(PRE_FIX)).toBeNull();
    expect(ggCardRule(PRE_FIX)).not.toMatch(/min-width:\s*0\b/);
  });
});

describe('🩳 SOURCE GUARD — the card note lives in the label, GajjalaBoard.tsx is untouched', () => {
  const MOUNTS = [
    "import { GgShortInterestLabel } from './GgShortInterestLabel';",
    "read.setup === 'reversal_squeeze' ? <GgShortInterestLabel",
    "t.gajjala?.setup !== 'reversal_squeeze' ? <>{' '}<ShortInterestChip",
  ];

  it('GajjalaBoard.tsx keeps the three 11-08 mount strings byte-for-byte and never mounts GgSiExtremeNote', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    for (const m of MOUNTS) expect(src).toContain(m);
    expect(src).not.toContain('GgSiExtremeNote');
  });

  it('the label reads the note through the lib (siExtreme) and compares no SI number itself', async () => {
    const src = await readSource('src/components/GgShortInterestLabel.tsx');
    expect(src).toContain('siExtreme(read)');
    expect(src).not.toMatch(/(pct_of_float|pct_of_shares_out|days_to_cover)/);
    expect(src).not.toMatch(/SI_HIGH_PCT\s*[<>=]/);
  });

  it('NEGATIVE: a board source that mounts GgSiExtremeNote or drops a mount string fails the guard', () => {
    const bad = `${MOUNTS[0]}\n${MOUNTS[1]}\nimport { GgSiExtremeNote } from './GgSiExtremeNote';`;
    expect(bad).toContain('GgSiExtremeNote');
    expect(MOUNTS.every((m) => bad.includes(m))).toBe(false);
  });
});
