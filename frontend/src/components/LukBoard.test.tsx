import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import LukBoard from './LukBoard';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { VOYA } from '../lib/__fixtures__/cardLadder.tiles';

/* 🔄 2026-11-11 (lukscan WP-LUK-FE): LukBoard reads useCurrentUser for the owner's scan-now button; the real hook fetches
 * /auth/me and would shift every fetch-count assertion here — no user (the scan glue is pinned in LukBoard.scan.test). */
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: null, loading: false }) }));

/* 🥇 Luk's board (2026-11-01, luk spec §3.10 / §3.13 / WP-E). Ajay: "look at other winners of US stocks champion ship
 * and pic the next best one like Gajjala. Implement their strategy please if they have online resources." … "I need
 * something like Gajjlala that is exposed". The board prints the served payload VERBATIM and composes no word and no
 * number. A real-shaped hand fixture in the §3.10 shape (the backend golden lands with WP-C). NEGATIVES: no b-word, no
 * "edge", no number that is not in the payload, an absent block renders nothing, a listed tile keeps trigger/stop/R. */

const SUBS = [
  { key: 'pullback_reversal', emoji: '↩️', label: 'Pullback reversal', n: 3, title: 'his pullback setup' },
  { key: 'opening_range_high', emoji: '🔔', label: 'Opening range', n: 0, title: null },
  { key: 'inside_day_pdh', emoji: '📦', label: 'Inside day', n: 0, title: null },
  { key: 'premarket', emoji: '☀️', label: 'Premarket', n: 2, title: null },
  { key: 'leader', emoji: '🏆', label: 'Leader', n: 0, title: null },
  { key: 'potent', emoji: '⚡', label: 'Potent', n: 0, title: null },
  { key: 'playbook', emoji: '📓', label: 'Playbook', n: 2, title: null },
  { key: 'track_record', emoji: '🏁', label: 'Track record', n: 1, title: null },
];

const TILE = (symbol: string, state: string, extra: Record<string, unknown> = {}) => ({
  symbol, href: `/sepa/${symbol}`, setup: 'pullback_reversal', state,
  state_label: state === 'aplus' ? 'A+ — every rule met, the trigger bar traded through and closed' : state,
  frame_text: '5-minute candle', trigger_text: 'trigger 12.40', stop_text: 'stop 11.98 (−3.4%) · R $0.42', listed_why: null,
  criteria: [
    { key: 'daily_pullback_9', label: 'pulled back to the daily 9 EMA', ok: true, value: 'low 12.01 ≤ 12.10', need: null },
    { key: 'no_chase', label: 'no chase', ok: true, value: '2.9% above the low of day', need: 'at most 3%' },
    { key: 'stop_width', label: 'stop width', ok: null, value: null, need: 'ADR unknown — the half-ADR cap not judged' },
  ],
  chips: { tier_text: 'Lead — 9 EMA > 21 EMA > 50 EMA', adr_text: '>5% ADR — his preference, not a hard rule',
    cap_text: '$1.2B', small_cap_text: 'small cap (<$5B) — his second list', confluence_text: '2 of his levels touched today: 9 EMA, 50 EMA',
    flush_text: 'flushed 1.8% below the hourly 9 EMA at 09:55', window_text: 'inside his first 60 minutes', screens_text: '☀️ #3 · ⚡ #7' },
  bars5: [], curves5: [], vol_avg5: null, as_of_bar_t5: '2026-11-03T10:05:00-05:00', read_at_text: 'read 10:06 ET',
  gajjala: { setup: 'pullback_reversal', state },
  ...extra,
});

