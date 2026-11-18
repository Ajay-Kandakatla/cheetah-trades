import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { GgShortInterestLabel } from './GgShortInterestLabel';
import { _resetShortInterestCache } from '../hooks/useShortInterest';

/* 🎾 GgShortInterestLabel (2026-11-08) — the SERVED chip text as a label, the SERVED title on hover, through the same
 * hook + lib as the house chip; NOTHING when there is nothing served (never a zero). fetch is stubbed — no mock of the
 * hook or the lib, so the real one-bulk-GET path runs. */

const TITLE = '🩳 Short interest — FINRA settlement 2026-10-15 (published ~2026-10-24). A count of open short positions — not a forecast.';
const ITEMS: Record<string, unknown> = {
  VJET: { symbol: 'VJET', status: 'ok', chip: '🩳 SI 21.9% float · 1.0d · 10/15', title: TITLE, rows: [] },
  ZNB: { symbol: 'ZNB', status: 'ok', chip: '🩳 SI 185.6K sh · 1.0d · 10/15', title: TITLE, rows: [] },
  OLD: { symbol: 'OLD', status: 'stale', chip: '🩳 SI 30.6% shs out · 5.0d · 8/31 · stale', title: 'served stale title', rows: [] },
  MISS: { symbol: 'MISS', status: 'no_record', chip: null, title: 'Short interest: no FINRA record on file for MISS — not read.', rows: [] },
  BLANK: { symbol: 'BLANK', status: 'ok', chip: '   ', title: TITLE, rows: [] },
};

/* 🩳 EXTREME note (2026-11-18, spec sinote WP fe-card) — the served `extreme` object; the label prints its `text`.
 * 2026-11-18 sitier: re-pinned from the AKAN shape to the CLRO shape (spec sitier §3.4). AKAN's 36.4% sits on a stale
 * float and is no longer EXTREME (Ajay: "Yes please" to "only call 🩳 EXTREME when it's ≥ 20% of float AND ≥ 10% of all
 * shares"); CLRO is the confirmed EXTREME. The served note text IS the served chip now (`🩳 SI EXTREME …` order). */
const X_TEXT = '🩳 SI EXTREME 44.0% float · 1.0d · 10/30';
const X_TITLE = '🩳 EXTREME short interest — served hover sentence (SI_HIGH_PCT heuristic). Not advice.';
const X = { text: X_TEXT, short: '🩳 SI EXTREME 44.0% float', title: X_TITLE, basis: 'si_doc_float' };
const CL_CHIP = X_TEXT;
/* the AKAN shape after sitier: tier high, float unconfirmed, NO extreme object (spec sitier §3.4) */
const AK_CHIP = '🩳 SI High 36.4% float · float unconfirmed · 1.0d · 10/30';
Object.assign(ITEMS, {
  CLRO: { symbol: 'CLRO', status: 'ok', tier: 'extreme', float_check: 'confirmed', chip: CL_CHIP, title: TITLE, rows: [], extreme: X },
  AKAN: { symbol: 'AKAN', status: 'ok', tier: 'high', float_check: 'unconfirmed', chip: AK_CHIP, title: TITLE, rows: [], extreme: null },
  GPX: { symbol: 'GPX', status: 'ok', chip: '🩳 SI 4.1% float · 1.0d · 10/30', title: TITLE, rows: [], extreme: null },
  OLDX: { symbol: 'OLDX', status: 'stale', tier: 'extreme', chip: '🩳 SI 30.6% float · 5.0d · 8/31 · stale', title: 'served stale title', rows: [], extreme: X },
  BADX: { symbol: 'BADX', status: 'ok', chip: CL_CHIP, title: TITLE, rows: [], extreme: { ...X, text: '   ' } },
});

function stub(ok = true) {
  const f = vi.fn(async (url: string) => {
    if (!ok) throw new Error('down');
    const q = decodeURIComponent(String(url).split('symbols=')[1] || '').split(',');
    const items: Record<string, unknown> = {};
    for (const s of q) if (ITEMS[s]) items[s] = ITEMS[s];
    return { ok: true, json: async () => ({ items, n: Object.keys(items).length, max_symbols: 200 }) } as unknown as Response;
  });
  vi.stubGlobal('fetch', f);
  return f;
}
const settle = (f: ReturnType<typeof vi.fn>) =>
  waitFor(() => expect(f).toHaveBeenCalled()).then(() => new Promise((r) => setTimeout(r, 0)));

