import { cleanup, render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import golden from './__fixtures__/gajjala_potential_golden_2026_10_15.json';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import gg1 from './__fixtures__/gajjala_1m_board_2026_10_27.json';
import { patchTiles, type CardLiveAnswer } from '../lib/cardLive';

/* 🧭 Setup stages on every Gajjala card (2026-11-11, stages spec §3.5 / §5.2, WP-ST-FE).
 *
 * Ajay 2026-11-11: "Another big thing I need is what stages a stock has crossed in the past like Bullflag -> EMA Kiss
 * and Fly -> and Horizontal -Fade so I know their stages may be add them like tags or some UI to show me stages with
 * time stamps if its same day"
 *
 * Boards: in-file CLONES of the served goldens with `gajjala.stages` hand-added (the §3.4 shape) to two tiles — one with
 * two sessions, one not-today (`clock: false`, no clock in any text). Every word below is test data standing in for
 * the served words; the FE types none. NEGATIVES: no block / empty groups / non-string title → nothing; a tag with
 * empty or non-string text is skipped, a group left with no tag is skipped; the live overlay keeps the key; a
 * not-today group prints no clock the payload did not carry; GgStages.tsx carries no step word, arrow or title. */

vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: null, loading: false }) }));
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
import { GgStages } from './GgStages';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const clone = (x: any) => JSON.parse(JSON.stringify(x));
const GOLD: Record<string, any> = (golden as any).boards;
const HAND: Record<string, any> = (hand as any).boards;
const GG1: Record<string, any> = (gg1 as any).boards;

/* ---- the served blocks (test data, §3.4 shape) ---- */
const TWO_DAYS = {
  title: '\u{1F9ED} Setup stages',
  hint: 'served hint — the setups this stock passed through, oldest first',
  sep: ' \u2192 ',
  groups: [
    { date: '2026-10-09', label: 'Fri 10-09', clock: false, tags: [
      { setup: 'kiss_fly', emoji: '\u{1F48B}', label: 'EMA Kiss & Fly', here: false,
        steps: [{ stage: 'potential', word: '\u{1F9E0} potential', at_et: null }],
        text: '\u{1F48B} EMA Kiss & Fly · \u{1F9E0} potential' },
    ] },
    { date: '2026-10-13', label: 'today', clock: true, tags: [
      { setup: 'horizontal_fade', emoji: '\u2796', label: 'Horizontal Fade', here: false,
        steps: [{ stage: 'potential', word: '\u{1F9E0} potential', at_et: '09:52' }],
        text: '\u2796 Horizontal Fade · \u{1F9E0} potential 09:52' },
      { setup: 'bull_flag', emoji: '\u{1F6A9}', label: 'Bull Flag', here: true,
        steps: [{ stage: 'potential', word: '\u{1F9E0} potential', at_et: '10:31' },
                { stage: 'aplus', word: '\u{1F3AF} A+', at_et: '10:41' }],
        text: '\u{1F6A9} Bull Flag · \u{1F9E0} potential 10:31 · \u{1F3AF} A+ 10:41' },
    ] },
  ],
  text: 'Fri 10-09: \u{1F48B} EMA Kiss & Fly · \u{1F9E0} potential \u2192 today: \u2796 Horizontal Fade · \u{1F9E0} potential 09:52 \u2192 \u{1F6A9} Bull Flag · \u{1F9E0} potential 10:31 · \u{1F3AF} A+ 10:41',
};
const NOT_TODAY = {
  title: '\u{1F9ED} Setup stages',
  hint: 'served hint — earlier sessions show the date only',
  sep: ' \u2192 ',
  groups: [
    { date: '2026-10-12', label: 'Mon 10-12', clock: false, tags: [
      { setup: 'bull_flag', emoji: '\u{1F6A9}', label: 'Bull Flag', here: false,
        steps: [{ stage: 'potential', word: '\u{1F9E0} potential', at_et: null },
                { stage: 'stopped', word: 'stopped', at_et: null }],
        text: '\u{1F6A9} Bull Flag · \u{1F9E0} potential · stopped' },
    ] },
  ],
  text: 'Mon 10-12: \u{1F6A9} Bull Flag · \u{1F9E0} potential · stopped',
};
const servedWords = (b: any): string[] => [b.title, b.hint, b.sep, b.text,
  ...b.groups.flatMap((g: any) => [g.label, ...g.tags.map((t: any) => t.text)])];

