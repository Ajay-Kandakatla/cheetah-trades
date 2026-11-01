import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import trGolden from './__fixtures__/gajjala_track_record_golden_2026_10_16.json';
import type { CurrentUser } from '../hooks/useUser';
import { TAB_META } from '../lib/chartMaps';
import { _resetGgLiteCache } from './GgEntryTape';

/* 🧪 Gajjala · Audited on the real board and the real Chart Maps page (2026-11-01, gg-audited spec §3.8 / §4 WP-E).
 *
 * Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day.."
 * "Gajjals-Audited" "So we can keep track of improvements on this tab".
 *
 * ONE board component, a third page: variant="gajjala_audited" GETs /chart-maps/gajjala-audited and POSTs its /scan on
 * open; three mount points draw the served `audited` (the folded 🧪 strip), `held` (A+ held by the audit — listed,
 * never hidden) and `audited_compare` (the 🏁 side by side). A held tile prints its served state_label with the class
 * gg-state-aplus_held. NEGATIVES: no block → nothing renders, no crash; a 🚩 payload that (wrongly) carries the blocks
 * still prints only served words; floor_reached is never printed as a verdict; the three new components type no
 * digit and never the b-word.
 *
 * Boards: SYNTHETIC in-file clones of the 2026-10-13 hand fixture and the 2026-10-16 🏁 golden, shaped as the spec's
 * §3.6 / §3.9 serve the audited board — every sentence below is test data standing in for the served words. */

let userRet: CurrentUser | null = null;
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => {} }));
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
import ChartMaps from '../pages/ChartMaps';

const clone = (x: any) => JSON.parse(JSON.stringify(x));
const HAND: Record<string, any> = (hand as any).boards;
const TR5D: any = (trGolden as any).boards['5d'];
const OWNER: CurrentUser = {
  email: 'owner@example.com', display_name: 'Owner', given_name: 'Owner', picture: null,
  is_default_user: false, is_admin: true,
};
const PA = '/chart-maps/gajjala-audited';
const P5 = '/chart-maps/gajjala';
const P1 = '/chart-maps/gajjala-1m';

