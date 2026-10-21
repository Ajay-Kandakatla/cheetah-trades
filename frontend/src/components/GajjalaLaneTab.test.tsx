/* GajjalaLaneTab — the 🚩 Gajjala paper lane tab on /trading (2026-10-20).
 *
 * Ajay: "in the autopilot can you stop rest of the strategies and only use the
 * Gajjalas strategies please." A real-money trader reads this tab and it
 * carries three writes, so: every number-bearing sentence on it is the served
 * string (the fixture below is BUILD_SPEC17 §2 verbatim), ON → OFF is one
 * click and POSTs exactly {gajjala_entry: false}, OFF → ON asks first, waiving
 * the house floors asks first with the SERVED confirm text and Cancel sends
 * nothing, Close posts only after the confirm and only on a closable row, an
 * empty day says the served words, 403 says "Owner only.", nulls print "—"
 * (never NaN), the poll stops on unmount, and the source types none of the
 * lane's numbers and never the b-word. */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import {
  GajjalaLaneTab, POLL_MS, OWNER_ONLY_TEXT, LOAD_ERR_PREFIX, FLOORS_WAIVED_CHIP, DASH, served, GG_RULE_KEYS, ggRulesOf,
} from './GajjalaLaneTab';
import type { GajjalaPayload, GajjalaRow, GajjalaRules } from './GajjalaLaneTab';

/* BUILD_SPEC17 §2 — GET /trading/gajjala, verbatim. */
const FIXTURE: GajjalaPayload = {"date":"2026-10-20","armed":true,"mode":"paper","as_of":"2026-10-20T15:02:11Z",
 "status":{"strategy":"gajjala","enabled":true,"paper":true,"floors":"house",
  "floors_text":"House safety floors ON for this lane: share price ≥ $2.00 and a known market cap ≥ $700M. Most of his names sit under them, so most alerts are skipped and counted.",
  "floors_flip":"POST /trading/config {\"gajjala_floors\": false}",
  "floors_off_confirm_text":"Turn the house floors off for the 🚩 lane? Names under $2 and small caps will trade on paper.",
  "skipped_floor_today":1,"skipped_floor_text":"1 skipped by the floors today",
  "skipped_today":{"floor":1},"entries_today":2,"max_per_day":3,"open_n":1,"max_open":3,
  "caps_text":"2 of 3 entries today · 1 of 3 open","window":"09:45–15:30 ET","flatten_at":"15:55 ET",
  "settings":{"risk_pct":0.5,"max_notional_pct":10.0,"max_entries_per_day":3,"max_open":3,"signal_max_age_min":20,
   "chase_pct":0.5,"fill_wait_sec":180,"max_round_r_pct":10.0,"r_mult":1.0,"min_r_pct":0.5},
  "rules":["<RULES[0..6] §3.1, composed>"],
  "unmeasured_text":"UNMEASURED — the study of his five setups read no edge; this lane trades them on paper so the fills can be read, not because they are measured.",
  "streak_text":"The engine's losing-streak size cut is not applied here: every alert risks the same 0.5% so the fills stay comparable with the 🏁 Track record.",
  "track_record_text":"🏁 Track record grades the same alerts by GG's math — compare the fills there.",
  "track_record_url":"/chart-maps?tab=gajjala&sub=track_record",
  "empty_today_text":"No 🚩 A+ entry has reached your phone today — the lane waits for one.",
  "disabled_text":null,"live_text":null},
 "today":[
  {"id":"GG:2026-10-20|SAIQ|bull_flag","symbol":"SAIQ","setup":"bull_flag","setup_label":"🚩 Bull Flag","alert_et":"10:52",
   "trigger":4.46,"stop":4.31,"r":0.15,"r_pct":3.3632,"state":"open","skip_kind":null,"why":null,
   "entry":4.51,"target":4.66,"qty":2217,"risk_usd":443.4,"notional":9998.67,"fill_px":4.49,"fill_et":"10:53",
   "exit_px":null,"exit_et":null,"exit_kind":null,"pnl_usd":133.02,"r_mult":null,"last":4.55,
   "fate_text":"filled 2,217 @ 4.49 at 10:53 ET · target 4.66 · stop 4.31","pnl_text":"+$133.02 open (last 4.55)",
   "floors":"house","floor_warnings":["market cap unknown — the size floor could not be checked"],"broker_text":null,
   "url":"/chart-maps?tab=gajjala&sub=bull_flag&focus=SAIQ","closable":true},
  {"id":"GG:2026-10-20|DRMA|intraday_vcp","symbol":"DRMA","setup":"intraday_vcp","setup_label":"🌀 Intraday VCP","alert_et":"11:05",
   "trigger":0.8744,"stop":0.861,"r":0.0134,"r_pct":1.5325,"state":"skipped","skip_kind":"floor",
   "why":"house safety floors: share price $0.88 is under the $2.00 penny floor — thin quotes are where the tape games live",
   "entry":0.8834,"target":0.8968,"qty":11319,"risk_usd":253.55,"notional":9999.2,"fill_px":null,"fill_et":null,
   "exit_px":null,"exit_et":null,"exit_kind":null,"pnl_usd":null,"r_mult":null,"last":0.879,
   "fate_text":"skipped — house safety floors: share price $0.88 is under the $2.00 penny floor — thin quotes are where the tape games live",
   "pnl_text":null,"floors":"house","floor_warnings":[],"broker_text":null,"url":"/chart-maps?tab=gajjala&sub=intraday_vcp&focus=DRMA","closable":false},
  {"id":"GG:2026-10-20|JBDI|kiss_fly","symbol":"JBDI","setup":"kiss_fly","setup_label":"💋 EMA Kiss & Fly","alert_et":"11:20",
   "trigger":2.48,"stop":2.4,"r":0.08,"r_pct":3.2258,"state":"closed","skip_kind":null,"why":null,"entry":2.51,"target":2.59,
   "qty":3984,"risk_usd":438.24,"notional":9999.84,"fill_px":2.49,"fill_et":"11:21","exit_px":2.59,"exit_et":"11:31",
   "exit_kind":"target","pnl_usd":398.4,"r_mult":1.25,"last":null,
   "fate_text":"target 2.59 at 11:31 ET · +$398.40 · +1.25R","pnl_text":"+$398.40 · +1.25R","floors":"house",
   "floor_warnings":[],"broker_text":null,"url":"/chart-maps?tab=gajjala&sub=kiss_fly&focus=JBDI","closable":false}],
 "recent":[],
 "journal":{"n":2,"closed":1,"wins":1,"losses":0,"flat":0,"unfilled":0,"win_rate_pct":100.0,"pnl_usd":398.4,"avg_r":1.25,
  "text":"1 closed · 1 target · 0 stop · 0 flat · P&L +$398.40 · avg +1.25R · 0 not filled"}};

