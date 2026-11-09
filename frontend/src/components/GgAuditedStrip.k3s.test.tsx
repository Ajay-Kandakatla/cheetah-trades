import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { GgAuditedStrip } from './GgAuditedStrip';

/* 🧪 K3S on the strip (2026-11-09, gg_k3 spec §3.5 / WP-D).
 *
 * Ajay 2026-11-09: "yes change the audit as per you like that is yours I need you to make it successful and earn money
 * that is the goal".
 *
 * The strip prints the served `admitted.text` (today's admit-pass line) after the unaudited line — verbatim; the counts
 * beside it disagree with the text so any FE composition would show. Test data, WORDS_GGA-shaped. */

const clone = (x: any) => JSON.parse(JSON.stringify(x));
const LINE = "1 \u{1F9EA} A+ by K3S today — \u{1F6A9} read them 'broke — not A+' · 1 rang in shadow · 0 held · 2 refused by K11 · 3 candidates · 4 \u{1F3BE} breaks partial on another rule";
const BASE = {
  title: 'served strip title',
  registry: [{ id: 'K3S', name: 'K3 volume-dry not binding', status: 'on', kind: 'admit', rule: 'served rule' }],
  pass: { text: 'served pass line' },
  unaudited: { n: 1, text: 'served unaudited line' },
};
const withAdmitted = (admitted: any) => ({ ...clone(BASE), admitted });

afterEach(() => cleanup());

describe('🧪 K3S — the strip prints the served admitted line (2026-11-09)', () => {
  it('prints admitted.text verbatim, after the unaudited line', () => {
    render(<GgAuditedStrip block={withAdmitted({ n: 9, rang: 9, held: 9, candidates: 9, k11_refused: 9, placebo_a: 9, text: LINE })} />);
    const el = screen.getByTestId('gg-audited-admitted');
    expect(el.textContent).toBe(LINE);
    const un = screen.getByTestId('gg-audited-unaudited');
    expect(!!(un.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(screen.getByTestId('gg-audited-strip').textContent).not.toMatch(/\b9\b/);
  });

  it('NEGATIVE: no admitted key / null / a non-object → no testid and the strip renders as before', () => {
    const legacy = render(<GgAuditedStrip block={clone(BASE)} />);
    const html = legacy.container.innerHTML;
    expect(screen.queryByTestId('gg-audited-admitted')).toBeNull();
    cleanup();
    for (const v of [null, undefined, 'text', 4]) {
      const { container } = render(<GgAuditedStrip block={withAdmitted(v)} />);
      expect(screen.queryByTestId('gg-audited-admitted')).toBeNull();
      expect(container.innerHTML).toBe(html);
      cleanup();
    }
  });

  it('NEGATIVE: text null / empty / whitespace / missing (the key-absent payload) → not rendered', () => {
    for (const text of [null, '', '  ', undefined, 5]) {
      render(<GgAuditedStrip block={withAdmitted({ n: null, rang: null, held: null, candidates: null, k11_refused: null, placebo_a: null, text })} />);
      expect(screen.queryByTestId('gg-audited-admitted')).toBeNull();
      cleanup();
    }
  });
});
