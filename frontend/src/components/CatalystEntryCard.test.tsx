/* CatalystEntryCard — the paper Auto-Pilot's catalyst lane (2026-09-05).
 *
 * Ajay: "What ever rules I created for the alerts are the ideal conditions for
 * a stock to be bough in Autopilot. Keep the minervini entries but also make
 * sure you have demand zone and catalyst based entries time to time and
 * journal it appropriately." This card is the lane's switch and its status.
 * A trader with real money next door reads it, and the switch is a config
 * write, so everything is pinned with negatives: OFF renders as OFF with the
 * engine's own reason; turning ON needs the confirm and then POSTs exactly
 * {catalyst_entry: true}; turning OFF is one click and POSTs false; a failed
 * POST shows the error and refreshes nothing; a LIVE mode is named in red;
 * "no cached catalyst scan" is said out loud; nulls never print as NaN.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CatalystEntryCard, NO_SCAN_TEXT } from './CatalystEntryCard';
import type { CatalystEntryInfo } from './CatalystEntryCard';

const RULES = [
  { rule: 'room to the first unbroken band overhead', value: '>= 5.0%', source: 'owner setting — ALERT_MIN_ROOM_PCT (Ajay 2026-09-05)' },
  { rule: 'max catalyst entries per day', value: 2, source: 'owner setting — CATALYST_MAX_PER_DAY' },
];

const ON: CatalystEntryInfo = {
  enabled: true,
  entries_today: 1,
  max_per_day: 2,
  rules: RULES,
  candidates: [
    { symbol: 'EOSE', price: 15.57, room_pct: 17.0, room_state: 'ROOM', why: 'promo circuit · 3 tier-A callers', state: 'bought' },
    { symbol: 'CLYM', price: 9.8, room_pct: null, room_state: 'CLEAR', why: 'FDA date 09-12', state: 'eligible' },
  ],
  skipped: [
    { symbol: 'TRU', reason: 'room 0.3% < 5.0% floor' },
    { symbol: 'NTAP', reason: 'earnings in 3 days' },
  ],
  as_of: '2026-09-05T14:02:11+00:00',
};

const OFF: CatalystEntryInfo = {
  enabled: false, entries_today: 0, max_per_day: 2, rules: RULES, candidates: [], skipped: [],
  as_of: null, reason: 'catalyst entries disabled',
};

function stubPost(ok = true) {
  const fn = vi.fn(async () => ({ ok, status: ok ? 200 : 500, json: async () => (ok ? { catalyst_entry: true } : { detail: 'engine refused' }) }));
  vi.stubGlobal('fetch', fn);
  return fn;
}

const draw = (c: CatalystEntryInfo, mode: 'sim' | 'paper' | 'live' = 'paper', onChanged = vi.fn()) => {
  render(<MemoryRouter><CatalystEntryCard c={c} mode={mode} onChanged={onChanged} /></MemoryRouter>);
  return onChanged;
};

beforeEach(() => { vi.restoreAllMocks(); });
afterEach(() => { vi.unstubAllGlobals(); });

/** EXACTLY what backend catalyst_entry.status_block emits (review 2026-09-05):
 *  candidates = _candidate(c) rows, room/state live only in today's attempts. */
