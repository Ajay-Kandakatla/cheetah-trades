/* ⌘/Ctrl-click a stock row on 🔥 Hottest to open it in a new tab.
 *
 * Ajay 2026-09-19: "can you give me control click in this page for the stocks
 * so I can open new tab on the stock. IN hottest sector page please"
 *
 * The ticker text was ALREADY a real <a href>, so Cmd-click worked on the
 * ticker. Probing the rendered row showed why that wasn't enough:
 *
 *     ANCHORS: [ 'NVDA -> /sepa/NVDA' ]
 *     CONAME is a link?: false
 *     NUMERIC CELLS with links: 0 of 7
 *
 * One live target the width of four characters, in a row eleven columns wide.
 * He was Cmd-clicking the row and hitting dead pixels.
 *
 * The negatives below matter more than the positives: a plain click must STILL
 * do nothing (this table is sorted, scanned and drag-selected), and the row
 * must never steal a click that landed on the ★, the + Signals button or a chip.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HottestSectors } from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';

const NAME = {
  symbol: 'NVDA', name: 'NVIDIA Corporation', industry: 'Semiconductors',
  rel_1d: 1.2, rel_5d: 3.0, rel_21d: 8.0, sales_yoy: 55, sales_tier: 'explosive',
  q_eps_yoy: 60, net_margin: 50, eq_score: 80, next_earnings: null,
};
const PAYLOAD = {
  as_of: '2026-09-19', benchmark: 'RSP', sorted_by: 'rel_5d',
  legs: ['rel_1d', 'rel_5d', 'rel_21d'],
  sectors: [{
    group: 'Technology', n_full: 1, sampled_of: 1, sampled_used: 1,
    basis: 'rotation grid sample', n_measured: 1,
    rel_1d: 1, rel_5d: 2, rel_21d: 3, names: [NAME], names_total: 1,
    industries: [{
      group: 'Semiconductors', n_full: 1, ranked: true, thin: false,
      basis: 'rotation grid sample',
      rel_1d: 1, rel_5d: 2, rel_21d: 3, names: [NAME], names_total: 1,
    }],
  }],
};

function memStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(), key: (i: number) => [...m.keys()][i] ?? null,
    get length() { return m.size; },
  };
}

let openSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
  _resetSignalWatchlist();
  vi.stubGlobal('localStorage', memStorage());
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => PAYLOAD,
  }));
  openSpy = vi.fn();
  vi.stubGlobal('open', openSpy);
});
afterEach(() => { vi.unstubAllGlobals(); _resetSignalWatchlist(); });

/** Render, expand Technology → Semiconductors, return the NVDA row. */
async function row(): Promise<HTMLTableRowElement> {
  render(
    <MemoryRouter initialEntries={['/chart-maps?tab=hot_sectors']}>
      <HottestSectors />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole('button', { name: /Technology/ }));
  await waitFor(() => screen.getByRole('button', { name: /Semiconductors/ }));
  fireEvent.click(screen.getByRole('button', { name: /Semiconductors/ }));
  await waitFor(() => expect(document.querySelector('tr.hs-name')).toBeTruthy());
  return document.querySelector('tr.hs-name') as HTMLTableRowElement;
}

/** A cell with no link in it — the dead pixels he was clicking. */
function numberCell(tr: HTMLTableRowElement): HTMLElement {
  const td = [...tr.querySelectorAll('td.hs-num')].find((c) => !c.querySelector('a'));
  expect(td, 'expected a number cell with no link of its own').toBeTruthy();
  return td as HTMLElement;
}

