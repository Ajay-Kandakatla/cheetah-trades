import { describe, it, expect } from 'vitest';
import {
  FOCUS_PARAM, GROWTH_TAB, STAGE_LABEL, arrivalGlyph, arrivalHref, arrivalTitle,
  arrivalsHeadline, hiddenArrivals, parseFocus, type HideStage,
} from './growthArrivals';

/* ✨ growthArrivals — the pure half of the Chart Maps strip (2026-10-12).
 * Addresses go through tabSearch; labels and glyphs come from SERVED flags. */

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const S = (...xs: string[]) => new Set(xs);

describe('arrivalHref', () => {
  it('sets tab=growth and focus=SYM, keeps every other param, drops pattern', () => {
    const p = new URLSearchParams('tab=winners&pattern=cup_with_handle&universe=full&show=all');
    const h = arrivalHref(p, 'pgen');
    expect(h.startsWith('?')).toBe(true);
    const q = new URLSearchParams(h.slice(1));
    expect(q.get('tab')).toBe(GROWTH_TAB);
    expect(q.get(FOCUS_PARAM)).toBe('PGEN');
    expect(q.get('universe')).toBe('full');
    expect(q.get('show')).toBe('all');
    expect(q.has('pattern')).toBe(false);
  });

  it('NEGATIVE: never mutates the router params it was given', () => {
    const p = new URLSearchParams('tab=zones&pattern=x');
    arrivalHref(p, 'PGEN');
    expect(p.toString()).toBe('tab=zones&pattern=x');
  });

  it('replaces an older focus rather than stacking a second one', () => {
    const q = new URLSearchParams(arrivalHref(new URLSearchParams('tab=growth&focus=OLD'), 'NEW').slice(1));
    expect(q.getAll(FOCUS_PARAM)).toEqual(['NEW']);
  });
});

describe('parseFocus', () => {
  it('upper-cases and trims', () => {
    expect(parseFocus(' pgen ')).toBe('PGEN');
    expect(parseFocus('BRK.B')).toBe('BRK.B');
  });
  it('NEGATIVE: null on empty / null / a path / 16+ chars / script', () => {
    expect(parseFocus('')).toBeNull();
    expect(parseFocus('   ')).toBeNull();
    expect(parseFocus(null)).toBeNull();
    expect(parseFocus(undefined)).toBeNull();
    expect(parseFocus('../x')).toBeNull();
    expect(parseFocus('A'.repeat(16))).toBeNull();
    expect(parseFocus('<script>')).toBeNull();
    expect(parseFocus('A'.repeat(15))).toBe('A'.repeat(15));
  });
});

describe('arrivalsHeadline', () => {
  it('reads the served count and window, with the ✨ glyph', () => {
    expect(arrivalsHeadline(11, 30)).toBe('✨ 11 new on 🚀 Explosive Growth (last 30 days)');
  });
  it('NEGATIVE: no window served → no invented "(last N days)"', () => {
    expect(arrivalsHeadline(3, null)).toBe('✨ 3 new on 🚀 Explosive Growth');
  });
});

describe('arrivalGlyph / arrivalTitle', () => {
  it('⛔ beats ⚠️; liquid and clean → no glyph', () => {
    expect(arrivalGlyph({ symbol: 'A', refused: true, liquid: false })).toBe('⛔');
    expect(arrivalGlyph({ symbol: 'A', refused: true, liquid: true })).toBe('⛔');
    expect(arrivalGlyph({ symbol: 'A', refused: false, liquid: false })).toBe('⚠️');
    expect(arrivalGlyph({ symbol: 'A', liquid: true })).toBe('');
  });
  it('NEGATIVE: a missing liquid flag is not read as liquid', () => {
    expect(arrivalGlyph({ symbol: 'A' })).toBe('⚠️');
  });
  it('title carries the served date and warnings verbatim', () => {
    const t = arrivalTitle({ symbol: 'MGNX', first_seen: '2026-10-12T02:29:05.396512+00:00',
      warnings: ['⛔ cap $284M', 'thin tape'] });
    expect(t).toBe('Arrived on 🚀 Explosive Growth 2026-10-12 · ⛔ cap $284M · thin tape');
    expect(arrivalTitle({ symbol: 'PGEN', first_seen: '2026-10-12T02:29:05+00:00' }))
      .toBe('Arrived on 🚀 Explosive Growth 2026-10-12 · no warnings');
  });
  it('NEGATIVE: an unknown arrival date says so, never invents one', () => {
    const t = arrivalTitle({ symbol: 'X', first_seen: null });
    expect(t).toContain('arrival date unknown');
    expect(t).not.toMatch(/\d{4}-\d{2}-\d{2}/);
  });
});

describe('STAGE_LABEL', () => {
  it('has exactly the six stage codes, in board order', () => {
    expect(Object.keys(STAGE_LABEL)).toEqual(['refused', 'demand', 'sector', 'debt', 'enterable', 'quality']);
    expect(STAGE_LABEL.refused).toBe('hide what the engine refuses');
    expect(STAGE_LABEL.enterable).toBe('enterable only');
  });
});

describe('hiddenArrivals', () => {
  const st = (code: keyof typeof STAGE_LABEL, ...kept: string[]): HideStage =>
    ({ code, label: STAGE_LABEL[code], kept: S(...kept) });

  it('attributes each hidden new symbol to the FIRST stage that dropped it', () => {
    const stages = [st('refused', 'A', 'B', 'C'), st('sector', 'A', 'C'), st('quality', 'A')];
    expect(hiddenArrivals(['A', 'B', 'C', 'D'], stages)).toEqual([
      { symbol: 'B', code: 'sector', label: 'sector filter' },
      { symbol: 'C', code: 'quality', label: 'quality chips' },
      { symbol: 'D', code: 'refused', label: 'hide what the engine refuses' },
    ]);
  });

  it('ignores symbols that are drawn', () => {
    expect(hiddenArrivals(['A'], [st('refused', 'A'), st('debt', 'A')])).toEqual([]);
  });

  it('returns [] when nothing is hidden or no stage is on', () => {
    expect(hiddenArrivals(['A', 'B'], [st('demand', 'A', 'B')])).toEqual([]);
    expect(hiddenArrivals(['A', 'B'], [])).toEqual([]);
    expect(hiddenArrivals([], [st('demand')])).toEqual([]);
  });

  it('NEGATIVE: a stage absent from `stages` (OFF) is never blamed', () => {
    const out = hiddenArrivals(['B'], [st('sector', 'A')]);
    expect(out.map((h) => h.code)).toEqual(['sector']);
    expect(out.some((h) => h.code === 'refused')).toBe(false);
  });

  it('NEGATIVE: a symbol not on the board is never counted as hidden', () => {
    const out = hiddenArrivals(['A', 'GONE'], [st('refused')], ['A', 'B']);
    expect(out.map((h) => h.symbol)).toEqual(['A']);
  });

  it('NEGATIVE: a duplicate new symbol is counted once', () => {
    expect(hiddenArrivals(['A', 'A'], [st('refused')])).toHaveLength(1);
  });
});

describe('source guards', () => {
  it('NEGATIVE: no 🆕, no measured-number literals, no admin email in the lib', async () => {
    const src = await readSource('src/lib/growthArrivals.ts');
    expect(src).not.toContain('🆕');
    expect(src).not.toMatch(/[+−-]?\d+(\.\d+)?\s*pp\b/);
    expect(src).not.toMatch(/\bCI\b/);
    expect(src).not.toContain('@gmail');
    expect(src).not.toContain('ajaykandakatla');
  });
});
