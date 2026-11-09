import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { GgAuditedCompare } from './GgAuditedCompare';

/* 🧪 K3S on the 🏁 compare (2026-11-09, gg_k3 spec §3.5 / WP-D).
 *
 * Ajay 2026-11-09: "yes change the audit as per you like that is yours I need you to make it successful and earn money
 * that is the goal".
 *
 * The compare prints the served `admitted` block — title, line, held-by line, one li per row — after the held line and
 * BEFORE recon, every string verbatim. The numeric fields below DISAGREE with the served texts (mean_r 0.123456 vs
 * "mean +0.4000R"; n 9 vs "2 🧪 only") so any FE arithmetic or formatting would show. Test data, WORDS_GGA-shaped. */

const clone = (x: any) => JSON.parse(JSON.stringify(x));

const ADMITTED = {
  title: "\u{1F9EA} only — A+ this tab admitted that \u{1F6A9} read 'broke — not A+' · UNMEASURED",
  n: 9, rang: 9, held: 9, filled: 9, win: 9, loss: 9, unfilled: 9, pending: 9, mean_r: 0.123456,
  same_day_original: 9, held_by_counts: { G1: 7 },
  held_by_text: 'held by: G1 ×1',
  text: '2 \u{1F9EA} only by K3S: 1 rang in shadow · 1 held by another rule · 1 W / 0 L of 1 filled · 0 no entry · 0 not graded yet · mean +0.4000R',
  rows: [
    { date: '2026-11-09', symbol: 'HUHU', setup: 'reversal_squeeze', setup_label: '\u{1F3BE} Reversal Squeeze', rule: 'K3S',
      kind: 'rang', held_by: null, outcome: 'win', outcome_text: 'win +0.4000R', dup_of: null, original_same_day: false,
      text: '2026-11-09 · HUHU · \u{1F3BE} Reversal Squeeze · \u{1F9EA} only by K3S · rang in shadow · win +0.4000R' },
    { date: '2026-11-09', symbol: 'LABT', setup: 'reversal_squeeze', setup_label: '\u{1F3BE} Reversal Squeeze', rule: 'K3S',
      kind: 'held', held_by: ['G1'], outcome: 'held', outcome_text: 'held', dup_of: null, original_same_day: true,
      text: '2026-11-09 · LABT · \u{1F3BE} Reversal Squeeze · \u{1F9EA} only by K3S · held by G1 · held · \u{1F6A9} rang its own \u{1F3BE} A+ later the same day — not judged here (one claim per name per day)' },
  ],
};

const BASE = {
  title: '\u{1F9EA} Audited vs \u{1F6A9} original — served title · UNMEASURED',
  sides: [
    { key: 'original', label: '\u{1F6A9} original', n: 7, filled: 5, win: 3, loss: 2, open_flat: 0, unfilled: 2, mean_r: 0.4, win_pct: 60, text: 'served original line' },
    { key: 'audited', label: '\u{1F9EA} audited', n: 4, filled: 3, win: 2, loss: 1, open_flat: 0, unfilled: 1, mean_r: 0.6667, win_pct: 66.7, text: 'served audited line' },
  ],
  held: { n: 1, text: 'served held compare line',
          rows: [{ date: '2026-11-03', symbol: 'BKYI', setup: 'bull_flag', held_by: ['G1'], outcome: 'loss',
                   outcome_text: 'loss on the original', text: 'BKYI held by G1 — loss on the original' }] },
  recon: { original_only: 1, audited_only: 0, both: 0, admitted: 1, text: 'served recon line · UNMEASURED' },
  per_rule_title: 'served per-rule title',
  per_rule: [{ key: 'K3S', id: 'K3S', kind: 'admit', label: 'K3S served label',
               with: { label: 'w', text: 'served K3S with text' }, other: { label: 'o', text: 'served K3S other text' },
               delta_text: 'served K3S delta' }],
  honesty: 'served honesty',
  unmeasured_text: 'served unmeasured',
};
const withAdmitted = (patch: (a: any) => void = () => {}) => {
  const b: any = clone(BASE);
  b.admitted = clone(ADMITTED);
  patch(b.admitted);
  return b;
};
const TESTIDS = ['gg-audited-compare-admitted-block', 'gg-audited-compare-admitted-title', 'gg-audited-compare-admitted',
  'gg-audited-compare-admitted-heldby'];

afterEach(() => cleanup());

