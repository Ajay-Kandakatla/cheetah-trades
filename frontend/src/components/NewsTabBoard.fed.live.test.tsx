import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LIVE from './__fixtures__/news_tab_live_2026_10_07.json';
import NewsTabBoard from './NewsTabBoard';

/* 📅 LIVE capture, not hand-built: news_tab.build() run on the
 * feat/dynamic-macro-dates branch in a write-blocked throwaway container on
 * 2026-10-07 ~06:40 ET against the real federalreserve.gov pages (the ET clock
 * pinned to 14:30 so the minutes row reads released; the 🧠 model leg stubbed;
 * no FRED key in that container, so the FRED rows are absent — the live
 * NEGATIVE "FRED down never blanks the Fed rows").
 *
 * Ajay 2026-10-07: "First today there was an FOMC event why is it not in our
 * new tab in chart maps. I want us to pull dynamic dates". */

const JUNK = ['[object Object]', 'NaN', 'undefined', '· null', 'null ·', 'Infinity', 'bounce'];

async function mount() {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => LIVE })));
  render(<MemoryRouter><NewsTabBoard /></MemoryRouter>);
  await screen.findByTestId('news-tab-board');
}

describe('live 10-07 News macro block — the Fed calendar', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('renders the FOMC minutes row with its meeting and its ET time, and no junk', async () => {
    await mount();
    const sec = screen.getByTestId('nt-section-macro');
    for (const bad of JUNK) expect(sec.textContent || '', bad).not.toContain(bad);
    const rows = Array.from(sec.querySelectorAll('[data-testid^="nt-macro-row-"]'));
    const minutes = rows.find((r) => (r.textContent || '').includes('FOMC minutes'));
    expect(minutes).toBeTruthy();
    expect(minutes!.textContent).toContain('Meeting of September 15-16');
    expect(minutes!.textContent).toContain('2:00 pm ET');
    expect(minutes!.textContent).toContain('today · released 2:00 pm ET');
  });

  it('pins the next FOMC decision 2026-10-28 and says where the dates came from', async () => {
    await mount();
    const nf = screen.getByTestId('nt-next-fomc');
    expect(nf).toHaveTextContent('Next FOMC decision');
    expect(nf).toHaveTextContent('2026-10-28');
    expect(nf).toHaveTextContent('press conference 2:30 pm ET');
    expect(screen.getByTestId('nt-macro-fed')).toHaveTextContent('federalreserve.gov');
  });

  it('every served row is dated on or after 2026-10-07', () => {
    const ev = ((LIVE as any).macro?.events || []) as Array<{ date: string }>;
    expect(ev.length).toBeGreaterThan(0);
    for (const e of ev) expect(e.date >= '2026-10-07', e.date).toBe(true);
  });
});
