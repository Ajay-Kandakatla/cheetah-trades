import { describe, it, expect } from 'vitest';
import {
  enterableChipText,
  isShown,
  partitionEnterable,
  measuredStatusWords,
  topHiddenReasons,
  type EnterableRead,
} from './enterable';
import { ENTERABLE_KIND } from './chartMaps';

/* 🎯 ENTERABLE — the frontend half of one read (2026-09-15).
 *
 * The partition and the tab→kind map are pinned against the SAME file the
 * backend test reads, backend/tests/fixtures/enterable_mirror_2026_09_15.json.
 * Edit the fixture, both suites fail — which is the point: a filter that is ON
 * by default must hide the same rows on both sides of the wire.
 *
 * The negatives carry the weight here, because every way this feature can hurt
 * him is an ABSENCE: a row with no read must never be hidden, a disabled filter
 * must return the board untouched, and the chip must render NOTHING rather than
 * imply a verdict nobody served.
 */

type Fx = {
  kind_by_tab: Record<string, string>;
  rows: { symbol: string; read: EnterableRead | null }[];
  expected_shown_enterable: string[];
  expected_hidden: number;
  expected_unread: number;
  expected_hidden_by_reason: Record<string, number>;
};

async function load(): Promise<Fx> {
  const { default: raw } = await import('../../../backend/tests/fixtures/enterable_mirror_2026_09_15.json?raw');
  return JSON.parse(raw) as Fx;
}

const mapOf = (fx: Fx) =>
  new Map<string, EnterableRead | null>(fx.rows.map((r) => [r.symbol, r.read]));

const symbolOf = (r: { symbol: string }) => r.symbol;

describe('enterable partition — the shared backend fixture (2026-09-15)', () => {
  it('reproduces the served shown list, the counts and the reason breakdown', async () => {
    const fx = await load();
    const part = partitionEnterable(fx.rows, symbolOf, mapOf(fx), true);
    expect(part.rows.map((r) => r.symbol)).toEqual(fx.expected_shown_enterable);
    expect(part.hidden).toBe(fx.expected_hidden);
    expect(part.unread).toBe(fx.expected_unread);
    expect(part.hiddenByReason).toEqual(fx.expected_hidden_by_reason);
  });

  it('mirrors the backend KIND_BY_TAB key for key', async () => {
    const fx = await load();
    expect(ENTERABLE_KIND).toEqual(fx.kind_by_tab);
  });

  it('is a stable partition, not a sort — served order inside each half', async () => {
    const fx = await load();
    const part = partitionEnterable(fx.rows, symbolOf, mapOf(fx), true);
    const served = fx.rows.map((r) => r.symbol);
    const shown = part.rows.slice(0, part.rows.length - part.unread).map((r) => r.symbol);
    const unread = part.rows.slice(part.rows.length - part.unread).map((r) => r.symbol);
    const inServedOrder = (xs: string[]) =>
      xs.every((s, i) => i === 0 || served.indexOf(xs[i - 1]) < served.indexOf(s));
    expect(inServedOrder(shown)).toBe(true);
    expect(inServedOrder(unread)).toBe(true);
    // Every unread row sits after every shown row.
    expect(unread.every((u) => served.indexOf(u) >= 0)).toBe(true);
  });

  it('NEGATIVE: hides ONLY the BLOCKED rows — nothing else ever leaves the list', async () => {
    const fx = await load();
    const part = partitionEnterable(fx.rows, symbolOf, mapOf(fx), true);
    const kept = new Set(part.rows.map((r) => r.symbol));
    for (const r of fx.rows) {
      const blocked = r.read?.verdict === 'BLOCKED';
      expect(kept.has(r.symbol)).toBe(!blocked);
    }
  });

  it('NEGATIVE: every served sentence is his wording — no "bounc" anywhere', async () => {
    const fx = await load();
    for (const r of fx.rows) {
      const text = [...(r.read?.reason_text || []), ...(r.read?.reason_short || [])].join(' ');
      expect(text.toLowerCase()).not.toContain('bounc');
      const chip = enterableChipText(r.read);
      if (chip) {
        expect(`${chip.text} ${chip.title}`.toLowerCase()).not.toContain('bounc');
        expect(`${chip.text} ${chip.title}`).not.toContain('NaN');
      }
    }
  });
});

