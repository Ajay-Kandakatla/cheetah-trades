import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from '../lib/__fixtures__/longTerm.payload.json';

/* 🔔 The zone block in the 📅 tab's 🧭 section (2026-11-12, pkzone spec §3.7 / §3.9, WP-FE-TAB). Ajay 2026-11-12: "add an
 * alert list when stocks reach Pankaj's zones and also tell me if you finish the long term tabs in general".
 *
 * The board prints `zones.alert` as served — names in one of Pankaj's zones now, the reason / stale / push lines and the
 * session's reach log with each row's served push line — and falls back to the closed-bar at_zone strip when `alert` is
 * absent (never both). Four variants: live (the fixture), close, stale, absent. NEGATIVES throughout.
 * The four house chips are mocked inert (their own wording is outside this tab's word rule, spec C8). */

vi.mock('./GrowthChip', () => ({ GrowthChip: () => null }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => null }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => null }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => null }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import LongTermBoard from './LongTermBoard';
import { LT_PATH } from '../lib/longTerm';

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
const NOT_A_SIGNAL = /None of these lists is a buy signal\.?/g;
const BANNED = /\b(buy|buying|bought|sell|selling|sold|entry|entries|exit|exits)\b/i;
const SECTIONS = ['header', 'digest', 'zones', 'started_moving', 'changed',
  'category', 'category', 'category', 'category', 'forward', 'history', 'rules'];

const LIVE = fixture.zones.alert;

/** Off-hours: the latest closed bar, labelled as such (texts as words.py serves them for basis "close"). */
function closeVariant(): any {
  const p = clone(fixture) as any;
  p.zones.alert = {
    ...p.zones.alert,
    live: false,
    as_of_text: 'At the 11-13 close — no live read now',
    now: [
      { symbol: 'TSM', his_symbol: 'TSM', zone: 'Agg', text: "in Pankaj's Agg zone (400–410) at the 11-13 close (405.80) · Tier A" },
      { symbol: 'NVDA', his_symbol: 'NVDA', zone: 'C2', text: "in Pankaj's C2 zone (160–170) at the 11-13 close (164.30) · Tier A" },
    ],
    reason: null,
    stale_text: null,
    log: [],
    log_empty_text: "No name reached one of Pankaj's zones on 11-13.",
  };
  return p;
}

/** A live pass where 3 names have no close from the previous session (they cannot ring) and no snapshot came back. */
function staleVariant(): any {
  const p = clone(fixture) as any;
  p.zones.alert.stale_text = '3 of 40 names have no cached close from 11-11 — they cannot ring this session.';
  p.zones.alert.reason = 'No live prices at the 10:35 ET pass — nothing could ring.';
  return p;
}

function absentVariant(): any {
  const p = clone(fixture) as any;
  delete p.zones.alert;
  return p;
}

async function mount(body: unknown) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => (
    String(url).includes(LT_PATH)
      ? { ok: true, status: 200, json: async () => clone(body) }
      : { ok: true, status: 200, json: async () => ({}) })));
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=long_term']}><LongTermBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.lt-board:not([data-state="loading"])')).not.toBeNull());
  return r;
}

afterEach(() => { vi.unstubAllGlobals(); });

