import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CurrentUser } from '../hooks/useUser';

/* 🏁 Track record on Gajjala's board (2026-10-16, BUILD_SPEC9 §3.11 / §4 WP-C).
 *
 * Ajay: "also can you track all Gajjals stocks and keep a new tab to show wins vs losses. To see a percentage and the
 * ticker." and "We are not looking for winners just in time but when they got in to our alerts if they made it or not.
 * Like XLAB today was a winner I made good money on it".
 *
 * Rendered from TWO sources: the in-file FIXTURE below (shaped exactly like the §3.8 served payload — test data, the
 * board prints whatever it is given) and, once backend tests/test_gajjala_track_record_tab.py has written it, the
 * GOLDEN (gajjala_track_record_golden_2026_10_16.json — the served payload, never typed; a missing file FAILS, never
 * skips). What is pinned: every cell / count / shadow / today / day line == the served string; the span buttons ==
 * the served spans and a click writes `?span=` that the next GET carries. NEGATIVES: no tile, no PatternChart, no room
 * POST (the only fetches: the GET, and the scan POST for an owner); an older payload without `track_record` → the served
 * empty note, no table; an empty ledger → the served empty text; no NaN / undefined / None / the b-word in the DOM;
 * every number in the panel is part of a served string (the panel composes none).
 *
 * ⏪ + ✅ / ❌ (2026-10-16 night, DECISIONS11 D5 / D11 / D12, AMENDMENTS11 F13). Ajay: "Would you be able to back test for
 * the past week from his alerts any way to do so? build a pre historic timeline or so?" and "I want winners and losers
 * category in his track record and would like us to study the losers". Pinned too: the ⏪ replayed line + its caveat
 * line == served (right under the 🎯 entries line) or absent; a row's ⏪ chip == its served replay_text; a ❌ row's
 * served loss_text as the sub-line right under it, on loss rows only; NEGATIVE no per-row ✅ / ❌ chip (F13); the
 * honesty line still LAST. */