/* ---- the served blocks (test data, WORDS_GGA-shaped) ---- */
const VARIANT_GGA = {
  key: 'gga', tab: 'gajjala_audited', label: '\u{1F9EA} Gajjala · Audited',
  title: "\u{1F9EA} Gajjala · Audited — \u{1F6A9} Gajjala's A+ reads, filtered by the audit overlay · UNMEASURED",
  honesty: "The same scanner, the same bars, the same detectors as \u{1F6A9} Gajjala's — served honesty line · UNMEASURED.",
  tfs: ['5m', '15m'], primary: '5m', slow: '15m', api_base: PA, record_from: '2026-11-01',
};
const REG = ['G1', 'G2', 'G3', 'G4'].map((id) => ({
  id, name: `name-${id}`, rule: `rule text ${id}`, params_text: `params ${id}`, source_text: `source ${id} prereg row`,
  since: `since-${id}`, status: id === 'G3' ? 'lane_only' : 'on', status_text: id === 'G3' ? 'lane only — not applied' : 'ON',
  verdict: 'UNMEASURED', verdict_text: `verdict ${id} UNMEASURED`, changes_text: `changes ${id}`, applies: id !== 'G3',
  note: `note ${id}`,
}));
const AUDITED = {
  title: '\u{1F9EA} What is different here',
  registry: REG, on_ids: ['G1', 'G2', 'G4'],
  lane_only_text: 'served lane-only line — registered here, not applied on this tab. UNMEASURED.',
  unmeasured_text: 'served unmeasured line — the replay read TOO SMALL.',
  process_text: 'served process line — the 🚩 tab is never the target.',
  pass: { at_et: '10:40', ok: true, n_read: 9, n_aplus_original: 2, n_aplus_audited: 1, n_held: 1,
          text: '\u{1F9EA} audit overlay ran on the 10:40 ET pass · 9 reads · 2 A+ on the original · 1 pass · 1 held' },
  stale: false, stale_text: null,
  unaudited: { n: 1, text: '1 A+ on the original carry no audit on this pass — shown as the original reads them' },
};
const HELD = {
  title: '\u{1F6A9} A+ on the original, held here by the audit · 1 · UNMEASURED',
  rows: [{
    symbol: 'BKYI', setup: 'bull_flag', setup_label: '\u{1F6A9} Bull Flag', frame: '5m', trigger: 1.31, stop: 1.2,
    risk_pct: 8.4, since_et: '10:40', href: '/chart-maps?tab=gajjala_audited&sub=bull_flag&focus=BKYI',
    text: 'BKYI \u{1F6A9} Bull Flag · trigger 1.31 · stop 1.20 · served held row line',
    held_by: [{ id: 'G1', why: 'break-bar volume 120K < 2× the base mean 90K' }, { id: 'G4', why: 'stop 1.20 is 8.4% under the trigger (> 10%)' }],
    audit_text: '\u{1F6A9} A+ on the original, held here by: G1 — served why · UNMEASURED',
  }],
  empty_text: 'No A+ held by the audit right now.',
  note: 'served held note — an audit-derived modification becomes a registry entry.',
};
const HELD_LABEL = '\u{1F6A9} A+ on the original, held here by: G1 — the break bar closed 1.30 vs trigger 1.31 · UNMEASURED';
const COMPARE = {
  title: '\u{1F9EA} Audited vs \u{1F6A9} original — the same sessions, the same trade math · UNMEASURED',
  honesty: 'served compare honesty — gross, as the 🏁 ledger grades. UNMEASURED until the record holds the floor; 1 so far.',
  span: '5d',
  sides: [
    { key: 'original', label: '\u{1F6A9} original', n: 7, filled: 5, win: 3, loss: 2, open_flat: 0, unfilled: 2, mean_r: 0.4, win_pct: 60, text: 'served original line' },
    { key: 'audited', label: '\u{1F9EA} audited', n: 4, filled: 3, win: 2, loss: 1, open_flat: 0, unfilled: 1, mean_r: 0.6667, win_pct: 66.7, text: 'served audited line' },
  ],
  held: { n: 3, win: 1, loss: 1, open_flat: 0, unfilled: 1, no_original: 0, mean_r: 0, text: 'served held compare line · 3 held',
          rows: [{ date: '2026-11-03', symbol: 'BKYI', setup: 'bull_flag', setup_label: '\u{1F6A9} Bull Flag', held_by: ['G1'],
                   outcome: 'loss', outcome_text: 'loss on the original', text: 'BKYI held by G1 — loss on the original' }] },
  recon: { original_only: 1, audited_only: 1, both: 0, text: '1 A+ on the original with no audited or held row · 1 audited with no original row · UNMEASURED' },
  by_rule: [{ id: 'G1', n_held: 2, win: 1, loss: 1, unfilled: 0, text: 'served G1 rule line' },
            { id: 'G4', n_held: 2, win: 0, loss: 1, unfilled: 1, text: 'served G4 rule line' }],
  by_rule_note: 'a held A+ counts under every rule it failed — these rows can sum past the held total',
  by_day: [{ date: '2026-11-03', label: 'Mon 11-03', original: { n: 7, win: 3, loss: 2 }, audited: { n: 4, win: 2, loss: 1 },
             held: { n: 3, win: 1, loss: 1 }, text: 'served day line' }],
  entry_weeks: 31, floor_weeks: 30, floor_reached: true,
  unmeasured_text: 'The record holds 31 entry weeks (the lab’s floor is 30) — still UNMEASURED until the lab’s out-of-sample + placebo read; nothing flips by count.',
};
const SCAN = { state: 'idle', on_demand: false, as_of_text: 'served as-of line', rescan_label: 'served rescan', rescan_title: 'served title' };

