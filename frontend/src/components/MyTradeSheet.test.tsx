/**
 * 🧾 MyTradeSheet (2026-11-23, spec accountability §3.1 / §3.5 / WP-FE step 2). Ajay 2026-11-23: "hold me accountable
 * if I am missing out any gajjalas rules".
 *
 * Pinned: the POST carries ONLY what was typed or tapped; "use the alert's stop" → stop_src "alert" with the served px;
 * a typed stop → "typed"; neither → "none" and no stop key; the served verdict_text + warn_lines print verbatim; exit =
 * {exit_px, exit_note?}; void needs a second tap. NEGATIVES: an untouched entry (the last price is a placeholder only),
 * symbol, grade, patience or discipline blocks the POST; why_b is never sent on an A+ or when untyped; a 409 prints the
 * served detail and never re-reads; a double tap sends ONE POST; an empty exit px sends nothing.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MY_TRADES_PATH, MyTradeSheet, buildTapBody } from './MyTradeSheet';
import type { MyTradesOk } from './MyDayLine';

const DATA: MyTradesOk = {
  state: 'ok', date: '2026-11-23',
  my_day: { text: 'served day', data_text: 'served data' },
  trades: [{ id: 'abc', sym: 'PFAI', verdict: 'missed', verdict_text: 'served verdict',
    checks: [
      { id: 'A2', kind: 'hard', state: 'flag', words: 'served A2 words' },
      { id: 'A5', kind: 'info', state: 'ok', words: 'served A5 words' },
      { id: 'A9', kind: 'soft', state: 'ok', words: 'served A9 words' },
      { id: 'A7', kind: 'hard', state: 'unknown', words: 'served A7 words' },
    ],
    warned_at_tap: [], alert_id: null, alert_same: { state: 'ok', text: 'served same' }, exit_text: 'served exit' }],
  voided: [{ id: 'v1', sym: 'BKYI', verdict_text: 'x' }],
  aplus_today: [{ sym: 'SCNI', setup: 'bull_flag', trigger: 2.5, stop: 2.31 }, { sym: 'TCRT', setup: 'vcp', trigger: 1, stop: null }],
};

type Call = { url: string; method: string; body: any };
let calls: Call[] = [];
const posts = () => calls.filter((c) => c.method === 'POST');

function stub(answer: { status?: number; body?: any } = {}) {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url: String(url), method: (init?.method || 'GET').toUpperCase(), body: init?.body ? JSON.parse(String(init.body)) : undefined });
    const status = answer.status ?? 200;
    return { ok: status < 400, status, json: async () => JSON.parse(JSON.stringify(answer.body ?? {})) };
  }));
}

function mount(opts: { priceOf?: (s: string) => number | null } = {}) {
  const onChanged = vi.fn();
  const onClose = vi.fn();
  render(<MyTradeSheet data={DATA} priceOf={opts.priceOf} onChanged={onChanged} onClose={onClose} />);
  return { onChanged, onClose };
}

const type = (id: string, v: string) => fireEvent.change(screen.getByTestId(id), { target: { value: v } });
const tap = (id: string) => fireEvent.click(screen.getByTestId(id));
function fillAll(skip: string[] = []) {
  if (!skip.includes('sym')) type('my-sheet-sym', 'pfai');
  if (!skip.includes('entry')) type('my-sheet-entry', '3.20');
  if (!skip.includes('grade')) tap('my-sheet-grade-A+');
  if (!skip.includes('patience')) tap('my-sheet-patience-patient');
  if (!skip.includes('discipline')) tap('my-sheet-discipline-kept');
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🧾 buildTapBody (pure)', () => {
  const base = { sym: 'x', entry: '1', stop: '', stopSrc: 'none' as const, alertStop: null, shares: '', grade: 'A+' as const,
    whyB: '', patience: 'patient' as const, discipline: 'kept' as const };
  it('only the required fields + stop_src none', () => {
    expect(buildTapBody(base)).toEqual({ sym: 'X', entry: 1, stop_src: 'none', grade: 'A+', patience: 'patient', discipline: 'kept' });
  });
  it('NEGATIVE: each required field untouched → null', () => {
    expect(buildTapBody({ ...base, sym: ' ' })).toBeNull();
    expect(buildTapBody({ ...base, entry: '' })).toBeNull();
    expect(buildTapBody({ ...base, entry: 'abc' })).toBeNull();
    expect(buildTapBody({ ...base, entry: '0' })).toBeNull();
    expect(buildTapBody({ ...base, grade: null })).toBeNull();
    expect(buildTapBody({ ...base, patience: null })).toBeNull();
    expect(buildTapBody({ ...base, discipline: null })).toBeNull();
  });
  it('NEGATIVE: why_b only on a B with words; an alert stop without a px is no stop', () => {
    expect(buildTapBody({ ...base, whyB: 'w' })).not.toHaveProperty('why_b');
    expect(buildTapBody({ ...base, grade: 'B' })).not.toHaveProperty('why_b');
    expect(buildTapBody({ ...base, grade: 'B', whyB: ' w ' })?.why_b).toBe('w');
    expect(buildTapBody({ ...base, stopSrc: 'alert', alertStop: null })).toMatchObject({ stop_src: 'none' });
    expect(buildTapBody({ ...base, stopSrc: 'alert', alertStop: null })).not.toHaveProperty('stop');
  });
});

describe('🧾 MyTradeSheet', () => {
  it('posts only what was typed / tapped (no stop, no shares, no why_b) and prints the served answer verbatim', async () => {
    stub({ body: { doc: {}, checks: [], verdict_text: 'served answer', warn_lines: ['served warn 1', 'served warn 2'] } });
    const { onChanged } = mount();
    fillAll();
    tap('my-sheet-send');
    await screen.findByTestId('my-sheet-verdict');
    expect(posts()).toHaveLength(1);
    expect(posts()[0].url).toMatch(new RegExp(`${MY_TRADES_PATH}$`));
    expect(posts()[0].body).toEqual({ sym: 'PFAI', entry: 3.2, stop_src: 'none', grade: 'A+', patience: 'patient', discipline: 'kept' });
    expect(screen.getByTestId('my-sheet-verdict').textContent).toBe('served answer');
    expect(screen.getAllByTestId('my-sheet-warn').map((e) => e.textContent)).toEqual(['served warn 1', 'served warn 2']);
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: an untouched entry blocks the POST — the last price is a placeholder only', async () => {
    stub();
    mount({ priceOf: (s) => (s === 'PFAI' ? 3.33 : null) });
    fillAll(['entry']);
    const entry = screen.getByTestId('my-sheet-entry') as HTMLInputElement;
    expect(entry.value).toBe('');
    expect(entry.placeholder).toBe('3.33');
    expect(entry.required).toBe(true);
    expect((screen.getByTestId('my-sheet-send') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.submit(screen.getByTestId('my-sheet-form'));
    await new Promise((r) => setTimeout(r, 0));
    expect(posts()).toHaveLength(0);
  });

  for (const skip of ['sym', 'grade', 'patience', 'discipline']) {
    it(`NEGATIVE: untouched ${skip} blocks the POST`, async () => {
      stub();
      mount();
      fillAll([skip]);
      fireEvent.submit(screen.getByTestId('my-sheet-form'));
      await new Promise((r) => setTimeout(r, 0));
      expect(posts()).toHaveLength(0);
    });
  }

  it('"use the alert\'s stop" → stop_src alert with the served px; a 🎯 pick sets the symbol', async () => {
    stub({ body: { verdict_text: 'v', warn_lines: [] } });
    mount();
    expect(screen.queryByTestId('my-sheet-alert-stop')).toBeNull();
    tap('my-sheet-aplus-SCNI');
    expect((screen.getByTestId('my-sheet-sym') as HTMLInputElement).value).toBe('SCNI');
    expect(screen.getByTestId('my-sheet-alert-stop').textContent).toContain('2.31');
    tap('my-sheet-alert-stop');
    fillAll(['sym']);
    tap('my-sheet-send');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toMatchObject({ sym: 'SCNI', stop: 2.31, stop_src: 'alert' });
  });

  it('NEGATIVE: an A+ without a served stop offers no alert-stop tap; a typed stop after the tap → typed', async () => {
    stub({ body: {} });
    mount();
    tap('my-sheet-aplus-TCRT');
    expect(screen.queryByTestId('my-sheet-alert-stop')).toBeNull();
    tap('my-sheet-aplus-SCNI');
    tap('my-sheet-alert-stop');
    type('my-sheet-stop', '2.25');
    fillAll(['sym']);
    tap('my-sheet-send');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toMatchObject({ stop: 2.25, stop_src: 'typed' });
  });

  it('NEGATIVE: switching symbol drops an alert stop picked for the old one', async () => {
    stub({ body: {} });
    mount();
    tap('my-sheet-aplus-SCNI');
    tap('my-sheet-alert-stop');
    type('my-sheet-sym', 'PFAI');
    fillAll(['sym']);
    tap('my-sheet-send');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body.stop_src).toBe('none');
    expect(posts()[0].body).not.toHaveProperty('stop');
  });

  it('typed shares + a B with words are sent; the why-B box shows only on a B', async () => {
    stub({ body: {} });
    mount();
    fillAll(['grade']);
    expect(screen.queryByTestId('my-sheet-why-b')).toBeNull();
    tap('my-sheet-grade-B');
    type('my-sheet-why-b', 'late but strong');
    type('my-sheet-shares', '100');
    tap('my-sheet-send');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toMatchObject({ grade: 'B', why_b: 'late but strong', shares: 100 });
  });

  it('NEGATIVE: a 409 prints the served detail and never re-reads', async () => {
    stub({ status: 409, body: { detail: 'served closed' } });
    const { onChanged } = mount();
    fillAll();
    tap('my-sheet-send');
    expect((await screen.findByTestId('my-sheet-err')).textContent).toBe('served closed');
    expect(onChanged).not.toHaveBeenCalled();
    expect(screen.queryByTestId('my-sheet-answer')).toBeNull();
  });

  it('NEGATIVE: a double tap sends ONE POST', async () => {
    stub({ body: {} });
    mount();
    fillAll();
    fireEvent.submit(screen.getByTestId('my-sheet-form'));
    fireEvent.submit(screen.getByTestId('my-sheet-form'));
    await waitFor(() => expect(posts()).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 0));
    expect(posts()).toHaveLength(1);
  });

  it('trade rows print the served words: verdict, flagged + info checks only, the 🏁 same cell, the exit text; voided listed', () => {
    stub();
    mount();
    expect(screen.getByTestId('my-trade-verdict-abc').textContent).toBe('served verdict');
    const checks = screen.getByTestId('my-trade-checks-abc').textContent || '';
    expect(checks).toContain('served A2 words');
    expect(checks).toContain('served A5 words');
    expect(checks).not.toContain('served A9 words');
    expect(checks).not.toContain('served A7 words');
    expect(screen.getByTestId('my-trade-exit-text-abc').textContent).toBe('served exit');
    expect(screen.getByText('served same')).toBeTruthy();
    expect(screen.getByTestId('my-voided-v1').textContent).toContain('BKYI');
  });

  it('exit → POST /{id}/exit with exit_px only when no note was typed; NEGATIVE an empty px sends nothing', async () => {
    stub({ body: {} });
    const { onChanged } = mount();
    tap('my-trade-exit-open-abc');
    fireEvent.submit(screen.getByTestId('my-trade-exit-form-abc'));
    await new Promise((r) => setTimeout(r, 0));
    expect(posts()).toHaveLength(0);
    type('my-trade-exit-px-abc', '3.5');
    tap('my-trade-exit-send-abc');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].url).toMatch(new RegExp(`${MY_TRADES_PATH}/abc/exit$`));
    expect(posts()[0].body).toEqual({ exit_px: 3.5 });
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it('exit with a note sends exit_note; NEGATIVE a second exit (409) prints the served detail', async () => {
    stub({ status: 409, body: { detail: 'served second exit' } });
    const { onChanged } = mount();
    tap('my-trade-exit-open-abc');
    type('my-trade-exit-px-abc', '3.5');
    type('my-trade-exit-note-abc', 'half at 1R');
    tap('my-trade-exit-send-abc');
    expect((await screen.findByTestId('my-trade-err-abc')).textContent).toBe('served second exit');
    expect(posts()[0].body).toEqual({ exit_px: 3.5, exit_note: 'half at 1R' });
    expect(onChanged).not.toHaveBeenCalled();
  });

  it('void needs a second tap → POST /{id}/void; NEGATIVE "keep" sends nothing', async () => {
    stub({ body: {} });
    mount();
    tap('my-trade-void-abc');
    tap('my-trade-void-no-abc');
    expect(posts()).toHaveLength(0);
    tap('my-trade-void-abc');
    tap('my-trade-void-yes-abc');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].url).toMatch(new RegExp(`${MY_TRADES_PATH}/abc/void$`));
  });

  it('close calls onClose and posts nothing', () => {
    stub();
    const { onClose } = mount();
    tap('my-sheet-close');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(posts()).toHaveLength(0);
  });
});
