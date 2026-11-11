/* GajjalaLaneTab — 🏁 not traded on the 🚩 lane (2026-11-11).
 *
 * Ajay: "Maintain a track record when Alpaca is blocked please, Like we do in Gajjals so I know how our strategies are
 * working". A lane row with no fill carries the 🏁's own same-session cell words as the served `track_text` (muted, in
 * the P&L cell, no tint, no data-outcome), and the served `untraded` block sits under "Lane journal": span, total, one
 * line per reason (data-reason / data-in-total), the lane's own fills by the same 🏁, the honesty line. The FE prints
 * served words only — the fixture below is HAND-BUILT in the spec §3.1 shape (never a shared golden), and changing a
 * served number changes the print. NEGATIVES: no block when nothing is served, a served fault_text prints alone, a real
 * pnl_text always wins over track_text, a row with neither prints "—", the row tint stays real P&L only. */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { GajjalaLaneTab, DASH } from './GajjalaLaneTab';
import type { GajjalaPayload, GajjalaRow, GajjalaUntraded, GajjalaUntradedLine } from './GajjalaLaneTab';

const D = '2026-11-11';
const row = (sym: string, patch: Partial<GajjalaRow>): GajjalaRow => ({
  id: `GG:${D}|${sym}|bull_flag`, symbol: sym, setup: 'bull_flag', setup_label: '🚩 Bull Flag', alert_et: '10:31',
  state: 'skipped', fate_text: `skipped — ${sym}`, pnl_text: null, url: null, closable: false,
  track_state: null, track_text: null, ...patch,
});

const counts = (win: number, loss: number) => ({ win, loss, no_entry: 0, open: 0, no_plan: 0, no_risk: 0, no_time: 0,
  pending: 0, thin: 0, pct: win + loss ? Math.round((100 * win) / (win + loss)) : null });
const line = (key: string, text: string, in_total = true, n = 1): GajjalaUntradedLine => ({
  key, label: key, n, counts: counts(1, 0), dup: 0, no_row: 0, late: 0, in_total, provisional: false, text });

const UNTRADED: GajjalaUntraded = {
  title: "🏁 Not traded — the same alerts graded by GG's trade math",
  span_text: 'Every lane row without a fill since 2026-10-20 — 17 rows · the 🏁 same-session column · one count per stock per day',
  total: { ...line('total', "All not traded (the lane's 'out' rows apart): 11 · 6 wins · 2 losses · 75% won · 1 open"), n: 11 },
  lines: [
    line('broker_gap', "broker_gap words: 2 · 2 wins · 0 losses · 100% won", true, 2),
    line('floor', 'house safety floors (your switch): 4 · 3 wins · 1 loss · 75% won', true, 4),
    line('never_triggered', "never triggered for the lane: 4 · 1 win · 0 losses · 100% won · 2 no entry · not in the total — the lane's own rule said out", false, 4),
  ],
  traded: line('traded', 'Lane fills, the same 🏁 grade: 16 · 7 wins · 9 losses · 44% won', true, 16),
  honesty: 'A 🏁 grade is not a fill: it enters at the trigger from 09:45 ET and wins at +1R before the stop. UNMEASURED, not advice.',
  fault_text: null,
};

const WOULD = 'not traded · 🏁 WIN · best +6.2% — +1R at 10:44 · close +3.9% · at the alert\'s stop, which Alpaca refuses';
const FIXTURE: GajjalaPayload = {
  date: D, armed: true, mode: 'paper', as_of: `${D}T17:00:00Z`,
  status: { caps_text: 'caps words', enabled: true, floors: 'house' },
  today: [
    row('DBGI', { skip_kind: 'broker_gap', track_state: 'win', track_text: WOULD }),
    row('AMC', { state: 'closed', pnl_usd: -6.6, fate_text: 'stop 3.24 at 12:53 ET', pnl_text: '−$6.60 · −2.00R' }),
    row('BOTH', { state: 'closed', pnl_usd: 5, pnl_text: '+$5.00 · +1.00R', track_state: 'win', track_text: 'not traded · 🏁 should never print' }),
    row('NONE', {}),
  ],
  recent: [],
  journal: { text: 'journal words' },
  untraded: UNTRADED,
};

function stub(body: GajjalaPayload) {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(() =>
    Promise.resolve({ ok: true, status: 200, json: async () => body })));
}
const view = () => render(<MemoryRouter><GajjalaLaneTab /></MemoryRouter>);
const rowOf = (sym: string) => document.querySelector(`[data-row-id^="GG:${D}|${sym}|"]`) as HTMLElement;
const ready = async () => { await screen.findByText('caps words'); };

beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('🏁 not traded — the row cell', () => {
  it('an untraded row prints the served track_text verbatim in gg-lane-pnl > gg-lane-would, muted, with its state', async () => {
    stub(FIXTURE);
    view();
    await ready();
    const pnl = within(rowOf('DBGI')).getByTestId('gg-lane-pnl');
    const would = within(pnl).getByTestId('gg-lane-would');
    expect(would.textContent).toBe(WOULD);
    expect(pnl.textContent).toBe(WOULD);
    expect(would.getAttribute('data-state')).toBe('win');
    expect(would.style.fontStyle).toBe('italic');
    expect(would.style.color).toContain('--text-sub');
  });

  it('NEGATIVE: an untraded row carries NO data-outcome and no tint (the tint stays real P&L only)', async () => {
    stub(FIXTURE);
    view();
    await ready();
    const tr = rowOf('DBGI');
    expect(tr.getAttribute('data-outcome')).toBeNull();
    expect(tr.style.background).toBe('');
    expect(tr.style.boxShadow).toBe('');
    // the real loss keeps its red tint and its served P&L
    expect(rowOf('AMC').getAttribute('data-outcome')).toBe('loss');
    expect(within(rowOf('AMC')).getByTestId('gg-lane-pnl').textContent).toBe('−$6.60 · −2.00R');
    expect(within(rowOf('AMC')).queryByTestId('gg-lane-would')).toBeNull();
  });

  it('NEGATIVE: a row with BOTH pnl_text and track_text prints pnl_text only', async () => {
    stub(FIXTURE);
    view();
    await ready();
    const pnl = within(rowOf('BOTH')).getByTestId('gg-lane-pnl');
    expect(pnl.textContent).toBe('+$5.00 · +1.00R');
    expect(within(pnl).queryByTestId('gg-lane-would')).toBeNull();
    expect(document.body.textContent).not.toContain('should never print');
  });

  it('NEGATIVE: a row with neither prints "—"; a blank track_text prints "—" too', async () => {
    stub({ ...FIXTURE, today: [...FIXTURE.today!, row('BLANK', { track_text: '   ', track_state: 'win' })] });
    view();
    await ready();
    for (const sym of ['NONE', 'BLANK']) {
      const pnl = within(rowOf(sym)).getByTestId('gg-lane-pnl');
      expect(pnl.textContent).toBe(DASH);
      expect(within(pnl).queryByTestId('gg-lane-would')).toBeNull();
    }
  });

  it('changing a served number in track_text changes the print (the FE typed nothing)', async () => {
    const moved = WOULD.replace('+6.2%', '+7.7%');
    stub({ ...FIXTURE, today: [row('DBGI', { skip_kind: 'broker_gap', track_state: 'win', track_text: moved })] });
    view();
    await ready();
    expect(within(rowOf('DBGI')).getByTestId('gg-lane-would').textContent).toBe(moved);
    expect(document.body.textContent).not.toContain('+6.2%');
  });
});

