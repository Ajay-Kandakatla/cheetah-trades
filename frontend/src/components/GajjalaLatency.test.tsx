/* ⏱ Speed on the 🏁 (GG LIVE P4, 2026-11-09) — GajjalaLatency.
 *
 * Ajay 2026-11-09: "… where there is a low latency monitoring on the prices
 * action changes please?" The block prints the SERVED words of
 * GET /trading/gajjala/latency verbatim (the fixture below is the payload shape
 * of backend/chart_maps/gajjala/latency.payload, the §1.4 "before" numbers),
 * renders nothing for a non-owner or on a 403 (NEGATIVE), a table on desktop
 * and stacked `label: p50 · p90 (n)` lines on a ≤ 430 px phone, no check /
 * finality block when the server serves none (NEGATIVE), the empty words on an
 * empty span, and the source types no word of its own. */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';

let userRet: any = { email: 'owner@example.com', is_admin: true };
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: false }) }));

import { GajjalaLatency, LATENCY_PATH, PHONE_MAX_PX } from './GajjalaLatency';
import type { LatencyPayload } from './GajjalaLatency';

const cells = (vals: string[]) => ['Read', 'Rang', 'Lane saw', 'Ordered', 'Filled'].map((l, i) => ({
  key: ['read', 'ring', 'seen', 'order', 'fill'][i], text: vals[i], line: `${l}: ${vals[i]}`,
}));

const FIXTURE: LatencyPayload = {
  title: '⏱ Speed — seconds after the 5-minute bar closed', span: '10d', n_alerts: 4,
  columns: [{ key: 'read', label: 'Read' }, { key: 'ring', label: 'Rang' }, { key: 'seen', label: 'Lane saw' },
    { key: 'order', label: 'Ordered' }, { key: 'fill', label: 'Filled' }],
  summary: [
    { label: 'before 2026-11-10', side: 'before', n: 3,
      cells: cells(['61.0 · 153.1 (3)', '70.6 · 176.9 (3)', '122.0 · 2,008.4 (3)', '124.0 · 2,907.2 (3)', '127.0 · 2,909.4 (3)']) },
    { label: 'since 2026-11-10', side: 'since', n: 1, cells: cells(['31.0 · 31.0 (1)', '40.0 · 40.0 (1)', '—', '—', '—']) },
  ],
  ci: [{ key: 'ring', label: 'Rang', text: 'Rang: fewer than 5 on a side — no interval (n 3 before · 1 since)' }],
  footnote: 'From the alert and lane records: p50 · p90 (n). A timing, not a result.',
  placebo_text: 'No placebo — a timing, not an outcome.', empty_text: null,
  check: { title: 'Stream vs 1-minute check — same outcome 3 · different 2', same: 3, different: 2, n: 5,
    pairs: [{ stream: 'trigger', tick: 'ordered', agree: true, n: 1, text: 'stream: trigger print first · 1-minute: ordered (1)' },
      { stream: 'trigger', tick: 'missed', agree: false, n: 1, text: 'stream: trigger print first · 1-minute: missed (1)' }],
    entry_delta_r: { n: 2, text: "1-minute fill vs the stream's trigger print: p50 +0.10 R · p90 +0.26 R (2)" },
    odd_lot_only: { n: 4, k: 1, text: 'Trigger seen only on an odd-lot print: 1 of 4' },
    // 2026-11-09 REVIEW #3: docs the stream decided leave the 1-minute comparison and are counted, never dropped
    stream_ordered: { n: 2, text: 'Stream-decided docs left out of the 1-minute comparison: 2' } },
  finality: { n: 4, text: 'Bar finality: 3 of 4 closed 5-minute bars changed between 30 s and 60 s after close (volume on 2).',
    parts: [{ part: 'regular', text: 'Regular hours — Bar finality: 2 of 3 closed 5-minute bars changed between 30 s and 60 s after close (volume on 1).' }] },
};

let fetchMock: ReturnType<typeof vi.fn>;
function serve(body: any, status = 200) {
  fetchMock = vi.fn(async () => ({ ok: status >= 200 && status < 300, status, json: async () => body }));
  (globalThis as any).fetch = fetchMock;
}
function viewport(phone: boolean) {
  (window as any).matchMedia = (q: string) => ({
    matches: phone && q === `(max-width: ${PHONE_MAX_PX}px)`, media: q,
    addEventListener: () => {}, removeEventListener: () => {},
  });
}

