import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SepaCandidatePage } from './SepaCandidate';
import { SepaCandidateCard } from '../components/SepaCandidateCard';
import { sepaAsOfParts, etClock } from '../lib/sepaAsOf';

/* Ajay 2026-10-21 "Dated info." — the page said "Data as of Oct 21, 11:03 AM"
 * at 12:0x ET: the BROWSER's fetch time labelled as the data's age, plus a
 * typed "Re-rates after 3:00 PM CT (4:00 PM ET)" (the close, not the 16:30 ET
 * re-rate). The line is now served facts only:
 *   1. "loaded {ET clock}" — the browser clock, labelled as what it is;
 *   2. "price live (…)" when the live quote carries a price;
 *   3. "SEPA read from the {as_of_close} close" from /sepa/candidate;
 *   4. the served `rerate_text`.
 *   NEGATIVE: absent facts are omitted, the old "Data as of" never prints, and
 *   the typed CT note is gone from the page and the card (source guard).
 */

const LOADED = new Date(Date.UTC(2026, 9, 21, 16, 3, 0));   // Oct 21 12:03 ET

describe('sepaAsOfParts — served facts only', () => {
  it('prints the four facts in order', () => {
    expect(sepaAsOfParts({
      loadedAt: LOADED, livePriced: true, liveAsOf: '2026-10-21T16:04:00Z',
      asOfClose: '2026-10-20', rerateText: 're-rates after 4:30 PM ET',
    })).toEqual([
      'loaded 12:03 PM ET',
      'price live (12:04 PM ET)',
      'SEPA read from the 2026-10-20 close',
      're-rates after 4:30 PM ET',
    ]);
  });

  it('prints whatever re-rate text the server sends, verbatim', () => {
    const parts = sepaAsOfParts({ loadedAt: LOADED, livePriced: false, rerateText: 're-rates after 9:05 AM ET' });
    expect(parts).toEqual(['loaded 12:03 PM ET', 're-rates after 9:05 AM ET']);
  });

  it('NEGATIVE: an older API (no close, no re-rate) prints only the load time', () => {
    const parts = sepaAsOfParts({ loadedAt: LOADED, livePriced: false });
    expect(parts).toEqual(['loaded 12:03 PM ET']);
    expect(parts.join(' · ')).not.toMatch(/Data as of|SEPA read|re-rates|3:00 PM CT/);
  });

  it('NEGATIVE: null / empty / non-string served values are omitted', () => {
    for (const bad of [null, undefined, '', '   ', 20261020, {}, []]) {
      const parts = sepaAsOfParts({ loadedAt: LOADED, livePriced: false, asOfClose: bad, rerateText: bad });
      expect(parts).toEqual(['loaded 12:03 PM ET']);
    }
  });

  it('NEGATIVE: live without a stamp says "price live" with no invented time', () => {
    expect(sepaAsOfParts({ loadedAt: LOADED, livePriced: true, liveAsOf: null }))
      .toEqual(['loaded 12:03 PM ET', 'price live']);
    expect(sepaAsOfParts({ loadedAt: LOADED, livePriced: true, liveAsOf: 'garbage' }))
      .toEqual(['loaded 12:03 PM ET', 'price live']);
  });

  // Critic fix (1) 2026-10-21: a bare-date as_of is UTC midnight — it must
  // never print as "price live (8:00 PM ET)" the evening before.
  it('NEGATIVE: a bare YYYY-MM-DD live stamp prints "price live" with no time', () => {
    const parts = sepaAsOfParts({ loadedAt: LOADED, livePriced: true, liveAsOf: '2026-10-21' });
    const live = parts.find((p) => p.startsWith('price live'))!;
    expect(live).toBe('price live');
    expect(live).not.toMatch(/AM ET|PM ET/);
    expect(parts).toEqual(['loaded 12:03 PM ET', 'price live']);
  });

  it('a full ISO / space-separated / epoch live stamp prints its clock', () => {
    const at = (liveAsOf: string | number) =>
      sepaAsOfParts({ loadedAt: LOADED, livePriced: true, liveAsOf })[1];
    expect(at('2026-10-21T16:04:00Z')).toBe('price live (12:04 PM ET)');
    expect(at('2026-10-21 16:04:00Z')).toBe('price live (12:04 PM ET)');
    expect(at(Date.UTC(2026, 9, 21, 16, 4, 0))).toBe('price live (12:04 PM ET)');
  });

  it('NEGATIVE: no live price → no "price live" claim, even with a stamp', () => {
    const parts = sepaAsOfParts({ loadedAt: LOADED, livePriced: false, liveAsOf: '2026-10-21T16:04:00Z' });
    expect(parts.join(' · ')).not.toMatch(/price live/);
  });

  it('NEGATIVE: an invalid clock prints nothing for it', () => {
    expect(etClock(new Date('nope'))).toBeNull();
    expect(etClock(null)).toBeNull();
    expect(sepaAsOfParts({ loadedAt: new Date('nope'), livePriced: false })).toEqual([]);
  });
});