describe('🏁 not traded — the block under Lane journal', () => {
  it('prints title, span, total, each line (data-reason / data-in-total), the traded line, then the honesty — in order', async () => {
    stub(FIXTURE);
    view();
    await ready();
    expect(screen.getByText(UNTRADED.title!)).toBeTruthy();
    const span = screen.getByTestId('gg-lane-untraded-span');
    const total = screen.getByTestId('gg-lane-untraded-total');
    const ul = screen.getByTestId('gg-lane-untraded-lines');
    const traded = screen.getByTestId('gg-lane-untraded-traded');
    const honesty = screen.getByTestId('gg-lane-untraded-honesty');
    expect(span.textContent).toBe(UNTRADED.span_text);
    expect(total.textContent).toBe(UNTRADED.total!.text);
    expect(traded.textContent).toBe(UNTRADED.traded!.text);
    expect(honesty.textContent).toBe(UNTRADED.honesty);
    const lis = Array.from(ul.querySelectorAll('li'));
    expect(lis.map((l) => l.getAttribute('data-reason'))).toEqual(['broker_gap', 'floor', 'never_triggered']);
    expect(lis.map((l) => l.getAttribute('data-in-total'))).toEqual(['true', 'true', 'false']);
    expect(lis.map((l) => l.textContent)).toEqual(UNTRADED.lines!.map((l) => l.text));
    const order = [span, total, ul, traded, honesty];
    for (let i = 1; i < order.length; i++) {
      expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
    // the block sits right after the Lane journal
    const journal = screen.getByTestId('gg-lane-journal');
    expect(journal.compareDocumentPosition(span) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // never summed into the journal: the journal prints its own served words only
    expect(journal.textContent).toBe('journal words');
  });

  it('an in_total false line is muted; an in_total line is not', async () => {
    stub(FIXTURE);
    view();
    await ready();
    const ul = screen.getByTestId('gg-lane-untraded-lines');
    const out = ul.querySelector('[data-reason="never_triggered"]') as HTMLElement;
    const inn = ul.querySelector('[data-reason="floor"]') as HTMLElement;
    expect(out.style.color).toContain('--text-sub');
    expect(inn.style.color).toBe('');
  });

  it('lines and the block carry overflowWrap anywhere + minWidth 0 (430 px phone)', async () => {
    stub(FIXTURE);
    view();
    await ready();
    const block = screen.getByTestId('gg-lane-untraded');
    const ul = screen.getByTestId('gg-lane-untraded-lines');
    for (const el of [block, ul, ...Array.from(ul.querySelectorAll('li'))] as HTMLElement[]) {
      expect(el.style.overflowWrap).toBe('anywhere');
      expect(['0', '0px']).toContain(el.style.minWidth);
    }
    expect(block.style.fontSize).toBe('13px');
  });

  it('changing a served number in a line, the total or the traded line changes the print', async () => {
    const u: GajjalaUntraded = {
      ...UNTRADED,
      total: { ...UNTRADED.total!, text: UNTRADED.total!.text!.replace('75% won', '71% won') },
      lines: [line('floor', 'house safety floors (your switch): 5 · 4 wins · 1 loss · 80% won', true, 5)],
      traded: { ...UNTRADED.traded!, text: UNTRADED.traded!.text!.replace('44% won', '41% won') },
    };
    stub({ ...FIXTURE, untraded: u });
    view();
    await ready();
    expect(screen.getByTestId('gg-lane-untraded-total').textContent).toContain('71% won');
    expect(screen.getByTestId('gg-lane-untraded-traded').textContent).toContain('41% won');
    const lis = screen.getByTestId('gg-lane-untraded-lines').querySelectorAll('li');
    expect(lis.length).toBe(1);
    expect(lis[0].textContent).toContain('80% won');
    expect(document.body.textContent).not.toMatch(/75% won|44% won/);
  });

  it('NEGATIVE: no `untraded` served → no block, no crash', async () => {
    const { untraded: _u, ...rest } = FIXTURE;
    void _u;
    stub(rest);
    view();
    await ready();
    expect(screen.getByTestId('gg-lane-journal').textContent).toBe('journal words');
    expect(screen.queryByText(UNTRADED.title!)).toBeNull();
    for (const id of ['gg-lane-untraded', 'gg-lane-untraded-fault', 'gg-lane-untraded-span', 'gg-lane-untraded-lines',
                      'gg-lane-untraded-traded', 'gg-lane-untraded-honesty']) {
      expect(screen.queryByTestId(id)).toBeNull();
    }
    stub({ ...rest, untraded: null });
    expect(document.body.textContent).not.toMatch(/NaN|null|undefined/);
  });

  it('NEGATIVE: a served fault_text prints alone (role=status) — no span, total, lines, traded or honesty', async () => {
    stub({ ...FIXTURE, untraded: { ...UNTRADED, fault_text: '🏁 grades not read on this open — the lane rows are unchanged' } });
    view();
    await ready();
    const f = screen.getByTestId('gg-lane-untraded-fault');
    expect(f.getAttribute('role')).toBe('status');
    expect(f.textContent).toBe('🏁 grades not read on this open — the lane rows are unchanged');
    for (const id of ['gg-lane-untraded', 'gg-lane-untraded-span', 'gg-lane-untraded-total', 'gg-lane-untraded-lines',
                      'gg-lane-untraded-traded', 'gg-lane-untraded-honesty']) {
      expect(screen.queryByTestId(id)).toBeNull();
    }
  });

  it('NEGATIVE: an empty served block (no untraded doc yet) prints the span words, no total line, no list, still the traded line', async () => {
    stub({ ...FIXTURE, untraded: { ...UNTRADED, total: null, lines: [], span_text: 'No lane row without a fill yet.' } });
    view();
    await waitFor(() => expect(screen.getByTestId('gg-lane-untraded-span').textContent).toBe('No lane row without a fill yet.'));
    expect(screen.queryByTestId('gg-lane-untraded-total')).toBeNull();
    expect(screen.queryByTestId('gg-lane-untraded-lines')).toBeNull();
    expect(screen.getByTestId('gg-lane-untraded-traded').textContent).toBe(UNTRADED.traded!.text);
    expect(document.body.textContent).not.toMatch(/NaN|null|undefined/);
  });
});

describe('🏁 not traded — source guard', () => {
  it('UntradedBlock types no digit, no b-word, no book; the P&L cell reads row.track_text (with self-tests)', async () => {
    const src = (await import('./GajjalaLaneTab.tsx?raw')).default as string;
    const at = src.indexOf('function UntradedBlock(');
    expect(at).toBeGreaterThan(0);
    const end = src.indexOf('\n}\n', at);
    expect(end).toBeGreaterThan(at);
    const block = src.slice(at, end);
    expect(block).not.toMatch(/\d/);
    expect(src).not.toMatch(/boun/i);
    expect(src).not.toMatch(/TLSW|TTLAC|Minervini p\./);
    for (const need of ['row.track_text', 'untraded.lines', 'untraded.traded', 'untraded.fault_text', 'untraded.honesty']) {
      expect(src).toContain(need);
    }
    // NEGATIVE self-tests: the guard catches a typed digit.
    expect(`${block}\n<li>6 wins</li>`).toMatch(/\d/);
  });
});
