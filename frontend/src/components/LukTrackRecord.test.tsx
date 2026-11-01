import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LukTrackRecord } from './LukTrackRecord';
import type { LukTrackRecord as LukTr } from '../lib/luk';

/* 🥇 Luk's 🏁 Track record (2026-11-01, luk spec §3.9 / §3.13). The served rows (plan / fill / exit / flags / rang
 * texts), the 3R / 5R flags, an open row, the folded rule ⓘ, the served span chips — and the 📈 toggle that fetches
 * the LUK tape route only. NEGATIVES: never a 🚩 route; nothing fetched until the toggle; the FE types no number. */

const ID_A = '2026-11-03|AAA|pullback_reversal|aplus';
const ID_B = '2026-11-03|BBB|opening_range_high|aplus';
const ID_C = '2026-11-04|CCC|inside_day_pdh|aplus';
const TR: LukTr = {
  title: '🏁 Track record — every 🥇 A+ recorded here since 2026-11-01, graded by Luk\'s trade math · UNMEASURED',
  rule_text: 'Fill = the first 1-minute bar at least 30 s after the alert trading at or above the trigger. Exit = the stop or the first daily close below the 9 EMA.',
  honesty: 'Every row is a shadow record — none reached your phone. UNMEASURED until the strategy lab\'s 30-entry-week floor (1 entry weeks so far).',
  counts_text: '3 A+ recorded · 3 filled · 1 stopped · 1 closed below the 9 EMA · 1 open · mean +0.65R over 2 closed · 1 of 30 entry weeks',
  spans: [{ key: 'today', label: 'today' }, { key: '5d', label: '5 sessions' }, 'all'], span: '5d',
  days: [
    { date: '2026-11-04', label: 'Wed 11-04', rows: [
      { id: ID_C, symbol: 'CCC', setup_label: 'Inside day', at_et: '13:10', plan_text: 'trigger 30.00 · stop 29.10 (−3.0%) · R $0.90',
        fill_text: 'filled 30.02 at 13:11', exit_text: 'open · +0.8R after 2 sessions', flags_text: '', rang_text: 'rang RTH' }] },
    { date: '2026-11-03', label: 'Tue 11-03', rows: [
      { id: ID_A, symbol: 'AAA', href: '/sepa/AAA', setup_label: 'Pullback reversal', at_et: '09:52', plan_text: 'trigger 12.40 · stop 11.98 (−3.4%) · R $0.42',
        fill_text: 'filled 12.41 at 09:53', exit_text: 'closed below the 9 EMA on 11-05 · +2.3R · 3 sessions', flags_text: '+3R reached', rang_text: 'rang RTH' },
      { id: ID_B, symbol: 'BBB', setup_label: 'Opening range', at_et: '09:36', plan_text: 'trigger 5.10 · stop 4.95 (−2.9%) · R $0.15',
        fill_text: 'filled 5.11 at 09:37', exit_text: 'stopped 10:12 · −1.0R', flags_text: '+3R and +5R reached', rang_text: 'rang RTH' }] },
  ],
};

const TAPE = { id: ID_A, ticker: 'AAA', tf: '5m', lite: false, n_bars: 2, title: 'AAA tape', tone: 'up', note: null,
  aria: 'AAA entry tape', as_of: '2026-11-05', read: 'filled 12.41 · closed below the 9 EMA · +2.3R',
  bars: [{ t: 1762180200, c: 12.4, s: 'rth' }, { t: 1762180500, c: 12.6, s: 'rth' }], rules: [], dots: [], hlines: [] };

const mount = (t: LukTr | null, path = '/chart-maps?tab=luk&sub=track_record&span=5d') =>
  render(<MemoryRouter initialEntries={[path]}><LukTrackRecord track={t} /></MemoryRouter>);

