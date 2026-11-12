import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LukTrackRecord } from './LukTrackRecord';
import { _resetGgLiteCache } from './GgEntryTape';
import type { LukTrackRecord as LukTr, LukTrRow } from '../lib/luk';
import type { GgTrCell } from '../lib/gajjala';
import src from './LukTrackRecord.tsx?raw';

/* 🥇 Luk's 🏁 — the R of a stop measured from the ACTUAL fill (spec rec157 WP-1, 2026-11-11).
 * Ajay 2026-11-11 (relayed by the main session): "Do your receommendations".
 * The server derives a stopped row's R from the fill (luk/ledger.py stop_r) and serves the words; the component prints
 * the served exit cell and the served counts line VERBATIM and composes no R. SYNTHETIC block in the served shape.
 * NEGATIVES: no −1.0R appears that the payload did not carry; the component source holds no R arithmetic. */

const ID = '2026-11-06|RCX|opening_range_high|aplus';
const cell = (state: string, text: string): GgTrCell => ({ state, text, sub_text: null, provisional: false });
const ROW = {
  id: ID, key: ID.replace(/\|/g, '-'), date: '2026-11-06', symbol: 'RCX', setup: 'opening_range_high',
  setup_label: '🔔 Opening range', kind: 'aplus', line: 'live', kind_text: '🥇 A+ — sent to your phone',
  at_et: '09:36', at_text: '09:36 ET', rang: 'rth', rang_text: 'rang RTH', thin_text: null,
  href: '/chart-maps?tab=luk&focus=RCX', note: null, loss_text: null, broker_text: null, trader_text: null,
  dup_of: null, dup_text: null, plan_text: 'trigger 10.00 · stop 9.50 (−5.0%) · R $0.50',
  fill: cell('filled', 'filled 12.41 at 09:47'), exit: cell('loss', 'stopped 10:12 · −5.8R'),
  bucket: 'loss', bucket_text: '❌ loser', flag_text: '❌ loser', r: -5.82,
} as unknown as LukTrRow;

const TR: LukTr = {
  title: "🏁 Track record — every 🥇 A+ recorded here since 2026-11-01, graded by Luk's trade math · UNMEASURED",
  rule_text: "Stop = the alert's stop, a touch; the R of a stop is measured from the actual fill, so a fill above the trigger loses more than one R.",
  honesty: 'UNMEASURED.',
  counts_text: '1 A+ recorded · 1 filled · 1 stopped · 0 closed below the 9 EMA · 0 open · mean -5.82R over 1 closed · 1 of 30 entry weeks',
  counts: { n: 1, filled: 1, stopped: 1, open: 0, dup: 0 },
  spans: [{ key: 'all', label: 'all' }], span: 'all',
  heads: [{ key: 'symbol', label: 'Ticker' }, { key: 'setup', label: 'Setup' }, { key: 'at', label: 'Alert' },
          { key: 'kind', label: 'Kind' }, { key: 'plan', label: 'Trigger · stop · R' }, { key: 'fill', label: 'Fill' },
          { key: 'exit', label: 'Exit · R · sessions' }],
  more_text: null, empty_text: 'No 🥇 A+ in this span — none rang, none was recorded.',
  days: [{ date: '2026-11-06', label: 'Fri 11-06', rows: [ROW] }],
} as unknown as LukTr;

const mount = (t: LukTr) =>
  render(<MemoryRouter initialEntries={['/chart-maps?tab=luk&sub=track_record&span=all']}><LukTrackRecord track={t} /></MemoryRouter>);

describe('LukTrackRecord — a stop R from the fill, printed as served', () => {
  beforeEach(() => {
    _resetGgLiteCache();
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
  });
  afterEach(() => { vi.unstubAllGlobals(); _resetGgLiteCache(); });

  it('prints the served "stopped 10:12 · −5.8R" and the served counts line verbatim', () => {
    mount(TR);
    const sec = screen.getByTestId('luk-tr');
    expect(within(sec).getByText('stopped 10:12 · −5.8R')).toBeInTheDocument();
    expect(screen.getByTestId('luk-tr-counts')).toHaveTextContent(TR.counts_text as string);
    expect(screen.getByTestId('luk-tr-rule')).toHaveTextContent('measured from the actual fill');
  });

  it('NEGATIVE: never composes an R — no −1.0R on the page the payload did not carry', () => {
    mount(TR);
    const text = screen.getByTestId('luk-tr').textContent || '';
    expect(text).not.toContain('−1.0R');
    expect(text).not.toContain('-1.0R');
    expect(text).not.toContain('−5.82R');                       // the served words, not the served number
  });

  it('NEGATIVE: an unknown-R stop prints the served words, never a number of its own', () => {
    const row = { ...ROW, exit: cell('loss', 'stopped 10:12 · R not known — the fill is missing'), r: null } as unknown as LukTrRow;
    mount({ ...TR, days: [{ date: '2026-11-06', label: 'Fri 11-06', rows: [row] }] } as unknown as LukTr);
    expect(screen.getByText('stopped 10:12 · R not known — the fill is missing')).toBeInTheDocument();
    expect(screen.getByTestId('luk-tr').textContent || '').not.toMatch(/[−-]\d+(\.\d+)?R(?! over)/);
  });

  it('NEGATIVE: the component source holds no R arithmetic on a row', () => {
    expect(src).not.toMatch(/-\s*1(\.0)?\b/);
    expect(src).not.toMatch(/\.r\b/);
    expect(src).not.toMatch(/\br_now\b|\bfill_px\b|\bmean_r_closed\b/);
  });
});
