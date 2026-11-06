import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, waitFor, cleanup, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { SepaCandidatePage } from './SepaCandidate';
import { FALLBACK_TIMEFRAMES, FALLBACK_WINDOWS } from '../lib/supportLevels';

/* 🚩 Gajjala's chart on the stock page (2026-11-06). Ajay: "If I click on Gajjalas tab stocks show me "Gajjalas chart"
 * in supply and demand of his view by default mainly.. Like if he looks at 24 hours or 2 week or anything else that is
 * what I would like to see". The 🚩 card's served href now carries `&tf=<Support-tab key>` (backend gajjala/tab.py
 * chart_href); this page reads `?tf=` / `?window=` ONCE on first paint into its plain state and hands `retired` to the
 * ONE <SupportLevels>. Mounts the REAL page (SepaCandidate.asOf.test.tsx pattern) and reads the support fetch URLs.
 *
 * THE ZOOM RULE (spec C3): the landed window is the link's own `?window=` or the house 1 year — never the picker's
 * frame pin (6m on 5m_today), because SupportLevels remembers the MOUNT window as what "The big picture" comes back to
 * (components/SupportLevels.tsx mountWindow, 2026-09-23).
 *
 * THE /sepa → /sepa LIMIT (spec C5): the route `/sepa/:symbol` keys nothing on :symbol (App.tsx), so a navigation from
 * one ticker page to another re-renders the mounted page and the lazy initialisers do NOT run again — a second `?tf=`
 * is ignored. Pinned as a NEGATIVE. A future in-page /sepa link that wants to carry a frame must remount or lift the
 * state; today no surface links /sepa → /sepa with `?tf=`. */

class NoopEventSource {
  close() {}
  addEventListener() {}
  removeEventListener() {}
  onmessage: unknown = null;
  onerror: unknown = null;
}

const ROW = (symbol: string) => ({
  symbol, name: `${symbol} Inc`, score: 72, rating: 'B', last_close: 0.75,
  trend: { passed: 8, checks: {} },
});

let support: string[] = [];

function stubFetch() {
  vi.stubGlobal('EventSource', NoopEventSource);
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const sym = url.match(/\/sepa\/candidate\/([A-Z.\-]+)/);
    if (sym) {
      return { ok: true, json: async () => ({ base: ROW(sym[1]) }) } as unknown as Response;
    }
    if (url.includes('/chart-maps/support?')) {
      support.push(url.split('?')[1]);
      return {
        ok: true,
        json: async () => ({ timeframes: FALLBACK_TIMEFRAMES, windows: FALLBACK_WINDOWS, supports: [], overhead: [] }),
      } as unknown as Response;
    }
    return { ok: true, json: async () => null, text: async () => '' } as unknown as Response;
  }));
}

let loc = { pathname: '', search: '' };
function Probe() {
  const l = useLocation();
  loc = { pathname: l.pathname, search: l.search };
  return null;
}
function GoTo({ to }: { to: string }) {
  const nav = useNavigate();
  return <button type="button" data-testid="goto" onClick={() => nav(to)}>go</button>;
}

function renderAt(path: string, goTo = '/sepa/BBB?tab=supply&tf=15m') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/sepa/:symbol" element={<SepaCandidatePage />} />
      </Routes>
      <Probe />
      <GoTo to={goTo} />
    </MemoryRouter>,
  );
}

const q = (raw: string) => new URLSearchParams(raw);
async function firstSupport(): Promise<URLSearchParams> {
  await waitFor(() => expect(support.length).toBeGreaterThan(0));
  return q(support[support.length - 1]);
}
async function nextSupport(after: number): Promise<string> {
  await waitFor(() => expect(support.length).toBeGreaterThan(after));
  return support[support.length - 1];
}
function frameSelect(): HTMLSelectElement {
  const s = document.querySelector('.sl-ctl-frame select');
  expect(s).toBeTruthy();
  return s as HTMLSelectElement;
}

