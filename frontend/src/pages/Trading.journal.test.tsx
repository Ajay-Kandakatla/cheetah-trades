import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { JournalView } from './Trading';
import { HONESTY_NOTE } from '../components/JournalByStrategy';

/* JournalView — the Auto-Pilot journal with the 2026-09-05 lane split.
   Ajay: "make sure you have demand zone and catalyst based entries time to
   time and journal it appropriately." Locked: the by-strategy table sits on
   the trades tab, every TradeCard wears its lane chip from
   trade.entry.strategy, a row without the tag (pre-2026-09-05) reads as
   manual — never as a Minervini trade — and a journal with no summary block
   still renders. */

const entry = (over: Record<string, unknown> = {}) => ({
  ts: 1757080000, price: 15.57, qty: 100, stop_price: 14.9, stop_pct: 4.3,
  target_price: 18.2, target_pct: 16.9, reward_risk: 3.9, regime: 'normal', trigger: null, ...over,
});

const J = {
  trades: [
    { trade_id: 't1', symbol: 'EOSE', status: 'closed', entry: entry({ strategy: 'demand_zone', entry_reason: { band: [14.6, 14.95], room_pct: 17.0 } }),
      protected_to_breakeven: false, exit: { ts: 1757090000, price: 16.4, leg: 'take_profit' },
      realized: { gain_pct: 5.3, gain_dollars: 83, r_multiple: 1.2, holding_days: 2, exit_reason: 'target' }, narrative: 'Bought the demand arrival.' },
    { trade_id: 't2', symbol: 'AVGO', status: 'closed', entry: entry({}),
      protected_to_breakeven: false, exit: { ts: 1757090000, price: 300, leg: 'stop' },
      realized: { gain_pct: -3.1, gain_dollars: -50, r_multiple: -1, holding_days: 1, exit_reason: 'stop' }, narrative: '' },
  ],
  open: [
    { trade_id: 't3', symbol: 'CLYM', status: 'open', entry: entry({ strategy: 'catalyst' }),
      protected_to_breakeven: false, exit: null, realized: null, narrative: '', mark: { last: 10.1, unrealized_pct: 3.0 } },
  ],
  decisions: [],
  summary: {
    by_strategy: {
      demand_zone: { n: 1, open: 0, closed: 1, wins: 1, losses: 0, win_rate_pct: 100, avg_r: 1.2, expectancy_pct: 5.3, realized_pnl: 83 },
      catalyst: { n: 1, open: 1, closed: 0, wins: 0, losses: 0, win_rate_pct: null, avg_r: null, expectancy_pct: null, realized_pnl: 0 },
      manual: { n: 1, open: 0, closed: 1, wins: 0, losses: 1, win_rate_pct: 0, avg_r: -1, expectancy_pct: -3.1, realized_pnl: -50 },
    },
  },
};

const draw = (j: unknown) => render(<MemoryRouter><JournalView j={j as never} err={false} /></MemoryRouter>);

describe('JournalView · by-strategy (2026-09-05)', () => {
  it('mounts the by-strategy table above the trades, with the honesty note', () => {
    draw(J);
    expect(screen.getByTestId('journal-by-strategy')).toBeInTheDocument();
    expect(screen.getByText(HONESTY_NOTE)).toBeInTheDocument();
    const row = screen.getByRole('row', { name: /demand zone/ });
    expect(within(row).getByText('100%')).toBeInTheDocument();
  });

  it('every trade card wears its lane chip; an untagged row is manual, never Minervini', () => {
    draw(J);
    const chips = screen.getAllByTestId('strategy-chip').map((c) => c.textContent);
    expect(chips).toContain('🧲 demand zone');
    expect(chips).toContain('🗞️ catalyst');
    expect(chips).toContain('✋ manual');
    expect(chips.some((c) => /Minervini/.test(c ?? ''))).toBe(false);
  });

  it('a journal with no summary block still renders trades and a muted table (negative)', () => {
    draw({ ...J, summary: undefined });
    expect(screen.getByTestId('journal-by-strategy')).toBeInTheDocument();
    expect(screen.getAllByTestId('strategy-chip')).toHaveLength(3);
  });

  it('shows the error state when the journal fails to load', () => {
    render(<MemoryRouter><JournalView j={null} err={true} /></MemoryRouter>);
    expect(screen.getByText(/Can't load the journal/)).toBeInTheDocument();
  });
});
