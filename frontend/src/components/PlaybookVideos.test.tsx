/* 📚 Playbook learning / 🎬 Videos — the shared section (2026-11-27, playbookvid spec §3.6, §4.3 WP fe-core).
 * Ajay 2026-11-27 ~02:15 ET, verbatim: "I loved the video can you move them under our replay tab with a PLaybook
 * learning and also add it to the playbook tab too with videos". The section prints the served payload verbatim (a hand
 * fixture in the backend playbook.payload shape). useCurrentUser is mocked (never the fetch — its module cache). The
 * matchMedia stub KEEPS its `change` listeners so a test can turn the phone (the latch, C3). NEGATIVES throughout. */
import { act, fireEvent, render, waitFor } from '@testing-library/react';
import { MemoryRouter, useSearchParams } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/playbook_videos_2026_11_27.json';
import { PlaybookVideos, PlaybookVideosOwner } from './PlaybookVideos';
import { API } from '../lib/apiBase';
import { PBV_FETCH_FAILED, PBV_PATH } from '../lib/playbookVideos';

let userRet: any = null;
let loadingRet = false;
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: loadingRet }) }));

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
const READY: any = (fixture as any).ready;
const PARTIAL: any = (fixture as any).partial;
const EMPTY: any = (fixture as any).empty;
const NO_FOLDER: any = (fixture as any).no_folder;
const SLUG = '2026-11-27_gg_film';
const V = (file: string) => `${API}${PBV_PATH}/video/${SLUG}/${file}`;
const OWNER = { email: 'o', display_name: 'o', given_name: null, picture: null, is_default_user: false, is_admin: true, is_primary_admin: true };
const CO_OWNER = { ...OWNER, is_primary_admin: false };

type Answer = { status?: number; body?: unknown; reject?: boolean; junk?: boolean; pending?: boolean };
function stub(a: Answer) {
  const f = vi.fn((url: string, init?: RequestInit) => {
    void url; void init;
    if (a.pending) return new Promise(() => undefined);
    if (a.reject) return Promise.reject(new Error('network'));
    const status = a.status ?? 200;
    return Promise.resolve({
      ok: status >= 200 && status < 300, status,
      json: async () => { if (a.junk) throw new SyntaxError('junk'); return clone(a.body); },
    });
  });
  vi.stubGlobal('fetch', f);
  return f;
}
const pbvCalls = (f: any) => f.mock.calls.filter((c: any[]) => String(c[0]) === `${API}${PBV_PATH}`);

/* A matchMedia stub that keeps its listeners: flip(m) changes `matches` and fires every `change` listener. */
function media(phone: boolean) {
  const state = { matches: phone };
  const listeners = new Set<() => void>();
  vi.stubGlobal('matchMedia', (q: string) => ({
    get matches() { return state.matches; }, media: q, onchange: null,
    addEventListener: (_t: string, h: () => void) => { listeners.add(h); },
    removeEventListener: (_t: string, h: () => void) => { listeners.delete(h); },
    addListener: (h: () => void) => { listeners.add(h); }, removeListener: (h: () => void) => { listeners.delete(h); },
    dispatchEvent: () => true,
  }));
  return {
    flip: async (m: boolean) => { state.matches = m; await act(async () => { listeners.forEach((h) => h()); }); },
    count: () => listeners.size,
  };
}