type Call = { url: string; init?: RequestInit };
type Resp = { ok: boolean; status: number; body: unknown };

function stub(get: Resp | (() => Resp), calls: Call[], postResp: Resp = { ok: true, status: 200, body: { ok: true } }) {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    const r = init?.method === 'POST' ? postResp : typeof get === 'function' ? get() : get;
    return Promise.resolve({ ok: r.ok, status: r.status, json: async () => r.body });
  }));
}
const ok = (body: GajjalaPayload): Resp => ({ ok: true, status: 200, body });
const posts = (calls: Call[]) => calls.filter((c) => c.init?.method === 'POST');
const gets = (calls: Call[]) => calls.filter((c) => c.init?.method !== 'POST');
const withStatus = (patch: Partial<NonNullable<GajjalaPayload['status']>>, extra: Partial<GajjalaPayload> = {}): GajjalaPayload =>
  ({ ...FIXTURE, ...extra, status: { ...FIXTURE.status!, ...patch } });
const view = (onChanged?: () => void) => render(<MemoryRouter><GajjalaLaneTab onChanged={onChanged} /></MemoryRouter>);
const rowOf = (sym: string) => document.querySelector(`[data-row-id^="GG:2026-10-20|${sym}|"]`) as HTMLElement;

beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('served()', () => {
  it('prints a served string as-is and "—" for null / undefined / blank (negative)', () => {
    expect(served('x')).toBe('x');
    expect(served(null)).toBe(DASH);
    expect(served(undefined)).toBe(DASH);
    expect(served('  ')).toBe(DASH);
  });
});