const BASE = {
  tab: 'luk', label: "🥇 Luk's",
  title: "🥇 Luk's — Martin Luk's published pullback / opening-range method, built from his own words · UNMEASURED",
  honesty: '2025 US Investing Championship winner (+969.8%). He sells nothing. Every alert here is recorded in shadow, never sent. Nothing here is measured.',
  variant: { key: 'luk', tab: 'luk', label: "🥇 Luk's", api_base: '/chart-maps/luk', record_from: '2026-11-01', push_mode: 'shadow', tfs: ['1m', '5m', '60m'], primary: '5m' },
  session: { badge: 'regular session', refresh_sec: 300 },
  pass: { as_of_et: '10:06', bars_through_et: '10:05', stale: false, stale_text: null, wall_s: 41.2, status: 'ok',
    text: 'pass 10:06 ET · bars through 10:05 · 31 read of 34 shortlisted · 412 screened · 6 not screened yet' },
  strip: { folded: true,
    market_state: { title: '🧭 Indices', rows: [
      { symbol: 'QQQ', text: 'QQQ: 9 EMA over 21', dist_text: 'QQQ +1.4% vs its 9 EMA' },
      { symbol: 'IWM', text: 'IWM: 9 EMA under 21 — his not-favourable-for-longs read', dist_text: 'IWM −0.6% vs its 9 EMA' }],
      note: 'A state word, never a gate (HIS CALL #8).' },
    push_text: "🥇 Luk's never sends: every alert is recorded in shadow.",
    record_text: '🏁 records every A+ since 2026-11-01.',
    external_text: 'Two external backtests read negative — EXTERNAL, not re-run here.',
    cost_text: 'one snapshot per pass + at most 40 minute fetches',
    latency_text: 'a 1-minute trigger is read on the next 5-minute pass — up to 5 minutes after its bar closed' },
  subs: SUBS,
  counts: { aplus: 1, triggered: 0, forming: 1, listed: 1, stopped: 0, none: 28 },
  counts_text: '1 A+ · 1 forming · 1 listed · 28 nothing to read',
  counts_legend: { aplus: 'A+ — every rule met, the trigger bar traded through and closed', listed: 'listed — a rule says not A+; trigger / stop / R still shown' },
  order_note: 'A+ first, then triggered, forming, listed, stopped',
};

const BOARDS: Record<string, any> = {
  pullback_reversal: { ...BASE, sub: 'pullback_reversal', tiles: [
    TILE('AAA', 'aplus'),
    TILE('BBB', 'forming', { state_label: 'forming — trigger 8.20 armed', trigger_text: 'trigger 8.20', stop_text: null }),
    TILE('CCC', 'listed', { state_label: 'listed — stop too wide by his rule — 6.2% > 5% of the trigger',
      listed_why: 'stop too wide by his rule — 6.2% > 5% of the trigger', trigger_text: 'trigger 20.10',
      stop_text: 'stop 18.85 (−6.2%) · R $1.25 · stop = the 5-minute entry candle low (entry-to-LOD > 5%)' }),
  ] },
  premarket: { ...BASE, sub: 'premarket', tiles: [],
    screens: { key: 'premarket', title: '☀️ Pre-market scan — his settings: cap > $100M · 10-day avg vol > 500K',
      sorted_by_text: 'sorted by pre-market % change', heads: [{ key: 'rank', label: '#' }, { key: 'symbol', label: 'Ticker' }, { key: 'pm_chg_text', label: 'Pre-mkt' }, { key: 'cap_text', label: 'Cap' }],
      rows: [
        { rank: 1, symbol: 'DDD', href: '/sepa/DDD', price_text: '4.10', pm_chg_text: '+22.5%', cap_text: '$410M', criteria: [{ key: 'cap', label: 'cap > $100M', ok: true, value: '$410M', need: null }] },
        { rank: 2, symbol: 'EEE', href: '/sepa/EEE', price_text: '9.80', pm_chg_text: '+11.0%', cap_text: 'cap unknown — not filtered', criteria: [{ key: 'cap', label: 'cap > $100M', ok: null, value: null, need: 'cap unknown — not filtered' }] },
      ],
      not_screened_text: '6 not screened yet — daily facts pending', considerations_text: 'He is considering a $100M dollar-volume floor — listed, not applied: HIS CALL',
      honesty: 'his settings as he showed them' } },
  playbook: { ...BASE, sub: 'playbook', tiles: [],
    playbook: { title: '📓 His Playbook', sections: [
      { key: 'stop', title: 'The stop', items: [
        { text: 'my portfolio risk per trade is around 0.5%', cite_text: 'VKNEJA5r8zw 0:16:09', url: 'https://www.youtube.com/watch?v=VKNEJA5r8zw&t=969', kind: 'his' },
        { text: 'ADR = 20 sessions', cite_text: 'MINE — HIS CALL #10', url: null, kind: 'mine' }] }] } },
  track_record: { ...BASE, sub: 'track_record', tiles: [],
    track_record: { title: '🏁 Track record — every 🥇 A+ recorded here since 2026-11-01 · UNMEASURED', rule_text: 'Exit = the stop or the first daily close below the 9 EMA.',
      honesty: 'Every row is a shadow record — none reached your phone.', counts_text: '1 A+ recorded · 1 filled · 0 stopped · 1 open',
      spans: [{ key: '5d', label: '5 sessions' }, { key: 'all', label: 'all' }], span: '5d',
      days: [{ date: '2026-11-03', label: 'Tue 11-03', rows: [{ id: '2026-11-03|AAA|pullback_reversal|aplus', symbol: 'AAA',
        setup_label: 'Pullback reversal', at_et: '10:06', plan_text: 'trigger 12.40 · stop 11.98 (−3.4%) · R $0.42',
        fill_text: 'filled 12.41 at 10:07', exit_text: 'open · +0.8R after 2 sessions', flags_text: '', rang_text: 'rang RTH' }] }] } },
};