describe('GgShortInterestLabel', () => {
  beforeEach(() => _resetShortInterestCache());
  afterEach(() => vi.unstubAllGlobals());

  it('prints the served chip text verbatim with the served title, bold-label classes, the given testid', async () => {
    stub();
    render(<GgShortInterestLabel symbol="VJET" testid="gg-si-label-VJET" />);
    const el = await screen.findByTestId('gg-si-label-VJET');
    expect(el.textContent).toBe('🩳 SI 21.9% float · 1.0d · 10/15');
    expect(el.getAttribute('title')).toBe(TITLE);
    expect(el.className).toBe('cm-note gg-line gg-si-label');
    expect(el.tagName).toBe('DIV');
  });

  it('the served share-count fallback prints as served (HIS CALL #10 — never hidden here)', async () => {
    stub();
    render(<GgShortInterestLabel symbol="ZNB" testid="t" />);
    expect((await screen.findByTestId('t')).textContent).toBe('🩳 SI 185.6K sh · 1.0d · 10/15');
  });

  it('a stale read carries gg-si-stale and the SERVED stale word (typed nowhere here)', async () => {
    stub();
    render(<GgShortInterestLabel symbol="OLD" testid="t" />);
    const el = await screen.findByTestId('t');
    expect(el.className).toContain('gg-si-stale');
    expect(el.textContent).toBe('🩳 SI 30.6% shs out · 5.0d · 8/31 · stale');
    expect(el.getAttribute('title')).toBe('served stale title');
  });

  it('NEGATIVE: an ok read is never marked stale', async () => {
    stub();
    render(<GgShortInterestLabel symbol="VJET" testid="t" />);
    expect((await screen.findByTestId('t')).className).not.toContain('gg-si-stale');
  });

  it('NEGATIVE: a no_record block renders nothing', async () => {
    const f = stub();
    const { container } = render(<GgShortInterestLabel symbol="MISS" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: an empty served chip renders nothing', async () => {
    const f = stub();
    const { container } = render(<GgShortInterestLabel symbol="BLANK" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: an absent symbol renders nothing, never a 0', async () => {
    const f = stub();
    const { container } = render(<GgShortInterestLabel symbol="NOPE" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
    expect(container.textContent).not.toMatch(/0%|0\.0/);
  });

  it('NEGATIVE: a failed fetch renders nothing and does not throw', async () => {
    const f = stub(false);
    const { container } = render(<GgShortInterestLabel symbol="VJET" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: nothing before the read lands (loading is not a zero)', () => {
    stub();
    const { container } = render(<GgShortInterestLabel symbol="VJET" testid="t" />);
    expect(container.innerHTML).toBe('');
  });

  it('three labels on one screen cost ONE bulk GET', async () => {
    const f = stub();
    render(<>
      <GgShortInterestLabel symbol="VJET" testid="a" />
      <GgShortInterestLabel symbol="ZNB" testid="b" />
      <GgShortInterestLabel symbol="OLD" testid="c" />
    </>);
    await screen.findByTestId('c');
    expect(f).toHaveBeenCalledTimes(1);
    expect(String(f.mock.calls[0][0])).toContain('/short-interest/map?symbols=');
  });
});

describe('GgShortInterestLabel — 🩳 EXTREME note (2026-11-18): ONE line, the label IS the note', () => {
  beforeEach(() => _resetShortInterestCache());
  afterEach(() => vi.unstubAllGlobals());

  it('an ok block with `extreme` prints extreme.text verbatim, the served title, the extreme class and basis', async () => {
    stub();
    render(<GgShortInterestLabel symbol="CLRO" testid="gg-si-label-CLRO" />);
    const el = await screen.findByTestId('gg-si-label-CLRO');
    expect(el.textContent).toBe(X_TEXT);
    expect(el.getAttribute('title')).toBe(X_TITLE);
    expect(el.className).toBe('cm-note gg-line gg-si-label gg-si-extreme');
    expect(el.getAttribute('data-si-basis')).toBe('si_doc_float');
    expect(el.getAttribute('data-si-tier')).toBe('extreme');
    expect(el.tagName).toBe('DIV');
  });

  it('NEGATIVE: the extreme form REPLACES the chip — the chip words never print beside it', async () => {
    stub();
    const { container } = render(<GgShortInterestLabel symbol="CLRO" testid="t" />);
    await screen.findByTestId('t');
    /* 2026-11-18 sitier: the served note text IS the served chip, so the line prints it exactly once */
    expect(container.textContent).toBe(CL_CHIP);
    expect(container.querySelectorAll('[data-testid="t"]')).toHaveLength(1);
    expect(container.textContent!.split('🩳').length - 1).toBe(1);
  });

  it('NEGATIVE: extreme null → the chip branch byte-identical to today (class exact, no data-si-basis)', async () => {
    stub();
    render(<GgShortInterestLabel symbol="GPX" testid="t" />);
    const el = await screen.findByTestId('t');
    expect(el.textContent).toBe('🩳 SI 4.1% float · 1.0d · 10/30');
    expect(el.getAttribute('title')).toBe(TITLE);
    expect(el.className).toBe('cm-note gg-line gg-si-label');
    expect(el.hasAttribute('data-si-basis')).toBe(false);
  });

  it('NEGATIVE: an older API without the extreme key → the chip branch (class exact, no data-si-basis)', async () => {
    stub();
    render(<GgShortInterestLabel symbol="VJET" testid="t" />);
    const el = await screen.findByTestId('t');
    expect(el.className).toBe('cm-note gg-line gg-si-label');
    expect(el.hasAttribute('data-si-basis')).toBe(false);
  });

  it('NEGATIVE: a stale block carrying an extreme object → the stale chip, never the note', async () => {
    stub();
    render(<GgShortInterestLabel symbol="OLDX" testid="t" />);
    const el = await screen.findByTestId('t');
    expect(el.textContent).toBe('🩳 SI 30.6% float · 5.0d · 8/31 · stale');
    expect(el.className).toBe('cm-note gg-line gg-si-label gg-si-stale');
    expect(el.className).not.toContain('gg-si-extreme');
    expect(el.hasAttribute('data-si-basis')).toBe(false);
    expect(el.textContent).not.toContain('EXTREME');
  });

  it('NEGATIVE: a malformed extreme (blank text) → the chip, not a blank bold line', async () => {
    stub();
    render(<GgShortInterestLabel symbol="BADX" testid="t" />);
    const el = await screen.findByTestId('t');
    expect(el.textContent).toBe(CL_CHIP);
    expect(el.className).toBe('cm-note gg-line gg-si-label');
    expect(el.hasAttribute('data-si-basis')).toBe(false);
  });

  it('NEGATIVE: nothing before the read lands, even for an extreme name (loading is not a note)', () => {
    stub();
    const { container } = render(<GgShortInterestLabel symbol="CLRO" testid="t" />);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: a failed fetch for an extreme name renders nothing and does not throw', async () => {
    const f = stub(false);
    const { container } = render(<GgShortInterestLabel symbol="CLRO" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('the ONE-bulk-GET pin holds with an extreme block in the map', async () => {
    const f = stub();
    render(<>
      <GgShortInterestLabel symbol="CLRO" testid="a" />
      <GgShortInterestLabel symbol="GPX" testid="b" />
      <GgShortInterestLabel symbol="OLDX" testid="c" />
      <GgShortInterestLabel symbol="VJET" testid="d" />
    </>);
    await screen.findByTestId('d');
    await screen.findByTestId('a');
    expect(f).toHaveBeenCalledTimes(1);
    expect(String(f.mock.calls[0][0])).toContain('/short-interest/map?symbols=');
  });
});

describe('GgShortInterestLabel — 🩳 tier key (2026-11-18, later): the AKAN shape is no longer EXTREME', () => {
  /* Ajay: "Yes please and may be add better terminilogy like Moderate with a percentage relative to float." */
  beforeEach(() => _resetShortInterestCache());
  afterEach(() => vi.unstubAllGlobals());

  it('NEGATIVE: AKAN unconfirmed → NO gg-si-extreme, the served chip with float unconfirmed, data-si-tier="high"', async () => {
    stub();
    render(<GgShortInterestLabel symbol="AKAN" testid="t" />);
    const el = await screen.findByTestId('t');
    expect(el.textContent).toBe(AK_CHIP);
    expect(el.textContent).toContain('float unconfirmed');
    expect(el.className).toBe('cm-note gg-line gg-si-label');
    expect(el.className).not.toContain('gg-si-extreme');
    expect(el.hasAttribute('data-si-basis')).toBe(false);
    expect(el.getAttribute('data-si-tier')).toBe('high');
    expect(el.textContent).not.toContain('EXTREME');
  });

  it('NEGATIVE: an older API / a stale read (even with a tier key riding along) → no data-si-tier', async () => {
    stub();
    render(<><GgShortInterestLabel symbol="VJET" testid="a" /><GgShortInterestLabel symbol="OLDX" testid="b" /></>);
    expect((await screen.findByTestId('a')).hasAttribute('data-si-tier')).toBe(false);
    expect((await screen.findByTestId('b')).hasAttribute('data-si-tier')).toBe(false);
  });
});
