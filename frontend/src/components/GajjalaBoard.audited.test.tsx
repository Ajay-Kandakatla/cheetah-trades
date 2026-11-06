import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import trGolden from './__fixtures__/gajjala_track_record_golden_2026_10_16.json';
import trackFix from './__fixtures__/gajjala_audited_track_2026_11_05.json';
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

import GajjalaBoard, { ggTrTapeAt } from './GajjalaBoard';
import { GgAuditedCompare } from './GgAuditedCompare';
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
/* The registry as served from 2026-11-01: G1–G4 + the eight modifications (T1 T2 A1 H1 T4 A2 = filters, T3 T5 =
 * exits), every row carrying a `kind` WORD. G3 stays lane-only → on_ids = the other eleven. */
const REG_IDS = ['G1', 'G2', 'G3', 'G4', 'T1', 'T2', 'A1', 'H1', 'T4', 'A2', 'T3', 'T5'];
const EXIT_IDS = ['T3', 'T5'];
const REG = REG_IDS.map((id) => ({
  id, name: `name-${id}`, rule: `rule text ${id}`, params_text: `params ${id}`, source_text: `source ${id} prereg row`,
  since: `since-${id}`, status: id === 'G3' ? 'lane_only' : 'on', status_text: id === 'G3' ? 'lane only — not applied' : 'ON',
  verdict: 'UNMEASURED', verdict_text: `verdict ${id} UNMEASURED`, changes_text: `changes ${id}`, applies: id !== 'G3',
  note: `note ${id}`, kind: EXIT_IDS.includes(id) ? 'exit' : 'filter',
}));
const AUDITED = {
  title: '\u{1F9EA} What is different here',
  registry: REG, on_ids: REG_IDS.filter((id) => id !== 'G3'),
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
/* 🧪 Rule by rule (2026-11-01) — test data shaped like audited_tab._per_rule. The served TEXTS carry odd numbers
 * ("0.6667", "fired on 3 rung bars · alone on 2", "removed 1 winner and 2 losers") that any arithmetic would change, and
 * the numeric fields deliberately DISAGREE with the texts (n 5 vs "3 A+"; fired_alone 7; tie_held 9) — the FE must print
 * the texts and never compose from the numbers. No served text in the T1 / T4 rows contains a 7 or a 9. */
const SIDE_NUMS = { n: 5, win: 4, loss: 4, unfilled: 4, open_flat: 4, pending: 4, no_original: 4, mean_r: 0.123456 };
const prSide = (label: string, text: string) => ({ ...SIDE_NUMS, label, text });
const PR_WITH = 'with the rule';
const PR_HELD = 'held by the rule — what the original did';
const PR_CAP = 'held — cap reached — what the original did';
const PR_GGM = "GG's math on the same rows";
const PER_RULE_KEYS = ['G1', 'G2', 'G4', 'T1', 'T2', 'A1', 'H1', 'T4', 'A2', 'T3_2R', 'T3_3R', 'T5'];
const PER_RULE: any[] = PER_RULE_KEYS.map((key) => {
  const id = key.split('_')[0];
  const exit = EXIT_IDS.includes(id);
  const row: any = {
    key, id, name: `name-${id}`, kind: exit ? 'exit' : key === 'T1' ? 'cap' : 'filter', label: `${key} served label`,
    with: prSide(PR_WITH, `${PR_WITH}: 3 A+ · 2 W / 1 L · 0 no entry · mean +0.6667R`),
    other: prSide(exit ? PR_GGM : PR_HELD, `${exit ? PR_GGM : PR_HELD}: 3 A+ · 1 W / 2 L · 0 no entry · mean −0.3333R`),
    not_judged: 4, fired_alone: null, tie_held: null,
    delta_text: exit ? `${key} served label: 2 W / 1 L · GG's math: 1 W / 2 L on the same 3` : 'removed 1 winner and 2 losers · 0 never filled',
    text: `${key} served full sentence · UNMEASURED`,
  };
  if (key === 'T4' || key === 'T1') row.with = prSide(PR_WITH, `${PR_WITH}: 2 A+ · 1 W / 1 L · 0 no entry · mean +0.5000R`);
  if (key === 'T4') {
    row.fired_alone = 7;
    row.other = prSide(PR_HELD, `${PR_HELD}: 3 A+ · 1 W / 2 L · 0 no entry · mean −0.3333R · fired on 3 rung bars · alone on 2`);
  }
  if (key === 'T1') {
    row.tie_held = 9;
    row.other = prSide(PR_CAP, `${PR_CAP}: 2 A+ · 1 W / 1 L · 0 no entry · mean +0.0000R · 1 held on a tied bar — \u{1F6A9}'s ring order broke the tie`);
  }
  if (key === 'T3_3R') {
    row.with = prSide(PR_WITH, `${PR_WITH}: 0 A+ · 0 W / 0 L · 0 no entry · 3 not graded yet · mean —`);
    row.delta_text = 'not graded yet — exit grades land the night after the session';
  }
  return row;
});
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
  per_rule_title: '\u{1F9EA} Rule by rule — what each change would have done on the same A+ · counts, not verdicts · UNMEASURED',
  per_rule: PER_RULE,
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
function stub(boards: { gga?: (q: URLSearchParams) => any; gg5?: (q: URLSearchParams) => any; gg1?: (q: URLSearchParams) => any } = {}) {
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
    if (boards.gg1 && u.pathname.endsWith(P1)) return ok(boards.gg1(u.searchParams));
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
const mount = (q: string, variant?: 'gajjala' | 'gajjala_1m' | 'gajjala_audited') => render(
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
  it('renders the twelve served registry rows (id / rule / source / since / verdict / note) and the served lines', async () => {
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
    expect(strip.querySelectorAll('.gg-audited-rule')).toHaveLength(12);
    expect([...strip.querySelectorAll('.gg-audited-rule')].map((li) => li.getAttribute('data-testid')))
      .toEqual(REG_IDS.map((id) => `gg-audited-rule-${id}`));
    // NEGATIVE: `kind` is a served WORD the strip does not print — never as a number, never as a word of its own
    expect(AUDITED.on_ids).toHaveLength(11);
    expect(strip.textContent || '').not.toMatch(/\b(filter|exit|kind)\b/);
    expect(strip.querySelector('[data-testid^="gg-audited-rule-kind"]')).toBeNull();
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
  it('prints the served sides / held / recon / per_rule + note / by_day / honesty / unmeasured', async () => {
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
    const g4 = within(cmp).getByTestId('gg-audited-per-rule-G4');
    expect(g4.querySelector('th')?.textContent).toBe(PER_RULE[2].label);
    expect([...g4.querySelectorAll('td')].map((td) => td.textContent))
      .toEqual([PER_RULE[2].with.text, PER_RULE[2].other.text, PER_RULE[2].delta_text]);
    expect(within(cmp).getByTestId('gg-audited-by-rule-note').textContent).toBe(COMPARE.by_rule_note);
    const day = within(cmp).getByTestId('gg-audited-by-day-2026-11-03');
    expect(day.textContent).toContain('Mon 11-03');
    expect(day.textContent).toContain('7 · 3 W · 2 L');
    expect(day.textContent).toContain('4 · 2 W · 1 L');
    expect(within(cmp).getByTestId('gg-audited-compare-honesty').textContent).toBe(COMPARE.honesty);
    expect(within(cmp).getByTestId('gg-audited-compare-unmeasured').textContent).toBe(COMPARE.unmeasured_text);
    // 🧪 2026-11-05 (gg-track-parity, HIS CALL #30 default): the 🏁 rows FIRST, the compare block below them
    const tr = screen.getByTestId('gg-track-record');
    expect(tr.compareDocumentPosition(cmp) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(cmp.compareDocumentPosition(tr) & Node.DOCUMENT_POSITION_FOLLOWING).toBeFalsy();
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

/* 🧪 Rule by rule (2026-11-01). Ajay: "Yes make the changes in audited please" and "But keep a track record too to see
 * the winners and loster". ONE served per-rule table replaces the held-only by_rule table; the FE prints served words. */
describe('🧪 Rule by rule — the served per_rule table (2026-11-01)', () => {
  const cmpOf = (patch: (b: any) => void = () => {}) => { const b: any = clone(COMPARE); patch(b); return b; };
  const ruleTable = (root: ParentNode) => root.querySelector('[data-testid="gg-audited-per-rule"]') as HTMLElement | null;

  it('ONE table, one row per served row in served order; every cell = label / with.text / other.text / delta_text verbatim', async () => {
    stub();
    const { container } = mount('tab=gajjala_audited&sub=track_record', 'gajjala_audited');
    await loaded(container);
    const cmp = await screen.findByTestId('gg-audited-compare');
    expect(cmp.querySelectorAll('[data-testid="gg-audited-per-rule"]')).toHaveLength(1);
    const table = ruleTable(cmp)!;
    const rows = [...table.querySelectorAll('tbody tr')];
    expect(rows.map((r) => r.getAttribute('data-testid'))).toEqual(PER_RULE_KEYS.map((k) => `gg-audited-per-rule-${k}`));
    PER_RULE.forEach((pr, i) => {
      expect(rows[i].querySelector('th')?.textContent).toBe(pr.label);
      expect([...rows[i].querySelectorAll('td')].map((td) => td.textContent)).toEqual([pr.with.text, pr.other.text, pr.delta_text]);
    });
    // the odd served numbers survive verbatim (any rounding / summing would change them)
    expect(within(table).getByTestId('gg-audited-per-rule-T4').textContent).toContain('fired on 3 rung bars · alone on 2');
    expect(within(table).getByTestId('gg-audited-per-rule-G1').textContent).toContain('removed 1 winner and 2 losers');
    expect(within(table).getByTestId('gg-audited-per-rule-G1').textContent).toContain('+0.6667R');
    expect(within(table).getByTestId('gg-audited-per-rule-T3_3R').textContent).toContain('not graded yet — exit grades land');
    // structural head only
    expect([...table.querySelectorAll('thead th')].map((th) => th.textContent))
      .toEqual(['rule', 'with the rule', "held / GG's math", 'what changed']);
    // the served title above the table, the served note below it
    const title = within(cmp).getByTestId('gg-audited-per-rule-title');
    expect(title.textContent).toBe(COMPARE.per_rule_title);
    const note = within(cmp).getByTestId('gg-audited-by-rule-note');
    expect(note.textContent).toBe(COMPARE.by_rule_note);
    expect(title.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(table.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('NEGATIVE: fired_alone 7 / tie_held 9 and the disagreeing side numbers never reach the DOM — only served texts', () => {
    render(<GgAuditedCompare block={cmpOf()} />);
    const t4 = screen.getByTestId('gg-audited-per-rule-T4');
    const t1 = screen.getByTestId('gg-audited-per-rule-T1');
    expect(t4.textContent).not.toMatch(/7/);
    expect(t1.textContent).not.toMatch(/9/);
    const table = ruleTable(document)!;
    const txt = table.textContent || '';
    // a row's cells are EXACTLY its served strings — nothing else is left over
    const served = ["rule", "with the rule", "held / GG's math", 'what changed',
      ...PER_RULE.flatMap((r) => [r.label, r.with.text, r.other.text, r.delta_text])];
    expect(leftover(txt, served)).toBe('');
    // the numeric fields (n 5, win 4, mean_r 0.123456, not_judged 4) are never printed on their own
    expect(txt).not.toContain('0.123456');
    expect(txt).not.toMatch(/\b5 A\+/);
    expect(txt).not.toMatch(/undefined|null|NaN/);
    // the row's full `text` is not printed either (its parts are)
    expect(txt).not.toContain('served full sentence');
  });

  it('NEGATIVE: no legacy by_rule table — a payload WITH a by_rule key renders nothing for it', () => {
    const legacy = [{ id: 'G1', n_held: 2, win: 1, loss: 1, unfilled: 0, text: 'served G1 legacy rule line' },
                    { id: 'G4', n_held: 2, win: 0, loss: 1, unfilled: 1, text: 'served G4 legacy rule line' }];
    render(<GgAuditedCompare block={cmpOf((b) => { b.by_rule = legacy; delete b.per_rule; })} />);
    const cmp = screen.getByTestId('gg-audited-compare');
    const byRuleIds = [...cmp.querySelectorAll('[data-testid^="gg-audited-by-rule"]')].map((e) => e.getAttribute('data-testid'));
    expect(byRuleIds).toEqual(['gg-audited-by-rule-note']);
    expect(cmp.textContent).not.toContain('legacy rule line');
    expect(ruleTable(cmp)).toBeNull();
    cleanup();
    // both keys served → only the per_rule table, still nothing from by_rule
    render(<GgAuditedCompare block={cmpOf((b) => { b.by_rule = legacy; })} />);
    const again = screen.getByTestId('gg-audited-compare');
    expect(ruleTable(again)).not.toBeNull();
    expect(again.textContent).not.toContain('legacy rule line');
    expect([...again.querySelectorAll('[data-testid^="gg-audited-by-rule"]')].map((e) => e.getAttribute('data-testid')))
      .toEqual(['gg-audited-by-rule-note']);
  });

  it('NEGATIVE: absent / empty / null per_rule → no table and no title; the rest of the compare intact', () => {
    for (const patch of [(b: any) => { delete b.per_rule; }, (b: any) => { b.per_rule = []; }, (b: any) => { b.per_rule = null; },
                         (b: any) => { b.per_rule = [null, { label: 'no key' }, 'junk']; }]) {
      render(<GgAuditedCompare block={cmpOf(patch)} />);
      const cmp = screen.getByTestId('gg-audited-compare');
      expect(ruleTable(cmp)).toBeNull();
      expect(within(cmp).queryByTestId('gg-audited-per-rule-title')).toBeNull();
      expect(cmp.textContent).not.toContain('no key');
      expect(within(cmp).getByTestId('gg-audited-compare-title').textContent).toBe(COMPARE.title);
      expect(within(cmp).getByTestId('gg-audited-side-original')).toBeTruthy();
      expect(within(cmp).getByTestId('gg-audited-recon').textContent).toBe(COMPARE.recon.text);
      expect(within(cmp).getByTestId('gg-audited-by-rule-note').textContent).toBe(COMPARE.by_rule_note);
      expect(within(cmp).getByTestId('gg-audited-by-day-2026-11-03')).toBeTruthy();
      expect(within(cmp).getByTestId('gg-audited-compare-unmeasured').textContent).toBe(COMPARE.unmeasured_text);
      cleanup();
    }
  });

  it('NEGATIVE: a row without served sides / delta prints empty cells (no crash, no composed words); no label → its key', () => {
    render(<GgAuditedCompare block={cmpOf((b) => {
      b.per_rule = [{ key: 'A2', with: null, other: { n: 3, win: 1, loss: 2 }, delta_text: '', fired_alone: 7, tie_held: 9 }];
    })} />);
    const row = screen.getByTestId('gg-audited-per-rule-A2');
    expect(row.querySelector('th')?.textContent).toBe('A2');
    expect([...row.querySelectorAll('td')].map((td) => td.textContent)).toEqual(['', '', '']);
    // the served numbers (n 3, 1 W, 2 L, fired_alone 7, tie_held 9) are never composed into words — only the key prints
    expect(row.textContent).toBe('A2');
  });
});

/* 📱 his phone (430 px): jsdom has no layout, so these are SOURCE guards on the stylesheet the compare imports — the
 * section scrolls the table inside itself and every per-rule cell wraps. The NEGATIVE mutations show each matcher
 * rejects a stylesheet that lost the rule. */
describe('📱 the compare section on the phone — source guards on ggAudited.css', () => {
  async function readCss(): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/src/styles/ggAudited.css`, 'utf8');
  }
  /** The declarations of the `.gg-audited-compare { … }` rule (not `-title`). */
  const compareRule = (src: string): string | null => {
    const m = src.match(/(^|\n)\s*\.gg-audited-compare\s*\{([^}]*)\}/);
    return m ? m[2] : null;
  };
  /** The declarations of the `.gg-audited-per-rule td { … }` rule. */
  const cellRule = (src: string): string | null => {
    const m = src.match(/(^|\n)\s*\.gg-audited-per-rule td\s*\{([^}]*)\}/);
    return m ? m[2] : null;
  };
  /** The body of the phone `@media (max-width: 720px) { … }` block (2026-11-01: stacked per-rule rows, no sideways scroll). */
  const phoneBlock = (src: string): string | null => {
    const m = src.match(/@media \(max-width:\s*720px\)\s*\{([\s\S]*?)\n\}/);
    return m ? m[1] : null;
  };
  const phoneOk = (src: string): boolean => {
    const ph = phoneBlock(src);
    return !!ph
      && /\.gg-audited-per-rule tr\s*\{[^}]*display:\s*block\b/.test(ph)
      && /\.gg-audited-per-rule th\[scope='row'\],\s*\.gg-audited-per-rule td\s*\{[^}]*display:\s*block\b/.test(ph)
      && /\.gg-audited-per-rule th\[scope='row'\],\s*\.gg-audited-per-rule td\s*\{[^}]*min-width:\s*0\b/.test(ph);
  };
  const ok = (src: string): boolean => {
    const c = compareRule(src);
    const td = cellRule(src);
    return !!c && /overflow-x:\s*auto\b/.test(c) && /min-width:\s*0\b/.test(c)
      && !!td && /overflow-wrap:\s*anywhere\b/.test(td) && /white-space:\s*normal\b/.test(td)
      && phoneOk(src);
  };

  it('.gg-audited-compare scrolls inside itself (overflow-x: auto; min-width: 0); per-rule cells wrap anywhere', async () => {
    const src = await readCss();
    expect(compareRule(src)).toMatch(/overflow-x:\s*auto\b/);
    expect(compareRule(src)).toMatch(/min-width:\s*0\b/);
    expect(cellRule(src)).toMatch(/overflow-wrap:\s*anywhere\b/);
    expect(cellRule(src)).toMatch(/white-space:\s*normal\b/);
    expect(src).toMatch(/\.gg-audited-per-rule th\[scope='row'\]\s*\{[^}]*white-space:\s*normal/);
    expect(ok(src)).toBe(true);
  });

  it('📱 under 720 px every per-rule row stacks (tr, th and td display: block; no sideways scroll) — 2026-11-01', async () => {
    const src = await readCss();
    expect(phoneBlock(src)).not.toBeNull();
    expect(phoneOk(src)).toBe(true);
    expect(phoneBlock(src)).toMatch(/\.gg-audited-per-rule thead\s*\{[^}]*display:\s*none\b/);
  });

  it('NEGATIVE: a stylesheet that lost any one of the rules fails the same guard', async () => {
    const src = await readCss();
    const mutations = [
      src.replace(/(\.gg-audited-compare\s*\{[^}]*)overflow-x:\s*auto/, '$1overflow-x: visible'),
      src.replace(/(\.gg-audited-compare\s*\{[^}]*)min-width:\s*0/, '$1min-width: auto'),
      src.replace(/(\.gg-audited-per-rule td\s*\{[^}]*)overflow-wrap:\s*anywhere/, '$1overflow-wrap: normal'),
      src.replace(/(\.gg-audited-per-rule td\s*\{[^}]*)white-space:\s*normal/, '$1white-space: nowrap'),
      src.replace(/\.gg-audited-per-rule td\s*\{/, '.gg-audited-per-rule-gone td {'),
      // 📱 the phone block lost, or its rows back to table-row (the sideways scroll returns)
      src.replace(/@media \(max-width:\s*720px\)\s*\{[\s\S]*?\n\}\n/, ''),
      src.replace(/(@media \(max-width:\s*720px\)[\s\S]*?\.gg-audited-per-rule tr\s*\{[^}]*)display:\s*block/, '$1display: table-row'),
      src.replace(/(@media \(max-width:\s*720px\)[\s\S]*?\.gg-audited-per-rule td\s*\{[^}]*)min-width:\s*0/, '$1min-width: 9rem'),
    ];
    for (const m of mutations) {
      expect(m).not.toBe(src);
      expect(ok(m)).toBe(false);
    }
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

/* 🧪 2026-11-05 (gg-track-parity WP-C). Ajay: "Can you make both Gajjala's track record and Gajjalas 1 min and Gajjalas
 * AUDIT HAVE similar track record ... its hard to tell which ones won in Gajjlas Audit page"; trigger: "Why are the other
 * winners not having charts?". The 🧪 🏁 now serves 🚩's own A+ rows (audited_tab.track_block) with a served `audit`
 * cell under the served head "audit"; the FE draws it through TrRowCells' default branch (TrCell) — no new component.
 * Fixture: __fixtures__/gajjala_audited_track_2026_11_05.json — HAND-BUILT test data (spec §3.4) + tonight's served
 * 0-row block verbatim. Every assertion compares against a served string; nothing is composed. */
describe('🧪 🏁 — 🚩 A+ rows with the served 🧪 Audit cell (2026-11-05)', () => {
  const TRK: any = (trackFix as any).track_record;
  const TRK_EMPTY: any = (trackFix as any).track_record_empty;
  const rowsOf = (tr: any): any[] => tr.days.flatMap((d: any) => d.rows);
  const row = (sym: string, setup: string): any => rowsOf(TRK).find((r: any) => r.symbol === sym && r.setup === setup);
  const HELD_R = row('HUHU', 'reversal_squeeze');
  const PASSED_R = row('MERC', 'intraday_vcp');
  const NJ_R = row('CNSY', 'intraday_vcp');
  const LOSS_R = row('JDZG', 'reversal_squeeze');
  const DUP_R = row('JDZG', 'intraday_vcp');
  const trackBoard = (patch: (tr: any) => void = () => {}, tr: any = TRK) => {
    const b = ggaTrBoard(); b.track_record = clone(tr); patch(b.track_record); return b;
  };
  const open = async (q = '', patch: (tr: any) => void = () => {}, tr: any = TRK) => {
    stub({ gga: () => trackBoard(patch, tr) });
    const r = mount(`tab=gajjala_audited&sub=track_record${q}`, 'gajjala_audited');
    await loaded(r.container);
    return r;
  };
  const cellOf = (r: any) => screen.getByTestId(`gg-tr-audit-${r.key}`);

  it('fixture sanity: one held / passed / not_judged row, one duplicate, one pending row of today; counts / kinds null', () => {
    expect([HELD_R, PASSED_R, NJ_R, LOSS_R, DUP_R].every(Boolean)).toBe(true);
    expect(HELD_R.audit.state).toBe('held');
    expect(HELD_R.audit.sub_text).toBeNull();
    expect(PASSED_R.audit.state).toBe('passed');
    expect(typeof PASSED_R.audit.sub_text).toBe('string');
    expect(NJ_R.audit.state).toBe('not_judged');
    expect(DUP_R.dup_of).toBe(LOSS_R.id);
    expect(HELD_R.same.state).toBe('pending');
    expect(HELD_R.same.provisional).toBe(false);
    expect(TRK.counts_text).toBeNull();
    expect(TRK.kinds).toBeNull();
    expect(TRK.heads[1].key).toBe('audit');
    expect(TRK_EMPTY.days).toEqual([]);
  });

  it('order: the 🏁 section PRECEDES the compare block on the 🧪 🏁', async () => {
    await open();
    const tr = screen.getByTestId('gg-track-record');
    const cmp = screen.getByTestId('gg-audited-compare');
    expect(tr.compareDocumentPosition(cmp) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('every row: gg-tr-audit-<key> prints the served text verbatim, the served sub_text in <small>, the state class', async () => {
    await open();
    for (const r of rowsOf(TRK)) {
      const td = cellOf(r);
      expect(td.tagName).toBe('TD');
      expect(td.firstChild?.textContent).toBe(r.audit.text);
      expect(td.classList.contains('gg-tr-cell')).toBe(true);
      expect(td.classList.contains(`gg-tr-${r.audit.state}`)).toBe(true);
      expect(td.classList.contains('gg-tr-prov')).toBe(false);
      const small = td.querySelector('small');
      if (r.audit.sub_text) expect(small?.textContent).toBe(r.audit.sub_text);
      else expect(small).toBeNull();
      // NEGATIVE: nothing composed — the cell is exactly the served strings
      expect(leftover(td.textContent || '', [r.audit.text, r.audit.sub_text || ''].filter(Boolean))).toBe('');
    }
    expect(cellOf(PASSED_R).classList.contains('gg-tr-passed')).toBe(true);
    expect(cellOf(PASSED_R).querySelector('small')?.textContent).toBe(PASSED_R.audit.sub_text);
    expect(cellOf(NJ_R).classList.contains('gg-tr-not_judged')).toBe(true);
  });

  it('NEGATIVE: a held row renders NO <small> (ids only in the cell; the why sentences stay in the held list)', async () => {
    await open();
    for (const r of [HELD_R, LOSS_R, DUP_R]) {
      const td = cellOf(r);
      expect(td.classList.contains('gg-tr-held')).toBe(true);
      expect(td.querySelector('small')).toBeNull();
      expect(td.textContent).toBe(r.audit.text);
    }
  });

  it('heads: Ticker · Tape · 🧪 Audit · Setup … — the Tape <th> at index 1, the audit <th> at index 2', async () => {
    await open();
    expect(ggTrTapeAt(TRK.heads)).toBe(1);
    const sec = screen.getByTestId('gg-track-record');
    const ths = [...(sec.querySelector('.gg-tr-table thead tr') as HTMLElement).querySelectorAll('th')].map((th) => th.textContent);
    const labels = TRK.heads.map((h: any) => h.label);
    expect(ths).toEqual([labels[0], TRK.views.tape_head, ...labels.slice(1)]);
    expect(ths[1]).toBe(TRK.views.tape_head);
    expect(ths[2]).toBe(TRK.heads[1].label);
    // the row's cells ride the same order: the audit cell is the third <td>
    const tr = screen.getByTestId(`gg-tr-row-${PASSED_R.key}`);
    expect(tr.querySelectorAll(':scope > td')[2].getAttribute('data-testid')).toBe(`gg-tr-audit-${PASSED_R.key}`);
  });

  it('the 🕰️ timeline (?view=timeline) renders the same served cell', async () => {
    await open('&view=timeline');
    const tl = screen.getByTestId('gg-tl');
    for (const r of rowsOf(TRK)) {
      const td = within(tl).getByTestId(`gg-tr-audit-${r.key}`);
      expect(td.firstChild?.textContent).toBe(r.audit.text);
      expect(td.classList.contains(`gg-tr-${r.audit.state}`)).toBe(true);
    }
  });

  it('kinds / counts_text null: no 🎯 chips, no 🧠 count lines — while the entries line and the A+ charts render', async () => {
    await open();
    expect(screen.queryByTestId('gg-tr-kinds')).toBeNull();
    expect(screen.queryByTestId('gg-tr-kind-empty')).toBeNull();
    expect(screen.queryByTestId('gg-tr-counts-same')).toBeNull();
    expect(screen.queryByTestId('gg-tr-counts-next')).toBeNull();
    expect(screen.getByTestId('gg-tr-entries').textContent).toBe(TRK.entries_text);
    expect(screen.getByTestId('gg-ap')).toBeTruthy();
    expect(screen.getByTestId('gg-ap-chart-outcomes')).toBeTruthy();
    expect(screen.queryByTestId('gg-ap-empty')).toBeNull();
    expect(screen.getByTestId('gg-tr-title').textContent).toBe(TRK.title);
    expect(screen.getByTestId('gg-tr-honesty').textContent).toBe(TRK.honesty);
    // the ✅ / ❌ served chips over the rows
    expect(screen.getByTestId('gg-tr-cat-win').textContent).toBe(TRK.categories[1].text);
    expect(screen.getByTestId('gg-tr-cat-loss').textContent).toBe(TRK.categories[2].text);
  });

  it('the duplicate row keeps its 🔁 chip AND its audit cell; it serves no ✅ / ❌ flag', async () => {
    await open();
    expect(screen.getByTestId(`gg-tr-dup-${DUP_R.key}`).textContent).toBe(DUP_R.dup_text);
    expect(cellOf(DUP_R).textContent).toBe(DUP_R.audit.text);
    expect(screen.queryByTestId(`gg-tr-flag-${DUP_R.key}`)).toBeNull();
    expect(screen.getByTestId(`gg-tr-flag-${LOSS_R.key}`).textContent).toBe(LOSS_R.flag_text);
    expect(screen.getByTestId(`gg-tr-flag-${PASSED_R.key}`).textContent).toBe(PASSED_R.flag_text);
  });

  it('✅ wins first orders by the served bucket order; the audit cell rides its row; ?sort=rang = the served order', async () => {
    const day = TRK.days.find((d: any) => d.date === '2026-11-03');
    const keysIn = () => [...(screen.getByTestId('gg-tr-day-2026-11-03').parentElement as HTMLElement)
      .querySelectorAll('tbody tr[data-testid^="gg-tr-row-"]')].map((tr) => tr.getAttribute('data-testid'));
    await open();
    // served order: CNSY (out) · JDZG dup · JDZG loss → the loss first, then the out row, the duplicate last (ggSortRows)
    expect(day.rows.map((r: any) => r.key)).toEqual([NJ_R.key, DUP_R.key, LOSS_R.key]);
    expect(TRK.bucket_order.indexOf('loss')).toBeLessThan(TRK.bucket_order.indexOf('out'));
    expect(keysIn()).toEqual([LOSS_R, NJ_R, DUP_R].map((r: any) => `gg-tr-row-${r.key}`));
    expect(keysIn()).not.toEqual(day.rows.map((r: any) => `gg-tr-row-${r.key}`));
    for (const r of day.rows) {
      const tr = screen.getByTestId(`gg-tr-row-${r.key}`);
      expect(within(tr).getByTestId(`gg-tr-audit-${r.key}`).firstChild?.textContent).toBe(r.audit.text);
    }
    cleanup();
    await open('&sort=rang');
    expect(keysIn()).toEqual(day.rows.map((r: any) => `gg-tr-row-${r.key}`));
  });

  it("today's pending row prints the served 'not read yet' words, never a provisional mark; the served today line", async () => {
    await open();
    const same = screen.getByTestId(`gg-tr-same-${HELD_R.key}`);
    expect(same.firstChild?.textContent).toBe(HELD_R.same.text);
    expect(same.querySelector('small')?.textContent).toBe(HELD_R.same.sub_text);
    expect(same.classList.contains('gg-tr-pending')).toBe(true);
    expect(same.classList.contains('gg-tr-prov')).toBe(false);
    expect(screen.getByTestId('gg-tr-today').textContent).toBe(TRK.today_text);
    expect(screen.getByTestId('gg-track-record').querySelectorAll('.gg-tr-prov')).toHaveLength(0);
  });

  it('NEGATIVE: heads without "audit" → no gg-tr-audit-* even though every row carries `audit`', async () => {
    await open('', (tr) => { tr.heads = tr.heads.filter((h: any) => h.key !== 'audit'); });
    expect(document.querySelectorAll('[data-testid^="gg-tr-audit-"]')).toHaveLength(0);
    expect(screen.getByTestId(`gg-tr-row-${PASSED_R.key}`)).toBeTruthy();
    expect(screen.getByTestId('gg-track-record').textContent).not.toContain(PASSED_R.audit.text);
  });

  it('NEGATIVE: a row without `audit` (absent or null) under the head → an empty third cell, no audit test id, no crash', async () => {
    await open('', (tr) => { delete tr.days[0].rows[0].audit; tr.days[1].rows[0].audit = null; });
    for (const r of [HELD_R, PASSED_R]) {
      expect(screen.queryByTestId(`gg-tr-audit-${r.key}`)).toBeNull();
      const td = screen.getByTestId(`gg-tr-row-${r.key}`).querySelectorAll(':scope > td')[2];
      expect(td.textContent).toBe('');
      expect(td.className).toBe('');
    }
    // the other rows keep theirs
    expect(cellOf(NJ_R).firstChild?.textContent).toBe(NJ_R.audit.text);
  });

  it("NEGATIVE: tonight's served 0-row block renders its empty_text exactly as today — no row, no audit cell", async () => {
    await open('', () => {}, TRK_EMPTY);
    expect(screen.getByTestId('gg-tr-empty').textContent).toBe(TRK_EMPTY.empty_text);
    expect(document.querySelectorAll('[data-testid^="gg-tr-row-"]')).toHaveLength(0);
    expect(document.querySelectorAll('[data-testid^="gg-tr-audit-"]')).toHaveLength(0);
    expect(screen.getByTestId('gg-ap-empty').textContent).toBe(TRK_EMPTY.aplus.empty_text);
    // its served counts lines still print (the older block serves them)
    expect(screen.getByTestId('gg-tr-counts-same').textContent).toBe(TRK_EMPTY.counts_text.same);
    expect(screen.getByTestId('gg-tr-counts-next').textContent).toBe(TRK_EMPTY.counts_text.next);
  });

  it('NEGATIVE: an older block WITH counts_text still prints both served lines verbatim', async () => {
    const lines = { same: 'served same-session line · 1 · 2', next: 'served next-session line · 3 · 4' };
    await open('', (tr) => { tr.counts_text = { ...lines }; });
    expect(screen.getByTestId('gg-tr-counts-same').textContent).toBe(lines.same);
    expect(screen.getByTestId('gg-tr-counts-next').textContent).toBe(lines.next);
  });

  it('NEGATIVE: no number composed — the head row is exactly the served labels; no NaN / undefined anywhere', async () => {
    await open();
    const sec = screen.getByTestId('gg-track-record');
    const head = sec.querySelector('.gg-tr-table thead tr') as HTMLElement;
    expect(leftover(head.textContent || '', [...TRK.heads.map((h: any) => h.label), TRK.views.tape_head])).toBe('');
    expect(sec.textContent || '').not.toMatch(/undefined|null|NaN|\[object/);
  });

  it("NEGATIVE: 🚩 Gajjala's 🏁 is unchanged by the swap — no compare, no audit column, Setup third after the Tape", async () => {
    const g5 = () => { const b = clone(TR5D); b.session = { ...b.session, refresh_sec: 0 }; b.tab = 'gajjala'; return b; };
    stub({ gg5: g5 });
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    expect(getsTo(PA)).toHaveLength(0);
    expect(screen.getByTestId('gg-track-record')).toBeTruthy();
    expect(screen.queryByTestId('gg-audited-compare')).toBeNull();
    expect(document.querySelectorAll('[data-testid^="gg-tr-audit-"]')).toHaveLength(0);
    const ths = [...(container.querySelector('.gg-tr-table thead tr') as HTMLElement).querySelectorAll('th')].map((th) => th.textContent);
    expect(ths[0]).toBe(TR5D.track_record.heads[0].label);
    expect(ths[1]).toBe(TR5D.track_record.views.tape_head);
    expect(ths[2]).toBe(TR5D.track_record.heads[1].label);
    expect(TR5D.track_record.heads.some((h: any) => h.key === 'audit')).toBe(false);
  });

  it("NEGATIVE: the 1-minute 🏁 is unchanged by the swap — no compare, no audit column", async () => {
    const g1 = () => { const b = clone(TR5D); b.session = { ...b.session, refresh_sec: 0 }; b.tab = 'gajjala_1m'; return b; };
    stub({ gg1: g1 });
    const { container } = mount('tab=gajjala_1m&sub=track_record', 'gajjala_1m');
    await loaded(container);
    expect(getsTo(P1).length).toBeGreaterThan(0);
    expect(getsTo(PA)).toHaveLength(0);
    expect(screen.getByTestId('gg-track-record')).toBeTruthy();
    expect(screen.queryByTestId('gg-audited-compare')).toBeNull();
    expect(document.querySelectorAll('[data-testid^="gg-tr-audit-"]')).toHaveLength(0);
  });
});

/* 📱 the audit cell's CSS hooks (2026-11-05) — source guards on ggAudited.css; NEGATIVE: a lost hook fails the guard. */
describe('🧪 audit cell CSS hooks — ggAudited.css (2026-11-05)', () => {
  async function readCss(): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/src/styles/ggAudited.css`, 'utf8');
  }
  const hooksOk = (src: string): boolean =>
    /\.gg-tr-cell\.gg-tr-held\s*\{[^}]*color:/.test(src)
    && /\.gg-tr-cell\.gg-tr-passed\s*\{[^}]*color:/.test(src)
    && /\.gg-tr-cell\.gg-tr-not_judged,\s*\.gg-tr-cell\.gg-tr-not_read\s*\{[^}]*color:/.test(src)
    // 📱 the audit cell wraps (the 🏁 td is nowrap) — a passed row's exit line must never set the column width
    && /td\.gg-tr-cell\.gg-tr-not_read\s*\{[^}]*white-space:\s*normal\b[^}]*overflow-wrap:\s*anywhere\b[^}]*max-width:/.test(src);

  it('held / passed / not_judged / not_read each carry a colour hook; the audit cell wraps (📱)', async () => {
    expect(hooksOk(await readCss())).toBe(true);
  });

  it('NEGATIVE: a stylesheet that lost any one hook fails the guard', async () => {
    const src = await readCss();
    for (const m of [
      src.replace('.gg-tr-cell.gg-tr-held', '.gg-tr-cell.gg-tr-held-gone'),
      src.replace('.gg-tr-cell.gg-tr-passed', '.gg-tr-cell.gg-tr-passed-gone'),
      src.replace('.gg-tr-cell.gg-tr-not_read {', '.gg-tr-cell.gg-tr-not_read-gone {'),
      src.replace(/(td\.gg-tr-cell\.gg-tr-not_read\s*\{[^}]*)white-space:\s*normal/, '$1white-space: nowrap'),
      src.replace(/(td\.gg-tr-cell\.gg-tr-not_read\s*\{[^}]*)max-width:[^;]*;/, '$1'),
    ]) {
      expect(m).not.toBe(src);
      expect(hooksOk(m)).toBe(false);
    }
  });
});
