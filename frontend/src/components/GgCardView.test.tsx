import { act, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import watchFixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import { GGC_FETCH_FAILED, GGC_PATH, GGC_STRETCH_ORDER } from '../lib/gajjalaCardView';
import type { GgTile } from '../lib/gajjala';
import { GgCardView } from './GgCardView';

/* GgCardView on its own (2026-11-16, ggcard3 spec WP-D) — the REAL PatternChart / GgwStretch / Frame over a routed fetch
 * stub. Ajay: "when I click on a card from any of the Gajjala I would like us to open the 3 chart extension like in the
 * Watch list" · "instead of 3 mins make it 15 mins timeframe". Frames = CLONES of the 2026-11-15 Watch fixture's OMH
 * frames relabelled 15m / 5m / 1m (never edited). Every word is a stand-in for a served one. NEGATIVES: a re-render with
 * the same [at, boardSeq] never re-GETs; an empty frame draws no svg; an older answer never overwrites a newer symbol's;
 * a failed RE-read keeps the frames on screen. */

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
const LABEL: Record<string, string> = { '15m': '15-min', '5m': '5-min', '1m': '1-min' };

function frame(sym: string, tf: string) {
  const f = clone((watchFixture as any).rows[0].frames.find((x: any) => x.tf === SRC_TF[tf]));
  f.tf = tf;
  f.label = LABEL[tf];
  f.tile.symbol = sym;
  f.as_of_et = '10:30';
  f.stale = false;
  f.empty_text = null;
  return f;
}
const payload = (sym: string, mut: (p: any) => void = () => {}) => {
  const p: any = {
    state: 'ok', symbol: sym, session: '2026-11-13', is_today: true, in_window: true, as_of_et: '10:30', stale: false,
    text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(sym, tf)),
  };
  mut(p);
  return p;
};
const card = (sym: string, plan: string | null = 'served plan: Entry above 4.10 · stop 3.80'): GgTile =>
  ({ symbol: sym, name: null, href: `/sepa/${sym}?tab=supply&tf=5m_today`, bars: [], lines: [], bands: [], markers: [],
     stats: [], why: '', tf: '5m', gajjala: plan ? { plan_text: plan } : null } as unknown as GgTile);

type Answer = { ok: boolean; body: any } | Promise<{ ok: boolean; body: any }>;
let answer: (sym: string, n: number) => Answer = (sym) => ({ ok: true, body: payload(sym) });
const fetchMock = vi.fn(async (url: string) => {
  const sym = decodeURIComponent(String(url).split(GGC_PATH + '/')[1] || '');
  const a = await answer(sym, fetchMock.mock.calls.length);
  return { ok: a.ok, status: a.ok ? 200 : 500, json: async () => a.body };
});
const gets = () => fetchMock.mock.calls.map(([u]) => decodeURIComponent(String(u).split(GGC_PATH + '/')[1] || ''));

const view = (sym: string, seq: number, c: GgTile = card(sym)) => (
  <MemoryRouter>
    <GgCardView card={c} at={sym} variant="gajjala" boardSeq={seq} onClose={() => {}} onStep={null} />
  </MemoryRouter>
);
const svgIn = (sym: string, tf: string) => screen.getByTestId(`ggw-frame-${sym}-${tf}`).querySelector('svg');

beforeEach(() => {
  fetchMock.mockClear();
  answer = (sym) => ({ ok: true, body: payload(sym) });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  document.body.style.overflow = '';
});

