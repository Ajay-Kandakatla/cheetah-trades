import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AlertsPage, TAPE_CONTROL_PASS } from './Alerts';
import { _resetAlertHistoryCache } from '../hooks/useAlertHistory';

/* 🎚️ tape_control — the LIVE capture (BUILD_SPEC7 §4 WP-M, 2026-10-16).
 *
 * Ajay 2026-10-16: "Can you add a watcher tape for IREN please." then "I wwant you to alert
 * me when the Buyers are winning in tape for IREN today."
 *
 * Renders the REAL /alerts page with the body of ONE read-only GET /alerts/status taken from
 * the live api after the deploy (__fixtures__/alerts_status_tape_control_2026_10_16.json —
 * never typed by hand; SKIPPED while the file is absent). Only fetch is stubbed; the clock is
 * pinned to the capture's own `now_et` so the page's ET day is the capture's day. Asserts the
 * 🎚️ row prints the served pins[0].text and note verbatim (the FE composes no pin sentence),
 * and that no NaN / undefined / None / the b-word reaches the DOM. */

async function fsMod(): Promise<any> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  return mod?.default || mod;
}
const root = (globalThis as any).process?.cwd?.() || '.';
async function readJsonIfPresent(rel: string): Promise<any | null> {
  const fs = await fsMod();
  const p = `${root}/${rel}`;
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null;
}

const LIVE: any = await readJsonIfPresent('src/pages/__fixtures__/alerts_status_tape_control_2026_10_16.json');
const STATUS: any = LIVE?.status ?? null;
const TC: any = STATUS?.passes?.[TAPE_CONTROL_PASS.key] ?? null;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

function stubFetch() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/alerts/status')) return { ok: true, status: 200, json: async () => clone(STATUS) } as Response;
    return { ok: true, status: 200, json: async () => ({ rows: [] }) } as Response;
  }));
}
const draw = () => render(<MemoryRouter initialEntries={['/alerts']}><AlertsPage /></MemoryRouter>);

const BANNED = /NaN|undefined|\bNone\b|\[object Object\]/;
const BWORD = new RegExp(['b', 'ounce'].join(''), 'i');

describe('🎚️ tape_control row — the LIVE /alerts/status capture (2026-10-16)', () => {
  beforeEach(() => {
    if (STATUS?.now_et) vi.useFakeTimers({ now: new Date(STATUS.now_et), toFake: ['Date'] });
    _resetAlertHistoryCache();
  });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it.skipIf(!LIVE)('the capture carries its recipe, its stamp and the served 🎚️ pass', () => {
    expect(typeof LIVE._recipe).toBe('string');
    expect(LIVE._recipe).toContain('/alerts/status');
    expect(LIVE.captured_et).toMatch(/^\d\d:\d\d:\d\d$/);
    expect(TC, 'passes.tape_control').toBeTruthy();
    expect(Array.isArray(TC.pins) && TC.pins.length).toBeGreaterThan(0);
    expect(typeof TC.pins[0].text).toBe('string');
    expect(typeof TC.note).toBe('string');
  });

  it.skipIf(!TC)('the real page prints pins[0].text and the note verbatim inside the 🎚️ row', async () => {
    stubFetch();
    draw();
    const p0 = TC.pins[0];
    const pin = await screen.findByTestId(`tape-control-pin-${p0.symbol}`);
    const box = screen.getByTestId('tape-control');
    expect(within(box).getByTestId(`tape-control-pin-${p0.symbol}`)).toBe(pin);
    expect(within(pin).getByTestId('tape-control-pin-text').textContent).toBe(p0.text);
    expect(screen.getByTestId('tape-control-note').textContent).toBe(TC.note);
    const a = within(pin).getByTestId('tape-control-pin-link');
    expect(a.textContent).toBe(p0.symbol);
    expect(a.getAttribute('href')).toBe(p0.url);
    expect(within(box).getByTestId('pass-tape_control')).toBeTruthy();
  });

  it.skipIf(!TC)('NEGATIVE: never NaN / undefined / None / the b-word in the rendered page', async () => {
    stubFetch();
    const { container } = draw();
    await screen.findByTestId(`tape-control-pin-${TC.pins[0].symbol}`);
    const row = screen.getByTestId('tape-control').textContent || '';
    expect(row).not.toMatch(BANNED);
    expect(row).not.toMatch(BWORD);
    const txt = container.textContent || '';
    expect(txt).not.toMatch(BANNED);
    expect(txt).not.toMatch(BWORD);
  });
});
