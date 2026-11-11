import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { LukCard } from './LukCard';
import type { LukTile } from '../lib/luk';

/* 🥇 Luk — the "not re-read" tag on a card (2026-11-11, lukstale spec §3.2 / §3.3 / §3.5, WP-FE). The server compares
 * the card's read stamp with the latest pass's and serves `not_reread` + `not_reread_text`; the card prints the served
 * sentence as an amber .luk-not-reread pill beside the state pill and drops the plain bottom read-at line (the pill
 * carries the same time). Strictly `=== true`; the FE types no word. NEGATIVES: false / blank / absent / truthy
 * non-boolean → no pill and today's card; the source types no tag word; the pre-change stylesheet has no pill rule. */

const SENT = 'not re-read since 09:46 ET';
const READ = 'read at 09:46 ET';
const base = (extra: Record<string, unknown> = {}): LukTile => ({
  symbol: 'HQ', href: '/sepa/HQ', setup: 'opening_range_high', state: 'aplus', state_label: 'A+',
  frame_text: 'hourly frame', trigger_text: 'trigger 4.10', stop_text: 'stop 3.90', criteria: [], chips: null,
  bars5: [], read_at_text: READ, ...extra,
} as LukTile);
const mount = (t: LukTile) => render(<MemoryRouter><LukCard tile={t} /></MemoryRouter>);

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
function rule(src: string, selector: RegExp): string | null {
  const m = src.match(new RegExp(`(^|\\n)\\s*${selector.source}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}

/** today's card (no tag): no pill, the plain read-at line, no data-not-reread. */
function expectUntagged(container: HTMLElement) {
  expect(container.querySelector('[data-testid="luk-not-reread-HQ"]')).toBeNull();
  expect(container.querySelector('.luk-not-reread')).toBeNull();
  expect(container.querySelector('[data-testid="luk-read-at-HQ"]')!.textContent).toBe(READ);
  expect(container.querySelector('[data-testid="luk-tile-HQ"]')!.getAttribute('data-not-reread')).toBeNull();
}

describe('LukCard — the served not-re-read pill', () => {
  it('tagged: the served sentence verbatim in an amber .luk-not-reread pill inside .luk-pills; data-not-reread="true"; NO read-at line', () => {
    const { container } = mount(base({ not_reread: true, not_reread_text: SENT }));
    const pill = container.querySelector('[data-testid="luk-not-reread-HQ"]') as HTMLElement;
    expect(pill).not.toBeNull();
    expect(pill.textContent).toBe(SENT);
    expect(pill.className).toBe('luk-not-reread');
    expect(pill.parentElement!.className).toBe('luk-pills');
    // beside the state pill (after the frame pill)
    const pills = Array.from(pill.parentElement!.children).map((e) => e.getAttribute('data-testid'));
    expect(pills).toEqual(['luk-state-HQ', 'luk-frame-HQ', 'luk-not-reread-HQ']);
    expect(container.querySelector('[data-testid="luk-tile-HQ"]')!.getAttribute('data-not-reread')).toBe('true');
    expect(container.querySelector('[data-testid="luk-read-at-HQ"]')).toBeNull();
  });

  it('NEGATIVE: not_reread false with a served sentence → no pill, the read-at line prints, no data-not-reread', () => {
    expectUntagged(mount(base({ not_reread: false, not_reread_text: SENT })).container);
  });

  for (const blank of [null, '', '   ']) {
    it(`NEGATIVE: not_reread true with a ${JSON.stringify(blank)} sentence → no pill (no typed fallback), the plain line prints`, () => {
      expectUntagged(mount(base({ not_reread: true, not_reread_text: blank })).container);
    });
  }

  it('NEGATIVE: both keys absent (an older api) → exactly today\'s card', () => {
    const { container } = mount(base());
    expectUntagged(container);
    const { container: tagged } = mount(base({ not_reread: true, not_reread_text: SENT }));
    // the only differences a tag makes: the pill, the attribute, the dropped line.
    expect(container.querySelectorAll('.luk-pills > *')).toHaveLength(2);
    expect(tagged.querySelectorAll('.luk-pills > *')).toHaveLength(3);
  });

  for (const truthy of ['true', 1] as const) {
    it(`NEGATIVE: a truthy non-boolean not_reread (${JSON.stringify(truthy)}) → no pill`, () => {
      expectUntagged(mount(base({ not_reread: truthy as unknown as boolean, not_reread_text: SENT })).container);
    });
  }
});

describe('LukCard source + stylesheet — the pill', () => {
  it('NEGATIVE: LukCard.tsx types none of the tag words and no b-word in code', async () => {
    const src = await readSource('src/components/LukCard.tsx');
    for (const w of ['re-read', 'not re', 'since']) expect(src).not.toContain(w);
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    expect(code).not.toMatch(new RegExp('b' + 'ounce', 'i'));
    expect(src).toMatch(/t\.not_reread === true \? lukText\(t\.not_reread_text\) : null/);
  });

  it('a .luk-not-reread rule exists in luk.css (pill shape, house amber); NEGATIVE: the pre-change stylesheet has none', async () => {
    const decl = rule(await readSource('src/styles/luk.css'), /\.luk-not-reread/);
    expect(decl).not.toBeNull();
    expect(decl).toMatch(/border-radius:\s*999px/);
    expect(decl).toMatch(/var\(--gold/);
    const PRE = `.luk-pills { display: flex; flex-wrap: wrap; gap: 0.3rem; min-width: 0; }
.luk-frame {
  display: inline-block; padding: 0.08rem 0.45rem; border-radius: 999px;
}`;
    expect(rule(PRE, /\.luk-not-reread/)).toBeNull();
  });
});
