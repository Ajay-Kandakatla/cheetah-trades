import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';

/* ⚡ Enter like GG (2026-11-11, entry spec WP-FE §5.5). Ajay: "Also apply your proposal too." / "Here is how he enters
 * please tell me to enter based on this" / "Can you check for any mistakes". The board prints SERVED words only:
 *   F1 the card's plan line = the served `plan_text` (tab.plan_text), verbatim — the FE joins no trigger / stop / risk;
 *   F2 the 💧 pill = the served `chips.vol_dried`;
 *   F3 the 🔝 Focus header = the served `focus.text`, a divider after the last served focus card, every card still listed;
 *   F4 the 🌅 Day-2 rows on ☀️ = router Links to the served href (ggHref + withSource); an unsafe href → text;
 *   F5 the ⚡ break line = the served `push_break.text`; a 🧠 Track row's ⚡ word = the served `brk_text`.
 * Built against the WP-TAB served shape (spec §3.1–§3.8) with fixtures INSIDE this file (clones of the hand fixture —
 * the hand fixture itself is never edited). NEGATIVES on every side. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({
  PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} />,
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

const BOARDS: Record<string, any> = (fixture as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

/* ---- the WP-TAB served words (spec §3.1–§3.8), as fixture values ---- */
const PLAN_ENTRY = 'Entry above 4.12 · stop 3.95 · risk 4.1%';
const PLAN_OTHER = 'trigger 2.66 · stop 2.58 · risk 3.0%';
const VOL_DRIED = '💧 volume dried up';
const FOCUS_TEXT = '🔝 Focus 5 — the first five cards in this board\'s own order (GG keeps 4–5 names active). Display only: '
  + 'nothing measured says these five win more.';
const BRK_STATUS = '⚡ Break pushes: SHADOW — the first trade over an armed 🧠 plan\'s trigger on the live bar is recorded, '
  + 'not sent, until your word. The A+ push still waits for the bar close. UNMEASURED.';
const BRK_ROW = '⚡ break rang 10:07:12 ET';
const DAY2_TITLE = '🌅 Day 2 — last session\'s A+ and after-hours movers';
const DAY2_NOTE = 'List only, no push. GG keeps the prior day\'s movers on his morning list (R2). Our 21-session read: they '
  + 'print +1R again on day 2 about as often as any listed name — a list, not a signal.';
const DAY2_EMPTY = 'No A+ rang and no after-hours mover passed his checks last session.';
const DAY2_ROWS = [
  { symbol: 'PFAI', text: 'PFAI · 🚩 Bull Flag A+ rang 10:06 ET last session · on today\'s list',
    href: '/chart-maps?tab=gajjala&sub=bull_flag&focus=PFAI' },
  { symbol: 'AVGR', text: 'AVGR · 🌙 after-hours mover last session',
    href: '/chart-maps?tab=gajjala&sub=premarket&focus=AVGR' },
];
const UNSAFE: unknown[] = ['//evil.example/x', 'https://x.example', '', null, 42];

let boardFor: (sub: string) => any = (sub) => clone(BOARDS[sub] || BOARDS.bull_flag);
function stubFetch() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    if (u.pathname.endsWith('/chart-maps/gajjala')) {
      const b = boardFor(u.searchParams.get('sub') || 'bull_flag');
      if (b.session) b.session.refresh_sec = 0;
      return { ok: true, status: 200, json: async () => b };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  }));
}

let loc: { pathname: string; search: string; state: any } = { pathname: '', search: '', state: null };
function Probe() {
  const l = useLocation();
  loc = { pathname: l.pathname, search: l.search, state: l.state };
  return null;
}
const mount = (q: string) => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}>
    <Routes>
      <Route path="/chart-maps" element={<GajjalaBoard />} />
      <Route path="*" element={<div data-testid="landed" />} />
    </Routes>
    <Probe />
  </MemoryRouter>);

/** The bull_flag board with `edit` applied to each tile's read (by symbol). */
const bullFlag = (edit: (sym: string, g: any) => void) => {
  const b = clone(BOARDS.bull_flag);
  for (const t of b.tiles) if (t.gajjala) edit(t.symbol, t.gajjala);
  return b;
};

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

