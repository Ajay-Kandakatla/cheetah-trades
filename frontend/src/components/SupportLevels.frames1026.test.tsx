import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SupportLevels } from './SupportLevels';
import { FALLBACK_WINDOWS, type SupportLevel, type SupportPayload } from '../lib/supportLevels';
import served from './__fixtures__/support_timeframes_2026_10_26.json';

/* 🕐 The 1-minute + weekly Support frames through the REAL component (2026-10-26).
 *
 * Ajay: "Can you build me 1 min bar chart and also 1 week bar chart in the
 * supply and demand".
 *
 * The rows come from the GENERATED served fixture (json.dumps of
 * `tf_options(include_live=True)`); no frame word is typed in this file. */

// Mocked exactly as SupportLevels.test.tsx: the tab's job here is the CONTROLS.
vi.mock('./PatternChart', () => ({
  PatternChart: ({ tile, bandStudy }: any) => (
    <div data-testid="chart" data-band-study={bandStudy?.headline ?? ''}>
      {tile.symbol}
      {tile.band_structure
        ? <span data-testid="chart-band-read">{tile.band_structure.stat}</span> : null}
    </div>
  ),
}));

type Row = { key: string; label: string; span: string; bar_label: string;
  window_label: string; bars: number };
const SERVED = served as Row[];

function lvl(over: Partial<SupportLevel> = {}): SupportLevel {
  return {
    lo: 148.22, hi: 152.74, mid: 150.48, origin: 'demand', touches: 4,
    strength: 72, bars_since_test: 5, oldest_touch_bars: 40, recent: true,
    tested: true,
    distance_pct: 2.4,
    ...over,
  };
}

const PAYLOAD: SupportPayload = {
  symbol: 'DHI',
  name: 'D.R. Horton',
  window: '3m',
  window_label: '3 months',
  windows: FALLBACK_WINDOWS,
  timeframes: SERVED,
  recent_bars: 21,
  last_price: 156.4,
  bars_used: 63,
  short_history: null,
  tile: {
    symbol: 'DHI', href: '/sepa/DHI?tab=supply', bars: [], bands: [],
    lines: [], markers: [], stats: [], why: 'x',
  } as any,
  supports: [lvl(), lvl({ lo: 138.0, hi: 140.5, recent: false,
                          bars_since_test: 44, distance_pct: 10.2, touches: 2 })],
  overhead: [lvl({ lo: 161.0, hi: 163.2, distance_pct: 2.9, origin: 'supply',
                   touches: 3, bars_since_test: 12 })],
  standing_in: null,
  levels_capped: false,
  note: 'Levels are read from this window only.',
  disclaimer: 'Not advice.',
} as SupportPayload;