beforeEach(() => { userRet = { email: 'owner@example.com', is_admin: true }; viewport(false); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('⏱ GajjalaLatency', () => {
  it('owner: fetches its own span and prints every served word verbatim (desktop table)', async () => {
    serve(FIXTURE);
    render(<GajjalaLatency span="10d" />);
    await screen.findByTestId('gg-latency');
    expect(String(fetchMock.mock.calls[0][0])).toContain(`${LATENCY_PATH}?span=10d`);
    expect(screen.getByText(FIXTURE.title)).toBeTruthy();
    const table = screen.getByTestId('gg-latency-table');
    for (const c of FIXTURE.columns) expect(table.textContent).toContain(c.label);
    const before = screen.getByTestId('gg-latency-row-before');
    expect(before.textContent).toBe('before 2026-11-10' + FIXTURE.summary[0].cells.map((c) => c.text).join(''));
    expect(screen.getByTestId('gg-latency-row-since').textContent).toContain('—');
    expect(screen.getByTestId('gg-latency-ci').textContent).toBe(FIXTURE.ci![0].text);
    const chk = screen.getByTestId('gg-latency-check');
    expect(chk.textContent).toContain(FIXTURE.check!.title);
    for (const p of FIXTURE.check!.pairs) expect(chk.textContent).toContain(p.text);
    expect(chk.textContent).toContain(FIXTURE.check!.entry_delta_r!.text);
    expect(chk.textContent).toContain(FIXTURE.check!.odd_lot_only!.text);
    expect(chk.textContent).toContain(FIXTURE.check!.stream_ordered!.text);
    expect(screen.getByTestId('gg-latency-finality').textContent).toContain(FIXTURE.finality!.text);
    expect(screen.getByTestId('gg-latency-footnote').textContent).toBe(FIXTURE.footnote);
    expect(screen.queryByTestId('gg-latency-stacked')).toBeNull();
  });

  it(`phone (≤ ${PHONE_MAX_PX} px): stacked served lines, no table`, async () => {
    viewport(true);
    serve(FIXTURE);
    render(<GajjalaLatency span="10d" />);
    await screen.findByTestId('gg-latency-stacked');
    expect(screen.queryByTestId('gg-latency-table')).toBeNull();
    const lines = screen.getAllByTestId('gg-latency-line').map((n) => n.textContent);
    expect(lines.slice(0, 5)).toEqual(FIXTURE.summary[0].cells.map((c) => c.line));
    expect(lines).toContain('Rang: 70.6 · 176.9 (3)');
  });

  it('NEGATIVE: a non-owner sees nothing and nothing is fetched', async () => {
    userRet = { email: 'guest@example.com', is_admin: false };
    serve(FIXTURE);
    const { container } = render(<GajjalaLatency span="10d" />);
    await new Promise((r) => setTimeout(r, 0));
    expect(container.innerHTML).toBe('');
    expect(fetchMock).not.toHaveBeenCalled();
    userRet = null;
    const again = render(<GajjalaLatency span="10d" />);
    expect(again.container.innerHTML).toBe('');
  });

  it('NEGATIVE: a 403 renders nothing', async () => {
    serve({ detail: 'admin only' }, 403);
    const { container } = render(<GajjalaLatency span="5d" />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(container.innerHTML).toBe('');
  });

  it('empty span: the served empty words; NEGATIVE no check / finality block when none is served', async () => {
    serve({ ...FIXTURE, summary: [], ci: [], check: null, finality: null, n_alerts: 0,
      empty_text: 'No 🚩 A+ rang in this span.' });
    render(<GajjalaLatency span="today" />);
    expect((await screen.findByTestId('gg-latency-empty')).textContent).toBe('No 🚩 A+ rang in this span.');
    expect(screen.queryByTestId('gg-latency-table')).toBeNull();
    expect(screen.queryByTestId('gg-latency-check')).toBeNull();
    expect(screen.queryByTestId('gg-latency-finality')).toBeNull();
  });

  it('the source types no served word of its own, no b-word, no edge claim, no email', async () => {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    const src: string = fs.readFileSync(`${root}/src/components/GajjalaLatency.tsx`, 'utf8');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '');
    expect(code).not.toMatch(new RegExp('b' + 'ounc', 'i'));
    expect(code).not.toMatch(/\bedge\b/i);
    expect(code).not.toMatch(/@[a-z0-9.-]+\.[a-z]{2,}/i);
    for (const w of ['Speed', 'Rang', 'Lane saw', 'Bar finality', 'p50', 'A timing']) expect(code).not.toContain(w);
  });
});