/** The audited board (bull_flag sub): tab gajjala_audited, the variant block, the three blocks, BKYI held. */
function ggaBoard(opts: { blocks?: boolean; tab?: string } = {}): any {
  const b = clone(HAND.bull_flag);
  b.session = { ...b.session, refresh_sec: 0 };
  b.scan = { ...SCAN };
  b.tab = opts.tab ?? 'gajjala_audited';
  if (b.tab === 'gajjala_audited') b.variant = clone(VARIANT_GGA);
  b.enterable = { title: 'served A+ title', rows: [], empty_text: 'served no A+ line', note: null };
  b.tiles = b.tiles.map((t: any) => (t.symbol === 'BKYI'
    ? { ...t, gajjala: { ...t.gajjala, state: 'aplus_held', state_label: HELD_LABEL,
                         audit: { aplus: false, original_aplus: true, rules: ['G1', 'G2', 'G4'], passed: ['G2', 'G4'],
                                  failed: [{ id: 'G1', why: 'the break bar closed 1.30 vs trigger 1.31' }], frame: '5m',
                                  values: {}, text: HELD_LABEL, version: 1 } } }
    : t));
  if (opts.blocks !== false) {
    b.audited = clone(AUDITED);
    b.held = clone(HELD);
  }
  return b;
}
/** The audited 🏁 board from the 2026-10-16 golden + the compare block. */
function ggaTrBoard(opts: { blocks?: boolean; tab?: string } = {}): any {
  const b = clone(TR5D);
  b.session = { ...b.session, refresh_sec: 0 };
  b.tab = opts.tab ?? 'gajjala_audited';
  if (b.tab === 'gajjala_audited') b.variant = clone(VARIANT_GGA);
  if (opts.blocks !== false) {
    b.audited = clone(AUDITED);
    b.held = clone(HELD);
    b.audited_compare = clone(COMPARE);
  }
  return b;
}

type Call = { method: string; path: string; url: string; q: URLSearchParams };
let calls: Call[] = [];
const RULES = { sections: { gajjala: { title: 'R', emoji: '\u{1F6A9}', picks: [], stops: [], alerts: [], note: 'N' } } };
function stub(boards: { gga?: (q: URLSearchParams) => any; gg5?: (q: URLSearchParams) => any } = {}) {
  calls = [];
  const spy = vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    const method = String(init?.method || 'GET').toUpperCase();
    calls.push({ method, path: u.pathname, url: String(url), q: u.searchParams });
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.endsWith('/entry-tape')) return ok({ id: 'x', bars: [], rules: [], lite: true });
    if (u.pathname.endsWith(PA)) return ok((boards.gga || ((q) => (q.get('sub') === 'track_record' ? ggaTrBoard() : ggaBoard())))(u.searchParams));
    if (u.pathname.endsWith(P5)) return ok((boards.gg5 || (() => ggaBoard({ blocks: false, tab: 'gajjala' })))(u.searchParams));
    if (u.pathname.endsWith('/supply-demand/rules')) return ok(RULES);
    return ok({});
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const ends = (p: string) => calls.filter((c) => c.path.endsWith(p));
const getsTo = (p: string) => ends(p).filter((c) => c.method === 'GET');
const postsTo = (p: string) => ends(p).filter((c) => c.method === 'POST');
const sleep = (ms: number) => act(() => new Promise<void>((r) => setTimeout(r, ms)));
const mount = (q: string, variant?: 'gajjala' | 'gajjala_audited') => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}>
    {variant ? <GajjalaBoard variant={variant} /> : <GajjalaBoard />}
  </MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
/** Strip every served string out of `text`; what is left must be only whitespace / the ⓘ fold mark. */
const leftover = (text: string, served: string[]) =>
  [...served].sort((a, b) => b.length - a.length).reduce((t, s) => t.split(s).join(''), text).replace(/[\sⓘ]/g, '');

