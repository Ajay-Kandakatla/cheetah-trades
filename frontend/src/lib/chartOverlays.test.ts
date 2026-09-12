import { toneColor } from './chartMaps';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { OVERLAY_GROUPS, filterTile, loadHidden, presentGroups, saveHidden, STUDY_KEYS, defaultHidden, studiesWanted, filterForGrid } from './chartOverlays';

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
  it('offers a checkbox only for DATA-DRIVEN families the view actually draws', () => {
    const keys = presentGroups([tile()]).map((g) => g.key);
    expect(keys).toContain('order_block');
    expect(keys).toContain('trade');
    const bare = presentGroups([{ bands: [{ kind: 'demand', lo: 1, hi: 2 }], lines: [] } as any])
      .map((g) => g.key).filter((k) => !STUDY_KEYS.includes(k));
    expect(bare).toEqual(['demand']);
  });

  /* Ajay 2026-09-12. The study families are fetched ONLY while one is on, so a
     purely data-driven legend would never render the switch that turns them on
     — a control unreachable because it is off. */
  it('Keltner joins the study families and keeps its own tone', () => {
    const g = OVERLAY_GROUPS.find((x) => x.key === 'keltner')!;
    expect(g.always).toBe(true);
    expect(STUDY_KEYS).toContain('keltner');
    // lines tagged `keltner` must not fall through to another family's box
    const t = { lines: [{ price: 1, tone: 'keltner', label: 'KC upper 1.00' }] } as any;
    expect(filterTile(t, new Set(['keltner'])).lines).toHaveLength(0);
    expect(filterTile(t, new Set(['trade', 'meanrev'])).lines).toHaveLength(1);
  });

  it('NEGATIVE: the KC mid label does not get eaten by the mean-reversion box', () => {
    const t = { lines: [{ price: 1, tone: 'keltner', label: 'KC mid 1.00 · squeeze 4b' }] } as any;
    expect(filterTile(t, new Set(['meanrev'])).lines).toHaveLength(1);
  });

  it('the study families ALWAYS get a checkbox, even with no data', () => {
    const keys = presentGroups([]).map((g) => g.key);
    expect(keys).toEqual(STUDY_KEYS);
  });

  it('an empty view offers the study switches and nothing else', () => {
    expect(presentGroups([]).every((g) => g.always)).toBe(true);
  });
});

describe('the 2026-09-12 default (supply/demand + order blocks only)', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('defaultHidden hides everything except the three he named', () => {
    const shown = OVERLAY_GROUPS.map((g) => g.key).filter((k) => !defaultHidden().has(k));
    expect(shown).toEqual(['demand', 'supply', 'order_block']);
  });

  it('a browser that has never saved anything gets that default', () => {
    vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => {} });
    expect([...loadHidden()].sort()).toEqual([...defaultHidden()].sort());
  });

  /* THE MIGRATION BUG THIS PREVENTS: reading the v1 key would hand every
     existing browser its old empty hidden-set — the previous show-everything
     default — and his instruction would silently never take effect. */
  it('NEGATIVE: a v1 value does NOT leak in and resurrect the old default', () => {
    const store: Record<string, string> = { 'cm-hidden-overlays': '[]' };
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => store[k] ?? null, setItem: () => {},
    });
    expect(loadHidden().size).toBeGreaterThan(0);
    expect(loadHidden().has('fib')).toBe(true);
  });

  it('once he saves a choice it wins over the default', () => {
    const store: Record<string, string> = { 'cm-hidden-overlays-v2': '["fvg"]' };
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => store[k] ?? null, setItem: () => {},
    });
    expect([...loadHidden()]).toEqual(['fvg']);
  });

  it('studiesWanted is false on the default view and true once one is on', () => {
    expect(studiesWanted(defaultHidden())).toBe(false);
    const one = new Set(defaultHidden()); one.delete('fib');
    expect(studiesWanted(one)).toBe(true);
  });

  it('fib is stripped from a GRID tile and kept on the expanded one', () => {
    const t = { lines: [{ price: 1, tone: 'fib' }, { price: 2, tone: 'now' }] } as any;
    expect(filterForGrid(t, false).lines.map((l: any) => l.tone)).toEqual(['now']);
    expect(filterForGrid(t, true).lines).toHaveLength(2);
  });

  /* REGRESSION 2026-09-12. Shipped broken and he caught it: "Non of these are
     showing up I selected AMD, Fibonacci." Three separate defects, all mine —
     the tones were missing from CmLineTone so every study line rendered in the
     SAME GREY as the grid; amd_accumulation was missing from BAND_FILL; and
     the page passed expanded=false to filterForGrid, so fib was stripped from
     the only chart surface that page has. */
  it('every study tone has its OWN colour, never the grid grey', () => {
    const grey = toneColor('neutral');
    for (const tone of ['amd', 'fib', 'meanrev', 'keltner'] as const) {
      expect(toneColor(tone)).not.toEqual(grey);
    }
    const seen = new Set(['amd', 'fib', 'meanrev', 'keltner'].map((t) => toneColor(t as any)));
    expect(seen.size).toBe(4);          // and four DIFFERENT colours
  });

  it('the ledger swatch matches the line colour for each study family', () => {
    for (const key of STUDY_KEYS) {
      const g = OVERLAY_GROUPS.find((x) => x.key === key)!;
      expect(g.swatch).toEqual(toneColor(key as any));
    }
  });

  it('NEGATIVE: filterForGrid never touches the levels he trades', () => {
    const t = { lines: [{ price: 1, tone: 'buy' }, { price: 2, tone: 'meanrev' }] } as any;
    expect(filterForGrid(t, false).lines).toHaveLength(2);
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

  it('a blocked store renders the DEFAULT view, never a crash and never show-all', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('blocked'); },
      setItem: () => { throw new Error('blocked'); },
    });
    // the DEFAULT, not an empty set — an empty set is the old show-everything
    // view, which is precisely what a blocked store must not silently restore
    expect([...loadHidden()].sort()).toEqual([...defaultHidden()].sort());
    expect(() => saveHidden(new Set(['fvg']))).not.toThrow();
  });

  it('junk in the store is the DEFAULT set, not a crash and not show-all', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => '{not json',
      setItem: () => {},
    });
    expect([...loadHidden()].sort()).toEqual([...defaultHidden()].sort());
  });

  it('NEGATIVE: a stored NON-array is the default, not a crash', () => {
    vi.stubGlobal('localStorage', { getItem: () => '{"a":1}', setItem: () => {} });
    expect([...loadHidden()].sort()).toEqual([...defaultHidden()].sort());
  });
});
