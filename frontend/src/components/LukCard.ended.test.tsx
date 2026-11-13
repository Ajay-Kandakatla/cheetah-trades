import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { LukCard } from './LukCard';
import type { LukTile } from '../lib/luk';

/* 🏁 2026-11-12 — ended cards fold, the card half (lukend spec §3.7 / WP-B test 2). Ajay, verbatim: "Is this still good
 * ro enter? From Luks" → "I shouldn't be seeing this" → "I want it to be realtime".
 * A served `trade_text` prints as a .luk-trade pill in the pills row; a card with `ended` strictly true prints its served
 * `ended_text` first in the extras and, when latched by the live poll, the served `ended_vs_text`. Every word is a
 * stand-in for a served string. NEGATIVES: an ended_text with ended !== true prints nothing; no trade_text → no pill;
 * blank served strings print nothing; the source types no fold word. */

const TRADE = 'served window sentence 10:30';
const ENDED = 'served ended sentence 112.32';
const VS = 'served live vs words 112.10';
const base = (extra: Record<string, unknown> = {}): LukTile => ({
  symbol: 'MSTR', href: '/sepa/MSTR', setup: 'pullback_reversal', state: 'triggered', state_label: 'triggered earlier',
  frame_text: '1-minute candle', trigger_text: 'trigger 114.31', stop_text: 'stop 112.32', criteria: [], chips: null,
  bars5: [], read_at_text: 'read at 16:01 ET', ...extra,
} as LukTile);
const mount = (t: LukTile) => render(<MemoryRouter><LukCard tile={t} /></MemoryRouter>);

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('LukCard — the served trade pill', () => {
  it('a served trade_text prints verbatim as a .luk-trade pill inside .luk-pills, after the state pill', () => {
    const { container } = mount(base({ trade_text: TRADE }));
    const pill = container.querySelector('[data-testid="luk-trade-MSTR"]') as HTMLElement;
    expect(pill).not.toBeNull();
    expect(pill.textContent).toBe(TRADE);
    expect(pill.className).toBe('luk-trade');
    expect(pill.parentElement!.className).toBe('luk-pills');
    const ids = Array.from(pill.parentElement!.children).map((e) => e.getAttribute('data-testid'));
    expect(ids).toEqual(['luk-state-MSTR', 'luk-frame-MSTR', 'luk-trade-MSTR']);
    expect(container.querySelector('[data-testid="luk-tile-MSTR"]')!.getAttribute('data-ended')).toBeNull();
  });
  for (const v of [undefined, null, '', '   ']) {
    it(`NEGATIVE: trade_text ${JSON.stringify(v)} → no pill`, () => {
      const { container } = mount(base({ trade_text: v }));
      expect(container.querySelector('[data-testid="luk-trade-MSTR"]')).toBeNull();
      expect(container.querySelector('.luk-trade')).toBeNull();
    });
  }
});

describe('LukCard — the served ended lines', () => {
  it('ended true: the served ended_text first in .luk-extras, then the served vs words; data-ended="true"', () => {
    const { container } = mount(base({ ended: true, ended_text: ENDED, ended_vs_text: VS }));
    const line = container.querySelector('[data-testid="luk-ended-MSTR"]') as HTMLElement;
    expect(line.textContent).toBe(ENDED);
    expect(line.className).toBe('luk-line luk-ended-line');
    const extras = container.querySelector('.luk-extras')!;
    expect(extras.firstElementChild).toBe(line);
    const vs = container.querySelector('[data-testid="luk-ended-vs-MSTR"]') as HTMLElement;
    expect(vs.textContent).toBe(VS);
    expect(vs.className).toBe('luk-line luk-live');
    expect(line.nextElementSibling).toBe(vs);
    expect(container.querySelector('[data-testid="luk-tile-MSTR"]')!.getAttribute('data-ended')).toBe('true');
  });
  it('ended true from the server (no vs words): the ended line only', () => {
    const { container } = mount(base({ ended: true, ended_text: ENDED }));
    expect(container.querySelector('[data-testid="luk-ended-MSTR"]')!.textContent).toBe(ENDED);
    expect(container.querySelector('[data-testid="luk-ended-vs-MSTR"]')).toBeNull();
  });
  for (const ended of [false, null, undefined, 'true', 1]) {
    it(`NEGATIVE: ended ${JSON.stringify(ended)} with a served ended_text → no ended line, no vs line, no data-ended`, () => {
      const { container } = mount(base({ ended, ended_text: ENDED, ended_vs_text: VS }));
      expect(container.querySelector('[data-testid="luk-ended-MSTR"]')).toBeNull();
      expect(container.querySelector('[data-testid="luk-ended-vs-MSTR"]')).toBeNull();
      expect(container.querySelector('.luk-ended-line')).toBeNull();
      expect(container.querySelector('[data-testid="luk-tile-MSTR"]')!.getAttribute('data-ended')).toBeNull();
    });
  }
  it('NEGATIVE: ended true with a blank ended_text → no ended line (no typed fallback)', () => {
    const { container } = mount(base({ ended: true, ended_text: '  ' }));
    expect(container.querySelector('[data-testid="luk-ended-MSTR"]')).toBeNull();
  });
  it('NEGATIVE: no fold key at all (an older api) → the card has no .luk-trade and no ended line', () => {
    const { container } = mount(base());
    expect(container.querySelectorAll('.luk-pills > *')).toHaveLength(2);
    expect(container.querySelector('.luk-ended-line')).toBeNull();
  });
});

describe('LukCard source — no fold word typed', () => {
  it('NEGATIVE: none of the tag / fold words anywhere in LukCard.tsx (comments included)', async () => {
    const src = await readSource('src/components/LukCard.tsx');
    for (const w of ['since', 're-read', 'not re', 'entry window', 'not an entry', 'open trade', "Luk's exit",
      'ended today', 'official close']) expect(src).not.toContain(w);
    expect(src).toMatch(/const ended = t\.ended === true;/);
  });
});
