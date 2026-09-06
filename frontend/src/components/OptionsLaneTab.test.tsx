/* OptionsLaneTab — the Auto-Pilot's paper options lane tab (2026-09-06).
 *
 * Ajay: "create a new tab on the Auto pilot on options trading and paper
 * trade with it." A trader with real money next door reads this tab and it
 * carries two writes (the lane switch, a close-now), so everything is pinned
 * with negatives: the payload renders open contracts, closed rows, rules and
 * settings in plain words; OFF → ON asks first and then POSTs exactly
 * {options_entry: true}; ON → OFF is one click; Close posts to
 * /trading/options/close/KLAC only after the confirm, never on the first
 * click; a payload with nothing in it says so in words; a broker without
 * options helpers gets a warning; nulls never print as NaN.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import {
  OptionsLaneTab, EMPTY_OPEN_TEXT, EMPTY_ATTEMPTS_TEXT, EMPTY_CLOSED_TEXT, NO_BROKER_TEXT,
  fmtEt, legsText, structureLabel, settingsRows, fmtIv, netText,
} from './OptionsLaneTab';
import type { OptionsLanePayload, OptionPosition } from './OptionsLaneTab';

const SETTINGS = {
  risk_pct_of_equity: 1.0, max_premium_per_trade: 1500, min_dte: 28, max_dte: 60, close_dte: 7,
  delta_lo: 0.55, delta_hi: 0.75, iv_spread_threshold: 0.45, min_open_interest: 200,
  max_spread_pct_of_mid: 10, min_underlying_price: 20, earnings_close_days: 2, stop_buffer_pct: 0.5,
};
const RULES = [
  'Signal: the same demand-zone touch the stock lane buys, under the alert gate.',
  'Strike from the zone: long call = highest strike at or under the band top with delta 0.55-0.75.',
  'Exit on the underlying, never on the premium.',
];

const KLAC: OptionPosition = {
  pos_id: 'KLAC-2026-09-06', symbol: 'KLAC', status: 'open', structure: 'bull_call_spread',
  legs: [
    { symbol: 'KLAC261017C00900000', side: 'buy', position_intent: 'buy_to_open', ratio_qty: 1, strike: 900, role: 'long' },
    { symbol: 'KLAC261017C00960000', side: 'sell', position_intent: 'sell_to_open', ratio_qty: 1, strike: 960, role: 'short' },
  ],
  qty: 2, debit: 22.4, max_loss: 4480, expiry: '2026-10-17', dte: 41, iv: 0.52, delta: 0.63,
  band: { lo: 895.2, hi: 905.0, touches: 3, strength: 0.8 },
  entry_underlying: 906.1, stop_underlying: 890.72, target_underlying: 962.0,
  earnings: '2026-10-28', room: { state: 'ROOM', room_pct: 6.2, target: 962.0 },
  order_id: 'o-1', entry_ts: '2026-09-06T14:31:05+00:00', day: '2026-09-06', mode: 'paper',
  close_reason: null, exit_credit: null, realized_pnl: null, closed_ts: null,
};
const NTAP: OptionPosition = {
  ...KLAC, pos_id: 'NTAP-2026-09-06', symbol: 'NTAP', status: 'closing', structure: 'long_call',
  legs: [{ symbol: 'NTAP261017C00110000', side: 'buy', position_intent: 'buy_to_open', ratio_qty: 1, strike: 110, role: 'long' }],
  qty: 1, debit: 6.1, max_loss: 610, iv: 0.31, delta: 0.58, target_underlying: null, earnings: null,
};
const CLOSED: OptionPosition = {
  ...KLAC, pos_id: 'AVGO-2026-09-02', symbol: 'AVGO', status: 'closed', structure: 'long_call',
  legs: [{ symbol: 'AVGO261010C00300000', side: 'buy', position_intent: 'buy_to_open', ratio_qty: 1, strike: 300, role: 'long' }],
  qty: 1, debit: 12.0, close_reason: 'underlying reached the room target 318.00', exit_credit: 19.5,
  realized_pnl: 750.0, closed_ts: '2026-09-04T19:55:00+00:00',
};
const LOSER: OptionPosition = {
  ...CLOSED, pos_id: 'EOSE-2026-09-01', symbol: 'EOSE', debit: 3.2, exit_credit: 1.1, realized_pnl: -210.0,
  close_reason: 'underlying under the band floor -0.5%', closed_ts: '2026-09-03T14:02:00+00:00',
};

const FULL: OptionsLanePayload = {
  status: {
    enabled: true, strategy: 'options_zone', broker_has_options: true, entries_today: 1, max_per_day: 1,
    max_open: 3, last_entry_et: '15:45', rules: RULES, settings: SETTINGS,
    open: [KLAC, NTAP],
    attempts: [
      { symbol: 'KLAC', result: 'entered', reason: null, ts: '2026-09-06T14:31:05+00:00' },
      { symbol: 'TRU', result: 'blocked', reason: 'room 0.3% < 5.0% floor', ts: '2026-09-06T14:40:00+00:00' },
    ],
    journal: { n: 4, open: 2, closed: 2, wins: 1, losses: 1, win_rate_pct: 50, avg_r: null, expectancy_pct: -1.6, realized_pnl: 540.0 },
  },
  armed: true, mode: 'paper', recent_closed: [CLOSED, LOSER],
};

const EMPTY: OptionsLanePayload = {
  status: {
    enabled: false, strategy: 'options_zone', broker_has_options: true, entries_today: 0, max_per_day: 1,
    max_open: 3, last_entry_et: '15:45', rules: RULES, settings: SETTINGS, open: [], attempts: [],
    journal: { n: 0, open: 0, closed: 0, wins: 0, losses: 0, win_rate_pct: null, avg_r: null, expectancy_pct: null, realized_pnl: 0 },
  },
  armed: false, mode: 'paper', recent_closed: [],
};

type Call = [string, RequestInit | undefined];

/** fetch stub: GET /trading/options → payload; POSTs → ok/refused. */
function stubFetch(payload: OptionsLanePayload | null, postOk = true) {
  const fn = vi.fn(async (_url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    if (method === 'GET') {
      if (payload == null) return { ok: false, status: 500, json: async () => ({ detail: 'down' }) };
      return { ok: true, status: 200, json: async () => payload };
    }
    return { ok: postOk, status: postOk ? 200 : 500, json: async () => (postOk ? { ok: true } : { detail: 'engine refused' }) };
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}
const posts = (fn: ReturnType<typeof vi.fn>): Call[] =>
  (fn.mock.calls as unknown as Call[]).filter(([, init]) => init?.method === 'POST');

const draw = (onChanged = vi.fn()) => {
  render(<MemoryRouter><OptionsLaneTab onChanged={onChanged} /></MemoryRouter>);
  return onChanged;
};

beforeEach(() => { vi.restoreAllMocks(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('OptionsLaneTab — the payload renders', () => {
  it('header: ON pill, PAPER + armed chips, entries 1 / 1, open 2 / 3, last entry time', async () => {
    stubFetch(FULL);
    draw();
    const hdr = await screen.findByTestId('options-lane-header');
    expect(within(hdr).getByRole('button', { name: /Options lane \(paper\) ON/ })).toBeInTheDocument();
    expect(within(hdr).getByText('PAPER')).toBeInTheDocument();
    expect(within(hdr).getByText('armed')).toBeInTheDocument();
    expect(hdr.textContent).toMatch(/entries today\s*1\s*\/\s*1/);
    expect(hdr.textContent).toMatch(/open\s*2\s*\/\s*3/);
    expect(within(hdr).getByText(/no new entry after 15:45 ET/)).toBeInTheDocument();
    // NEGATIVE: a broker with helpers gets no warning.
    expect(screen.queryByTestId('options-no-broker')).toBeNull();
  });

  it('rules list + settings in plain words', async () => {
    stubFetch(FULL);
    draw();
    const rules = await screen.findByTestId('options-lane-rules');
    for (const r of RULES) expect(within(rules).getByText(r)).toBeInTheDocument();
    const grid = within(rules).getByTestId('options-lane-settings');
    expect(within(grid).getByText('1% of equity')).toBeInTheDocument();
    expect(within(grid).getByText('$1,500')).toBeInTheDocument();
    expect(within(grid).getByText('28–60 days')).toBeInTheDocument();
    expect(within(grid).getByText('≤ 7 DTE')).toBeInTheDocument();
    expect(within(grid).getByText('0.55–0.75')).toBeInTheDocument();
    expect(within(grid).getByText('45%')).toBeInTheDocument();
    expect(within(grid).getByText('10% of mid')).toBeInTheDocument();
    expect(within(grid).getByText('$20')).toBeInTheDocument();
    expect(within(grid).getByText('2 days')).toBeInTheDocument();
    expect(within(grid).getByText('0.5%')).toBeInTheDocument();
  });

  it('open positions: structure, legs with roles, qty, debit, max loss, expiry + DTE, delta, IV, entry / stop / target or clear, status chip', async () => {
    stubFetch(FULL);
    draw();
    const rows = await screen.findAllByTestId('options-open-row');
    expect(rows).toHaveLength(2);
    const k = rows[0];
    expect(within(k).getByRole('link', { name: /KLAC/ })).toBeInTheDocument();
    expect(within(k).getByText('bull call spread')).toBeInTheDocument();
    expect(within(k).getByText('L 900 · S 960')).toBeInTheDocument();
    expect(within(k).getByText('2')).toBeInTheDocument();
    expect(within(k).getByText('$22.40')).toBeInTheDocument();
    expect(within(k).getByText('$4,480')).toBeInTheDocument();
    expect(within(k).getByText('2026-10-17')).toBeInTheDocument();
    expect(within(k).getByText('41 DTE')).toBeInTheDocument();
    expect(within(k).getByText('0.63')).toBeInTheDocument();
    expect(within(k).getByText('52%')).toBeInTheDocument();
    expect(within(k).getByText('$906.10')).toBeInTheDocument();
    expect(within(k).getByText('$890.72')).toBeInTheDocument();
    expect(within(k).getByText('$962.00')).toBeInTheDocument();
    expect(within(k).getByText(/earn 2026-10-28/)).toBeInTheDocument();
    expect(within(k).getByText('open')).toBeInTheDocument();
    const n = rows[1];
    expect(within(n).getByText('long call')).toBeInTheDocument();
    expect(within(n).getByText('L 110')).toBeInTheDocument();
    expect(within(n).getByText('clear')).toBeInTheDocument();         // no supply overhead
    expect(within(n).getByText('closing')).toBeInTheDocument();
    // NEGATIVE: a position already closing cannot be closed twice.
    expect(within(n).getByRole('button', { name: 'Close' })).toBeDisabled();
    expect(within(k).getByRole('button', { name: 'Close' })).toBeEnabled();
  });

  it("today's attempts: symbol, result chip, reason", async () => {
    stubFetch(FULL);
    draw();
    const items = await screen.findAllByTestId('options-attempt');
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText('KLAC')).toBeInTheDocument();
    expect(within(items[0]).getByText('entered')).toBeInTheDocument();
    expect(within(items[1]).getByText('TRU')).toBeInTheDocument();
    expect(within(items[1]).getByText('blocked')).toBeInTheDocument();
    expect(within(items[1]).getByText(/room 0\.3% < 5\.0% floor/)).toBeInTheDocument();
  });

  it('recent closed: debit → exit credit, realized $ green / red, reason, ET time', async () => {
    stubFetch(FULL);
    draw();
    const rows = await screen.findAllByTestId('options-closed-row');
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText('$12.00 → $19.50')).toBeInTheDocument();
    const win = within(rows[0]).getByText('+$750.00');
    expect(win).toHaveStyle({ color: '#10b981' });
    expect(within(rows[0]).getByText(/reached the room target/)).toBeInTheDocument();
    expect(within(rows[0]).getByText(/Sep 4, 3:55 PM ET/)).toBeInTheDocument();
    const loss = within(rows[1]).getByText('-$210.00');
    expect(loss).toHaveStyle({ color: '#ef4444' });
    expect(within(rows[1]).getByText(/under the band floor/)).toBeInTheDocument();
  });

  it('journal mini-card: n / open / closed / win rate / expectancy / realized', async () => {
    stubFetch(FULL);
    draw();
    const j = await screen.findByTestId('options-lane-journal');
    expect(j.textContent).toMatch(/n\s*4/);
    expect(j.textContent).toMatch(/open\s*2/);
    expect(j.textContent).toMatch(/closed\s*2/);
    expect(within(j).getByText('50%')).toBeInTheDocument();
    expect(within(j).getByText('-1.6%')).toBeInTheDocument();
    expect(within(j).getByText('+$540.00')).toBeInTheDocument();
    expect(j.textContent).not.toMatch(/NaN|undefined|null/);
  });
});

describe('OptionsLaneTab — empty, warning and error states', () => {
  it('an empty lane says so in words (open / attempts / closed) and the journal shows dashes, not 0%', async () => {
    stubFetch(EMPTY);
    draw();
    expect(await screen.findByText(EMPTY_OPEN_TEXT)).toBeInTheDocument();
    expect(screen.getByText(EMPTY_ATTEMPTS_TEXT)).toBeInTheDocument();
    expect(screen.getByText(EMPTY_CLOSED_TEXT)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Options lane \(paper\) OFF/ })).toBeInTheDocument();
    expect(screen.getByText('disarmed')).toBeInTheDocument();
    const j = screen.getByTestId('options-lane-journal');
    expect(within(j).queryByText('0%')).toBeNull();
    expect(within(j).getAllByText('—').length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('broker without options helpers → the warning (negative: nothing else breaks)', async () => {
    stubFetch({ ...EMPTY, status: { ...EMPTY.status!, broker_has_options: false, enabled: true } });
    draw();
    const w = await screen.findByTestId('options-no-broker');
    expect(w).toHaveTextContent(NO_BROKER_TEXT);
    expect(screen.getByText(/engine not armed/)).toBeInTheDocument();
  });

  it('a payload of nulls renders "—", never NaN / null / undefined (negative)', async () => {
    stubFetch({ status: { enabled: null, broker_has_options: null, entries_today: null, max_per_day: null, max_open: null,
                          last_entry_et: null, rules: null, settings: null,
                          open: [{ symbol: 'XYZ', status: null, structure: null, legs: null, qty: null, debit: null, max_loss: null,
                                   expiry: null, dte: null, iv: null, delta: null, entry_underlying: null, stop_underlying: null,
                                   target_underlying: null }],
                          attempts: null, journal: null },
                armed: null, mode: null, recent_closed: null });
    draw();
    const tab = await screen.findByTestId('options-lane-tab');
    expect(tab.textContent).not.toMatch(/NaN|null|undefined/);
    expect(tab.textContent).toMatch(/entries today\s*—\s*\/\s*—/);
    expect(screen.getAllByTestId('options-open-row')).toHaveLength(1);
  });

  it('a failed GET shows the unreachable line (negative: no table, no switch)', async () => {
    stubFetch(null);
    draw();
    expect(await screen.findByTestId('options-lane-error')).toHaveTextContent(/Can't reach the options lane/);
    expect(screen.queryByRole('button')).toBeNull();
  });
});

describe('OptionsLaneTab — the switch (POST /trading/config)', () => {
  it('OFF → ON asks first, then POSTs exactly {options_entry: true} and refreshes', async () => {
    const fn = stubFetch(EMPTY);
    const onChanged = draw();
    fireEvent.click(await screen.findByRole('button', { name: /Options lane \(paper\) OFF/ }));
    // NEGATIVE: nothing is posted until the confirm.
    expect(posts(fn)).toHaveLength(0);
    expect(screen.getByRole('dialog', { name: 'Enable the options lane?' })).toHaveTextContent(/PAPER account \(no real dollars\)/);
    fireEvent.click(screen.getByRole('button', { name: /^Enable/ }));
    await waitFor(() => expect(posts(fn)).toHaveLength(1));
    const [url, init] = posts(fn)[0];
    expect(url).toMatch(/\/trading\/config$/);
    expect(JSON.parse(String(init!.body))).toEqual({ options_entry: true });
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
  });

  it('Cancel on the confirm posts nothing (negative)', async () => {
    const fn = stubFetch(EMPTY);
    draw();
    fireEvent.click(await screen.findByRole('button', { name: /Options lane \(paper\) OFF/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(posts(fn)).toHaveLength(0);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('ON → OFF is one click (safer) and POSTs {options_entry: false}', async () => {
    const fn = stubFetch(FULL);
    draw();
    fireEvent.click(await screen.findByRole('button', { name: /Options lane \(paper\) ON/ }));
    await waitFor(() => expect(posts(fn)).toHaveLength(1));
    expect(JSON.parse(String(posts(fn)[0][1]!.body))).toEqual({ options_entry: false });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('a refused POST shows the engine error and refreshes nothing (negative)', async () => {
    stubFetch(FULL, false);
    const onChanged = draw();
    fireEvent.click(await screen.findByRole('button', { name: /Options lane \(paper\) ON/ }));
    await waitFor(() => expect(screen.getByText(/engine refused/)).toBeInTheDocument());
    expect(onChanged).not.toHaveBeenCalled();
  });
});

describe('OptionsLaneTab — Close now (POST /trading/options/close/{underlying})', () => {
  it('Close asks first, then POSTs to /trading/options/close/KLAC and refreshes', async () => {
    const fn = stubFetch(FULL);
    const onChanged = draw();
    const rows = await screen.findAllByTestId('options-open-row');
    fireEvent.click(within(rows[0]).getByRole('button', { name: 'Close' }));
    // NEGATIVE: the first click opens the dialog, it never sends.
    expect(posts(fn)).toHaveLength(0);
    const dlg = screen.getByRole('dialog', { name: 'Close KLAC options?' });
    expect(dlg).toHaveTextContent(/short leg goes first/);
    fireEvent.click(within(dlg).getByRole('button', { name: 'Close KLAC' }));
    await waitFor(() => expect(posts(fn)).toHaveLength(1));
    const [url, init] = posts(fn)[0];
    expect(url).toMatch(/\/trading\/options\/close\/KLAC$/);
    expect(init!.method).toBe('POST');
    expect(init!.body).toBeUndefined();
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('Cancel in the close dialog posts nothing (negative)', async () => {
    const fn = stubFetch(FULL);
    draw();
    const rows = await screen.findAllByTestId('options-open-row');
    fireEvent.click(within(rows[0]).getByRole('button', { name: 'Close' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }));
    expect(posts(fn)).toHaveLength(0);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('a refused close shows the engine error (negative)', async () => {
    stubFetch(FULL, false);
    draw();
    const rows = await screen.findAllByTestId('options-open-row');
    fireEvent.click(within(rows[0]).getByRole('button', { name: 'Close' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Close KLAC' }));
    await waitFor(() => expect(screen.getByText(/engine refused/)).toBeInTheDocument());
  });
});

describe('OptionsLaneTab — helpers', () => {
  it('fmtEt prints Eastern wall-clock with the ET tag; garbage → "—"', () => {
    expect(fmtEt('2026-09-04T19:55:00+00:00')).toBe('Sep 4, 3:55 PM ET');
    expect(fmtEt(1757080000)).toMatch(/ET$/);                    // epoch seconds
    expect(fmtEt('nope')).toBe('—');
    expect(fmtEt(null)).toBe('—');
  });
  it('legsText: role + strike per leg, side as fallback, "—" for none', () => {
    expect(legsText(KLAC.legs)).toBe('L 900 · S 960');
    expect(legsText([{ side: 'sell', strike: 12.5 }])).toBe('S 12.50');
    expect(legsText([])).toBe('—');
    expect(legsText(null)).toBe('—');
  });
  it('structureLabel / fmtIv / settingsRows are null-safe', () => {
    expect(structureLabel('long_call')).toBe('long call');
    expect(structureLabel('short_put_spread')).toBe('short put spread');
    expect(netText(-1.9)).toBe('$1.90 cr');
    expect(netText(6.3)).toBe('$6.30');
    expect(netText(null)).toBe('—');
    expect(structureLabel('iron_condor')).toBe('iron condor');
    expect(structureLabel(null)).toBe('—');
    expect(fmtIv(0.45)).toBe('45%');
    expect(fmtIv(45)).toBe('45%');
    expect(fmtIv(null)).toBe('—');
    const rows = settingsRows(null);
    expect(rows).toHaveLength(11);
    for (const [, v] of rows) expect(v).not.toMatch(/NaN|undefined|null/);
  });
});
