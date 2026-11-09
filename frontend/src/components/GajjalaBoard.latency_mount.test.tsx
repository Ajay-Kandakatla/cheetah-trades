import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import trGolden from './__fixtures__/gajjala_track_record_golden_2026_10_16.json';
import type { CurrentUser } from '../hooks/useUser';

/* ⏱ the latency ledger's mount on the 🏁 Track record (2026-11-09, gg_live spec §3.6 / §4 Z).
 *
 * Ajay 2026-11-09: "I would like the autopilot to be continously monitored or live tracked … where there is a low latency
 * monitoring on the prices action changes please?". GajjalaLatency (WP-E) is mounted ONCE, under the A+ charts, on the
 * 🏁 view, with the SERVED span key (`track_record.span`). Pinned: an owner sees the ⏱ block right after the A+ charts
 * and its GET carries the served span. NEGATIVES: a non-owner fetches nothing and sees nothing; a non-🏁 sub never
 * mounts it; the board's 🏁 still renders when the latency read fails. */

let userRet: CurrentUser | null = null;
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({ PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> }));
vi.mock('./GajjalaAplusCharts', () => ({ default: () => <div data-testid="ap-charts-mock" /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const OWNER: CurrentUser = {
  email: 'owner@example.com', display_name: 'Owner', given_name: 'Owner', picture: null,
  is_default_user: false, is_admin: true,
};
const clone = (x: any) => JSON.parse(JSON.stringify(x));
const BOARD: any = (trGolden as any).boards['5d'];
const LAT = {
  title: '⏱ Speed — seconds after the 5-minute bar closed', span: '5d', n_alerts: 0,
  columns: [{ key: 'read', label: 'Read' }], summary: [], ci: [], footnote: 'served footnote', empty_text: 'served empty line',
};

type Call = { method: string; path: string; span: string | null };
let calls: Call[] = [];
function stub(opts: { latencyOk?: boolean; board?: any } = {}) {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    const method = String(init?.method || 'GET').toUpperCase();
    calls.push({ method, path: u.pathname, span: u.searchParams.get('span') });
    if (u.pathname.endsWith('/trading/gajjala/latency')) {
      if (opts.latencyOk === false) return { ok: false, status: 500, json: async () => ({}) };
      return { ok: true, status: 200, json: async () => clone(LAT) };
    }
    if (u.pathname.endsWith('/scan')) return { ok: true, status: 200, json: async () => ({ state: 'closed', text: 'served closed line' }) };
    return { ok: true, status: 200, json: async () => clone(opts.board ?? BOARD) };
  }));
}
const mount = (q: string) => render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /></MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
const latencyGets = () => calls.filter((c) => c.path.endsWith('/trading/gajjala/latency'));

beforeEach(() => { userRet = null; calls = []; });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('GajjalaBoard — ⏱ latency ledger mounted under the A+ charts on the 🏁', () => {
  it('the golden serves a 🏁 with an A+ block and a span (the mount reads tr.span)', () => {
    expect(BOARD?.track_record?.aplus).toBeTruthy();
    expect(typeof BOARD?.track_record?.span).toBe('string');
  });

  it('owner: ONE ⏱ block inside the 🏁 panel, right after the A+ charts, its GET carries the served span', async () => {
    userRet = OWNER;
    stub();
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    await waitFor(() => expect(screen.getByTestId('gg-latency')).toBeTruthy());
    const panel = screen.getByTestId('gg-track-record');
    const block = screen.getByTestId('gg-latency');
    expect(panel.contains(block)).toBe(true);
    expect(container.querySelectorAll('[data-testid="gg-latency"]')).toHaveLength(1);
    const charts = screen.getByTestId('ap-charts-mock');
    expect(charts.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(charts.nextElementSibling).toBe(block);
    expect(latencyGets().length).toBeGreaterThan(0);
    for (const c of latencyGets()) {
      expect(c.method).toBe('GET');
      expect(c.span).toBe(BOARD.track_record.span);
    }
    expect(block.textContent).toContain('served footnote');
  });

  it('NEGATIVE: a non-owner fetches no latency and sees no ⏱ block', async () => {
    stub();
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    expect(screen.getByTestId('gg-track-record')).toBeTruthy();
    expect(screen.queryByTestId('gg-latency')).toBeNull();
    expect(latencyGets()).toHaveLength(0);
  });

  it('NEGATIVE: a non-🏁 sub never mounts it (owner)', async () => {
    userRet = OWNER;
    const flag = { ...clone(BOARD), sub: 'bull_flag', tiles: [], track_record: null };
    stub({ board: flag });
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    expect(screen.queryByTestId('gg-latency')).toBeNull();
    expect(latencyGets()).toHaveLength(0);
  });

  it('NEGATIVE: a failed latency read renders no ⏱ block and the 🏁 still renders', async () => {
    userRet = OWNER;
    stub({ latencyOk: false });
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    await waitFor(() => expect(latencyGets().length).toBeGreaterThan(0));
    expect(screen.getByTestId('gg-track-record')).toBeTruthy();
    expect(screen.queryByTestId('gg-latency')).toBeNull();
  });
});