describe('🔔 live — every node is the served text', () => {
  it('title, data-live, as-of line, push line', async () => {
    await mount(fixture);
    const a = screen.getByTestId('lt-zone-alert');
    expect(a.getAttribute('data-live')).toBe('true');
    expect(within(a).getByRole('heading', { level: 3 })).toHaveTextContent(LIVE.title);
    expect(screen.getByTestId('lt-zone-alert-asof')).toHaveTextContent(LIVE.as_of_text);
    expect(screen.getByTestId('lt-zone-alert-push')).toHaveTextContent(LIVE.push_text);
  });
  it('each name in a zone now: a ticker link (his symbol as title) + its served text, in served order', async () => {
    const { container } = await mount(fixture);
    for (const z of LIVE.now) {
      const row = screen.getByTestId(`lt-zone-now-${z.symbol}`);
      const link = row.querySelector('a')!;
      expect(link).not.toBeNull();
      expect(link).toHaveTextContent(z.symbol);
      expect(link.getAttribute('href')).toContain(`/sepa/${z.symbol}`);
      expect(link.getAttribute('title')).toBe(z.his_symbol);
      expect(row).toHaveTextContent(z.text);
    }
    const order = [...container.querySelectorAll('[data-testid^="lt-zone-now-"]')].map((n) => n.getAttribute('data-testid'));
    expect(order).toEqual(LIVE.now.map((z) => `lt-zone-now-${z.symbol}`));
  });
  it('the log: served title, one row per served reach — at_text first, ticker, text, then THAT row\'s served push text', async () => {
    const { container } = await mount(fixture);
    expect(screen.getByTestId('lt-zone-log-title')).toHaveTextContent(LIVE.log_title);
    const rows = [...container.querySelectorAll('[data-testid^="lt-zone-log-"]')]
      .filter((n) => !['lt-zone-log-title', 'lt-zone-log', 'lt-zone-log-empty'].includes(n.getAttribute('data-testid')!));
    expect(rows.map((n) => n.getAttribute('data-testid'))).toEqual(LIVE.log.map((r) => `lt-zone-log-${r.symbol}-${r.zone}`));
    for (const r of LIVE.log) {
      const row = screen.getByTestId(`lt-zone-log-${r.symbol}-${r.zone}`);
      const t = row.textContent || '';
      expect(t.startsWith(r.at_text)).toBe(true);
      expect(t.endsWith(r.push_text)).toBe(true);
      expect(t).toContain(r.text);
      expect(within(row).getByText(r.symbol).closest('a')).not.toBeNull();
    }
    /* the three served outcomes, each on its own row (never a shared or typed outcome) */
    expect(screen.getByTestId('lt-zone-log-TSM-Agg')).toHaveTextContent('rang your phone');
    expect(screen.getByTestId('lt-zone-log-NVDA-C2')).toHaveTextContent('no phone has this alert on');
    expect(screen.getByTestId('lt-zone-log-ANET-Agg')).toHaveTextContent('not sent — phone push is off');
    expect(screen.getByTestId('lt-zone-log-TSM-Agg')).not.toHaveTextContent('no phone has this alert on');
  });
  it('NEGATIVE: reason and stale_text served null → no node; lists non-empty → no empty-text node', async () => {
    await mount(fixture);
    expect(screen.queryByTestId('lt-zone-alert-reason')).toBeNull();
    expect(screen.queryByTestId('lt-zone-alert-stale')).toBeNull();
    expect(screen.queryByTestId('lt-zone-now-empty')).toBeNull();
    expect(screen.queryByTestId('lt-zone-log-empty')).toBeNull();
  });
  it('the served rows_note still follows the block', async () => {
    await mount(fixture);
    const z = screen.getByTestId('lt-zones');
    expect(z).toHaveTextContent(fixture.zones.rows_note);
    expect(z.lastElementChild).toHaveTextContent(fixture.zones.rows_note);
  });
});