beforeEach(() => { loc = { pathname: '', search: '', state: null }; boardFor = (sub) => clone(BOARDS[sub] || BOARDS.bull_flag); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('F1 — the plan line is the served plan_text, verbatim', () => {
  it('an entry read prints "Entry above …", another read its served "trigger …" line, each exactly as served', async () => {
    boardFor = () => bullFlag((sym, g) => {
      if (sym === 'PFAI') g.plan_text = PLAN_ENTRY;
      if (sym === 'TCRT') g.plan_text = PLAN_OTHER;
    });
    stubFetch();
    mount('tab=gajjala&sub=bull_flag');
    const pf = await screen.findByTestId('gg-tile-PFAI');
    expect(within(pf).getByTestId('gg-plan').textContent).toBe(PLAN_ENTRY);
    expect(within(screen.getByTestId('gg-tile-TCRT')).getByTestId('gg-plan').textContent).toBe(PLAN_OTHER);
  });

  it('NEGATIVE: no plan_text → no gg-plan div, even with a trigger, a stop and a risk on the read', async () => {
    boardFor = () => bullFlag((sym, g) => { if (sym === 'TCRT') g.plan_text = PLAN_OTHER; });
    stubFetch();
    mount('tab=gajjala&sub=bull_flag');
    const pf = await screen.findByTestId('gg-tile-PFAI');
    expect(BOARDS.bull_flag.tiles[0].gajjala.trigger).toBe(4.12);       // the fixture read carries the numbers…
    expect(within(pf).queryByTestId('gg-plan')).toBeNull();              // …and the FE joins none of them
    for (const s of ['BKYI', 'SCNI']) expect(within(screen.getByTestId(`gg-tile-${s}`)).queryByTestId('gg-plan')).toBeNull();
    expect(within(pf).getByTestId('gg-extras').textContent).not.toMatch(/trigger 4\.12|stop 3\.95|risk 4\.1%/);
  });

  it.each([null, '', '   ', 42, { text: 'x' }])('NEGATIVE: plan_text %j → no gg-plan div', async (bad) => {
    boardFor = () => bullFlag((sym, g) => { if (sym === 'PFAI') g.plan_text = bad; });
    stubFetch();
    mount('tab=gajjala&sub=bull_flag');
    const pf = await screen.findByTestId('gg-tile-PFAI');
    expect(within(pf).queryByTestId('gg-plan')).toBeNull();
    expect(document.body.textContent).not.toMatch(/undefined|NaN|\[object Object\]/);
  });

  it('source pin: GajjalaBoard.tsx composes no trigger / stop / risk words for the plan line', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    expect(src).not.toContain('`trigger ${');
    expect(src).not.toContain('`stop ${');
    expect(src).not.toContain('`risk ${');
    expect(src).not.toMatch(/ggPx\(read\.|riskText\(read\./);
    expect(src).toContain('read.plan_text');
  });

  it('NEGATIVE: the pre-change join would fail the same source pin', () => {
    const before = "{[trig ? `trigger ${trig}` : null, stop ? `stop ${stop}` : null, risk ? `risk ${risk}` : null]";
    expect(before).toContain('`trigger ${');
    expect(before).toContain('`stop ${');
  });
});

describe('F2 — the 💧 volume-dried pill', () => {
  it('prints the served chips.vol_dried verbatim beside the state pill', async () => {
    boardFor = () => bullFlag((sym, g) => { if (sym === 'PFAI') g.chips = { ...g.chips, vol_dried: VOL_DRIED }; });
    stubFetch();
    mount('tab=gajjala&sub=bull_flag');
    const pill = await screen.findByTestId('gg-vol-dried-PFAI');
    expect(pill.textContent).toBe(VOL_DRIED);
    expect(pill.className).toContain('gg-vol-dried');
    expect(pill.parentElement!.className).toContain('gg-pills');
    // printed once — never also in the chip row
    expect(within(screen.getByTestId('gg-tile-PFAI')).getByTestId('gg-chip-row').textContent).not.toContain(VOL_DRIED);
  });

  it('NEGATIVE: an absent / empty / null key → no pill on any card', async () => {
    boardFor = () => bullFlag((sym, g) => {
      if (sym === 'BKYI') g.chips = { ...g.chips, vol_dried: '' };
      if (sym === 'TCRT') g.chips = { ...g.chips, vol_dried: null };
    });
    stubFetch();
    mount('tab=gajjala&sub=bull_flag');
    await screen.findByTestId('gg-tile-PFAI');
    expect(screen.queryAllByTestId(/^gg-vol-dried-/)).toHaveLength(0);
    expect(document.body.textContent).not.toContain('💧');
  });
});

/** Seven bull_flag cards (clones of the hand tiles, renamed), the first five served `focus: true`. */
const seven = (flag = 5, served = true) => {
  const b = clone(BOARDS.bull_flag);
  const base = b.tiles;
  b.tiles = Array.from({ length: 7 }, (_, i) => {
    const t = clone(base[i % base.length]);
    t.symbol = `F${i + 1}`;
    if (i < flag) t.focus = true;
    return t;
  });
  if (served) b.focus = { n: 5, text: FOCUS_TEXT };
  return b;
};

describe('F3 — the 🔝 Focus header and divider', () => {
  it('the served header above the first card, the divider right after the 5th focus card, all 7 cards listed', async () => {
    boardFor = () => seven();
    stubFetch();
    mount('tab=gajjala&sub=bull_flag');
    await screen.findByTestId('gg-tile-F7');
    const head = screen.getByTestId('gg-focus-head');
    expect(head.textContent).toBe(FOCUS_TEXT);
    const first = screen.getByTestId('gg-tile-F1');
    expect(head.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const dividers = screen.getAllByTestId('gg-focus-divider');
    expect(dividers).toHaveLength(1);
    expect(dividers[0].previousElementSibling).toBe(screen.getByTestId('gg-tile-F5'));
    expect(dividers[0].nextElementSibling).toBe(screen.getByTestId('gg-tile-F6'));
    expect(dividers[0].textContent).toBe('');                          // a divider, no word
    for (let i = 1; i <= 7; i++) expect(screen.getByTestId(`gg-tile-F${i}`)).toBeTruthy();
  });

  it('a 🚫 name skipped by the server: the divider follows the LAST flagged card, wherever it sits', async () => {
    boardFor = () => {
      const b = seven();
      b.tiles[2].focus = false;      // the server skipped F3 (🚫) …
      b.tiles[5].focus = true;       // … and flagged F6
      return b;
    };
    stubFetch();
    mount('tab=gajjala&sub=bull_flag');
    await screen.findByTestId('gg-tile-F7');
    expect(screen.getByTestId('gg-focus-divider').previousElementSibling).toBe(screen.getByTestId('gg-tile-F6'));
  });

  it('NEGATIVE: no served focus block → no header and no divider, even when tiles carry focus flags', async () => {
    boardFor = () => seven(5, false);
    stubFetch();
    mount('tab=gajjala&sub=bull_flag');
    await screen.findByTestId('gg-tile-F7');
    expect(screen.queryByTestId('gg-focus-head')).toBeNull();
    expect(screen.queryByTestId('gg-focus-divider')).toBeNull();
    for (let i = 1; i <= 7; i++) expect(screen.getByTestId(`gg-tile-F${i}`)).toBeTruthy();
  });

  it('NEGATIVE: the plain hand board (no focus key anywhere) → nothing new', async () => {
    stubFetch();
    mount('tab=gajjala&sub=bull_flag');
    await screen.findByTestId('gg-tile-PFAI');
    expect(screen.queryByTestId('gg-focus-head')).toBeNull();
    expect(screen.queryByTestId('gg-focus-divider')).toBeNull();
  });

  it('NEGATIVE: a served block but no flagged tile → the header only, no divider', async () => {
    boardFor = () => seven(0, true);
    stubFetch();
    mount('tab=gajjala&sub=bull_flag');
    await screen.findByTestId('gg-tile-F7');
    expect(screen.getByTestId('gg-focus-head').textContent).toBe(FOCUS_TEXT);
    expect(screen.queryByTestId('gg-focus-divider')).toBeNull();
  });
});

const withDay2 = (rows: any[] = DAY2_ROWS, extra: Record<string, unknown> = {}) => {
  const b = clone(BOARDS.premarket);
  b.day2 = { title: DAY2_TITLE, note: DAY2_NOTE, rows, empty_text: DAY2_EMPTY, ...extra };
  return b;
};

describe('F4 — the 🌅 Day-2 list on ☀️', () => {
  it('prints the served title, note and rows; each row is ONE router Link (withSource + back state); a click moves the router', async () => {
    boardFor = (sub) => (sub === 'premarket' ? withDay2() : clone(BOARDS[sub] || BOARDS.bull_flag));
    stubFetch();
    mount('tab=gajjala&sub=premarket');
    const block = await screen.findByTestId('gg-day2');
    expect(within(block).getByTestId('gg-day2-title').textContent).toBe(DAY2_TITLE);
    expect(within(block).getByTestId('gg-day2-note').textContent).toBe(DAY2_NOTE);
    for (const r of DAY2_ROWS) {
      const row = within(block).getByTestId(`gg-day2-row-${r.symbol}`);
      expect(row.className).toContain('gg-day2-row');
      const links = within(row).getAllByRole('link');
      expect(links).toHaveLength(1);
      expect(links[0].textContent).toBe(r.text);
      const href = links[0].getAttribute('href') || '';
      expect(href.startsWith(r.href.split('?')[0])).toBe(true);
      const q = new URLSearchParams(href.split('?')[1]);
      expect(q.get('focus')).toBe(r.symbol);
      expect(q.get('from')).toBe('chart-maps');
    }
    expect(screen.queryByTestId('gg-day2-empty')).toBeNull();
    const startHistory = window.history.length;
    fireEvent.click(within(block).getByTestId('gg-day2-link-AVGR'));
    // A plain anchor never moves a MemoryRouter — only a router Link does; no full-page navigation either.
    await waitFor(() => expect(new URLSearchParams(loc.search).get('focus')).toBe('AVGR'));
    expect(loc.pathname).toBe('/chart-maps');
    expect(loc.state).toEqual({ from: '/chart-maps?tab=gajjala&sub=premarket', label: 'Chart Maps' });
    expect(window.history.length).toBe(startHistory);
  });

  it.each(UNSAFE)('NEGATIVE: a row href %j renders its served text, never a link', async (bad) => {
    boardFor = (sub) => (sub === 'premarket'
      ? withDay2([{ ...DAY2_ROWS[0], href: bad }]) : clone(BOARDS[sub] || BOARDS.bull_flag));
    stubFetch();
    mount('tab=gajjala&sub=premarket');
    const row = await screen.findByTestId('gg-day2-row-PFAI');
    expect(row.textContent).toBe(DAY2_ROWS[0].text);
    expect(within(row).queryAllByRole('link')).toHaveLength(0);
    expect(row.querySelector('a')).toBeNull();
  });

  it('NEGATIVE: no rows → the served empty line, no list', async () => {
    boardFor = (sub) => (sub === 'premarket' ? withDay2([]) : clone(BOARDS[sub] || BOARDS.bull_flag));
    stubFetch();
    mount('tab=gajjala&sub=premarket');
    const block = await screen.findByTestId('gg-day2');
    expect(within(block).getByTestId('gg-day2-empty').textContent).toBe(DAY2_EMPTY);
    expect(block.querySelectorAll('.gg-day2-row')).toHaveLength(0);
  });

  it.each([
    ['rows an object', { rows: {} }, 0, true],
    ['rows a string', { rows: 'PFAI' }, 0, true],
    ['title an object', { rows: [], title: { x: 1 } }, 0, false],
    ['note an object', { note: { x: 1 } }, DAY2_ROWS.length, true],
    ['empty_text an object', { rows: [], empty_text: { x: 1 } }, 0, true],
    ['a row not an object', { rows: [7, null, 'PFAI', { symbol: 'PFAI', text: { x: 1 } }] }, 0, true],
  ])('NEGATIVE (critic fix): %s → the board renders, the bad part is dropped, nothing throws',
    async (_n, extra, nRows, hasTitle) => {
      boardFor = (sub) => (sub === 'premarket' ? withDay2(DAY2_ROWS, extra) : clone(BOARDS[sub] || BOARDS.bull_flag));
      stubFetch();
      mount('tab=gajjala&sub=premarket');
      await screen.findByTestId('gg-tile-YJ');
      const block = await screen.findByTestId('gg-day2');
      expect(block.querySelectorAll('.gg-day2-row')).toHaveLength(nRows as number);
      expect(within(block).queryByTestId('gg-day2-title')?.textContent ?? null).toBe(hasTitle ? DAY2_TITLE : null);
      if ((extra as any).note) expect(within(block).queryByTestId('gg-day2-note')).toBeNull();
      expect(document.body.textContent).not.toContain('[object Object]');
    });

  it('NEGATIVE (critic fix): an object title with no rows and no empty line → no block at all', async () => {
    boardFor = (sub) => (sub === 'premarket'
      ? withDay2([], { title: { x: 1 }, empty_text: null }) : clone(BOARDS[sub] || BOARDS.bull_flag));
    stubFetch();
    mount('tab=gajjala&sub=premarket');
    await screen.findByTestId('gg-tile-YJ');
    expect(screen.queryByTestId('gg-day2')).toBeNull();
  });

  it('NEGATIVE: no day2 key (every other sub, GG1, 🧪, an older API) → no block', async () => {
    stubFetch();
    mount('tab=gajjala&sub=premarket');
    await screen.findByTestId('gg-tile-YJ');
    expect(screen.queryByTestId('gg-day2')).toBeNull();
    expect(document.body.textContent).not.toContain('🌅');
  });
});

/** A minimal 🧠 board (WP-TAB shape) with one Track row. */
const potentialBoard = (row: Record<string, unknown>) => {
  const b = clone(BOARDS.bull_flag);
  b.sub = 'potential';
  b.tiles = [];
  b.track = {
    title: '📈 Track — today', unmeasured: 'UNMEASURED',
    today: { date: '2026-11-11', rows: [{ symbol: 'PFAI', setup: 'bull_flag', text: 'PFAI · 🚩 armed 10:02 ET', ...row }] },
  };
  return b;
};

describe('F5 — the ⚡ break line and the 🧠 Track ⚡ word', () => {
  it('prints the served push_break text verbatim, right after the 🧠 push line', async () => {
    boardFor = () => {
      const b = clone(BOARDS.bull_flag);
      b.push_potential = { mode: 'live', text: '🧠 Potential pushes: LIVE' };
      b.push_break = { mode: 'shadow', text: BRK_STATUS, watching: 3 };
      return b;
    };
    stubFetch();
    mount('tab=gajjala&sub=bull_flag');
    const line = await screen.findByTestId('gg-push-break');
    expect(line.textContent).toBe(BRK_STATUS);
    expect(screen.getByTestId('gg-push-potential').nextElementSibling).toBe(line);
  });

  it.each([undefined, null, { mode: 'shadow' }, { text: '' }, { text: 7 }])('NEGATIVE: push_break %j → no line', async (pb) => {
    boardFor = () => ({ ...clone(BOARDS.bull_flag), push_break: pb });
    stubFetch();
    mount('tab=gajjala&sub=bull_flag');
    await screen.findByTestId('gg-tile-PFAI');
    expect(screen.queryByTestId('gg-push-break')).toBeNull();
    expect(document.body.textContent).not.toMatch(/⚡ Break|undefined|\[object Object\]/);
  });

  it('a 🧠 Track row prints its served brk_text', async () => {
    boardFor = () => potentialBoard({ brk_text: BRK_ROW });
    stubFetch();
    mount('tab=gajjala&sub=potential');
    const pill = await screen.findByTestId('gg-track-brk-PFAI-bull_flag');
    expect(pill.textContent).toBe(` · ${BRK_ROW}`);
    expect(pill.className).toContain('gg-track-brk');
  });

  it.each([undefined, null, ''])('NEGATIVE: brk_text %j → no ⚡ word on the row', async (v) => {
    boardFor = () => potentialBoard(v === undefined ? {} : { brk_text: v });
    stubFetch();
    mount('tab=gajjala&sub=potential');
    await screen.findByTestId('gg-track-row-PFAI-bull_flag');
    expect(screen.queryByTestId('gg-track-brk-PFAI-bull_flag')).toBeNull();
    expect(screen.getByTestId('gg-track-row-PFAI-bull_flag').textContent).not.toContain('⚡');
  });

  it('wording: no served fixture word above says "bounce" (reversal, never bounce)', () => {
    for (const s of [PLAN_ENTRY, PLAN_OTHER, VOL_DRIED, FOCUS_TEXT, BRK_STATUS, BRK_ROW, DAY2_TITLE, DAY2_NOTE, DAY2_EMPTY]) {
      expect(s).not.toMatch(/boun/i);
    }
  });
});
