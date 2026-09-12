import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { GrowthChip } from './GrowthChip';
import { growthChip, fetchGrowthTags, _resetGrowthTagsCache } from '../hooks/useGrowthTags';

/* 🚀 GrowthChip — Ajay 2026-09-11: "I am hoping this new list will be considerd
 * in all chart maps. Like in Deep demand scan" → "ALL TABS IN CHART MAPS".
 *
 * Three rules it must never break:
 *   1. it renders NOTHING for a name that is not on the growth board;
 *   2. a name the trading engine REFUSES reads differently from a clean one;
 *   3. a growth-board outage is silent — it must never blank somebody else's
 *      board or make a qualifying name look like it does not qualify.
 */

const TAGS = {
  AXTI: { sales: 145.9, eps: 185.0, refused: false },
  FF: { sales: 120.7, eps: 204.2, refused: true },
};

function stub(ok = true, body: unknown = { tags: TAGS }) {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok, json: async () => body,
  }) as unknown as Response));
}

describe('GrowthChip', () => {
  beforeEach(() => _resetGrowthTagsCache());
  afterEach(() => vi.unstubAllGlobals());

  it('marks a name that is on the growth board, leading with sales', async () => {
    stub();
    render(<GrowthChip symbol="AXTI" />);
    await waitFor(() => expect(screen.getByText('🚀 +146%')).toBeTruthy());
  });

  it('NEGATIVE: renders nothing for a name that is not on the board', async () => {
    stub();
    const { container } = render(<GrowthChip symbol="GOOGL" />);
    await waitFor(() => expect(container.querySelector('span')).toBeNull());
  });

  it('a refused name gets the bad tone and says so in the tooltip', async () => {
    stub();
    const { container } = render(<GrowthChip symbol="FF" />);
    await waitFor(() => expect(screen.getByText('🚀 +121%')).toBeTruthy());
    const el = container.querySelector('span')!;
    expect(el.className).toContain('cm-badge-bad');
    expect(el.getAttribute('title')).toMatch(/REFUSE/);
  });

  it('a clean name does NOT get the bad tone (negative of the above)', async () => {
    stub();
    const { container } = render(<GrowthChip symbol="AXTI" />);
    await waitFor(() => expect(screen.getByText('🚀 +146%')).toBeTruthy());
    const el = container.querySelector('span')!;
    expect(el.className).toContain('cm-badge-growth');
    expect(el.className).not.toContain('cm-badge-bad');
    expect(el.getAttribute('title')).not.toMatch(/REFUSE/);
  });

  it('NEGATIVE: a failing endpoint renders nothing and does not throw', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('down'); }));
    const { container } = render(<GrowthChip symbol="AXTI" />);
    await waitFor(() => expect(container.querySelector('span')).toBeNull());
  });

  it('NEGATIVE: a non-200 renders nothing rather than crashing the host board', async () => {
    stub(false, {});
    const { container } = render(<GrowthChip symbol="AXTI" />);
    await waitFor(() => expect(container.querySelector('span')).toBeNull());
  });

  it('fetches ONCE for a whole grid of tiles, not once per tile', async () => {
    stub();
    const spy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    render(<><GrowthChip symbol="AXTI" /><GrowthChip symbol="FF" /><GrowthChip symbol="NVDA" /></>);
    await waitFor(() => expect(screen.getByText('🚀 +146%')).toBeTruthy());
    expect(spy.mock.calls.length).toBe(1);
  });

  it('growthChip is case-insensitive and handles a missing leg', () => {
    expect(growthChip(TAGS, 'axti')?.text).toBe('🚀 +146%');
    expect(growthChip(TAGS, 'NOPE')).toBeNull();
    expect(growthChip({ X: { sales: null, eps: null } }, 'X')?.text).toBe('🚀');
  });

  it('caches the miss too — a dead endpoint is not retried per tile', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('down'); }));
    const spy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    await fetchGrowthTags();
    await fetchGrowthTags();
    await fetchGrowthTags();
    expect(spy.mock.calls.length).toBe(1);
  });
});
