import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AlertsPage } from './Alerts';
import { _resetAlertHistoryCache } from '../hooks/useAlertHistory';

/* 📡 The live-feed line on /alerts (GG LIVE 2026-11-09, spec §3.1 / WP-A).
 *
 * Ajay 2026-11-09: "I would like the autopilot to be continously monitored or live tracked … make it more live
 * with websockets". The first step is honesty about the one Massive socket: /alerts prints the SERVED `word`
 * from /live/feed-status (and the SERVED `admin_word` when the server sends it — admins only). The page
 * composes no feed sentence: no lag, no kick count, no "ms" of its own. */

const NOW = Date.parse('2026-11-10T15:10:00Z');            // 10:10 ET
const KICKED = '📡 Reconnecting — another connection on this Massive key took the stream (3 times today). The 1-minute check keeps running.';
const ADMIN = 'lag 412 ms · 3 kicks today · 96 s blind';

function stubFetch(feed: { ok: boolean; body?: unknown } | 'throw') {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/live/feed-status')) {
      if (feed === 'throw') throw new Error('network down');
      return { ok: feed.ok, status: feed.ok ? 200 : 503, json: async () => feed.body ?? {} } as Response;
    }
    if (u.includes('/alerts/status')) return { ok: true, status: 200, json: async () => ({ in_session: true, passes: {} }) } as Response;
    return { ok: true, status: 200, json: async () => ({ rows: [] }) } as Response;
  }));
}
const draw = () => render(<MemoryRouter initialEntries={['/alerts']}><AlertsPage /></MemoryRouter>);

describe('/alerts — the served live-feed word (2026-11-09)', () => {
  beforeEach(() => { vi.useFakeTimers({ now: new Date(NOW), toFake: ['Date'] }); _resetAlertHistoryCache(); });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('prints the served word verbatim at the top of the status strip', async () => {
    stubFetch({ ok: true, body: { state: 'kicked', word: KICKED, kicks_today: 3, lag_ms_p50: 412.4, blind_s_today: 96.2 } });
    draw();
    const line = await screen.findByTestId('live-feed-word');
    expect(line).toHaveTextContent(KICKED);
    const strip = screen.getByRole('region', { name: 'Alert passes' });
    expect(strip.firstElementChild).toBe(line);
    // NEGATIVE: no admin_word served → none shown, and the page builds no lag / kicks string from the numbers
    expect(screen.queryByTestId('live-feed-admin-word')).toBeNull();
    expect(line.textContent).not.toMatch(/412|96 s|ms ·|kicks today/);
  });

  it('prints the served admin_word verbatim when the server sends it', async () => {
    stubFetch({ ok: true, body: { state: 'live', word: '📡 Live prices — last print 2 s ago', admin_word: ADMIN } });
    draw();
    expect(await screen.findByTestId('live-feed-word')).toHaveTextContent('📡 Live prices — last print 2 s ago');
    expect(screen.getByTestId('live-feed-admin-word')).toHaveTextContent(ADMIN);
  });

  it('NEGATIVE: a failed feed read prints no line (HTTP error)', async () => {
    stubFetch({ ok: false });
    draw();
    await screen.findByRole('region', { name: 'Alert passes' });
    await Promise.resolve();
    expect(screen.queryByTestId('live-feed-word')).toBeNull();
  });

  it('NEGATIVE: a network failure prints no line', async () => {
    stubFetch('throw');
    draw();
    await screen.findByRole('region', { name: 'Alert passes' });
    await Promise.resolve();
    expect(screen.queryByTestId('live-feed-word')).toBeNull();
  });

  it('NEGATIVE: an answer without a word (older api) prints nothing, even with the numbers present', async () => {
    stubFetch({ ok: true, body: { connected: true, kicks_today: 3, lag_ms_p50: 412.4, admin_word: ADMIN } });
    draw();
    await screen.findByRole('region', { name: 'Alert passes' });
    await Promise.resolve();
    expect(screen.queryByTestId('live-feed-word')).toBeNull();
    expect(screen.queryByTestId('live-feed-admin-word')).toBeNull();
  });
});