describe('LukTrackRecord', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('the served title, counts, honesty and the rule folded under ⓘ', () => {
    mount(TR);
    expect(screen.getByTestId('luk-tr-title')).toHaveTextContent(TR.title);
    expect(screen.getByTestId('luk-tr-counts')).toHaveTextContent(TR.counts_text!);
    expect(screen.getByTestId('luk-tr-honesty')).toHaveTextContent(TR.honesty!);
    const rule = screen.getByTestId('luk-tr-rule') as HTMLDetailsElement;
    expect(rule.open).toBe(false);
    expect(rule).toHaveTextContent(TR.rule_text!);
  });

  it('rows by served day, with plan / fill / exit / flags / rang texts verbatim', () => {
    const { container } = mount(TR);
    const days = Array.from(container.querySelectorAll('[data-testid^="luk-tr-day-"]')).map((d) => d.getAttribute('data-testid'));
    expect(days).toEqual(['luk-tr-day-2026-11-04', 'luk-tr-day-2026-11-03']);
    expect(screen.getByTestId(`luk-tr-plan_text-${ID_A}`)).toHaveTextContent('trigger 12.40 · stop 11.98 (−3.4%) · R $0.42');
    expect(screen.getByTestId(`luk-tr-fill_text-${ID_A}`)).toHaveTextContent('filled 12.41 at 09:53');
    expect(screen.getByTestId(`luk-tr-exit_text-${ID_A}`)).toHaveTextContent('closed below the 9 EMA on 11-05 · +2.3R · 3 sessions');
    expect(screen.getByTestId(`luk-tr-flags_text-${ID_A}`)).toHaveTextContent('+3R reached');
    expect(screen.getByTestId(`luk-tr-flags_text-${ID_B}`)).toHaveTextContent('+3R and +5R reached');
    expect(screen.getByTestId(`luk-tr-exit_text-${ID_B}`)).toHaveTextContent('stopped 10:12 · −1.0R');
  });

  it('an open row prints its served open text; NEGATIVE: an empty flags_text prints no flag cell', () => {
    mount(TR);
    expect(screen.getByTestId(`luk-tr-exit_text-${ID_C}`)).toHaveTextContent('open · +0.8R after 2 sessions');
    expect(screen.queryByTestId(`luk-tr-flags_text-${ID_C}`)).toBeNull();
  });

  it('the served span chips: the served span is current; a chip keeps the luk sub and sets span', () => {
    mount(TR);
    expect(screen.getByTestId('luk-tr-span-5d').getAttribute('aria-current')).toBe('true');
    expect(screen.getByTestId('luk-tr-span-today').getAttribute('aria-current')).toBeNull();
    expect(screen.getByTestId('luk-tr-span-all')).toHaveTextContent('all');
    const href = screen.getByTestId('luk-tr-span-today').getAttribute('href')!;
    const q = new URLSearchParams(href.split('?')[1]);
    expect(q.get('tab')).toBe('luk'); expect(q.get('sub')).toBe('track_record'); expect(q.get('span')).toBe('today');
  });

  it('the 📈 toggle fetches the LUK tape path only, then draws the served tape', async () => {
    const f = vi.fn(async (_url: string) => ({ ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(TAPE)) }));
    vi.stubGlobal('fetch', f);
    mount(TR);
    expect(f).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId(`luk-tape-toggle-${ID_A}`));
    await waitFor(() => expect(screen.getByTestId('gg-tape-read')).toHaveTextContent(TAPE.read));
    const urls = f.mock.calls.map((c) => String(c[0]));
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain(`/chart-maps/luk/entry-tape?id=${encodeURIComponent(ID_A)}`);
    // NEGATIVE: never a 🚩 route (GgEntryTape gets the preset payload, so its own fetch never runs)
    for (const u of urls) expect(u).not.toMatch(/gajjala/);
  });

  it('NEGATIVE: a toggle closed again unmounts the tape; a failed tape read shows the glyph, never a 🚩 retry', async () => {
    const f = vi.fn(async () => ({ ok: false, status: 404, json: async () => ({}) }));
    vi.stubGlobal('fetch', f);
    mount(TR);
    fireEvent.click(screen.getByTestId(`luk-tape-toggle-${ID_B}`));
    await waitFor(() => expect(screen.getByTestId('luk-tape')).toHaveTextContent('—'));
    for (const c of f.mock.calls) expect(String((c as unknown[])[0])).toMatch(/\/chart-maps\/luk\/entry-tape/);
    fireEvent.click(screen.getByTestId(`luk-tape-toggle-${ID_B}`));
    expect(screen.queryByTestId('luk-tape')).toBeNull();
  });

  it('NEGATIVE: no rows → the served empty line; no block → nothing; no number the payload lacks', () => {
    const r = mount({ ...TR, days: [], empty_text: 'no A+ recorded on this span yet' });
    expect(screen.getByTestId('luk-tr-empty')).toHaveTextContent('no A+ recorded on this span yet');
    r.unmount();
    const r2 = mount(null);
    expect(r2.container.innerHTML).toBe('');
    r2.unmount();
    const { container } = mount(TR);
    const served = JSON.stringify(TR);
    for (const n of (container.textContent || '').match(/\d+(?:[.,]\d+)*/g) || []) expect(served).toContain(n);
  });
});