describe('GgCardView — the three charts', () => {
  it('draws three real charts, 15m / 5m / 1m, with the card\'s served plan line in the head', async () => {
    render(view('PFAI', 1));
    await waitFor(() => expect(svgIn('PFAI', '1m')).not.toBeNull());
    for (const tf of GGC_STRETCH_ORDER) expect(svgIn('PFAI', tf), tf).not.toBeNull();
    const tile = screen.getByTestId('ggw-stretch-tile-PFAI');
    expect([...tile.querySelectorAll('.ggw-frame')].map((f) => f.getAttribute('data-tf'))).toEqual(['15m', '5m', '1m']);
    expect(within(tile).getByTestId('ggw-row-text').textContent).toBe('served plan: Entry above 4.10 · stop 3.80');
    expect(screen.queryByText(/bounce/i)).toBeNull();
  });

  it('NEGATIVE: an empty frame prints its served words and NO svg; the other two still draw', async () => {
    answer = (sym) => ({ ok: true, body: payload(sym, (p) => {
      p.frames[1].tile.bars = [];
      p.frames[1].tile.curves = [];
      p.frames[1].axis = null;
      p.frames[1].empty_text = 'served words: no 5-minute bars stored';
    }) });
    render(view('PFAI', 1));
    const w = await screen.findByTestId('ggw-frame-empty-PFAI-5m');
    expect(w.textContent).toBe('served words: no 5-minute bars stored');
    expect(svgIn('PFAI', '5m')).toBeNull();
    expect(svgIn('PFAI', '15m')).not.toBeNull();
    expect(svgIn('PFAI', '1m')).not.toBeNull();
  });

  it('a served `text` (no bars at all) prints in the head, never the plan line', async () => {
    answer = (sym) => ({ ok: true, body: payload(sym, (p) => {
      p.text = 'served words: no bars stored for PFAI this session yet';
      for (const f of p.frames) { f.tile.bars = []; f.tile.curves = []; f.axis = null; f.empty_text = 'served empty'; }
    }) });
    render(view('PFAI', 1));
    await waitFor(() => expect(screen.getByTestId('ggw-row-text').textContent)
      .toBe('served words: no bars stored for PFAI this session yet'));
    expect(document.querySelectorAll('.ggw-stretch svg')).toHaveLength(0);
  });

  it('a failed GET prints GGC_FETCH_FAILED; a served error prints its reason verbatim', async () => {
    answer = () => ({ ok: false, body: null });
    const r = render(view('PFAI', 1));
    await waitFor(() => expect(screen.getByTestId('ggw-row-text').textContent).toBe(GGC_FETCH_FAILED));
    r.unmount();
    answer = () => ({ ok: true, body: { state: 'error', reason: 'served reason: KeyError' } });
    render(view('PFAI', 1));
    await waitFor(() => expect(screen.getByTestId('ggw-row-text').textContent).toBe('served reason: KeyError'));
  });

  it('NEGATIVE: loading → no frames and no words until the GET lands', async () => {
    let release: (v: { ok: boolean; body: any }) => void = () => {};
    answer = () => new Promise((res) => { release = res; });
    render(view('PFAI', 1));
    expect(screen.getByTestId('ggw-stretch-tile-PFAI')).toBeTruthy();
    expect(document.querySelectorAll('.ggw-frame')).toHaveLength(0);
    expect(screen.queryByTestId('ggw-row-text')).toBeNull();
    await act(async () => { release({ ok: true, body: payload('PFAI') }); });
    await waitFor(() => expect(document.querySelectorAll('.ggw-frame')).toHaveLength(3));
  });
});

describe('GgCardView — the GET cadence [C1]', () => {
  it('a re-render with the same [at, boardSeq] (a new card object) never re-GETs; boardSeq + 1 re-GETs once', async () => {
    const r = render(view('PFAI', 1));
    await waitFor(() => expect(svgIn('PFAI', '1m')).not.toBeNull());
    for (let i = 0; i < 5; i += 1) r.rerender(view('PFAI', 1, card('PFAI', `served plan ${i}`)));
    await act(async () => {});
    expect(gets()).toEqual(['PFAI']);
    r.rerender(view('PFAI', 2));
    await waitFor(() => expect(gets()).toEqual(['PFAI', 'PFAI']));
  });

  it('NEGATIVE: an older symbol\'s late answer never overwrites the newer symbol', async () => {
    let releaseOld: (v: { ok: boolean; body: any }) => void = () => {};
    answer = (sym) => (sym === 'PFAI' ? new Promise((res) => { releaseOld = res; }) : { ok: true, body: payload(sym) });
    const r = render(view('PFAI', 1));
    r.rerender(view('BKYI', 1));
    await waitFor(() => expect(svgIn('BKYI', '1m')).not.toBeNull());
    await act(async () => { releaseOld({ ok: true, body: payload('PFAI') }); });
    expect(screen.getByTestId('ggw-stretch-tile-BKYI')).toBeTruthy();
    expect(screen.queryByTestId('ggw-frame-PFAI-1m')).toBeNull();
    expect(gets()).toEqual(['PFAI', 'BKYI']);
  });

  it('a failed RE-read (boardSeq + 1) keeps the frames already on screen', async () => {
    const r = render(view('PFAI', 1));
    await waitFor(() => expect(svgIn('PFAI', '1m')).not.toBeNull());
    answer = () => ({ ok: false, body: null });
    r.rerender(view('PFAI', 2));
    await waitFor(() => expect(gets()).toHaveLength(2));
    await act(async () => {});
    expect(svgIn('PFAI', '1m')).not.toBeNull();
    expect(screen.queryByText(GGC_FETCH_FAILED)).toBeNull();
  });
});