describe('🧪 K3S — the served admitted block on the compare (2026-11-09)', () => {
  it('prints the served title, line, held-by line and one li per row, each verbatim', () => {
    render(<GgAuditedCompare block={withAdmitted()} />);
    const cmp = screen.getByTestId('gg-audited-compare');
    expect(within(cmp).getByTestId('gg-audited-compare-admitted-title').textContent).toBe(ADMITTED.title);
    expect(within(cmp).getByTestId('gg-audited-compare-admitted').textContent).toBe(ADMITTED.text);
    expect(within(cmp).getByTestId('gg-audited-compare-admitted-heldby').textContent).toBe(ADMITTED.held_by_text);
    const blk = within(cmp).getByTestId('gg-audited-compare-admitted-block');
    const lis = blk.querySelectorAll('li');
    expect(lis).toHaveLength(2);
    expect(within(cmp).getByTestId('gg-audited-compare-admitted-HUHU-reversal_squeeze').textContent).toBe(ADMITTED.rows[0].text);
    expect(within(cmp).getByTestId('gg-audited-compare-admitted-LABT-reversal_squeeze').textContent).toBe(ADMITTED.rows[1].text);
  });

  it('mounts AFTER the held line and BEFORE recon (DOM order); per_rule stays after recon', () => {
    render(<GgAuditedCompare block={withAdmitted()} />);
    const held = screen.getByTestId('gg-audited-compare-held');
    const adm = screen.getByTestId('gg-audited-compare-admitted-block');
    const recon = screen.getByTestId('gg-audited-recon');
    const pr = screen.getByTestId('gg-audited-per-rule');
    const after = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    expect(after(held, adm)).toBe(true);
    expect(after(adm, recon)).toBe(true);
    expect(after(recon, pr)).toBe(true);
  });

  it('NEGATIVE: no number is composed — the block text is exactly the served strings; mean_r / counts never reach the DOM', () => {
    render(<GgAuditedCompare block={withAdmitted()} />);
    const blk = screen.getByTestId('gg-audited-compare-admitted-block');
    const served = [ADMITTED.title, ADMITTED.text, ADMITTED.held_by_text, ...ADMITTED.rows.map((r) => r.text)];
    expect(blk.textContent).toBe(served.join(''));
    expect(blk.textContent).not.toContain('0.123456');
    expect(blk.textContent).not.toContain('0.12');
    expect(blk.textContent).not.toMatch(/\b9\b/);
    expect(blk.textContent).not.toMatch(/\b7\b/);
  });

  it('NEGATIVE: rows without a symbol are dropped; a null / non-array rows list renders no list', () => {
    render(<GgAuditedCompare block={withAdmitted((a) => {
      a.rows = [{ ...a.rows[0], symbol: '' }, { ...a.rows[1], symbol: null }, null, { ...a.rows[0], symbol: 'EHGO' }];
    })} />);
    const blk = screen.getByTestId('gg-audited-compare-admitted-block');
    expect(blk.querySelectorAll('li')).toHaveLength(1);
    expect(within(blk).getByTestId('gg-audited-compare-admitted-EHGO-reversal_squeeze').textContent).toBe(ADMITTED.rows[0].text);
    cleanup();
    for (const rows of [null, 'nope', {}]) {
      render(<GgAuditedCompare block={withAdmitted((a) => { a.rows = rows; })} />);
      const b2 = screen.getByTestId('gg-audited-compare-admitted-block');
      expect(b2.querySelector('ul')).toBeNull();
      expect(within(b2).getByTestId('gg-audited-compare-admitted').textContent).toBe(ADMITTED.text);
      cleanup();
    }
  });

  it('NEGATIVE: empty / whitespace / null title, text and held_by_text are not rendered', () => {
    for (const v of ['', '   ', null, undefined, 3]) {
      render(<GgAuditedCompare block={withAdmitted((a) => { a.title = v; a.text = v; a.held_by_text = v; })} />);
      const blk = screen.getByTestId('gg-audited-compare-admitted-block');
      expect(within(blk).queryByTestId('gg-audited-compare-admitted-title')).toBeNull();
      expect(within(blk).queryByTestId('gg-audited-compare-admitted')).toBeNull();
      expect(within(blk).queryByTestId('gg-audited-compare-admitted-heldby')).toBeNull();
      expect(blk.querySelectorAll('li')).toHaveLength(2);
      cleanup();
    }
  });

  it('NEGATIVE: no `admitted` key / null / a non-object → nothing admitted renders; the legacy compare is unchanged', () => {
    const legacy = render(<GgAuditedCompare block={clone(BASE) as any} />);
    const legacyHtml = legacy.container.innerHTML;
    for (const id of TESTIDS) expect(screen.queryByTestId(id)).toBeNull();
    cleanup();
    for (const v of [null, 'K3S', 5]) {
      const b: any = clone(BASE);
      b.admitted = v;
      const { container } = render(<GgAuditedCompare block={b} />);
      for (const id of TESTIDS) expect(screen.queryByTestId(id)).toBeNull();
      expect(container.innerHTML).toBe(legacyHtml);
      cleanup();
    }
  });

  it('NEGATIVE: recon.admitted is a count and is never printed — recon prints only its served text', () => {
    render(<GgAuditedCompare block={withAdmitted()} />);
    expect(screen.getByTestId('gg-audited-recon').textContent).toBe(BASE.recon.text);
  });
});