describe('GajjalaLaneTab — the served payload', () => {
  it('renders every served line, the Today rows and the journal; never NaN / null', async () => {
    const calls: Call[] = [];
    stub(ok(FIXTURE), calls);
    view();
    const s = FIXTURE.status!;
    expect(await screen.findByText(s.caps_text!)).toBeTruthy();
    expect(calls[0].url).toMatch(/\/trading\/gajjala$/);
    expect(calls[0].init?.credentials).toBe('include');
    for (const t of [s.floors_text!, s.floors_flip!, s.skipped_floor_text!, s.unmeasured_text!, s.streak_text!,
                     (s.rules as string[])[0], FIXTURE.journal!.text!]) {
      expect(screen.getByText(t)).toBeTruthy();
    }
    const track = screen.getByTestId('gg-lane-track');
    expect(track.textContent).toBe(s.track_record_text);
    expect(track.getAttribute('href')).toBe(s.track_record_url);
    for (const row of FIXTURE.today!) {
      const tr = rowOf(row.symbol);
      expect(within(tr).getByText(row.setup_label!)).toBeTruthy();
      expect(within(tr).getByText(row.alert_et!)).toBeTruthy();
      expect(within(tr).getByTestId('gg-lane-fate').textContent).toBe(row.fate_text);
      expect(within(tr).getByRole('link', { name: row.symbol }).getAttribute('href')).toBe(row.url);
    }
    expect(within(rowOf('SAIQ')).getByTestId('gg-lane-pnl').textContent).toBe('+$133.02 open (last 4.55)');
    expect(within(rowOf('JBDI')).getByTestId('gg-lane-pnl').textContent).toBe('+$398.40 · +1.25R');
    // NEGATIVE: a null pnl_text prints "—", never "null".
    expect(within(rowOf('DRMA')).getByTestId('gg-lane-pnl').textContent).toBe(DASH);
    expect(document.body.textContent).not.toMatch(/NaN|null|undefined/);
    expect(screen.queryByTestId('gg-lane-live')).toBeNull();
    expect(screen.queryByTestId('gg-lane-disabled')).toBeNull();
  });

  it('NEGATIVE: a row whose served texts are null prints "—" in each cell', async () => {
    const bare: GajjalaRow = { id: 'GG:2026-10-20|XYZ|bull_flag', symbol: 'XYZ', setup_label: null, alert_et: null,
                               fate_text: null, pnl_text: null, url: null, closable: null };
    stub(ok({ ...FIXTURE, today: [bare] }), []);
    view();
    const tr = await waitFor(() => { const r = rowOf('XYZ'); if (!r) throw new Error('no row'); return r; });
    expect(within(tr).getAllByText(DASH).length).toBeGreaterThanOrEqual(4);
    expect(within(tr).queryByRole('link')).toBeNull();
    expect(within(tr).queryByRole('button', { name: 'Close' })).toBeNull();
    expect(tr.textContent).not.toMatch(/NaN|null|undefined/);
  });

  it('"floors waived" chip only on a floors gg row; the broker_text chip when served (negative first)', async () => {
    stub(ok(FIXTURE), []);
    const r1 = view();
    await screen.findByText(FIXTURE.status!.caps_text!);
    expect(screen.queryByText(FLOORS_WAIVED_CHIP)).toBeNull();        // every fixture row is house
    expect(screen.queryByTestId('gg-lane-broker')).toBeNull();
    r1.unmount();
    const today = FIXTURE.today!.map((r) => (r.symbol === 'DRMA' ? { ...r, floors: 'gg', broker_text: '🚫 not eligible at Fidelity' } : r));
    stub(ok({ ...FIXTURE, today }), []);
    view();
    await screen.findByText(FIXTURE.status!.caps_text!);
    expect(within(rowOf('DRMA')).getByTestId('gg-lane-waived').textContent).toBe(FLOORS_WAIVED_CHIP);
    expect(within(rowOf('DRMA')).getByTestId('gg-lane-broker').textContent).toBe('🚫 not eligible at Fidelity');
    expect(within(rowOf('SAIQ')).queryByTestId('gg-lane-waived')).toBeNull();
    expect(within(rowOf('JBDI')).queryByTestId('gg-lane-waived')).toBeNull();
    expect(screen.getAllByTestId('gg-lane-waived')).toHaveLength(1);
  });
});

