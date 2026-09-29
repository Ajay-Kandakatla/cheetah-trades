/* 🔥 Hottest — no hidden columns (Ajay 2026-09-28: "Can you fix the
 * horizontal columns hiding").
 *
 * jsdom loads no CSS and lays nothing out, so this file pins the STRUCTURE the
 * CSS fix relies on (wrapper → scroll box → table, a sticky-able first cell on
 * every row kind, full-width rows pinned to the box) and drives the "N more
 * columns →" cue with mocked geometry. The real-browser check is
 * scripts/hottest-layout-probe.mjs, fed by the gated snapshot writer below. */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HottestSectors, HS_COLS, colLabel, colSpanOf } from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const name = (symbol: string) => ({
  symbol, name: `${symbol} Incorporated Holdings`, industry: 'Semiconductors',
  rel_1d: 0.4, rel_5d: 3.1, rel_21d: 8.2, d1_source: 'close',
  sales_yoy: 12, sales_tier: 'steady', q_eps_yoy: 30, net_margin: 11,
  eq_score: 90, eq_tier: 'steady', next_earnings: '2026-10-28', earnings_when: 'AMC',
});
const PAYLOAD = {
  as_of: '2026-09-25', benchmark: 'RSP', sorted_by: 'rel_5d', sorted_dir: 'desc',
  sorted_then_by: [], sort_max_keys: 3,
  d1: { basis: 'close', live: false, close_as_of: '2026-09-25' },
  themes: [{ group: 'quantum', n_full: 12, ranked: true, thin: false, basis: 'full membership',
             rel_1d: 0.1, rel_5d: 1, rel_21d: 2, names: [name('IONQ')], names_total: 12 }],
  sectors: [{
    group: 'Technology', n_full: 305, sampled_of: 305, sampled_used: 40,
    basis: 'rotation grid sample', n_measured: 40, rel_1d: 0.1, rel_5d: 2, rel_21d: -1,
    names: [name('NVDA')], names_total: 305,
    day_tag: { date: '2026-09-25', sector: 'Technology', symbol: 'NVDA', positive: true,
               bull: 'A long bull case that would run across every column of the table.',
               bear: 'A long bear case that would run across every column of the table.' },
    industries: [{ group: 'Semiconductors', n_full: 60, ranked: true, thin: false,
                   basis: 'rotation grid sample', rel_1d: 0.1, rel_5d: 2, rel_21d: 3,
                   names: [name('NVDA')], names_total: 60 }],
  }],
};

function stub() {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (String(url).includes('/supply-demand/bounce-room')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ rows: [] }) } as Response);
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(PAYLOAD) } as Response);
  }));
}
const view = () => render(
  <MemoryRouter>
    <EnterableFilterProvider enterableOnly={false} kind="demand" setEnterableOnly={() => {}}>
      <HottestSectors />
    </EnterableFilterProvider>
  </MemoryRouter>);

const proto = HTMLElement.prototype;
const isBox = (el: HTMLElement) => !!el.classList?.contains('hs-scroll');
/** Geometry: every header 100px wide, laid out left to right; the box is
 *  `box`px wide and its content `content(el)`px. */
function mockGeometry(box: number, content: () => number) {
  vi.spyOn(proto, 'clientWidth', 'get').mockImplementation(function (this: HTMLElement) {
    return isBox(this) ? box : 0;
  });
  vi.spyOn(proto, 'scrollWidth', 'get').mockImplementation(function (this: HTMLElement) {
    return isBox(this) ? content() : 0;
  });
  vi.spyOn(proto, 'offsetWidth', 'get').mockImplementation(function (this: HTMLElement) {
    return this.tagName === 'TH' ? 100 : 0;
  });
  vi.spyOn(proto, 'offsetLeft', 'get').mockImplementation(function (this: HTMLElement) {
    if (this.tagName !== 'TH' || !this.parentElement) return 0;
    return Array.from(this.parentElement.children).indexOf(this) * 100;
  });
}
const anyOpen = () => !!document.querySelector('.hs-disc[aria-expanded="true"]');

function memStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear(),
    key: (i: number) => [...m.keys()][i] ?? null, get length() { return m.size; },
  };
}