/** A board clone with `stages` hand-added to the named tiles (other tiles untouched). */
function withStages(board: any, add: Record<string, any>): any {
  const b = clone(board);
  b.session = { ...(b.session || {}), refresh_sec: 0 };
  // the golden's own cards carry served stages since 2026-11-11 — a card not named in `add` gets none here
  b.tiles = (b.tiles || []).map((t: any) => (t.gajjala
    ? { ...t, gajjala: { ...t.gajjala, stages: add[t.symbol] ? clone(add[t.symbol]) : null } } : t));
  return b;
}

let board: (u: URL) => any = () => ({});
function stub() {
  const spy = vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.endsWith('/entry-tape')) return ok({ id: 'x', bars: [], rules: [], lite: true });
    if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) return ok(board(u));
    if (u.pathname.endsWith('/supply-demand/rules')) return ok({ sections: {} });
    return ok({});
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const mount = (q: string, variant?: 'gajjala' | 'gajjala_1m' | 'gajjala_audited') => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}>
    {variant ? <GajjalaBoard variant={variant} /> : <GajjalaBoard />}
  </MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
const row = (c: HTMLElement, sym: string) => c.querySelector(`[data-testid="gg-stages-${sym}"]`) as HTMLElement | null;
/** The row's children in DOM order as [class, text] — title, day labels, chips and arrows. */
const seq = (el: HTMLElement) => Array.from(el.children).map((n) => [n.className, n.textContent || ''] as const);