describe('GajjalaLaneTab — the lane switch', () => {
  it('ON → OFF is one click and POSTs exactly {gajjala_entry: false}', async () => {
    const calls: Call[] = [];
    const onChanged = vi.fn();
    stub(ok(FIXTURE), calls);
    view(onChanged);
    const btn = await screen.findByRole('button', { name: 'Lane ON — turn off' });
    expect(btn.getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(btn);
    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    expect(posts(calls)[0].url).toMatch(/\/trading\/config$/);
    expect(JSON.parse(String(posts(calls)[0].init?.body))).toEqual({ gajjala_entry: false });
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it('OFF → ON asks first; No sends nothing (negative); Yes sends {gajjala_entry: true}', async () => {
    const calls: Call[] = [];
    stub(ok(withStatus({ enabled: false })), calls);
    view();
    fireEvent.click(await screen.findByRole('button', { name: 'Lane OFF — turn on' }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Turn the Gajjala lane on?' })).getByRole('button', { name: 'No' }));
    expect(posts(calls)).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Lane OFF — turn on' }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Turn the Gajjala lane on?' })).getByRole('button', { name: 'Yes, on' }));
    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    expect(JSON.parse(String(posts(calls)[0].init?.body))).toEqual({ gajjala_entry: true });
  });
});

describe('GajjalaLaneTab — the floors switch', () => {
  it('ON → OFF asks with the SERVED confirm text; Cancel sends nothing (negative); Yes sends {gajjala_floors: false}', async () => {
    const calls: Call[] = [];
    stub(ok(FIXTURE), calls);
    view();
    const btn = await screen.findByRole('button', { name: 'House floors ON — waive for this lane' });
    expect(btn.getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(btn);
    expect(posts(calls)).toHaveLength(0);                                 // a click alone sends nothing
    const dlg = screen.getByRole('dialog', { name: 'Turn the house floors off for the Gajjala lane?' });
    expect(dlg.textContent).toContain(FIXTURE.status!.floors_off_confirm_text!);
    fireEvent.click(within(dlg).getByRole('button', { name: 'Cancel' }));
    expect(posts(calls)).toHaveLength(0);
    expect(screen.queryByRole('dialog', { name: 'Turn the house floors off for the Gajjala lane?' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'House floors ON — waive for this lane' }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Turn the house floors off for the Gajjala lane?' })).getByRole('button', { name: 'Yes, waive them' }));
    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    expect(posts(calls)[0].url).toMatch(/\/trading\/config$/);
    expect(JSON.parse(String(posts(calls)[0].init?.body))).toEqual({ gajjala_floors: false });
  });

  it('OFF → ON is one click and POSTs exactly {gajjala_floors: true}; no confirm dialog (negative)', async () => {
    const calls: Call[] = [];
    stub(ok(withStatus({ floors: 'gg', floors_text: 'House safety floors OFF for this lane (your switch).', floors_flip: 'POST /trading/config {"gajjala_floors": true}' })), calls);
    view();
    const btn = await screen.findByRole('button', { name: 'House floors OFF — turn back on' });
    expect(btn.getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByText('POST /trading/config {"gajjala_floors": true}')).toBeTruthy();
    fireEvent.click(btn);
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    expect(JSON.parse(String(posts(calls)[0].init?.body))).toEqual({ gajjala_floors: true });
  });
});

describe('GajjalaLaneTab — close now', () => {
  it('only the closable row has a Close button (negative for the others)', async () => {
    stub(ok(FIXTURE), []);
    view();
    await screen.findByText(FIXTURE.status!.caps_text!);
    expect(screen.getAllByRole('button', { name: 'Close' })).toHaveLength(1);
    expect(within(rowOf('SAIQ')).getByRole('button', { name: 'Close' })).toBeTruthy();
    expect(within(rowOf('DRMA')).queryByRole('button', { name: 'Close' })).toBeNull();
    expect(within(rowOf('JBDI')).queryByRole('button', { name: 'Close' })).toBeNull();
  });

  it('Close posts /trading/gajjala/close/SAIQ only after the confirm (negative first: No sends nothing)', async () => {
    const calls: Call[] = [];
    stub(ok(FIXTURE), calls);
    view();
    fireEvent.click(await screen.findByRole('button', { name: 'Close' }));
    expect(posts(calls)).toHaveLength(0);
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Close SAIQ Gajjala?' })).getByRole('button', { name: 'No' }));
    expect(posts(calls)).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Close SAIQ Gajjala?' })).getByRole('button', { name: 'Yes' }));
    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    expect(posts(calls)[0].url).toMatch(/\/trading\/gajjala\/close\/SAIQ$/);
    expect(posts(calls)[0].init?.body).toBeUndefined();
  });

  it('a refused close shows the served detail', async () => {
    const calls: Call[] = [];
    stub(ok(FIXTURE), calls, { ok: false, status: 400, body: { detail: 'engine not armed' } });
    view();
    fireEvent.click(await screen.findByRole('button', { name: 'Close' }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Close SAIQ Gajjala?' })).getByRole('button', { name: 'Yes' }));
    expect(await screen.findByText('engine not armed')).toBeTruthy();
  });

  it('NEGATIVE: a disarmed engine disables Close', async () => {
    stub(ok({ ...FIXTURE, armed: false }), []);
    view();
    const btn = await screen.findByRole('button', { name: 'Close' });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('GajjalaLaneTab — empty, banners, failures', () => {
  it('an empty day prints the served empty_today_text', async () => {
    stub(ok({ ...FIXTURE, today: [] }), []);
    view();
    expect(await screen.findByText(FIXTURE.status!.empty_today_text!)).toBeTruthy();
    expect(screen.queryByTestId('gg-lane-today')).toBeNull();
  });

  it('live_text and disabled_text render as banners only when served (negative: null → no banner)', async () => {
    const live = 'Live broker detected — the 🚩 Gajjala lane is paper-only and stays idle.';
    const off = 'Lane switched off — POST /trading/config {"gajjala_entry": true} turns it on.';
    stub(ok(withStatus({ live_text: live, paper: false }, { mode: 'live' })), []);
    const r1 = view();
    expect((await screen.findByTestId('gg-lane-live')).textContent).toBe(live);
    expect(screen.queryByTestId('gg-lane-disabled')).toBeNull();
    r1.unmount();
    stub(ok(withStatus({ disabled_text: off, enabled: false })), []);
    view();
    expect((await screen.findByTestId('gg-lane-disabled')).textContent).toBe(off);
    expect(screen.queryByTestId('gg-lane-live')).toBeNull();
  });

  it('a failed load says so; 403 says "Owner only." and shows no switch (negative)', async () => {
    stub({ ok: false, status: 500, body: {} }, []);
    const r1 = view();
    expect(await screen.findByText(`${LOAD_ERR_PREFIX}HTTP 500`)).toBeTruthy();
    r1.unmount();
    stub({ ok: false, status: 403, body: { detail: 'owner only' } }, []);
    view();
    expect(await screen.findByText(OWNER_ONLY_TEXT)).toBeTruthy();
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.queryByText(/Could not load/)).toBeNull();
  });
});

describe('GajjalaLaneTab — the poll', () => {
  it('re-reads every POLL_MS and stops on unmount', async () => {
    const calls: Call[] = [];
    stub(ok(FIXTURE), calls);
    const r = view();
    await screen.findByText(FIXTURE.status!.caps_text!);
    expect(gets(calls)).toHaveLength(1);
    await act(async () => { vi.advanceTimersByTime(POLL_MS); });
    await waitFor(() => expect(gets(calls)).toHaveLength(2));
    await act(async () => { vi.advanceTimersByTime(POLL_MS / 2); });
    expect(gets(calls)).toHaveLength(2);                                   // NEGATIVE: not before the next tick
    r.unmount();
    await act(async () => { vi.advanceTimersByTime(POLL_MS * 3); });
    expect(gets(calls)).toHaveLength(2);                                   // NEGATIVE: nothing after unmount
  });
});

describe('GajjalaLaneTab — source guard', () => {
  it('types none of the lane numbers, no book, never the b-word (with self-tests)', async () => {
    const src = (await import('./GajjalaLaneTab.tsx?raw')).default as string;
    const TYPED = /15:55|0\.5%|09:45/;
    const BWORD = /boun/i;
    const BOOK = /TLSW|TTLAC|Minervini p\./;
    expect(src).not.toMatch(TYPED);
    expect(src).not.toMatch(BWORD);
    expect(src).not.toMatch(BOOK);
    // NEGATIVE self-tests: the guards do catch a typed number / the word / a book.
    expect(`${src}\nflat by 15:55 ET`).toMatch(TYPED);
    expect(`${src}\nrisk 0.5% a trade`).toMatch(TYPED);
    expect('a reversal bounce').toMatch(BWORD);
    expect('TLSW p.312').toMatch(BOOK);
    expect(src).toContain('export const POLL_MS = 60_000');
  });
});


/* BUILD_SPEC19 D14 — status.rules v2 (an object), the served words as WP-A composes them from its constants
 * (GAJJALA_RISK_PCT 0.25, GG_BE_AFTER_BARS 3, flatten_at 15:55 ET). The tab must print them VERBATIM and type none. */
const GG_RULES: GajjalaRules = {
  entry_text: "market at the break, after the entry bar closes (GG: 'right at the break … sometimes I wait for the bar close')",
  stop_text: "the alert's stop, a market stop at the broker from the fill (GG: 'low of the prior bar as the stop loss')",
  size_text: "half of 0.25% of equity at risk first; the other half is added at breakeven (GG: 'half size, then add')",
  manage_text: 'no target — after 3 closed bars above the entry the stop moves to breakeven and the second half is added; the remainder trails the 5-minute 9 EMA (out on a close below it); flat at 15:55 ET',
  risk_text: '0.25% of equity per trade, halved after a loss, back to 0.25% after a win — now 0.125%; drawdown mode off',
  exempt_text: 'no earnings shield, no five-position ceiling, no SEPA distribution exit on lane names — GG\'s rules only',
  not_built: ['base counting (3rd base climax, 4th out)', 'psychological $1 / $5 / $10 levels', 'exit before the stop on hesitation',
              'mental stops', 'monthly risk re-basing'],
  awaiting: [
    { key: 'GG_PARTIAL_R', question: '"peel off 1/3 or half … when strong": at how many R above the entry?' },
    { key: 'GG_TRAIL_EMA_KF', question: '9 or 21 ("the 21 on Kiss & Fly maybe")' },
    { key: 'GG_HALT_CALM_MIN', question: '"when it\'s clean, when it\'s calmer, then I enter": minutes since the last halt resumed' },
    { key: 'GG_CUSHION_DOUBLE_PCT', question: 'the account cushion (% above the start of the month?) at which an A+ gets double size' },
  ],
};
const withRules = (rules: unknown) => withStatus({ rules: rules as GajjalaRules });

describe("GajjalaLaneTab — GG's rules (2026-10-21)", () => {
  it('ggRulesOf: the object only — NEGATIVE: an array (older API), null, a string, a number → null', () => {
    expect(ggRulesOf(GG_RULES)).toBe(GG_RULES);
    expect(ggRulesOf(['a rule'])).toBeNull();
    expect(ggRulesOf(null)).toBeNull();
    expect(ggRulesOf(undefined)).toBeNull();
    expect(ggRulesOf('a rule')).toBeNull();
    expect(ggRulesOf(7)).toBeNull();
  });

  it('prints the six served lines, the not-built list and the awaiting rows (key + question) verbatim, in order', async () => {
    stub(ok(withRules(GG_RULES)), []);
    view();
    const block = await screen.findByTestId('gg-lane-gg-rules');
    expect(screen.getByText("GG's rules")).toBeTruthy();
    const shown = GG_RULE_KEYS.map((k) => within(block).getByTestId(`gg-rule-${k}`).textContent);
    expect(shown).toEqual(GG_RULE_KEYS.map((k) => GG_RULES[k]));
    const nb = within(block).getByTestId('gg-lane-not-built');
    expect([...nb.querySelectorAll('li')].map((li) => li.textContent)).toEqual(GG_RULES.not_built);
    const aw = within(block).getByTestId('gg-lane-awaiting');
    const items = [...aw.querySelectorAll('li')];
    expect(items.map((li) => li.getAttribute('data-awaiting-key'))).toEqual(GG_RULES.awaiting!.map((a) => a.key));
    items.forEach((li, i) => {
      expect(li.querySelector('code')!.textContent).toBe(GG_RULES.awaiting![i].key);
      expect(li.textContent).toBe(`${GG_RULES.awaiting![i].key} — ${GG_RULES.awaiting![i].question}`);
    });
    // NEGATIVE: the older list block is not drawn for the v2 object; no NaN / null / undefined anywhere.
    expect(screen.queryByTestId('gg-lane-rules')).toBeNull();
    expect(document.body.textContent).not.toMatch(/NaN|null|undefined|\[object Object\]/);
  });

  it('NEGATIVE: no `rules` served → no GG\'s rules block and no older list', async () => {
    stub(ok(withRules(undefined)), []);
    view();
    await screen.findByText(FIXTURE.status!.caps_text!);
    expect(screen.queryByTestId('gg-lane-gg-rules')).toBeNull();
    expect(screen.queryByText("GG's rules")).toBeNull();
    expect(screen.queryByTestId('gg-lane-rules')).toBeNull();
  });

  it('NEGATIVE: the older API (rules: string[]) renders the old list exactly as before, no GG\'s rules block', async () => {
    stub(ok(FIXTURE), []);
    view();
    const list = await screen.findByTestId('gg-lane-rules');
    expect([...list.querySelectorAll('li')].map((li) => li.textContent)).toEqual(FIXTURE.status!.rules);
    expect(screen.getByText('Rules (owner rules, paper)')).toBeTruthy();
    expect(screen.queryByTestId('gg-lane-gg-rules')).toBeNull();
  });

  it('NEGATIVE: an empty awaiting list (every number given) → no awaiting list; an empty not_built → no not-built list', async () => {
    stub(ok(withRules({ ...GG_RULES, awaiting: [], not_built: [] })), []);
    view();
    const block = await screen.findByTestId('gg-lane-gg-rules');
    expect(within(block).queryByTestId('gg-lane-awaiting')).toBeNull();
    expect(within(block).queryByText('Awaiting your number')).toBeNull();
    expect(within(block).queryByTestId('gg-lane-not-built')).toBeNull();
    expect(within(block).getByTestId('gg-rule-manage_text').textContent).toBe(GG_RULES.manage_text);
  });

  it('NEGATIVE: a null / blank served line is not drawn (never "null" or "—" in its place); an empty object draws nothing', async () => {
    stub(ok(withRules({ ...GG_RULES, risk_text: null, exempt_text: '  ', awaiting: [{ key: 'GG_PARTIAL_R', question: null }] })), []);
    const r1 = view();
    const block = await screen.findByTestId('gg-lane-gg-rules');
    expect(within(block).queryByTestId('gg-rule-risk_text')).toBeNull();
    expect(within(block).queryByTestId('gg-rule-exempt_text')).toBeNull();
    expect(within(block).getByTestId('gg-rule-entry_text').textContent).toBe(GG_RULES.entry_text);
    expect(within(block).getByTestId('gg-lane-awaiting').textContent).toBe(`GG_PARTIAL_R — ${DASH}`);
    expect(block.textContent).not.toMatch(/null|undefined/);
    r1.unmount();
    stub(ok(withRules({})), []);
    view();
    await screen.findByText(FIXTURE.status!.caps_text!);
    expect(screen.queryByTestId('gg-lane-gg-rules')).toBeNull();
    expect(screen.queryByTestId('gg-lane-rules')).toBeNull();
  });

  it('source guard: the GG\'s rules block types no digit and no rule word of its own (with self-tests)', async () => {
    const src = (await import('./GajjalaLaneTab.tsx?raw')).default as string;
    const at = src.indexOf('function GgRulesBlock(');
    const end = src.indexOf('\nfunction Block(', at);
    expect(at).toBeGreaterThan(0);
    expect(end).toBeGreaterThan(at);
    const block = src.slice(at, end);
    expect(block).not.toMatch(/\d/);
    for (const w of ['breakeven', 'EMA', 'market', 'half', 'earnings', 'stop']) expect(block).not.toContain(w);
    // NEGATIVE self-tests: the guards catch a typed digit / a typed rule word.
    expect(`${block}\n<li>after 3 bars</li>`).toMatch(/\d/);
    expect(`${block}\ntrail the 9 EMA`).toContain('EMA');
  });
});