/* Router helpers: the URL as text, and buttons that change OTHER params (a session pick, a 🏆 chip jump). */
function Nav() {
  const [p, setP] = useSearchParams();
  const set = (kv: Record<string, string>) => setP((prev) => {
    const n = new URLSearchParams(prev);
    for (const [k, v] of Object.entries(kv)) n.set(k, v);
    return n;
  });
  return (
    <div data-testid="nav">
      <output data-testid="where">{p.toString()}</output>
      <button type="button" data-testid="nav-date" onClick={() => set({ date: '2026-11-24' })}>d</button>
      <button type="button" data-testid="nav-date2" onClick={() => set({ date: '2026-11-21' })}>d2</button>
      <button type="button" data-testid="nav-jump" onClick={() => set({ winners: '1', reel: 'winners/x.mp4', date: '2026-11-18' })}>j</button>
    </div>
  );
}
async function mount(ans: Answer, entry = '/chart-maps?tab=replays', where: 'replays' | 'playbook' = 'replays', owner = false) {
  const f = stub(ans);
  const r = render(
    <MemoryRouter initialEntries={[entry]}>
      <div data-testid="host">{owner ? <PlaybookVideosOwner where={where} /> : <PlaybookVideos where={where} />}</div>
      <Nav />
    </MemoryRouter>,
  );
  if (!ans.pending) await act(async () => { await Promise.resolve(); });
  return { ...r, f, host: () => r.getByTestId('host'), q: () => new URLSearchParams(r.getByTestId('where').textContent || '') };
}
const settle = async (r: { getByTestId: (s: string) => HTMLElement }) => {
  await waitFor(() => expect(r.getByTestId('pbv-section').getAttribute('data-state')).not.toBe('loading'));
};
const click = async (el: Element) => { await act(async () => { fireEvent.click(el); }); };
const videos = (c: HTMLElement) => Array.from(c.querySelectorAll('video'));
const rowText = (c: HTMLElement, key: string) => (c.querySelector(`[data-testid="pbv-row-${SLUG}-${key}"]`)?.textContent || '');

let playSpy: any;
beforeEach(() => {
  userRet = null;
  loadingRet = false;
  playSpy = vi.spyOn(HTMLMediaElement.prototype, 'play').mockImplementation(() => Promise.resolve());
});
afterEach(() => { vi.unstubAllGlobals(); playSpy.mockRestore(); });

