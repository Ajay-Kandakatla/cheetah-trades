import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HoldingDiagnosis } from './HoldingDiagnosis';

/* HoldingDiagnosis — the 📅 macro-event heads-up box (Ajay 2026-06-16: "consider
   macro news in the advice"). It's informational (not a sell signal), so it
   renders only when imminent events exist. */

const FACTORS = Object.fromEntries(
  ['market_macro', 'sector_rotation', 'distribution', 'liquidity',
   'stock_specific', 'macro_risk_fwd', 'trend_health'].map((k) => [k, { score: 10, note: 'x' }]),
);

const diag = (extra: Record<string, unknown>) => ({
  symbol: 'MU', name: 'Micron', sector: 'semis_ai', move_pct: 1.2, verdict: 'HOLD',
  headline_label: 'Broad market (macro)', writeup: 'A short note.', scorecard: FACTORS,
  position: null, earnings_quality: null, eq_sell_risk: [],
  ...extra,
});

const okFetch = (body: unknown) =>
  vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(body) });

const renderIn = (ui: React.ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('HoldingDiagnosis — macro events', () => {
  it('shows the 📅 macro-event box when events are present', async () => {
    vi.stubGlobal('fetch', okFetch(diag({
      macro_events: ['FOMC decision tomorrow (2026-06-17) — binary macro event; position size and stops matter more than usual'],
    })));
    renderIn(<HoldingDiagnosis symbol="MU" defaultOpen />);
    await waitFor(() => expect(screen.getByText(/Macro event ahead/i)).toBeInTheDocument());
    expect(screen.getByText(/FOMC decision tomorrow/i)).toBeInTheDocument();
    expect(screen.getByText(/not a sell signal/i)).toBeInTheDocument();   // informational framing
  });

  it('omits the macro-event box when there are none (negative)', async () => {
    vi.stubGlobal('fetch', okFetch(diag({ macro_events: [] })));
    renderIn(<HoldingDiagnosis symbol="MU" defaultOpen />);
    await waitFor(() => expect(screen.getByText(/Why is it moving/i)).toBeInTheDocument());
    expect(screen.queryByText(/Macro event ahead/i)).toBeNull();
  });
});
