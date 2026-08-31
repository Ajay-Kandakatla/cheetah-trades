import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  OVERLAY_GROUPS, filterTile, loadHidden, presentGroups, saveHidden,
} from './chartOverlays';

const tile = (): any => ({
  symbol: 'X', href: '/x', bars: [], markers: [], stats: [], why: '',
  bands: [
    { kind: 'demand', lo: 1, hi: 2 },
    { kind: 'supply', lo: 5, hi: 6 },
    { kind: 'order_block', lo: 2, hi: 2.5 },
    { kind: 'fvg_demand', lo: 3, hi: 3.2 },
    { kind: 'neutral', lo: 4, hi: 4.2 },
  ],
  lines: [
    { price: 2, label: 'BUY', tone: 'buy' },
    { price: 1, label: 'STOP', tone: 'stop' },
    { price: 9, label: 'now', tone: 'now' },
  ],
});

describe('filterTile', () => {
  it('removes exactly the hidden families and nothing else', () => {
    const out = filterTile(tile(), new Set(['order_block', 'trade']));
    expect(out.bands.map((b: any) => b.kind))
      .toEqual(['demand', 'supply', 'fvg_demand', 'neutral']);
    // trade lines gone; the "now" line is not a trade line and stays
    expect(out.lines.map((l: any) => l.label)).toEqual(['now']);
  });

  it('is the identity when nothing is hidden', () => {
    const t = tile();
    expect(filterTile(t, new Set())).toBe(t);
  });

  it('always KEEPS overlay kinds the legend has never heard of', () => {
    // A new overlay must appear by default, never vanish silently.
    const t = tile();
    t.bands.push({ kind: 'brand_new_thing', lo: 7, hi: 8 });
    const out = filterTile(t, new Set(OVERLAY_GROUPS.map((g) => g.key)));
    expect(out.bands.map((b: any) => b.kind)).toEqual(['brand_new_thing']);
  });
});

describe('label-prefix grouping (the right-edge text labels)', () => {
  // Ajay 2026-08-31, screenshot of swept 71.80 / BOS 70.85 / overhead 70.85 /
  // support 68.43 / now: "I wanna able to toggle these".
  const labeled = (): any => ({
    symbol: 'X', href: '/x', bars: [], markers: [], stats: [], why: '', bands: [],
    lines: [
      { price: 68.43, label: 'support 68.43', tone: 'buy' },
      { price: 70.85, label: 'overhead 70.85', tone: 'target' },
      { price: 70.85, label: 'BOS 70.85', tone: 'target', quiet: true },
      { price: 71.8, label: 'swept 71.80', tone: 'neutral', quiet: true },
      { price: 70.0, label: 'now', tone: 'now' },
      { price: 69.0, label: 'BUY', tone: 'buy' },
    ],
  });

  it('prefix beats tone: hiding Trade lines must NOT eat the support label', () => {
    const out = filterTile(labeled(), new Set(['trade']));
    expect(out.lines.map((l: any) => l.label))
      .toEqual(['support 68.43', 'overhead 70.85', 'BOS 70.85', 'swept 71.80', 'now']);
  });

  it('support hides with demand, overhead with supply', () => {
    const out = filterTile(labeled(), new Set(['demand', 'supply']));
    // BOS is priced AT the overhead level but is a structure read, not supply —
    // it must survive the supply checkbox and fall to the structure one.
    expect(out.lines.map((l: any) => l.label))
      .toEqual(['BOS 70.85', 'swept 71.80', 'now', 'BUY']);
  });

  it('swept / BOS / CHoCH hide together under the structure checkbox', () => {
    const t = labeled();
    t.lines.push({ price: 70.2, label: 'CHoCH 70.20', tone: 'stop', quiet: true });
    const out = filterTile(t, new Set(['structure']));
    expect(out.lines.map((l: any) => l.label))
      .toEqual(['support 68.43', 'overhead 70.85', 'now', 'BUY']);
  });

  it('the now marker has its own checkbox', () => {
    const out = filterTile(labeled(), new Set(['now']));
    expect(out.lines.map((l: any) => l.label)).not.toContain('now');
    expect(out.lines.map((l: any) => l.label)).toContain('BUY');
  });

  it('a label the legend has never heard of is always kept', () => {
    const t = labeled();
    t.lines.push({ price: 1, label: 'mystery 1.00', tone: 'weird' });
    const out = filterTile(t, new Set(OVERLAY_GROUPS.map((g) => g.key)));
    expect(out.lines.map((l: any) => l.label)).toEqual(['mystery 1.00']);
  });

  it('presentGroups sees prefix-matched families too', () => {
    const keys = presentGroups([labeled()]).map((g) => g.key);
    expect(keys).toEqual(
      expect.arrayContaining(['demand', 'supply', 'structure', 'now', 'trade']));
  });
});

describe('presentGroups', () => {
  it('offers a checkbox only for families the view actually draws', () => {
    const keys = presentGroups([tile()]).map((g) => g.key);
    expect(keys).toContain('order_block');
    expect(keys).toContain('trade');
    const bare = presentGroups([{ bands: [{ kind: 'demand', lo: 1, hi: 2 }], lines: [] } as any]);
    expect(bare.map((g) => g.key)).toEqual(['demand']);
  });

  it('is empty for an empty view', () => {
    expect(presentGroups([])).toEqual([]);
  });
});

describe('persistence', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('round-trips through localStorage and drops unknown keys', () => {
    const store: Record<string, string> = {};
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => store[k] ?? null,
      setItem: (k: string, v: string) => { store[k] = v; },
    });
    saveHidden(new Set(['fvg', 'bogus_key']));
    expect([...loadHidden()]).toEqual(['fvg']);
  });

  it('a blocked store renders the default view, never a crash', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('blocked'); },
      setItem: () => { throw new Error('blocked'); },
    });
    expect([...loadHidden()]).toEqual([]);
    expect(() => saveHidden(new Set(['fvg']))).not.toThrow();
  });

  it('junk in the store is an empty set, not a crash', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => '{not json',
      setItem: () => {},
    });
    expect([...loadHidden()]).toEqual([]);
  });
});
