import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { GgShortInterestLabel } from './GgShortInterestLabel';
import { _resetShortInterestCache } from '../hooks/useShortInterest';

/* 🎾 GgShortInterestLabel (2026-11-08) — the SERVED chip text as a label, the SERVED title on hover, through the same
 * hook + lib as the house chip; NOTHING when there is nothing served (never a zero). fetch is stubbed — no mock of the
 * hook or the lib, so the real one-bulk-GET path runs. */

const TITLE = '🩳 Short interest — FINRA settlement 2026-10-15 (published ~2026-10-24). A count of open short positions — not a forecast.';
const ITEMS: Record<string, unknown> = {
  VJET: { symbol: 'VJET', status: 'ok', chip: '🩳 SI 21.9% float · 1.0d · 10/15', title: TITLE, rows: [] },
  ZNB: { symbol: 'ZNB', status: 'ok', chip: '🩳 SI 185.6K sh · 1.0d · 10/15', title: TITLE, rows: [] },
  OLD: { symbol: 'OLD', status: 'stale', chip: '🩳 SI 30.6% shs out · 5.0d · 8/31 · stale', title: 'served stale title', rows: [] },
  MISS: { symbol: 'MISS', status: 'no_record', chip: null, title: 'Short interest: no FINRA record on file for MISS — not read.', rows: [] },
  BLANK: { symbol: 'BLANK', status: 'ok', chip: '   ', title: TITLE, rows: [] },
};

function stub(ok = true) {
  const f = vi.fn(async (url: string) => {
    if (!ok) throw new Error('down');
    const q = decodeURIComponent(String(url).split('symbols=')[1] || '').split(',');
    const items: Record<string, unknown> = {};
    for (const s of q) if (ITEMS[s]) items[s] = ITEMS[s];
    return { ok: true, json: async () => ({ items, n: Object.keys(items).length, max_symbols: 200 }) } as unknown as Response;
  });
  vi.stubGlobal('fetch', f);
  return f;
}
const settle = (f: ReturnType<typeof vi.fn>) =>
  waitFor(() => expect(f).toHaveBeenCalled()).then(() => new Promise((r) => setTimeout(r, 0)));

describe('GgShortInterestLabel', () => {
  beforeEach(() => _resetShortInterestCache());
  afterEach(() => vi.unstubAllGlobals());

  it('prints the served chip text verbatim with the served title, bold-label classes, the given testid', async () => {
    stub();
    render(<GgShortInterestLabel symbol="VJET" testid="gg-si-label-VJET" />);
    const el = await screen.findByTestId('gg-si-label-VJET');
    expect(el.textContent).toBe('🩳 SI 21.9% float · 1.0d · 10/15');
    expect(el.getAttribute('title')).toBe(TITLE);
    expect(el.className).toBe('cm-note gg-line gg-si-label');
    expect(el.tagName).toBe('DIV');
  });

  it('the served share-count fallback prints as served (HIS CALL #10 — never hidden here)', async () => {
    stub();
    render(<GgShortInterestLabel symbol="ZNB" testid="t" />);
    expect((await screen.findByTestId('t')).textContent).toBe('🩳 SI 185.6K sh · 1.0d · 10/15');
  });

  it('a stale read carries gg-si-stale and the SERVED stale word (typed nowhere here)', async () => {
    stub();
    render(<GgShortInterestLabel symbol="OLD" testid="t" />);
    const el = await screen.findByTestId('t');
    expect(el.className).toContain('gg-si-stale');
    expect(el.textContent).toBe('🩳 SI 30.6% shs out · 5.0d · 8/31 · stale');
    expect(el.getAttribute('title')).toBe('served stale title');
  });

  it('NEGATIVE: an ok read is never marked stale', async () => {
    stub();
    render(<GgShortInterestLabel symbol="VJET" testid="t" />);
    expect((await screen.findByTestId('t')).className).not.toContain('gg-si-stale');
  });

  it('NEGATIVE: a no_record block renders nothing', async () => {
    const f = stub();
    const { container } = render(<GgShortInterestLabel symbol="MISS" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: an empty served chip renders nothing', async () => {
    const f = stub();
    const { container } = render(<GgShortInterestLabel symbol="BLANK" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: an absent symbol renders nothing, never a 0', async () => {
    const f = stub();
    const { container } = render(<GgShortInterestLabel symbol="NOPE" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
    expect(container.textContent).not.toMatch(/0%|0\.0/);
  });

  it('NEGATIVE: a failed fetch renders nothing and does not throw', async () => {
    const f = stub(false);
    const { container } = render(<GgShortInterestLabel symbol="VJET" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: nothing before the read lands (loading is not a zero)', () => {
    stub();
    const { container } = render(<GgShortInterestLabel symbol="VJET" testid="t" />);
    expect(container.innerHTML).toBe('');
  });

  it('three labels on one screen cost ONE bulk GET', async () => {
    const f = stub();
    render(<>
      <GgShortInterestLabel symbol="VJET" testid="a" />
      <GgShortInterestLabel symbol="ZNB" testid="b" />
      <GgShortInterestLabel symbol="OLD" testid="c" />
    </>);
    await screen.findByTestId('c');
    expect(f).toHaveBeenCalledTimes(1);
    expect(String(f.mock.calls[0][0])).toContain('/short-interest/map?symbols=');
  });
});