let userRet: CurrentUser | null = null;
const roomCalls: string[][] = [];
const chartProps: any[] = [];
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({
  PatternChart: (props: any) => { chartProps.push(props); return <div data-testid={`chart-${props.tile.symbol}`} />; },
}));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: ({ symbol }: any) => <span data-testid={`short-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: (symbols: string[]) => {
    roomCalls.push([...(symbols || [])]);
    return { map: new Map(), payload: null, loading: false, error: null, pending: 0 };
  },
}));

import GajjalaBoard from './GajjalaBoard';

/* tsc-safe source / fixture reads (the GajjalaBoard.potential.test precedent). */
async function fsMod(): Promise<any> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  return mod?.default || mod;
}
const root = (globalThis as any).process?.cwd?.() || '.';
async function readSource(rel: string): Promise<string> {
  return (await fsMod()).readFileSync(`${root}/${rel}`, 'utf8');
}
async function readJsonIfPresent(rel: string): Promise<any | null> {
  const fs = await fsMod();
  const p = `${root}/${rel}`;
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null;
}
const GOLDEN: any = await readJsonIfPresent('src/components/__fixtures__/gajjala_track_record_golden_2026_10_16.json');
const clone = (x: any) => JSON.parse(JSON.stringify(x));

/* ---- the in-file FIXTURE: test data shaped like the §3.8 served payload (strings shaped like W1–W16). ---- */
const SUBS = [
  ['bull_flag', '\u{1F6A9}', 'Bull Flag'], ['kiss_fly', '\u{1F48B}', 'EMA Kiss & Fly'], ['horizontal_fade', '➖', 'Horizontal Fade'],
  ['intraday_vcp', '\u{1F300}', 'Intraday VCP'], ['reversal_squeeze', '\u{1F3BE}', 'Reversal Squeeze'],
  ['premarket', '☀️', 'Premarket'], ['postmarket', '\u{1F319}', 'Post-market'], ['playbook', '\u{1F4D3}', 'Playbook'],
  ['potential', '\u{1F9E0}', 'Potential'], ['track_record', '\u{1F3C1}', 'Track record'],
].map(([key, emoji, label]) => ({ key, emoji, label, count: key === 'track_record' ? 2 : 0 }));
const SPANS = [{ key: 'today', label: 'Today' }, { key: 'yesterday', label: 'Yesterday' },
               { key: '5d', label: 'Last 5 sessions' }, { key: 'all', label: 'All' }];
const HEADS = [{ key: 'symbol', label: 'Ticker' }, { key: 'setup', label: 'Setup' }, { key: 'at', label: 'Alert' },
               { key: 'kind', label: 'Kind' }, { key: 'plan', label: 'Trigger → fill · stop' },
               { key: 'same', label: 'Same session' }, { key: 'next', label: 'Through next session' }];
const cell = (state: string, text: string, sub_text: string | null, provisional = false) => ({ state, text, sub_text, provisional });
const row = (date: string, symbol: string, setup: string, setup_label: string, kind: string, line: string,
             kind_text: string, at_et: string, plan_text: string, same: any, next: any,
             extra: Record<string, unknown> = {}) => ({
  key: `${date}-${symbol}-${setup}-${kind}`, id: `${date}|${symbol}|${setup}|${kind}`, date, symbol, setup, setup_label,
  kind, line, kind_text, at_et, at_text: `${at_et} ET`, trigger: null, stop: null, fill_px: null, plan_text, note: null,
  href: `/chart-maps?tab=gajjala&sub=${setup}&focus=${symbol}`, same, next, rang_text: null, thin_text: null, ...extra,
});
const PENDING_NEXT = cell('pending', "after today's close", 'graded tonight 20:15 ET');
const D16 = { date: '2026-10-16', label: 'Fri 2026-10-16 · today', more_n: null, rows: [
  row('2026-10-16', 'XLAB', 'intraday_vcp', '\u{1F300} Intraday VCP', 'potential', 'live', '\u{1F9E0} live', '09:01',
      'trigger 1.85 → fill 1.89 at 09:45 · stop 1.75 · +1R 1.99',
      cell('win', 'WIN · best +103.2% so far', '+1R at 09:46 · not final', true), PENDING_NEXT,
      { trigger: 1.85, stop: 1.75, fill_px: 1.89, rang_text: 'rang pre' }),
  row('2026-10-16', 'XLAB', 'horizontal_fade', '➖ Horizontal Fade', 'potential', 'live', '\u{1F9E0} live', '08:51',
      'trigger 1.81 → fill 1.89 at 09:45 · stop 1.70 · +1R 2.00',
      cell('win', 'WIN · best +103.2% so far', '+1R at 09:46 · not final', true), PENDING_NEXT,
      { trigger: 1.81, stop: 1.7, fill_px: 1.89, note: 'trigger as first seen 08:49 ET (the ring was 08:51 ET)',
        rang_text: 'rang pre' }),
  row('2026-10-16', 'PMI', 'bull_flag', '\u{1F6A9} Bull Flag', 'aplus', 'shadow', 'A+ shadow — never sent', '10:05',
      'trigger 4.10 → fill 4.12 at 10:06 · stop 3.95 · +1R 4.29',
      cell('loss', 'LOSS · best +2.4% so far', 'stop at 10:20 · not final', true), PENDING_NEXT,
      { rang_text: 'rang RTH', bucket: 'loss', bucket_text: '❌ loser',
        loss_text: 'stopped 14 min after the fill · high +0.6R through the stop minute · filled 1 min after it rang' }),
  // E4: a thin-R row — its cell still reads WIN (state win) but the server counts it as thin, out of the %
  row('2026-10-16', 'THNR', 'bull_flag', '\u{1F6A9} Bull Flag', 'potential', 'live', '\u{1F9E0} live', '10:12',
      'trigger 3.00 → fill 3.00 at 10:13 · stop 2.99 · +1R 3.01',
      cell('win', 'WIN · best +4.0% so far', '+1R at 10:14 · not final', true), PENDING_NEXT,
      { trigger: 3, stop: 2.99, fill_px: 3, rang_text: 'rang RTH', thin_text: 'thin R' }),
  row('2026-10-16', 'TIE', 'kiss_fly', '\u{1F48B} EMA Kiss & Fly', 'potential', 'live', '\u{1F9E0} live', '10:30',
      'trigger 2.40 · stop 2.40', cell('no_risk', 'no risk', 'trigger = stop on the alert — no risk to size'),
      cell('no_risk', 'no risk', null), { rang_text: '', thin_text: '' }),
  row('2026-10-16', 'NOPL', 'reversal_squeeze', '\u{1F3BE} Reversal Squeeze', 'potential', 'live', '\u{1F9E0} live', '11:02',
      'no trigger or stop on the alert', cell('no_plan', 'no plan', null), cell('no_plan', 'no plan', null),
      { href: '//elsewhere.example/x', rang_text: undefined, thin_text: undefined }),
] };
const D15 = { date: '2026-10-15', label: 'Thu 2026-10-15', more_n: null, rows: [
  row('2026-10-15', 'XLAB', 'intraday_vcp', '\u{1F300} Intraday VCP', 'potential', 'live', '\u{1F9E0} live', '15:11',
      'trigger 1.22 → fill 1.22 at 15:21 · stop 1.16 · +1R 1.28',
      cell('win', 'WIN · best +14.8%', '+1R at 15:22 · close +9.0%'),
      cell('win', 'WIN · best +214.7%', '+1R at 15:22 · close +122.1%'),
      { trigger: 1.22, stop: 1.16, fill_px: 1.22, rang_text: 'rang AH' }),
  row('2026-10-15', 'QQQX', 'bull_flag', '\u{1F6A9} Bull Flag', 'potential', 'live', '\u{1F9E0} live', '13:40',
      'trigger 7.10 · stop 6.90', cell('no_entry', 'no entry', 'the trigger never traded'),
      cell('no_entry', 'no entry', 'the trigger never traded')),
  // ⏪ a replayed row (DECISIONS11 D5): its own line, its served chip; a WIN that never rang
  row('2026-10-15', 'RPL', 'reversal_squeeze', '\u{1F3BE} Reversal Squeeze', 'aplus', 'replayed', '⏪ A+ replayed', '10:35',
      'trigger 1.23 → fill 1.24 at 10:36 · stop 1.11 · +1R 1.35',
      cell('win', 'WIN · best +12.1%', '+1R at 10:50 · close +4.0%'), cell('pending', 'not graded (bars not cached)', null),
      { id: 'REPLAY:2026-10-15|RPL|reversal_squeeze', rang_text: 'rang RTH', replay_text: '⏪ replayed · 🎾 ungated',
        bucket: 'win', bucket_text: '✅ winner', loss_text: null }),
] };
const RULE = "GG's trade math (your answer, 2026-10-16). Entry = the trigger the alert gave. No entry and no plan are listed, never counted.";
const HONESTY = 'A ledger of the alerts as sent, graded by GG\'s own trade math — not a backtest of a strategy, and small n early.';
const block = (span: string, days: any[], over: Record<string, unknown> = {}) => ({
  title: "\u{1F3C1} Track record — every Gajjala alert that rang, graded by GG's trade math · UNMEASURED",
  rule_label: 'ⓘ how each alert is graded', rule_text: RULE, honesty: HONESTY, span, spans: SPANS, heads: HEADS,
  counts_text: { same: 'Same session: 3 wins · 0 losses · 100% won · 1 no entry · 0 open · 1 no plan · today not final',
                 next: 'Through next session: 1 win · 0 losses · 100% won · 1 no entry · 0 flat · 1 no plan · 2 not graded yet' },
  shadow_text: 'A+ shadow (never sent, not in the %): same session 0 wins · 1 loss · 0% won · 0 no entry · 0 open; '
    + 'through next session 0 wins · 0 losses · no graded entry yet · 0 flat',
  today_text: 'Today · through 12:25 ET · not final',
  replayed_text: "⏪ Replayed with today's detectors (never rang, not in any %): same session 1 win · 0 losses; through next session 0 wins · 0 losses",
  replayed_note: 'Replayed on the study’s same-day universe, no float gate, as-printed bars; these never rang.',
  days, more_text: null, empty_text: null, grade_at_et: '20:15', ...over,
});
const board = (tr: any) => ({
  tab: 'gajjala', sub: 'track_record', tf: '5m', subs: SUBS,
  session: { date: '2026-10-16', label: 'Fri 2026-10-16', refresh_sec: 0 },
  pass: { as_of_et: '12:25 ET', stale: false, warming: false },
  // NEGATIVE bait: tiles in the payload are never drawn on 🏁 (the tiles memo returns [] there)
  tiles: [{ symbol: 'XLAB', bars: [{ t: 1, o: 1, h: 1, l: 1, c: 1 }], href: '/x' }],
  note: 'UNMEASURED.', empty_note: null, rules_section: 'gajjala', track_record: tr,
});
const FIX: Record<string, any> = {
  '5d': board(block('5d', [D16, D15])),
  today: board(block('today', [D16])),
  yesterday: board(block('yesterday', [], {
    counts_text: { same: 'Same session: 0 wins · 0 losses · no graded entry yet · 0 no entry · 0 open',
                   next: 'Through next session: 0 wins · 0 losses · no graded entry yet · 0 no entry · 0 flat' },
    shadow_text: null, today_text: null, empty_text: 'No Gajjala alert rang on 2026-10-15.', replayed_text: null, replayed_note: null,
  })),
};
FIX.all = board(block('all', [D16, D15]));

/* The server's default span when no `?span=` rides is 5d (AMENDMENTS9 E2) — the stub answers that board. */
const DEFAULT_SPAN = '5d';

type Call = { method: string; path: string; span: string | null; sub: string | null };
let calls: Call[] = [];
function stub(boards: Record<string, any>, over?: (u: URL) => any) {
  calls = [];
  const spy = vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    const method = String(init?.method || 'GET').toUpperCase();
    calls.push({ method, path: u.pathname, span: u.searchParams.get('span'), sub: u.searchParams.get('sub') });
    if (u.pathname.endsWith('/chart-maps/gajjala/scan')) {
      return { ok: true, status: 200, json: async () => ({ state: 'closed', latest_at: null, text: 'served closed line' }) };
    }
    const b = over ? over(u) : boards[u.searchParams.get('span') || DEFAULT_SPAN] || boards[DEFAULT_SPAN];
    return { ok: true, status: 200, json: async () => clone(b) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const gets = () => calls.filter((c) => c.method === 'GET' && c.path.endsWith('/chart-maps/gajjala'));

let loc = { search: '' };
function Probe() {
  const l = useLocation();
  loc = { search: l.search };
  return null;
}
const mount = (q: string) => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /><Probe /></MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));

/** Every string anywhere in a served block. */
function servedStrings(x: unknown, out: string[] = []): string[] {
  if (typeof x === 'string') out.push(x);
  else if (Array.isArray(x)) x.forEach((v) => servedStrings(v, out));
  else if (x && typeof x === 'object') Object.values(x).forEach((v) => servedStrings(v, out));
  return out;
}
const NUM = /\d+(?:[.,:]\d+)*/g;
/** Whole-token check: every number the panel prints is a WHOLE number token of some served string
 *  (a substring check passed '5', '1.7' or '4.1' composed on the FE — critic, fix round 1). */
function numbersServed(root: HTMLElement, served: string[]) {
  const toks = new Set(served.join(' \u0000 ').match(NUM) || []);
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let seen = 0;
  for (let t = walk.nextNode(); t; t = walk.nextNode()) {
    for (const n of (t.textContent || '').match(NUM) || []) {
      seen += 1;
      expect(toks.has(n), `number ${n} (in "${t.textContent}") is not a token of any served string`).toBe(true);
    }
  }
  return seen;
}
const BANNED = /NaN|undefined|\bNone\b|\[object Object\]/;
/** The house-banned word for a reversal, built so this file never spells it (identifiers excepted). */
const BWORD = new RegExp(['b', 'ounce'].join(''), 'i');

const SOURCES: [string, Record<string, any> | null][] = [
  ['fixture', FIX],
  ['golden', GOLDEN ? (GOLDEN as any).boards : null],
];

beforeEach(() => { userRet = null; roomCalls.length = 0; chartProps.length = 0; calls = []; });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

for (const [name, BOARDS] of SOURCES) {
  describe(`GajjalaBoard — 🏁 Track record (${name})`, () => {
    const B = BOARDS as Record<string, any>;
    const spans = Object.keys(B || {}).filter((k) => B[k]?.track_record);

    // NEGATIVE: a missing / board-less golden FAILS (never a silent skip) — the backend golden test writes it
    it('the source exists and serves a 🏁 track_record on the default span', () => {
      if (name === 'golden') expect(GOLDEN).not.toBeNull();
      expect(BOARDS).not.toBeNull();
      expect(spans.length).toBeGreaterThan(0);
      expect(spans).toContain(DEFAULT_SPAN);
    });

    it('every served line, cell and head prints as served, rows in the SERVED order', async () => {
      for (const sp of spans) {
        stub(B);
        const { container, unmount } = mount(`tab=gajjala&sub=track_record&span=${sp}`);
        await loaded(container);
        const tr = B[sp].track_record;
        const sec = screen.getByTestId('gg-track-record');
        expect(screen.getByTestId('gg-tr-title').textContent).toBe(tr.title);
        expect(screen.getByTestId('gg-tr-counts-same').textContent).toBe(tr.counts_text.same);
        expect(screen.getByTestId('gg-tr-counts-next').textContent).toBe(tr.counts_text.next);
        if (tr.shadow_text) expect(screen.getByTestId('gg-tr-shadow').textContent).toBe(tr.shadow_text);
        else expect(screen.queryByTestId('gg-tr-shadow')).toBeNull();
        if (tr.today_text) expect(screen.getByTestId('gg-tr-today').textContent).toBe(tr.today_text);
        else expect(screen.queryByTestId('gg-tr-today')).toBeNull();
        const shownRows = within(sec).queryAllByTestId(/^gg-tr-row-/).map((r) => r.getAttribute('data-testid'));
        expect(shownRows).toEqual(tr.days.flatMap((d: any) => d.rows.map((r: any) => `gg-tr-row-${r.key}`)));
        for (const d of tr.days) {
          expect(screen.getByTestId(`gg-tr-day-${d.date}`).textContent).toBe(d.label);
          const table = screen.getByTestId(`gg-tr-day-${d.date}`).parentElement!.querySelector('table.gg-tr-table')!;
          expect([...table.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(tr.heads.map((h: any) => h.label));
          for (const r of d.rows) {
            const tr_el = screen.getByTestId(`gg-tr-row-${r.key}`);
            for (const col of ['same', 'next'] as const) {
              const td = screen.getByTestId(`gg-tr-${col}-${r.key}`);
              expect(td.textContent, `${r.key} ${col}`).toBe(r[col].text + (r[col].sub_text || ''));
              expect(td.className).toContain(`gg-tr-${r[col].state}`);
              expect(td.className.includes('gg-tr-prov')).toBe(!!r[col].provisional);
            }
            const kind = tr_el.querySelector('.gg-tr-kind')!;
            expect(kind.textContent).toBe(r.kind_text);
            expect(kind.className).toContain(`gg-tr-${r.line}`);
            // E1 / E4 chips: the served text exactly; null / absent / blank → no chip at all
            for (const [chip, val] of [['rang', r.rang_text], ['thin', r.thin_text], ['replay', r.replay_text]] as const) {
              const el = screen.queryByTestId(`gg-tr-${chip}-${r.key}`);
              if (typeof val === 'string' && val.trim()) {
                expect(el, `${r.key} ${chip}`).not.toBeNull();
                expect(el!.textContent).toBe(val);
                expect(el!.className).toContain('gg-tr-chip');
              } else expect(el, `${r.key} ${chip}`).toBeNull();
            }
            // NEGATIVE (AMENDMENTS11 F13): no per-row ✅ / ❌ chip — bucket_text stays served, never drawn
            expect(screen.queryByTestId(`gg-tr-bucket-${r.key}`), `${r.key} bucket chip`).toBeNull();
            // D12: a ❌ row's served loss facts are the sub-line right under it; every other row has none
            const loss = screen.queryByTestId(`gg-tr-loss-${r.key}`);
            if (typeof r.loss_text === 'string' && r.loss_text.trim()) {
              expect(r.bucket, `${r.key} loss_text on a non-loss row`).toBe('loss');
              expect(loss, `${r.key} loss line`).not.toBeNull();
              expect(loss!.textContent).toBe(r.loss_text);
              expect(loss!.getAttribute('colspan')).toBe(String(tr.heads.length));
              expect(loss!.closest('tr')!.className).toContain('gg-tr-sub');
              expect(loss!.closest('tr')!.previousElementSibling).toBe(tr_el);
            } else expect(loss, `${r.key} loss line`).toBeNull();
            const text = tr_el.textContent || '';
            for (const s of [r.symbol, r.setup_label, r.at_text, r.plan_text]) expect(text).toContain(s);
            if (r.note) expect(text).toContain(r.note);
          }
        }
        // ⏪ the replayed line + its caveat line: served or absent, right under the 🎯 entries line (else the shadow line)
        for (const [id, val] of [['gg-tr-replayed', tr.replayed_text], ['gg-tr-replayed-note', tr.replayed_note]] as const) {
          if (typeof val === 'string' && val) expect(screen.getByTestId(id).textContent, id).toBe(val);
          else expect(screen.queryByTestId(id), id).toBeNull();
        }
        if (tr.replayed_text) {
          const above = screen.queryByTestId('gg-tr-entries') || screen.queryByTestId('gg-tr-shadow');
          if (above) expect(above.nextElementSibling).toBe(screen.getByTestId('gg-tr-replayed'));
          if (tr.replayed_note) expect(screen.getByTestId('gg-tr-replayed').nextElementSibling).toBe(screen.getByTestId('gg-tr-replayed-note'));
        }
        if (tr.more_text) expect(screen.getByTestId('gg-tr-more').textContent).toBe(tr.more_text);
        else expect(screen.queryByTestId('gg-tr-more')).toBeNull();
        if (tr.rule_text) {
          const rule = screen.getByTestId('gg-tr-rule');
          expect(rule.tagName).toBe('DETAILS');
          expect(rule.querySelector('summary')!.textContent).toBe(tr.rule_label);
          expect(rule.textContent).toBe(`${tr.rule_label}${tr.rule_text}`);
        }
        if (tr.honesty) {
          expect(screen.getByTestId('gg-tr-honesty').textContent).toBe(tr.honesty);
          expect(sec.lastElementChild).toBe(screen.getByTestId('gg-tr-honesty'));     // the honesty line is LAST
        }
        unmount();
      }
    });

    it('span buttons == the served spans; a click writes ?span= and the next GET carries it', async () => {
      stub(B);
      const { container } = mount('tab=gajjala&sub=track_record');
      await loaded(container);
      // NEGATIVE: no `?span=` in the URL → the first GET carries none (the server picks its default)
      expect(gets()[0].span).toBeNull();
      const tr = B[DEFAULT_SPAN].track_record;
      const btns = within(screen.getByTestId('gg-track-record')).getAllByTestId(/^gg-tr-span-/);
      expect(btns.map((b) => b.getAttribute('data-testid'))).toEqual(tr.spans.map((s: any) => `gg-tr-span-${s.key}`));
      expect(btns.map((b) => b.textContent)).toEqual(tr.spans.map((s: any) => s.label));
      expect(btns.filter((b) => b.getAttribute('aria-selected') === 'true').map((b) => b.getAttribute('data-testid')))
        .toEqual([`gg-tr-span-${tr.span}`]);
      const pick = tr.spans.find((s: any) => s.key !== tr.span && B[s.key]) || tr.spans.find((s: any) => s.key !== tr.span);
      fireEvent.click(screen.getByTestId(`gg-tr-span-${pick.key}`));
      await waitFor(() => expect(new URLSearchParams(loc.search).get('span')).toBe(pick.key));
      await waitFor(() => expect(gets()[gets().length - 1].span).toBe(pick.key));
      expect(gets()[gets().length - 1].sub).toBe('track_record');
      if (B[pick.key]) {
        await waitFor(() => expect(screen.getByTestId(`gg-tr-span-${pick.key}`).getAttribute('aria-selected')).toBe('true'));
      }
      // NEGATIVE: a sub click drops the 🏁 span (it belongs to the sub it was picked on)
      fireEvent.click(screen.getByTestId('gg-sub-bull_flag'));
      await waitFor(() => expect(new URLSearchParams(loc.search).get('sub')).toBe('bull_flag'));
      expect(new URLSearchParams(loc.search).get('span')).toBeNull();
    });

    it('NEGATIVE: no tile, no PatternChart, no room POST — the only fetch is the GET (no owner)', async () => {
      stub(B);
      const { container } = mount('tab=gajjala&sub=track_record');
      await loaded(container);
      expect(container.querySelectorAll('[data-testid^="gg-tile-"]')).toHaveLength(0);
      expect(chartProps).toHaveLength(0);
      expect(roomCalls.length).toBeGreaterThan(0);
      for (const c of roomCalls) expect(c).toEqual([]);
      expect(calls.every((c) => c.method === 'GET' && c.path.endsWith('/chart-maps/gajjala'))).toBe(true);
      for (const id of ['gg-counts', 'gg-tf-5m', 'gg-tf-15m', 'gg-track', 'gg-playbook']) expect(screen.queryByTestId(id)).toBeNull();
    });

    it('NEGATIVE: an owner adds only the scan POST — still no room POST', async () => {
      userRet = { email: 'owner@example.com', display_name: 'Owner', given_name: 'Owner', picture: null,
                  is_default_user: false, is_admin: true };
      stub(B);
      const { container } = mount('tab=gajjala&sub=track_record');
      await loaded(container);
      await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true));
      for (const c of calls) {
        const ok = (c.method === 'GET' && c.path.endsWith('/chart-maps/gajjala'))
          || (c.method === 'POST' && c.path.endsWith('/chart-maps/gajjala/scan'));
        expect(ok, `${c.method} ${c.path}`).toBe(true);
      }
      expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1);
      for (const c of roomCalls) expect(c).toEqual([]);
    });

    it('NEGATIVE: no NaN / undefined / None / the b-word in the DOM; every panel number is in a served string', async () => {
      for (const sp of spans) {
        stub(B);
        const { container, unmount } = mount(`tab=gajjala&sub=track_record&span=${sp}`);
        await loaded(container);
        expect(container.innerHTML).not.toMatch(BANNED);
        expect(container.textContent || '').not.toMatch(BWORD);
        expect(numbersServed(screen.getByTestId('gg-track-record'), servedStrings(B[sp].track_record))).toBeGreaterThan(0);
        unmount();
      }
    });
  });
}

describe('GajjalaBoard — 🏁 Track record (fixture-only negatives)', () => {
  it('NEGATIVE: the number check is whole-token — an FE-composed count, raw stop or truncated decimal fails it', () => {
    const served = ['Same session: 15 wins · 2 losses · 88.2% won', '1.81 → 1.85 · stop 1.70', '08:51 ET'];
    const el = (txt: string) => { const d = document.createElement('div'); d.textContent = txt; return d; };
    for (const bad of ['5 rows', '7 alerts', '9', '1.7', '4.1', '8.2', '08:5']) {
      expect(() => numbersServed(el(bad), served), bad).toThrow();
    }
    expect(numbersServed(el('15 wins 88.2% 1.70 08:51 ET'), served)).toBe(4);
  });

  it('NEGATIVE: an older payload without `track_record` → the served empty note in gg-tr-empty, no table', async () => {
    const old = clone(FIX['5d']);
    delete old.track_record;
    old.empty_note = '\u{1F3C1} The alert record could not be read this time — the next re-read tries again.';
    stub(FIX, () => old);
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    expect(screen.getByTestId('gg-tr-empty').textContent).toBe(old.empty_note);
    expect(screen.getByTestId('gg-tr-empty').className).toContain('cm-note');
    expect(screen.queryByTestId('gg-track-record')).toBeNull();
    expect(container.querySelector('table')).toBeNull();
    expect(container.querySelectorAll('[data-testid^="gg-tile-"]')).toHaveLength(0);
  });

  it('NEGATIVE: no block and no served note → nothing at all (the panel types no fallback word)', async () => {
    const old = clone(FIX['5d']);
    delete old.track_record;
    stub(FIX, () => old);
    const { container } = mount('tab=gajjala&sub=track_record');
    await loaded(container);
    expect(screen.queryByTestId('gg-tr-empty')).toBeNull();
    expect(screen.queryByTestId('gg-track-record')).toBeNull();
  });

  it('NEGATIVE: an empty ledger → the served empty text, no row, no day table', async () => {
    stub(FIX);
    const { container } = mount('tab=gajjala&sub=track_record&span=yesterday');
    await loaded(container);
    const tr = FIX.yesterday.track_record;
    expect(screen.getByTestId('gg-tr-empty').textContent).toBe(tr.empty_text);
    expect(container.querySelector('table')).toBeNull();
    expect(screen.queryAllByTestId(/^gg-tr-row-/)).toHaveLength(0);
    expect(screen.getByTestId('gg-tr-counts-same').textContent).toBe(tr.counts_text.same);
    expect(screen.queryByTestId('gg-tr-shadow')).toBeNull();
    expect(screen.queryByTestId('gg-tr-today')).toBeNull();
  });

  it('the ticker links to the served card href; NEGATIVE a protocol-relative href prints the ticker unlinked', async () => {
    stub(FIX);
    const { container } = mount('tab=gajjala&sub=track_record&span=today');
    await loaded(container);
    const ok = screen.getByTestId('gg-tr-row-2026-10-16-XLAB-intraday_vcp-potential').querySelector('a')!;
    expect(ok.getAttribute('href')).toBe('/chart-maps?tab=gajjala&sub=intraday_vcp&focus=XLAB');
    expect(ok.textContent).toBe('XLAB');
    const bad = screen.getByTestId('gg-tr-row-2026-10-16-NOPL-reversal_squeeze-potential');
    expect(bad.querySelector('a')).toBeNull();
    expect(bad.querySelector('.gg-tr-sym')!.textContent).toBe('NOPL');
  });

  it('no_risk (AMENDMENTS9 E4) and no_plan cells print the served words with their CSS hook; shadow row dashed', async () => {
    stub(FIX);
    const { container } = mount('tab=gajjala&sub=track_record&span=today');
    await loaded(container);
    const nr = screen.getByTestId('gg-tr-same-2026-10-16-TIE-kiss_fly-potential');
    expect(nr.className).toContain('gg-tr-no_risk');
    expect(nr.textContent).toBe('no risk' + 'trigger = stop on the alert — no risk to size');
    // NEGATIVE: a null sub_text prints no <small> and no "null"
    const np = screen.getByTestId('gg-tr-next-2026-10-16-NOPL-reversal_squeeze-potential');
    expect(np.querySelector('small')).toBeNull();
    expect(np.textContent).toBe('no plan');
    const sh = screen.getByTestId('gg-tr-row-2026-10-16-PMI-bull_flag-aplus').querySelector('.gg-tr-kind')!;
    expect(sh.className).toContain('gg-tr-shadow');
    expect(sh.textContent).toBe('A+ shadow — never sent');
    // the deferred-ring note is printed as served, muted
    expect(screen.getByTestId('gg-tr-note-2026-10-16-XLAB-horizontal_fade-potential').textContent)
      .toBe('trigger as first seen 08:49 ET (the ring was 08:51 ET)');
  });

  it('E1 rang chip + E4 thin R chip print the served words; NEGATIVE null / absent / blank print no chip and no "null"', async () => {
    stub(FIX);
    const { container } = mount('tab=gajjala&sub=track_record&span=5d');
    await loaded(container);
    expect(screen.getByTestId('gg-tr-rang-2026-10-16-XLAB-intraday_vcp-potential').textContent).toBe('rang pre');
    expect(screen.getByTestId('gg-tr-rang-2026-10-16-PMI-bull_flag-aplus').textContent).toBe('rang RTH');
    expect(screen.getByTestId('gg-tr-rang-2026-10-15-XLAB-intraday_vcp-potential').textContent).toBe('rang AH');
    const thin = screen.getByTestId('gg-tr-thin-2026-10-16-THNR-bull_flag-potential');
    expect(thin.textContent).toBe('thin R');
    expect(thin.className).toContain('gg-tr-chip');
    expect(thin.closest('td')!.querySelector('.gg-tr-kind')!.textContent).toBe('\u{1F9E0} live');
    // the thin row's cell keeps its served WIN words — the chip is what marks it out of the %
    expect(screen.getByTestId('gg-tr-same-2026-10-16-THNR-bull_flag-potential').textContent)
      .toBe('WIN · best +4.0% so far' + '+1R at 10:14 · not final');
    // NEGATIVE: exactly one thin chip (only the served thin row), none on a non-thin WIN row
    expect(screen.queryAllByTestId(/^gg-tr-thin-/)).toHaveLength(1);
    expect(screen.queryByTestId('gg-tr-thin-2026-10-16-XLAB-intraday_vcp-potential')).toBeNull();
    // NEGATIVE: null (QQQX), absent (NOPL) and blank '' (TIE) → no chip, no "null"/"undefined" text
    for (const k of ['2026-10-15-QQQX-bull_flag-potential', '2026-10-16-NOPL-reversal_squeeze-potential',
                     '2026-10-16-TIE-kiss_fly-potential']) {
      expect(screen.queryByTestId(`gg-tr-rang-${k}`), k).toBeNull();
      expect(screen.queryByTestId(`gg-tr-thin-${k}`), k).toBeNull();
      const td = screen.getByTestId(`gg-tr-row-${k}`).querySelectorAll('td')[3];
      expect(td.querySelectorAll('.gg-tr-chip')).toHaveLength(0);
      expect(td.textContent).toBe('\u{1F9E0} live');
    }
    expect(container.textContent || '').not.toMatch(/\bnull\b|undefined/);
  });

  it('NEGATIVE: a no_time cell (E3) carries the muted gg-tr-no_time hook and the served words only', async () => {
    const b = clone(FIX.today);
    const r0 = b.track_record.days[0].rows[0];
    r0.same = { state: 'no_time', text: 'no alert time', sub_text: null, provisional: false };
    stub(FIX, () => b);
    const { container } = mount('tab=gajjala&sub=track_record&span=today');
    await loaded(container);
    const td = screen.getByTestId(`gg-tr-same-${r0.key}`);
    expect(td.className).toContain('gg-tr-no_time');
    expect(td.className).not.toContain('gg-tr-win');
    expect(td.textContent).toBe('no alert time');
    const css = await readSource('src/styles/gajjala.css');
    const muted = css.split('\n').find((l) => l.includes('.gg-tr-no_risk'))!;
    expect(muted).toContain('.gg-tr-no_time');
    expect(muted).not.toContain('.gg-tr-win');
  });

  it('⏪ a replayed row: its served kind words + chip; the ⏪ lines under the entries/shadow line; NEGATIVE none on other rows', async () => {
    stub(FIX);
    const { container } = mount('tab=gajjala&sub=track_record&span=5d');
    await loaded(container);
    const k = '2026-10-15-RPL-reversal_squeeze-aplus';
    const row = screen.getByTestId(`gg-tr-row-${k}`);
    expect(row.querySelector('.gg-tr-kind')!.textContent).toBe('⏪ A+ replayed');
    expect(row.querySelector('.gg-tr-kind')!.className).toContain('gg-tr-replayed');
    expect(screen.getByTestId(`gg-tr-replay-${k}`).textContent).toBe('⏪ replayed · 🎾 ungated');
    expect(screen.getByTestId(`gg-tr-replay-${k}`).className).toContain('gg-tr-chip');
    expect(screen.queryAllByTestId(/^gg-tr-replay-/)).toHaveLength(1);
    expect(screen.getByTestId('gg-tr-replayed').textContent).toBe(FIX['5d'].track_record.replayed_text);
    expect(screen.getByTestId('gg-tr-replayed-note').textContent).toBe(FIX['5d'].track_record.replayed_note);
    expect(screen.getByTestId('gg-tr-shadow').nextElementSibling).toBe(screen.getByTestId('gg-tr-replayed'));
    // NEGATIVE: the ⏪ line never moves the count lines (they print the served strings as before)
    expect(screen.getByTestId('gg-tr-counts-same').textContent).toBe(FIX['5d'].track_record.counts_text.same);
    // NEGATIVE: a winner serves no loss line; no bucket chip anywhere (F13)
    expect(screen.queryByTestId(`gg-tr-loss-${k}`)).toBeNull();
    expect(screen.queryAllByTestId(/^gg-tr-bucket-/)).toHaveLength(0);
    expect(screen.getByTestId('gg-track-record').lastElementChild).toBe(screen.getByTestId('gg-tr-honesty'));
  });

  it('NEGATIVE: a span without the ⏪ line prints no replayed line / note; a blank replay_text prints no chip', async () => {
    const b = clone(FIX['5d']);
    b.track_record.replayed_text = null;
    b.track_record.replayed_note = '';
    const r = b.track_record.days[1].rows.find((x: any) => x.symbol === 'RPL');
    r.replay_text = '  ';
    stub(FIX, () => b);
    const { container } = mount('tab=gajjala&sub=track_record&span=5d');
    await loaded(container);
    expect(screen.queryByTestId('gg-tr-replayed')).toBeNull();
    expect(screen.queryByTestId('gg-tr-replayed-note')).toBeNull();
    expect(screen.queryAllByTestId(/^gg-tr-replay-/)).toHaveLength(0);
    expect(container.textContent || '').not.toMatch(/\bnull\b|undefined/);
  });

  it('❌ the served loss facts sit right under the loser row, spanning the served heads; NEGATIVE a blank loss_text → no line', async () => {
    stub(FIX);
    const { container, unmount } = mount('tab=gajjala&sub=track_record&span=today');
    await loaded(container);
    const k = '2026-10-16-PMI-bull_flag-aplus';
    const td = screen.getByTestId(`gg-tr-loss-${k}`);
    expect(td.textContent).toBe('stopped 14 min after the fill · high +0.6R through the stop minute · filled 1 min after it rang');
    expect(td.closest('tr')!.previousElementSibling).toBe(screen.getByTestId(`gg-tr-row-${k}`));
    expect(screen.queryAllByTestId(/^gg-tr-loss-/)).toHaveLength(1);
    unmount();
    const b = clone(FIX.today);
    b.track_record.days[0].rows.find((x: any) => x.symbol === 'PMI').loss_text = ' ';
    stub(FIX, () => b);
    const r2 = mount('tab=gajjala&sub=track_record&span=today');
    await loaded(r2.container);
    expect(screen.queryAllByTestId(/^gg-tr-loss-/)).toHaveLength(0);
    expect(r2.container.querySelector('tr.gg-tr-sub')).toBeNull();
  });

  it('NEGATIVE: the 🏁 panel source composes no number and types no percent (the contract regex)', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    for (const fn of ['TrackRecordPanel', 'TrRowCells', 'TrCell']) {
      const at = src.indexOf(`function ${fn}(`);
      expect(at, fn).toBeGreaterThan(0);
      const next = src.indexOf('\nfunction ', at + 10);
      const body = src.slice(at, next < 0 ? undefined : next);
      expect(body, fn).not.toMatch(/toFixed|changeText\(|riskText\(|pxText\(|Math\.|%/);
      expect(body, fn).not.toMatch(/\brow\.(trigger|stop|fill_px)\b|\{[\w.?]*\.length\s*\}/);
      // the E1 / E3 / E4 words are SERVED — the panel never types them
      const code = body.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
      expect(code, fn).not.toMatch(/rang (pre|RTH|AH)|thin R|no alert time|no risk|['"`](WIN|LOSS)/);
      // ⏪ / ✅ ❌ words are SERVED too (DECISIONS11 D5 / D11 / D12)
      expect(code, fn).not.toMatch(/winner|loser|never rang|min after/i);
    }
    for (const id of ['gg-track-record', 'gg-tr-counts-same', 'gg-tr-counts-next']) {
      expect(src).toContain(`data-testid="${id}"`);
    }
  });
});
