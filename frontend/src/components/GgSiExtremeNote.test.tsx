import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { GgSiExtremeNote } from './GgSiExtremeNote';
import { GgShortInterestLabel } from './GgShortInterestLabel';
import { _resetShortInterestCache } from '../hooks/useShortInterest';

/* 🩳 GgSiExtremeNote (2026-11-18) — Ajay: "When there are extreme cases of short interest make a not for them on
 * reversal squeeze like percentage of short interest on the tickers card and also on watch list". The 👀 tile prints
 * the SERVED short form, the SERVED sentence on hover; NOTHING when the server sends no note (never a zero). fetch is
 * stubbed — no mock of the hook or the lib, so the real one-bulk-GET path runs. */

const TITLE = '🩳 EXTREME short interest — 36.4% of the float is sold short at the FINRA settlement 2026-10-30 (published ~2026-11-10). A count of open short positions — not a forecast. Not advice.';
const AKAN_X = { text: '🩳 EXTREME SI 36.4% float · 1.0d · 10/30', short: '🩳 EXTREME SI 36.4% float', title: TITLE, basis: 'si_doc_float' };
const EOSE_X = { text: '🩳 EXTREME SI 38.4% float · 5.5d · 10/30', short: '🩳 EXTREME SI 38.4% float', title: 'eose served title', basis: 'si_doc_float' };
const ITEMS: Record<string, unknown> = {
  AKAN: { symbol: 'AKAN', status: 'ok', chip: '🩳 SI 36.4% float · 1.0d · 10/30', title: 'chip title', rows: [], extreme: AKAN_X },
  EOSE: { symbol: 'EOSE', status: 'ok', chip: '🩳 SI 38.4% float · 5.5d · 10/30', title: 'chip title', rows: [], extreme: EOSE_X },
  GP: { symbol: 'GP', status: 'ok', chip: '🩳 SI 4.1% float · 1.0d · 10/30', title: 'chip title', rows: [], extreme: null },
  OLDAPI: { symbol: 'OLDAPI', status: 'ok', chip: '🩳 SI 4.1% float · 1.0d · 10/30', title: 'chip title', rows: [] },
  OLD: { symbol: 'OLD', status: 'stale', chip: '🩳 SI 30.6% float · 5.0d · 8/31 · stale', title: 'stale', rows: [], extreme: AKAN_X },
  MISS: { symbol: 'MISS', status: 'no_record', chip: null, title: 'Short interest: no FINRA record on file for MISS — not read.', rows: [], extreme: null },
};

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
const mapGets = (f: ReturnType<typeof vi.fn>) => f.mock.calls.filter((c) => String(c[0]).includes('/short-interest/map')).length;

