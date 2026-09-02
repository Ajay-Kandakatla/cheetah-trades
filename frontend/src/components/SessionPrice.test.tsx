import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SessionPrice, lines, type QuoteView } from './SessionPrice';

const ah: QuoteView = { session: 'afterhours', rth_close: 3.81, prev_close: 3.96, day_change: -0.15, day_change_pct: -3.79,
  ext_price: 5.12, ext_change: 1.31, ext_change_pct: 34.38, ext_label: 'After Hours', last: 5.12 };

afterEach(() => vi.unstubAllGlobals());

describe('SessionPrice (RTH close + extended-hours print)', () => {
  it('after hours: the close with its day change over the AH print vs the close — the TLYS shape', () => {
    render(<SessionPrice symbol="TLYS" data={ah} />);
    const t = document.querySelector('.session-price')!.textContent!;
    expect(t).toContain('$3.81');
    expect(t).toContain('↓ $0.15 (-3.79%)');
    expect(t).toContain('Today · Closed $3.81');
    expect(t).toContain('$5.12');
    expect(t).toContain('↑ $1.31 (+34.38%)');
    expect(t).toContain('☾ After Hours');
  });

  it('pure lines(): rth = one live line; pre-market vs prev close; closed with equal print = one line', () => {
    expect(lines({ ...ah, session: 'rth', rth_close: 4.95, ext_price: null, day_change: 1.14, day_change_pct: 29.9 }).map((l) => l.tag))
      .toEqual(['Today · Live']);
    const pre = lines({ ...ah, session: 'premarket', rth_close: null, day_change: null, day_change_pct: null, ext_price: 5.0, ext_change: 1.19, ext_change_pct: 31.23, ext_label: 'Pre-Market' });
    expect(pre.length).toBe(1);
    expect(pre[0].tag).toBe('☀ Pre-Market');
    expect(pre[0].ref).toBe('Prev close $3.96');
    expect(lines({ ...ah, session: 'closed', ext_price: null, ext_change: null, ext_change_pct: null, ext_label: null, last: 3.81 }).length).toBe(1);
  });

  it('fetches the view and falls back to the scan close when the endpoint fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ view: ah }) }));
    render(<SessionPrice symbol="TLYS" fallbackClose={3.5} fallbackPct={-1} />);
    await waitFor(() => expect(screen.getByText('☾ After Hours')).toBeInTheDocument());
    expect((fetch as any).mock.calls[0][0]).toMatch(/\/sepa\/live-price\/TLYS$/);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }));
    render(<SessionPrice symbol="XXXX" fallbackClose={3.5} fallbackPct={-1} />);
    await waitFor(() => expect(screen.getAllByText('$3.50').length).toBeGreaterThan(0));
  });
});
