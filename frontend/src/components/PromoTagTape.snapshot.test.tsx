/* 🕰️ (2026-10-16, DECISIONS11 D1 / BUILD_SPEC11 §4 WP-B1 step 2 / AMENDMENTS11 F12) — the BYTE-IDENTICAL guard for the
 * Promo Circuit tape. Ajay asked for "the graph component from that" (the Promo Circuit tab) on Gajjala's A+ entries;
 * the drawing moves into a shared primitive (TapeChart.tsx) and this snapshot proves PromoTagTape / MiniTape render the
 * SAME markup after the extraction — cut by the main session on the UNTOUCHED PromoTagTape.tsx (commit 714b7c13),
 * BEFORE any refactor, and never regenerated after (its sha256 is recorded in AMENDMENTS11 F12).
 *
 * Regenerate (only on the untouched component, never after the refactor):
 *   PTT_WRITE_SNAPSHOT=1 rtk proxy npx vitest run src/components/PromoTagTape.snapshot.test.tsx */
import { render, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PromoTagTape, MiniTape, _resetLiteCache, type TapePayload } from './PromoTagTape';
import sampleJson from './__fixtures__/promo_tape_c_2026_10_16.json';
import liteJson from './__fixtures__/promo_tape_c_lite_2026_10_16.json';

// The frontend tsconfig carries no node types: the fixtures are static JSON imports and the one write path (the cut)
// reaches node:fs the way GajjalaBoard.track_record.test.tsx does — a dynamic import tsc does not resolve.
const FIX = 'src/components/__fixtures__/';
const SNAP = FIX + 'promo_tape_c_svg_2026_10_16.json';
const RECIPE = 'PTT_WRITE_SNAPSHOT=1 rtk proxy npx vitest run src/components/PromoTagTape.snapshot.test.tsx — ONLY on the untouched PromoTagTape.tsx (714b7c13), never after the refactor';
const ENV: Record<string, string | undefined> = ((globalThis as any).process?.env) ?? {};
async function nodeFs(): Promise<any> { return await import(/* @vite-ignore */ ('node:' + 'fs')); }

const sample = sampleJson as unknown as TapePayload;
const lite = liteJson as unknown;

async function renderBoth(data: TapePayload): Promise<{ full: string; mini: string }> {
  const a = render(<PromoTagTape ticker={data.ticker} data={data} />);
  const full = a.container.innerHTML;
  a.unmount();
  _resetLiteCache();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => lite }));
  const b = render(<MiniTape ticker={data.ticker} width={100} />);
  await waitFor(() => expect(b.container.querySelector('.ptt__mini svg')).not.toBeNull());
  const mini = b.container.querySelector('.ptt__mini')!.outerHTML;
  b.unmount();
  return { full, mini };
}

afterEach(() => { vi.unstubAllGlobals(); _resetLiteCache(); });

describe('PromoTagTape + MiniTape — byte-identical snapshot of the live sample (ticker C, 1,241 bars)', () => {
  it('renders exactly the recorded markup (full tape and mini sparkline)', async () => {
    expect(sample.bars.length).toBeGreaterThan(1000);
    const got = await renderBoth(sample);
    expect(got.full.length).toBeGreaterThan(1000);
    expect(got.mini).toContain('<svg');
    const fs = await nodeFs();
    if (ENV.PTT_WRITE_SNAPSHOT === '1') {
      fs.writeFileSync(SNAP, JSON.stringify({ _recipe: RECIPE, full: got.full, mini: got.mini }, null, 1) + '\n');
    }
    if (!fs.existsSync(SNAP)) throw new Error(`snapshot missing — ${RECIPE}`);
    const want = JSON.parse(fs.readFileSync(SNAP, 'utf8'));
    expect(got.full).toBe(want.full);
    expect(got.mini).toBe(want.mini);
  });

  it('NEGATIVE: one changed close renders a different full tape (the comparison bites)', async () => {
    const fs = await nodeFs();
    const want = JSON.parse(fs.readFileSync(SNAP, 'utf8'));
    const bars = sample.bars.map((b, i) => (i === 600 ? { ...b, c: b.c * 1.5 } : b));
    const got = await renderBoth({ ...sample, bars });
    expect(got.full).not.toBe(want.full);
  });
});