describe('🔔 present vs absent — the at_zone fallback, never both', () => {
  it('present → the at_zone strip (its heading and list) does NOT render; each name is listed once', async () => {
    const { container } = await mount(fixture);
    for (const hit of fixture.zones.at_zone) expect(screen.queryByTestId(`lt-zone-${hit.symbol}`)).toBeNull();
    expect(container.textContent).not.toContain(fixture.zones.as_of_text);
    for (const z of LIVE.now) expect(container.querySelectorAll(`[data-testid="lt-zone-now-${z.symbol}"]`)).toHaveLength(1);
  });
  it('absent → the old at_zone strip renders as before; NEGATIVE: no 🔔 node', async () => {
    await mount(absentVariant());
    expect(screen.queryByTestId('lt-zone-alert')).toBeNull();
    expect(screen.getByTestId('lt-zones')).toHaveTextContent(fixture.zones.as_of_text);
    for (const hit of fixture.zones.at_zone) expect(screen.getByTestId(`lt-zone-${hit.symbol}`)).toHaveTextContent(hit.zone_text);
    expect(screen.queryByTestId('lt-zone-now-TSM')).toBeNull();
  });
  it('NEGATIVE: alert served null (or not an object) → the old strip, no 🔔 node', async () => {
    for (const v of [null, 'x']) {
      const p = clone(fixture) as any;
      p.zones.alert = v;
      const { unmount } = await mount(p);
      expect(screen.queryByTestId('lt-zone-alert')).toBeNull();
      expect(screen.getByTestId('lt-zone-TSM')).toBeTruthy();
      unmount();
      vi.unstubAllGlobals();
    }
  });
  it('an alert with an empty at_zone / no zones heading still renders its section', async () => {
    const p = clone(fixture) as any;
    p.zones.at_zone = [];
    p.zones.as_of_text = null;
    p.zones.rows_note = null;
    await mount(p);
    expect(screen.getByTestId('lt-zones')).toBeTruthy();
    expect(screen.getByTestId('lt-zone-alert')).toBeTruthy();
  });
  it('section order is unchanged in every variant (live / close / stale / absent)', async () => {
    for (const body of [fixture, closeVariant(), staleVariant(), absentVariant()]) {
      const { container, unmount } = await mount(body);
      expect([...container.querySelectorAll('[data-section]')].map((n) => n.getAttribute('data-section'))).toEqual(SECTIONS);
      expect(screen.getByTestId('lt-zones').querySelectorAll('[data-section]')).toHaveLength(0);
      unmount();
      vi.unstubAllGlobals();
    }
  });
});

describe('🔔 close and stale variants', () => {
  it('close: data-live false, the served close as-of line and close texts; NEGATIVE: no reason / stale node', async () => {
    const p = closeVariant();
    await mount(p);
    expect(screen.getByTestId('lt-zone-alert').getAttribute('data-live')).toBe('false');
    expect(screen.getByTestId('lt-zone-alert-asof')).toHaveTextContent(p.zones.alert.as_of_text);
    for (const z of p.zones.alert.now) expect(screen.getByTestId(`lt-zone-now-${z.symbol}`)).toHaveTextContent(z.text);
    expect(screen.queryByTestId('lt-zone-alert-reason')).toBeNull();
    expect(screen.queryByTestId('lt-zone-alert-stale')).toBeNull();
  });
  it('log [] → the served log_empty_text; NEGATIVE: no log list and no log row', async () => {
    const p = closeVariant();
    const { container } = await mount(p);
    expect(screen.getByTestId('lt-zone-log-empty')).toHaveTextContent(p.zones.alert.log_empty_text);
    expect(screen.queryByTestId('lt-zone-log')).toBeNull();
    expect(container.querySelector('[data-testid^="lt-zone-log-TSM"]')).toBeNull();
  });
  it('now [] → the served empty_text; NEGATIVE: no now row', async () => {
    const p = clone(fixture) as any;
    p.zones.alert.now = [];
    p.zones.alert.empty_text = "No name is inside one of Pankaj's zones now.";
    const { container } = await mount(p);
    expect(screen.getByTestId('lt-zone-now-empty')).toHaveTextContent(p.zones.alert.empty_text);
    expect(container.querySelector('[data-testid^="lt-zone-now-"]:not([data-testid="lt-zone-now-empty"])')).toBeNull();
  });
  it('NEGATIVE: empty lists with null empty texts print nothing typed (no node, no list)', async () => {
    const p = clone(fixture) as any;
    Object.assign(p.zones.alert, { now: [], empty_text: null, log: [], log_empty_text: null });
    await mount(p);
    expect(screen.queryByTestId('lt-zone-now-empty')).toBeNull();
    expect(screen.queryByTestId('lt-zone-log-empty')).toBeNull();
    expect(screen.getByTestId('lt-zone-alert').querySelector('ul, li')).toBeNull();
  });
  it('stale: the served stale_text and reason render, each in its own node', async () => {
    const p = staleVariant();
    await mount(p);
    expect(screen.getByTestId('lt-zone-alert-stale')).toHaveTextContent(p.zones.alert.stale_text);
    expect(screen.getByTestId('lt-zone-alert-reason')).toHaveTextContent(p.zones.alert.reason);
    expect(screen.getByTestId('lt-zone-alert-stale')).not.toHaveTextContent(p.zones.alert.reason);
  });
});