const BACKEND: CatalystEntryInfo = {
  enabled: true, paper_only: true, entries_today: 1, max_per_day: 1, last_entry_et: '15:45',
  as_of: '2026-09-05T14:02:11+00:00', scan: { cached: true, cache_age_sec: 60, n_total: 3 },
  rules: RULES,
  candidates: [
    { symbol: 'EOSE', quadrant: 'REAL', grade: 'A', catalyst_summary: 'Grid storage contract award',
      price: 5.0, dollar_volume: 5_000_000, change_pct: 12.0, market_cap: 3e8, composite_score: 80,
      day_low: 4.83, day_high: 5.05, prev_close: 4.9 },
    { symbol: 'CLYM', quadrant: 'OVERLOOKED', grade: 'B', catalyst_summary: null,
      price: 9.8, dollar_volume: 3_000_000, change_pct: 8.0, market_cap: 2e8, composite_score: 61,
      day_low: 9.1, day_high: 9.9, prev_close: 9.0 },
  ],
  skipped: [{ symbol: 'BBB', reason: 'quadrant PUMP_RISK' }],
  attempts: [
    { key: 'EOSE:2026-09-05', symbol: 'EOSE', date: '2026-09-05', attempted: true, entered: true,
      result: 'entered', reason: null, print: 5.0, print_basis: 'catalyst scan price', print_age_sec: 60,
      room: { state: 'ROOM', room_pct: 12.0, room_pct_raw: 12.0, target: 5.6, touches: 3,
              band: { kind: 'supply', lo: 5.6, hi: 5.8, touches: 3 } },
      side: 'demand', band: { kind: 'demand', lo: 4.8, hi: 4.97, touches: 3 },
      stop_price: 4.776, stop_pct: 4.48, order_id: 'o-1' },
  ],
};

describe('CatalystEntryCard — the backend shape', () => {
  it('why <- catalyst_summary, state <- quadrant/grade (+ today\'s result), room <- today\'s attempt; no attempt = honest dash', () => {
    stubPost();
    draw(BACKEND);
    const card = screen.getByTestId('catalyst-entry');
    expect(within(card).getByText('Grid storage contract award')).toBeInTheDocument();
    expect(within(card).getByText(/REAL\/A · entered/)).toBeInTheDocument();
    expect(within(card).getByText('OVERLOOKED/B')).toBeInTheDocument();
    expect(within(card).getByText(/\+12\.0% room/)).toBeInTheDocument();
    expect(within(card).getByText(/\$5\.00/)).toBeInTheDocument();
    // CLYM: no summary, no attempt today -> "—" for why and room, never NaN / undefined
    const clym = within(card).getByRole('link', { name: /CLYM/ }).closest('tr')!;
    expect(within(clym).getAllByText('—').length).toBe(2);
    expect(within(clym).getByTitle(/zone gate runs at tick time/)).toBeInTheDocument();
    expect(card.textContent).not.toMatch(/NaN|undefined/);
    expect(within(card).getByText(/quadrant PUMP_RISK/)).toBeInTheDocument();
  });
});