describe('the stock page lands on the frame the link names (🚩 2026-11-06)', () => {
  beforeEach(() => { support = []; loc = { pathname: '', search: '' }; stubFetch(); });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('no ?tf → symbol only: daily, the house 1 year, exactly as before; no retired note', async () => {
    renderAt('/sepa/AAA');
    const p = await firstSupport();
    expect(p.toString()).toBe('symbol=AAA');
    expect(p.get('tf')).toBeNull();
    expect(p.get('window')).toBeNull();
    expect(screen.queryByTestId('sl-tf-retired')).toBeNull();
    expect(frameSelect().value).toBe('daily');
  });

  it('?tab=supply&tf=5m_today → tf=5m_today and NO window (NEGATIVE: never the picker pin window=6m)', async () => {
    renderAt('/sepa/BBB?tab=supply&tf=5m_today');
    const p = await firstSupport();
    expect(p.toString()).toBe('symbol=BBB&tf=5m_today');
    expect(p.get('window')).toBeNull();
    expect(support.every((s) => !s.includes('window=6m'))).toBe(true);
    expect(frameSelect().value).toBe('5m_today');
    expect(screen.queryByTestId('sl-tf-retired')).toBeNull();
  });

  it('land 5m_today, pick "The big picture" in the REAL picker → symbol=X exactly (daily at 1 year, NOT 6 months)', async () => {
    renderAt('/sepa/BBB?tab=supply&tf=5m_today');
    await firstSupport();
    const n = support.length;
    const sel = frameSelect();
    expect([...sel.options].map((o) => o.value)).toContain('daily');
    fireEvent.change(sel, { target: { value: 'daily' } });
    const next = await nextSupport(n);
    expect(next).toBe('symbol=BBB');
    expect(next).not.toContain('window=6m');
  });

  it('?tf=15m → tf=15m, no window', async () => {
    renderAt('/sepa/CCC?tf=15m');
    const p = await firstSupport();
    expect(p.toString()).toBe('symbol=CCC&tf=15m');
  });

  it("?tf=15m&window=2w → window=2w&tf=15m; then daily keeps the link's own 2w", async () => {
    renderAt('/sepa/CCC?tf=15m&window=2w');
    const p = await firstSupport();
    expect(p.toString()).toBe('symbol=CCC&window=2w&tf=15m');
    const n = support.length;
    fireEvent.change(frameSelect(), { target: { value: 'daily' } });
    expect(await nextSupport(n)).toBe('symbol=CCC&window=2w');
  });

  it('?window=2w&tf=daily → window=2w, no tf', async () => {
    renderAt('/sepa/DDD?window=2w&tf=daily');
    const p = await firstSupport();
    expect(p.toString()).toBe('symbol=DDD&window=2w');
  });

  it('NEGATIVE: ?tf=garbage → daily (no tf=), no retired note', async () => {
    renderAt('/sepa/EEE?tf=garbage');
    const p = await firstSupport();
    expect(p.toString()).toBe('symbol=EEE');
    expect(screen.queryByTestId('sl-tf-retired')).toBeNull();
  });

  it('NEGATIVE: ?window=garbage → the house 1 year (no window=)', async () => {
    renderAt('/sepa/EEE?window=garbage');
    const p = await firstSupport();
    expect(p.toString()).toBe('symbol=EEE');
  });

  it('a RETIRED key (5m_live) → 24h and the page says so; a later frame pick clears the note', async () => {
    renderAt('/sepa/FFF?tab=supply&tf=5m_live');
    const p = await firstSupport();
    expect(p.get('tf')).toBe('24h');
    await waitFor(() => expect(screen.getByTestId('sl-tf-retired')).toBeTruthy());
    expect(screen.getByTestId('sl-tf-retired').textContent).toContain('Last 24 hours');
    const n = support.length;
    fireEvent.change(frameSelect(), { target: { value: '15m' } });
    await nextSupport(n);
    await waitFor(() => expect(screen.queryByTestId('sl-tf-retired')).toBeNull());
  });

  it('a later pick wins over the URL: the next fetch carries the picked frame while the URL still says 5m_today', async () => {
    renderAt('/sepa/GGG?tab=supply&tf=5m_today');
    await firstSupport();
    const n = support.length;
    fireEvent.change(frameSelect(), { target: { value: '15m' } });
    const next = q(await nextSupport(n));
    expect(next.get('tf')).toBe('15m');
    expect(q(loc.search).get('tf')).toBe('5m_today');
    expect(frameSelect().value).toBe('15m');
  });

  it('setTab copies the params: ?tf=5m_today survives a tab switch and back; no support fetch with another tf', async () => {
    renderAt('/sepa/HHH?tab=supply&tf=5m_today');
    await firstSupport();
    fireEvent.click(screen.getByRole('tab', { name: 'trend' }));
    await waitFor(() => expect(q(loc.search).get('tab')).toBe('trend'));
    expect(q(loc.search).get('tf')).toBe('5m_today');
    fireEvent.click(screen.getByRole('tab', { name: 'supply / demand' }));
    await waitFor(() => expect(q(loc.search).get('tab')).toBe('supply'));
    expect(q(loc.search).get('tf')).toBe('5m_today');
    await waitFor(() => expect(document.querySelector('.sl-ctl-frame select')).toBeTruthy());
    expect(support.length).toBeGreaterThan(0);
    for (const s of support) expect(q(s).get('tf')).toBe('5m_today');
  });

  it('NEGATIVE (C5): /sepa/AAA?tf=5m_today → in-app /sepa/BBB?tf=15m keeps the page state 5m_today (read once per mount)', async () => {
    renderAt('/sepa/AAA?tab=supply&tf=5m_today', '/sepa/BBB?tab=supply&tf=15m');
    await firstSupport();
    expect(screen.queryByTestId('sl-tf-retired')).toBeNull();
    fireEvent.click(screen.getByTestId('goto'));
    await waitFor(() => expect(loc.pathname).toBe('/sepa/BBB'));
    await waitFor(() => expect(support.some((s) => q(s).get('symbol') === 'BBB')).toBe(true));
    const bbb = support.filter((s) => q(s).get('symbol') === 'BBB');
    for (const s of bbb) {
      expect(q(s).get('tf')).toBe('5m_today');
      expect(q(s).get('tf')).not.toBe('15m');
    }
    expect(screen.queryByTestId('sl-tf-retired')).toBeNull();
  });

  it('NEGATIVE: a bare ?tf=5m lands on the 24-hour frame (the alias), NOT today — why the backend sends the key', async () => {
    renderAt('/sepa/III?tf=5m');
    const p = await firstSupport();
    expect(p.get('tf')).toBe('24h');
    expect(p.get('tf')).not.toBe('5m_today');
    expect(screen.queryByTestId('sl-tf-retired')).toBeNull();
  });
});

describe('source guard — the zoom seed is never the frame pin', () => {
  it('SepaCandidate.tsx does not use windowForFrame and seeds the window with SEPA_SUPPLY_WINDOW', async () => {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs = mod.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    const s: string = fs.readFileSync(`${root}/src/pages/SepaCandidate.tsx`, 'utf8');
    expect(s).not.toContain('windowForFrame');
    expect(s).toMatch(/useState<string>\(\(\) =>\s*landed\.get\('window'\) \? parseWindow\(landed\.get\('window'\)\) : SEPA_SUPPLY_WINDOW\)/);
    expect(s).toContain('retired={supportTfRetired}');
  });
});