describe('🔔 words and numbers — served only', () => {
  it('NEGATIVE: no "NaN" / "undefined" / "null" / "Infinity" in the DOM in any variant, nor with null row texts', async () => {
    const nulls = clone(fixture) as any;
    nulls.zones.alert.now[0].text = null;
    nulls.zones.alert.log[0].at_text = null;
    nulls.zones.alert.log[0].push_text = null;
    nulls.zones.alert.log[1].text = null;
    nulls.zones.alert.as_of_text = null;
    for (const body of [fixture, closeVariant(), staleVariant(), absentVariant(), nulls]) {
      const { container, unmount } = await mount(body);
      expect(container.textContent).not.toMatch(/NaN|Infinity|undefined|\bnull\b/);
      unmount();
      vi.unstubAllGlobals();
    }
  });
  it('a null row text prints "—"; NEGATIVE: a null as_of_text renders no as-of node', async () => {
    const p = clone(fixture) as any;
    p.zones.alert.now[0].text = null;
    p.zones.alert.as_of_text = null;
    await mount(p);
    expect(screen.getByTestId(`lt-zone-now-${p.zones.alert.now[0].symbol}`)).toHaveTextContent('—');
    expect(screen.queryByTestId('lt-zone-alert-asof')).toBeNull();
  });
  it('NEGATIVE: rendered text minus the one allowed sentence passes the buy/sell/entry/exit regex in every variant', async () => {
    for (const body of [fixture, closeVariant(), staleVariant()]) {
      const { container, unmount } = await mount(body);
      const t = (container.textContent || '').replace(NOT_A_SIGNAL, '');
      expect(t).not.toMatch(BANNED);
      expect(screen.getByTestId('lt-zone-alert').textContent).not.toMatch(BANNED);
      unmount();
      vi.unstubAllGlobals();
    }
  });
  it('NEGATIVE: the matcher is live — a served "Buy CL1" would be caught', () => {
    expect('Buy CL1'.replace(NOT_A_SIGNAL, '')).toMatch(BANNED);
    expect("reached Pankaj's Agg zone".replace(NOT_A_SIGNAL, '')).not.toMatch(BANNED);
  });
  it('the board types no digit of its own in this block (every served string swapped for a digit-free one)', async () => {
    const p = clone(fixture) as any;
    const a = p.zones.alert;
    for (const k of ['title', 'as_of_text', 'push_text', 'log_title']) a[k] = `served ${k}`;
    a.reason = 'served reason';
    a.stale_text = 'served stale';
    a.now = a.now.map((z: any) => ({ ...z, text: 'served now text' }));
    a.log = a.log.map((r: any) => ({ ...r, at_text: 'served at', text: 'served log text', push_text: 'served push' }));
    await mount(p);
    const block = screen.getByTestId('lt-zone-alert');
    expect(block.textContent).toContain('served reason');
    expect(block.textContent).not.toMatch(/\d/);
  });
  it('the fixture carries ONLY the spec §3.7 keys under zones.alert', () => {
    expect(Object.keys(LIVE).sort()).toEqual(['as_of_text', 'empty_text', 'live', 'log', 'log_empty_text', 'log_title',
      'now', 'push_text', 'reason', 'stale_text', 'title']);
    for (const z of LIVE.now) expect(Object.keys(z).sort()).toEqual(['his_symbol', 'symbol', 'text', 'zone']);
    for (const r of LIVE.log) expect(Object.keys(r).sort()).toEqual(['at_text', 'his_symbol', 'push_text', 'symbol', 'text', 'zone']);
  });
  it('the fixture digest says the live served pushed_text (it rings this week)', () => {
    expect(fixture.digest.pushed_text).toBe("This week's digest rang — one push to your phone when allowed.");
  });
});