beforeEach(() => { board = () => ({}); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🧭 GgStages on a 🚩 setup card — every word served, verbatim', () => {
  it('title, each session label and each tag text render verbatim, oldest first; the served sep between tags', async () => {
    board = () => withStages(GOLD.bull_flag, { EEE: TWO_DAYS, AAA: NOT_TODAY });
    stub();
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    const el = row(container, 'EEE')!;
    expect(el).not.toBeNull();
    expect(seq(el)).toEqual([
      ['gg-stages-title', TWO_DAYS.title],
      ['gg-stage-day', 'Fri 10-09'],
      ['cm-badge gg-stage', TWO_DAYS.groups[0].tags[0].text],
      ['gg-stage-sep', ' \u2192 '],
      ['gg-stage-day', 'today'],
      ['cm-badge gg-stage', TWO_DAYS.groups[1].tags[0].text],
      ['gg-stage-sep', ' \u2192 '],
      ['cm-badge gg-stage gg-stage-here', TWO_DAYS.groups[1].tags[1].text],
    ]);
    expect(el.getAttribute('title')).toBe(TWO_DAYS.hint);
    expect(el.getAttribute('aria-label')).toBe(TWO_DAYS.text);
    expect(container.querySelector('[data-testid="gg-stage-day-EEE-2026-10-13"]')?.textContent).toBe('today');
    expect(container.querySelector('[data-testid="gg-stage-EEE-2026-10-09-kiss_fly"]')?.textContent)
      .toBe(TWO_DAYS.groups[0].tags[0].text);
    // the row sits inside the card's extras, after everything else
    const extras = el.closest('[data-testid="gg-extras"]')!;
    expect(extras).not.toBeNull();
    expect(extras.lastElementChild).toBe(el);
  });

  it('`here` marks ONLY the card’s own setup in the board session; NEGATIVE: never on another chip', async () => {
    board = () => withStages(GOLD.bull_flag, { EEE: TWO_DAYS, AAA: NOT_TODAY });
    stub();
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    const here = container.querySelectorAll('[data-testid="gg-stages-EEE"] .gg-stage-here');
    expect(here).toHaveLength(1);
    expect(here[0].getAttribute('data-testid')).toBe('gg-stage-EEE-2026-10-13-bull_flag');
    expect(container.querySelectorAll('[data-testid="gg-stages-AAA"] .gg-stage-here')).toHaveLength(0);
  });

  it('NEGATIVE: a clock:false group prints no HH:MM the payload did not carry; the sep never leads the row', async () => {
    board = () => withStages(GOLD.bull_flag, { EEE: TWO_DAYS, AAA: NOT_TODAY });
    stub();
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    const el = row(container, 'AAA')!;
    expect(el.textContent).not.toMatch(/\d\d:\d\d/);
    expect(el.querySelectorAll('.gg-stage-sep')).toHaveLength(0);
    expect(seq(el)).toEqual([
      ['gg-stages-title', NOT_TODAY.title],
      ['gg-stage-day', 'Mon 10-12'],
      ['cm-badge gg-stage', NOT_TODAY.groups[0].tags[0].text],
    ]);
    // every number printed in the EEE row is inside some served string
    const pool = servedWords(TWO_DAYS).join(' \u0000 ');
    for (const n of row(container, 'EEE')!.textContent!.match(/\d+(?:[.,:-]\d+)*/g) || []) expect(pool).toContain(n);
    expect(container.textContent).not.toMatch(/NaN|undefined|\bNone\b|\[object Object\]/);
  });

  it('every served word replaced by ZZ… renders as-is (the FE types none)', async () => {
    const zz = clone(TWO_DAYS);
    zz.title = 'ZZ1'; zz.hint = 'ZZ2'; zz.sep = 'ZZ3'; zz.text = 'ZZ4';
    zz.groups[0].label = 'ZZ5'; zz.groups[1].label = 'ZZ6';
    zz.groups[0].tags[0].text = 'ZZ7'; zz.groups[1].tags[0].text = 'ZZ8'; zz.groups[1].tags[1].text = 'ZZ9';
    board = () => withStages(GOLD.bull_flag, { EEE: zz });
    stub();
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    const el = row(container, 'EEE')!;
    expect(el.textContent).toBe('ZZ1ZZ5ZZ7ZZ3ZZ6ZZ8ZZ3ZZ9');
    expect(el.getAttribute('title')).toBe('ZZ2');
    expect(el.getAttribute('aria-label')).toBe('ZZ4');
    expect(el.textContent).not.toMatch(/potential|A\+|today|\u2192|Stages/);
  });

  it('NEGATIVE: a card with no stages has no gg-stages row; the board without any stages renders none', async () => {
    board = () => withStages(GOLD.bull_flag, { EEE: TWO_DAYS });
    stub();
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    expect(row(container, 'EEE')).not.toBeNull();
    expect(row(container, 'AAA')).toBeNull();
    expect(container.querySelectorAll('[data-testid^="gg-stages-"]')).toHaveLength(1);
    cleanup();
    board = () => withStages(GOLD.bull_flag, {});
    stub();
    const r = mount('tab=gajjala&sub=bull_flag');
    await loaded(r.container);
    expect(r.container.querySelectorAll('[data-testid^="gg-stages-"]')).toHaveLength(0);
    expect(r.container.querySelectorAll('.gg-stages, .gg-stage')).toHaveLength(0);
  });
});