beforeEach(() => {
  vi.stubGlobal('localStorage', memStorage());
  _resetSignalWatchlist(); _resetBounceRoomCache();
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('the scroll structure the CSS fix relies on', () => {
  it('.hs > .hs-scrollwrap > .hs-scroll > table.hs-table', async () => {
    stub();
    const { container } = view();
    await screen.findByText(/Technology/);
    const table = container.querySelector('table.hs-table') as HTMLElement;
    expect(table.parentElement?.classList.contains('hs-scroll')).toBe(true);
    expect(table.parentElement?.parentElement?.classList.contains('hs-scrollwrap')).toBe(true);
    expect(table.parentElement?.parentElement?.parentElement?.classList.contains('hs')).toBe(true);
  });

  it('every row kind starts with a td.hs-sym, and th count == colSpanOf(data)', async () => {
    stub();
    const { container } = view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await waitFor(() => expect(container.querySelector('tr.hs-name')).toBeTruthy());
    for (const kind of ['tr.hs-theme', 'tr.hs-sector:not(.hs-theme)', 'tr.hs-industry', 'tr.hs-name']) {
      const rows = container.querySelectorAll(kind);
      expect(rows.length, kind).toBeGreaterThan(0);
      rows.forEach((r) => expect(r.firstElementChild?.classList.contains('hs-sym'), kind).toBe(true));
    }
    expect(container.querySelector('thead th')?.classList.contains('hs-sym')).toBe(true);
    expect(container.querySelectorAll('thead th').length).toBe(colSpanOf(PAYLOAD as never));
  });

  it('every full-width row wraps ALL its content in exactly one .hs-rowpin', async () => {
    stub();
    const { container } = view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByTestId('hs-expand-all'));
    fireEvent.click(screen.getByRole('button', { name: /📰 NVDA/ }));
    await waitFor(() => expect(container.querySelector('tr.hs-daytag')).toBeTruthy());
    const wide = Array.from(container.querySelectorAll('td[colspan]')) as HTMLElement[];
    // two grain labels, the day-tag, and "showing N of M" (roster + industry)
    expect(wide.length).toBeGreaterThanOrEqual(5);
    for (const td of wide) {
      expect(td.children.length, td.textContent || '').toBe(1);
      const pin = td.firstElementChild as HTMLElement;
      expect(pin.classList.contains('hs-rowpin')).toBe(true);
      expect((pin.textContent || '').trim()).toBe((td.textContent || '').trim());
    }
    // the box width the pins read is written by the hook on the scroll box —
    // NEGATIVE: and on nothing else
    const carriers = Array.from(container.querySelectorAll('[style]'))
      .filter((el) => (el.getAttribute('style') || '').includes('--hs-box-w'));
    expect(carriers.length).toBe(1);
    expect(carriers[0].classList.contains('hs-scroll')).toBe(true);
  });
});

describe('"N more columns →"', () => {
  it('names the off-right columns and scrolls on click', async () => {
    mockGeometry(800, () => 1000);
    stub();
    const { container } = view();
    await screen.findByText(/Technology/);
    const btn = await screen.findByTestId('hs-more-cols');
    expect(btn.textContent).toBe('2 more columns →');
    const last2 = HS_COLS.slice(-2).map((c) => colLabel(c.key, PAYLOAD as never));
    expect(btn.getAttribute('title')).toBe(`Off to the right: ${last2.join(', ')}`);
    expect(container.querySelector('.hs-scrollwrap')?.classList.contains('is-more-right')).toBe(true);
    const box = container.querySelector('.hs-scroll') as HTMLElement & { scrollBy: unknown };
    const spy = vi.fn();
    box.scrollBy = spy;
    fireEvent.click(btn);
    expect(spy).toHaveBeenCalledWith({ left: 640, behavior: 'smooth' });
  });

  it('NEGATIVE: a table that fits shows no button and no class', async () => {
    mockGeometry(1000, () => 1000);
    stub();
    const { container } = view();
    await screen.findByText(/Technology/);
    await new Promise((r) => setTimeout(r, 10));
    expect(screen.queryByTestId('hs-more-cols')).toBeNull();
    expect(container.querySelector('.hs-scrollwrap')?.classList.contains('is-more-right')).toBe(false);
  });

  it('opening a group that widens the TABLE brings the cue; NEGATIVE: closing removes it', async () => {
    mockGeometry(800, () => (anyOpen() ? 1200 : 800));
    stub();
    const { container } = view();
    await screen.findByText(/Technology/);
    await new Promise((r) => setTimeout(r, 10));
    expect(screen.queryByTestId('hs-more-cols')).toBeNull();
    const caret = screen.getByRole('button', { name: /▸ Technology/ });
    fireEvent.click(caret);
    await screen.findByTestId('hs-more-cols');
    expect(container.querySelector('.hs-scrollwrap')?.classList.contains('is-more-right')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /▾ Technology/ }));
    await waitFor(() => expect(screen.queryByTestId('hs-more-cols')).toBeNull());
  });
});

describe('gated snapshot for the real-browser probe', () => {
  it('writes the rendered board when HS_LAYOUT_SNAPSHOT is set (expand-all on)', async () => {
    const out = (globalThis as { process?: { env?: Record<string, string | undefined> } })
      .process?.env?.HS_LAYOUT_SNAPSHOT;
    if (!out) return;
    stub();
    const { container } = view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByTestId('hs-expand-all'));
    fireEvent.click(screen.getByRole('button', { name: /📰 NVDA/ }));
    await waitFor(() => expect(container.querySelector('tr.hs-daytag')).toBeTruthy());
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    (mod?.default || mod).writeFileSync(out, container.innerHTML, 'utf8');
  });
});