class NoopEventSource {
  close() {}
  addEventListener() {}
  removeEventListener() {}
  onmessage: unknown = null;
  onerror: unknown = null;
}

const ROW = (symbol: string, over: Record<string, unknown> = {}) => ({
  symbol, name: `${symbol} Inc`, score: 72, rating: 'B', last_close: 0.75,
  trend: { passed: 8, checks: {} }, ...over,
});

function stubFetch(candidate: Record<string, unknown>) {
  vi.stubGlobal('EventSource', NoopEventSource);
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/sepa/candidate/')) {
      return { ok: true, json: async () => candidate } as unknown as Response;
    }
    return { ok: true, json: async () => null, text: async () => '' } as unknown as Response;
  }));
}

function renderTicker(symbol: string) {
  return render(
    <MemoryRouter initialEntries={[`/sepa/${symbol}`]}>
      <Routes>
        <Route path="/sepa/:symbol" element={<SepaCandidatePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('the candidate page "as of" line', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('prints the served close and re-rate, and the browser clock only as "loaded"', async () => {
    stubFetch({ base: ROW('POLA'), as_of_close: '2026-10-20', rerate_text: 're-rates after 4:30 PM ET' });
    renderTicker('POLA');
    await waitFor(() => expect(screen.getByTestId('sepa-asof').textContent).toMatch(/SEPA read/));
    const line = screen.getByTestId('sepa-asof').textContent!;
    expect(line).toMatch(/^loaded \d{1,2}:\d{2} [AP]M ET/);
    expect(line).toContain('SEPA read from the 2026-10-20 close');
    expect(line).toContain('re-rates after 4:30 PM ET');
    expect(document.body.textContent).not.toMatch(/Data as of/);
    expect(document.body.textContent).not.toMatch(/Re-rates after 3:00 PM CT/);
  });

  it('falls back to the fields on the scan row', async () => {
    stubFetch({ base: ROW('POLB', { as_of_close: '2026-10-19', rerate_text: 're-rates after 4:30 PM ET' }) });
    renderTicker('POLB');
    await waitFor(() => expect(screen.getByTestId('sepa-asof').textContent).toMatch(/2026-10-19/));
  });

  it('NEGATIVE: an older API prints only what is served — never "Data as of"', async () => {
    stubFetch({ base: ROW('POLC') });
    const { container } = renderTicker('POLC');
    await waitFor(() => expect(container.querySelector('.sepa-card__flags')).toBeTruthy());
    const line = screen.getByTestId('sepa-asof').textContent!;
    expect(line).toMatch(/^loaded \d{1,2}:\d{2} [AP]M ET$/);
    expect(line).not.toMatch(/SEPA read|re-rates|CT/);
    expect(document.body.textContent).not.toMatch(/Data as of/);
  });

  it('NEGATIVE: a null close (in-progress bar) omits the close fact', async () => {
    stubFetch({ base: ROW('POLD'), as_of_close: null, rerate_text: 're-rates after 4:30 PM ET' });
    renderTicker('POLD');
    await waitFor(() => expect(screen.getByTestId('sepa-asof').textContent).toMatch(/re-rates/));
    expect(screen.getByTestId('sepa-asof').textContent).not.toMatch(/SEPA read/);
  });
});

// Critic fix (3) 2026-10-21: "loaded" is when the VISIBLE data was fetched.
// A stale-while-revalidate paint prints the cache envelope's time — also after
// the background refresh fails — and a fresh fetch prints the fetch time.
describe('the "loaded" clock follows the visible data', () => {
  const NOW = new Date(Date.UTC(2026, 9, 21, 16, 5, 0));      // 12:05 PM ET
  const CACHED = Date.UTC(2026, 9, 21, 13, 0, 0);             //  9:00 AM ET

  function memStorage(): Storage {
    const m = new Map<string, string>();
    return {
      get length() { return m.size; },
      clear: () => m.clear(),
      getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
      key: (i: number) => Array.from(m.keys())[i] ?? null,
      removeItem: (k: string) => { m.delete(k); },
      setItem: (k: string, v: string) => { m.set(k, String(v)); },
    };
  }

  function seedCache(sym: string, data: Record<string, unknown>) {
    vi.stubGlobal('localStorage', memStorage());
    window.localStorage.setItem(`pounce.swr.sepa.candidate.${sym}`,
      JSON.stringify({ v: 1, ts: CACHED, data }));
  }

  afterEach(() => {
    cleanup(); vi.unstubAllGlobals(); vi.useRealTimers();
  });

  it('a cache-sourced paint (refresh in flight) prints the cached time', async () => {
    vi.useFakeTimers({ toFake: ['Date'] }); vi.setSystemTime(NOW);
    seedCache('POLE', { base: ROW('POLE'), rerate_text: 're-rates after 4:30 PM ET' });
    vi.stubGlobal('EventSource', NoopEventSource);
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));   // never lands
    renderTicker('POLE');
    await waitFor(() => expect(screen.getByTestId('sepa-asof').textContent).toMatch(/re-rates/));
    const line = screen.getByTestId('sepa-asof').textContent!;
    expect(line).toMatch(/^loaded 9:00 AM ET/);
    expect(line).not.toContain('12:05 PM ET');
  });

  it('NEGATIVE: a failed background refresh still prints the cached time, not the render time', async () => {
    vi.useFakeTimers({ toFake: ['Date'] }); vi.setSystemTime(NOW);
    seedCache('POLF', { base: ROW('POLF'), rerate_text: 're-rates after 4:30 PM ET' });
    vi.stubGlobal('EventSource', NoopEventSource);
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes('/sepa/candidate/')) throw new Error('offline');
      return { ok: true, json: async () => null, text: async () => '' } as unknown as Response;
    }));
    renderTicker('POLF');
    await waitFor(() => expect(screen.getByTestId('sepa-asof').textContent).toMatch(/re-rates/));
    await waitFor(() => expect(document.querySelector('.sepa-candidate-page__stale')).toBeNull());
    const line = screen.getByTestId('sepa-asof').textContent!;
    expect(line).toMatch(/^loaded 9:00 AM ET/);
    expect(line).not.toContain('12:05 PM ET');
  });

  it('a fresh fetch (no cache) prints the fetch time', async () => {
    vi.useFakeTimers({ toFake: ['Date'] }); vi.setSystemTime(NOW);
    stubFetch({ base: ROW('POLG'), rerate_text: 're-rates after 4:30 PM ET' });
    renderTicker('POLG');
    await waitFor(() => expect(screen.getByTestId('sepa-asof').textContent).toMatch(/re-rates/));
    const line = screen.getByTestId('sepa-asof').textContent!;
    expect(line).toMatch(/^loaded 12:05 PM ET/);
    expect(line).not.toContain('9:00 AM ET');
  });
});