describe('🧭 GgStages on every card kind and page', () => {
  it('renders on a 🧠 card', async () => {
    board = (u) => withStages(GOLD[u.searchParams.get('sub') || 'bull_flag'] || GOLD.bull_flag, { DDD: TWO_DAYS });
    stub();
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    expect(row(container, 'DDD')?.textContent).toContain(TWO_DAYS.groups[1].tags[1].text);
  });

  it('renders on a ☀️ pre-market card (no `here` from the backend there)', async () => {
    const pm = clone(NOT_TODAY);
    board = () => withStages(HAND.premarket, { YJ: pm });
    stub();
    const { container } = mount('tab=gajjala&sub=premarket');
    await loaded(container);
    const el = row(container, 'YJ')!;
    expect(el).not.toBeNull();
    expect(el.textContent).toContain(pm.groups[0].tags[0].text);
    expect(el.querySelectorAll('.gg-stage-here')).toHaveLength(0);
  });

  it('renders on the 1-minute board', async () => {
    board = (u) => withStages(GG1[u.searchParams.get('sub') || 'bull_flag'] || GG1.bull_flag, { GGA: TWO_DAYS });
    stub();
    const { container } = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(container);
    expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala_1m');
    expect(row(container, 'GGA')?.getAttribute('aria-label')).toBe(TWO_DAYS.text);
  });

  it('renders on the 🧪 audited board (the served borrowed sentence rides in the hint)', async () => {
    const aud = clone(TWO_DAYS);
    aud.hint = 'served hint · served borrowed sentence';
    board = () => {
      const b = withStages(GOLD.bull_flag, { EEE: aud });
      b.tab = 'gajjala_audited';
      b.variant = { key: 'gga', tab: 'gajjala_audited', label: 'served label', title: 'served title',
                    honesty: 'served honesty', tfs: ['5m', '15m'], primary: '5m', slow: '15m',
                    api_base: '/chart-maps/gajjala-audited', record_from: '2026-11-01' };
      return b;
    };
    stub();
    const { container } = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(container);
    expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala_audited');
    expect(row(container, 'EEE')?.getAttribute('title')).toBe(aud.hint);
  });
});

describe('🧭 GgStages — NEGATIVE shapes render nothing they were not served', () => {
  const r = (stages: any) => render(<GgStages stages={stages} sym="XYZ" />).container;

  it('no block / null / groups: [] / groups not an array → nothing', () => {
    for (const s of [undefined, null, { ...clone(TWO_DAYS), groups: [] }, { ...clone(TWO_DAYS), groups: 'x' },
                     { ...clone(TWO_DAYS), groups: null }]) {
      const c = r(s);
      expect(c.querySelector('[data-testid^="gg-stages-"]')).toBeNull();
      expect(c.textContent).toBe('');
      cleanup();
    }
  });

  it('a non-string or blank title → nothing', () => {
    for (const title of [null, undefined, 42, '', '   ', { t: 1 }]) {
      const c = r({ ...clone(TWO_DAYS), title });
      expect(c.innerHTML).toBe('');
      cleanup();
    }
  });

  it('a tag with empty / non-string text is skipped; a group left with no tag is skipped (and its label)', () => {
    const s = clone(TWO_DAYS);
    s.groups[0].tags[0].text = '';
    s.groups[1].tags[0].text = 42;
    const c = r(s);
    expect(c.querySelector('[data-testid="gg-stage-day-XYZ-2026-10-09"]')).toBeNull();
    expect(c.querySelector('[data-testid="gg-stage-XYZ-2026-10-13-horizontal_fade"]')).toBeNull();
    const el = c.querySelector('[data-testid="gg-stages-XYZ"]') as HTMLElement;
    expect(seq(el)).toEqual([
      ['gg-stages-title', s.title],
      ['gg-stage-day', 'today'],
      ['cm-badge gg-stage gg-stage-here', s.groups[1].tags[1].text],
    ]);
    expect(el.textContent).not.toContain('42');
  });

  it('every tag invalid (null, non-object, no text) → nothing at all', () => {
    const s = clone(TWO_DAYS);
    s.groups[0].tags = [null, 'x', { setup: 'bull_flag' }];
    s.groups[1].tags = [{ text: null }, { text: '  ' }];
    expect(r(s).innerHTML).toBe('');
  });

  it('a missing / non-string sep prints no arrow; a missing hint / text sets no title / aria-label', () => {
    const s = clone(TWO_DAYS);
    delete s.sep; delete s.hint; s.text = 7;
    const el = r(s).querySelector('[data-testid="gg-stages-XYZ"]') as HTMLElement;
    expect(el.querySelectorAll('.gg-stage-sep')).toHaveLength(0);
    expect(el.hasAttribute('title')).toBe(false);
    expect(el.hasAttribute('aria-label')).toBe(false);
    expect(el.querySelectorAll('.gg-stage')).toHaveLength(3);
  });

  it('the live overlay (patchTiles) keeps gajjala.stages on a patched tile', () => {
    const b = withStages(GOLD.bull_flag, { EEE: TWO_DAYS });
    const t = b.tiles.find((x: any) => x.symbol === 'EEE');
    t.bars = [{ t: '2026-10-12', o: 4, h: 4.1, l: 3.9, c: 4.05, v: 1000 }, { t: '2026-10-13', o: 4, h: 4.1, l: 3.9, c: 4.05, v: 1011 }];
    const last = t.bars[t.bars.length - 1];
    const answer: CardLiveAnswer = {
      session: 'rth' as any, as_of_epoch: 1, as_of: 'a', footer: { live: 'L', stale: 'S' }, now_labels: ['now'],
      cap: 250, asked: 1, served: 1, missing: [], fault: null,
      quotes: { EEE: { bar: { ...last, c: last.c + 0.01, h: Math.max(last.h, last.c + 0.01) }, prev_t: null, now: null } },
    };
    const out = patchTiles(b.tiles, answer);
    const p: any = out.find((x: any) => x.symbol === 'EEE');
    expect(p).not.toBe(t);
    expect(p.gajjala.stages).toEqual(TWO_DAYS);
    expect(p.bars[p.bars.length - 1].c).toBeCloseTo(last.c + 0.01);
  });
});

