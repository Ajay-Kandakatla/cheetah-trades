import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ShortInterestChip } from './ShortInterestChip';
import { _resetShortInterestCache } from '../hooks/useShortInterest';

/* 🩳 ShortInterestChip — prints the served chip and hover verbatim, one
 * neutral tone; renders NOTHING when there is nothing served (never a 0). */

const TITLE = '🩳 Short interest — FINRA settlement 2026-09-15 (published ~2026-09-24). A count of open short positions — not a forecast.';
const ITEMS: Record<string, unknown> = {
  EOSE: { symbol: 'EOSE', status: 'ok', chip: '🩳 SI 33.6% float · 4.1d · 9/15', title: TITLE, rows: [] },
  DTC: { symbol: 'DTC', status: 'ok', days_to_cover: null, chip: '🩳 SI 33.6% float · 9/15', title: TITLE, rows: [] },
  OLD: { symbol: 'OLD', status: 'stale', chip: '🩳 SI 30.6% shs out · 5.0d · 8/31 · stale', title: 'old', rows: [] },
  MISS: { symbol: 'MISS', status: 'no_record', chip: null, title: 'Short interest: no FINRA record on file for MISS at the last warm — not read.',
          rows: [{ k: 'Short interest', v: 'not read — no FINRA record at the last warm' }] },
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

const settle = (f: ReturnType<typeof vi.fn>) => waitFor(() => expect(f).toHaveBeenCalled()).then(() => new Promise((r) => setTimeout(r, 0)));

describe('ShortInterestChip', () => {
  beforeEach(() => _resetShortInterestCache());
  afterEach(() => vi.unstubAllGlobals());

  it('renders the served chip text with the served title, neutral tone', async () => {
    stub();
    render(<ShortInterestChip symbol="EOSE" />);
    const el = await screen.findByTestId('si-chip');
    expect(el.textContent).toBe('🩳 SI 33.6% float · 4.1d · 9/15');
    expect(el.getAttribute('title')).toBe(TITLE);
    expect(el.className).toBe('cm-badge cm-badge-muted');
  });

  it('carries the wrapper class it is given (Hottest / Bonde / Session tones)', async () => {
    stub();
    render(<ShortInterestChip symbol="EOSE" className="hs-badge" />);
    expect((await screen.findByTestId('si-chip')).className).toBe('hs-badge hs-badge-muted');
  });

  it('a stale read says stale in its own text', async () => {
    stub();
    render(<ShortInterestChip symbol="OLD" />);
    expect((await screen.findByTestId('si-chip')).textContent).toMatch(/· stale$/);
  });

  it('NEGATIVE: a no_record block renders nothing', async () => {
    const f = stub();
    const { container } = render(<ShortInterestChip symbol="MISS" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: an absent symbol renders nothing (never 0%)', async () => {
    const f = stub();
    const { container } = render(<ShortInterestChip symbol="NOPE" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
    expect(container.textContent).not.toMatch(/0%|0\.0/);
  });

  it('NEGATIVE: a fetch failure renders nothing and does not throw', async () => {
    const f = stub(false);
    const { container } = render(<ShortInterestChip symbol="EOSE" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: the served chip without a days-to-cover segment never grows a 0.0d', async () => {
    stub();
    render(<ShortInterestChip symbol="DTC" />);
    const el = await screen.findByTestId('si-chip');
    expect(el.textContent).toBe('🩳 SI 33.6% float · 9/15');
    expect(el.textContent).not.toMatch(/0\.0d|\b0%/);
  });
});

/* Style guard (critic 2026-10-03): the chip appends `${family}-muted`; a family
 * with no such rule renders in the table's inherited ink and reads like a plain
 * row value. Every family the chip is mounted with must define a slate -muted. */
const SI_TSX = (import.meta as any).glob('../**/*.tsx',
  { eager: true, query: '?raw', import: 'default' }) as Record<string, string>;

async function siCss(): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/src/styles.css`, 'utf8');
}

function siFamilies(): string[] {
  const fams = new Set<string>(['cm-badge']);
  for (const [path, src] of Object.entries(SI_TSX)) {
    if (path.includes('ShortInterestChip')) continue;
    for (const m of src.matchAll(/<ShortInterestChip\b[^>]*?className="([^"]+)"/g)) fams.add(m[1]);
  }
  return [...fams].sort();
}

describe('ShortInterestChip style guard', () => {
  it('every family the chip is mounted with has a slate -muted rule', async () => {
    const CSS = await siCss();
    const fams = siFamilies();
    expect(fams).toEqual(['bd-gchip', 'cm-badge', 'hs-badge', 'sb-chip']);
    for (const fam of fams) {
      const rule = new RegExp(`\\.${fam}-muted\\s*\\{([^}]*)\\}`).exec(CSS);
      expect(rule, `.${fam}-muted is not defined in styles.css`).toBeTruthy();
      expect(rule![1], `.${fam}-muted must carry the slate ink`).toContain('#8595ad');
    }
  });

  it('NEGATIVE: no -muted rule the chip uses wears a signal colour', async () => {
    const CSS = await siCss();
    for (const fam of siFamilies()) {
      const body = new RegExp(`\\.${fam}-muted\\s*\\{([^}]*)\\}`).exec(CSS)![1];
      for (const hue of ['#22d3ee', '#f85149', '#f59e0b', '#10b981']) expect(body).not.toContain(hue);
    }
  });

  it('NEGATIVE: a family with no -muted rule is caught, not passed', async () => {
    const CSS = await siCss();
    expect(new RegExp(`\\.zz-nofam-muted\\s*\\{([^}]*)\\}`).exec(CSS)).toBeNull();
  });
});
