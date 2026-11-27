import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ShortInterest } from '../hooks/useRealtimeSignals';

/* 🩳 the SEPA card's short-interest chip — the served share-count sentence (2026-11-26, spec floatguard §3.8 / §3.9 / §4.3,
 * WP fe). Ajay 2026-11-26 ~21:20 ET: "Also the Float share count issue and SI discrepancy happened too many times need to
 * do something about it".
 * client.short_interest_for now serves `shares_source` (+ `shares_asof`): which share count the % divides by. The hover
 * gains ONE sentence `Share count: {shares_source}` (+ `, as of {shares_asof}` when served). No number changes.
 * NEGATIVES: no `shares_source` (an older API), or a junk one (null / '' / a number / NaN), keeps today's hover BYTE FOR BYTE
 * (rebuilt below from today's template); a junk `shares_asof` adds no "as of"; the chip text never changes. */

let SI: ShortInterest | null = null;
vi.mock('../hooks/useRealtimeSignals', () => ({
  useRealtimeSignals: () => ({ ref: { current: null }, shortInterest: SI, accumulation: null }),
}));

import { RealtimeChips } from './RealtimeChips';

const BASE: ShortInterest = {
  available: true, settlement_date: '2026-11-13', short_interest: 1234567, days_to_cover: 3.9, pct_of_shares: 12.34,
  si_change_pct: 5.6, squeeze: 'high',
};
/** Today's hover (RealtimeChips before 2026-11-26), rebuilt from its own template — the byte-for-byte baseline. */
const todayTitle = (si: ShortInterest) =>
  `Short interest (settled ${si.settlement_date ?? '—'}): ` +
  `${si.pct_of_shares != null ? `${si.pct_of_shares}% of shares outstanding` : 'n/a'}` +
  `${si.days_to_cover != null ? ` · ${si.days_to_cover} days-to-cover` : ''}` +
  `${si.si_change_pct != null ? ` · ${si.si_change_pct > 0 ? '+' : ''}${si.si_change_pct}% vs prior settlement` : ''}` +
  `.\nSqueeze fuel: ${si.squeeze} (FINRA bi-monthly; % of shares outstanding, not free float).`;

const chip = () => document.querySelector('.si-chip') as HTMLElement | null;

afterEach(() => { SI = null; });

describe('🩳 RealtimeChips — the served share-count sentence', () => {
  it('prints the served source as the last hover sentence; the chip text is unchanged', () => {
    const src = 'Massive ticker details — the provider gives no as-of date';
    SI = { ...BASE, shares_source: src, shares_asof: null };
    render(<RealtimeChips symbol="ABC" />);
    expect(chip()!.getAttribute('title')).toBe(`${todayTitle(BASE)}\nShare count: ${src}`);
    expect(chip()!.textContent).toBe('🩳 Short 12.34% · 3.9d');
  });

  it('adds the served as-of when it is served', () => {
    SI = { ...BASE, shares_source: 'served source words', shares_asof: '2026-11-24' };
    render(<RealtimeChips symbol="ABC" />);
    expect(chip()!.getAttribute('title')).toBe(`${todayTitle(BASE)}\nShare count: served source words, as of 2026-11-24`);
  });

  it('NEGATIVE: no shares_source (an older API) → today\'s hover byte for byte; same for null / "" / blank / a number / NaN', () => {
    for (const v of [undefined, null, '', '   ', 7, NaN]) {
      SI = { ...BASE, shares_asof: '2026-11-24' } as ShortInterest;
      if (v !== undefined) (SI as any).shares_source = v;
      const r = render(<RealtimeChips symbol="ABC" />);
      expect(chip()!.getAttribute('title')).toBe(todayTitle(BASE));
      expect(chip()!.getAttribute('title')).not.toMatch(/Share count|as of/);
      r.unmount();
    }
    // the older API exactly: neither key present
    SI = { ...BASE };
    render(<RealtimeChips symbol="ABC" />);
    expect(chip()!.getAttribute('title')).toBe(todayTitle(BASE));
  });

  it('NEGATIVE: a junk shares_asof (null / "" / a number / NaN) adds no "as of"', () => {
    for (const a of [null, '', 20261124, NaN]) {
      SI = { ...BASE, shares_source: 'served source words', shares_asof: a as any };
      const r = render(<RealtimeChips symbol="ABC" />);
      expect(chip()!.getAttribute('title')).toBe(`${todayTitle(BASE)}\nShare count: served source words`);
      expect(chip()!.getAttribute('title')).not.toMatch(/NaN|undefined|null|as of/);
      r.unmount();
    }
  });

  it('NEGATIVE: a low squeeze still draws no chip, whatever the source', () => {
    SI = { ...BASE, squeeze: 'low', shares_source: 'served source words' };
    render(<RealtimeChips symbol="ABC" />);
    expect(chip()).toBeNull();
    expect(screen.queryByText(/Short/)).toBeNull();
  });

  it('source: the sentence is the only addition — one served guard, no arithmetic on the source fields', async () => {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    const src: string = fs.readFileSync(`${root}/src/components/RealtimeChips.tsx`, 'utf8');
    expect(src.split('shareCountText(').length - 1).toBe(2);
    expect(src).not.toMatch(/shares_(source|asof)[^;\n]*(toFixed|[*\/+-]\s*\d)/);
    const hook: string = fs.readFileSync(`${root}/src/hooks/useRealtimeSignals.ts`, 'utf8');
    expect(hook).toMatch(/shares_source\?: string \| null;/);
    expect(hook).toMatch(/shares_asof\?: string \| null;/);
  });
});
