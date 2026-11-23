/* 🏆 chip → jump to that win's replay at its peak (2026-11-22, pwjump spec §3.5–§3.8). Ajay 2026-11-22, verbatim: "New
 * feature when I click on this past winner tag take me to that video so change the date and focus me on that video at
 * that. time" · "past winner 11-18 +57%". Hand fixtures in the served shapes (store.payload + winners_payload with the two
 * new card keys + jump_missing_text). NEGATIVES throughout: the same chip twice, chained Back, an origin URL with no date,
 * missing / wrong-symbol / wrong-date targets, a failed 🏆 GET, a date pick clearing `card`, ⌘-click. */
import { act, fireEvent, render, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ReplaysBoard from './ReplaysBoard';
import { API } from '../lib/apiBase';
import { FETCH_FAILED, RP_PATH, RP_SETUP_LS_KEY, RP_WINNERS_PATH } from '../lib/replays';

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
const D20 = '2026-11-20';
const D18 = '2026-11-18';
const DATES = [D20, D18, '2026-11-17'];
const VWAV_DAY = 'VWAV_reversal_squeeze_potential_45x.mp4';
const AKAN_DAY = 'AKAN_kiss_fly_45x.mp4';
const VWAV_REEL = '2026-11-18_VWAV_45x.mp4';
const AKAN_REEL = '2026-11-13_AKAN_45x.mp4';
const AKAN_RUN = '2026-04-22_AKAN_45x.mp4';
const SEEK_VWAV = '⏩ opens at the peak minute, 15:54 ET';
const SEEK_AKAN = '⏩ opens at the peak minute, 15:23 ET';
const NONE = 'no peak time on this replay — it opens at the start';
const MISSING = 'That replay is no longer listed.';

const pwVWAV = { day: D18, kind: 'single_day', close_gain_pct: 57.07, file: VWAV_REEL, sub: 'winners', text: '🏆 past winner 11-18 +57%' };
const pwAKAN = { day: '2026-11-13', kind: 'single_day', close_gain_pct: 120, file: AKAN_REEL, sub: 'winners', text: '🏆 past winner 11-13 +120%' };
const pwRUN = { day: '2026-05-01', kind: 'multi_day', close_gain_pct: 1657, file: AKAN_RUN, sub: 'multiday', text: '🏆 past winner 05-01 +1657% multi-day' };

const dayCard = (date: string, file: string, symbol: string, extra: Record<string, unknown> = {}) => ({
  file, src: `/chart-maps/replays/video/${date}/${file}`, symbol, setup_text: 'setup', ...extra,
});
function dayOf(date: string): any {
  const groups = date === D20 ? [
    { key: 'g1', label: 'Group one', videos: [
      dayCard(D20, VWAV_DAY, 'VWAV', { past_winner: [pwVWAV], past_winner_count: 1, past_winner_more_text: null }),
      dayCard(D20, AKAN_DAY, 'AKAN', { past_winner: [pwAKAN, pwRUN], past_winner_count: 2, past_winner_more_text: null }),
    ] },
    { key: 'g2', label: 'Group two', videos: [dayCard(D20, 'CENN_x_45x.mp4', 'CENN')] },
  ] : [{ key: 'g1', label: 'Group one', videos: [dayCard(date, 'VWAV_x_45x.mp4', 'VWAV')] }];
  return { state: 'ready', title: 'Replays', tab: 'replays', date, dates: DATES, window_note: 'wn', groups, rs: null };
}
const wsrc = (sub: string, file: string) => `/chart-maps/replays/winners/video/${sub}/${file}`;
const reel = (sub: string, file: string, symbol: string, extra: Record<string, unknown> = {}) => ({
  file, sub, src: wsrc(sub, file), symbol, kind: sub === 'winners' ? 'single_day' : 'multi_day',
  kind_text: sub === 'winners' ? 'single-day' : 'multi-day', spike_print: false, ...extra,
});
const WIN: any = {
  title: '🏆 Past winners', tab: 'replays', state: 'ready', text: null, note: 'note', window: 'w', window_note: 'wn',
  summary_text: '4 videos', counts: {}, jump_missing_text: MISSING,
  setups: [{ key: 'all', label: 'All', count: 2 }, { key: 'reversal_squeeze', label: '🎾', count: 1 }, { key: 'none', label: 'none', count: 1 }],
  rows: [
    { key: 'sym-VWAV', symbol: 'VWAV', wins_text: '2 wins', filter_keys: ['none'], videos: [
      reel('winners', VWAV_REEL, 'VWAV', { seek_s: 952.05, seek_text: SEEK_VWAV }),
      reel('winners', '2026-10-02_VWAV_45x.mp4', 'VWAV', { seek_s: 600.05, seek_text: '⏩ opens at the peak minute, 11:30 ET' }),
    ] },
    { key: 'sym-AKAN', symbol: 'AKAN', wins_text: '2 wins', filter_keys: ['reversal_squeeze'], videos: [
      reel('winners', AKAN_REEL, 'AKAN', { seek_s: 910.65, seek_text: SEEK_AKAN,
        past_winner: [{ ...pwRUN, text: '🏆 won before 05-01 +1657% multi-day' }], past_winner_count: 1 }),
      reel('multiday', AKAN_RUN, 'AKAN', { seek_s: null, seek_text: NONE }),
    ] },
  ],
};

type Answer = { ok?: boolean; status?: number; body?: unknown; reject?: boolean };
/* An in-memory localStorage (the ReplaysPastWinnersSetup pattern — this runner has none). */
function mem() {
  const store: Record<string, string> = {};
  return {
    getItem: (k: string) => (k in store ? store[k] : null),
    setItem: (k: string, v: string) => { store[k] = String(v); },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { for (const k of Object.keys(store)) delete store[k]; },
    key: (i: number) => Object.keys(store)[i] ?? null,
    get length() { return Object.keys(store).length; },
  };
}
let ls = mem();
const isWin = (url: string) => url === `${API}${RP_WINNERS_PATH}`;
function stub(win: Answer = { body: WIN }, day: (d: string) => any = dayOf) {
  const f = vi.fn(async (url: string) => {
    const u = String(url);
    let a: Answer;
    if (isWin(u)) a = win;
    else {
      const m = /\?date=([0-9-]+)$/.exec(u);
      a = { body: day(m ? m[1] : D20) };
    }
    if (a.reject) throw new Error('network');
    return { ok: a.ok ?? true, status: a.status ?? 200, json: async () => clone(a.body) };
  });
  vi.stubGlobal('fetch', f);
  vi.stubGlobal('localStorage', ls);
  return f;
}
const winCalls = (f: any) => f.mock.calls.filter((c: any[]) => isWin(String(c[0])));

function Where() {
  const loc = useLocation();
  return <output data-testid="where">{loc.search}</output>;
}
function Back() {
  const nav = useNavigate();
  return <button type="button" data-testid="back" onClick={() => nav(-1)}>back</button>;
}

/* scrollIntoView spy: each call records the element and the board's state at that moment. */
type Call = { el: Element; board: string | null; cards: string };
let calls: Call[] = [];
const orig = (Element.prototype as any).scrollIntoView;
beforeEach(() => {
  calls = [];
  (Element.prototype as any).scrollIntoView = vi.fn(function (this: Element) {
    calls.push({ el: this, board: document.querySelector('.rp-board')?.getAttribute('data-state') ?? null,
      cards: Array.from(document.querySelectorAll('.rp-card')).map((c) => c.getAttribute('data-testid')).join(' ') });
  });
  ls = mem();
});
afterEach(() => {
  (Element.prototype as any).scrollIntoView = orig;
  vi.unstubAllGlobals();
});
const scrolledOn = (el: Element | null) => calls.filter((c) => c.el === el).length;

async function mount(entry = `/chart-maps?tab=replays&date=${D20}`, win: Answer = { body: WIN }, day = dayOf) {
  const f = stub(win, day);
  const r = render(<MemoryRouter initialEntries={[entry]}><ReplaysBoard /><Where /><Back /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.rp-board:not([data-state="loading"])')).not.toBeNull());
  const q = () => new URLSearchParams(r.getByTestId('where').textContent || '');
  const section = () => r.getByTestId('rpw-section');
  const row = (sub: string, file: string) => r.queryByTestId(`rpw-row-${sub}-${file}`);
  const chip = (cardFile: string, text: string) => Array.from(r.getByTestId(`rp-card-${cardFile}`)
    .querySelectorAll('[data-testid="rp-pastwin"]')).find((e) => e.textContent === text) as HTMLElement;
  const settle = async () => waitFor(() => {
    expect(r.container.querySelector('.rp-board:not([data-state="loading"])')).not.toBeNull();
    const st = section().getAttribute('data-state');
    expect(st === 'loaded' || st === 'failed' || st === 'closed').toBe(true);
  });
  const landOn = async (sub: string, file: string) => {
    await waitFor(() => expect(row(sub, file)?.querySelector('video')).toBeTruthy());
    await settle();
  };
  const back = async () => { await act(async () => { fireEvent.click(r.getByTestId('back')); }); await settle(); };
  return { ...r, f, q, section, row, chip, settle, landOn, back };
}
const sectionVideos = (s: HTMLElement) => s.querySelectorAll('video');

describe('🏆 chip → link (tests 1, 12, 13, 16)', () => {
  it('1: the chip is an <a> in .rp-chips; href carries date / winners / sym / reel; text = the served text', async () => {
    const m = await mount();
    const a = m.chip(VWAV_DAY, pwVWAV.text);
    expect(a.tagName).toBe('A');
    expect(a.closest('.rp-chips')).not.toBeNull();
    expect(a.textContent).toBe(pwVWAV.text);
    const href = a.getAttribute('href')!;
    expect(href).toContain(`date=${D18}`);
    expect(href).toContain('winners=1');
    expect(href).toContain('sym=VWAV');
    expect(href).toContain(`reel=winners%2F${VWAV_REEL}`);
    expect(href.startsWith('/chart-maps?')).toBe(true);
  });
  it('12 NEGATIVE: the win\'s day is not a served session → the href keeps the current date', async () => {
    const m = await mount();
    const href = new URLSearchParams(m.chip(AKAN_DAY, pwAKAN.text).getAttribute('href')!.split('?')[1]);
    expect(href.get('date')).toBe(D20);
    expect(href.get('reel')).toBe(`winners/${AKAN_REEL}`);
  });
  it('13 NEGATIVE: an entry with no sub stays a SPAN; "+N more" stays a SPAN; a "won before" chip in a 🏆 row stays a SPAN', async () => {
    const day = (d: string) => {
      const p = dayOf(d);
      if (d === D20) {
        const v = p.groups[0].videos[0];
        const { sub: _s, ...noSub } = pwVWAV;
        v.past_winner = [noSub, pwVWAV];
        v.past_winner_count = 3;
        v.past_winner_more_text = '+1 more';
      }
      return p;
    };
    const m = await mount(`/chart-maps?tab=replays&date=${D20}`, { body: WIN }, day);
    const chips = Array.from(m.getByTestId(`rp-card-${VWAV_DAY}`).querySelectorAll('[data-testid="rp-pastwin"]'));
    expect(chips.map((c) => c.tagName)).toEqual(['SPAN', 'A']);
    expect(chips[0].querySelector('a')).toBeNull();
    const more = m.getByTestId(`rp-card-${VWAV_DAY}`).querySelector('[data-testid="rp-pastwin-more"]')!;
    expect(more.tagName).toBe('SPAN');
    await act(async () => { fireEvent.click(m.chip(AKAN_DAY, pwAKAN.text)); });
    await m.landOn('winners', AKAN_REEL);
    const won = m.row('winners', AKAN_REEL)!.querySelector('[data-testid="rpw-pastwin"]')!;
    expect(won.tagName).toBe('SPAN');
    expect(won.textContent).toBe('🏆 won before 05-01 +1657% multi-day');
    expect(m.section().querySelector('a.rp-pastwin')).toBeNull();
  });
  it('16 NEGATIVE: a card on the win\'s own day (no served list) carries no chip / anchor', async () => {
    const m = await mount(`/chart-maps?tab=replays&date=${D18}`);
    expect(m.container.querySelector('.rp-board a.rp-pastwin, .rp-board .rp-pastwin')).toBeNull();
  });
});

describe('🏆 the landing (tests 2, 3, 6, 10, 11, 14)', () => {
  it('2: refetch ?date=11-18, ONE 🏆 GET, the row open, ONE video at #t=952.05, outlined, served words, scrolled after the board settled', async () => {
    const m = await mount();
    await act(async () => { fireEvent.click(m.chip(VWAV_DAY, pwVWAV.text)); });
    await m.landOn('winners', VWAV_REEL);
    expect(m.f.mock.calls.some((c: any[]) => String(c[0]) === `${API}${RP_PATH}?date=${D18}`)).toBe(true);
    expect(winCalls(m.f)).toHaveLength(1);
    expect(m.getByTestId('rpw-stock-VWAV').getAttribute('data-open')).toBe('1');
    const row = m.row('winners', VWAV_REEL)!;
    expect(sectionVideos(m.section())).toHaveLength(1);
    const v = row.querySelector('video')!;
    expect(v.getAttribute('src')).toBe(`${API}${wsrc('winners', VWAV_REEL)}#t=952.05`);
    expect(row.classList.contains('rpw-focus')).toBe(true);
    expect(row.getAttribute('tabindex')).toBe('-1');
    expect(m.getByTestId('rpw-seek').textContent).toBe(SEEK_VWAV);
    expect(row.contains(m.getByTestId('rpw-seek'))).toBe(true);
    const onRow = calls.filter((c) => c.el === row);
    expect(onRow).toHaveLength(1);
    expect(onRow[0].board).not.toBe('loading');
    expect(m.container.querySelectorAll('.rpw-focus')).toHaveLength(1);
    expect(m.q().get('reel')).toBe(`winners/${VWAV_REEL}`);
    expect(m.q().get('date')).toBe(D18);
    expect(m.q().has('card')).toBe(false);
  });
  it('3: loadedmetadata puts the video at the served second; NEGATIVE: already there → left; no autoplay / muted', async () => {
    const m = await mount();
    await act(async () => { fireEvent.click(m.chip(VWAV_DAY, pwVWAV.text)); });
    await m.landOn('winners', VWAV_REEL);
    const v = m.row('winners', VWAV_REEL)!.querySelector('video')! as HTMLVideoElement;
    v.currentTime = 5;
    fireEvent.loadedMetadata(v);
    expect(v.currentTime).toBe(952.05);
    v.currentTime = 952.3;                                              // within half a second: not re-written
    fireEvent.loadedMetadata(v);
    expect(v.currentTime).toBe(952.3);
    for (const x of ['autoplay', 'muted', 'poster', 'download', 'loop']) expect(v.hasAttribute(x)).toBe(false);
    expect(v.hasAttribute('controls')).toBe(true);
    expect(v.getAttribute('preload')).toBe('metadata');
  });
  it('6 NEGATIVE: a served seek_s null → no #t=, the none words print, loadedmetadata writes no currentTime', async () => {
    const win = clone(WIN);
    win.rows[0].videos[0].seek_s = null;
    win.rows[0].videos[0].seek_text = NONE;
    const m = await mount(`/chart-maps?tab=replays&date=${D20}`, { body: win });
    await act(async () => { fireEvent.click(m.chip(VWAV_DAY, pwVWAV.text)); });
    await m.landOn('winners', VWAV_REEL);
    const v = m.row('winners', VWAV_REEL)!.querySelector('video')! as HTMLVideoElement;
    expect(v.getAttribute('src')).toBe(`${API}${wsrc('winners', VWAV_REEL)}`);
    expect(m.getByTestId('rpw-seek').textContent).toBe(NONE);
    v.currentTime = 5;
    fireEvent.loadedMetadata(v);
    expect(v.currentTime).toBe(5);
  });
  it('10 NEGATIVE: ▶ on ANOTHER row → its src is exactly API + served src, currentTime untouched, the seek line is gone', async () => {
    const m = await mount();
    await act(async () => { fireEvent.click(m.chip(VWAV_DAY, pwVWAV.text)); });
    await m.landOn('winners', VWAV_REEL);
    const other = m.row('winners', '2026-10-02_VWAV_45x.mp4')!;
    await act(async () => { fireEvent.click(other.querySelector('button[aria-label="play"]')!); });
    const v = other.querySelector('video')! as HTMLVideoElement;
    expect(v.getAttribute('src')).toBe(`${API}${wsrc('winners', '2026-10-02_VWAV_45x.mp4')}`);
    expect(sectionVideos(m.section())).toHaveLength(1);
    v.currentTime = 3;
    fireEvent.loadedMetadata(v);
    expect(v.currentTime).toBe(3);
    expect(m.queryByTestId('rpw-seek')).toBeNull();
    expect(other.classList.contains('rpw-focus')).toBe(false);
    expect(other.hasAttribute('tabindex')).toBe(false);
  });
  it('11: a multi-day entry → reel=multiday/…, the multi-day row gets the video, opens at the start with the none words', async () => {
    const m = await mount();
    const a = m.chip(AKAN_DAY, pwRUN.text);
    expect(a.getAttribute('href')).toContain(`reel=multiday%2F${AKAN_RUN}`);
    await act(async () => { fireEvent.click(a); });
    await m.landOn('multiday', AKAN_RUN);
    const v = m.row('multiday', AKAN_RUN)!.querySelector('video')!;
    expect(v.getAttribute('src')).toBe(`${API}${wsrc('multiday', AKAN_RUN)}`);
    expect(m.getByTestId('rpw-seek').textContent).toBe(NONE);
    expect(m.row('multiday', AKAN_RUN)!.classList.contains('rpw-focus')).toBe(true);
    expect(m.q().get('date')).toBe(D20);
  });
  it('14: the remembered filter would hide the row → the row is shown (All in state), localStorage keeps the pick', async () => {
    ls.setItem(RP_SETUP_LS_KEY, 'reversal_squeeze');
    const m = await mount();
    await act(async () => { fireEvent.click(m.chip(VWAV_DAY, pwVWAV.text)); });
    await m.landOn('winners', VWAV_REEL);
    expect(m.getByTestId('rpw-filter-all').getAttribute('aria-pressed')).toBe('true');
    expect(m.row('winners', VWAV_REEL)!.classList.contains('rpw-focus')).toBe(true);
    expect(m.getByTestId('rpw-filter-reversal_squeeze').getAttribute('aria-pressed')).toBe('false');
    expect(ls.getItem(RP_SETUP_LS_KEY)).toBe('reversal_squeeze');
  });
});

describe('🏆 Back and the origin card (tests 4, 5, 18, 19, 21)', () => {
  it('4: Back → card=<11-20>/<file>, no reel; that card outlined + scrolled to; NEGATIVE: no other card outlined or tabbable', async () => {
    const m = await mount();
    await act(async () => { fireEvent.click(m.chip(VWAV_DAY, pwVWAV.text)); });
    await m.landOn('winners', VWAV_REEL);
    await m.back();
    await waitFor(() => expect(m.getByTestId(`rp-card-${VWAV_DAY}`).classList.contains('rp-focus')).toBe(true));
    expect(m.q().get('card')).toBe(`${D20}/${VWAV_DAY}`);
    expect(m.q().has('reel')).toBe(false);
    expect(m.q().get('date')).toBe(D20);
    const card = m.getByTestId(`rp-card-${VWAV_DAY}`);
    expect(scrolledOn(card)).toBe(1);
    expect(card.getAttribute('tabindex')).toBe('-1');
    expect(m.container.querySelectorAll('.rp-focus')).toHaveLength(1);
    expect(m.container.querySelectorAll('.rp-card[tabindex]')).toHaveLength(1);
    expect(m.section().getAttribute('data-state')).toBe('closed');
  });
  it('5 NEGATIVE: a ⌘-click marks nothing (no card) and does not navigate', async () => {
    const m = await mount();
    const before = m.getByTestId('where').textContent;
    const stop = (e: Event) => e.preventDefault();                     // jsdom: no real new-tab navigation
    document.addEventListener('click', stop);
    try {
      await act(async () => { fireEvent.click(m.chip(VWAV_DAY, pwVWAV.text), { metaKey: true }); });
      await act(async () => { fireEvent.click(m.chip(VWAV_DAY, pwVWAV.text), { button: 1 }); });
    } finally { document.removeEventListener('click', stop); }
    expect(m.getByTestId('where').textContent).toBe(before);
    expect(m.q().has('card')).toBe(false);
    expect(m.section().getAttribute('data-state')).toBe('closed');
  });
  it('18 chained: A (date kept) → B (date switch) → Back → card only, no reel, no 🏆 focus; Back again → card A', async () => {
    const m = await mount();
    await act(async () => { fireEvent.click(m.chip(AKAN_DAY, pwAKAN.text)); });
    await m.landOn('winners', AKAN_REEL);
    await act(async () => { fireEvent.click(m.chip(VWAV_DAY, pwVWAV.text)); });
    await m.landOn('winners', VWAV_REEL);
    /* NEGATIVE (stale board): the VWAV row is already open by the URL's sym in the click's own render; it is scrolled to
     * only once the 11-18 board is in — never while the 11-20 cards (about to empty) are still on screen. */
    const onB = calls.filter((c) => c.el === m.row('winners', VWAV_REEL));
    expect(onB).toHaveLength(1);
    expect(onB[0].board).not.toBe('loading');
    expect(onB[0].cards).not.toContain(VWAV_DAY);
    expect(onB[0].cards).toContain('VWAV_x_45x.mp4');
    const n = calls.length;
    await m.back();
    await waitFor(() => expect(m.getByTestId(`rp-card-${VWAV_DAY}`).classList.contains('rp-focus')).toBe(true));
    expect(m.q().get('card')).toBe(`${D20}/${VWAV_DAY}`);
    expect(m.q().has('reel')).toBe(false);
    expect(m.q().get('sym')).toBe('AKAN');
    expect(m.container.querySelectorAll('.rp-focus')).toHaveLength(1);
    expect(m.container.querySelector('.rpw-focus')).toBeNull();
    expect(calls.slice(n).some((c) => c.el.closest('.rpw-section'))).toBe(false);
    await m.back();
    await waitFor(() => expect(m.getByTestId(`rp-card-${AKAN_DAY}`).classList.contains('rp-focus')).toBe(true));
    expect(m.q().get('card')).toBe(`${D20}/${AKAN_DAY}`);
    expect(m.getByTestId(`rp-card-${VWAV_DAY}`).classList.contains('rp-focus')).toBe(false);
    expect(m.section().getAttribute('data-state')).toBe('closed');
  });
  it('19: an origin URL with no date → Back marks card=<SERVED date>/<file> and outlines it', async () => {
    const m = await mount('/chart-maps?tab=replays');
    expect(m.chip(VWAV_DAY, pwVWAV.text).getAttribute('href')).toContain(`date=${D18}`);
    await act(async () => { fireEvent.click(m.chip(VWAV_DAY, pwVWAV.text)); });
    await m.landOn('winners', VWAV_REEL);
    await m.back();
    await waitFor(() => expect(m.getByTestId(`rp-card-${VWAV_DAY}`).classList.contains('rp-focus')).toBe(true));
    expect(m.q().get('card')).toBe(`${D20}/${VWAV_DAY}`);
    expect(m.q().has('date')).toBe(false);
    expect(scrolledOn(m.getByTestId(`rp-card-${VWAV_DAY}`))).toBe(1);
  });
  it('21 NEGATIVE: after Back, another session drops card; the first session again → no outline, no further scroll', async () => {
    const m = await mount();
    await act(async () => { fireEvent.click(m.chip(VWAV_DAY, pwVWAV.text)); });
    await m.landOn('winners', VWAV_REEL);
    await m.back();
    await waitFor(() => expect(m.container.querySelector('.rp-focus')).not.toBeNull());
    const n = calls.length;
    await act(async () => { fireEvent.change(m.getByLabelText('session'), { target: { value: '2026-11-17' } }); });
    await m.settle();
    expect(m.q().has('card')).toBe(false);
    expect(m.q().get('date')).toBe('2026-11-17');
    await act(async () => { fireEvent.change(m.getByLabelText('session'), { target: { value: D20 } }); });
    await m.settle();
    await waitFor(() => expect(m.queryByTestId(`rp-card-${VWAV_DAY}`)).not.toBeNull());
    expect(m.container.querySelector('.rp-focus')).toBeNull();
    expect(calls.length).toBe(n);
  });
});

describe('🏆 the same chip twice (test 17, C1) and a hand-closed row (test 15)', () => {
  const land = async () => {
    const m = await mount();
    await act(async () => { fireEvent.click(m.chip(AKAN_DAY, pwAKAN.text)); });
    await m.landOn('winners', AKAN_REEL);
    return m;
  };
  it('17a: row left open → same URL, scrolled a SECOND time, the SAME video back at 910.65; ONE Back → the origin card', async () => {
    const m = await land();
    const row = m.row('winners', AKAN_REEL)!;
    const v = row.querySelector('video')! as HTMLVideoElement;
    expect(v.getAttribute('src')).toBe(`${API}${wsrc('winners', AKAN_REEL)}#t=910.65`);
    expect(scrolledOn(row)).toBe(1);
    const url = m.getByTestId('where').textContent;
    v.currentTime = 1000;
    await act(async () => { fireEvent.click(m.chip(AKAN_DAY, pwAKAN.text)); });
    await m.settle();
    expect(m.getByTestId('where').textContent).toBe(url);
    expect(scrolledOn(m.row('winners', AKAN_REEL))).toBe(2);
    expect(m.row('winners', AKAN_REEL)!.querySelector('video')).toBe(v);
    expect(v.currentTime).toBe(910.65);
    await m.back();
    await waitFor(() => expect(m.getByTestId(`rp-card-${AKAN_DAY}`).classList.contains('rp-focus')).toBe(true));
    expect(m.q().get('card')).toBe(`${D20}/${AKAN_DAY}`);
    expect(m.q().has('winners')).toBe(false);
    expect(m.q().has('reel')).toBe(false);
  });
  it('17b: row closed by hand → the same chip again opens it with ONE video, outlined', async () => {
    const m = await land();
    await act(async () => { fireEvent.click(m.getByTestId('rpw-stock-toggle-AKAN')); });
    expect(m.row('winners', AKAN_REEL)).toBeNull();
    await act(async () => { fireEvent.click(m.chip(AKAN_DAY, pwAKAN.text)); });
    await m.landOn('winners', AKAN_REEL);
    expect(m.getByTestId('rpw-stock-AKAN').getAttribute('data-open')).toBe('1');
    expect(sectionVideos(m.section())).toHaveLength(1);
    expect(m.row('winners', AKAN_REEL)!.classList.contains('rpw-focus')).toBe(true);
  });
  it('17c NEGATIVE: no second click — a session pick after the landing scrolls the 🏆 row zero extra times, writes no currentTime', async () => {
    const m = await land();
    const row = m.row('winners', AKAN_REEL)!;
    const v = row.querySelector('video')! as HTMLVideoElement;
    v.currentTime = 1000;
    await act(async () => { fireEvent.change(m.getByLabelText('session'), { target: { value: D18 } }); });
    await m.settle();
    expect(m.q().get('date')).toBe(D18);
    expect(m.q().get('reel')).toBe(`winners/${AKAN_REEL}`);
    expect(scrolledOn(m.row('winners', AKAN_REEL))).toBe(1);
    expect(m.row('winners', AKAN_REEL)!.querySelector('video')).toBe(v);
    expect(v.currentTime).toBe(1000);
  });
  it('15: a row closed by hand opens again on a NEW jump to it (another reel of the same stock)', async () => {
    const m = await land();
    await act(async () => { fireEvent.click(m.getByTestId('rpw-stock-toggle-AKAN')); });
    expect(m.getByTestId('rpw-stock-AKAN').getAttribute('data-open')).toBe('0');
    await act(async () => { fireEvent.click(m.chip(AKAN_DAY, pwRUN.text)); });
    await m.landOn('multiday', AKAN_RUN);
    expect(m.getByTestId('rpw-stock-AKAN').getAttribute('data-open')).toBe('1');
    expect(sectionVideos(m.section())).toHaveLength(1);
    expect(m.row('winners', AKAN_REEL)!.querySelector('video')).toBeNull();
    expect(m.row('winners', AKAN_REEL)!.classList.contains('rpw-focus')).toBe(false);
  });
});

describe('🏆 missing targets and a failed GET (tests 7, 8, 9, 20, 22)', () => {
  const missing = async (m: Awaited<ReturnType<typeof mount>>) => {
    await waitFor(() => expect(m.queryByTestId('rpw-jump-missing')).not.toBeNull());
    await m.settle();
    const line = m.getByTestId('rpw-jump-missing');
    expect(line.textContent).toBe(MISSING);
    await waitFor(() => expect(scrolledOn(line)).toBe(1));
    expect(sectionVideos(m.section())).toHaveLength(0);
    expect(m.container.querySelector('.rpw-focus')).toBeNull();
    return line;
  };
  it('7 NEGATIVE: the listing has no such reel → the served sentence, scrolled to; no video, no focus', async () => {
    const win = clone(WIN);
    win.rows[0].videos.shift();
    const m = await mount(`/chart-maps?tab=replays&date=${D20}`, { body: win });
    await act(async () => { fireEvent.click(m.chip(VWAV_DAY, pwVWAV.text)); });
    const line = await missing(m);
    expect(m.section().querySelector('.rpw-section > *:nth-child(2)')).toBe(line);   // the FIRST line of the body
    expect(calls.find((c) => c.el === line)!.board).not.toBe('loading');
  });
  it('8 NEGATIVE: the wrong symbol (sym=AKAN, a VWAV reel) → the sentence; AKAN\'s reels untouched', async () => {
    const m = await mount(`/chart-maps?tab=replays&date=${D18}&winners=1&sym=AKAN&reel=winners%2F${VWAV_REEL}`);
    await missing(m);
    expect(m.getByTestId('rpw-stock-AKAN').getAttribute('data-open')).toBe('1');
    expect(m.row('winners', AKAN_REEL)!.querySelector('video')).toBeNull();
    expect(m.row('winners', VWAV_REEL)).toBeNull();
  });
  it('9 NEGATIVE: the wrong date in the file → the sentence; the 11-18 reel is not opened', async () => {
    const m = await mount(`/chart-maps?tab=replays&date=${D18}&winners=1&sym=VWAV&reel=winners%2F2026-11-19_VWAV_45x.mp4`);
    await missing(m);
    expect(m.row('winners', VWAV_REEL)!.querySelector('video')).toBeNull();
  });
  it('NEGATIVE: an old api with no served sentence prints nothing and scrolls nothing', async () => {
    const win = clone(WIN);
    delete win.jump_missing_text;
    const m = await mount(`/chart-maps?tab=replays&date=${D18}&winners=1&sym=VWAV&reel=winners%2F2026-11-19_VWAV_45x.mp4`, { body: win });
    await waitFor(() => expect(m.section().getAttribute('data-state')).toBe('loaded'));
    expect(m.queryByTestId('rpw-jump-missing')).toBeNull();
    expect(calls).toHaveLength(0);
  });
  it('20: the 🏆 GET fails with a reel → FETCH_FAILED scrolled to; NEGATIVE: no reel → no tabindex, nothing scrolls', async () => {
    let m = await mount(`/chart-maps?tab=replays&date=${D18}&winners=1&sym=VWAV&reel=winners%2F${VWAV_REEL}`, { reject: true });
    await waitFor(() => expect(m.getByTestId('rpw-failed').textContent).toBe(FETCH_FAILED));
    await m.settle();
    await waitFor(() => expect(scrolledOn(m.getByTestId('rpw-failed'))).toBe(1));
    expect(m.getByTestId('rpw-failed').getAttribute('tabindex')).toBe('-1');
    m.unmount();
    vi.unstubAllGlobals();
    calls = [];
    m = await mount(`/chart-maps?tab=replays&date=${D18}&winners=1&sym=VWAV`, { ok: false, status: 500, body: {} });
    await waitFor(() => expect(m.getByTestId('rpw-failed').textContent).toBe(FETCH_FAILED));
    await m.settle();
    expect(m.getByTestId('rpw-failed').hasAttribute('tabindex')).toBe(false);
    expect(m.getByTestId('rpw-failed').className).toBe('rp-line');
    expect(calls).toHaveLength(0);
  });
  it('22 (OC-c): a row served as "Abc" — the chip sym=Abc lands on that row, never the missing sentence', async () => {
    const file = '2026-11-18_Abc_45x.mp4';
    const day = (d: string) => {
      const p = dayOf(d);
      if (d === D20) p.groups[1].videos.push(dayCard(D20, 'Abc_x_45x.mp4', 'Abc', {
        past_winner: [{ ...pwVWAV, file, text: '🏆 past winner 11-18 +40%' }], past_winner_count: 1 }));
      return p;
    };
    const win = clone(WIN);
    win.rows.push({ key: 'sym-Abc', symbol: 'Abc', wins_text: '1 win', filter_keys: [], videos: [
      reel('winners', file, 'Abc', { seek_s: 700.05, seek_text: 'w' })] });
    const m = await mount(`/chart-maps?tab=replays&date=${D20}`, { body: win }, day);
    const a = m.chip('Abc_x_45x.mp4', '🏆 past winner 11-18 +40%');
    expect(a.getAttribute('href')).toContain('sym=Abc');
    await act(async () => { fireEvent.click(a); });
    await m.landOn('winners', file);
    expect(m.getByTestId('rpw-stock-Abc').getAttribute('data-open')).toBe('1');
    expect(m.row('winners', file)!.classList.contains('rpw-focus')).toBe(true);
    expect(m.queryByTestId('rpw-jump-missing')).toBeNull();
  });
});