describe('CatalystEntryCard — states', () => {
  it('ON: pill, entries today / max, candidates with room, skipped with reasons, as-of', () => {
    stubPost();
    draw(ON);
    const card = screen.getByTestId('catalyst-entry');
    expect(within(card).getByRole('button', { name: /Catalyst entries \(paper\) ON/ })).toBeInTheDocument();
    expect(within(card).getByText('1')).toBeInTheDocument();
    expect(within(card).getByText('/ 2')).toBeInTheDocument();
    expect(within(card).getByRole('link', { name: /EOSE/ })).toBeInTheDocument();
    expect(within(card).getByText(/\+17\.0% room/)).toBeInTheDocument();
    expect(within(card).getByText(/open sky/)).toBeInTheDocument();
    expect(within(card).getByText(/promo circuit · 3 tier-A callers/)).toBeInTheDocument();
    expect(within(card).getByText('TRU')).toBeInTheDocument();
    expect(within(card).getByText(/room 0\.3% < 5\.0% floor/)).toBeInTheDocument();
    expect(within(card).getByText(/earnings in 3 days/)).toBeInTheDocument();
    expect(within(card).getByTestId('catalyst-as-of')).toHaveAttribute('title', '2026-09-05T14:02:11+00:00');
    // The rules the engine served are on the card, with their sources.
    expect(within(card).getByText(/room to the first unbroken band overhead/)).toBeInTheDocument();
    expect(within(card).getByText(/ALERT_MIN_ROOM_PCT/)).toBeInTheDocument();
  });

  it('OFF: pill OFF, the engine reason, and the no-cached-scan line (negative: no candidates table)', () => {
    stubPost();
    draw(OFF);
    const card = screen.getByTestId('catalyst-entry');
    expect(within(card).getByRole('button', { name: /Catalyst entries \(paper\) OFF/ })).toBeInTheDocument();
    expect(within(card).getByText(/catalyst entries disabled/)).toBeInTheDocument();
    expect(within(card).getByText(NO_SCAN_TEXT)).toBeInTheDocument();
    expect(within(card).queryByRole('table')).toBeNull();
    expect(within(card).getByText('0')).toBeInTheDocument();
  });

  it('a payload of nulls renders "—", never NaN / null (negative)', () => {
    stubPost();
    draw({ enabled: null, entries_today: null, max_per_day: null, rules: null, candidates: null, skipped: null, as_of: null });
    const card = screen.getByTestId('catalyst-entry');
    expect(card.textContent).not.toMatch(/NaN|null|undefined/);
    expect(card.textContent).toMatch(/entries today\s*—\s*\/\s*—/);
    expect(within(card).getByText(NO_SCAN_TEXT)).toBeInTheDocument();
  });

  it('at the daily cap the count turns amber and says so', () => {
    stubPost();
    draw({ ...ON, entries_today: 2 });
    expect(screen.getByText(/at today's cap/)).toBeInTheDocument();
  });
});

describe('CatalystEntryCard — the switch (POST /trading/config)', () => {
  it('OFF → ON asks first, then POSTs exactly {catalyst_entry: true} and refreshes', async () => {
    const fn = stubPost();
    const onChanged = draw(OFF);
    fireEvent.click(screen.getByRole('button', { name: /Catalyst entries \(paper\) OFF/ }));
    // NEGATIVE: nothing is posted until the confirm.
    expect(fn).not.toHaveBeenCalled();
    expect(screen.getByText(/Enable catalyst entries\?/)).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toHaveTextContent(/paper account \(no real dollars\)/);
    fireEvent.click(screen.getByRole('button', { name: /^Enable/ }));
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(1));
    const [url, init] = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/trading\/config$/);
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({ catalyst_entry: true });
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
  });

  it('Cancel on the confirm posts nothing (negative)', () => {
    const fn = stubPost();
    draw(OFF);
    fireEvent.click(screen.getByRole('button', { name: /Catalyst entries \(paper\) OFF/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(fn).not.toHaveBeenCalled();
    expect(screen.queryByText(/Enable catalyst entries\?/)).toBeNull();
  });

  it('ON → OFF is one click (safer), POSTs {catalyst_entry: false}', async () => {
    const fn = stubPost();
    const onChanged = draw(ON);
    fireEvent.click(screen.getByRole('button', { name: /Catalyst entries \(paper\) ON/ }));
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(1));
    const [, init] = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ catalyst_entry: false });
    expect(screen.queryByText(/Enable catalyst entries\?/)).toBeNull();
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
  });

  it('a refused POST shows the engine error and refreshes nothing (negative)', async () => {
    stubPost(false);
    const onChanged = draw(ON);
    fireEvent.click(screen.getByRole('button', { name: /Catalyst entries \(paper\) ON/ }));
    await waitFor(() => expect(screen.getByText(/engine refused/)).toBeInTheDocument());
    expect(onChanged).not.toHaveBeenCalled();
  });

  it('LIVE mode is named in the confirm — real dollars', () => {
    stubPost();
    draw(OFF, 'live');
    fireEvent.click(screen.getByRole('button', { name: /Catalyst entries OFF/ }));
    expect(screen.getByRole('dialog')).toHaveTextContent(/LIVE account\. Real dollars\./);
    expect(screen.getByRole('button', { name: 'Enable (LIVE)' })).toBeInTheDocument();
    // NEGATIVE: the pill does not call a live account "paper".
    expect(screen.queryByRole('button', { name: /\(paper\)/ })).toBeNull();
  });
});
