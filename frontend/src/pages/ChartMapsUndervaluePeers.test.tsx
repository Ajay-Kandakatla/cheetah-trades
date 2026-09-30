/* 🏷️ Under Value vs peers on the real Chart Maps page (2026-09-29).
 *
 * Ajay, verbatim: "create me another tab where valuations are wrong based on
 * analytics …" then "Use the same tab actually". The real page, fetch mocked:
 * the toggle renders from the served block, a click writes `?uv=peers` into
 * the URL AND the next fetch, 💎 removes it, and `uv` never rides elsewhere.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ChartMaps from './ChartMaps';

const OPTIONS = [{ key: 'psg', label: '💎 P/S ÷ growth' }, { key: 'peers', label: '🏷️ vs peers' }];
const block = (view: string) => ({
  param: 'uv', view, default: 'psg', options: OPTIONS, measured: false,
  header: view === 'peers' ? '🏷️ served header' : null,
  note: view === 'peers' ? '🏷️ UNMEASURED served note' : null,
  counts: view === 'peers' ? { passed: 0 } : null,
  constants: view === 'peers' ? { min_peers: 5 } : null,
});
const payload = (url: string) => {
  const peers = url.includes('uv=peers');
  const base: Record<string, unknown> = { tab: 'undervalue', tiles: [], note: 'n' };
  if (url.includes('tab=undervalue')) base.undervalue_view = block(peers ? 'peers' : 'psg');
  return base;
};
function stub() {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => payload(url) } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const boardCalls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls
  .map((c) => String(c[0])).filter((u) => u.includes('/chart-maps?'));
const lastBoardCall = () => boardCalls()[boardCalls().length - 1];

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /><Loc /></MemoryRouter>);
const search = () => screen.getByTestId('loc').textContent || '';

describe('🏷️ Under Value vs peers — same tab toggle', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
    vi.stubGlobal('fetch', stub());
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('default: no uv= sent, the served toggle renders with 💎 pressed', async () => {
    page('/chart-maps?tab=undervalue');
    await waitFor(() => expect(screen.getByTestId('cm-uv-board')).toBeTruthy());
    expect(boardCalls().every((u) => !u.includes('uv='))).toBe(true);
    expect(screen.getByTestId('cm-uv-view-psg').getAttribute('aria-pressed')).toBe('true');
    expect(screen.queryByTestId('cm-uv-header')).toBeNull();
  });

  it('clicking 🏷️ refetches with uv=peers and writes it into the URL', async () => {
    page('/chart-maps?tab=undervalue');
    await waitFor(() => expect(screen.getByTestId('cm-uv-view-peers')).toBeTruthy());
    fireEvent.click(screen.getByTestId('cm-uv-view-peers'));
    await waitFor(() => expect(lastBoardCall()).toContain('uv=peers'));
    await waitFor(() => expect(search()).toContain('uv=peers'));
    await waitFor(() => expect(screen.getByTestId('cm-uv-header').textContent).toBe('🏷️ served header'));
    expect(screen.getByTestId('cm-uv-view-peers').getAttribute('aria-pressed')).toBe('true');
  });

  it('?uv=peers then 💎 removes uv from the URL and the fetch', async () => {
    page('/chart-maps?tab=undervalue&uv=peers');
    await waitFor(() => expect(screen.getByTestId('cm-uv-header')).toBeTruthy());
    expect(lastBoardCall()).toContain('uv=peers');
    fireEvent.click(screen.getByTestId('cm-uv-view-psg'));
    await waitFor(() => expect(search()).not.toContain('uv='));
    await waitFor(() => expect(lastBoardCall()).not.toContain('uv='));
  });

  it('NEGATIVE: ?uv=bogus sends no uv', async () => {
    page('/chart-maps?tab=undervalue&uv=bogus');
    await waitFor(() => expect(screen.getByTestId('cm-uv-board')).toBeTruthy());
    expect(boardCalls().every((u) => !u.includes('uv='))).toBe(true);
  });

  it('NEGATIVE: another tab never sends uv and shows no toggle', async () => {
    page('/chart-maps?tab=gabbar&uv=peers');
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    expect(boardCalls().every((u) => !u.includes('uv='))).toBe(true);
    expect(screen.queryByTestId('cm-uv-board')).toBeNull();
  });

  it('?uv=peers&phase=reached sends both', async () => {
    page('/chart-maps?tab=undervalue&uv=peers&phase=reached');
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    const u = lastBoardCall();
    expect(u).toContain('uv=peers');
    expect(u).toContain('phase=reached');
  });
});