describe('🎬 where="replays" — closed, lazy', () => {
  it('NEGATIVE: closed on mount → ZERO fetch, the title only, no row', async () => {
    media(false);
    const { f, getByTestId, container } = await mount({ body: READY });
    expect(f).not.toHaveBeenCalled();
    const s = getByTestId('pbv-section');
    expect(s.getAttribute('data-state')).toBe('closed');
    expect(s.getAttribute('data-where')).toBe('replays');
    expect(getByTestId('pbv-toggle').textContent).toBe('📚 Playbook learning');
    expect(getByTestId('pbv-toggle').getAttribute('aria-expanded')).toBe('false');
    expect(container.querySelector('.pbv-row')).toBeNull();
  });
  it('?playbook=1 → ONE GET, credentials include, no-store; rows in served order with the served words', async () => {
    media(false);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    expect(pbvCalls(r.f)).toHaveLength(1);
    expect(r.f).toHaveBeenCalledTimes(1);
    expect(r.f.mock.calls[0][1]).toMatchObject({ credentials: 'include', cache: 'no-store' });
    expect(r.getByTestId('pbv-section').getAttribute('data-state')).toBe('ready');
    expect(r.getByTestId('pbv-note').textContent).toBe(READY.note);
    const film = r.getByTestId(`pbv-film-${SLUG}`);
    expect(film.textContent).toContain("Gajjala's Five Setups · 2 of 9 chapters · 18 min so far");
    expect(film.textContent).toContain('his teaching charts, read bar by bar');
    const rows = Array.from(film.querySelectorAll('.pbv-row')).map((x) => x.getAttribute('data-testid'));
    expect(rows).toEqual([`pbv-row-${SLUG}-00_intro`, `pbv-row-${SLUG}-01_bull_flag`, `pbv-row-${SLUG}-full`]);
    const t1 = rowText(r.container, '01_bull_flag');
    for (const w of ['01', 'Bull Flag', 'a 2 to 5 bar pause at the top of the run', '10:33', '1080p', '186 MB']) expect(t1).toContain(w);
    const tf = rowText(r.container, 'full');
    for (const w of ['Full film', '2 chapters back to back', '17:51', '300 MB']) expect(tf).toContain(w);
    expect(videos(r.container)).toHaveLength(0);                          // NEGATIVE: no video before ▶
  });
  it('the toggle opens it (ONE GET) and keeps tab / date; closing deletes only playbook and removes the video', async () => {
    media(false);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&date=2026-11-25');
    await click(r.getByTestId('pbv-toggle'));
    await settle(r);
    expect(pbvCalls(r.f)).toHaveLength(1);
    expect(r.q().get('playbook')).toBe('1');
    expect(r.q().get('tab')).toBe('replays');
    expect(r.q().get('date')).toBe('2026-11-25');
    await click(r.getByTestId(`pbv-play-${SLUG}-00_intro`));
    expect(videos(r.container)).toHaveLength(1);
    await click(r.getByTestId('pbv-toggle'));
    expect(r.q().has('playbook')).toBe(false);
    expect(r.q().get('date')).toBe('2026-11-25');
    expect(r.getByTestId('pbv-section').getAttribute('data-state')).toBe('closed');
    expect(videos(r.container)).toHaveLength(0);
    expect(pbvCalls(r.f)).toHaveLength(1);                                // NEGATIVE: closing fetches nothing
  });
  it('▶ mounts exactly ONE video (controls, metadata, playsInline); another ▶ moves it; the same ▶ again removes it', async () => {
    media(false);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    await click(r.getByTestId(`pbv-play-${SLUG}-00_intro`));
    let vs = videos(r.container);
    expect(vs).toHaveLength(1);
    expect(vs[0].getAttribute('src')).toBe(V('00_intro.mp4'));
    expect(vs[0].hasAttribute('controls')).toBe(true);
    expect(vs[0].getAttribute('preload')).toBe('metadata');
    expect(vs[0].hasAttribute('playsinline')).toBe(true);
    expect(r.getByTestId(`pbv-row-${SLUG}-00_intro`).contains(vs[0])).toBe(true);
    expect(r.getByTestId(`pbv-play-${SLUG}-00_intro`).getAttribute('aria-pressed')).toBe('true');
    await click(r.getByTestId(`pbv-play-${SLUG}-01_bull_flag`));
    vs = videos(r.container);
    expect(vs).toHaveLength(1);
    expect(vs[0].getAttribute('src')).toBe(V('01_bull_flag.mp4'));
    expect(r.getByTestId(`pbv-row-${SLUG}-01_bull_flag`).contains(vs[0])).toBe(true);
    expect(r.getByTestId(`pbv-play-${SLUG}-00_intro`).getAttribute('aria-pressed')).toBe('false');
    await click(r.getByTestId(`pbv-play-${SLUG}-01_bull_flag`));
    expect(videos(r.container)).toHaveLength(0);
    expect(playSpy).not.toHaveBeenCalled();
  });
});

