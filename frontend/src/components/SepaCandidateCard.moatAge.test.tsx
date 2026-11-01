import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SepaCandidateCard } from './SepaCandidateCard';

/* 🏰 2026-10-11: a Yahoo 429 used to blank the moat; the backend now keeps
 * the last good moat, so the chip's tooltip says when it was read.
 *   1. a moat with `as_of` prints "Moat data as of …" in the tooltip;
 *   2. the line also rides the tier-0 ("no data") tooltip — the ternary
 *      precedence trap: `a ? b : c + x` appends x to the else branch only;
 *   3. NEGATIVE: a legacy moat without `as_of` prints no date line.
 */

class NoopEventSource {
  close() {}
  addEventListener() {}
  removeEventListener() {}
  onmessage: unknown = null;
  onerror: unknown = null;
}

function stubFetch() {
  vi.stubGlobal('EventSource', NoopEventSource);
  vi.stubGlobal('fetch', vi.fn(async () =>
    ({ ok: true, json: async () => null, text: async () => '' }) as unknown as Response));
}

const AS_OF = Date.UTC(2026, 9, 4, 20, 0, 0) / 1000;   // Oct 4, 2026 16:00 ET

const MOAT = (over: Record<string, unknown> = {}) => ({
  score: 72, label: 'NARROW', tier: 3, narrative: 'Narrow moat — ROE 30%.',
  components: {
    profitability: { score: 25, roe_pct: 30 },
    margins: { score: 20, gross_pct: 60, operating_pct: 30 },
    fcf: { score: 18, fcf_margin_pct: 20 },
    capital: { score: 4, net_debt_ebitda: 2.5 },
    growth: { score: 5, rev_growth_pct: 9 },
  },
  data_completeness: 6, is_partial: false, ...over,
});

const ROW = (moat: unknown) => ({
  symbol: 'KO', name: 'Coca-Cola', score: 72, rating: 'B', last_close: 70,
  trend: { passed: 8, checks: {} }, moat,
});

async function moatTitle(moat: unknown): Promise<string> {
  stubFetch();
  render(
    <MemoryRouter>
      <SepaCandidateCard row={ROW(moat) as any} onSelect={() => {}} />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByText('▸ why-buy & signals'));
  const chip = await waitFor(() => {
    const el = Array.from(document.querySelectorAll('.sepa-flag[role="button"]'))
      .find((n) => (n.textContent || '').startsWith('🏰'));
    expect(el).toBeTruthy();
    return el!;
  });
  return chip.getAttribute('title') || '';
}

describe('🏰 moat chip — as-of line', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('prints when the moat was read', async () => {
    const title = await moatTitle(MOAT({ as_of: AS_OF }));
    expect(title).toContain('Buffett-style economic moat — NARROW.');
    expect(title).toMatch(/Moat data as of Oct 4, 2026/);
  });

  it('the tier-0 "no data" tooltip carries it too', async () => {
    const title = await moatTitle(MOAT({ tier: 0, label: 'UNKNOWN', score: 0, as_of: AS_OF }));
    expect(title).toContain('No moat data');
    expect(title).toMatch(/Moat data as of Oct 4, 2026/);
  });

  it('NEGATIVE: a legacy moat without as_of prints no date line', async () => {
    const title = await moatTitle(MOAT());
    expect(title).toContain('NARROW');
    expect(title).not.toContain('Moat data as of');
  });

  it('NEGATIVE: a millisecond stamp prints no date line', async () => {
    const title = await moatTitle(MOAT({ as_of: AS_OF * 1000 }));
    expect(title).toContain('NARROW');
    expect(title).not.toContain('Moat data as of');
  });
});

/* 🏰 2026-11-01: a score of 0 FROM data is served as NONE / tier 1 (Ford) —
 * the chip reads "NONE 0" in red with the scored tooltip, never "no data". */
describe('🏰 moat chip — a zero score from data', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  async function moatChip(moat: unknown): Promise<Element> {
    stubFetch();
    render(
      <MemoryRouter>
        <SepaCandidateCard row={ROW(moat) as any} onSelect={() => {}} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByText('▸ why-buy & signals'));
    return waitFor(() => {
      const el = Array.from(document.querySelectorAll('.sepa-flag[role="button"]'))
        .find((n) => (n.textContent || '').startsWith('🏰'));
      expect(el).toBeTruthy();
      return el!;
    });
  }

  it('NONE / tier 1 with score 0 renders red "NONE 0" and the scored tooltip', async () => {
    const chip = await moatChip(MOAT({ score: 0, label: 'NONE', tier: 1, as_of: AS_OF,
      narrative: 'No measurable moat fingerprint — likely commodity / cyclical.' }));
    expect(chip.textContent).toContain('🏰 NONE 0');
    expect(chip.className).toContain('sepa-flag--bad');
    const title = chip.getAttribute('title') || '';
    expect(title).toContain('why this scored 0/100');
    expect(title).not.toContain('missing fundamentals');
  });

  it('NEGATIVE: tier 0 (0 inputs) still reads "no data", muted', async () => {
    const chip = await moatChip(MOAT({ score: 0, label: 'UNKNOWN', tier: 0, data_completeness: 0 }));
    expect(chip.textContent).toContain('🏰 no data');
    expect(chip.className).toContain('sepa-flag--muted');
  });
});
