/* 🧬 Medical events on the ticker page's Catalyst tab (/sepa/KOD?tab=catalyst).
 * The served UNMEASURED note and Setup ride on every state that has a
 * payload — zero events included (critic #12) — and a fetch error is one muted
 * line that leaves the rest of the tab (📰 NewsReadButton) standing. */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { MedicalEventsPanel } from './MedicalEventsPanel';
import { NewsReadButton } from './NewsReadButton';
import { KOD_ROW, MED_SYMBOL_EMPTY, MED_SYMBOL_KOD, UNMEASURED_NOTE } from '../lib/__fixtures__/medicalCatalysts';

function stubFetch(payload: unknown, status = 200) {
  const fn = vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/catalysts/medical/')) return { ok: status === 200, status, json: async () => payload };
    return { ok: true, status: 200, json: async () => ({ rows: [] }) };
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}
const draw = (sym = 'KOD') =>
  render(<MemoryRouter initialEntries={[`/sepa/${sym}?tab=catalyst`]}><MedicalEventsPanel symbol={sym} /></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🧬 MedicalEventsPanel', () => {
  it('KOD timeline: the served row, note and setup', async () => {
    const fn = stubFetch(MED_SYMBOL_KOD);
    draw();
    const panel = await screen.findByTestId('mc-panel');
    expect(within(panel).getByText('🧬 Medical events')).toBeInTheDocument();
    expect(screen.getByTestId('mc-panel-unmeasured')).toHaveTextContent(UNMEASURED_NOTE);
    expect(screen.getByTestId('mc-panel-setup')).toHaveTextContent('Setup: pending study');
    expect(within(panel).getByText('Phase 3 topline positive')).toBeInTheDocument();
    expect(within(panel).getByText('ophthalmology')).toBeInTheDocument();
    expect(panel.textContent).toContain('close +178.0%');
    const url = fn.mock.calls.map((c) => String(c[0])).find((u) => u.includes('/catalysts/medical/'))!;
    expect(url).toContain('/catalysts/medical/KOD?days=180');
  });

  it('NEGATIVE: the row on its own timeline carries no "🧬 timeline" self-link', async () => {
    stubFetch(MED_SYMBOL_KOD);
    draw();
    await screen.findByTestId('mc-panel');
    expect(screen.queryByRole('link', { name: '🧬 timeline' })).toBeNull();
  });

  it('newest first, whatever order the payload arrives in', async () => {
    const older = { ...KOD_ROW, event_key: 'KOD|designation|2026-06-02', session_date: '2026-06-02',
      label: 'Fast Track designation', published_at_et: '2026-06-02T07:00:00-04:00' };
    stubFetch({ ...MED_SYMBOL_KOD, events: [older, KOD_ROW] });
    draw();
    await screen.findByTestId('mc-panel');
    const keys = screen.getAllByTestId('mc-row').map((r) => r.getAttribute('data-event-key'));
    expect(keys).toEqual(['KOD|topline_positive|2026-09-28', 'KOD|designation|2026-06-02']);
  });

  it('zero events → "No medical catalysts recorded…" AND the note + setup still render', async () => {
    stubFetch(MED_SYMBOL_EMPTY);
    draw('AAPL');
    expect(await screen.findByTestId('mc-panel-empty')).toHaveTextContent('No medical catalysts recorded for AAPL since Sep 29');
    expect(screen.getByTestId('mc-panel-unmeasured')).toHaveTextContent(UNMEASURED_NOTE);
    expect(screen.getByTestId('mc-panel-setup')).toHaveTextContent('Setup: pending study');
    expect(screen.queryAllByTestId('mc-row')).toHaveLength(0);
  });

  it('NEGATIVE: zero events before the first lap never prints a made-up date', async () => {
    stubFetch({ ...MED_SYMBOL_EMPTY, tracking_since: null });
    draw('AAPL');
    const empty = await screen.findByTestId('mc-panel-empty');
    expect(empty).toHaveTextContent('first full roster pass has not finished');
    expect(empty.textContent).not.toMatch(/since/);
  });

  it('NEGATIVE: a fetch error is one muted line and the rest of the tab (NewsReadButton) stays', async () => {
    stubFetch({}, 503);
    render(
      <MemoryRouter>
        <NewsReadButton symbol="KOD" />
        <MedicalEventsPanel symbol="KOD" />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('mc-panel-error')).toHaveTextContent('🧬 Medical events unavailable (HTTP 503)');
    expect(screen.getByRole('button', { name: /What’s the news say/ })).toBeInTheDocument();
    expect(screen.queryByTestId('mc-panel')).toBeNull();
  });

  it('NEGATIVE: no "bounce" and no Stop / Target / Entry on the panel', async () => {
    stubFetch(MED_SYMBOL_KOD);
    const { container } = draw();
    await screen.findByTestId('mc-panel');
    container.querySelectorAll('details').forEach((d) => { d.open = true; });
    expect(container.textContent).not.toMatch(/bounce/i);
    expect(container.textContent).not.toMatch(/\b(Stop|Target|Entry)\b/);
  });
});
