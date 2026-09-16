import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SepaCandidatePage } from './SepaCandidate';
import { SepaCandidateCard } from '../components/SepaCandidateCard';
import { GrowthChip } from '../components/GrowthChip';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';

/* 🚀 Ajay 2026-09-16: "Can you add the explosive growth pill in to the
 * individual tickers."
 *
 * The pill on the ticker page must be the SAME chip on the SAME read the
 * Chart Maps boards use — never a second definition of growth. So the rules
 * under test are:
 *   1. a name served by /growth/tags wears the pill in the ticker page header;
 *   2. NEGATIVE: a name the board does not carry renders no pill at all — not
 *      a placeholder, not an empty span;
 *   3. NEGATIVE: a /growth/tags outage leaves the page standing (the chip is
 *      decoration on somebody else's board);
 *   4. the text on the ticker page is character-for-character what the boards
 *      show for the same read.
 */

const TAGS = {
  AXTI: { sales: 145.9, eps: 185.0, refused: false },
  FF: { sales: 120.7, eps: 204.2, refused: true },
};

const ROW = (symbol: string) => ({
  symbol,
  name: `${symbol} Inc`,
  score: 72,
  rating: 'B',
  last_close: 31.5,
  trend: { passed: 8, checks: {} },
});

/** The page opens a live-quote SSE stream on mount; jsdom has no EventSource.
 *  A no-op stand-in keeps the stream out of the way of the chip. */
class NoopEventSource {
  close() {}
  addEventListener() {}
  removeEventListener() {}
  onmessage: unknown = null;
  onerror: unknown = null;
}

/** Route every endpoint the page reaches for; only /growth/tags matters here.
 *  `growth` === 'fail' makes THAT one call reject, everything else keeps
 *  answering — the outage case. */
function stubFetch(growth: 'ok' | 'empty' | 'fail' = 'ok') {
  vi.stubGlobal('EventSource', NoopEventSource);
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/growth/tags')) {
      if (growth === 'fail') throw new Error('growth board down');
      return { ok: true, json: async () => ({ tags: growth === 'ok' ? TAGS : {} }) } as unknown as Response;
    }
    if (url.includes('/sepa/candidate/')) {
      const sym = decodeURIComponent(url.split('/sepa/candidate/')[1].split('?')[0]);
      return { ok: true, json: async () => ({ base: ROW(sym) }) } as unknown as Response;
    }
    // Everything else on this very busy page answers "nothing served" rather
    // than throwing, so a failure in this test is about the chip and not
    // about a stub shape the page's other panels did not expect.
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

describe('growth pill on the individual ticker page', () => {
  // The hook caches the board map at module level (one fetch per page load
  // for every chip on screen) — each test starts from a cold cache.
  beforeEach(() => _resetGrowthTagsCache());
  afterEach(() => { vi.unstubAllGlobals(); });

  it('renders the pill for a name the growth board carries', async () => {
    stubFetch('ok');
    renderTicker('AXTI');
    await waitFor(() => expect(screen.getByText('🚀 +146%')).toBeTruthy());
    expect(screen.getByText('🚀 +146%').className).toContain('cm-badge-growth');
  });

  it('NEGATIVE: renders nothing — not a placeholder — for a name off the board', async () => {
    stubFetch('ok');
    const { container } = renderTicker('GOOGL');
    // Wait for the page's own header to exist, so "no pill" is a real read
    // and not just "nothing has rendered yet".
    await waitFor(() => expect(container.querySelector('.sepa-card__flags')).toBeTruthy());
    // The page's own "🚀 breakout" tab owns the rocket too, so the read is
    // the chip's own text and its two classes — nothing at all was added.
    await waitFor(() => expect(document.body.textContent).not.toMatch(/🚀 [+-]/));
    expect(container.querySelector('.cm-badge-growth')).toBeNull();
    expect(container.querySelector('.cm-badge-bad')).toBeNull();
    expect(container.querySelector('.sepa-card__flags')!.textContent).not.toMatch(/🚀/);
  });

  it('NEGATIVE: an empty growth board is the same as no board at all', async () => {
    stubFetch('empty');
    const { container } = renderTicker('AXTI');
    await waitFor(() => expect(container.querySelector('.sepa-card__flags')).toBeTruthy());
    expect(container.querySelector('.cm-badge-growth')).toBeNull();
  });

  it('NEGATIVE: a failed growth fetch does not break the page', async () => {
    stubFetch('fail');
    const { container } = renderTicker('AXTI');
    await waitFor(() => expect(container.querySelector('.sepa-card__flags')).toBeTruthy());
    expect(screen.getAllByText('AXTI').length).toBeGreaterThan(0);
    expect(container.querySelector('.cm-badge-growth')).toBeNull();
  });

  it('a refused name reads ⛔ here exactly as it does on the boards', async () => {
    stubFetch('ok');
    const { container } = renderTicker('FF');
    await waitFor(() => expect(screen.getByText('🚀 +121%')).toBeTruthy());
    const el = container.querySelector('.cm-badge-bad')!;
    expect(el).toBeTruthy();
    expect(el.getAttribute('title')).toMatch(/REFUSE/);
  });

  it('the pill text equals what the boards show for the SAME read', async () => {
    stubFetch('ok');
    // The boards' rendering of this symbol, from the same component + hook.
    const board = render(<GrowthChip symbol="AXTI" />);
    await waitFor(() => expect(board.container.querySelector('span')).toBeTruthy());
    const boardEl = board.container.querySelector('span')!;
    board.unmount();

    const { container } = renderTicker('AXTI');
    await waitFor(() => expect(container.querySelector('.cm-badge-growth')).toBeTruthy());
    const pageEl = container.querySelector('.cm-badge-growth')!;

    expect(pageEl.textContent).toBe(boardEl.textContent);
    expect(pageEl.getAttribute('title')).toBe(boardEl.getAttribute('title'));
    expect(pageEl.className).toBe(boardEl.className);
  });
});

describe('growth pill on the SEPA list card', () => {
  beforeEach(() => { _resetGrowthTagsCache(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  function renderCard(symbol: string) {
    return render(
      <MemoryRouter>
        <SepaCandidateCard row={ROW(symbol) as any} onSelect={() => {}} />
      </MemoryRouter>,
    );
  }

  it('the card carries the same pill, on the same shared read', async () => {
    stubFetch('ok');
    const { container } = renderCard('AXTI');
    await waitFor(() => expect(container.querySelector('.cm-badge-growth')).toBeTruthy());
    expect(container.querySelector('.cm-badge-growth')!.textContent).toBe('🚀 +146%');
  });

  it('NEGATIVE: an off-board name adds nothing to the card', async () => {
    stubFetch('ok');
    const { container } = renderCard('GOOGL');
    await waitFor(() => expect(container.querySelector('.sepa-card__sym-line')).toBeTruthy());
    await waitFor(() => expect(document.body.textContent).not.toMatch(/🚀 \+/));
    expect(container.querySelector('.cm-badge-growth')).toBeNull();
  });
});