function stub(boardFor: (url: string) => any) {
  const f = vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/chart-maps/luk') && !u.includes('entry-tape')) return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(boardFor(u))) };
    return { ok: true, status: 200, json: async () => ({}) };
  });
  vi.stubGlobal('fetch', f);
  return f;
}
const bySub = (u: string) => {
  const sub = new URL(u, 'http://x').searchParams.get('sub') || 'pullback_reversal';
  return BOARDS[sub] ?? BOARDS.pullback_reversal;
};
async function mount(path = '/chart-maps?tab=luk') {
  const r = render(<MemoryRouter initialEntries={[path]}><LukBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.luk-board[data-state="loaded"]')).not.toBeNull());
  return r;
}

describe('LukBoard — the served payload, verbatim', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('renders title / honesty / pass line / subs / counts verbatim', async () => {
    stub(bySub);
    await mount();
    const b = BOARDS.pullback_reversal;
    expect(screen.getByTestId('luk-title')).toHaveTextContent(b.title);
    expect(screen.getByTestId('luk-honesty')).toHaveTextContent(b.honesty);
    expect(screen.getByTestId('luk-pass')).toHaveTextContent(b.pass.text);
    expect(screen.getByTestId('luk-session-badge')).toHaveTextContent('regular session');
    expect(screen.getByTestId('luk-counts')).toHaveTextContent(b.counts_text);
    for (const s of SUBS) expect(screen.getByTestId(`luk-sub-${s.key}`)).toHaveTextContent(s.label);
    expect(screen.getByTestId('luk-sub-pullback_reversal').getAttribute('aria-current')).toBe('page');
    expect(screen.getByTestId('luk-sub-premarket').getAttribute('aria-current')).toBeNull();
    expect(screen.getByTestId('luk-sub-premarket').getAttribute('href')).toBe('/chart-maps?tab=luk&sub=premarket');
  });

  it('the strip is FOLDED by default and carries the QQQ / IWM rows and the five served lines', async () => {
    stub(bySub);
    await mount();
    const strip = screen.getByTestId('luk-strip') as HTMLDetailsElement;
    expect(strip.open).toBe(false);
    expect(screen.getByTestId('luk-strip-head')).toHaveTextContent('🧭 Indices');
    expect(screen.getByTestId('luk-market-QQQ')).toHaveTextContent('QQQ: 9 EMA over 21');
    expect(screen.getByTestId('luk-market-IWM')).toHaveTextContent('IWM −0.6% vs its 9 EMA');
    for (const k of ['push', 'record', 'external', 'cost', 'latency']) {
      expect(screen.getByTestId(`luk-strip-${k}`)).toHaveTextContent(BASE.strip[`${k}_text` as keyof typeof BASE.strip] as string);
    }
  });

  it('NEGATIVE: a strip served `folded: false` opens; a strip with nothing to say renders nothing', async () => {
    stub((u) => ({ ...bySub(u), strip: { ...BASE.strip, folded: false } }));
    const r = await mount();
    expect((screen.getByTestId('luk-strip') as HTMLDetailsElement).open).toBe(true);
    r.unmount();
    vi.unstubAllGlobals();
    stub((u) => ({ ...bySub(u), strip: { folded: true, market_state: null, push_text: null } }));
    await mount();
    expect(screen.queryByTestId('luk-strip')).toBeNull();
  });

  it('the counts legend is folded under ⓘ with the served definitions', async () => {
    stub(bySub);
    await mount();
    const legend = screen.getByTestId('luk-legend') as HTMLDetailsElement;
    expect(legend.open).toBe(false);
    expect(screen.getByTestId('luk-legend-listed')).toHaveTextContent(BASE.counts_legend.listed);
  });

  it('the setup sub draws one card per served tile in the SERVED order', async () => {
    stub(bySub);
    const { container } = await mount();
    const ids = Array.from(container.querySelectorAll('[data-testid^="luk-tile-"]'))
      .map((e) => e.getAttribute('data-testid')).filter((x) => !x!.includes('link'));
    expect(ids).toEqual(['luk-tile-AAA', 'luk-tile-BBB', 'luk-tile-CCC']);
    expect(screen.getByTestId('luk-state-AAA')).toHaveTextContent(BOARDS.pullback_reversal.tiles[0].state_label);
    expect(screen.getByTestId('luk-crit-AAA-no_chase')).toHaveTextContent('✓ no chase — 2.9% above the low of day (at most 3%)');
    expect(screen.getByTestId('luk-crit-AAA-stop_width')).toHaveTextContent('· stop width (ADR unknown — the half-ADR cap not judged)');
    expect(screen.getByTestId('luk-chip-AAA-flush_text')).toHaveTextContent('flushed 1.8% below the hourly 9 EMA at 09:55');
    expect(screen.getByTestId('luk-order-note')).toHaveTextContent(BASE.order_note);
  });

  it('NEGATIVE: a listed tile still shows trigger / stop / R and its listed_why', async () => {
    stub(bySub);
    await mount();
    const t = BOARDS.pullback_reversal.tiles[2];
    expect(screen.getByTestId('luk-trigger-CCC')).toHaveTextContent(t.trigger_text);
    expect(screen.getByTestId('luk-stop-CCC')).toHaveTextContent('stop 18.85 (−6.2%) · R $1.25');
    expect(screen.getByTestId('luk-why-CCC')).toHaveTextContent(t.listed_why);
    // a forming card with no served stop prints no stop line (never a made-up one)
    expect(screen.queryByTestId('luk-stop-BBB')).toBeNull();
  });

  it('a tile with served bars draws through the real PatternChart', async () => {
    const bars = [
      { t: '2026-11-03T09:35:00', o: 12.0, h: 12.3, l: 11.9, c: 12.2, v: 1000, s: 'rth' },
      { t: '2026-11-03T09:40:00', o: 12.2, h: 12.5, l: 12.1, c: 12.45, v: 1500, s: 'rth' },
    ];
    stub((u) => ({ ...bySub(u), tiles: [TILE('AAA', 'aplus', { bars5: bars,
      curves5: [{ tone: 'ema9', label: '9 EMA', values: [12.1, 12.2] }] })] }));
    const { container } = await mount();
    const tile = screen.getByTestId('luk-tile-AAA');
    expect(tile.querySelector('svg')).not.toBeNull();
    expect(container.querySelector('.pc-vol-pane')).not.toBeNull();
  });

  it('sub switch: each sub renders its own body', async () => {
    stub(bySub);
    let r = await mount('/chart-maps?tab=luk&sub=premarket');
    expect(screen.getByTestId('luk-screen-premarket')).toBeTruthy();
    expect(screen.queryByTestId('luk-grid')).toBeNull();
    r.unmount();
    r = await mount('/chart-maps?tab=luk&sub=playbook');
    expect(screen.getByTestId('luk-playbook')).toBeTruthy();
    expect(screen.queryByTestId('luk-screen-premarket')).toBeNull();
    r.unmount();
    r = await mount('/chart-maps?tab=luk&sub=track_record');
    expect(screen.getByTestId('luk-tr')).toBeTruthy();
    expect(screen.queryByTestId('luk-playbook')).toBeNull();
    r.unmount();
  });

  it('a sub-bar click fetches that sub (the GET carries sub / span / focus only)', async () => {
    const f = stub(bySub);
    await mount('/chart-maps?tab=luk&universe=full');
    fireEvent.click(screen.getByTestId('luk-sub-premarket'));
    await waitFor(() => expect(screen.getByTestId('luk-screen-premarket')).toBeTruthy());
    const urls = f.mock.calls.map((c) => String(c[0])).filter((u) => u.includes('/chart-maps/luk'));
    expect(urls.some((u) => u.endsWith('/chart-maps/luk?sub=premarket'))).toBe(true);
    for (const u of urls) {
      const q = new URL(u, 'http://x').searchParams;
      for (const k of q.keys()) expect(['sub', 'span', 'focus']).toContain(k);
    }
  });

  it('NEGATIVE: an absent block renders nothing (no playbook served on the playbook sub, no screens on a scan sub)', async () => {
    stub((u) => {
      const b = { ...bySub(u) };
      delete b.playbook; delete b.screens; delete b.track_record;
      return b;
    });
    let r = await mount('/chart-maps?tab=luk&sub=playbook');
    expect(screen.queryByTestId('luk-playbook')).toBeNull();
    r.unmount();
    r = await mount('/chart-maps?tab=luk&sub=premarket');
    expect(screen.queryByTestId('luk-screen-premarket')).toBeNull();
    expect(screen.queryByTestId('luk-grid')).toBeNull();
    r.unmount();
    r = await mount('/chart-maps?tab=luk&sub=track_record');
    expect(screen.queryByTestId('luk-tr')).toBeNull();
    r.unmount();
  });

  it('NEGATIVE: no b-word, no "edge", no NaN / undefined / null on any sub', async () => {
    stub(bySub);
    for (const sub of Object.keys(BOARDS)) {
      const { container, unmount } = await mount(`/chart-maps?tab=luk&sub=${sub}`);
      const txt = container.textContent || '';
      expect(txt, sub).not.toMatch(new RegExp('b' + 'ounce', 'i'));
      expect(txt, sub).not.toMatch(/\bedge\b/i);
      expect(txt, sub).not.toMatch(/NaN|undefined|\bnull\b|\bNone\b|\[object Object\]/);
      unmount();
    }
  });

  it('NEGATIVE: every number on screen is in the served payload (the FE composes none)', async () => {
    stub(bySub);
    for (const sub of Object.keys(BOARDS)) {
      const { container, unmount } = await mount(`/chart-maps?tab=luk&sub=${sub}`);
      const served = JSON.stringify(BOARDS[sub]);
      const nums = (container.textContent || '').match(/\d+(?:[.,]\d+)*/g) || [];
      for (const n of nums) expect(served, `${sub}: ${n}`).toContain(n);
      unmount();
    }
  });

  it('re-reads on the SERVED cadence; NEGATIVE: never on a typed cadence when one is served', async () => {
    const si = vi.spyOn(window, 'setInterval');
    stub(bySub);
    await mount();
    await waitFor(() => expect(si.mock.calls.some((c) => c[1] === 300_000)).toBe(true));
    si.mockRestore();
  });

  it('NEGATIVE: a failed GET shows the error glyph, never a blank board', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })));
    const { container } = render(<MemoryRouter initialEntries={['/chart-maps?tab=luk']}><LukBoard /></MemoryRouter>);
    await waitFor(() => expect(container.querySelector('.luk-board[data-state="error"]')).not.toBeNull());
    expect(screen.getByTestId('luk-err')).toBeTruthy();
    expect(screen.queryByTestId('luk-title')).toBeNull();
  });

  it('focus highlights the served name', async () => {
    stub(bySub);
    await mount('/chart-maps?tab=luk&sub=pullback_reversal&focus=BBB');
    expect(screen.getByTestId('luk-tile-BBB').className).toMatch(/luk-focus/);
    expect(screen.getByTestId('luk-tile-AAA').className).not.toMatch(/luk-focus/);
    expect(within(screen.getByTestId('luk-tile-BBB')).getByTestId('luk-state-BBB')).toHaveTextContent('forming — trigger 8.20 armed');
  });
});

