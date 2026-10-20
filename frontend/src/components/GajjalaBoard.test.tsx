import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation, useNavigationType } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import { staleAfterSec } from '../pages/Alerts';

/* 🚩 Gajjala's board (2026-10-13). The board draws what the server ordered and
 * said; these pin that it never composes a rule, never invents a sub, never
 * re-orders, never polls a closed session, and that a push deep link lands on
 * the sub the server resolved. */

const trackFeature = vi.fn();
vi.mock('../lib/usageTracker', () => ({ trackFeature: (k: string) => trackFeature(k) }));

const chartProps: any[] = [];
vi.mock('./PatternChart', () => ({
  PatternChart: (props: any) => {
    chartProps.push(props);
    const { tile } = props;
    return (
      <div data-testid={`chart-${tile.symbol}`}>
        {(tile.curves || []).map((c: any) => <span key={c.tone} data-testid={`curve-${tile.symbol}`}>{c.tone}</span>)}
        {(tile.lines || []).map((l: any) => <span key={l.label} data-testid={`line-${tile.symbol}`}>{l.tone}</span>)}
      </div>
    );
  },
}));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: ({ symbol }: any) => <span data-testid={`short-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
const roomSyms: string[][] = [];
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: (s: readonly string[]) => {
    roomSyms.push([...s]);
    return { map: new Map(), payload: null, loading: false, error: null, pending: 0 };
  },
}));

import GajjalaBoard from './GajjalaBoard';

const BOARDS: Record<string, any> = (fixture as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

function stubFetch(pick: (url: URL) => any) {
  const spy = vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    return { ok: true, status: 200, json: async () => pick(u) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const bySub = (u: URL) => clone(BOARDS[u.searchParams.get('sub') || 'bull_flag'] || BOARDS.bull_flag);

let loc: { search: string; type: string } = { search: '', type: '' };
function Probe() {
  const l = useLocation();
  const t = useNavigationType();
  loc = { search: l.search, type: t };
  return null;
}
const mount = (q = 'tab=gajjala') => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /><Probe /></MemoryRouter>);
const gajjalaUrls = (spy: any) => spy.mock.calls.map((c: any[]) => String(c[0])).filter((u: string) => u.includes('/chart-maps/gajjala'));

describe('GajjalaBoard', () => {
  beforeEach(() => { chartProps.length = 0; roomSyms.length = 0; trackFeature.mockClear(); });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('renders the 8 sub buttons with the SERVED labels and counts', async () => {
    stubFetch(bySub);
    mount();
    await screen.findByTestId('gg-tile-PFAI');
    const btns = screen.getAllByRole('tab').filter((b) => b.getAttribute('data-testid')?.startsWith('gg-sub-'));
    expect(btns).toHaveLength(8);
    expect(btns.map((b) => b.textContent)).toEqual(BOARDS.bull_flag.subs.map((s: any) => `${s.emoji} ${s.label} · ${s.count}`));
    expect(screen.getByTestId('gg-sub-bull_flag')).toHaveAttribute('aria-selected', 'true');
  });

  it('a sub click sets `sub`, keeps tab=gajjala, and tracks chart-maps:tab:gajjala:<sub>', async () => {
    const spy = stubFetch(bySub);
    mount('tab=gajjala&sub=bull_flag');
    await screen.findByTestId('gg-tile-PFAI');
    expect(trackFeature).toHaveBeenCalledWith('chart-maps:tab:gajjala:bull_flag');
    fireEvent.click(screen.getByTestId('gg-sub-intraday_vcp'));
    await screen.findByTestId('gg-tile-AIXI');
    const q = new URLSearchParams(loc.search);
    expect(q.get('tab')).toBe('gajjala');
    expect(q.get('sub')).toBe('intraday_vcp');
    expect(gajjalaUrls(spy).some((u: string) => u.includes('sub=intraday_vcp'))).toBe(true);
    expect(trackFeature).toHaveBeenCalledWith('chart-maps:tab:gajjala:intraday_vcp');
  });

  it('NEGATIVE: an unknown `sub` asks for bull_flag and the URL adopts it', async () => {
    const spy = stubFetch(bySub);
    mount('tab=gajjala&sub=nonsense');
    await screen.findByTestId('gg-tile-PFAI');
    expect(gajjalaUrls(spy)[0]).toContain('sub=bull_flag');
    expect(gajjalaUrls(spy)[0]).not.toContain('nonsense');
    await waitFor(() => expect(new URLSearchParams(loc.search).get('sub')).toBe('bull_flag'));
  });

  it('a `focus` deep link with no `sub` sends NO sub and adopts the served sub with history replace (one fetch)', async () => {
    const spy = stubFetch(() => ({ ...clone(BOARDS.reversal_squeeze), sub_resolved_from: 'focus_alert' }));
    mount('tab=gajjala&focus=FCHL');
    await screen.findByTestId('gg-tile-FCHL');
    const first = new URL(gajjalaUrls(spy)[0], 'http://x');
    expect(first.searchParams.has('sub')).toBe(false);
    expect(first.searchParams.get('focus')).toBe('FCHL');
    await waitFor(() => expect(new URLSearchParams(loc.search).get('sub')).toBe('reversal_squeeze'));
    expect(loc.type).toBe('REPLACE');
    expect(new URLSearchParams(loc.search).get('focus')).toBe('FCHL');
    expect(gajjalaUrls(spy)).toHaveLength(1);
    // `focus` outlines that tile.
    expect(screen.getByTestId('gg-tile-FCHL').className).toContain('gg-focus');
  });

  it('`focus` scrolls the tile into view', async () => {
    const scroll = vi.fn();
    (HTMLElement.prototype as any).scrollIntoView = scroll;
    stubFetch(bySub);
    mount('tab=gajjala&sub=bull_flag&focus=TCRT');
    await screen.findByTestId('gg-tile-TCRT');
    await waitFor(() => expect(scroll).toHaveBeenCalled());
    expect(screen.getByTestId('gg-tile-TCRT').className).toContain('gg-focus');
    expect(screen.getByTestId('gg-tile-PFAI').className).not.toContain('gg-focus');
    delete (HTMLElement.prototype as any).scrollIntoView;
  });

  // Review 2026-10-13: `focus` stays in the URL and every 300 s refresh hands
  // a NEW tiles array — keyed on tiles alone, the page jumped back to the
  // focused tile on every refresh (4 fetches → 4 scrolls).
  // Captures the board's own SERVED-cadence timer only; every other interval
  // (waitFor polls on one) runs for real.
  const captureInterval = () => {
    const ticks: Array<() => void> = [];
    const real = window.setInterval.bind(window);
    vi.spyOn(window, 'setInterval').mockImplementation(((fn: () => void, ms?: number, ...a: any[]) => {
      if (ms === 300_000) { ticks.push(fn); return -1 as any; }
      return real(fn, ms, ...a);
    }) as any);
    return ticks;
  };

  it('NEGATIVE: `focus` scrolls ONCE — served refreshes do not jump the page back', async () => {
    const scroll = vi.fn();
    (HTMLElement.prototype as any).scrollIntoView = scroll;
    const ticks = captureInterval();
    const spy = stubFetch(bySub);
    mount('tab=gajjala&sub=bull_flag&focus=TCRT');
    await screen.findByTestId('gg-tile-TCRT');
    await waitFor(() => expect(scroll).toHaveBeenCalledTimes(1));
    for (let i = 2; i <= 4; i += 1) {
      act(() => { ticks[ticks.length - 1](); });
      await waitFor(() => expect(gajjalaUrls(spy)).toHaveLength(i));
      await screen.findByTestId('gg-tile-TCRT');
    }
    expect(scroll).toHaveBeenCalledTimes(1);
    // the outline stays on the focused tile
    expect(screen.getByTestId('gg-tile-TCRT').className).toContain('gg-focus');
    delete (HTMLElement.prototype as any).scrollIntoView;
  });

  it('NEGATIVE: a `focus` whose tile is not on the board does not scroll — it scrolls once when a refresh brings it in', async () => {
    const scroll = vi.fn();
    (HTMLElement.prototype as any).scrollIntoView = scroll;
    const ticks = captureInterval();
    let n = 0;
    stubFetch(() => {
      n += 1;
      const b = clone(BOARDS.bull_flag);
      if (n === 1) b.tiles = b.tiles.filter((t: any) => t.symbol !== 'TCRT');
      return b;
    });
    mount('tab=gajjala&sub=bull_flag&focus=TCRT');
    await screen.findByTestId('gg-tile-PFAI');
    expect(screen.queryByTestId('gg-tile-TCRT')).toBeNull();
    expect(scroll).not.toHaveBeenCalled();
    act(() => { ticks[ticks.length - 1](); });
    await screen.findByTestId('gg-tile-TCRT');
    await waitFor(() => expect(scroll).toHaveBeenCalledTimes(1));
    act(() => { ticks[ticks.length - 1](); });
    await waitFor(() => expect(n).toBe(3));
    expect(scroll).toHaveBeenCalledTimes(1);
    delete (HTMLElement.prototype as any).scrollIntoView;
  });

  it('strip / ⏳ first15 / stale / warming / awaiting / push lines are the SERVED strings', async () => {
    const b = clone(BOARDS.bull_flag);
    b.session.first15 = true;
    b.pass = { ...b.pass, stale: true, stale_text: 'stale — last pass 10:05 ET (over 900 s)', warming: true, warming_text: 'no pass yet this session' };
    b.awaiting = [{ setup: 'reversal_squeeze', his_call: 'H1', text: "\u{1F3BE} waiting for your number (H1)" }];
    stubFetch(() => b);
    mount();
    expect(await screen.findByTestId('gg-strip-text')).toHaveTextContent(b.strip.text);
    expect(screen.getByTestId('gg-session-badge')).toHaveTextContent('RTH');
    expect(screen.getByTestId('gg-as-of')).toHaveTextContent('10:31 ET');
    expect(screen.getByTestId('gg-first15')).toHaveTextContent(b.session.first15_text);
    expect(screen.getByTestId('gg-stale')).toHaveTextContent(b.pass.stale_text);
    expect(screen.getByTestId('gg-warming')).toHaveTextContent('no pass yet this session');
    expect(screen.getByTestId('gg-awaiting')).toHaveTextContent('waiting for your number (H1)');
    expect(screen.getByTestId('gg-push')).toHaveTextContent(/SHADOW/);
    expect(screen.getByTestId('gg-graveyard')).toHaveTextContent('OLDX');
    expect(screen.getByTestId('gg-note')).toHaveTextContent('UNMEASURED');
    expect(screen.getByTestId('rules-info')).toHaveTextContent('gajjala');
  });

  it('NEGATIVE: not stale, not warming, not first15 → none of those lines', async () => {
    stubFetch(bySub);
    mount();
    await screen.findByTestId('gg-tile-PFAI');
    for (const id of ['gg-stale', 'gg-warming', 'gg-first15', 'gg-awaiting']) expect(screen.queryByTestId(id)).toBeNull();
  });

  it('tiles mount PatternChart with the 9 + 21 EMA curves, BUY / STOP lines and the served vol_avg, in the SERVED order', async () => {
    stubFetch(bySub);
    mount();
    await screen.findByTestId('gg-tile-PFAI');
    const order = screen.getAllByTestId(/^gg-tile-/).map((e) => e.getAttribute('data-testid'));
    expect(order).toEqual(BOARDS.bull_flag.tiles.map((t: any) => `gg-tile-${t.symbol}`));
    const pf = chartProps.filter((p) => p.tile.symbol === 'PFAI').pop();
    expect(pf.tile.curves.map((c: any) => c.tone)).toEqual(['ema9', 'ema21']);
    expect(pf.tile.lines.map((l: any) => l.tone)).toEqual(['buy', 'stop']);
    expect(pf.tile.vol_avg.values).toHaveLength(pf.tile.bars.length);
    expect(pf.tile.vol_avg).toEqual(BOARDS.bull_flag.tiles[0].vol_avg);
  });

  it('the head row carries the four house chips and PatternChart skips its own copies (no chip printed twice)', async () => {
    stubFetch(bySub);
    mount();
    await screen.findByTestId('gg-tile-PFAI');
    const head = screen.getByTestId('gg-chips-PFAI');
    expect(within(head).getByTestId('growth-PFAI')).toBeTruthy();
    expect(within(head).getByTestId('short-PFAI')).toBeTruthy();
    expect(within(head).getByTestId('explosive')).toBeTruthy();
    expect(within(head).getByTestId('enterable')).toBeTruthy();
    const pf = chartProps.filter((p) => p.tile.symbol === 'PFAI').pop();
    expect([...pf.outerChips].sort()).toEqual(['enterable', 'explosive', 'growth', 'short']);
    // ONE bounce-room read for every name on screen.
    expect(roomSyms[roomSyms.length - 1]).toEqual(BOARDS.bull_flag.tiles.map((t: any) => t.symbol));
  });

  it('a sub-dollar plan line keeps the served decimals: trigger 0.3101 · stop 0.295 (2026-10-20, the MMA finding)', async () => {
    const sub = clone(BOARDS.bull_flag);
    Object.assign(sub.tiles[0].gajjala, { trigger: 0.3101, stop: 0.295, risk_pct: 4.869 });
    stubFetch(() => sub);
    mount();
    const pf = await screen.findByTestId('gg-tile-PFAI');
    expect(within(pf).getByTestId('gg-plan')).toHaveTextContent('trigger 0.3101 · stop 0.295 · risk 4.9%');
    // NEGATIVE: the house three-decimal print would have read "0.310" — the trigger and the stop must not blur
    expect(within(pf).getByTestId('gg-plan').textContent).not.toContain('0.310 ');
  });

  it('card extras: state pill, plan line, ✓ / ✗ / · criteria and the served chips', async () => {
    stubFetch(bySub);
    mount();
    const pf = await screen.findByTestId('gg-tile-PFAI');
    expect(within(pf).getByTestId('gg-state')).toHaveTextContent(BOARDS.bull_flag.tiles[0].gajjala.state_label);
    expect(within(pf).getByTestId('gg-state').className).toContain('gg-state-aplus');
    expect(within(pf).getByTestId('gg-plan')).toHaveTextContent('trigger 4.12 · stop 3.95 · risk 4.1%');
    const crit = within(pf).getByTestId('gg-criteria');
    expect(crit.textContent).toContain('✓ pullback bars — 2 (1–3)');
    const chips = within(pf).getByTestId('gg-chip-row').textContent || '';
    for (const s of ['Float 3.1M', '\u{1F504} float ×4.2', '\u{1F9F1} $5', '+48.2%', 'vol 13.0M (min_av)', 'RTH']) expect(chips).toContain(s);

    const sc = screen.getByTestId('gg-tile-SCNI');
    expect(within(sc).getByTestId('gg-criteria').textContent).toContain('· 9 EMA — warming up (judgeable)');
    const scChips = within(sc).getByTestId('gg-chip-row').textContent || '';
    expect(scChips).toContain('⏸ halted ×2 today (LUDP)');
    expect(scChips).toContain('stopped earlier today on this setup');

    const tc = screen.getByTestId('gg-tile-TCRT');
    expect(within(tc).getByTestId('gg-criteria').textContent).toContain('✗ pullback bars — 5 (1–3 (A+))');
    expect(within(tc).getByTestId('gg-variant')).toHaveTextContent('long flag');
    const tcChips = within(tc).getByTestId('gg-chip-row').textContent || '';
    expect(tcChips).toContain('4 red closes in a row');
    expect(tcChips).toContain('type unknown');
    expect(within(screen.getByTestId('gg-tile-BKYI')).getByTestId('gg-chip-row').textContent).toContain('day 2 · since 2026-10-12');
  });

  it('NEGATIVE: a null chip prints nothing, and the 🎾 history chip rides only the 🎾 sub', async () => {
    const b = clone(BOARDS.bull_flag);
    b.tiles[0].gajjala.chips = { float: null, rotation: '', halts: undefined, psych: [], squeeze_history: 'SQUEEZE-ON-FLAG',
                                  change_pct: null, volume: null, first15: false };
    b.tiles[0].gajjala.listed = null;
    stubFetch(() => b);
    mount();
    const pf = await screen.findByTestId('gg-tile-PFAI');
    expect(within(pf).queryByTestId('gg-chip-row')).toBeNull();
    expect(pf.textContent).not.toContain('SQUEEZE-ON-FLAG');
  });

  it('🎾 sub shows the squeeze-history chip and the float-suspect line; 🌀 shows "B — imperfect"', async () => {
    stubFetch(bySub);
    mount('tab=gajjala&sub=reversal_squeeze');
    const fc = await screen.findByTestId('gg-tile-FCHL');
    const t = within(fc).getByTestId('gg-chip-row').textContent || '';
    expect(t).toContain('\u{1F3BE} squeeze history: 3 of last 30 sessions');
    expect(t).toContain('exceeds shares out');
    fireEvent.click(screen.getByTestId('gg-sub-intraday_vcp'));
    const ax = await screen.findByTestId('gg-tile-AIXI');
    expect(within(ax).getByTestId('gg-grade')).toHaveTextContent('B — imperfect');
  });

  it('the 15m toggle sets `tf` and re-reads with it', async () => {
    const spy = stubFetch(bySub);
    mount();
    await screen.findByTestId('gg-tile-PFAI');
    fireEvent.click(screen.getByTestId('gg-tf-15m'));
    await waitFor(() => expect(new URLSearchParams(loc.search).get('tf')).toBe('15m'));
    await waitFor(() => expect(gajjalaUrls(spy).some((u: string) => u.includes('tf=15m'))).toBe(true));
  });

  it('re-reads on the SERVED cadence only when refresh_sec > 0', async () => {
    const si = vi.spyOn(window, 'setInterval');
    stubFetch(bySub);
    mount();
    await screen.findByTestId('gg-tile-PFAI');
    expect(si.mock.calls.some((c) => c[1] === 300_000)).toBe(true);
  });

  it('NEGATIVE: refresh_sec 0 (closed session) → no timer', async () => {
    const si = vi.spyOn(window, 'setInterval');
    stubFetch(() => ({ ...clone(BOARDS.bull_flag), session: { ...BOARDS.bull_flag.session, refresh_sec: 0 } }));
    mount();
    await screen.findByTestId('gg-tile-PFAI');
    expect(si.mock.calls.some((c) => c[1] == null || c[1] === 0 || c[1] === 300_000)).toBe(false);
  });

  it('NEGATIVE: no tiles → the served empty_note', async () => {
    stubFetch(() => ({ ...clone(BOARDS.bull_flag), tiles: [] }));
    mount();
    expect(await screen.findByTestId('gg-empty')).toHaveTextContent(BOARDS.bull_flag.empty_note);
    expect(screen.queryAllByTestId(/^gg-tile-/)).toHaveLength(0);
  });

  it('📓 renders his quotes with timestamps, S8 / S9 sources and the third-party link labelled — NO tiles', async () => {
    stubFetch(bySub);
    mount('tab=gajjala&sub=playbook');
    const pb = await screen.findByTestId('gg-playbook');
    expect(pb.textContent).toContain("I only do long side trading, I don't short.");
    expect(pb.textContent).toContain('S8 10:19');
    expect(pb.textContent).toContain('S9 2:01:46');
    const rows = screen.getAllByTestId('gg-pb-source');
    expect(rows).toHaveLength(3);
    const third = rows.find((r) => r.textContent?.includes('Retail Traders Repository'))!;
    expect(third.textContent).toContain('third-party');
    expect(third.querySelector('a')?.getAttribute('href')).toBe('https://retailtradersrepository.substack.com/p/goverdhan-gajjala-a-deep-dive-into');
    expect(rows[0].textContent).toContain('first-hand');
    expect(screen.queryAllByTestId(/^gg-tile-/)).toHaveLength(0);
    expect(chartProps).toHaveLength(0);
    expect(roomSyms.every((s) => s.length === 0)).toBe(true);
  });

  it('📓 status pills: the served label, else the raw served code — NEGATIVE never a guessed pill', async () => {
    stubFetch(bySub);
    mount('tab=gajjala&sub=playbook');
    await screen.findByTestId('gg-playbook');
    const pills = screen.getAllByTestId('gg-pb-pill').map((p) => p.textContent);
    expect(pills).toEqual(['his words', 'weird_new_code', '2+ sources']);
  });

  it('🌙 shows the served unchecked line, the A+ recap and a bar-less row without a chart', async () => {
    stubFetch(bySub);
    mount('tab=gajjala&sub=postmarket');
    expect(await screen.findByTestId('gg-unchecked')).toHaveTextContent('12 after-hours gainers not checked yet');
    expect(screen.getByTestId('gg-recap')).toHaveTextContent("Today's A+ recap");
    const av = screen.getByTestId('gg-tile-AVGR');
    expect(av.textContent).toContain('checked 19:46 ET');
    expect(screen.queryByTestId('chart-AVGR')).toBeNull();
  });

  it('☀️ sort buttons are SERVED and set `sort`; a sub click drops it', async () => {
    const spy = stubFetch(bySub);
    mount('tab=gajjala&sub=premarket');
    await screen.findByTestId('gg-tile-YJ');
    expect(screen.getByTestId('gg-sort-change')).toHaveTextContent('% change');
    fireEvent.click(screen.getByTestId('gg-sort-change'));
    await waitFor(() => expect(new URLSearchParams(loc.search).get('sort')).toBe('change'));
    await waitFor(() => expect(gajjalaUrls(spy).some((u: string) => u.includes('sort=change'))).toBe(true));
    expect(screen.getByTestId('gg-tile-LIFW').textContent).toContain("carried from yesterday's after-hours +14.0% (last after-hours pass 20:01)");
    fireEvent.click(screen.getByTestId('gg-sub-bull_flag'));
    await waitFor(() => expect(new URLSearchParams(loc.search).get('sort')).toBeNull());
  });

  it('the board says why it has no 🧨 ordering toggle (contract NO_TOGGLE)', async () => {
    stubFetch(bySub);
    const { container } = mount();
    await screen.findByTestId('gg-tile-PFAI');
    expect(container.querySelector('[data-no-toggle]')?.getAttribute('data-no-toggle')).toMatch(/his setup state orders this board/);
  });

  it('NEGATIVE: rendered text never says bounce / NaN / undefined / None, on every sub', async () => {
    for (const sub of Object.keys(BOARDS)) {
      stubFetch(bySub);
      const { container, unmount } = mount(`tab=gajjala&sub=${sub}`);
      await waitFor(() => expect(container.querySelector('.gg-board')?.textContent || '').toContain(BOARDS[sub].strip.text));
      const txt = container.textContent || '';
      expect(txt, sub).not.toMatch(/bounce/i);
      expect(txt, sub).not.toMatch(/NaN|undefined|\bNone\b|\[object Object\]/);
      unmount();
      vi.unstubAllGlobals();
    }
  });

  it('an HTTP error says so instead of drawing an empty board', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })));
    mount();
    expect(await screen.findByTestId('gg-error')).toHaveTextContent('HTTP 503');
  });

  it('a card drawn on another frame than the toggle says so; same-frame / no-frame cards do not', async () => {
    const b = clone(BOARDS.bull_flag);
    b.tf = '15m';
    const [fell, same, none, junk] = b.tiles.map((t: any) => t.symbol);
    b.tiles[0].tf = '5m';                                  // a read that fell back to 5-minute bars
    b.tiles[1].tf = '15m';                                 // NEGATIVE: equal to the board tf
    delete b.tiles[2].tf;                                  // NEGATIVE: no served frame → never a guess
    b.tiles[3].tf = '1h';                                  // NEGATIVE: not a bar size this board draws
    stubFetch(() => clone(b));
    mount();
    await screen.findByTestId(`gg-tile-${fell}`);
    expect(screen.getByTestId('gg-tf-15m')).toHaveAttribute('aria-selected', 'true');
    const chip = within(screen.getByTestId(`gg-tile-${fell}`)).getByTestId(`gg-frame-${fell}`);
    expect(chip).toHaveTextContent('5-min read');
    expect(chip.getAttribute('title')).toMatch(/5-min bars, not the 15-min bars/);
    for (const sym of [same, none, junk]) expect(screen.queryByTestId(`gg-frame-${sym}`), sym).toBeNull();
  });

  it('NEGATIVE: on a 5m board a 5m card carries no frame chip', async () => {
    const b = clone(BOARDS.bull_flag);
    b.tiles.forEach((t: any) => { t.tf = '5m'; });
    stubFetch(() => clone(b));
    const { container } = mount();
    await screen.findByTestId('gg-tile-PFAI');
    expect(container.querySelector('[data-testid^="gg-frame-"]')).toBeNull();
  });

  it("the fixture's stale_after_sec equals the /alerts stale rule for a 300 s pass", () => {
    expect(staleAfterSec(300)).toBe(BOARDS.bull_flag.pass.stale_after_sec);
  });
});
