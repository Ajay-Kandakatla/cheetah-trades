/* /alerts — the 🎪 Promo tag on 🚩 Gajjala's rows (2026-10-29, BUILD_SPEC32 D4).
 *
 * Ajay 2026-10-29: "should we pull stocks from PROMO circuit by default every day ... I do wanna run them against
 * Gajjalas strategies". A row of the 🚩 shadow A+ list or the 🧠 potentials list whose name came from (or is also on)
 * the Promo circuit carries the SERVED `promo_text`; this page prints it through the board's ONE chip component
 * (GgTraderChip, its own module since 2026-10-29) and types no word. Fixtures are synthetic; PROMO stands in for the backend's words.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';
import { GAJJALA_POTENTIAL_KEYS, GajjalaShadowList, GgPotentialList, ggPotentialChipText } from './Alerts';

async function readSource(rel: string): Promise<string> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fs: any = mod?.default || mod;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const tsCode = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '').replace(/(^|\s)\/\/[^\n]*/g, '$1')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, '');

const TODAY = '2026-10-29';
const PROMO = '\u{1F3AA} promo · first tag 09:41 ET · @served_handle (S)';
const pot = (extra: Record<string, unknown> = {}) => ({
  date: TODAY, symbol: 'MXCT', setup: 'bull_flag', at: '2026-10-29T10:41:00-04:00', kind: 'armed',
  text: 'MXCT · line', url: null, push_state: null, push_at: null, held: null, ...extra,
});
const shadow = (extra: Record<string, unknown> = {}) => ({
  date: TODAY, symbol: 'QQQX', setup: 'bull_flag', at: '2026-10-29T10:46:00-04:00', trigger: 2.5, stop: 2.2,
  text: 'QQQX · bull flag · trigger 2.50 · stop 2.20', url: null, note: 'shadow — not sent', ...extra,
});
const mountPot = (items: any[]) => render(<MemoryRouter><GgPotentialList items={items} today={TODAY} /></MemoryRouter>);
const mountShadow = (items: any[]) => render(<MemoryRouter><GajjalaShadowList items={items} today={TODAY} /></MemoryRouter>);

describe('/alerts — 🎪 the served promo chip on 🚩 Gajjala rows', () => {
  afterEach(() => cleanup());

  it('a 🧠 potential row carrying promo_text prints it verbatim, after the row line, inside the row', () => {
    const { container } = mountPot([pot({ promo: true, promo_text: PROMO }), pot({ symbol: 'NOPE', text: 'NOPE · line' })]);
    const chip = screen.getByTestId('gg-alert-promo-pot-MXCT-bull_flag');
    expect(chip.textContent).toBe(PROMO);
    expect(chip.classList.contains('gg-promo')).toBe(true);
    expect(chip.classList.contains('cm-badge')).toBe(true);
    expect(chip.closest('[data-testid="gg-pot-row"]')).not.toBeNull();
    expect(screen.queryByTestId('gg-alert-promo-pot-NOPE-bull_flag')).toBeNull();   // NEGATIVE the untagged row
    expect(container.querySelectorAll('.gg-promo').length).toBe(1);
    expect(container.querySelectorAll('.gg-trader').length).toBe(0);               // no 📌 chip invented
  });

  it('a 🚩 shadow A+ row carrying promo_text prints it verbatim', () => {
    mountShadow([shadow({ promo_text: PROMO })]);
    const chip = screen.getByTestId('gg-alert-promo-shadow-QQQX-bull_flag');
    expect(chip.textContent).toBe(PROMO);
    expect(chip.closest('[data-testid="gg-shadow-row"]')).not.toBeNull();
  });

  for (const [name, v] of [['absent (the promo bool alone)', undefined], ['null', null], ['empty', ''], ['whitespace', '  '], ['a number', 3]] as const) {
    it(`NEGATIVE: ${name} promo_text → no chip on either list`, () => {
      const extra = v === undefined ? { promo: true } : { promo: true, promo_text: v };
      const a = mountPot([pot(extra)]);
      expect(a.container.querySelectorAll('.gg-promo').length).toBe(0);
      cleanup();
      const b = mountShadow([shadow(extra)]);
      expect(b.container.querySelectorAll('.gg-promo').length).toBe(0);
      expect(document.querySelectorAll('[data-testid^="gg-alert-promo-"]').length).toBe(0);
    });
  }

  it('NEGATIVE: Alerts.tsx reuses the board chip (no second copy) and types no 🎪 in code', async () => {
    const src = await readSource('src/pages/Alerts.tsx');
    // 2026-10-29: chip module — the ONE chip is imported from its own module (moved, not loosened).
    expect(src).toMatch(/^import \{ GgTraderChip \} from '\.\.\/components\/GgTraderChip';$/m);
    expect((src.match(/<GgTraderChip promoText=\{it\.promo_text\}/g) || []).length).toBe(2);
    expect(src).not.toMatch(/function Gg(Promo|Trader)Chip\(/);
    expect(tsCode(src)).not.toContain('\u{1F3AA}');
  });

  // 2026-10-29: chip module — /alerts is a code-split route: importing the board would pull GajjalaBoard, PatternChart,
  // the board hooks and gajjala.css into the /alerts chunk.
  it('NEGATIVE: Alerts.tsx imports nothing from GajjalaBoard, PatternChart or gajjala.css', async () => {
    const code = tsCode(await readSource('src/pages/Alerts.tsx'));
    const specs = [...code.matchAll(/(?:from|import)\s*\(?\s*'([^'\n]+)'/g)].map((m) => m[1]);
    expect(specs).toContain('../components/GgTraderChip');
    for (const s of specs) expect(s).not.toMatch(/GajjalaBoard|PatternChart|gajjala\.css/);
  });
});

/* critic F3 (2026-10-29): the served `promo_held_text` was never printed — 'promo_held' was not a chip key, so the
 * count showed only in the "Also counted" hover. SERVED stands in for backend promo_names.PROMO_HOLD_TEXT. */
describe('/alerts — the 🎪 hold counter prints its served words', () => {
  const SERVED = 'held: SERVED-PROMO-HOLD-WORDS';

  it('promo_held is a 🧠 counter chip, worded from the served pass text', () => {
    expect(GAJJALA_POTENTIAL_KEYS).toContain('promo_held');
    expect(ggPotentialChipText('promo_held', 2, null, SERVED)).toBe(`2 ${SERVED}`);
  });

  it('NEGATIVE: the 📌 words never word the 🎪 chip, and the 🎪 words never word the 📌 one', () => {
    expect(ggPotentialChipText('promo_held', 2, SERVED, null)).toBe('2 promo held');
    expect(ggPotentialChipText('trader_held', 2, null, SERVED)).toBe('2 trader held');
  });

  it('NEGATIVE: no served words (an older API) → the generic counter words, never invented ones', () => {
    for (const t of [null, undefined, '', '  ']) expect(ggPotentialChipText('promo_held', 3, null, t)).toBe('3 promo held');
    expect(ggPotentialChipText('muted', 1, null, SERVED)).toBe('1 held: his first 15 minutes');
  });

  it('the strip hands the served pass words to the chip', async () => {
    const src = await readSource('src/pages/Alerts.tsx');
    expect(src).toContain('ggPotentialChipText(k, n, pass?.trader_held_text, pass?.promo_held_text)');
    expect(tsCode(src)).not.toMatch(/listed and read|volume floor/);
  });
});
