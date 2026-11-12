import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { CardLiveQuote } from '../lib/cardLive';
import type { LukTile } from '../lib/luk';

/* 🔴 🥇 Luk realtime cards — one card (2026-11-12, lukrt spec §3.5 / WP-D). Ajay, verbatim: "Luks scan is not realtime
 * I see all dated values can you make it realtime". LukCard splices its quote with cardLive.patchTile and prints the
 * served `vs.text` and `vs.pct_text` under the plan lines (each only when served, only on a card with a served
 * `live_level`); a served `not_rung_text` prints as a .luk-not-rung pill in the pills row. NEGATIVES: no quote → today's
 * card; a vs without pct_text → no pct line; a pct_text with no vs kind → nothing; a stopped card (live_level null) prints
 * no live words even when a vs is served; the state pill / data-state never move; a blank not_rung_text → no pill; the
 * source types no live or pill word; 📱 430 px — the new lines and the pill wrap, no inline style. */

const chartTiles: any[] = [];
vi.mock('./PatternChart', () => ({
  PatternChart: (p: any) => { chartTiles.push(p.tile); return <div data-testid={`chart-${p.tile.symbol}`} />; },
}));

import { LukCard } from './LukCard';

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

const VS = 'served vs words for HQ';
const PCT = 'served pct words for HQ';
const RUNG = 'served did-not-ring sentence';
const base = (extra: Record<string, unknown> = {}): LukTile => ({
  symbol: 'HQ', href: '/sepa/HQ', setup: 'opening_range_high', state: 'aplus', state_label: 'served A+ label',
  frame_text: 'hourly frame', trigger_text: 'trigger 4.10', stop_text: 'stop 3.90', criteria: [], chips: null, bars5: [],
  read_at_text: 'read at 09:46 ET', live_level: { trigger: 4.1, stop: 3.9, tf: '5m' }, ...extra,
} as LukTile);
const now = (price: number) => ({ price, label: 'now', session: null, add_line: true, as_of_epoch: 1, as_of: 'x' });
const quote = (vs: unknown): CardLiveQuote => ({ bar: null, prev_t: null, now: now(4.2), ...(vs === undefined ? {} : { vs }) } as CardLiveQuote);
const mount = (t: LukTile, live?: CardLiveQuote) =>
  render(<MemoryRouter><LukCard tile={t} live={live} nowLabels={['now']} /></MemoryRouter>);
const q = (c: HTMLElement, id: string) => c.querySelector(`[data-testid="${id}"]`) as HTMLElement | null;

describe('LukCard — 🔴 the served live words', () => {
  it('vs text and pct text print verbatim under the plan lines, in that order', () => {
    const { container } = mount(base(), quote({ kind: 'over_trigger', text: VS, pct_text: PCT }));
    expect(q(container, 'luk-live-HQ')!.textContent).toBe(VS);
    expect(q(container, 'luk-live-pct-HQ')!.textContent).toBe(PCT);
    const ids = Array.from(container.querySelectorAll('.luk-extras > p')).map((e) => e.getAttribute('data-testid'));
    expect(ids.slice(0, 4)).toEqual(['luk-trigger-HQ', 'luk-stop-HQ', 'luk-live-HQ', 'luk-live-pct-HQ']);
    expect(q(container, 'luk-live-HQ')!.className).toBe('luk-line luk-live');
  });

  it('NEGATIVE: no quote → today\'s card (no live line, no pct line)', () => {
    const { container } = mount(base());
    expect(q(container, 'luk-live-HQ')).toBeNull();
    expect(q(container, 'luk-live-pct-HQ')).toBeNull();
  });

  it('NEGATIVE: a vs without pct_text → the vs line only', () => {
    const { container } = mount(base(), quote({ kind: 'under_stop', text: VS }));
    expect(q(container, 'luk-live-HQ')!.textContent).toBe(VS);
    expect(q(container, 'luk-live-pct-HQ')).toBeNull();
  });

  for (const bad of [{ kind: '', text: VS, pct_text: PCT }, { text: VS, pct_text: PCT }, { kind: 'over_trigger', text: '  ', pct_text: PCT }, null]) {
    it(`NEGATIVE: an invalid vs ${JSON.stringify(bad)} → no live line and no pct line`, () => {
      const { container } = mount(base(), quote(bad));
      expect(q(container, 'luk-live-HQ')).toBeNull();
      expect(q(container, 'luk-live-pct-HQ')).toBeNull();
    });
  }

  for (const blank of ['', '   ', 7]) {
    it(`NEGATIVE: a ${JSON.stringify(blank)} pct_text → no pct line`, () => {
      const { container } = mount(base(), quote({ kind: 'between', text: VS, pct_text: blank }));
      expect(q(container, 'luk-live-HQ')!.textContent).toBe(VS);
      expect(q(container, 'luk-live-pct-HQ')).toBeNull();
    });
  }

  for (const lv of [null, undefined]) {
    it(`NEGATIVE: a stopped card (live_level ${String(lv)}) prints no live words even when a vs is served`, () => {
      const { container } = mount(base({ state: 'stopped', state_label: 'served stopped label', live_level: lv }),
        quote({ kind: 'under_stop', text: VS, pct_text: PCT }));
      expect(q(container, 'luk-live-HQ')).toBeNull();
      expect(q(container, 'luk-live-pct-HQ')).toBeNull();
    });
  }

  it('NEGATIVE: the quote never moves the state pill or data-state', () => {
    const a = mount(base());
    const b = mount(base(), quote({ kind: 'under_stop', text: VS, pct_text: PCT }));
    for (const c of [a.container, b.container]) {
      expect(q(c, 'luk-tile-HQ')!.getAttribute('data-state')).toBe('aplus');
      expect(q(c, 'luk-state-HQ')!.textContent).toBe('served A+ label');
    }
  });

  it('with bars: the now line moves on the drawn tile (patchTile) — intraday bars are never patched', () => {
    chartTiles.length = 0;
    const bars5 = [{ t: '2026-11-12T10:00:00-05:00', o: 4, h: 4.2, l: 3.95, c: 4.1, v: 1000 }];
    mount(base({ bars5 }), { bar: { t: '2026-11-12', o: 4, h: 4.3, l: 3.9, c: 4.2, v: 9e5 }, prev_t: null, now: now(4.2) } as CardLiveQuote);
    const t = chartTiles[chartTiles.length - 1];
    expect(t.bars).toEqual(bars5);
    expect(t.lines).toEqual([{ price: 4.2, label: 'now', tone: 'now' }]);
  });
});

