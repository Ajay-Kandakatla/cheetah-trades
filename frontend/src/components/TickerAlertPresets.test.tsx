import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import type { PriceAlert } from '../hooks/usePriceAlerts';
// The component's own source text, for the static locks below. Vite's `?raw`
// loader has no ambient type in this tsconfig (no @types/node either, so
// `fs` is not an option) — the import is real at runtime.
// @ts-ignore - no ambient declaration for the ?raw query
import RAW from './TickerAlertPresets.tsx?raw';
const SOURCE = RAW as unknown as string;

/* 🔔 TickerAlertPresets — the latch state line is SERVED, never composed.
 *
 * The backend (sepa/price_alerts._state_line) words the whole sentence: the
 * day label, the price (or no price, for a legacy latch) and the direction
 * price has to cross back. This component prints that string verbatim under
 * the kind label and dims the row while the alert is latched.
 *
 * The locks: the served text appears exactly as served (no `$` added, no date
 * math), and the negatives — no `state_line`, an empty one, or a legacy row
 * with no state keys at all must render NO extra line rather than a sentence
 * the frontend invented.
 */

const listPriceAlerts = vi.fn<() => Promise<PriceAlert[]>>();
const createPriceAlert = vi.fn();
const deletePriceAlert = vi.fn();

vi.mock('../hooks/usePriceAlerts', () => ({
  listPriceAlerts:   (...a: any[]) => (listPriceAlerts as any)(...a),
  createPriceAlert:  (...a: any[]) => (createPriceAlert as any)(...a),
  deletePriceAlert:  (...a: any[]) => (deletePriceAlert as any)(...a),
}));

// Imported after the mock so the component picks up the mocked module.
const { TickerAlertPresets } = await import('./TickerAlertPresets');

/** A served row. Only the keys the backend actually writes are set here —
 *  `over` adds the latch keys so the legacy case can omit them entirely. */
const row = (over: Partial<PriceAlert> = {}): PriceAlert => ({
  _id: 'a1',
  symbol: 'MKSI',
  kind: 'below',
  level: 306.18,
  created_price: 331.39,
  created_at: 1_748_000_000,
  last_fired_at: 1_758_000_000,
  channels: ['push', 'browser'],
  note: 'stop line',
  ...over,
});

const mount = async (rows: PriceAlert[]) => {
  listPriceAlerts.mockResolvedValue(rows);
  render(<TickerAlertPresets symbol="MKSI" onClose={() => {}} />);
  await waitFor(() => expect(kindLabel()).not.toBeNull());
};

/** The kind-label span of the first active-alert row (`↓ $306.18 · note`). */
const kindLabel = () =>
  document.querySelector('span.mono:not(.pa-state-line)') as HTMLElement | null;

const stateLines = () => Array.from(document.querySelectorAll('.pa-state-line'));

beforeEach(() => {
  listPriceAlerts.mockReset();
  createPriceAlert.mockReset();
  deletePriceAlert.mockReset();
});

describe('TickerAlertPresets — served latch state line', () => {
  it('renders the served state_line verbatim, exactly once, and dims the latched row', async () => {
    const served = 'triggered Sep 21 at $256.15 — re-arms when price crosses back above the line';
    await mount([row({ armed: false, state_line: served })]);

    const lines = stateLines();
    expect(lines).toHaveLength(1);
    expect(lines[0].textContent).toBe(served);
    expect(screen.getAllByText(served)).toHaveLength(1);

    const rowEl = lines[0].closest('div');
    expect(rowEl).not.toBeNull();
    expect((rowEl as HTMLElement).style.opacity).toBe('0.7');
  });

  it('NEG: armed row with state_line null renders no line and no "re-arms" text', async () => {
    await mount([row({ armed: true, state_line: null })]);

    expect(stateLines()).toHaveLength(0);
    expect(document.body.textContent).not.toContain('re-arms');
    // the row itself is still there, undimmed
    expect(kindLabel()!.textContent).toContain('↓ $306.18');
    const rowEl = kindLabel()!.closest('div') as HTMLElement;
    expect(rowEl.style.opacity).toBe('1');
  });

  it('NEG: latched row with an empty state_line composes nothing from armed/triggered_at', async () => {
    await mount([row({
      armed: false,
      state_line: '',
      triggered_at: 1_758_470_000,
      triggered_price: 256.15,
    })]);

    expect(stateLines()).toHaveLength(0);
    expect(document.body.textContent).not.toContain('triggered');
    expect(document.body.textContent).not.toContain('256.15');
  });

  it('NEG: a legacy row with no state keys at all renders exactly as before', async () => {
    await mount([row()]);

    expect(stateLines()).toHaveLength(0);
    expect(kindLabel()!.textContent).toContain('↓ $306.18');
    expect(screen.getByText('· stop line')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '✕ remove' })).toBeInTheDocument();
    const rowEl = kindLabel()!.closest('div') as HTMLElement;
    expect(rowEl.style.opacity).toBe('1');
  });

  it('NEG static: the component never does date math and never writes the served wording', () => {
    expect(SOURCE).not.toContain('new Date(');
    expect(SOURCE).not.toContain('re-arms');
    // it does read the served key and print it
    expect(SOURCE).toContain('state_line');
    expect(SOURCE).toContain('pa-state-line');
  });

  it('renders a legacy latch line with no price verbatim — the FE adds no $', async () => {
    const served = 'triggered Sep 21 — re-arms when price crosses back above the line';
    await mount([row({ armed: false, triggered_price: null, state_line: served })]);

    const lines = stateLines();
    expect(lines).toHaveLength(1);
    expect(lines[0].textContent).toBe(served);
    expect(lines[0].textContent).not.toContain('$');
  });
});