describe('the SEPA list card re-rate note', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  function renderCard(row: Record<string, unknown>) {
    stubFetch({});
    return render(
      <MemoryRouter>
        <SepaCandidateCard row={row as any} onSelect={() => {}} />
      </MemoryRouter>,
    );
  }

  it('prints the served re-rate text', () => {
    renderCard(ROW('KO', { rerate_text: 're-rates after 4:30 PM ET' }));
    expect(screen.getByTestId('sepa-card-rerate').textContent).toBe('· re-rates after 4:30 PM ET');
  });

  it('NEGATIVE: an older row without the field prints no re-rate note', () => {
    renderCard(ROW('KO'));
    expect(screen.queryByTestId('sepa-card-rerate')).toBeNull();
    expect(document.body.textContent).not.toMatch(/Re-rates after 3:00 PM CT/);
  });
});

describe('source guard — the typed notes are gone', () => {
  async function src(rel: string): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs = mod.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/${rel}`, 'utf8');
  }

  it.each(['src/pages/SepaCandidate.tsx', 'src/components/SepaCandidateCard.tsx'])(
    '%s types no re-rate time and no "Data as of"', async (rel) => {
      const s = await src(rel);
      expect(s).not.toMatch(/Re-rates after 3:00 PM CT/);
      expect(s).not.toMatch(/Re-rates after \d/i);
      expect(s).not.toMatch(/Data as of \{/);
      expect(s).not.toMatch(/4 PM ET \/ 3 PM CT close/);
    });
});