function mockFetch(payload: any, ok = true) {
  const spy = vi.fn().mockResolvedValue({
    ok, status: ok ? 200 : 500, json: async () => payload,
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

const noop = () => {};
const ready = () => waitFor(() => expect(screen.getByText('$148.22 – $152.74')).toBeTruthy());

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe('🕐 SupportLevels — the 1-minute and weekly frames', () => {
  it('the picker shows the SERVED rows, in served order, with their served words', async () => {
    mockFetch(PAYLOAD);
    const { container } = render(
      <SupportLevels symbol="DHI" window="1y" tf="daily"
                     onSymbol={noop} onWindow={noop} onView={noop} />);
    await ready();
    const opts = Array.from(container.querySelectorAll('select')[0].querySelectorAll('option'));
    expect(opts.map((o) => o.getAttribute('value'))).toEqual(SERVED.map((r) => r.key));
    opts.forEach((o, i) => expect(o.textContent).toBe(`${SERVED[i].label} · ${SERVED[i].span}`));
  });

  it('the weekly chart carries a zoom offering only its own windows', async () => {
    mockFetch(PAYLOAD);
    const onView = vi.fn();
    const { container } = render(
      <SupportLevels symbol="DHI" window="1y" tf="weekly"
                     onSymbol={noop} onWindow={noop} onView={onView} />);
    await ready();
    const selects = container.querySelectorAll('select');
    expect(selects.length).toBe(2);
    expect(Array.from(selects[1].querySelectorAll('option')).map((o) => o.getAttribute('value')))
      .toEqual(['6m', '1y', '2y', '3y', '5y']);
    fireEvent.change(selects[1], { target: { value: '5y' } });
    expect(onView).toHaveBeenCalledTimes(1);
    expect(onView).toHaveBeenCalledWith('5y', 'weekly');
  });

  it('the 1-minute chart carries no zoom', async () => {
    mockFetch(PAYLOAD);
    const { container } = render(
      <SupportLevels symbol="DHI" window="6m" tf="1min"
                     onSymbol={noop} onWindow={noop} onView={noop} />);
    await ready();
    expect(container.querySelectorAll('select').length).toBe(1);
    expect((container.querySelectorAll('select')[0] as HTMLSelectElement).value).toBe('1min');
  });

  it('switching frames keeps or pins the zoom', async () => {
    mockFetch(PAYLOAD);
    const onView = vi.fn();
    const a = render(
      <SupportLevels symbol="DHI" window="1y" tf="daily"
                     onSymbol={noop} onWindow={noop} onView={onView} />);
    await ready();
    fireEvent.change(a.container.querySelectorAll('select')[0], { target: { value: 'weekly' } });
    expect(onView).toHaveBeenLastCalledWith('1y', 'weekly');
    a.unmount();

    const onView2 = vi.fn();
    const b = render(
      <SupportLevels symbol="DHI" window="1m" tf="15m"
                     onSymbol={noop} onWindow={noop} onView={onView2} />);
    await ready();
    const pick = b.container.querySelectorAll('select')[0];
    fireEvent.change(pick, { target: { value: 'weekly' } });
    // 1 month is not a zoom weekly bars can fill — weekly's own pin, 1 year.
    expect(onView2).toHaveBeenLastCalledWith('1y', 'weekly');
    fireEvent.change(pick, { target: { value: '1min' } });
    expect(onView2).toHaveBeenLastCalledWith('6m', '1min');
  });

  it('NEGATIVE: a served list without the new frames renders without them', async () => {
    const older = SERVED.filter((r) => r.key !== '1min' && r.key !== 'weekly');
    mockFetch({ ...PAYLOAD, timeframes: older });
    const { container } = render(
      <SupportLevels symbol="DHI" window="1y" tf="daily"
                     onSymbol={noop} onWindow={noop} onView={noop} />);
    await ready();
    const vals = Array.from(container.querySelectorAll('select')[0].querySelectorAll('option'))
      .map((o) => o.getAttribute('value'));
    expect(vals).toEqual(older.map((r) => r.key));
    expect(vals).not.toContain('1min');
    expect(vals).not.toContain('weekly');
  });

  it('NEGATIVE: the page prints the served words, not the mirror', async () => {
    const renamed = SERVED.map((r) => ({ ...r, label: `S-${r.key}` }));
    mockFetch({ ...PAYLOAD, timeframes: renamed });
    const { container } = render(
      <SupportLevels symbol="DHI" window="1y" tf="daily"
                     onSymbol={noop} onWindow={noop} onView={noop} />);
    await ready();
    const texts = Array.from(container.querySelectorAll('select')[0].querySelectorAll('option'))
      .map((o) => o.textContent);
    expect(texts[0]).toBe(`S-1min · ${SERVED[0].span}`);
    expect(texts[texts.length - 1]).toBe(`S-weekly · ${SERVED[SERVED.length - 1].span}`);
    const mirrorLabels = SERVED.map((r) => r.label);
    for (const t of texts) for (const m of mirrorLabels) expect(t).not.toContain(m);
  });

  it("the weekly payload's served note is printed verbatim", async () => {
    const note = 'Levels are read from this chart’s own weekly bars — SERVED-NOTE still forming.';
    mockFetch({ ...PAYLOAD, timeframe: 'weekly', note });
    render(
      <SupportLevels symbol="DHI" window="1y" tf="weekly"
                     onSymbol={noop} onWindow={noop} onView={noop} />);
    await ready();
    expect(screen.getByText(note)).toBeTruthy();
  });
});