describe('opening a stock in a new tab', () => {
  it('⌘-click on a dead part of the row opens the ticker in a new tab', async () => {
    const tr = await row();
    fireEvent.click(numberCell(tr), { metaKey: true });
    expect(openSpy).toHaveBeenCalledTimes(1);
    expect(openSpy.mock.calls[0][0]).toContain('/sepa/NVDA');
    expect(openSpy.mock.calls[0][1]).toBe('_blank');
  });

  it('Ctrl-click does the same — his words were "control click"', async () => {
    const tr = await row();
    fireEvent.click(numberCell(tr), { ctrlKey: true });
    expect(openSpy).toHaveBeenCalledTimes(1);
    expect(openSpy.mock.calls[0][0]).toContain('/sepa/NVDA');
  });

  it('middle-click opens a new tab too', async () => {
    const tr = await row();
    // This testing-library build has no fireEvent.auxClick helper, so the
    // native event is dispatched directly — which is also closer to what a
    // real middle-click does.
    fireEvent(numberCell(tr),
              new MouseEvent('auxclick', { button: 1, bubbles: true, cancelable: true }));
    expect(openSpy).toHaveBeenCalledTimes(1);
    expect(openSpy.mock.calls[0][0]).toContain('/sepa/NVDA');
  });

  it('the new tab carries ?from= so its back button still works', async () => {
    // A tab opened this way has no router state and no history. Without
    // ?from= the destination's back button hard-falls to /sepa — the exact
    // bug from 2026-08-24 ("it goes to sepa always").
    const tr = await row();
    fireEvent.click(numberCell(tr), { metaKey: true });
    expect(openSpy.mock.calls[0][0]).toMatch(/[?&]from=/);
  });

  it('opens with noopener,noreferrer', async () => {
    const tr = await row();
    fireEvent.click(numberCell(tr), { metaKey: true });
    expect(String(openSpy.mock.calls[0][2])).toContain('noopener');
  });

  it('the row says how to use it', async () => {
    const tr = await row();
    expect(tr.getAttribute('title')).toMatch(/click/i);
    expect(tr.getAttribute('title')).toMatch(/NVDA/);
    expect(tr.getAttribute('title')).toMatch(/new tab/i);
  });
});

describe('the company name is a real link now', () => {
  it('renders as an anchor to the ticker page', async () => {
    const tr = await row();
    const a = tr.querySelector('.hs-coname a') as HTMLAnchorElement | null;
    expect(a, 'company name should be a link').toBeTruthy();
    expect(a!.getAttribute('href')).toContain('/sepa/NVDA');
    expect(a!.textContent).toContain('NVIDIA Corporation');
  });

  it('the ticker itself is still its own link — nothing was taken away', async () => {
    const tr = await row();
    const hrefs = [...tr.querySelectorAll('a')].map((a) => a.getAttribute('href') || '');
    expect(hrefs.filter((h) => h.includes('/sepa/NVDA')).length).toBeGreaterThanOrEqual(2);
  });

  it('a row with no company name renders no empty link', async () => {
    (globalThis.fetch as any).mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({
        ...PAYLOAD,
        sectors: [{
          ...PAYLOAD.sectors[0],
          names: [{ ...NAME, name: null }],
          industries: [{ ...PAYLOAD.sectors[0].industries[0],
                         names: [{ ...NAME, name: null }] }],
        }],
      }),
    });
    const tr = await row();
    expect(tr.querySelector('.hs-coname a')).toBeNull();
  });
});

describe('NEGATIVES — what must NOT happen', () => {
  it('a PLAIN click on the row opens nothing and navigates nowhere', async () => {
    // He asked for the new tab, not for a new way to leave the page by
    // accident. This table gets sorted, scanned and drag-selected.
    const tr = await row();
    fireEvent.click(numberCell(tr));
    expect(openSpy).not.toHaveBeenCalled();
    expect(document.querySelector('tr.hs-name')).toBeTruthy();
  });

  it('a plain click on the row does not swallow text selection', async () => {
    const tr = await row();
    fireEvent.mouseDown(numberCell(tr));
    fireEvent.mouseUp(numberCell(tr));
    fireEvent.click(numberCell(tr));
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('⌘-click on the + Signals BUTTON does not also open a tab', async () => {
    const tr = await row();
    const btn = [...tr.querySelectorAll('button')]
      .find((b) => /signal/i.test(b.textContent || '') || /signal/i.test(b.title || ''));
    expect(btn, 'expected a Signals button in the row').toBeTruthy();
    fireEvent.click(btn!, { metaKey: true });
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('⌘-click on the ticker ANCHOR is left to the browser, not re-handled', async () => {
    // Double-handling would open two tabs.
    const tr = await row();
    const a = tr.querySelector('.hs-sym a') as HTMLAnchorElement;
    fireEvent.click(a, { metaKey: true });
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('⌘-click on the company-name link is left to the browser too', async () => {
    const tr = await row();
    const a = tr.querySelector('.hs-coname a') as HTMLAnchorElement;
    fireEvent.click(a, { metaKey: true });
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('⌘-click on any ★ / chip button in the row opens no tab', async () => {
    const tr = await row();
    for (const b of [...tr.querySelectorAll('button')]) {
      openSpy.mockClear();
      fireEvent.click(b, { metaKey: true });
      expect(openSpy, `button "${b.textContent}" triggered the row`).not.toHaveBeenCalled();
    }
  });
});
