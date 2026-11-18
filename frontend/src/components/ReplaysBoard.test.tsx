/* 🎬 Replays board (2026-11-17, replays spec §3.3, WP-FE). Ajay: "Can you store the videos in to the app please".
 * The board prints the served payload verbatim (a hand fixture in the §3.1 shape). NEGATIVES throughout. */
import { act, fireEvent, render, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/replays_2026_11_17.json';
import ReplaysBoard from './ReplaysBoard';
import { API } from '../lib/apiBase';
import { FETCH_FAILED, RP_PATH } from '../lib/replays';

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
const READY: any = (fixture as any).ready;
const EMPTY: any = (fixture as any).empty;
const NO_FOLDER: any = (fixture as any).no_folder;

type Answer = { ok?: boolean; status?: number; body?: unknown; reject?: boolean };
function stub(answer: Answer | ((url: string) => Answer)) {
  const f = vi.fn(async (url: string) => {
    const a = typeof answer === 'function' ? answer(String(url)) : answer;
    if (a.reject) throw new Error('network');
    return { ok: a.ok ?? true, status: a.status ?? 200, json: async () => clone(a.body) };
  });
  vi.stubGlobal('fetch', f);
  return f;
}
function Where() {
  const loc = useLocation();
  return <output data-testid="where">{loc.search}</output>;
}
async function mount(answer: Answer | ((url: string) => Answer), entry = '/chart-maps?tab=replays') {
  const f = stub(answer);
  const r = render(<MemoryRouter initialEntries={[entry]}><ReplaysBoard /><Where /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.rp-board:not([data-state="loading"])')).not.toBeNull());
  return { ...r, f };
}
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const allVideos = (p: any): any[] => p.groups.flatMap((g: any) => g.videos);

afterEach(() => { vi.unstubAllGlobals(); });

describe('🎬 the fetch', () => {
  it('ONE fetch on mount, no date, credentials include, no-store', async () => {
    const { f } = await mount({ body: READY });
    expect(f).toHaveBeenCalledTimes(1);
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`${API}${RP_PATH}`);
    expect(init).toMatchObject({ credentials: 'include', cache: 'no-store' });
  });
  it('a ?date= in the URL is sent, encoded', async () => {
    const { f } = await mount({ body: READY }, '/chart-maps?tab=replays&date=2026-11-16');
    expect(String(f.mock.calls[0][0])).toBe(`${API}${RP_PATH}?date=2026-11-16`);
  });
  it('NEGATIVE: a rejected fetch prints FETCH_FAILED only', async () => {
    const { container } = await mount({ reject: true });
    expect(container.querySelector('.rp-board')!.textContent).toBe(FETCH_FAILED);
    expect(container.querySelector('video')).toBeNull();
  });
  it('NEGATIVE: a 404 (non-owner) and a junk body print FETCH_FAILED', async () => {
    let r = await mount({ ok: false, status: 404, body: { detail: 'Not Found' } });
    expect(r.getByTestId('rp-failed').textContent).toBe(FETCH_FAILED);
    r.unmount();
    r = await mount({ body: { state: 'whatever' } });
    expect(r.getByTestId('rp-failed').textContent).toBe(FETCH_FAILED);
  });
});

describe('🎬 ready — every word is served', () => {
  it('title, window note, group labels in served order, the 🎾 tracker title and note', async () => {
    const { container, getByTestId } = await mount({ body: READY });
    expect(getByTestId('rp-title').textContent).toBe(READY.title);
    expect(getByTestId('rp-window-note').textContent).toBe(READY.window_note);
    const labels = Array.from(container.querySelectorAll('.rp-group > h2')).map((h) => h.textContent);
    expect(labels).toEqual(READY.groups.map((g: any) => g.label));
    const keys = Array.from(container.querySelectorAll('.rp-group')).map((s) => s.getAttribute('data-testid'));
    expect(keys).toEqual(READY.groups.map((g: any) => `rp-group-${g.key}`));
    expect(getByTestId('rp-rs').querySelector('h2')!.textContent).toBe(READY.rs.title);
    expect(getByTestId('rp-rs-note').textContent).toBe(READY.rs.note);
  });
  it('each card prints its served chips, why lines and story exactly (the U+2212 grade untouched)', async () => {
    const { getByTestId } = await mount({ body: READY });
    for (const v of allVideos(READY)) {
      const card = getByTestId(`rp-card-${v.file}`);
      const chips = Array.from(card.querySelectorAll('.rp-chip:not([data-testid])')).map((c) => c.textContent);
      expect(chips).toEqual([v.setup_text, v.page_text, v.grade, v.speed_text, v.length_text]);
      expect(Array.from(card.querySelectorAll('.rp-why')).map((w) => w.textContent)).toEqual(v.why);
      expect(card.querySelector('.rp-story')!.textContent).toBe(v.story);
      expect(card.textContent).toContain(v.symbol);
    }
    expect(getByTestId('rp-card-VIVK_kiss_fly_24x.mp4').textContent).toContain('L −1R');
    expect(getByTestId('rp-card-VIVK_kiss_fly_24x.mp4').textContent).not.toContain('L -1R');
  });
  it('one <video> per card: controls, preload=metadata, playsinline, src = API + served src; NEGATIVE: no autoplay / muted / poster / download', async () => {
    const { container } = await mount({ body: READY });
    const vids = Array.from(container.querySelectorAll('video'));
    expect(vids).toHaveLength(allVideos(READY).length);
    vids.forEach((el, i) => {
      expect(el.hasAttribute('controls')).toBe(true);
      expect(el.getAttribute('preload')).toBe('metadata');
      expect(el.hasAttribute('playsinline')).toBe(true);
      expect(el.getAttribute('src')).toBe(`${API}${allVideos(READY)[i].src}`);
      for (const a of ['autoplay', 'muted', 'poster', 'download', 'loop']) expect(el.hasAttribute(a)).toBe(false);
    });
  });
  it('the carried card shows its ring_day chip; NEGATIVE: a same-day card shows none', async () => {
    const { getByTestId } = await mount({ body: READY });
    const carried = allVideos(READY).find((v: any) => v.carried === true);
    expect(getByTestId(`rp-card-${carried.file}`).querySelector('[data-testid="rp-ring-day"]')!.textContent).toBe(carried.ring_day);
    for (const v of allVideos(READY).filter((x: any) => x.carried !== true)) {
      expect(getByTestId(`rp-card-${v.file}`).querySelector('[data-testid="rp-ring-day"]')).toBeNull();
    }
  });
  it('NEGATIVE: carried false with a ring_day served still shows no ring_day chip', async () => {
    const body = clone(READY);
    body.groups[0].videos[0].ring_day = '2026-11-10';
    body.groups[0].videos[0].carried = false;
    const { getByTestId } = await mount({ body });
    expect(getByTestId(`rp-card-${body.groups[0].videos[0].file}`).querySelector('[data-testid="rp-ring-day"]')).toBeNull();
  });
  it('the 🎾 card prints ONE plan line from its served potential fields joined by " · "; NEGATIVE: none elsewhere', async () => {
    const { container, getByTestId } = await mount({ body: READY });
    const v = allVideos(READY).find((x: any) => x.potential);
    const p = v.potential;
    expect(getByTestId(`rp-card-${v.file}`).querySelector('.rp-plan')!.textContent)
      .toBe([p.first_stored_et, p.trigger, p.stop, p.page_text, p.setup_text].join(' · '));
    expect(container.querySelectorAll('.rp-plan')).toHaveLength(1);
  });
  it('the 🎾 table: served column labels and served cells, row by row', async () => {
    const { getByTestId } = await mount({ body: READY });
    const table = getByTestId('rp-rs-table');
    expect(Array.from(table.querySelectorAll('th')).map((t) => t.textContent)).toEqual(READY.rs.columns.map((c: any) => c.label));
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    expect(rows).toHaveLength(READY.rs.rows.length);
    rows.forEach((tr, i) => {
      expect(Array.from(tr.querySelectorAll('td')).map((t) => t.textContent))
        .toEqual(READY.rs.columns.map((c: any) => READY.rs.rows[i].cells[c.key]));
    });
    expect(table.closest('.rp-rs-wrap')).not.toBeNull();
  });
  it('NEGATIVE: an rs block with no rows prints rs.text and no table (and the note still)', async () => {
    const body = clone(READY);
    body.rs.rows = [];
    body.rs.text = 'No 🎾 tracker rows for this session.';
    const { queryByTestId, getByTestId } = await mount({ body });
    expect(queryByTestId('rp-rs-table')).toBeNull();
    expect(getByTestId('rp-rs-text').textContent).toBe(body.rs.text);
    expect(getByTestId('rp-rs-note').textContent).toBe(body.rs.note);
  });
  it('NEGATIVE: a card whose src is off the route renders no <video>', async () => {
    const body = clone(READY);
    body.groups[0].videos[0].src = 'https://elsewhere.example/x.mp4';
    const { container, getByTestId } = await mount({ body });
    expect(getByTestId(`rp-card-${body.groups[0].videos[0].file}`).querySelector('video')).toBeNull();
    expect(container.querySelectorAll('video')).toHaveLength(allVideos(READY).length - 1);
  });
});

describe('🎬 the session select', () => {
  it('lists the served dates in served order; value = served date', async () => {
    const { getByLabelText } = await mount({ body: READY });
    const sel = getByLabelText('session') as HTMLSelectElement;
    expect(Array.from(sel.options).map((o) => o.value)).toEqual(READY.dates);
    expect(sel.value).toBe(READY.date);
    expect(Array.from(sel.options).some((o) => o.disabled)).toBe(false);
  });
  it('[C7] a change refetches with ?date= and keeps a stranger param (NEGATIVE: focus=ABC survives)', async () => {
    const { f, getByLabelText, getByTestId } = await mount({ body: READY }, '/chart-maps?tab=replays&focus=ABC');
    const sel = getByLabelText('session') as HTMLSelectElement;
    await act(async () => { fireEvent.change(sel, { target: { value: '2026-11-13' } }); });
    await waitFor(() => expect(f).toHaveBeenCalledTimes(2));
    expect(String(f.mock.calls[1][0])).toBe(`${API}${RP_PATH}?date=2026-11-13`);
    const q = new URLSearchParams(getByTestId('where').textContent!);
    expect(q.get('tab')).toBe('replays');
    expect(q.get('focus')).toBe('ABC');
    expect(q.get('date')).toBe('2026-11-13');
  });
  it('[C8] empty payload whose date ∉ dates → the select reads the served date, that option disabled', async () => {
    expect(EMPTY.dates).not.toContain(EMPTY.date);
    const { getByLabelText } = await mount({ body: EMPTY }, `/chart-maps?tab=replays&date=${EMPTY.date}`);
    const sel = getByLabelText('session') as HTMLSelectElement;
    expect(sel.value).toBe(EMPTY.date);
    const opt = Array.from(sel.options).find((o) => o.value === EMPTY.date)!;
    expect(opt.disabled).toBe(true);
    expect(Array.from(sel.options).map((o) => o.value)).toEqual([EMPTY.date, ...EMPTY.dates]);
  });
});

describe('🎬 empty and no_folder print the served text (empty: + the served 🎾 tracker)', () => {
  // WIDENED 2026-11-17 (REFIX): the server serves `rs` with `empty` too — a session with 🎾 ledger rows but no
  // full-window video now shows its tracker under the served text. Was: "NEGATIVE: … no tracker".
  it('empty → title + served text + the served tracker block; NEGATIVE: no groups, no video, no window note', async () => {
    const { container, getByTestId, queryByTestId } = await mount({ body: EMPTY });
    expect(getByTestId('rp-text').textContent).toBe(EMPTY.text);
    expect(container.querySelector('.rp-group')).toBeNull();
    expect(container.querySelector('video')).toBeNull();
    expect(queryByTestId('rp-window-note')).toBeNull();
    expect(getByTestId('rp-rs').querySelector('h2')!.textContent).toBe(EMPTY.rs.title);
    expect(getByTestId('rp-rs-note').textContent).toBe(EMPTY.rs.note);
    expect(EMPTY.rs.rows).toHaveLength(0);
    expect(queryByTestId('rp-rs-table')).toBeNull();
    expect(getByTestId('rp-rs-text').textContent).toBe(EMPTY.rs.text);
    expect(container.querySelector('.rp-board')!.textContent)
      .toBe(`${EMPTY.title}${[EMPTY.date, ...EMPTY.dates].join('')}${EMPTY.text}${EMPTY.rs.title}${EMPTY.rs.note}${EMPTY.rs.text}`);
  });
  it('empty with served ledger rows → the tracker table prints every served cell, inside the scroll wrapper', async () => {
    const body = clone(EMPTY);
    body.rs.rows = clone(READY.rs.rows);
    body.rs.columns = clone(READY.rs.columns);
    body.rs.text = null;
    const { container, getByTestId, queryByTestId } = await mount({ body });
    expect(getByTestId('rp-text').textContent).toBe(body.text);
    const table = getByTestId('rp-rs-table');
    expect(Array.from(table.querySelectorAll('th')).map((th) => th.textContent))
      .toEqual(body.rs.columns.map((c: any) => c.label));
    const trs = table.querySelectorAll('tbody tr');
    expect(trs).toHaveLength(body.rs.rows.length);
    trs.forEach((tr, i) => {
      expect(Array.from(tr.querySelectorAll('td')).map((td) => td.textContent))
        .toEqual(body.rs.columns.map((c: any) => body.rs.rows[i].cells[c.key]));
    });
    expect(table.closest('.rp-rs-wrap')).not.toBeNull();
    expect(queryByTestId('rp-rs-text')).toBeNull();
    expect(container.querySelector('video')).toBeNull();
    expect(container.querySelector('.rp-group')).toBeNull();
  });
  it('NEGATIVE: empty with no rs served (null / missing / not an object) → no tracker block', async () => {
    for (const rs of [null, undefined, 'x', 7]) {
      const body = clone(EMPTY);
      if (rs === undefined) delete body.rs; else body.rs = rs;
      const { getByTestId, queryByTestId, unmount } = await mount({ body });
      expect(getByTestId('rp-text').textContent).toBe(EMPTY.text);
      expect(queryByTestId('rp-rs')).toBeNull();
      unmount();
      vi.unstubAllGlobals();
    }
  });
  it('NEGATIVE: an empty body whose groups carry videos still prints no card (empty never renders groups)', async () => {
    const body = clone(EMPTY);
    body.groups = clone(READY.groups);
    const { container } = await mount({ body });
    expect(container.querySelector('.rp-group')).toBeNull();
    expect(container.querySelector('video')).toBeNull();
  });
  it('NEGATIVE: no_folder never prints a tracker, even if an rs block were served', async () => {
    const body = clone(NO_FOLDER);
    body.rs = clone(READY.rs);
    const { getByTestId, queryByTestId } = await mount({ body });
    expect(getByTestId('rp-text').textContent).toBe(NO_FOLDER.text);
    expect(queryByTestId('rp-rs')).toBeNull();
  });
  it('no_folder → its served text; NEGATIVE: no select (no dates served)', async () => {
    const { container, getByTestId, queryByLabelText } = await mount({ body: NO_FOLDER });
    expect(getByTestId('rp-text').textContent).toBe(NO_FOLDER.text);
    expect(queryByLabelText('session')).toBeNull();
    expect(container.querySelector('.rp-board')!.textContent).toBe(`${NO_FOLDER.title}${NO_FOLDER.text}`);
  });
});

describe('🎬 source guards', () => {
  it('NEGATIVE: ReplaysBoard.tsx types no word about a stock, no window and no admin email', async () => {
    const src = await readSource('src/components/ReplaysBoard.tsx');
    for (const w of ['A+', 'winner', 'loser', 'biggest mover', 'Reversal', '04:00', '20:00', 'ajaykandakatla']) {
      expect(src).not.toContain(w);
    }
    expect(src).not.toMatch(/autoPlay/);
  });
  it('carries the two written exemptions the contracts read, and the functional setParams', async () => {
    const src = await readSource('src/components/ReplaysBoard.tsx');
    expect(src).toContain('No house chips on this tab');
    expect(src).toContain('served group order orders this board');
    expect(src).toMatch(/setParams\(\(prev\) => rpDateParams\(prev, v\), \{ replace: true \}\)/);
    expect(src).toMatch(/<video className="rp-video" controls preload="metadata" playsInline/);
  });
});
