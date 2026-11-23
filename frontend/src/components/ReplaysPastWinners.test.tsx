/* 🏆 Past winners section (2026-11-18, pastwinners spec §3.6, WP-APP). Ajay 2026-11-18, verbatim: "can you work on
 * todays videos and also..  Winners in general from the past". The section prints the served payload verbatim (a
 * hand fixture in the backend winners_payload shape). NEGATIVES throughout. RE-PINNED 2026-11-22 (Ajay: "CLRO another
 * example add all the videos may be click them together"): the payload serves one row per stock (`rows`); these tests
 * open every row first, then check the reels exactly as before. */
import { act, fireEvent, render, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import dayFixture from './__fixtures__/replays_2026_11_17.json';
import ReplaysBoard from './ReplaysBoard';
import ReplaysPastWinners from './ReplaysPastWinners';
import { API } from '../lib/apiBase';
import { FETCH_FAILED, RP_PATH, RP_WINNERS_PATH, RP_WINNERS_TITLE } from '../lib/replays';

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
const DAY_READY: any = (dayFixture as any).ready;

const card = (o: Record<string, unknown>) => ({
  kind: 'single_day', kind_text: 'single-day', speed: 45, speed_text: '45x', minutes: 21.4, length_text: '21 min',
  high_pct: 180, spike_print: false, spike_text: null, pick_text: null, ...o,
});
const WIN: any = {
  title: '🏆 Past winners', tab: 'replays', state: 'ready', text: null,
  note: 'Market-wide stocks … descriptive, UNMEASURED, not a signal. Gains are quoted on the close.',
  window: 'served window', window_note: 'Only replays that run the served window (every session) are listed.',
  summary_text: '4 videos · 3 single-day · 1 multi-day',
  counts: { videos: 4, single_day: 3, multi_day: 1, skipped_window: 0, skipped_bad: 0, no_sidecar: 0 },
  rows: [
    { key: 'sym-GP', symbol: 'GP', wins: 1, wins_text: '1 win', newest_text: 'newest Fri 2026-11-13', videos: [
      card({ file: '2026-11-12_GP_45x.mp4', sub: 'winners', src: '/chart-maps/replays/winners/video/winners/2026-11-12_GP_45x.mp4',
        symbol: 'GP', date: '2026-11-12', days: ['2026-11-12'], days_text: '2026-11-12', close_gain_pct: 120,
        gain_text: '+120% on the close', high_text: '+180% high' }),
      card({ file: '2026-11-12_GP_45x.mp4', sub: 'multiday', src: '/chart-maps/replays/winners/video/multiday/2026-11-12_GP_45x.mp4',
        symbol: 'GP', kind: 'multi_day', kind_text: 'multi-day', date: '2026-11-12',
        days: ['2026-11-11', '2026-11-12', '2026-11-13'], days_text: '2026-11-11 → 2026-11-13 · 3 sessions',
        close_gain_pct: 90, gain_text: '+90% best close vs the day before', high_text: '+150% run high',
        pick_text: 'your example — not a +100% run', minutes: 64.0, length_text: '64 min' }),
    ] },
    { key: 'sym-PAVS', symbol: 'PAVS', wins: 1, wins_text: '1 win', newest_text: 'newest Tue 2026-06-09', videos: [
      card({ file: '2026-06-09_PAVS_45x.mp4', sub: 'winners', src: '/chart-maps/replays/winners/video/winners/2026-06-09_PAVS_45x.mp4',
        symbol: 'PAVS', date: '2026-06-09', days: ['2026-06-09'], days_text: '2026-06-09', close_gain_pct: 8,
        gain_text: '+8% on the close', high_text: '+2738% high', spike_print: true,
        spike_text: '⚠ high more than 2× the close — a spike print?' }),
    ] },
    { key: 'sym-DN', symbol: 'DN', wins: 1, wins_text: '1 win', newest_text: 'newest Tue 2026-06-09', videos: [
      card({ file: '2026-06-09_DN_45x.mp4', sub: 'winners', src: '/chart-maps/replays/winners/video/winners/2026-06-09_DN_45x.mp4',
        symbol: 'DN', date: '2026-06-09', days: ['2026-06-09'], days_text: '2026-06-09', close_gain_pct: -12,
        gain_text: '−12% on the close', high_text: null, high_pct: null }),
    ] },
  ],
};
const allRows = (p: any): any[] => p.rows.flatMap((g: any) => g.videos);

type Answer = { ok?: boolean; status?: number; body?: unknown; reject?: boolean };
function stub(route: (url: string) => Answer) {
  const f = vi.fn(async (url: string) => {
    const a = route(String(url));
    if (a.reject) throw new Error('network');
    return { ok: a.ok ?? true, status: a.status ?? 200, json: async () => clone(a.body) };
  });
  vi.stubGlobal('fetch', f);
  return f;
}
const isWin = (url: string) => url === `${API}${RP_WINNERS_PATH}`;
const winCalls = (f: any) => f.mock.calls.filter((c: any[]) => isWin(String(c[0])));
function Where() {
  const loc = useLocation();
  return <output data-testid="where">{loc.search}</output>;
}
async function mountBoard(win: Answer, entry = '/chart-maps?tab=replays') {
  const f = stub((url) => (isWin(url) ? win : { body: DAY_READY }));
  const r = render(<MemoryRouter initialEntries={[entry]}><ReplaysBoard /><Where /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.rp-board:not([data-state="loading"])')).not.toBeNull());
  return { ...r, f };
}
async function mountOpen(win: Answer, entry = '/chart-maps?tab=replays&winners=1') {
  const f = stub((url) => (isWin(url) ? win : { body: DAY_READY }));
  const r = render(<MemoryRouter initialEntries={[entry]}><ReplaysPastWinners /><Where /></MemoryRouter>);
  await waitFor(() => expect(r.getByTestId('rpw-section').getAttribute('data-state')).not.toBe('loading'));
  for (const b of Array.from(r.container.querySelectorAll('[data-testid^="rpw-stock-toggle-"]'))) {
    await act(async () => { fireEvent.click(b); });                       // open every stock row
  }
  return { ...r, f };
}
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

afterEach(() => { vi.unstubAllGlobals(); });

describe('🏆 lazy fetch', () => {
  it('NEGATIVE: no winners GET on the tab mount — the board GET is the only fetch; the section is collapsed', async () => {
    const { f, getByTestId, getByRole, container } = await mountBoard({ body: WIN });
    expect(f).toHaveBeenCalledTimes(1);
    expect(String(f.mock.calls[0][0])).toBe(`${API}${RP_PATH}`);
    expect(winCalls(f)).toHaveLength(0);
    expect(getByTestId('rpw-section').getAttribute('data-state')).toBe('closed');
    const btn = getByRole('button', { name: RP_WINNERS_TITLE });
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    expect(container.querySelector('.rpw-row')).toBeNull();
  });
  it('with winners=1 → exactly ONE winners GET, credentials include, no-store', async () => {
    const { f } = await mountOpen({ body: WIN });
    expect(winCalls(f)).toHaveLength(1);
    expect(winCalls(f)[0][1]).toMatchObject({ credentials: 'include', cache: 'no-store' });
    expect(f).toHaveBeenCalledTimes(1);
  });
  it('the toggle opens it (one GET) and keeps tab and date; closing deletes only winners', async () => {
    const { f, getByRole, getByTestId } = await mountBoard({ body: WIN }, '/chart-maps?tab=replays&date=2026-11-17');
    const btn = getByRole('button', { name: RP_WINNERS_TITLE });
    await act(async () => { fireEvent.click(btn); });
    await waitFor(() => expect(getByTestId('rpw-section').getAttribute('data-state')).toBe('loaded'));
    expect(winCalls(f)).toHaveLength(1);
    expect(f).toHaveBeenCalledTimes(2);                                   // NEGATIVE: the board did not refetch
    let q = new URLSearchParams(getByTestId('where').textContent!);
    expect(q.get('tab')).toBe('replays');
    expect(q.get('date')).toBe('2026-11-17');
    expect(q.get('winners')).toBe('1');
    await act(async () => { fireEvent.click(btn); });
    q = new URLSearchParams(getByTestId('where').textContent!);
    expect(q.has('winners')).toBe(false);
    expect(q.get('tab')).toBe('replays');
    expect(q.get('date')).toBe('2026-11-17');
    expect(getByTestId('rpw-section').getAttribute('data-state')).toBe('closed');
  });
  it('NEGATIVE: a failed winners GET prints FETCH_FAILED inside the section; .rp-board text unchanged', async () => {
    const ok = await mountBoard({ body: WIN });
    const before = ok.container.querySelector('.rp-board')!.textContent;
    ok.unmount();
    vi.unstubAllGlobals();
    for (const a of [{ reject: true }, { ok: false, status: 404, body: { detail: 'Not Found' } }, { body: { state: 'x' } }]) {
      const r = await mountBoard(a as Answer, '/chart-maps?tab=replays&winners=1');
      await waitFor(() => expect(r.getByTestId('rpw-failed').textContent).toBe(FETCH_FAILED));
      expect(r.getByTestId('rpw-section').contains(r.getByTestId('rpw-failed'))).toBe(true);
      expect(r.container.querySelector('.rp-board')!.textContent).toBe(before);
      expect(r.container.querySelector('.rpw-section video')).toBeNull();
      r.unmount();
      vi.unstubAllGlobals();
    }
  });
});

describe('🏆 ready — every word is served', () => {
  it('note, window note, summary, one stock header per served row, one reel row per served card in served order', async () => {
    const { getByTestId, container } = await mountOpen({ body: WIN });
    expect(getByTestId('rpw-note').textContent).toBe(WIN.note);
    expect(getByTestId('rpw-window-note').textContent).toBe(WIN.window_note);
    expect(getByTestId('rpw-summary').textContent).toBe(WIN.summary_text);
    expect(Array.from(container.querySelectorAll('.rpw-stock-head')).map((h) => h.textContent))
      .toEqual(WIN.rows.map((g: any) => `${g.symbol}${g.wins_text}${g.newest_text}`));
    const rows = Array.from(container.querySelectorAll('.rpw-row')).map((r) => r.getAttribute('data-testid'));
    expect(rows).toEqual(allRows(WIN).map((v) => `rpw-row-${v.sub}-${v.file}`));
  });
  it('each row prints its served chips in order (non-strings dropped)', async () => {
    const { getByTestId } = await mountOpen({ body: WIN });
    for (const v of allRows(WIN)) {
      const row = getByTestId(`rpw-row-${v.sub}-${v.file}`);
      const chips = Array.from(row.querySelectorAll('.rpw-chip')).map((c) => c.textContent);
      const want = [v.kind_text, v.gain_text, v.high_text, v.spike_print === true ? v.spike_text : null, v.pick_text,
        v.days_text, v.speed_text, v.length_text].filter((s) => typeof s === 'string');
      expect(chips).toEqual(want);
      expect(row.textContent).toContain(v.symbol);
    }
    expect(getByTestId('rpw-row-winners-2026-06-09_DN_45x.mp4').textContent).toContain('−12%');
  });
  it('the spike chip only when spike_print === true; NEGATIVE: a served spike_text with spike_print false/"true" prints nothing', async () => {
    const body = clone(WIN);
    body.rows[0].videos[0].spike_text = 'SPIKE-SHOULD-NOT-SHOW';
    body.rows[0].videos[1].spike_text = 'SPIKE-STRING-TRUE';
    body.rows[0].videos[1].spike_print = 'true';
    const { container, getAllByTestId } = await mountOpen({ body });
    expect(getAllByTestId('rpw-spike')).toHaveLength(1);
    expect(getAllByTestId('rpw-spike')[0].textContent).toBe(WIN.rows[1].videos[0].spike_text);
    expect(container.textContent).not.toContain('SPIKE-SHOULD-NOT-SHOW');
    expect(container.textContent).not.toContain('SPIKE-STRING-TRUE');
  });
  it('NEGATIVE: non-string chips are dropped and NaN / numbers print nothing', async () => {
    const body = clone(WIN);
    const v = body.rows[0].videos[0];
    v.gain_text = 42; v.high_text = { x: 1 }; v.pick_text = ['a']; v.days_text = null; v.speed_text = NaN;
    const { getByTestId } = await mountOpen({ body });
    const chips = Array.from(getByTestId(`rpw-row-${v.sub}-${v.file}`).querySelectorAll('.rpw-chip')).map((c) => c.textContent);
    expect(chips).toEqual([v.kind_text, v.length_text]);
    expect(getByTestId(`rpw-row-${v.sub}-${v.file}`).textContent).not.toMatch(/NaN|42|\[object/);
  });
  it('rows are text until tapped: NO <video> before a tap', async () => {
    const { container } = await mountOpen({ body: WIN });
    expect(container.querySelectorAll('video')).toHaveLength(0);
  });
  it('ONE <video> at a time, under the tapped row; tapping another row moves it; attrs controls / metadata / playsinline', async () => {
    const { container, getByTestId } = await mountOpen({ body: WIN });
    const [a, b] = allRows(WIN);
    const rowA = getByTestId(`rpw-row-${a.sub}-${a.file}`);
    await act(async () => { fireEvent.click(rowA.querySelector('button[aria-label="play"]')!); });
    let vids = Array.from(container.querySelectorAll('video'));
    expect(vids).toHaveLength(1);
    expect(rowA.contains(vids[0])).toBe(true);
    expect(vids[0].getAttribute('src')).toBe(`${API}${a.src}`);
    const rowB = getByTestId(`rpw-row-${b.sub}-${b.file}`);               // same file name, other sub → its own row
    await act(async () => { fireEvent.click(rowB.querySelector('button[aria-label="play"]')!); });
    vids = Array.from(container.querySelectorAll('video'));
    expect(vids).toHaveLength(1);
    expect(rowB.contains(vids[0])).toBe(true);
    expect(rowA.querySelector('video')).toBeNull();
    expect(vids[0].getAttribute('src')).toBe(`${API}${b.src}`);
    const el = vids[0];
    expect(el.hasAttribute('controls')).toBe(true);
    expect(el.getAttribute('preload')).toBe('metadata');
    expect(el.hasAttribute('playsinline')).toBe(true);
    for (const x of ['autoplay', 'muted', 'poster', 'download', 'loop']) expect(el.hasAttribute(x)).toBe(false);
  });
  it('NEGATIVE: a served src off the 🏆 route → no ▶ and no <video> for that row', async () => {
    const body = clone(WIN);
    body.rows[0].videos[0].src = '/chart-maps/replays/video/2026-11-17/x.mp4';
    body.rows[0].videos[1].src = 'https://elsewhere.example/x.mp4';
    const { container, getByTestId } = await mountOpen({ body });
    for (const v of body.rows[0].videos) {
      expect(getByTestId(`rpw-row-${v.sub}-${v.file}`).querySelector('button[aria-label="play"]')).toBeNull();
    }
    expect(container.querySelectorAll('button[aria-label="play"]')).toHaveLength(2);
    expect(container.querySelectorAll('video')).toHaveLength(0);
  });
});

describe('🏆 empty and no_folder', () => {
  it('print the served text; NEGATIVE: no rows, no note, no video', async () => {
    for (const state of ['empty', 'no_folder']) {
      const body = { ...clone(WIN), state, text: `served ${state} text`, rows: clone(WIN.rows) };
      const r = await mountOpen({ body });
      expect(r.getByTestId('rpw-text').textContent).toBe(`served ${state} text`);
      expect(r.container.querySelector('.rpw-row')).toBeNull();
      expect(r.queryByTestId('rpw-note')).toBeNull();
      expect(r.container.querySelector('video')).toBeNull();
      r.unmount();
      vi.unstubAllGlobals();
    }
  });
});

describe('🏆 source guards', () => {
  it('NEGATIVE: no window literal, no admin email, no b-word, no "edge"', async () => {
    const src = await readSource('src/components/ReplaysPastWinners.tsx');
    expect(src).not.toContain('04:00-20:00');
    expect(src).not.toMatch(/ajaykandakatla/i);
    expect(src).not.toMatch(/bounc/i);
    expect(src).not.toMatch(/\bedge\b/i);
    expect(src).not.toMatch(/autoPlay/);
  });
  it('the <video> attrs, rpWinnerSrc, the functional setParams and the two written exemptions', async () => {
    const src = await readSource('src/components/ReplaysPastWinners.tsx');
    const vids = src.match(/<video\b[^>]*\/?>/g) || [];
    expect(vids).toHaveLength(1);
    for (const v of vids) {
      expect(v).toMatch(/\bcontrols\b/);
      expect(v).toContain('preload="metadata"');
      expect(v).toMatch(/\bplaysInline\b/);
      for (const bad of [/\bautoPlay\b/, /\bmuted\b/, /\bposter\b/, /\bdownload\b/]) expect(v).not.toMatch(bad);
    }
    expect(src).toContain('rpWinnerSrc(v)');
    expect(src).toMatch(/setParams\(\(prev\) => rpWinnersParams\(prev, !open\), \{ replace: true \}\)/);
    expect(src).toContain('No house chips on this tab');
    expect(src).toContain('served group order orders this board');
  });
  it('the board mounts the section in every state', async () => {
    const src = await readSource('src/components/ReplaysBoard.tsx');
    // RE-PINNED 2026-11-22 (pwjump spec §3.5): both props always written out, so one regex pins all three mounts.
    expect((src.match(/<ReplaysPastWinners boardReady=\{(?:true|false)\} jumpN=\{jumpN\} \/>/g) || []).length).toBe(3);
  });
});
