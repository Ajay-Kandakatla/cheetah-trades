import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import golden from './__fixtures__/gajjala_potential_golden_2026_10_15.json';

/* ℹ️ the served legend for Gajjala's counts line and sub tabs (2026-10-18, DECISIONS15 D1–D3 / BUILD_SPEC15 WP-B).
 *
 * Ajay: "Ok Forming is still Criteria not met.. Potential is all the gajjalas criteria met. may be add an info tag for
 * them explicitly.. To tell me what athey are". The words are served by tab.count_legend (the ONE source); the board
 * prints them — each count's native title, one folded ⓘ under the counts line, the 🧠 sub button's title. The legend
 * rows below are SENTINELS ("served text for <key>"), so this file types no definition either: every assertion compares
 * the DOM to the served row. NEGATIVES: no served legend (absent / null / []) → today's markup; a served counts_text →
 * plain text, no spans; no definition phrase in GajjalaBoard.tsx. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({ PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: ({ symbol }: any) => <span data-testid={`short-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

/* tsc-safe source read (the GajjalaBoard.potential.test precedent): no node types in the app tsconfig. */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const GOLD: Record<string, any> = (golden as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

function stubFetch(pick: (url: URL) => any) {
  const spy = vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    return { ok: true, status: 200, json: async () => pick(u) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const mount = (q: string) => render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /></MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));

/* The served legend's keys in BUILD_SPEC15 A1 order (tab.LEGEND_KEYS = COUNT_STATES + awaiting_answer, listed, potential,
 * track); the words are the structural labels the counts line already prints. The texts are sentinels. */
const KEYS_WORDS: [string, string][] = [
  ['aplus', 'A+'], ['forming', 'forming'], ['partial', 'partial'], ['triggered', 'triggered'], ['stopped', 'stopped'],
  ['invalid', 'invalid'], ['none', 'none'], ['awaiting_answer', 'awaiting your number'], ['listed', 'listed'],
  ['potential', '\u{1F9E0} Potential'], ['track', '\u{1F4C8} Track'],
];
const LEGEND = KEYS_WORDS.map(([key, word]) => ({ key, word, text: `served text for ${key}` }));
const POT_TITLE = 'served text for potential';

/** `counts_legend` left OUT of the payload (an older API) — a default parameter would swallow `undefined`. */
const ABSENT = Symbol('absent');
/** A golden board with the served legend (and the 🧠 sub's served title) — or with `legend` as given (the negatives). */
function withLegend(sub: string, legend: any = LEGEND, extra: Record<string, any> = {}) {
  const b = clone(GOLD[sub] || GOLD.bull_flag);
  if (legend === ABSENT) delete b.counts_legend; else b.counts_legend = legend;
  b.subs = (b.subs || []).map((s: any) => {
    const t = { ...s };
    if (Array.isArray(legend) && legend.length) t.title = s.key === 'potential' ? POT_TITLE : null; else delete t.title;
    return t;
  });
  return { ...b, ...extra };
}

/** Today's counts line for the served counts — the structural words in the board's order, " · " joined. */
const TODAY_ORDER: [string, string][] = [
  ['aplus', 'A+'], ['triggered', 'triggered'], ['forming', 'forming'], ['partial', 'partial'], ['stopped', 'stopped'],
  ['invalid', 'invalid'], ['none', 'none'], ['awaiting_answer', 'awaiting your number'], ['listed', 'listed'],
];
const todayLine = (counts: Record<string, any>) =>
  TODAY_ORDER.filter(([k]) => typeof counts[k] === 'number').map(([k, w]) => `${w} ${counts[k]}`).join(' · ');

describe('GajjalaBoard — ℹ️ served counts legend (2026-10-18)', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  for (const sub of ['bull_flag', 'potential']) {
    it(`${sub}: every count span carries the served title, the line text is today's text`, async () => {
      const board = withLegend(sub);
      stubFetch(() => clone(board));
      const { container } = mount(`tab=gajjala&sub=${sub}`);
      await loaded(container);
      const line = screen.getByTestId('gg-counts');
      expect(line.textContent).toBe(todayLine(board.counts));
      const spans = within(line).getAllByTestId(/^gg-count-/);
      const counted = TODAY_ORDER.filter(([k]) => typeof board.counts[k] === 'number').map(([k]) => k);
      expect(counted.length).toBeGreaterThan(0);
      expect(spans.map((s) => s.getAttribute('data-testid'))).toEqual(counted.map((k) => `gg-count-${k}`));
      for (const s of spans) {
        const key = s.getAttribute('data-testid')!.replace('gg-count-', '');
        const row = LEGEND.find((r) => r.key === key)!;
        expect(s).toHaveAttribute('title', row.text);
        expect(s.textContent).toBe(`${row.word} ${board.counts[key]}`);
      }
    });
  }

  it('the ⓘ folds closed and lists EVERY served row in served order, served word then served text', async () => {
    stubFetch(() => withLegend('bull_flag'));
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    const det = screen.getByTestId('gg-counts-legend');
    expect(det.tagName).toBe('DETAILS');
    expect(det.hasAttribute('open')).toBe(false);
    expect(det.className).toContain('gg-aplus-note');
    expect(det.querySelector('summary')!.textContent).toBe('ⓘ');
    const rows = within(det).getAllByTestId(/^gg-legend-/);
    expect(rows.map((r) => r.getAttribute('data-testid'))).toEqual(LEGEND.map((r) => `gg-legend-${r.key}`));
    LEGEND.forEach((r, i) => {
      expect(rows[i].querySelector('strong')!.textContent).toBe(r.word);
      expect(rows[i].textContent).toBe(`${r.word} — ${r.text}`);
    });
    // potential + track are listed though neither is on the counts line
    expect(screen.queryByTestId('gg-count-potential')).toBeNull();
    expect(screen.queryByTestId('gg-count-track')).toBeNull();
    // right after the counts line
    expect(screen.getByTestId('gg-counts').nextElementSibling).toBe(det);
  });

  it('the 🧠 sub button carries the served title; NEGATIVE: no title on the other nine', async () => {
    const board = withLegend('potential');
    stubFetch(() => clone(board));
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    const btns = screen.getAllByRole('tab').filter((b) => b.getAttribute('data-testid')?.startsWith('gg-sub-'));
    expect(btns).toHaveLength(10);
    for (const b of btns) {
      if (b.getAttribute('data-testid') === 'gg-sub-potential') expect(b).toHaveAttribute('title', POT_TITLE);
      else expect(b.hasAttribute('title')).toBe(false);
    }
  });

  for (const [what, legend] of [['absent', ABSENT], ['null', null], ['[]', []]] as [string, any][]) {
    it(`NEGATIVE: counts_legend ${what} → no ⓘ, no spans, no titles, today's counts text`, async () => {
      const board = withLegend('bull_flag', legend);
      stubFetch(() => clone(board));
      const { container } = mount('tab=gajjala&sub=bull_flag');
      await loaded(container);
      expect(screen.queryByTestId('gg-counts-legend')).toBeNull();
      expect(container.querySelector('.gg-counts-legend')).toBeNull();
      const line = screen.getByTestId('gg-counts');
      expect(line.textContent).toBe(todayLine(board.counts));
      expect(line.children).toHaveLength(0);                        // plain text, as before
      expect(container.querySelector('[data-testid^="gg-count-"]')).toBeNull();
      expect(line.hasAttribute('title')).toBe(false);
      expect(screen.getByTestId('gg-sub-potential').hasAttribute('title')).toBe(false);
    });
  }

  it('NEGATIVE: an absent legend renders the same counts text as a served one', async () => {
    stubFetch(() => withLegend('bull_flag'));
    const a = mount('tab=gajjala&sub=bull_flag');
    await loaded(a.container);
    const withText = a.container.querySelector('[data-testid="gg-counts"]')!.textContent;
    a.unmount();
    vi.unstubAllGlobals();
    stubFetch(() => withLegend('bull_flag', ABSENT));
    const b = mount('tab=gajjala&sub=bull_flag');
    await loaded(b.container);
    expect(b.container.querySelector('[data-testid="gg-counts"]')!.textContent).toBe(withText);
  });

  it('NEGATIVE: a served counts_text still wins as plain text — no spans on the line', async () => {
    const TEXT = 'served counts sentence';
    stubFetch(() => withLegend('bull_flag', LEGEND, { counts_text: TEXT }));
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    const line = screen.getByTestId('gg-counts');
    expect(line.textContent).toBe(TEXT);
    expect(line.children).toHaveLength(0);
    expect(container.querySelector('[data-testid^="gg-count-"]')).toBeNull();
  });

  it('NEGATIVE: a malformed legend row (no text) is dropped, never printed as "undefined"', async () => {
    const bad = [...LEGEND.slice(0, 2), { key: 'partial', word: 'partial' }, null, ...LEGEND.slice(3)];
    stubFetch(() => withLegend('bull_flag', bad));
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    expect(screen.queryByTestId('gg-legend-partial')).toBeNull();
    expect(screen.getByTestId('gg-count-partial').hasAttribute('title')).toBe(false);
    expect(container.textContent).not.toMatch(/undefined|NaN|\[object Object\]/);
  });

  it('NEGATIVE: GajjalaBoard.tsx types no state definition — the words are served (DECISIONS15 D2)', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    for (const phrase of ['no rule has failed', 'every rule', 'a rule failed', 'criteria not met']) {
      expect(src.toLowerCase(), `GajjalaBoard.tsx types "${phrase}"`).not.toContain(phrase);
    }
    expect(src).toContain('gg-counts-legend');
    expect(src).toContain('counts_legend');
  });
});
