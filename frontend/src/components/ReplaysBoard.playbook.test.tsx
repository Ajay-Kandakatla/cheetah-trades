/* 📚 Playbook learning on 🎬 Replays (2026-11-27, playbookvid spec §3.7 / §4.4 fe-mount). Ajay, verbatim: "I loved the
 * video can you move them under our replay tab with a PLaybook learning and also add it to the playbook tab too with
 * videos". The board mounts <PlaybookVideos where="replays" /> as the FIRST child of all three returns behind a sticky
 * owner flag (`ownerSeen`, set once the board GET answered a 200 with a known state). So: the 📚 section and the 🏆
 * section each keep ONE stable child position — their <video> survives every session pick, 🏆 chip jump and Back.
 * Hand fixtures in the served shapes. NEGATIVES: no section before the first owner answer, none on a first-load
 * 404 / 500 / junk (and none on a later failed pick), zero playbook GET while closed, the source pins. */
import { act, fireEvent, render, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import pbFixture from './__fixtures__/playbook_videos_2026_11_27.json';
import ReplaysBoard from './ReplaysBoard';
import { API } from '../lib/apiBase';
import { FETCH_FAILED, RP_PATH, RP_WINNERS_PATH } from '../lib/replays';
import { PBV_PATH, PBV_WHERE } from '../lib/playbookVideos';

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
const PB_READY: any = (pbFixture as any).ready;
const FILM: any = PB_READY.films[0];
const CH0: any = FILM.chapters[0];
const CH1: any = FILM.chapters[1];
const D20 = '2026-11-20';
const D18 = '2026-11-18';
const D17 = '2026-11-17';
const DATES = [D20, D18, D17];
const AKAN_DAY = 'AKAN_kiss_fly_45x.mp4';
const AKAN_REEL = '2026-11-13_AKAN_45x.mp4';
const pwAKAN = { day: '2026-11-13', kind: 'single_day', close_gain_pct: 120, file: AKAN_REEL, sub: 'winners', text: '🏆 past winner 11-13 +120%' };

const dayCard = (date: string, file: string, symbol: string, extra: Record<string, unknown> = {}) => ({
  file, src: `/chart-maps/replays/video/${date}/${file}`, symbol, setup_text: 'setup', ...extra,
});
function dayOf(date: string): any {
  const videos = date === D20
    ? [dayCard(D20, AKAN_DAY, 'AKAN', { past_winner: [pwAKAN], past_winner_count: 1, past_winner_more_text: null })]
    : [dayCard(date, 'VWAV_x_45x.mp4', 'VWAV')];
  return { state: 'ready', title: 'Replays', tab: 'replays', date, dates: DATES, window_note: 'wn',
    groups: [{ key: 'g1', label: 'Group one', videos }], rs: null };
}
const WIN: any = {
  title: '🏆 Past winners', tab: 'replays', state: 'ready', text: null, note: 'note', window: 'w', window_note: 'wn',
  summary_text: '1 video', counts: {}, jump_missing_text: 'That replay is no longer listed.',
  setups: [{ key: 'all', label: 'All', count: 1 }],
  rows: [{ key: 'sym-AKAN', symbol: 'AKAN', wins_text: '1 win', filter_keys: ['none'], videos: [{
    file: AKAN_REEL, sub: 'winners', src: `/chart-maps/replays/winners/video/winners/${AKAN_REEL}`, symbol: 'AKAN',
    kind: 'single_day', kind_text: 'single-day', spike_print: false, seek_s: 910.65, seek_text: '⏩ peak',
  }] }],
};

type Answer = { ok?: boolean; status?: number; body?: unknown; reject?: boolean; pending?: boolean };
const isPb = (u: string) => u === `${API}${PBV_PATH}`;
const isWin = (u: string) => u === `${API}${RP_WINNERS_PATH}`;
const dateOf = (u: string) => { const m = /\?date=([0-9-]+)$/.exec(u); return m ? m[1] : null; };
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
/* `board(date, n)` answers the n-th board GET (0-based) for that URL date. */
function stub(board: (d: string | null, n: number) => Answer = (d) => ({ body: dayOf(d || D20) }),
  pb: Answer = { body: PB_READY }, win: Answer = { body: WIN }) {
  let n = 0;
  const f = vi.fn((url: string) => {
    const u = String(url);
    const a: Answer = isPb(u) ? pb : isWin(u) ? win : board(dateOf(u), n++);
    if (a.pending) return new Promise(() => undefined);
    if (a.reject) return Promise.reject(new Error('network'));
    return Promise.resolve({ ok: a.ok ?? true, status: a.status ?? 200, json: async () => clone(a.body) });
  });
  vi.stubGlobal('fetch', f);
  vi.stubGlobal('localStorage', mem());
  return f;
}
const pbCalls = (f: any) => f.mock.calls.filter((c: any[]) => isPb(String(c[0])));
const winCalls = (f: any) => f.mock.calls.filter((c: any[]) => isWin(String(c[0])));
const boardCalls = (f: any) => f.mock.calls.filter((c: any[]) => String(c[0]).startsWith(`${API}${RP_PATH}`)
  && !isPb(String(c[0])) && !isWin(String(c[0])));

function Where() {
  const loc = useLocation();
  return <output data-testid="where">{loc.search}</output>;
}
function Back() {
  const nav = useNavigate();
  return <button type="button" data-testid="back" onClick={() => nav(-1)}>back</button>;
}
function GoD18() {
  const nav = useNavigate();
  return <button type="button" data-testid="go-d18" onClick={() => nav(`/chart-maps?tab=replays&date=${D18}&playbook=1`)}>go</button>;
}
const orig = (Element.prototype as any).scrollIntoView;
beforeEach(() => { (Element.prototype as any).scrollIntoView = vi.fn(); });
afterEach(() => { (Element.prototype as any).scrollIntoView = orig; vi.unstubAllGlobals(); });

async function mount(entry = `/chart-maps?tab=replays&date=${D20}`, f = stub()) {
  const r = render(<MemoryRouter initialEntries={[entry]}><ReplaysBoard /><Where /><Back /><GoD18 /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.rp-board:not([data-state="loading"])')).not.toBeNull());
  const q = () => new URLSearchParams(r.getByTestId('where').textContent || '');
  const section = () => r.queryByTestId('pbv-section');
  const settle = async () => waitFor(() => {
    expect(r.container.querySelector('.rp-board:not([data-state="loading"])')).not.toBeNull();
  });
  const pick = async (d: string) => {
    await act(async () => { fireEvent.change(r.getByLabelText('session'), { target: { value: d } }); });
    await settle();
  };
  const playChapter = async (ch: any) => {
    await waitFor(() => expect(r.queryByTestId(`pbv-play-${FILM.slug}-${ch.key}`)).not.toBeNull());
    await act(async () => { fireEvent.click(r.getByTestId(`pbv-play-${FILM.slug}-${ch.key}`)); });
    await waitFor(() => expect(r.queryByTestId('pbv-video')).not.toBeNull());
    return r.getByTestId('pbv-video') as HTMLVideoElement;
  };
  return { ...r, f, q, section, settle, pick, playChapter };
}

describe('📚 the slot — position and the one GET', () => {
  it('after the board loads the section is the element right before .rp-board, closed, titled; ZERO playbook GET', async () => {
    const m = await mount();
    await waitFor(() => expect(m.section()).not.toBeNull());
    const s = m.section()!;
    expect(s.nextElementSibling).toBe(m.container.querySelector('.rp-board'));
    expect(s.getAttribute('data-where')).toBe('replays');
    expect(s.getAttribute('data-state')).toBe('closed');
    expect(m.getByTestId('pbv-toggle').textContent).toContain(PBV_WHERE.replays.title);
    expect(m.f).toHaveBeenCalledTimes(1);
    expect(pbCalls(m.f)).toHaveLength(0);
    /* the 🏆 section is unchanged below the board */
    expect(m.container.querySelector('.rp-board')!.nextElementSibling).toBe(m.getByTestId('rpw-section'));
  });
  it('?playbook=1 opens it and lists the fixture; a date pick keeps playbook=1', async () => {
    const m = await mount(`/chart-maps?tab=replays&date=${D20}&playbook=1`);
    await waitFor(() => expect(m.section()?.getAttribute('data-state')).toBe('ready'));
    expect(m.getByTestId(`pbv-film-${FILM.slug}`)).toBeTruthy();
    expect(m.getByTestId(`pbv-row-${FILM.slug}-${CH0.key}`).textContent).toContain(CH0.title);
    expect(m.getByTestId(`pbv-row-${FILM.slug}-${CH1.key}`)).toBeTruthy();
    await m.pick(D18);
    expect(m.q().get('date')).toBe(D18);
    expect(m.q().get('playbook')).toBe('1');
    expect(pbCalls(m.f)).toHaveLength(1);
  });
});

describe('📚 stays mounted (C2)', () => {
  it('▶ a chapter, currentTime 123 → two session picks → the same node, 123, open, ONE playbook GET', async () => {
    const m = await mount(`/chart-maps?tab=replays&date=${D20}&playbook=1`);
    const s0 = await waitFor(() => { const s = m.section(); expect(s).not.toBeNull(); return s!; });
    const v = await m.playChapter(CH0);
    v.currentTime = 123;
    await m.pick(D18);
    await m.pick(D17);
    expect(m.q().get('date')).toBe(D17);
    expect(m.section()).toBe(s0);
    expect(m.getByTestId('pbv-video')).toBe(v);
    expect(v.currentTime).toBe(123);
    expect(m.section()!.getAttribute('data-state')).toBe('ready');
    expect(pbCalls(m.f)).toHaveLength(1);
    expect(boardCalls(m.f)).toHaveLength(3);
  });
  it('the same across a 🏆 chip jump (date + winners=1&reel=…) and Back', async () => {
    const m = await mount(`/chart-maps?tab=replays&date=${D20}&playbook=1`);
    const v = await m.playChapter(CH0);
    v.currentTime = 123;
    const chip = Array.from(m.getByTestId(`rp-card-${AKAN_DAY}`).querySelectorAll('[data-testid="rp-pastwin"]'))
      .find((e) => e.textContent === pwAKAN.text) as HTMLElement;
    await act(async () => { fireEvent.click(chip); });
    await waitFor(() => expect(m.q().get('winners')).toBe('1'));
    expect(m.q().get('reel')).toBe(`winners/${AKAN_REEL}`);
    expect(m.q().get('playbook')).toBe('1');
    await waitFor(() => expect(m.queryByTestId(`rpw-row-winners-${AKAN_REEL}`)?.querySelector('video')).toBeTruthy());
    await m.settle();
    expect(m.getByTestId('pbv-video')).toBe(v);
    expect(v.currentTime).toBe(123);
    await act(async () => { fireEvent.click(m.getByTestId('back')); });
    await m.settle();
    expect(m.q().has('reel')).toBe(false);
    expect(m.getByTestId('pbv-video')).toBe(v);
    expect(v.currentTime).toBe(123);
    expect(m.section()!.getAttribute('data-state')).toBe('ready');
    expect(pbCalls(m.f)).toHaveLength(1);
  });
});

describe('🏆 keeps its place with 📚 open (C1)', () => {
  it('a 🏆 reel playing + 📚 open and listed → a session pick: the same 🏆 <video>, its currentTime, ONE winners GET', async () => {
    const m = await mount(`/chart-maps?tab=replays&date=${D20}&playbook=1`);
    await waitFor(() => expect(m.section()?.getAttribute('data-state')).toBe('ready'));
    const chip = Array.from(m.getByTestId(`rp-card-${AKAN_DAY}`).querySelectorAll('[data-testid="rp-pastwin"]'))
      .find((e) => e.textContent === pwAKAN.text) as HTMLElement;
    await act(async () => { fireEvent.click(chip); });
    await waitFor(() => expect(m.queryByTestId(`rpw-row-winners-${AKAN_REEL}`)?.querySelector('video')).toBeTruthy());
    await m.settle();
    const wv = m.getByTestId(`rpw-row-winners-${AKAN_REEL}`).querySelector('video') as HTMLVideoElement;
    wv.currentTime = 1000;
    await m.pick(D17);
    expect(m.q().get('date')).toBe(D17);
    expect(m.getByTestId(`rpw-row-winners-${AKAN_REEL}`).querySelector('video')).toBe(wv);
    expect(wv.currentTime).toBe(1000);
    expect(winCalls(m.f)).toHaveLength(1);
    expect(m.section()!.getAttribute('data-state')).toBe('ready');
  });
});

describe('📚 sticky across a later failed load', () => {
  it('first load OK, then a pick whose GET answers 500 → the same section node; .rp-board text is exactly FETCH_FAILED', async () => {
    const f = stub((d, n) => (n === 0 ? { body: dayOf(d || D20) } : { ok: false, status: 500, body: {} }));
    const m = await mount(`/chart-maps?tab=replays&date=${D20}`, f);
    const s0 = await waitFor(() => { const s = m.section(); expect(s).not.toBeNull(); return s!; });
    await m.pick(D18);
    await waitFor(() => expect(m.container.querySelector('.rp-board')!.getAttribute('data-state')).toBe('failed'));
    expect(m.section()).toBe(s0);
    expect(m.container.querySelector('.rp-board')!.textContent).toBe(FETCH_FAILED);
    expect(m.container.querySelector('.rp-board')!.contains(s0)).toBe(false);
  });
});

describe('📚 NEGATIVES — no section without an owner answer', () => {
  it('BEFORE the first owner answer (board GET pending) → no pbv-section', async () => {
    const f = stub(() => ({ pending: true }));
    const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=replays&playbook=1']}><ReplaysBoard /></MemoryRouter>);
    await act(async () => { await Promise.resolve(); });
    expect(r.container.querySelector('.rp-board')!.getAttribute('data-state')).toBe('loading');
    expect(r.queryByTestId('pbv-section')).toBeNull();
    expect(pbCalls(f)).toHaveLength(0);
  });
  const firsts: [string, Answer][] = [
    ['a 404 (non-owner)', { ok: false, status: 404, body: { detail: 'Not Found' } }],
    ['a 500', { ok: false, status: 500, body: {} }],
    ['a junk body', { body: { state: 'whatever' } }],
    ['a rejected fetch', { reject: true }],
  ];
  for (const [name, a] of firsts) {
    it(`a first-load ${name} → FETCH_FAILED and NO pbv-section; a later failed pick still none; ZERO playbook GET`, async () => {
      const f = stub(() => a);
      const m = await mount(`/chart-maps?tab=replays&date=${D20}&playbook=1`, f);
      expect(m.getByTestId('rp-failed').textContent).toBe(FETCH_FAILED);
      expect(m.section()).toBeNull();
      expect(m.container.querySelector('[data-testid^="pbv-"]')).toBeNull();
      await act(async () => { fireEvent.click(m.getByTestId('go-d18')); });
      await m.settle();
      expect(m.q().get('date')).toBe(D18);
      expect(boardCalls(f)).toHaveLength(2);
      expect(m.getByTestId('rp-failed').textContent).toBe(FETCH_FAILED);
      expect(m.section()).toBeNull();
      expect(pbCalls(f)).toHaveLength(0);
    });
  }
  it('closed on mount → the fetch spy has exactly ONE call, the board\'s', async () => {
    const m = await mount();
    await waitFor(() => expect(m.section()).not.toBeNull());
    expect(m.f).toHaveBeenCalledTimes(1);
    expect(boardCalls(m.f)).toHaveLength(1);
  });
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const count = (s: string, needle: string) => s.split(needle).length - 1;

describe('📚 source pins (§4.4)', () => {
  it('ReplaysBoard.tsx: the slot once, {pbSlot} three times, setOwnerSeen(true) once, no /auth/me, no useCurrentUser', async () => {
    const src = await readSource('src/components/ReplaysBoard.tsx');
    expect(count(src, '<PlaybookVideos where="replays" />')).toBe(1);
    expect(src).toContain('const pbSlot = ownerSeen ? <PlaybookVideos where="replays" /> : null;');
    expect(count(src, '{pbSlot}')).toBe(3);
    expect(count(src, 'setOwnerSeen(true)')).toBe(1);
    expect(src).not.toContain('useCurrentUser');
    expect(src).not.toContain('/auth/me');
    expect(src).not.toContain('PlaybookVideosOwner');
  });
  it('GajjalaBoard.tsx: <PlaybookVideosOwner where="playbook" /> once and no bare <PlaybookVideos ', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    expect(count(src, '<PlaybookVideosOwner where="playbook" />')).toBe(1);
    expect(src).not.toMatch(/<PlaybookVideos\s/);
  });
});