describe('GgSiExtremeNote', () => {
  beforeEach(() => _resetShortInterestCache());
  afterEach(() => vi.unstubAllGlobals());

  it('prints the served short form verbatim with the served title, default classes, SPAN, testid, basis', async () => {
    stub();
    render(<GgSiExtremeNote symbol="AKAN" testid="ggw-si-extreme-AKAN" />);
    const el = await screen.findByTestId('ggw-si-extreme-AKAN');
    expect(el.textContent).toBe('🩳 EXTREME SI 36.4% float');
    expect(el.getAttribute('title')).toBe(TITLE);
    expect(el.className).toBe('ggw-chip ggw-si-extreme');
    expect(el.tagName).toBe('SPAN');
    expect(el.getAttribute('data-si-basis')).toBe('si_doc_float');
  });

  it('prints the short form, never the longer card text', async () => {
    stub();
    render(<GgSiExtremeNote symbol="AKAN" testid="t" />);
    expect((await screen.findByTestId('t')).textContent).not.toBe(AKAN_X.text);
  });

  it('a custom className replaces the default', async () => {
    stub();
    render(<GgSiExtremeNote symbol="AKAN" testid="t" className="custom-x" />);
    expect((await screen.findByTestId('t')).className).toBe('custom-x');
  });

  it('NEGATIVE: extreme null renders nothing', async () => {
    const f = stub();
    const { container } = render(<GgSiExtremeNote symbol="GP" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: an older API with no extreme key renders nothing', async () => {
    const f = stub();
    const { container } = render(<GgSiExtremeNote symbol="OLDAPI" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: a no_record block renders nothing', async () => {
    const f = stub();
    const { container } = render(<GgSiExtremeNote symbol="MISS" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: a stale block carrying an extreme object renders nothing', async () => {
    const f = stub();
    const { container } = render(<GgSiExtremeNote symbol="OLD" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: an absent symbol renders nothing, never a 0', async () => {
    const f = stub();
    const { container } = render(<GgSiExtremeNote symbol="NOPE" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: a failed fetch renders nothing and does not throw', async () => {
    const f = stub(false);
    const { container } = render(<GgSiExtremeNote symbol="AKAN" testid="t" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: nothing before the read lands (loading is not a zero)', () => {
    stub();
    const { container } = render(<GgSiExtremeNote symbol="AKAN" testid="t" />);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: the printed text and hover never carry a 0%', async () => {
    stub();
    render(<>
      <GgSiExtremeNote symbol="AKAN" testid="a" />
      <GgSiExtremeNote symbol="EOSE" testid="b" />
    </>);
    for (const id of ['a', 'b']) {
      const el = await screen.findByTestId(id);
      expect(el.textContent).not.toMatch(/\b0(\.0)?%/);
      expect(el.getAttribute('title') || '').not.toMatch(/\b0(\.0)?%/);
    }
  });

  it('three notes + one card label on one screen cost ONE /short-interest/map GET', async () => {
    const f = stub();
    render(<>
      <GgSiExtremeNote symbol="AKAN" testid="a" />
      <GgSiExtremeNote symbol="EOSE" testid="b" />
      <GgSiExtremeNote symbol="GP" testid="c" />
      <GgShortInterestLabel symbol="GP" testid="lbl" />
    </>);
    await screen.findByTestId('b');
    await screen.findByTestId('lbl');
    expect(mapGets(f)).toBe(1);
    expect(f).toHaveBeenCalledTimes(1);
  });
});

describe('SOURCE GUARD — the FE computes no EXTREME verdict', () => {
  async function readSource(rel: string): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/${rel}`, 'utf8');
  }
  const FILES: Record<string, string> = {
    component: 'src/components/GgSiExtremeNote.tsx',
    lib: 'src/lib/shortInterest.ts',
  };
  const FIELD = '(pct_of_float|pct_of_shares_out|days_to_cover|si_shares|si_change_pct)';

  for (const [name, rel] of Object.entries(FILES)) {
    it(`${name}: no >= / < / toFixed against a short-interest field`, async () => {
      const src = await readSource(rel);
      expect(src).not.toMatch(new RegExp(`${FIELD}[^;\\n]*(>=|<|toFixed)`));
      expect(src).not.toMatch(new RegExp(`(>=|<)\\s*[\\w.?]*${FIELD}`));
      expect(src).not.toMatch(/toFixed/);
    });

    it(`${name}: no literal 20 (the cut is SI_HIGH_PCT, served)`, async () => {
      const src = await readSource(rel);
      expect(src.length).toBeGreaterThan(0);
      expect(src).not.toMatch(/\b20(\.0+)?\b/);
    });
  }

  it('the guard regex is not vacuous (matches a planted cut, ignores a year)', () => {
    expect('if (pf >= 20) x').toMatch(/\b20(\.0+)?\b/);
    expect('cut 20.0').toMatch(/\b20(\.0+)?\b/);
    expect('2026-11-18').not.toMatch(/\b20(\.0+)?\b/);
    expect('read.pct_of_float >= cut').toMatch(new RegExp(`${FIELD}[^;\\n]*(>=|<|toFixed)`));
  });
});