describe('LukCard — 🔴 the served "did not ring" pill', () => {
  it('a served not_rung_text prints verbatim as a .luk-not-rung pill in the pills row', () => {
    const { container } = mount(base({ not_rung_text: RUNG }));
    const pill = q(container, 'luk-not-rung-HQ')!;
    expect(pill.textContent).toBe(RUNG);
    expect(pill.className).toBe('luk-not-rung');
    expect(pill.parentElement!.className).toBe('luk-pills');
    expect(q(container, 'luk-tile-HQ')!.getAttribute('data-state')).toBe('aplus');
  });
  for (const blank of [null, '', '   ', undefined]) {
    it(`NEGATIVE: not_rung_text ${JSON.stringify(blank)} → no pill (two pills, as before)`, () => {
      const { container } = mount(base({ not_rung_text: blank }));
      expect(q(container, 'luk-not-rung-HQ')).toBeNull();
      expect(container.querySelectorAll('.luk-pills > *')).toHaveLength(2);
    });
  }
});

describe('LukCard source + 📱 stylesheet — 🔴 live words and pill', () => {
  it('NEGATIVE: LukCard.tsx types no live or pill word (every one is served)', async () => {
    const src = await readSource('src/components/LukCard.tsx');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    for (const w of ['vs the', 'over the', 'under the', 'did not', 'not ring', '% vs']) expect(code).not.toContain(w);
    expect(code).toMatch(/patchTile\(lukChartTile\(t\), live, nowLabels \?\? \[\]\)/);
  });
  it('.luk-live wraps (min-width: 0, overflow-wrap: anywhere); .luk-not-rung is a pill; it joins the ONE-line chip-wrap list', async () => {
    const src = await readSource('src/styles/luk.css');
    const live = rule(src, /\.luk-live/);
    expect(live).not.toBeNull();
    expect(live).toMatch(/min-width:\s*0\b/);
    expect(live).toMatch(/overflow-wrap:\s*anywhere/);
    const pill = rule(src, /\.luk-not-rung/);
    expect(pill).not.toBeNull();
    expect(pill).toMatch(/border-radius:\s*999px/);
    const m = src.match(/\n([^{}\n]*\.luk-chip-row \.cm-badge[^{}\n]*)\{([^}]*)\}/);
    expect(m).not.toBeNull();
    expect(m![1]).toContain('.luk-pills .luk-not-rung');
    expect(m![2]).toMatch(/white-space:\s*normal/);
  });
  it('NEGATIVE: a stylesheet without the rules fails the same matchers', () => {
    expect(rule('.luk-line { margin: 0; }', /\.luk-live/)).toBeNull();
    expect(rule('.luk-line { margin: 0; }', /\.luk-not-rung/)).toBeNull();
  });
  it('📱 430 px: the live lines and the pill carry no inline style', () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 430 });
    const long = 'served very long live words that must wrap on a phone and never widen the card · '.repeat(4);
    const { container } = mount(base({ not_rung_text: long }), quote({ kind: 'between', text: long, pct_text: long }));
    for (const id of ['luk-live-HQ', 'luk-live-pct-HQ', 'luk-not-rung-HQ']) {
      expect(q(container, id)).not.toBeNull();
      expect(q(container, id)!.getAttribute('style')).toBeNull();
    }
  });
});