describe('🧭 GgStages source + 📱 phone guards', () => {
  it('GgStages.tsx: no string literal or JSX text carrying a step word, the arrow, "today" or the title', async () => {
    const src = (await readSource('src/components/GgStages.tsx'))
      .replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    const lits = [...src.matchAll(/'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g)].map((m) => m[1] ?? m[2] ?? m[3]);
    const jsxText = [...src.matchAll(/>([^<>{}]+)</g)].map((m) => m[1].trim()).filter(Boolean);
    for (const s of [...lits, ...jsxText]) expect(s).not.toMatch(/potential|A\+|today|\u2192|Stages|triggered|stopped/);
    // NEGATIVE: the matcher catches a typed word
    expect(`'\u{1F9E0} potential'`).toMatch(/potential/);
    // literals are class names, testids, keys, typeof operands or the import paths only
    for (const s of lits) expect(s).toMatch(/^(|react|\.\.\/lib\/gajjala|cm-badge gg-stage( gg-stage-here)?|string|object|gg-stages?(-[a-z]+)?(-\$\{.*)?|gg-stage-[a-z]+(-\$\{.*)?|\$\{.*)$/);
  });

  it('gajjala.css: .gg-stages wraps with min-width: 0; .gg-stage breaks anywhere', async () => {
    const css = await readSource('src/styles/gajjala.css');
    const rule = (sel: string, src: string) => {
      const m = src.match(new RegExp(`(^|\\n)\\s*${sel.replace('.', '\\.')}\\s*\\{([^}]*)\\}`));
      return m ? m[2] : null;
    };
    const rows = rule('.gg-stages', css);
    expect(rows).toMatch(/flex-wrap:\s*wrap/);
    expect(rows).toMatch(/min-width:\s*0\b/);
    const chip = rule('.gg-stage', css);
    expect(chip).toMatch(/overflow-wrap:\s*anywhere/);
    expect(chip).toMatch(/min-width:\s*0\b/);
    expect(chip).toMatch(/white-space:\s*normal/);
    // NEGATIVE: the matchers reject a nowrap row
    const bad = '.gg-stages { display: flex; }\n.gg-stage { white-space: nowrap; }';
    expect(rule('.gg-stages', bad)).not.toMatch(/flex-wrap:\s*wrap/);
    expect(rule('.gg-stage', bad)).not.toMatch(/overflow-wrap:\s*anywhere/);
  });

  it('GajjalaBoard.tsx: ONE <GgStages line, at the end of CardExtras, fed read.stages', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    expect(src.match(/<GgStages /g)).toHaveLength(1);
    expect(src).toMatch(/<GgStages stages=\{read\.stages\} sym=\{sym\} \/>\n\s*<\/div>\n\s*\);\n\}/);
  });
});
