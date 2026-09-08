/* ZeroDteLaneTab — the paper 0DTE lane tab (2026-09-08).
 *
 * Ajay: "help me with doing options ODTE and same day expire day trading
 * options … I would like to see the accuracy and quickness". A real-money
 * trader reads this tab and it carries two writes, so: the payload renders the
 * open contract with its latency and why line, closed rows with P&L next to
 * what the stock did, ON → OFF is one click and POSTs exactly
 * {zero_dte_entry: false}, OFF → ON asks first, Close posts only after the
 * confirm, an empty payload says so in words, a live broker gets the warning,
 * nulls never print as NaN. */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import {
  ZeroDteLaneTab, EMPTY_OPEN_TEXT, EMPTY_RECENT_TEXT, EMPTY_ATTEMPTS_TEXT, LIVE_TEXT,
  fmtSec, fmtNum, pnlText, contractText, latencyText,
} from './ZeroDteLaneTab';
import type { ZeroDtePayload, ZeroDtePosition } from './ZeroDteLaneTab';

const OPEN: ZeroDtePosition = {
  pos_id: 'SPY-2026-09-09-1029', symbol: 'SPY', side: 'call', status: 'open', occ: 'SPY260909C00650000',
  expiry: '2026-09-09', qty: 4, limit_price: 1.25, fill_price: 1.24, mark: 1.4, stock_last: 648.9,
  signal: { kind: 'buy', price: 648.2, stop: 647.1, target: 650.4 },
  contract: { strike: 650, delta: 0.36, spread_pct: 4.1, moves_needed: 0.4 },
  expected_move_pct: 0.9, regime: 'AMPLIFYING',
  latency: { signal_to_seen_sec: 12, seen_to_order_sec: 1, order_to_fill_sec: 2, signal_to_fill_sec: 15 },
  narrative: 'Bought 4 × SPY 2026-09-09 $650.0 call @ $1.25 ask. Signal Lab BUY tag at 10:30:00.',
  signal_bar_close_ts: '2026-09-09T14:30:00+00:00',
};
const CLOSED: ZeroDtePosition = {
  ...OPEN, pos_id: 'QQQ-x', symbol: 'QQQ', status: 'closed', exit_price: 2.1, realized_pnl: 340, premium_return_pct: 69.4,
  stock_move_pct: 0.35, close_reason: 'stock 650.5 hit the 2R target 650.4', closed_ts: '2026-09-09T14:50:00+00:00',
  narrative: 'Bought 4 × QQQ … closed 10:50:00: stock 650.5 hit the 2R target 650.4 — out at $2.1, P&L +340 (stock 0.35%).',
};
const MISSED: ZeroDtePosition = { ...OPEN, pos_id: 'IWM-x', symbol: 'IWM', status: 'missed', fill_price: null, realized_pnl: null, narrative: null };

const PAYLOAD: ZeroDtePayload = {
  armed: true, mode: 'paper',
  status: {
    enabled: true, strategy: 'zero_dte', paper: true, broker_has_options: true, entries_today: 1, max_per_day: 3, max_open: 3,
    entry_window: '09:45–14:30', flatten_et: '15:45',
    rules: ['Names: the 0DTE tab — only a name with a SAME-DAY expiry trades.', 'Paper only: a live broker gates the lane off. Not advice.'],
    settings: { premium_take_pct: 100, premium_stop_pct: 50 },
    open: [OPEN],
    attempts: [{ symbol: 'SPY', result: 'entered', reason: null, ts: '2026-09-09T14:30:12+00:00' },
               { symbol: 'NVDA', result: 'skipped', reason: 'no same-day chain', ts: '2026-09-09T14:31:00+00:00' }],
    journal: { n: 3, open: 1, closed: 1, missed: 1, wins: 1, losses: 0, win_rate_pct: 100, avg_premium_return_pct: 69.4,
               realized_pnl: 340, avg_stock_move_pct: 0.35, median_signal_to_fill_sec: 15, median_order_to_fill_sec: 2 },
  },
  recent: [CLOSED, MISSED],
};

function stub(payload: ZeroDtePayload | null, calls: { url: string; init?: RequestInit }[]) {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    if (init?.method === 'POST') return Promise.resolve({ ok: true, json: async () => ({ ok: true }) });
    if (payload === null) return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
    return Promise.resolve({ ok: true, json: async () => payload });
  }));
}

beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('pure formatters', () => {
  it('never print NaN and say the latency in seconds', () => {
    expect(fmtNum(null)).toBe('—'); expect(fmtNum(undefined)).toBe('—'); expect(fmtNum('x')).toBe('—'); expect(fmtNum(1.234)).toBe('1.23');
    expect(fmtSec(null)).toBe('—'); expect(fmtSec(15)).toBe('15.0s');
    expect(pnlText(CLOSED)).toBe('+340 (+69%)'); expect(pnlText(MISSED)).toBe('—');
    expect(contractText(OPEN)).toBe('2026-09-09 $650 call');
    expect(contractText({ symbol: 'X' })).toBe('same-day $— ?');
    expect(latencyText(OPEN.latency)).toBe('12.0s → 1.0s → 2.0s (15.0s total)');
    expect(latencyText(null)).toBe('—');
  });
});

