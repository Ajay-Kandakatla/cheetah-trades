import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PromoTagTape, layout, etStamp, type TapePayload } from './PromoTagTape';

const T0 = Date.UTC(2026, 8, 2, 13, 0);                     // 9:00 ET
const bar = (t: number, c: number, s = 'rth') => ({ t, o: c, h: c + 0.02, l: c - 0.02, c, v: 1, s });
const bars = [bar(T0 - 60 * 60_000, 3.0, 'premarket'), bar(T0, 3.0), bar(T0 + 30 * 60_000, 3.5), bar(T0 + 60 * 60_000, 4.0), bar(T0 + 90 * 60_000, 3.6)];
const payload = (over: Partial<TapePayload> = {}): TapePayload => ({
  ticker: 'EOSE', bars, n_bars: bars.length, tf: '5min · pre/post market',
  tags: [{ handle: 'topstockalerts', tier: 'A', at: new Date(T0).toISOString(), which: 'first', sample: '$EOSE 🔥', price_at: 3.0, before_pct: 0, peak_after_pct: 34.0 }],
  verdict: 'BEFORE_THE_MOVE', read: 'Posted BEFORE the move: +0.0% in the hour before, then +34.0% to the peak 60 min later, +20.0% now',
  price_at_tag: 3.0, before_pct: 0, peak_pct: 34.0, now_pct: 20.0, mins_to_peak: 60, peak_at: new Date(T0 + 60 * 60_000).toISOString(), ...over,
});

afterEach(() => vi.unstubAllGlobals());

describe('PromoTagTape', () => {
  it('layout puts the tag marker on the bar closed at the tag, shades extended hours, spans the window', () => {
    const g = layout(bars, payload().tags, 720, 110)!;
    expect(g.markers[0].price).toBe(3.0);
    expect(g.markers[0].x).toBeGreaterThan(g.x(bars[0].t));
    expect(g.ext.length).toBe(1);                              // the premarket bar
    expect(g.lo).toBeCloseTo(2.98) ; expect(g.hi).toBeCloseTo(4.02);
    expect(layout([], [], 720, 110)).toBeNull();
  });

  it('renders the read, the marker tooltip with time + price, and the legend', () => {
    render(<PromoTagTape ticker="EOSE" data={payload()} />);
    expect(screen.getByText(/Posted BEFORE the move/)).toBeInTheDocument();
    const tip = document.querySelector('.ptt__tag title')?.textContent || '';
    expect(tip).toContain('@topstockalerts first post · Sep 2 · 9:00a ET · $3.00');
    expect(tip).toContain('+0.0% in the hour before · +34.0% to the peak after');
    expect(screen.getByText(/first tag Sep 2 · 9:00a ET @ \$3\.00/)).toBeInTheDocument();
    expect(screen.getByText(/peak \+34\.0%/)).toBeInTheDocument();
    expect(etStamp(T0)).toBe('Sep 2 · 9:00a ET');
    const posts = document.querySelector('.ptt__posts')!.textContent || '';
    expect(posts).toContain('Sep 2 · 9:00a ET');
    expect(posts).toContain('@topstockalerts');
    expect(posts).toContain('“$EOSE 🔥”');
    expect(posts).toContain('$3.00');
    expect(posts).toContain('+0.0% before');
    expect(posts).toContain('+34.0% after');
  });

  it('fetches when no data is given and degrades on HTTP error / empty bars', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload({ bars: [], n_bars: 0, verdict: null, read: null }) }));
    render(<PromoTagTape ticker="EOSE" />);
    await waitFor(() => expect(screen.getByText(/No intraday bars for EOSE yet/)).toBeInTheDocument());
    expect((fetch as any).mock.calls[0][0]).toMatch(/\/catalysts\/promo-circuit\/tape\/EOSE$/);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502, json: async () => ({}) }));
    render(<PromoTagTape ticker="XXXX" />);
    await waitFor(() => expect(screen.getByText(/Tape unavailable: HTTP 502/)).toBeInTheDocument());
  });
});
