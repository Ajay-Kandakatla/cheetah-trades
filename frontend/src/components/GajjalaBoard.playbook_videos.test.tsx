import '../test/ggCardWatchOff';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import pbFixture from './__fixtures__/playbook_videos_2026_11_27.json';

/* 🎬 Videos on 🚩 Gajjala → 📓 Playbook (2026-11-27, playbookvid spec §3.7 / §4.4 fe-mount). Ajay, verbatim: "I loved the
 * video can you move them under our replay tab with a PLaybook learning and also add it to the playbook tab too with
 * videos". PlaybookPanel mounts <PlaybookVideosOwner where="playbook" /> right after the served note. Owner only
 * (is_primary_admin), open by default, quiet (nothing at all unless ready with a playable row). NEGATIVES: a co-owner,
 * /auth/me loading, another sub, a 404 / empty list → no section and the playbook text still renders; the 📓 external
 * links stay target="_blank". */

let userRet: any = null;
let userLoading = false;
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: userLoading }) }));
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
import { API } from '../lib/apiBase';
import { PBV_PATH, PBV_WHERE } from '../lib/playbookVideos';

const BOARDS: Record<string, any> = (fixture as any).boards;
const PB_READY: any = (pbFixture as any).ready;
const PB_EMPTY: any = (pbFixture as any).empty;
const FILM: any = PB_READY.films[0];
const clone = (x: any) => JSON.parse(JSON.stringify(x));
const NOTE = 'his served playbook note';
const OWNER = { email: 'o@x', display_name: 'o', given_name: null, picture: null, is_default_user: false, is_admin: true, is_primary_admin: true };
const CO_OWNER = { ...OWNER, is_primary_admin: false };

type Answer = { ok?: boolean; status?: number; body?: unknown };
const isPb = (url: string) => String(url) === `${API}${PBV_PATH}`;
function stub(pb: Answer = { body: PB_READY }) {
  const spy = vi.fn(async (url: string) => {
    if (isPb(url)) return { ok: pb.ok ?? true, status: pb.status ?? 200, json: async () => clone(pb.body) };
    const u = new URL(String(url), 'http://x');
    const s = u.searchParams.get('sub') || 'bull_flag';
    const b = clone(BOARDS[s] || BOARDS.bull_flag);
    if (s === 'playbook' && b.playbook) b.playbook.note = NOTE;
    return { ok: true, status: 200, json: async () => b };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const pbCalls = (f: any) => f.mock.calls.filter((c: any[]) => isPb(String(c[0])));
const mount = (q: string) => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}>
    <Routes><Route path="/chart-maps" element={<GajjalaBoard />} /></Routes>
  </MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); userRet = null; userLoading = false; });

describe('📓 🎬 Videos — the owner', () => {
  it('owner on sub=playbook → pbv-section inside gg-playbook, after the note, before the first text section, open, listed', async () => {
    userRet = OWNER;
    const f = stub();
    mount('tab=gajjala&sub=playbook');
    const pb = await screen.findByTestId('gg-playbook');
    const s = await screen.findByTestId('pbv-section');
    await waitFor(() => expect(s.getAttribute('data-state')).toBe('ready'));
    expect(pb.contains(s)).toBe(true);
    expect(s.getAttribute('data-where')).toBe('playbook');
    expect(s.previousElementSibling?.textContent).toBe(NOTE);
    expect(s.nextElementSibling?.classList.contains('gg-pb-section')).toBe(true);
    expect(screen.getByTestId('pbv-toggle').textContent).toContain(PBV_WHERE.playbook.title);
    for (const ch of FILM.chapters) expect(screen.getByTestId(`pbv-row-${FILM.slug}-${ch.key}`)).toBeTruthy();
    expect(pbCalls(f)).toHaveLength(1);
  });
  it('with the videos mounted, every <a> on the playbook sub is still an external target="_blank" https link', async () => {
    userRet = OWNER;
    stub();
    const { container } = mount('tab=gajjala&sub=playbook');
    await screen.findByTestId('gg-playbook');
    const s = await screen.findByTestId('pbv-section');
    await waitFor(() => expect(s.getAttribute('data-state')).toBe('ready'));
    const links = [...container.querySelectorAll('a')];
    expect(links.length).toBeGreaterThan(0);
    for (const a of links) {
      expect(a.getAttribute('target')).toBe('_blank');
      expect(a.getAttribute('rel')).toBe('noopener noreferrer');
      expect((a.getAttribute('href') || '').startsWith('https://')).toBe(true);
    }
    expect(s.querySelector('a')).toBeNull();
  });
});

describe('📓 🎬 Videos — NEGATIVES', () => {
  const settled = async () => {
    await screen.findByTestId('gg-playbook');
    await screen.findAllByTestId('gg-pb-section');
    await new Promise((res) => setTimeout(res, 20));
  };
  it('a loaded co-owner (is_admin, not primary) → no pbv-section, no call to PBV_PATH', async () => {
    userRet = CO_OWNER;
    const f = stub();
    mount('tab=gajjala&sub=playbook');
    await settled();
    expect(screen.queryByTestId('pbv-section')).toBeNull();
    expect(pbCalls(f)).toHaveLength(0);
  });
  it('/auth/me loading → no pbv-section, no call to PBV_PATH', async () => {
    userLoading = true;
    const f = stub();
    mount('tab=gajjala&sub=playbook');
    await settled();
    expect(screen.queryByTestId('pbv-section')).toBeNull();
    expect(pbCalls(f)).toHaveLength(0);
  });
  it('the owner on sub=bull_flag → no call to PBV_PATH', async () => {
    userRet = OWNER;
    const f = stub();
    mount('tab=gajjala&sub=bull_flag');
    await waitFor(() => expect(f.mock.calls.length).toBeGreaterThan(0));
    await new Promise((res) => setTimeout(res, 20));
    expect(screen.queryByTestId('pbv-section')).toBeNull();
    expect(pbCalls(f)).toHaveLength(0);
  });
  const lists: [string, Answer][] = [['404', { ok: false, status: 404, body: { detail: 'Not Found' } }], ['empty', { body: PB_EMPTY }]];
  for (const [name, a] of lists) {
    it(`the owner when the list answers ${name} → no pbv-section; the playbook text still renders`, async () => {
      userRet = OWNER;
      const f = stub(a);
      mount('tab=gajjala&sub=playbook');
      await settled();
      await waitFor(() => expect(pbCalls(f)).toHaveLength(1));
      await new Promise((res) => setTimeout(res, 20));
      expect(screen.queryByTestId('pbv-section')).toBeNull();
      expect(screen.getByTestId('gg-playbook').textContent).toContain(NOTE);
      expect(screen.getAllByTestId('gg-pb-section').length).toBeGreaterThan(0);
    });
  }
});