describe('partitionEnterable — the ways it must NOT lose a row', () => {
  const read = (over: Partial<EnterableRead> = {}): EnterableRead => ({
    kind: 'demand', verdict: 'READY', reasons: [], reason_text: [], reason_short: [], ...over,
  });

  it('NEGATIVE: a row with no map entry is never hidden — it is shown LAST and counted', () => {
    const rows = [{ symbol: 'AAA' }, { symbol: 'PEND' }, { symbol: 'BLK' }];
    const map = new Map<string, EnterableRead | null>([
      ['AAA', read()],
      ['BLK', read({ verdict: 'BLOCKED', reasons: ['room'], reason_short: ['room < 5%'] })],
    ]);
    const part = partitionEnterable(rows, symbolOf, map, true);
    expect(part.rows.map((r) => r.symbol)).toEqual(['AAA', 'PEND']);
    expect(part.unread).toBe(1);
    expect(part.hidden).toBe(1);
  });

  it('NEGATIVE: a read with a null verdict (the n/a kind) is unread, never hidden', () => {
    const rows = [{ symbol: 'VCPX' }];
    const map = new Map<string, EnterableRead | null>([
      ['VCPX', read({ kind: 'n/a', verdict: null, reasons: ['na'] })],
    ]);
    const part = partitionEnterable(rows, symbolOf, map, true);
    expect(part.rows).toHaveLength(1);
    expect(part.hidden).toBe(0);
    expect(part.unread).toBe(1);
  });

  it('NEGATIVE: disabled returns the board untouched with zero counts', () => {
    const rows = [{ symbol: 'AAA' }, { symbol: 'BLK' }];
    const map = new Map<string, EnterableRead | null>([
      ['AAA', read()],
      ['BLK', read({ verdict: 'BLOCKED', reason_short: ['no band'] })],
    ]);
    const part = partitionEnterable(rows, symbolOf, map, false);
    expect(part.rows.map((r) => r.symbol)).toEqual(['AAA', 'BLK']);
    expect(part).toMatchObject({ hidden: 0, unread: 0, hiddenByReason: {} });
  });

  it('NEGATIVE: a blocked row with no served reason still counts, under a neutral label', () => {
    const rows = [{ symbol: 'BLK' }];
    const map = new Map<string, EnterableRead | null>([['BLK', read({ verdict: 'BLOCKED' })]]);
    const part = partitionEnterable(rows, symbolOf, map, true);
    expect(part.hidden).toBe(1);
    expect(Object.values(part.hiddenByReason)).toEqual([1]);
  });

  it('matches symbols case-insensitively, the way every board keys its map', () => {
    const rows = [{ symbol: 'aaa' }];
    const map = new Map<string, EnterableRead | null>([['AAA', read({ verdict: 'BLOCKED', reason_short: ['no band'] })]]);
    expect(partitionEnterable(rows, symbolOf, map, true).hidden).toBe(1);
  });

  it('counts the reasons the SERVER worded them, most first', () => {
    const by = { 'no band': 22, 'room < 5%': 8, 'floor swept': 3, 'not at band': 3 };
    expect(topHiddenReasons(by)).toEqual([
      { reason: 'no band', n: 22 }, { reason: 'room < 5%', n: 8 }, { reason: 'floor swept', n: 3 },
    ]);
    expect(topHiddenReasons(null)).toEqual([]);
  });
});

describe('isShown', () => {
  const mk = (verdict: EnterableRead['verdict']): EnterableRead =>
    ({ kind: 'demand', verdict, reasons: [], reason_text: [], reason_short: [] });

  it('hides BLOCKED under the enterable mode and nothing else', () => {
    expect(isShown(mk('READY'))).toBe(true);
    expect(isShown(mk('WATCH'))).toBe(true);
    expect(isShown(mk('BLOCKED'))).toBe(false);
    expect(isShown(mk(null))).toBe(true);
    expect(isShown(null)).toBe(true);
    expect(isShown(undefined)).toBe(true);
  });

  it('NEGATIVE: mode "all" shows everything, BLOCKED included — the escape hatch', () => {
    expect(isShown(mk('BLOCKED'), 'all')).toBe(true);
    expect(isShown(null, 'all')).toBe(true);
  });
});

