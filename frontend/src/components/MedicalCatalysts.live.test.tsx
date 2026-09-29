/* 🧬 The REAL captured payload (lib/__fixtures__/medicalCatalysts.live — branch API on a scratch
 * DB after one pass over real sources with the REAL classifier, 2026-09-29 03:47 ET) through the real 🧬 board and the real ticker
 * Catalyst-tab timeline. Catches backend↔frontend shape drift the hand-written fixture cannot:
 * served labels, the roll-up, UNMEASURED / "Setup: pending study", and no NaN / undefined /
 * bounce / Stop / Target / Entry anywhere. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LIVE_BOARD, LIVE_SYMBOL_KOD } from '../lib/__fixtures__/medicalCatalysts.live';
import { MedicalCatalysts } from './MedicalCatalysts';
import { MedicalEventsPanel } from './MedicalEventsPanel';

function stubFetch() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/catalysts/medical/')) return { ok: true, status: 200, json: async () => LIVE_SYMBOL_KOD };
    if (u.includes('/catalysts/medical')) return { ok: true, status: 200, json: async () => LIVE_BOARD };
    return { ok: true, status: 200, json: async () => ({ rows: [] }) };
  }));
}
const rowOf = (key: string) => document.querySelector(`[data-event-key="${key}"]`) as HTMLElement;
const KOD = 'KOD|topline_positive|2026-09-28';

function clean(text: string) {
  expect(text).not.toMatch(/NaN|undefined|null%|\[object Object\]/);
  expect(text).not.toMatch(/bounce/i);
  expect(text).not.toMatch(/\b(Stop|Target|Entry)\b/);
}

beforeEach(() => { stubFetch(); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🧬 board on the REAL payload', () => {
  const draw = () => render(
    <MemoryRouter initialEntries={['/chart-maps?tab=catalysts&sub=medical']}><MedicalCatalysts /></MemoryRouter>);

  it('KOD: served label, area, modality, trial, HIGH, the real close / RVOL / $ volume', async () => {
    draw();
    await screen.findByTestId('mc-board');
    const kod = rowOf(KOD);
    expect(kod).toBeTruthy();
    const w = within(kod);
    expect(w.getByText('Phase 3 topline positive')).toBeInTheDocument();
    expect(w.getByText('ophthalmology')).toBeInTheDocument();
    expect(w.getByText('DAYBREAK')).toBeInTheDocument();
    expect(w.getByText('HIGH')).toBeInTheDocument();
    expect(kod.textContent).toContain('close +178.0%');
    expect(kod.textContent).toContain('RVOL 57.1×');
    expect(kod.textContent).toContain('$22.7M');
    expect(w.getByText('sources (8)')).toBeInTheDocument();
    expect(w.getByRole('link', { name: '🧬 timeline' }).getAttribute('href')).toBe('/sepa/KOD?tab=catalyst');
  });

  it('served UNMEASURED note + Setup: pending study + the served gate text', async () => {
    draw();
    expect(await screen.findByTestId('mc-unmeasured')).toHaveTextContent(LIVE_BOARD.labels.note);
    expect(screen.getByTestId('mc-unmeasured')).toHaveTextContent(/^UNMEASURED/);
    expect(screen.getByTestId('mc-setup')).toHaveTextContent('Setup: pending study');
    expect(screen.getByTestId('mc-gate')).toHaveTextContent('50-session median dollar volume ≥ $5M');
  });

  it('roll-up by area: the ophthalmology row from the served numbers', async () => {
    draw();
    await screen.findByTestId('mc-roll');
    fireEvent.click(screen.getByRole('button', { name: 'By area' }));
    const eye = screen.getByTestId('mc-roll-ophthalmology');
    const served = LIVE_BOARD.rollup.by_area.find((r) => r.key === 'ophthalmology')!;
    const cells = [...eye.querySelectorAll('td')].map((td) => td.textContent);
    expect(cells[1]).toBe(String(served.n_events));
    expect(served.small_n).toBe(false);                    // 5 unique tickers in the served window
    expect(eye).not.toHaveClass('mc-roll__row--small');
    clean(eye.textContent ?? '');
  });

  it('roll-up by area: a served small_n row (infectious_disease, 2 tickers) is greyed', async () => {
    draw();
    await screen.findByTestId('mc-roll');
    fireEvent.click(screen.getByRole('button', { name: 'By area' }));
    const served = LIVE_BOARD.rollup.by_area.find((r) => r.key === 'infectious_disease')!;
    expect(served.small_n).toBe(true);
    expect(screen.getByTestId('mc-roll-infectious_disease')).toHaveClass('mc-roll__row--small');
  });

  it('NEGATIVE: the unresolved FDA-RSS approval has no ticker link', async () => {
    draw();
    await screen.findByTestId('mc-board');
    const un = document.querySelector('[data-event-key^="UNRESOLVED:"]') as HTMLElement;
    expect(un).toBeTruthy();
    expect(within(un).getByTestId('mc-unresolved')).toBeInTheDocument();
    expect(within(un).queryAllByRole('link').filter((a) => (a.getAttribute('href') ?? '').startsWith('/sepa/'))).toHaveLength(0);
  });

  it('NEGATIVE: no NaN / undefined / bounce / Stop / Target / Entry anywhere, sources opened', async () => {
    const { container } = draw();
    await screen.findByTestId('mc-board');
    container.querySelectorAll('details').forEach((d) => { d.open = true; });
    clean(container.textContent ?? '');
    expect(screen.getAllByTestId('mc-row')).toHaveLength(LIVE_BOARD.events.length);
  });
});

describe('🧬 ticker Catalyst tab on the REAL KOD payload', () => {
  const draw = () => render(
    <MemoryRouter initialEntries={['/sepa/KOD?tab=catalyst']}><MedicalEventsPanel symbol="KOD" /></MemoryRouter>);

  it('KOD timeline: both served events, note and setup', async () => {
    const { container } = draw();
    const panel = await screen.findByTestId('mc-panel');
    expect(screen.getByTestId('mc-panel-unmeasured')).toHaveTextContent(LIVE_SYMBOL_KOD.labels.note);
    expect(screen.getByTestId('mc-panel-setup')).toHaveTextContent('Setup: pending study');
    expect(within(panel).getAllByTestId('mc-row')).toHaveLength(LIVE_SYMBOL_KOD.events.length);
    expect(within(panel).getByText('Phase 3 topline positive')).toBeInTheDocument();
    expect(panel.textContent).toContain('close +178.0%');
    container.querySelectorAll('details').forEach((d) => { d.open = true; });
    clean(container.textContent ?? '');
  });
});