describe('📱 the size — phone default, latched, the switch', () => {
  it('430 px (matching) → the phone file; 1024 px → the desktop file', async () => {
    media(true);
    const a = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(a);
    expect(a.getByTestId('pbv-variant-phone').getAttribute('aria-pressed')).toBe('true');
    expect(rowText(a.container, '00_intro')).toContain('29 MB');
    await click(a.getByTestId(`pbv-play-${SLUG}-00_intro`));
    expect(videos(a.container)[0].getAttribute('src')).toBe(V('00_intro_phone.mp4'));
    a.unmount();
    media(false);
    const b = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(b);
    expect(b.getByTestId('pbv-variant-desktop').getAttribute('aria-pressed')).toBe('true');
    await click(b.getByTestId(`pbv-play-${SLUG}-00_intro`));
    expect(videos(b.container)[0].getAttribute('src')).toBe(V('00_intro.mp4'));
  });
  it('the switch flips the file and keeps the position (restored on loadedmetadata, paused, never .play)', async () => {
    media(true);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    await click(r.getByTestId(`pbv-play-${SLUG}-01_bull_flag`));
    const v = videos(r.container)[0];
    v.currentTime = 42;
    await click(r.getByTestId('pbv-variant-desktop'));
    const v2 = videos(r.container)[0];
    expect(v2.getAttribute('src')).toBe(V('01_bull_flag.mp4'));
    expect(r.getByTestId('pbv-variant-desktop').getAttribute('aria-pressed')).toBe('true');
    expect(r.getByTestId('pbv-variant-phone').getAttribute('aria-pressed')).toBe('false');
    expect(rowText(r.container, '01_bull_flag')).toContain('186 MB');
    v2.currentTime = 0;                                                    // the browser reloads the new file at 0
    fireEvent.loadedMetadata(v2);
    expect(v2.currentTime).toBe(42);
    expect(v2.paused).toBe(true);
    v2.currentTime = 5;                                                    // NEGATIVE: one restore only
    fireEvent.loadedMetadata(v2);
    expect(v2.currentTime).toBe(5);
    expect(playSpy).not.toHaveBeenCalled();
  });
  it('NEGATIVE: 🖥 then 📱 before loadedmetadata → the ORIGINAL position is restored, not 0', async () => {
    media(true);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    await click(r.getByTestId(`pbv-play-${SLUG}-01_bull_flag`));
    const v = videos(r.container)[0];
    expect(v.getAttribute('src')).toBe(V('01_bull_flag_phone.mp4'));
    v.currentTime = 42;
    await click(r.getByTestId('pbv-variant-desktop'));
    const v2 = videos(r.container)[0];
    v2.currentTime = 0;                                                    // the new file has not loaded yet
    await click(r.getByTestId('pbv-variant-phone'));                       // second tap, still no loadedmetadata
    const v3 = videos(r.container)[0];
    expect(v3.getAttribute('src')).toBe(V('01_bull_flag_phone.mp4'));
    v3.currentTime = 0;
    fireEvent.loadedMetadata(v3);
    expect(v3.currentTime).toBe(42);
    expect(v3.paused).toBe(true);
    expect(playSpy).not.toHaveBeenCalled();
  });
  it('NEGATIVE: a switch that does not change the playing file arms no restore', async () => {
    media(true);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    await click(r.getByTestId(`pbv-play-${SLUG}-full`));                   // the full film: desktop only
    const v = videos(r.container)[0];
    expect(v.getAttribute('src')).toBe(V('GG_setups_full.mp4'));
    v.currentTime = 30;
    await click(r.getByTestId('pbv-variant-desktop'));
    v.currentTime = 9;
    fireEvent.loadedMetadata(v);
    expect(v.currentTime).toBe(9);
  });
  it('the default is latched: turned to landscape BEFORE any ▶ → still the phone copy; a tap on 🖥 does switch', async () => {
    const mq = media(true);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    await mq.flip(false);
    expect(r.getByTestId('pbv-variant-phone').getAttribute('aria-pressed')).toBe('true');
    expect(rowText(r.container, '00_intro')).toContain('29 MB');
    expect(rowText(r.container, '00_intro')).toContain('720p');
    await click(r.getByTestId(`pbv-play-${SLUG}-00_intro`));
    expect(videos(r.container)[0].getAttribute('src')).toBe(V('00_intro_phone.mp4'));
    await click(r.getByTestId('pbv-variant-desktop'));
    expect(videos(r.container)[0].getAttribute('src')).toBe(V('00_intro.mp4'));
  });
  it('NEGATIVE latch: ▶ at 430 px, then the phone turns → the SAME video node, same src, same currentTime, same switch', async () => {
    const mq = media(true);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    await click(r.getByTestId(`pbv-play-${SLUG}-00_intro`));
    const v = videos(r.container)[0];
    v.currentTime = 77;
    await mq.flip(false);
    const after = videos(r.container);
    expect(after).toHaveLength(1);
    expect(after[0]).toBe(v);
    expect(after[0].getAttribute('src')).toBe(V('00_intro_phone.mp4'));
    expect(after[0].currentTime).toBe(77);
    expect(r.getByTestId('pbv-variant-phone').getAttribute('aria-pressed')).toBe('true');
    expect(r.getByTestId('pbv-variant-desktop').getAttribute('aria-pressed')).toBe('false');
  });
  it('NEGATIVE latch mirror: mounted at 1024 px, the query flips to matching → still the desktop file', async () => {
    const mq = media(false);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    await click(r.getByTestId(`pbv-play-${SLUG}-01_bull_flag`));
    const v = videos(r.container)[0];
    await mq.flip(true);
    expect(videos(r.container)[0]).toBe(v);
    expect(v.getAttribute('src')).toBe(V('01_bull_flag.mp4'));
    expect(r.getByTestId('pbv-variant-desktop').getAttribute('aria-pressed')).toBe('true');
  });
  it('partial (desktop only) on a phone → the desktop file plays, the chips show the desktop size, no switch', async () => {
    media(true);
    const r = await mount({ body: PARTIAL }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    expect(r.queryByTestId('pbv-variants')).toBeNull();
    const t = rowText(r.container, '00_intro');
    expect(t).toContain('115 MB');
    expect(t).toContain('1080p');
    expect(t).not.toContain('29 MB');
    await click(r.getByTestId(`pbv-play-${SLUG}-00_intro`));
    expect(videos(r.container)[0].getAttribute('src')).toBe(V('00_intro.mp4'));
  });
});

describe('payload shapes', () => {
  it('a third chapter added to the served payload renders with no code change', async () => {
    media(false);
    const p = clone(READY);
    const c = clone(p.films[0].chapters[1]);
    Object.assign(c, { key: '02_kiss_fly', nn: 2, nn_text: '02', id: 'kiss_fly', title: 'EMA Kiss & Fly', subtitle: 'a quiet pullback' });
    p.films[0].chapters.push(c);
    const r = await mount({ body: p }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    expect(rowText(r.container, '02_kiss_fly')).toContain('EMA Kiss & Fly');
    expect(r.getByTestId(`pbv-play-${SLUG}-02_kiss_fly`)).toBeTruthy();
  });
  it('full film: marker buttons appear when it plays; a tap sets currentTime to the served second (never .play)', async () => {
    media(false);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    expect(r.queryByTestId('pbv-markers')).toBeNull();
    await click(r.getByTestId(`pbv-play-${SLUG}-full`));
    const m = r.getByTestId('pbv-markers');
    expect(m.textContent).toContain('0:00 Gajjala\'s Five Setups');
    expect(m.textContent).toContain('7:18 Bull Flag');
    await click(r.getByTestId('pbv-marker-1'));
    expect(videos(r.container)[0].currentTime).toBeCloseTo(438.167, 3);
    await click(r.getByTestId('pbv-marker-0'));
    expect(videos(r.container)[0].currentTime).toBe(0);
    expect(playSpy).not.toHaveBeenCalled();
  });
  it('NEGATIVE: no markers on a chapter row', async () => {
    media(false);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    await click(r.getByTestId(`pbv-play-${SLUG}-00_intro`));
    expect(r.queryByTestId('pbv-markers')).toBeNull();
  });
});

describe('🚩 📓 where="playbook" through PlaybookVideosOwner', () => {
  it('the owner: ONE GET on mount, open by default, title 🎬 Videos', async () => {
    media(false);
    userRet = OWNER;
    const r = await mount({ body: READY }, '/chart-maps?tab=gajjala&sub=playbook', 'playbook', true);
    await settle(r);
    expect(pbvCalls(r.f)).toHaveLength(1);
    expect(r.f).toHaveBeenCalledTimes(1);
    const s = r.getByTestId('pbv-section');
    expect(s.getAttribute('data-where')).toBe('playbook');
    expect(s.getAttribute('data-state')).toBe('ready');
    expect(r.getByTestId('pbv-toggle').textContent).toBe('🎬 Videos');
    expect(r.getByTestId('pbv-toggle').getAttribute('aria-expanded')).toBe('true');
    expect(r.container.querySelectorAll('.pbv-row')).toHaveLength(3);
    await click(r.getByTestId('pbv-toggle'));                              // closing: playbook=0, no second GET
    expect(r.q().get('playbook')).toBe('0');
    expect(r.q().get('sub')).toBe('playbook');
    expect(r.getByTestId('pbv-section').getAttribute('data-state')).toBe('closed');
    await click(r.getByTestId('pbv-toggle'));
    expect(r.q().has('playbook')).toBe(false);
    expect(pbvCalls(r.f)).toHaveLength(1);
  });
  it.each([
    ['a loaded co-owner', CO_OWNER, false],
    ['/auth/me loading', null, true],
    ['user null, loaded', null, false],
  ])('NEGATIVE: %s → empty DOM and ZERO fetch', async (_n, u, l) => {
    media(false);
    userRet = u;
    loadingRet = l as boolean;
    const r = await mount({ body: READY }, '/chart-maps?tab=gajjala&sub=playbook', 'playbook', true);
    expect(r.host().innerHTML).toBe('');
    expect(r.f).not.toHaveBeenCalled();
  });
  it.each([
    ['loading (pending)', { pending: true }],
    ['failed (reject)', { reject: true }],
    ['failed (500)', { status: 500, body: READY }],
    ['empty', { body: EMPTY }],
    ['no_folder', { body: NO_FOLDER }],
  ])('NEGATIVE: %s → empty DOM', async (_n, ans) => {
    media(false);
    userRet = OWNER;
    const r = await mount(ans as Answer, '/chart-maps?tab=gajjala&sub=playbook', 'playbook', true);
    await act(async () => { await Promise.resolve(); });
    expect(r.host().innerHTML).toBe('');
  });
  it('NEGATIVE: ready with zero playable rows → empty DOM', async () => {
    media(false);
    userRet = OWNER;
    const p = clone(READY);
    for (const c of p.films[0].chapters) for (const v of c.variants) v.src = '/chart-maps/replays/video/x.mp4';
    p.films[0].full.variants[0].src = 'https://elsewhere.example/x.mp4';
    const r = await mount({ body: p }, '/chart-maps?tab=gajjala&sub=playbook', 'playbook', true);
    await act(async () => { await Promise.resolve(); });
    expect(r.host().innerHTML).toBe('');
  });
});

describe('🎬 stays mounted (C2)', () => {
  it('NEGATIVE: a date change, then a 🏆 jump (winners + reel) → ONE list GET, the same video node, currentTime kept, open', async () => {
    media(false);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1&date=2026-11-25');
    await settle(r);
    await click(r.getByTestId(`pbv-play-${SLUG}-00_intro`));
    const v = videos(r.container)[0];
    v.currentTime = 123;
    await click(r.getByTestId('nav-date'));
    await click(r.getByTestId('nav-date2'));
    expect(r.q().get('date')).toBe('2026-11-21');
    expect(videos(r.container)[0]).toBe(v);
    expect(v.currentTime).toBe(123);
    await click(r.getByTestId('nav-jump'));
    expect(r.q().get('reel')).toBe('winners/x.mp4');
    expect(r.q().get('playbook')).toBe('1');
    expect(videos(r.container)[0]).toBe(v);
    expect(v.currentTime).toBe(123);
    expect(r.getByTestId('pbv-section').getAttribute('data-state')).toBe('ready');
    expect(pbvCalls(r.f)).toHaveLength(1);
    expect(r.f).toHaveBeenCalledTimes(1);
  });
});

describe('NEGATIVES — answers', () => {
  it.each(['replays', 'playbook'] as const)('HTTP 404 → nothing at all, the title too (%s)', async (where) => {
    media(false);
    userRet = OWNER;
    const entry = where === 'replays' ? '/chart-maps?tab=replays&playbook=1' : '/chart-maps?tab=gajjala&sub=playbook';
    const r = await mount({ status: 404, body: { detail: 'Not Found' } }, entry, where, where === 'playbook');
    await waitFor(() => expect(r.host().innerHTML).toBe(''));
    expect(r.queryByTestId('pbv-toggle')).toBeNull();
    expect(pbvCalls(r.f)).toHaveLength(1);
  });
  it('NEGATIVE: after a 404 a later param change (Back to closed, then open) fires no second GET and shows nothing', async () => {
    media(false);
    const r = await mount({ status: 404 }, '/chart-maps?tab=replays&playbook=1');
    await waitFor(() => expect(r.host().innerHTML).toBe(''));
    await click(r.getByTestId('nav-date'));
    expect(r.host().innerHTML).toBe('');
    expect(pbvCalls(r.f)).toHaveLength(1);
  });
  it.each([
    ['a rejected fetch', { reject: true }],
    ['HTTP 500', { status: 500, body: READY }],
    ['an unknown state', { body: { ...READY, state: 'weird' } }],
    ['a non-object body', { body: 'x' }],
    ['junk JSON', { junk: true }],
  ])('replays: %s → PBV_FETCH_FAILED only, no row, no video', async (_n, ans) => {
    media(false);
    const r = await mount(ans as Answer, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    expect(r.getByTestId('pbv-section').getAttribute('data-state')).toBe('failed');
    expect(r.getByTestId('pbv-failed').textContent).toBe(PBV_FETCH_FAILED);
    expect(r.container.querySelector('.pbv-row')).toBeNull();
    expect(videos(r.container)).toHaveLength(0);
    expect(r.queryByTestId('pbv-note')).toBeNull();
  });
  it.each([['empty', EMPTY], ['no_folder', NO_FOLDER]])('replays: %s → the served text only', async (st, body) => {
    media(false);
    const r = await mount({ body }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    expect(r.getByTestId('pbv-section').getAttribute('data-state')).toBe(st);
    expect(r.getByTestId('pbv-text').textContent).toBe(body.text);
    expect(r.queryByTestId('pbv-note')).toBeNull();
    expect(r.queryByTestId('pbv-variants')).toBeNull();
    expect(r.container.querySelector('.pbv-row')).toBeNull();
    expect(r.queryByTestId('pbv-failed')).toBeNull();
  });
  it('NEGATIVE: a served src off the playbook video route → no ▶ for that variant and never a <video> of it', async () => {
    media(true);
    const p = clone(READY);
    p.films[0].chapters[0].variants[0].src = '/chart-maps/replays/video/2026-11-25/00_intro_phone.mp4';
    for (const v of p.films[0].chapters[1].variants) v.src = 'javascript:alert(1)';
    p.films[0].full.variants[0].src = `https://evil.example${PBV_PATH}/video/${SLUG}/GG_setups_full.mp4`;
    const r = await mount({ body: p }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    expect(rowText(r.container, '00_intro')).toContain('115 MB');          // the playable desktop copy is what will play
    expect(r.queryByTestId(`pbv-play-${SLUG}-01_bull_flag`)).toBeNull();
    expect(rowText(r.container, '01_bull_flag')).toContain('Bull Flag');   // the row stays, as text
    expect(r.queryByTestId(`pbv-play-${SLUG}-full`)).toBeNull();
    await click(r.getByTestId(`pbv-play-${SLUG}-00_intro`));
    const vs = videos(r.container);
    expect(vs).toHaveLength(1);
    expect(vs[0].getAttribute('src')).toBe(V('00_intro.mp4'));
    expect(r.container.innerHTML).not.toContain('javascript:');
    expect(r.container.innerHTML).not.toContain('evil.example');
  });
  it('NEGATIVE: junk fields → no crash, no NaN / undefined / [object in the text', async () => {
    media(false);
    const p = clone(READY);
    p.note = 7;
    p.variant_options = 'x';
    p.films[0].title = 5;
    p.films[0].summary_text = null;
    p.films[0].description = { a: 1 };
    p.films[0].chapters[0].title = 5;
    p.films[0].chapters[0].nn_text = 3;
    p.films[0].chapters[0].variants[0].length_text = NaN;
    p.films[0].chapters[0].variants[0].size_text = null;
    p.films[0].chapters[1].variants = 'x';
    p.films[0].full.markers = null;
    p.films.push({ slug: 'junk', chapters: {} }, 'x', null);
    const r = await mount({ body: p }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    const t = r.container.textContent || '';
    expect(t).not.toMatch(/NaN|undefined|\[object|null/);
    expect(r.queryByTestId('pbv-variants')).toBeNull();
    expect(r.queryByTestId(`pbv-play-${SLUG}-01_bull_flag`)).toBeNull();
    await click(r.getByTestId(`pbv-play-${SLUG}-full`));
    expect(r.queryByTestId('pbv-markers')).toBeNull();
    expect(r.queryByTestId('pbv-film-junk')).toBeNull();
    const r2 = await mount({ body: { ...READY, films: {} } }, '/chart-maps?tab=replays&playbook=1');
    await waitFor(() => expect(r2.getAllByTestId('pbv-section')[1].getAttribute('data-state')).toBe('ready'));
    expect(r2.getAllByTestId('pbv-section')[1].querySelector('.pbv-row')).toBeNull();
  });
  it('NEGATIVE: the <video> never carries autoplay / muted / poster / download; the tree has no <a>', async () => {
    media(false);
    const r = await mount({ body: READY }, '/chart-maps?tab=replays&playbook=1');
    await settle(r);
    for (const k of ['00_intro', '01_bull_flag', 'full']) {
      await click(r.getByTestId(`pbv-play-${SLUG}-${k}`));
      const v = videos(r.container)[0];
      for (const a of ['autoplay', 'muted', 'poster', 'download']) expect(v.hasAttribute(a)).toBe(false);
      expect(v.muted).toBe(false);
      expect(v.autoplay).toBe(false);
      expect(r.host().querySelector('a')).toBeNull();
    }
    expect(playSpy).not.toHaveBeenCalled();
  });
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const FILES = ['src/lib/playbookVideos.ts', 'src/components/PlaybookVideos.tsx', 'src/styles/playbookVideos.css'];

describe('source guards', () => {
  it('NEGATIVE: none of the three new files carries the admin email, the window literal, or the b-word', async () => {
    for (const f of FILES) {
      const src = await readSource(f);
      expect(src).not.toMatch(/@gmail|ajaykandakatla/i);
      expect(src).not.toContain('04:00-20:00');
      expect(src).not.toMatch(/bounc/i);
    }
  });
  it('the component: the video attributes, no autoplay / muted / poster / download, no <a, no .play(, the owner gate', async () => {
    const src = await readSource('src/components/PlaybookVideos.tsx');
    const tag = src.match(/<video\b[^>]*\/>/)![0];
    expect(tag).toMatch(/\bcontrols\b/);
    expect(tag).toContain('preload="metadata"');
    expect(tag).toMatch(/\bplaysInline\b/);
    expect(tag).not.toMatch(/autoPlay|muted|poster|download/);
    expect((src.match(/<video\b/g) || []).length).toBe(1);
    expect(src).not.toMatch(/<a[\s>]/);
    expect(src).not.toContain('.play(');
    expect(src).not.toContain('TickerLink');
    expect(src).toContain('if (loading || !user?.is_primary_admin) return null;');
  });
  it('the size is latched: useState(() => pbvDefaultVariant( once, and nowhere else', async () => {
    const src = await readSource('src/components/PlaybookVideos.tsx');
    expect(src).toContain('useState(() => pbvDefaultVariant(isMobile)');
    expect((src.match(/pbvDefaultVariant\(/g) || []).length).toBe(1);
  });
  it('lib: pbvSrc accepts only the playbook video route', async () => {
    const src = await readSource('src/lib/playbookVideos.ts');
    expect(src).toContain('src.startsWith(`${PBV_PATH}/video/`)');
  });
});