beforeEach(() => { userRet = OWNER; _resetGgLiteCache(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

describe('GajjalaBoard variant="gajjala_audited" — its own endpoint (2026-11-01)', () => {
  it('GETs /chart-maps/gajjala-audited? and POSTs its /scan ONCE on open (owner); data-variant', async () => {
    stub();
    const { container } = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(container);
    await sleep(30);
    expect(getsTo(PA).length).toBeGreaterThan(0);
    expect(getsTo(PA)[0].url).toContain('/chart-maps/gajjala-audited?');
    expect(getsTo(PA)[0].q.get('sub')).toBe('bull_flag');
    expect(postsTo(`${PA}/scan`)).toHaveLength(1);
    expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala_audited');
    // NEGATIVE: never a 🚩 or 1-minute path
    expect(getsTo(P5)).toHaveLength(0);
    expect(postsTo(`${P5}/scan`)).toHaveLength(0);
    expect(ends(P1)).toHaveLength(0);
  });

  it('prints the served variant title + honesty verbatim', async () => {
    stub();
    const { container } = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(container);
    expect(screen.getByTestId('gg-page-title').textContent).toBe(VARIANT_GGA.title);
    expect(screen.getByTestId('gg-page-honesty').textContent).toBe(VARIANT_GGA.honesty);
  });
});

describe('🧪 the strip — served `audited`, folded by default (Rule #5)', () => {
  it('renders the four served registry rows (id / rule / source / since / verdict / note) and the served lines', async () => {
    stub();
    const { container } = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(container);
    const strip = screen.getByTestId('gg-audited-strip');
    expect(within(strip).getByTestId('gg-audited-title').textContent).toBe(AUDITED.title);
    expect(within(strip).getByTestId('gg-audited-pass').textContent).toBe(AUDITED.pass.text);
    for (const r of REG) {
      const row = within(strip).getByTestId(`gg-audited-rule-${r.id}`);
      for (const w of [r.id, r.rule, r.source_text, r.since, r.verdict_text, r.note, r.status_text]) expect(row.textContent).toContain(w);
    }
    expect(strip.querySelectorAll('.gg-audited-rule')).toHaveLength(4);
    expect(within(strip).getByTestId('gg-audited-lane-only').textContent).toBe(AUDITED.lane_only_text);
    expect(within(strip).getByTestId('gg-audited-unmeasured').textContent).toBe(AUDITED.unmeasured_text);
    expect(within(strip).getByTestId('gg-audited-process').textContent).toBe(AUDITED.process_text);
    expect(within(strip).getByTestId('gg-audited-unaudited').textContent).toBe(AUDITED.unaudited.text);
    // NEGATIVE: not stale → no stale line
    expect(within(strip).queryByTestId('gg-audited-stale')).toBeNull();
  });

  it('is FOLDED by default and opens on a click of its summary', async () => {
    stub();
    const { container } = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(container);
    const strip = screen.getByTestId('gg-audited-strip') as HTMLDetailsElement;
    expect(strip.tagName).toBe('DETAILS');
    expect(strip.open).toBe(false);
    expect(strip.hasAttribute('open')).toBe(false);
    fireEvent.click(strip.querySelector('summary') as HTMLElement);
    await waitFor(() => expect(strip.open).toBe(true));
  });

  it('the stale line prints only when stale is true; the unaudited line only when its text is served', async () => {
    stub({ gga: () => {
      const b = ggaBoard();
      b.audited.stale = true;
      b.audited.stale_text = '⚠ the audit overlay did not run on the latest 🚩 pass (10:45 ET) — served';
      b.audited.unaudited = { n: 0, text: null };
      return b;
    } });
    const { container } = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(container);
    expect(screen.getByTestId('gg-audited-stale').textContent).toContain('did not run on the latest');
    expect(screen.queryByTestId('gg-audited-unaudited')).toBeNull();
    cleanup();
    stub({ gga: () => { const b = ggaBoard(); b.audited.stale = false; b.audited.stale_text = 'served but not stale'; return b; } });
    const again = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(again.container);
    // NEGATIVE: a stale_text with stale false is never printed
    expect(screen.queryByTestId('gg-audited-stale')).toBeNull();
  });
});

describe('🚩 held — A+ held by the audit, listed, never hidden', () => {
  it('lists the served rows with the held_by chips, the served audit line, the served link', async () => {
    stub();
    const { container } = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(container);
    const held = screen.getByTestId('gg-held');
    expect(within(held).getByTestId('gg-held-title').textContent).toBe(HELD.title);
    const line = within(held).getByTestId('gg-held-line-BKYI-bull_flag');
    expect(line.textContent).toBe(HELD.rows[0].text);
    expect(line.getAttribute('href')).toBe(HELD.rows[0].href);
    const chips = held.querySelectorAll('.gg-held-rule');
    expect([...chips].map((c) => c.textContent)).toEqual(['G1', 'G4']);
    expect(chips[0].getAttribute('title')).toBe(HELD.rows[0].held_by[0].why);
    expect(within(held).getByTestId('gg-held-audit-BKYI-bull_flag').textContent).toBe(HELD.rows[0].audit_text);
    expect(within(held).getByTestId('gg-held-note').textContent).toBe(HELD.note);
    // NEGATIVE: rows present → no empty line
    expect(within(held).queryByTestId('gg-held-empty')).toBeNull();
  });

  it('no rows → the served empty line; NEGATIVE: a non-path href is never a link', async () => {
    stub({ gga: () => { const b = ggaBoard(); b.held.rows = []; return b; } });
    const { container } = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(container);
    expect(screen.getByTestId('gg-held-empty').textContent).toBe(HELD.empty_text);
    cleanup();
    stub({ gga: () => { const b = ggaBoard(); b.held.rows[0].href = 'https://evil.example/x'; return b; } });
    const again = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(again.container);
    expect(screen.getByTestId('gg-held-line-BKYI-bull_flag').tagName).toBe('SPAN');
  });

  it('the held tile is PRESENT and prints its served state_label with class gg-state-aplus_held', async () => {
    stub();
    const { container } = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(container);
    const pill = container.querySelector('.gg-state-aplus_held') as HTMLElement;
    expect(pill).toBeTruthy();
    expect(pill.textContent).toBe(HELD_LABEL);
    expect(pill.textContent?.startsWith('\u{1F6A9} A+ on the original, held here by: G1')).toBe(true);
    // NEGATIVE: the held tile never wears the A+ class
    expect(pill.classList.contains('gg-state-aplus')).toBe(false);
  });
});

describe('🏁 the compare block — every number served, floor_reached never a verdict', () => {
  it('prints the served sides / held / recon / by_rule + note / by_day / honesty / unmeasured', async () => {
    stub();
    const { container } = mount('tab=gajjala_audited&sub=track_record', 'gajjala_audited');
    await loaded(container);
    const cmp = await screen.findByTestId('gg-audited-compare');
    expect(within(cmp).getByTestId('gg-audited-compare-title').textContent).toBe(COMPARE.title);
    const orig = within(cmp).getByTestId('gg-audited-side-original');
    const cells = [...orig.querySelectorAll('td')].map((td) => td.textContent);
    expect(cells).toEqual(['7', '5', '3', '2', '0', '2', '0.4', '60', 'served original line']);
    const aud = within(cmp).getByTestId('gg-audited-side-audited');
    // the served mean_r is printed AS SERVED — never rounded here
    expect([...aud.querySelectorAll('td')].map((td) => td.textContent)).toContain('0.6667');
    expect(within(cmp).getByTestId('gg-audited-compare-held').textContent).toContain(COMPARE.held.text);
    expect(within(cmp).getByTestId('gg-audited-compare-held-BKYI-bull_flag').textContent).toBe(COMPARE.held.rows[0].text);
    expect(within(cmp).getByTestId('gg-audited-recon').textContent).toBe(COMPARE.recon.text);
    const g4 = within(cmp).getByTestId('gg-audited-by-rule-G4');
    expect([...g4.querySelectorAll('td')].map((td) => td.textContent)).toEqual(['2', '0', '1', '1', 'served G4 rule line']);
    expect(within(cmp).getByTestId('gg-audited-by-rule-note').textContent).toBe(COMPARE.by_rule_note);
    const day = within(cmp).getByTestId('gg-audited-by-day-2026-11-03');
    expect(day.textContent).toContain('Mon 11-03');
    expect(day.textContent).toContain('7 · 3 W · 2 L');
    expect(day.textContent).toContain('4 · 2 W · 1 L');
    expect(within(cmp).getByTestId('gg-audited-compare-honesty').textContent).toBe(COMPARE.honesty);
    expect(within(cmp).getByTestId('gg-audited-compare-unmeasured').textContent).toBe(COMPARE.unmeasured_text);
    // the compare block sits above the Track record panel
    const tr = screen.getByTestId('gg-track-record');
    expect(cmp.compareDocumentPosition(tr) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('NEGATIVE: floor_reached true is never printed as a verdict — only the served unmeasured words', async () => {
    stub();
    const { container } = mount('tab=gajjala_audited&sub=track_record', 'gajjala_audited');
    await loaded(container);
    const cmp = await screen.findByTestId('gg-audited-compare');
    const t = cmp.textContent || '';
    expect(t).not.toMatch(/floor[ _]reached|\btrue\b|\bfalse\b/i);
    expect(t.replace(COMPARE.unmeasured_text, '').replace(COMPARE.title, '')
      .replace(COMPARE.honesty, '').replace(COMPARE.recon.text, '')).not.toMatch(/\bMEASURED\b/);
    // entry_weeks / floor_weeks are not printed by the FE (the served sentences carry them)
    expect(t).not.toContain('31 ·');
  });

  it('NEGATIVE: the 🏁 sub without a compare block renders no compare table and no crash', async () => {
    stub({ gga: () => { const b = ggaTrBoard(); delete b.audited_compare; return b; } });
    const { container } = mount('tab=gajjala_audited&sub=track_record', 'gajjala_audited');
    await loaded(container);
    await sleep(20);
    expect(screen.queryByTestId('gg-audited-compare')).toBeNull();
  });
});

describe('NEGATIVES — absent blocks, a 🚩 payload, typed words', () => {
  it('no audited / held / audited_compare in the payload → no strip, no held section, no compare, no crash', async () => {
    stub({ gga: (q) => {
      const b = q.get('sub') === 'track_record' ? ggaTrBoard({ blocks: false }) : ggaBoard({ blocks: false });
      return b;
    } });
    const { container } = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(container);
    expect(screen.queryByTestId('gg-audited-strip')).toBeNull();
    expect(screen.queryByTestId('gg-held')).toBeNull();
    expect(screen.queryByTestId('gg-audited-compare')).toBeNull();
    expect(container.querySelector('.gg-tile, [data-testid^="gg-tile"]') || container.querySelector('.gg-board')).toBeTruthy();
    cleanup();
    stub({ gga: () => ggaTrBoard({ blocks: false }) });
    const tr = mount('tab=gajjala_audited&sub=track_record', 'gajjala_audited');
    await loaded(tr.container);
    expect(screen.queryByTestId('gg-audited-compare')).toBeNull();
  });

  it('NEGATIVE: null blocks render nothing either', async () => {
    stub({ gga: () => { const b = ggaBoard(); b.audited = null; b.held = null; b.audited_compare = null; return b; } });
    const { container } = mount('tab=gajjala_audited&sub=bull_flag', 'gajjala_audited');
    await loaded(container);
    expect(screen.queryByTestId('gg-audited-strip')).toBeNull();
    expect(screen.queryByTestId('gg-held')).toBeNull();
  });

  it("NEGATIVE: 🚩 Gajjala's with a payload that (wrongly) carries the blocks prints ONLY served words — nothing composed", async () => {
    stub({ gg5: () => { const b = ggaBoard({ tab: 'gajjala' }); return b; } });
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    expect(getsTo(PA)).toHaveLength(0);
    const strip = screen.getByTestId('gg-audited-strip');
    const servedStrip = [AUDITED.title, AUDITED.pass.text, AUDITED.lane_only_text, AUDITED.unmeasured_text, AUDITED.process_text,
      AUDITED.unaudited.text, ...REG.flatMap((r) => [r.id, r.name, r.status_text, r.rule, r.params_text, r.source_text, r.since,
        r.verdict_text, r.changes_text, r.note])];
    expect(leftover(strip.textContent || '', servedStrip)).toBe('');
    const held = screen.getByTestId('gg-held');
    const r0 = HELD.rows[0];
    const servedHeld = [HELD.title, HELD.note, r0.text, r0.setup_label, r0.audit_text, ...r0.held_by.map((h) => h.id)];
    expect(leftover(held.textContent || '', servedHeld)).toBe('');
  });

  it('NEGATIVE: the three new components type no digit (outside test ids) and never the b-word', async () => {
    const files = ['./GgAuditedStrip.tsx?raw', './GgAuditedHeld.tsx?raw', './GgAuditedCompare.tsx?raw'];
    const srcs = [
      (await import('./GgAuditedStrip.tsx?raw')).default as string,
      (await import('./GgAuditedHeld.tsx?raw')).default as string,
      (await import('./GgAuditedCompare.tsx?raw')).default as string,
    ];
    expect(srcs).toHaveLength(files.length);
    for (const src of srcs) {
      expect(src).not.toMatch(new RegExp('b' + 'ounce', 'i'));
      const code = src
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/\/\/[^\n]*/g, '')
        .replace(/data-testid=\{`[^`]*`\}|data-testid="[^"]*"/g, '');
      expect(code).not.toMatch(/\d/);
    }
  });

  it('NEGATIVE: no "edge" claim in the tab label / blurb words of the audited page', () => {
    expect(TAB_META.gajjala_audited.blurb).not.toMatch(/\bedge\b/i);
  });
});

describe('ChartMaps mounts the audited board (2026-11-01)', () => {
  const page = (q: string) => render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><ChartMaps /></MemoryRouter>);

  it('?tab=gajjala_audited mounts GajjalaBoard variant="gajjala_audited" — it fetches /chart-maps/gajjala-audited?', async () => {
    stub();
    const { container } = page('tab=gajjala_audited');
    await waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala_audited'));
    await waitFor(() => expect(getsTo(PA).length).toBeGreaterThan(0));
    expect(getsTo(PA)[0].url).toContain('/chart-maps/gajjala-audited?');
    expect(getsTo(P5)).toHaveLength(0);
    expect(screen.getByRole('tab', { name: TAB_META.gajjala_audited.label })).toHaveAttribute('aria-selected', 'true');
  });

  it('switching gajjala → gajjala_audited REMOUNTS: a second on-open POST, to the audited path (key="gajjala_audited")', async () => {
    stub();
    const { container } = page('tab=gajjala&sub=bull_flag');
    await waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
    await waitFor(() => expect(postsTo(`${P5}/scan`)).toHaveLength(1));
    fireEvent.click(screen.getByRole('tab', { name: TAB_META.gajjala_audited.label }));
    await waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala_audited'));
    await waitFor(() => expect(postsTo(`${PA}/scan`)).toHaveLength(1));
    await waitFor(() => expect(getsTo(PA).length).toBeGreaterThan(0));
    await sleep(30);
    expect(postsTo(`${P5}/scan`)).toHaveLength(1);
    // the 🚩 `sub` did not cross the border (tabSearch over GAJJALA_TABS)
    expect(getsTo(PA)[0].q.has('sub')).toBe(false);
  });

  it("NEGATIVE: ?tab=gajjala never fetches the audited endpoint and draws no 🧪 block", async () => {
    stub();
    const { container } = page('tab=gajjala');
    await waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala'));
    await waitFor(() => expect(getsTo(P5).length).toBeGreaterThan(0));
    await sleep(20);
    expect(ends(PA)).toHaveLength(0);
    expect(screen.queryByTestId('gg-audited-strip')).toBeNull();
    expect(screen.queryByTestId('gg-held')).toBeNull();
  });
});