describe('enterableChipText', () => {
  const mk = (over: Partial<EnterableRead> = {}): EnterableRead => ({
    kind: 'demand', verdict: 'READY', reasons: [], reason_text: [], reason_short: [],
    print: { px: 100, source: 'live' }, measured: { status: 'pending' }, ...over,
  });

  it('NEGATIVE: no read renders nothing — an unknown never wears a chip', () => {
    expect(enterableChipText(null)).toBeNull();
    expect(enterableChipText(undefined)).toBeNull();
  });

  it('NEGATIVE: a read with no verdict and a real kind renders nothing', () => {
    expect(enterableChipText(mk({ verdict: null }))).toBeNull();
  });

  it('prints READY plainly', () => {
    const chip = enterableChipText(mk())!;
    expect(chip.text).toBe('🎯 READY');
    expect(chip.tone).toBe('ready');
  });

  it('prints the SERVED reason word on WATCH, verbatim', () => {
    const chip = enterableChipText(mk({
      verdict: 'WATCH', reasons: ['reclaim', 'weak_day'],
      reason_short: ['reclaim from below', 'weak day'],
      reason_text: ['closed back under the band floor first', 'down 4.2% today'],
    }))!;
    expect(chip.text).toBe('🎯 WATCH · reclaim from below');
    expect(chip.tone).toBe('watch');
    expect(chip.title).toContain('closed back under the band floor first');
    expect(chip.title).toContain('down 4.2% today');
  });

  it('prints the SERVED reason word on BLOCKED', () => {
    const chip = enterableChipText(mk({
      verdict: 'BLOCKED', reasons: ['room'], reason_short: ['room < 5%'],
      reason_text: ['3.8% to the first proven lid'],
    }))!;
    expect(chip.text).toBe('⛔ room < 5%');
    expect(chip.tone).toBe('blocked');
  });

  it('the n/a kind says so, muted, with the served sentence in the title', () => {
    const chip = enterableChipText(mk({
      kind: 'n/a', verdict: null, reasons: ['na'],
      reason_text: ['no demand read for this tab — its rows are not demand reversals'],
      reason_short: ['n/a'],
    }))!;
    expect(chip.text).toBe('n/a');
    expect(chip.tone).toBe('na');
    expect(chip.title).toContain('not demand reversals');
  });

  it('says so when the read was taken off the closed print', () => {
    const live = enterableChipText(mk())!;
    const scan = enterableChipText(mk({ print: { px: 100, source: 'scan' } }))!;
    expect(live.title).not.toContain('closed-bar read');
    expect(scan.title).toContain('closed-bar read (no live print)');
  });

  it("carries the study's status so a verdict is never read without it", () => {
    expect(enterableChipText(mk())!.title).toContain('pending');
  });

  it('NEGATIVE: falls back to the verdict word when the server sent no reason', () => {
    expect(enterableChipText(mk({ verdict: 'WATCH' }))!.text).toBe('🎯 WATCH');
    expect(enterableChipText(mk({ verdict: 'BLOCKED' }))!.text).toBe('⛔ BLOCKED');
  });

  it('NEGATIVE: never prints a number of its own — no NaN, ever', () => {
    const chip = enterableChipText(mk({
      verdict: 'BLOCKED', reason_short: ['room < 5%'],
      room: { state: 'ROOM', room_pct: null }, band: null, print: { px: null, source: 'live' },
    }))!;
    expect(`${chip.text} ${chip.title}`).not.toContain('NaN');
    expect(chip.text).toBe('⛔ room < 5%');
  });
});

/* 🎯 m6 (2026-09-15) — the chip tooltip is PROSE, so the study's status reaches
 * it in words. `measured.status` is a machine token on the wire (`no_signal`,
 * `pending`, `separates`) because the rules section, the alert-status payload
 * and both suites key off it; pasted raw at the end of an English sentence it
 * reads as a leaked identifier. Nothing is substituted or decided here — the
 * served token's own words, or the served banner headline when the surface has
 * it. The negatives: a raw token must never reach a title again, and no
 * headline may be invented when the server sent none. */
describe('enterableChipText — the study status reaches the tooltip in words (m6)', () => {
  const mk = (over: Partial<EnterableRead> = {}): EnterableRead => ({
    kind: 'demand', verdict: 'READY', reasons: [], reason_text: [], reason_short: [],
    print: { px: 100, source: 'live' }, measured: { status: 'no_signal' }, ...over,
  });

  it('NEGATIVE: the raw token never reaches the title — no underscore word at all', () => {
    const chip = enterableChipText(mk())!;
    expect(chip.title).not.toContain('no_signal');
    expect(chip.title).not.toMatch(/[A-Za-z]_[A-Za-z]/);
    expect(chip.title).toContain('no signal');
  });

  it('NEGATIVE: not one served sentence on the shared fixture carries a token', async () => {
    const fx = await load();
    for (const row of fx.rows) {
      for (const status of ['no_signal', 'pending', 'separates']) {
        const read = row.read ? ({ ...row.read, measured: { status } } as EnterableRead) : null;
        const chip = enterableChipText(read);
        if (!chip) continue;
        expect(chip.title).not.toMatch(/[A-Za-z]_[A-Za-z]/);
        expect(`${chip.text}`).not.toMatch(/[A-Za-z]_[A-Za-z]/);
      }
    }
  });

  it('prefers the SERVED banner headline when the surface holds one', () => {
    const chip = enterableChipText(mk(), {
      headline: 'MEASURED 2026-09-15: NO ENTRY TRIGGER SEPARATES — the read stays the gates that already shipped',
    })!;
    expect(chip.title).toContain('NO ENTRY TRIGGER SEPARATES');
    expect(chip.title).not.toContain('measured: no signal');
  });

  it('NEGATIVE: an empty or absent headline falls back to the served words, never to invented prose', () => {
    expect(enterableChipText(mk(), { headline: '   ' })!.title).toContain('measured: no signal');
    expect(enterableChipText(mk(), null)!.title).toContain('measured: no signal');
    expect(enterableChipText(mk({ measured: null }))!.title).toBe('');
  });

  it('NEGATIVE: measuredStatusWords invents nothing for an absent status', () => {
    expect(measuredStatusWords(null)).toBe('');
    expect(measuredStatusWords(undefined)).toBe('');
    expect(measuredStatusWords('  ')).toBe('');
    expect(measuredStatusWords('no_signal')).toBe('measured: no signal');
    expect(measuredStatusWords('pending')).toBe('measured: pending');
  });
});
