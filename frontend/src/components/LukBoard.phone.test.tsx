/**
 * 📱 🥇 Luk's on the phone (2026-11-01, luk spec §3.13 / §6). Ajay reads the app at 430 px (iPhone 14 Pro Max); the 🚩
 * 2026-10-19 lesson: a .cm-grid item's default `min-width: auto` lets ONE unbreakable served chip set the card's
 * minimum and push the chart off the screen. jsdom has no layout, so these are SOURCE guards on the stylesheet the
 * board imports (the GajjalaBoard.phone pattern) plus DOM guards on the classes the card carries. NEGATIVES: the
 * pre-fix stylesheet fails each matcher; no element carries an inline width / nowrap / horizontal-overflow attribute.
 */
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import LukBoard from './LukBoard';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const css = (): Promise<string> => readSource('src/styles/luk.css');

function rule(src: string, selector: RegExp): string | null {
  const m = src.match(new RegExp(`(^|\\n)\\s*${selector.source}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}
/** The rule whose selector list carries `.luk-chip-row .cm-badge` (the served chips). */
function chipWrapRule(src: string): { selectors: string; decl: string } | null {
  const m = src.match(/\n([^{}\n]*\.luk-chip-row \.cm-badge[^{}\n]*)\{([^}]*)\}/);
  return m ? { selectors: m[1], decl: m[2] } : null;
}
const PRE_FIX = `.luk-card { border-radius: 8px; }
.luk-chip-row { display: flex; gap: 0.25rem; }`;

describe('📱 Luk card — never wider than its grid column', () => {
  it('.luk-card carries min-width: 0 and max-width: 100%', async () => {
    const decl = rule(await css(), /\.luk-card/);
    expect(decl).not.toBeNull();
    expect(decl).toMatch(/min-width:\s*0\b/);
    expect(decl).toMatch(/max-width:\s*100%/);
  });
  it('NEGATIVE: the pre-fix rule fails the same matcher', () => {
    const decl = rule(PRE_FIX, /\.luk-card/);
    expect(decl).not.toMatch(/min-width:\s*0\b/);
  });
});

describe('📱 Luk chips — wrap instead of widening the card', () => {
  it('the chip row wraps and every served chip / state pill breaks anywhere', async () => {
    const src = await css();
    expect(rule(src, /\.luk-chip-row/)).toMatch(/flex-wrap:\s*wrap/);
    const r = chipWrapRule(src);
    expect(r).not.toBeNull();
    for (const sel of ['.luk-chip-row .cm-badge', '.luk-pills .luk-state']) expect(r!.selectors).toContain(sel);
    expect(r!.decl).toMatch(/white-space:\s*normal/);
    expect(r!.decl).toMatch(/overflow-wrap:\s*anywhere/);
  });
  it('NEGATIVE: the pre-fix stylesheet has no wrap and no chip-wrap rule', () => {
    expect(rule(PRE_FIX, /\.luk-chip-row/)).not.toMatch(/flex-wrap:\s*wrap/);
    expect(chipWrapRule(PRE_FIX)).toBeNull();
  });
  it('the scan table scrolls inside its own box, never the page', async () => {
    expect(rule(await css(), /\.luk-table-wrap/)).toMatch(/overflow-x:\s*auto/);
  });
});

describe('📱 Luk board DOM at 430 px', () => {
  afterEach(() => { vi.unstubAllGlobals(); });
  it('cards sit in the wrapping chip row; NEGATIVE: no inline width, no nowrap, no horizontal-overflow attribute', async () => {
    const LONG = 'flag #1 today · a very long unbreakable served chip text that would widen the card on a phone if it could not wrap';
    const board = { tab: 'luk', title: 'T', sub: 'pullback_reversal', subs: [{ key: 'pullback_reversal', label: 'Pullback reversal', n: 1 }],
      tiles: [{ symbol: 'AAA', setup: 'pullback_reversal', state: 'aplus', state_label: 'A+', trigger_text: 'trigger 1',
        chips: { tier_text: LONG, adr_text: LONG, screens_text: LONG }, criteria: [], bars5: [] }] };
    vi.stubGlobal('fetch', vi.fn(async (u: string) => ({ ok: true, status: 200,
      json: async () => (String(u).includes('/chart-maps/luk') ? board : {}) })));
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 430 });
    const { container } = render(<MemoryRouter initialEntries={['/chart-maps?tab=luk']}><LukBoard /></MemoryRouter>);
    await waitFor(() => expect(container.querySelector('.luk-board[data-state="loaded"]')).not.toBeNull());
    const card = container.querySelector('[data-testid="luk-tile-AAA"]')!;
    expect(card.className).toMatch(/\bluk-card\b/);
    const row = container.querySelector('[data-testid="luk-chips-AAA"]')!;
    expect(row.className).toMatch(/\bluk-chip-row\b/);
    expect(row.querySelectorAll('.cm-badge')).toHaveLength(3);
    for (const el of Array.from(container.querySelectorAll('*'))) {
      const st = (el as HTMLElement).getAttribute('style') || '';
      expect(st).not.toMatch(/(^|;)\s*(min-)?width\s*:|white-space\s*:\s*nowrap|overflow-x\s*:\s*(scroll|visible)/);
      expect(el.getAttribute('nowrap')).toBeNull();
    }
  });
});
