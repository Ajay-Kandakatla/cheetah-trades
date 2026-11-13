/**
 * 📱 📅 Long Term on the phone (2026-11-12, long-term spec §3.13). Ajay reads the app at 430 px (iPhone 14 Pro Max); the
 * 🚩 2026-10-19 lesson: a grid item's default `min-width: auto` lets ONE unbreakable served word set the card's minimum
 * and push the page sideways. jsdom has no layout, so these are SOURCE guards on the stylesheet the board imports (the
 * LukBoard.phone pattern) plus DOM guards on the classes the cards carry. NEGATIVES: a pre-fix stylesheet fails each
 * matcher; no element carries an inline width / no-wrap style.
 */
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from '../lib/__fixtures__/longTerm.payload.json';

vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => null }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => null }));

import LongTermBoard from './LongTermBoard';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const css = (): Promise<string> => readSource('src/styles/longTerm.css');

function rule(src: string, selector: RegExp): string | null {
  const m = src.match(new RegExp(`(^|\\n)\\s*${selector.source}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}
/** The rule whose selector list carries `.lt-pill` (the served pills / fields / lines wrap rule). */
function wrapRule(src: string): { selectors: string; decl: string } | null {
  const m = src.match(/\n([^{}\n]*\.lt-pill[,\s][^{}\n]*)\{([^}]*)\}/);
  return m ? { selectors: m[1], decl: m[2] } : null;
}
const PRE_FIX = `.lt-table-wrap { max-width: 100%; }
.lt-pills { display: flex; gap: 0.25rem; }
.lt-pill, .lt-field { white-space: nowrap; }`;

describe('📱 Long Term table (2026-11-13) — scrolls inside its own box, never the page', () => {
  it('.lt-table-wrap carries min-width: 0, max-width: 100% and overflow-x: auto', async () => {
    const decl = rule(await css(), /\.lt-table-wrap/);
    expect(decl).not.toBeNull();
    expect(decl).toMatch(/min-width:\s*0\b/);
    expect(decl).toMatch(/max-width:\s*100%/);
    expect(decl).toMatch(/overflow-x:\s*auto/);
  });
  it('NEGATIVE: the pre-fix rule fails the same matcher', () => {
    const decl = rule(PRE_FIX, /\.lt-table-wrap/);
    expect(decl).not.toMatch(/min-width:\s*0\b/);
    expect(decl).not.toMatch(/overflow-x:\s*auto/);
  });
  it('NEGATIVE: the old card grid rules are gone', async () => {
    const src = await css();
    expect(rule(src, /\.lt-grid/)).toBeNull();
    expect(rule(src, /\.lt-card/)).toBeNull();
  });
});

describe('📱 Long Term pills / fields / lines — wrap instead of widening the card', () => {
  it('pills, house chips and fields rows wrap; every pill / field / line / strip item breaks anywhere', async () => {
    const src = await css();
    expect(rule(src, /\.lt-pills, \.lt-house-chips, \.lt-fields/)).toMatch(/flex-wrap:\s*wrap/);
    expect(rule(src, /\.lt-strip/)).toMatch(/flex-wrap:\s*wrap/);
    const r = wrapRule(src);
    expect(r).not.toBeNull();
    for (const sel of ['.lt-pill', '.lt-field', '.lt-line', '.lt-status', '.lt-strip-item', '.lt-house-chips .cm-badge']) {
      expect(r!.selectors).toContain(sel);
    }
    expect(r!.decl).toMatch(/white-space:\s*normal/);
    expect(r!.decl).toMatch(/overflow-wrap:\s*anywhere/);
  });
  it('NEGATIVE: the stylesheet never sets nowrap (the pre-fix sample does, and is caught)', async () => {
    expect(await css()).not.toMatch(/nowrap/);
    expect(PRE_FIX).toMatch(/nowrap/);
  });
});

describe('📱 Long Term DOM — every saved row is a table row; nothing inline widens it', () => {
  afterEach(() => { vi.unstubAllGlobals(); });
  it('every saved row is an .lt-tr inside .lt-table-wrap; NEGATIVE: no .lt-card and no inline width / nowrap / overflow style', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(fixture)) })));
    const { container } = render(<MemoryRouter initialEntries={['/chart-maps?tab=long_term']}><LongTermBoard /></MemoryRouter>);
    await waitFor(() => expect(container.querySelector('.lt-board[data-state="ready"]')).not.toBeNull());
    const rows = container.querySelectorAll('.lt-table-wrap .lt-tr');
    expect(rows.length).toBe(8);
    expect(container.querySelectorAll('.lt-card').length).toBe(0);
    for (const el of container.querySelectorAll('[style]')) {
      expect(el.getAttribute('style') || '').not.toMatch(/width|nowrap|overflow/i);
    }
  });
});

/* 🔔 the zone block in the 🧭 section (2026-11-12, pkzone spec §3.9): the block and each of its list items can shrink and
 * wrap at 430 px. jsdom has no layout engine, so the right-edge check below holds trivially there (0 ≤ 0); the binding
 * guards are the stylesheet rules and the absence of any inline width / no-wrap style. */
const PRE_FIX_ALERT = `.lt-alert { display: flex; }
.lt-alert li { white-space: nowrap; }`;

describe('📱 🔔 zone block — items shrink and wrap at 430 px', () => {
  afterEach(() => { vi.unstubAllGlobals(); });
  it('.lt-alert and .lt-alert li carry min-width: 0, max-width: 100% and overflow-wrap: anywhere', async () => {
    const src = await css();
    for (const sel of [/\.lt-alert/, /\.lt-alert li/]) {
      const decl = rule(src, sel);
      expect(decl, sel.source).not.toBeNull();
      expect(decl).toMatch(/min-width:\s*0\b/);
      expect(decl).toMatch(/max-width:\s*100%/);
      expect(decl).toMatch(/overflow-wrap:\s*anywhere/);
    }
    expect(rule(src, /\.lt-alert li/)).toMatch(/white-space:\s*normal/);
  });
  it('NEGATIVE: the pre-fix block rules fail the same matchers', () => {
    expect(rule(PRE_FIX_ALERT, /\.lt-alert/)).not.toMatch(/min-width:\s*0\b/);
    const li = rule(PRE_FIX_ALERT, /\.lt-alert li/)!;
    expect(li).not.toMatch(/overflow-wrap:\s*anywhere/);
    expect(li).toMatch(/nowrap/);
  });
  it('DOM: every 🔔 item is an .lt-line inside .lt-alert, right edge ≤ the board width; NEGATIVE: no inline style', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(fixture)) })));
    const { container } = render(<MemoryRouter initialEntries={['/chart-maps?tab=long_term']}><LongTermBoard /></MemoryRouter>);
    await waitFor(() => expect(container.querySelector('.lt-board[data-state="ready"]')).not.toBeNull());
    const block = container.querySelector('.lt-alert');
    expect(block).not.toBeNull();
    const items = block!.querySelectorAll('li');
    expect(items.length).toBe(fixture.zones.alert.now.length + fixture.zones.alert.log.length);
    const board = container.querySelector('.lt-board') as HTMLElement;
    for (const li of items) {
      expect(li.className).toMatch(/\blt-line\b/);
      expect(li.getBoundingClientRect().right).toBeLessThanOrEqual(board.clientWidth);
    }
    for (const el of block!.querySelectorAll('[style]')) {
      expect(el.getAttribute('style') || '').not.toMatch(/width|nowrap|overflow/i);
    }
  });
});
