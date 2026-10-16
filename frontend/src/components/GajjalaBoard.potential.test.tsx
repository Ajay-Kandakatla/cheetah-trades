import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import golden from './__fixtures__/gajjala_potential_golden_2026_10_15.json';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';

/* 🧠 Potential + 📈 Track on Gajjala's board (2026-10-15, BUILD_SPEC4 §3.11 / WP-D).
 *
 * Ajay: "In Gajjalas setup I wanna find potential stocks this shows me what has
 * happened I am trying to setup for this tab to act like Gajjalas brain. So
 * create a potential category in this section." then "In all the sub tab and
 * add a track and alert to show me new potential is added everyday."
 *
 * Rendered from the GOLDEN fixture (written by backend tests/test_gajjala_potential_tab.py
 * — the served payload, never typed) and, once the main session captures it, the
 * LIVE fixture (gajjala_potential_live_2026_10_15.json; its tests SKIP while the
 * file is absent). The board composes no word and no number: every line below is
 * compared to a SERVED string. The negatives: no strip on ☀️ / 🌙 / 📓, the old
 * hand fixture (no potential keys) renders as before, an empty Track says the
 * served empty line, and no NaN / undefined / None / the b-word anywhere. */

const chartProps: any[] = [];
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({
  PatternChart: (props: any) => {
    chartProps.push(props);
    return <div data-testid={`chart-${props.tile.symbol}`} />;
  },
}));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: ({ symbol }: any) => <span data-testid={`short-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

/* tsc-safe source / fixture reads (the lib/gajjala.test precedent): the app's tsconfig carries no node
 * types, so `node:fs` is imported dynamically; paths are relative to frontend/ (vitest's cwd). */
async function fsMod(): Promise<any> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  return mod?.default || mod;
}
const root = (globalThis as any).process?.cwd?.() || '.';
async function readSource(rel: string): Promise<string> {
  return (await fsMod()).readFileSync(`${root}/${rel}`, 'utf8');
}
async function readJsonIfPresent(rel: string): Promise<any | null> {
  const fs = await fsMod();
  const p = `${root}/${rel}`;
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null;
}

const LIVE: any = await readJsonIfPresent('src/components/__fixtures__/gajjala_potential_live_2026_10_15.json');
const GOLD: Record<string, any> = (golden as any).boards;
const HAND: Record<string, any> = (hand as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

function stubFetch(pick: (url: URL) => any) {
  const spy = vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    return { ok: true, status: 200, json: async () => pick(u) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const from = (boards: Record<string, any>, fallback: string) =>
  (u: URL) => clone(boards[u.searchParams.get('sub') || fallback] || boards[fallback]);

let loc = { search: '' };
function Probe() {
  const l = useLocation();
  loc = { search: l.search };
  return null;
}
const mount = (q: string) => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /><Probe /></MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));

/** Every number printed must be part of some served string (the FE composes none). */
const NUM = /\d+(?:[.,:]\d+)*/g;
function numbersServed(rendered: string, served: string[]) {
  const pool = served.filter((s) => typeof s === 'string').join(' \u0000 ');
  for (const n of rendered.match(NUM) || []) expect(pool, `number ${n} is not in any served string`).toContain(n);
}
const BANNED = /NaN|undefined|\bNone\b|\[object Object\]/;
/** The house-banned word for a reversal, built so this file never spells it (identifiers excepted). */
const BWORD = new RegExp(['b', 'ounce'].join(''), 'i');

describe('GajjalaBoard — 🧠 Potential (golden fixture)', () => {
  beforeEach(() => { chartProps.length = 0; });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  // WIDENED 2026-10-16 — 🏁 Track record is the TENTH sub, LAST (Ajay "keep a new tab", BUILD_SPEC9 §3.11);
  // 🧠 Potential is btns[8] and keeps its served text.
  it('10 sub buttons on the golden payload — 🧠 Potential ninth, 🏁 Track record LAST, the other 8 in their served order', async () => {
    stubFetch(from(GOLD, 'potential'));
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    const btns = screen.getAllByRole('tab').filter((b) => b.getAttribute('data-testid')?.startsWith('gg-sub-'));
    expect(btns).toHaveLength(10);
    expect(btns.map((b) => b.getAttribute('data-testid'))).toEqual(GOLD.potential.subs.map((s: any) => `gg-sub-${s.key}`));
    expect(GOLD.potential.subs.map((s: any) => s.key).slice(0, 8)).toEqual(
      ['bull_flag', 'kiss_fly', 'horizontal_fade', 'intraday_vcp', 'reversal_squeeze', 'premarket', 'postmarket', 'playbook']);
    const pot = btns[8];
    const servedPot = GOLD.potential.subs[8];
    expect(servedPot.key).toBe('potential');
    expect(typeof servedPot.count).toBe('number');
    expect(pot.textContent).toBe(`${servedPot.emoji} ${servedPot.label} · ${servedPot.count}`);
    expect(pot.textContent).toMatch(/^\u{1F9E0} Potential/u);
    expect(pot).toHaveAttribute('aria-selected', 'true');
    const last = btns[btns.length - 1];
    const served = GOLD.potential.subs[GOLD.potential.subs.length - 1];
    expect(served.key).toBe('track_record');
    expect(typeof served.count).toBe('number');
    expect(last.textContent).toBe(`${served.emoji} ${served.label} · ${served.count}`);
    expect(last.textContent).toMatch(/^\u{1F3C1} Track record/u);
    expect(last).toHaveAttribute('aria-selected', 'false');
  });

  it('setup sub: the 🧠 strip — served title, served definition folded, rows in SERVED order with SERVED text', async () => {
    stubFetch(from(GOLD, 'bull_flag'));
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    const pot = GOLD.bull_flag.potential;
    const strip = screen.getByTestId('gg-potential');
    expect(screen.getByTestId('gg-potential-title').textContent).toBe(pot.title);
    expect(pot.title).toContain('UNMEASURED');
    const details = screen.getByTestId('gg-potential-title').closest('details')!;
    expect(details.hasAttribute('open')).toBe(false);                     // the definition is folded
    expect(within(details).getByTestId('gg-potential-text').textContent).toBe(pot.text);
    const rows = within(strip).getAllByTestId(/^gg-potential-row-/);
    expect(rows.map((r) => r.getAttribute('data-testid'))).toEqual(pot.rows.map((r: any) => `gg-potential-row-${r.symbol}`));
    pot.rows.forEach((r: any, i: number) => {
      // the row is the served line + the served tells, nothing composed between them
      expect(rows[i].textContent).toBe(r.text + (r.tells || []).map((t: any) => t.text).join(''));
      const badges = rows[i].querySelectorAll('.cm-badge.cm-badge-muted');
      expect([...badges].map((b) => b.textContent)).toEqual((r.tells || []).map((t: any) => t.text));
      expect([...badges].map((b) => b.getAttribute('title'))).toEqual((r.tells || []).map((t: any) => t.cite));
      expect(rows[i].querySelector('.gg-pot-kind')!.className).toContain(`gg-pot-kind-${r.kind}`);
    });
    // NEGATIVE: AAA is `again` and its served ↻ tell already says so — the ↻ is not printed twice.
    expect(pot.rows[0].again).toBe(true);
    expect(within(rows[0]).queryByTestId('gg-pot-again')).toBeNull();
    expect(screen.queryByTestId('gg-potential-empty')).toBeNull();
    // NEGATIVE: no Track / watch on a setup sub
    for (const id of ['gg-track', 'gg-watch']) expect(screen.queryByTestId(id)).toBeNull();
  });

  it('"↻" marks an `again` row only when no served ↻ tell carries it; NEGATIVE never on a not-again row', async () => {
    const b = clone(GOLD.bull_flag);
    b.potential.rows[0].tells = b.potential.rows[0].tells.filter((t: any) => t.key !== 'again');
    stubFetch(() => clone(b));
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    expect(within(screen.getByTestId('gg-potential-row-AAA')).getByTestId('gg-pot-again')).toHaveTextContent('↻');
    expect(b.potential.rows[1].again).toBe(false);
    expect(within(screen.getByTestId('gg-potential-row-JJJ')).queryByTestId('gg-pot-again')).toBeNull();
  });

  it('a strip row click writes `focus` (sub kept) and scrolls THAT tile once', async () => {
    const scrolled: string[] = [];
    (HTMLElement.prototype as any).scrollIntoView = function (this: HTMLElement) {
      scrolled.push(this.getAttribute('data-testid') || '');
    };
    const spy = stubFetch(from(GOLD, 'bull_flag'));
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    expect(scrolled).toEqual([]);
    fireEvent.click(screen.getByTestId('gg-potential-row-JJJ'));
    await waitFor(() => expect(new URLSearchParams(loc.search).get('focus')).toBe('JJJ'));
    expect(new URLSearchParams(loc.search).get('sub')).toBe('bull_flag');
    expect(new URLSearchParams(loc.search).get('tab')).toBe('gajjala');
    await waitFor(() => expect(scrolled).toEqual(['gg-tile-JJJ']));
    await waitFor(() => expect(spy.mock.calls.some((c) => String(c[0]).includes('focus=JJJ'))).toBe(true));
    expect(screen.getByTestId('gg-tile-JJJ').className).toContain('gg-focus');
    // NEGATIVE: the same row again does not re-scroll (once per focus value)
    fireEvent.click(screen.getByTestId('gg-potential-row-JJJ'));
    await screen.findByTestId('gg-tile-JJJ');
    expect(scrolled).toEqual(['gg-tile-JJJ']);
    delete (HTMLElement.prototype as any).scrollIntoView;
  });

  it('NEGATIVE: an empty strip shows the served empty_text and no row', async () => {
    const b = clone(GOLD.bull_flag);
    b.potential.rows = [];
    b.potential.empty_text = b.empty_note;                 // a served sentence, not one typed here
    stubFetch(() => clone(b));
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    expect(screen.getByTestId('gg-potential-empty').textContent).toBe(b.empty_note);
    expect(screen.queryAllByTestId(/^gg-potential-row-/)).toHaveLength(0);
  });

  it('🧠 sub: 📈 Track today (open) / yesterday (folded), timelines, the unmeasured line, 👀 links, the live push line', async () => {
    stubFetch(from(GOLD, 'potential'));
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    const tr = GOLD.potential.track;
    const track = screen.getByTestId('gg-track');
    expect(screen.getByTestId('gg-track-title').textContent).toBe(tr.title);
    expect(tr.title).toContain('UNMEASURED');
    const today = screen.getByTestId('gg-track-today');
    expect(today.hasAttribute('open')).toBe(true);
    const yday = screen.getByTestId('gg-track-yesterday');
    expect(yday.hasAttribute('open')).toBe(false);
    expect(yday.querySelector('summary')!.textContent).toBe(tr.yesterday.title);
    expect(screen.getByTestId('gg-track-unmeasured').textContent).toBe(tr.unmeasured);
    expect(screen.queryByTestId('gg-track-empty')).toBeNull();

    const tRows = within(today).getAllByTestId(/^gg-track-row-/);
    expect(tRows.map((r) => r.getAttribute('data-testid'))).toEqual(
      tr.today.rows.map((r: any) => `gg-track-row-${r.symbol}-${r.setup}`));
    const yRows = within(yday).getAllByTestId(/^gg-track-row-/);
    expect(yRows.map((r) => r.getAttribute('data-testid'))).toEqual(
      tr.yesterday.rows.map((r: any) => `gg-track-row-${r.symbol}-${r.setup}`));
    for (const r of [...tr.today.rows, ...tr.yesterday.rows]) {
      const id = `${r.symbol}-${r.setup}`;
      const row = within(track).getAllByTestId(`gg-track-row-${id}`)
        .find((el) => el.textContent?.startsWith(r.text))!;
      expect(row, id).toBeTruthy();
      const a = row.querySelector('a.gg-track-text')!;
      expect(a.textContent).toBe(r.text);
      expect(a.getAttribute('href')).toBe(r.href);
      if (r.vs_trigger_text) expect(row.textContent).toContain(r.vs_trigger_text);
      if (r.push_text) expect(within(row).getByTestId(`gg-track-push-${id}`).textContent).toBe(` · ${r.push_text}`);
      const tl = within(row).getByTestId(`gg-track-timeline-${id}`);
      expect(tl.tagName).toBe('DETAILS');
      expect([...tl.querySelectorAll('li')].map((li) => li.textContent)).toEqual(r.timeline.map((e: any) => e.text));
    }
    // a 🪦 graveyard entry and an A+ outcome are the served words
    expect(yday.textContent).toContain('🪦 graveyard');
    expect(today.textContent).toContain('A+ — broke the trigger');

    const w = GOLD.potential.watch;
    const watch = screen.getByTestId('gg-watch');
    expect(watch.textContent).toBe(w.text);                            // links replace the served names in place
    for (const s of w.symbols) expect(screen.getByTestId(`gg-watch-tk-${s.symbol}`).getAttribute('href')).toBe(s.href);

    expect(screen.getByTestId('gg-push').textContent).toBe(GOLD.potential.push.text);
    expect(screen.getByTestId('gg-push-potential').textContent).toBe(GOLD.potential.push_potential.text);
    // the A+ line says A+ stays shadow, the 🧠 line says live — never "nothing reaches"
    expect(screen.getByTestId('gg-push').textContent).toMatch(/A\+ pushes are in SHADOW/);
    expect(container.textContent).not.toMatch(/nothing (rings|reaches|is sent)/i);
    // NEGATIVE: no 🧠 strip on the 🧠 sub itself
    expect(screen.queryByTestId('gg-potential')).toBeNull();
  });

  it('🧠 sub tiles: PatternChart per symbol in SERVED order, each with its served potential pill and tells', async () => {
    stubFetch(from(GOLD, 'potential'));
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    const tiles = GOLD.potential.tiles;
    expect(screen.getAllByTestId(/^gg-tile-/).map((e) => e.getAttribute('data-testid'))).toEqual(
      tiles.map((t: any) => `gg-tile-${t.symbol}`));
    for (const t of tiles) {
      const el = screen.getByTestId(`gg-tile-${t.symbol}`);
      expect(within(el).getByTestId(`chart-${t.symbol}`)).toBeTruthy();
      const pill = within(el).getByTestId('gg-pot-kind');
      expect(pill.textContent).toBe(t.gajjala.potential.text);
      expect(pill.className).toContain(`gg-pot-kind-${t.gajjala.potential.kind}`);
      const tells = t.gajjala.potential.tells || [];
      if (tells.length) {
        expect([...within(el).getByTestId('gg-pot-tells').children].map((c) => c.textContent)).toEqual(tells.map((x: any) => x.text));
      } else {
        expect(within(el).queryByTestId('gg-pot-tells')).toBeNull();     // NEGATIVE: no tells → no empty badge row
      }
    }
    expect(new Set(chartProps.map((p) => p.tile.symbol))).toEqual(new Set(tiles.map((t: any) => t.symbol)));
  });

  it('D9: a joined row prints the served "joined mid-session" hold word on its Track row', async () => {
    const py = await readSource('../backend/chart_maps/gajjala/potential.py');
    const m = /"joined_midsession":\s*"([^"]+)"/.exec(py);
    expect(m, 'potential.HELD_WORDS joined_midsession').toBeTruthy();
    const b = clone(GOLD.potential);
    const row = b.track.today.rows[0];
    row.push_text = `held: ${m![1]}`;                         // what tab._track_row serves for a joined doc
    stubFetch(() => clone(b));
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    const id = `${row.symbol}-${row.setup}`;
    expect(screen.getByTestId(`gg-track-push-${id}`).textContent).toBe(` · held: ${m![1]}`);
    expect(m![1]).toMatch(/joined mid-session/);
    expect(m![1]).toMatch(/not ringing/);
  });

  it('NEGATIVE: an empty Track shows the served empty_today and no today row', async () => {
    const b = clone(GOLD.potential);
    b.track.today.rows = [];
    b.track.today.n = 0;
    stubFetch(() => clone(b));
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    expect(screen.getByTestId('gg-track-empty').textContent).toBe(b.track.empty_today);
    expect(within(screen.getByTestId('gg-track-today')).queryAllByTestId(/^gg-track-row-/)).toHaveLength(0);
    expect(screen.getByTestId('gg-track-unmeasured')).toBeTruthy();
  });

  it('NEGATIVE: no 🧠 strip on ☀️ / 🌙 / 📓 — even if a payload carried one', async () => {
    for (const sub of ['premarket', 'postmarket', 'playbook']) {
      const b = { ...clone(HAND[sub]), potential: clone(GOLD.bull_flag.potential), track: clone(GOLD.potential.track) };
      stubFetch(() => clone(b));
      const { container, unmount } = mount(`tab=gajjala&sub=${sub}`);
      await loaded(container);
      expect(screen.queryByTestId('gg-potential'), sub).toBeNull();
      expect(screen.queryByTestId('gg-track'), sub).toBeNull();
      unmount();
      vi.unstubAllGlobals();
    }
  });

  it('NEGATIVE: the old hand fixture (no potential keys) renders as before — no 🧠 surface anywhere', async () => {
    for (const sub of Object.keys(HAND)) {
      expect(HAND[sub].potential, sub).toBeUndefined();
      stubFetch(from(HAND, 'bull_flag'));
      const { container, unmount } = mount(`tab=gajjala&sub=${sub}`);
      await loaded(container);
      for (const id of ['gg-potential', 'gg-track', 'gg-watch', 'gg-push-potential', 'gg-pot-kind', 'gg-pot-tells']) {
        expect(screen.queryByTestId(id), `${sub} ${id}`).toBeNull();
      }
      expect(container.querySelector('[class*="gg-pot-"], .gg-track, .gg-watch'), sub).toBeNull();
      expect(screen.getAllByTestId(/^gg-sub-/)).toHaveLength(HAND[sub].subs.length);
      unmount();
      vi.unstubAllGlobals();
    }
  });

  it('NEGATIVE: the FE composes no number — every number in the strip and the Track is in a served string', async () => {
    stubFetch(from(GOLD, 'bull_flag'));
    let r = mount('tab=gajjala&sub=bull_flag');
    await loaded(r.container);
    const p = GOLD.bull_flag.potential;
    numbersServed(screen.getByTestId('gg-potential').textContent || '',
      [p.title, p.text, p.empty_text, ...p.rows.flatMap((x: any) => [x.text, ...(x.tells || []).map((t: any) => t.text)])]);
    r.unmount();
    vi.unstubAllGlobals();

    stubFetch(from(GOLD, 'potential'));
    r = mount('tab=gajjala&sub=potential');
    await loaded(r.container);
    const tr = GOLD.potential.track;
    const rows = [...tr.today.rows, ...tr.yesterday.rows];
    numbersServed(screen.getByTestId('gg-track').textContent || '',
      [tr.title, tr.unmeasured, tr.empty_today, tr.yesterday.title,
       ...rows.flatMap((x: any) => [x.text, x.vs_trigger_text, x.push_text, ...x.timeline.map((e: any) => e.text)])]);
    numbersServed(screen.getByTestId('gg-watch').textContent || '', [GOLD.potential.watch.text]);
    for (const t of GOLD.potential.tiles) {
      const el = screen.getByTestId(`gg-tile-${t.symbol}`).querySelector('.gg-pot-tile')!;
      numbersServed(el.textContent || '', [t.gajjala.potential.text, ...(t.gajjala.potential.tells || []).map((x: any) => x.text)]);
    }
  });

  it('NEGATIVE: never the b-word / NaN / undefined / None on every sub of the golden fixture', async () => {
    for (const sub of Object.keys(GOLD)) {
      stubFetch(from(GOLD, sub));
      const { container, unmount } = mount(`tab=gajjala&sub=${sub}`);
      await loaded(container);
      const txt = container.textContent || '';
      expect(txt, sub).not.toMatch(BWORD);
      expect(txt, sub).not.toMatch(BANNED);
      unmount();
      vi.unstubAllGlobals();
    }
  });
});

/* The LIVE capture (main session, BUILD_SPEC4 §5.3.3) — SKIPPED until the file exists. Before deploy its tracker is
 * empty, so `track` may be empty: these assert only what holds on any real payload. */
describe('GajjalaBoard — 🧠 Potential (live capture)', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
  const LB: Record<string, any> = LIVE?.boards || {};

  it.skipIf(!LIVE)('9 sub buttons, 🧠 Potential last; the live push line under the A+ line', async () => {
    stubFetch(from(LB, 'potential'));
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    const btns = screen.getAllByTestId(/^gg-sub-/);
    expect(btns).toHaveLength(9);
    expect(btns[8].getAttribute('data-testid')).toBe('gg-sub-potential');
    expect(screen.getByTestId('gg-push-potential').textContent).toBe(LB.potential.push_potential.text);
    expect(screen.getByTestId('gg-track')).toBeTruthy();
    const today = LB.potential.track?.today?.rows || [];
    if (!today.length) expect(screen.getByTestId('gg-track-empty').textContent).toBe(LB.potential.track.empty_today);
    expect(screen.getByTestId('gg-track-unmeasured')).toBeTruthy();
  });

  it.skipIf(!LIVE)('bull_flag strip rows in the SERVED order with the SERVED text (or the served empty line)', async () => {
    stubFetch(from(LB, 'bull_flag'));
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    const pot = LB.bull_flag.potential;
    expect(screen.getByTestId('gg-potential-title').textContent).toBe(pot.title);
    const rows = screen.queryAllByTestId(/^gg-potential-row-/);
    expect(rows.map((r) => r.getAttribute('data-testid'))).toEqual(pot.rows.map((r: any) => `gg-potential-row-${r.symbol}`));
    pot.rows.forEach((r: any, i: number) => expect(rows[i].textContent!.startsWith(r.text)).toBe(true));
    if (!pot.rows.length && pot.empty_text) expect(screen.getByTestId('gg-potential-empty').textContent).toBe(pot.empty_text);
  });

  it.skipIf(!LIVE)('NEGATIVE: never the b-word / NaN / undefined / None on every sub of the live capture', async () => {
    for (const sub of Object.keys(LB)) {
      stubFetch(from(LB, sub));
      const { container, unmount } = mount(`tab=gajjala&sub=${sub}`);
      await loaded(container);
      const txt = container.textContent || '';
      expect(txt, sub).not.toMatch(BWORD);
      expect(txt, sub).not.toMatch(BANNED);
      unmount();
      vi.unstubAllGlobals();
    }
  });
});