describe('ZeroDteLaneTab', () => {
  it('renders the open contract with its latency, why line, closed rows with P&L vs the stock, and the journal', async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    stub(PAYLOAD, calls);
    render(<ZeroDteLaneTab />);
    await screen.findByText('1/3 entries today · 1/3 open · entries 09:45–14:30 ET · flat by 15:45');
    expect(calls[0].url).toMatch(/\/trading\/zero-dte$/);
    const open = screen.getByText('Open').parentElement!;
    expect(within(open).getByText('SPY')).toBeTruthy();
    expect(within(open).getByText('2026-09-09 $650 call')).toBeTruthy();
    expect(within(open).getByText('12.0s → 1.0s → 2.0s (15.0s total)')).toBeTruthy();
    expect(within(open).getByText('648.90 / 647.10 / 650.40')).toBeTruthy();
    const whys = screen.getAllByTestId('zdte-why');
    expect(whys[0].textContent).toContain('Signal Lab BUY tag');
    const closed = screen.getByText('Closed today and recent').parentElement!;
    expect(within(closed).getByText('QQQ')).toBeTruthy();
    expect(within(closed).getByText('+340')).toBeTruthy();
    expect(within(closed).getByText('+0.35%')).toBeTruthy();
    expect(within(closed).getByText('stock 650.5 hit the 2R target 650.4')).toBeTruthy();
    expect(within(closed).getByText('missed')).toBeTruthy();
    const j = screen.getByTestId('zdte-journal');
    expect(j.textContent).toContain('1 (1W / 0L)');
    expect(j.textContent).toContain('15.0s');
    expect(screen.getByText(/NVDA — skipped: no same-day chain/)).toBeTruthy();
    expect(screen.getByText('Names: the 0DTE tab — only a name with a SAME-DAY expiry trades.')).toBeTruthy();
    expect(screen.queryByText(LIVE_TEXT)).toBeNull();
    expect(document.body.textContent).not.toContain('NaN');
  });

  it('ON → OFF is one click and POSTs exactly {zero_dte_entry: false}', async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    stub(PAYLOAD, calls);
    render(<ZeroDteLaneTab />);
    const btn = await screen.findByRole('button', { name: 'Lane ON — turn off' });
    expect(btn.getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(btn);
    await waitFor(() => expect(calls.some((c) => c.init?.method === 'POST')).toBe(true));
    const p = calls.find((c) => c.init?.method === 'POST')!;
    expect(p.url).toMatch(/\/trading\/config$/);
    expect(JSON.parse(String(p.init?.body))).toEqual({ zero_dte_entry: false });
  });

  it('OFF → ON asks first; No sends nothing (negative)', async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    stub({ ...PAYLOAD, status: { ...PAYLOAD.status!, enabled: false } }, calls);
    render(<ZeroDteLaneTab />);
    fireEvent.click(await screen.findByRole('button', { name: 'Lane OFF — turn on' }));
    const dlg = screen.getByRole('dialog', { name: 'Turn the 0DTE lane on?' });
    fireEvent.click(within(dlg).getByRole('button', { name: 'No' }));
    expect(calls.filter((c) => c.init?.method === 'POST')).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Lane OFF — turn on' }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Turn the 0DTE lane on?' })).getByRole('button', { name: 'Yes, on' }));
    await waitFor(() => expect(calls.some((c) => c.init?.method === 'POST')).toBe(true));
    expect(JSON.parse(String(calls.find((c) => c.init?.method === 'POST')!.init?.body))).toEqual({ zero_dte_entry: true });
  });

  it('Close posts /trading/zero-dte/close/SPY only after the confirm (negative first)', async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    stub(PAYLOAD, calls);
    render(<ZeroDteLaneTab />);
    fireEvent.click(await screen.findByRole('button', { name: 'Close' }));
    expect(calls.filter((c) => c.init?.method === 'POST')).toHaveLength(0);
    const dlg = screen.getByRole('dialog', { name: 'Close SPY 0DTE?' });
    fireEvent.click(within(dlg).getByRole('button', { name: 'Yes' }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith('/trading/zero-dte/close/SPY') && c.init?.method === 'POST')).toBe(true));
  });

  it('an empty payload says so in words; a live broker gets the warning; a failed load reports the error', async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    stub({ armed: true, mode: 'paper', status: { enabled: true, open: [], attempts: [], journal: null, rules: [] }, recent: [] }, calls);
    const { unmount } = render(<ZeroDteLaneTab />);
    expect(await screen.findByText(EMPTY_OPEN_TEXT)).toBeTruthy();
    expect(screen.getByText(EMPTY_RECENT_TEXT)).toBeTruthy();
    expect(screen.getByText(EMPTY_ATTEMPTS_TEXT)).toBeTruthy();
    unmount();
    stub({ ...PAYLOAD, mode: 'live', status: { ...PAYLOAD.status!, paper: false } }, calls);
    const r2 = render(<ZeroDteLaneTab />);
    expect(await screen.findByText(LIVE_TEXT)).toBeTruthy();
    r2.unmount();
    stub(null, calls);
    render(<ZeroDteLaneTab />);
    expect(await screen.findByText(/could not load: HTTP 500/)).toBeTruthy();
  });
});
