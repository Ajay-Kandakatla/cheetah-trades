import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AlertsPage } from './Alerts';
import { _resetAlertHistoryCache } from '../hooks/useAlertHistory';

/* 📬 Delivery receipts on the /alerts rows (2026-10-21).
 *
 * Ajay 2026-10-21, on the 15:36 ET 🚩 A+ push for NIXX that push_history recorded as sent 3 /
 * failed 0: "Oh man I did not get an A+ alert for it then today"; on the two 🧠 potentials
 * around it: "Yes POLA reached and SAIQ too". The row keeps its delivery line (the push
 * service accepting the message) and gains the SERVED `shown_on.text` (what the devices
 * reported after showing it) — printed verbatim, never recomposed on the page. */

const NOW = Date.parse('2026-10-21T20:10:00Z');            // 16:10 ET
const T = (iso: string) => Date.parse(iso) / 1000;
const base = { kind: 'gajjala_setup', url: '/chart-maps?tab=gajjala&sub=kiss_fly', source: 'push', body: 'his setup, not a buy signal' };
const ROWS = [
  { ...base, _id: 'nixx', ts: T('2026-10-21T19:36:15Z'), ts_iso: '2026-10-21T19:36:15+00:00', ticker: 'NIXX', title: '🚩 NIXX A+',
    sent: 3, failed: 0, total: 3,
    shown_on: { shown: 2, total: 3, devices: ['Mac Chrome', 'Mac Chrome'], missing: ['iPhone Safari'],
      text: 'shown on 2 of 3 devices (Mac Chrome ×2); no receipt from iPhone Safari' } },
  { ...base, _id: 'pola', ts: T('2026-10-21T20:01:09Z'), ts_iso: '2026-10-21T20:01:09+00:00', ticker: 'POLA', title: '🧠 POLA potential',
    kind: 'gajjala_potential', sent: 3, failed: 0, total: 3,
    shown_on: { shown: 3, total: 3, devices: ['Mac Chrome', 'Mac Chrome', 'iPhone Safari'], missing: [],
      text: 'shown on 3 of 3 devices (Mac Chrome ×2, iPhone Safari)' } },
  { ...base, _id: 'legacy', ts: T('2026-10-21T19:11:20Z'), ts_iso: '2026-10-21T19:11:20+00:00', ticker: 'SAIQ', title: '🧠 SAIQ potential',
    kind: 'gajjala_potential', sent: 3, failed: 0, total: 3, shown_on: null },
  { ...base, _id: 'older-api', ts: T('2026-10-21T19:00:00Z'), ts_iso: '2026-10-21T19:00:00+00:00', ticker: 'ABCD', title: '🚩 ABCD A+',
    sent: 1, failed: 1, total: 2 },
];

function stubFetch(rows: unknown[] = ROWS) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/notifications/recent')) return { ok: true, status: 200, json: async () => ({ rows }) } as Response;
    if (u.includes('/alerts/status')) return { ok: true, status: 200, json: async () => ({ in_session: false, passes: {} }) } as Response;
    return { ok: true, status: 200, json: async () => ({ rows: [] }) } as Response;
  }));
}
const draw = () => render(<MemoryRouter initialEntries={['/alerts?kinds=gajjala_setup,gajjala_potential']}><AlertsPage /></MemoryRouter>);

describe('/alerts rows — the served delivery receipt (2026-10-21)', () => {
  beforeEach(() => { vi.useFakeTimers({ now: new Date(NOW), toFake: ['Date'] }); _resetAlertHistoryCache(); });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('prints the served shown_on.text VERBATIM beside the delivery line, amber while a device is silent', async () => {
    stubFetch();
    draw();
    const rows = await screen.findAllByTestId('alert-row');
    const nixx = rows.find((r) => r.textContent?.includes('NIXX'))!;
    expect(within(nixx).getByText('delivered to 3/3 devices')).toBeInTheDocument();
    const line = within(nixx).getByTestId('alert-shown-on');
    expect(line).toHaveTextContent('shown on 2 of 3 devices (Mac Chrome ×2); no receipt from iPhone Safari');
    expect(line.style.color).toBe('rgb(245, 158, 11)');          // AMBER — the phone has not reported
    // NEGATIVE: the page composes no sentence of its own from the counts
    expect(nixx.textContent).not.toMatch(/2 of 3 devices shown|shown: 2|2\/3 shown/);
  });

  it('every device reported → the same served words, dim', async () => {
    stubFetch();
    draw();
    const rows = await screen.findAllByTestId('alert-row');
    const pola = rows.find((r) => r.textContent?.includes('POLA'))!;
    const line = within(pola).getByTestId('alert-shown-on');
    expect(line).toHaveTextContent('shown on 3 of 3 devices (Mac Chrome ×2, iPhone Safari)');
    expect(line.style.color).not.toBe('rgb(245, 158, 11)');
  });

  it('NEGATIVE: a row from before receipts (shown_on null) and an older API (no key) print no receipt line at all', async () => {
    stubFetch();
    draw();
    const rows = await screen.findAllByTestId('alert-row');
    for (const sym of ['SAIQ', 'ABCD']) {
      const row = rows.find((r) => r.textContent?.includes(sym))!;
      expect(within(row).queryByTestId('alert-shown-on')).toBeNull();
      expect(row.textContent).not.toMatch(/shown on|no receipt/);
    }
    // the delivery line is untouched on both
    expect(within(rows.find((r) => r.textContent?.includes('ABCD'))!).getByText('delivered to 1/2 devices')).toBeInTheDocument();
    expect(screen.queryByText(/undefined|NaN|\[object Object\]/)).toBeNull();
  });
});