/* 2026-11-01 — the house chips reach 🥇 Luk's (Ajay 2026-09-11 "ALL TABS IN CHART MAPS"; 2026-10-03 "add this field to
 * all our chart maps scan"): LukBoard mounts 🚀 / 🩳 / 🧨 / 🎯 per card off ONE bounce-room POST; LukCard places them
 * and PatternChart skips its own copies. NEGATIVES: no POST on a sub without cards, no chip twice on a charted card, no
 * chip without a served read. */
describe('LukBoard — the house chips (🚀 🩳 🧨 🎯)', () => {
  const EXPLOSIVE = { score: null, grade: null, intact: true, session_low: true, components: [],
    room: { state: 'ROOM', room_pct: 30, atr_days: 3, band: null, at_highs: false }, measured: { status: 'no_signal', mdl: 5.1 } };
  beforeEach(() => { _resetGrowthTagsCache(); _resetBounceRoomCache(); _resetShortInterestCache(); });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); _resetGrowthTagsCache(); _resetBounceRoomCache(); _resetShortInterestCache(); });

  function houseStub(boardFor: (url: string) => any) {
    const f = vi.fn(async (url: string, _init?: any) => {
      const u = String(url);
      if (u.includes('/chart-maps/luk') && !u.includes('entry-tape')) return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(boardFor(u))) };
      if (u.includes('/growth/tags')) return { ok: true, status: 200, json: async () => ({ tags: { AAA: { sales: 120, eps: 50 } } }) };
      if (u.includes('/short-interest/map')) return { ok: true, status: 200, json: async () => ({ items: { AAA: { chip: '🩳 SI 14%', title: 'FINRA 2026-10-15', status: 'fresh', rows: [] } } }) };
      if (u.includes('/supply-demand/bounce-room')) return { ok: true, status: 200, json: async () => ({ rows: { AAA: { explosive: EXPLOSIVE } }, pending: 0 }) };
      return { ok: true, status: 200, json: async () => ({}) };
    });
    vi.stubGlobal('fetch', f);
    return f;
  }
  const roomPosts = (f: any) => f.mock.calls.filter((c: any[]) => String(c[0]).includes('/supply-demand/bounce-room'));

  it('a card sub: ONE bounce-room POST for the cards on screen, and each served chip on its card', async () => {
    const f = houseStub(bySub);
    await mount();
    await waitFor(() => expect(roomPosts(f)).toHaveLength(1));
    expect(JSON.parse(roomPosts(f)[0][1].body).symbols).toEqual(['AAA', 'BBB', 'CCC']);
    const aaa = screen.getByTestId('luk-house-chips-AAA');
    await waitFor(() => expect(aaa.textContent).toContain('🚀 +120%'));
    await waitFor(() => expect(aaa.textContent).toContain('🩳 SI 14%'));
    await waitFor(() => expect(aaa.querySelector('.cm-badge-explosive')).not.toBeNull());
    // NEGATIVE: a name with no served read shows no chip (never a zero, never a guess).
    const bbb = screen.getByTestId('luk-house-chips-BBB');
    expect(bbb.textContent).not.toContain('🚀');
    expect(bbb.textContent).not.toContain('🩳');
    expect(bbb.querySelector('.cm-badge-explosive')).toBeNull();
    // NEGATIVE: the house chips never land in the served-chips row (that row is the served luk chips only).
    expect(within(screen.getByTestId('luk-chips-AAA')).queryByText(/🚀|🩳/)).toBeNull();
  });

  it('NEGATIVE: 📓 / 🏁 / a scan table draw no cards, so no bounce-room POST', async () => {
    const f = houseStub(bySub);
    for (const sub of ['playbook', 'track_record', 'premarket']) {
      const { unmount } = await mount(`/chart-maps?tab=luk&sub=${sub}`);
      unmount();
    }
    expect(roomPosts(f)).toHaveLength(0);
  });

  it('NEGATIVE: a charted card shows each house chip ONCE (PatternChart skips its own copies)', async () => {
    const charted = { ...BOARDS.pullback_reversal, tiles: [TILE('AAA', 'aplus', { bars5: VOYA.bars })] };
    houseStub(() => charted);
    const { container } = await mount();
    const card = screen.getByTestId('luk-tile-AAA');
    await waitFor(() => expect(card.textContent).toContain('🚀 +120%'));
    await waitFor(() => expect(card.textContent).toContain('🩳 SI 14%'));
    await waitFor(() => expect(card.querySelectorAll('.cm-badge-explosive')).toHaveLength(1));
    expect(container.querySelector('svg')).not.toBeNull();
    expect((card.textContent || '').split('🚀 +120%').length - 1).toBe(1);
    expect((card.textContent || '').split('🩳 SI 14%').length - 1).toBe(1);
  });
});
