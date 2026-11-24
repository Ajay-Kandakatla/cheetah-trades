import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import { GgSiExtremeNote } from './GgSiExtremeNote';
import { GgShortInterestLabel } from './GgShortInterestLabel';
import { ShortInterestChip } from './ShortInterestChip';
import { GgwTagsRow } from './GajjalaWatchTags';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';
import { parseGgw, type GgwBoard, type GgwRow } from '../lib/gajjalaWatch';

/* 🩳 the share-count flags print VERBATIM on every surface (2026-11-24, spec sidilute §3.7 [C6]). Ajay: "Make sure we are
 * looking for Dilution.." · "Also split related events and filing so we flag them in the right way". No new chip component
 * and no colour: the flags arrive INSIDE the served `chip`, `extreme.short` and `extreme.title`, so the house chip, the 🎾
 * card label, the 👀 Watch tags row and the 👀 EXTREME note print them as served. The REAL hook over a stubbed fetch routed
 * by pathname. NEGATIVES: a block with no flags prints exactly the old strings; the EXTREME note keeps the short form (never
 * the card text); a stale block with a flagged EXTREME note prints no note. */

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const SI_PATH = '/short-interest/map';
const SMTK_CHIP = '🩳 SI 8.9% shs out · 1.0d · 10/30 · ⚠️ float stale · ✂️ split 11/23 · 📄 S-4 11/13';
const SMTK_TITLE = '🩳 Short interest — SMTK … ⚠️ float stale — 4.7× more shares than when the float was read … SEC cover counts: 565,275 on 8/12 → 4,859,369 on 11/11 — 8.6×';
const SMTK_FLAGS = [
  { key: 'float_stale', emoji: '⚠️', short: '⚠️ float stale', text: '⚠️ float stale — served' },
  { key: 'split', emoji: '✂️', short: '✂️ split 11/23', text: '✂️ served split' },
  { key: 'filing', emoji: '📄', short: '📄 S-4 11/13', text: '📄 dilution filing: S-4 11/13' },
];
const JZ_X = {
  text: '🩳 SI EXTREME 27.2% float · 2.1d · 10/30 · ✂️ split due 12/24',
  short: '🩳 SI EXTREME 27.2% float · ✂️ split due 12/24',
  title: '🩳 EXTREME short interest — 27.2% of the float … ✂️ 1-for-10 reverse split due 12/24 … served study note.',
  basis: 'si_doc_float',
};
const JZ_SPLIT = { key: 'split', emoji: '✂️', short: '✂️ split due 12/24', text: '✂️ 1-for-10 reverse split due 12/24' };
const PLAIN_X = { text: '🩳 SI EXTREME 44.0% float · 1.0d · 10/30', short: '🩳 SI EXTREME 44.0% float', title: 'served CLRO hover', basis: 'si_doc_float' };
const SI: Record<string, unknown> = {
  SMTK: { symbol: 'SMTK', status: 'ok', tier: null, chip: SMTK_CHIP, title: SMTK_TITLE, rows: [], extreme: null,
          basis: { status: 'ok', float_refused: 'diluted', refused_reasons: ['diluted'], flags: SMTK_FLAGS } },
  JZ: { symbol: 'JZ', status: 'ok', tier: 'extreme', chip: JZ_X.text, title: 'jz chip title', rows: [], extreme: JZ_X,
        basis: { status: 'ok', float_refused: null, flags: [JZ_SPLIT] } },
  CLRO: { symbol: 'CLRO', status: 'ok', tier: 'extreme', chip: PLAIN_X.text, title: 'clro chip title', rows: [], extreme: PLAIN_X },
  OLD: { symbol: 'OLD', status: 'stale', chip: '🩳 SI 30.6% float · 5.0d · 8/31 · stale', title: 'stale', rows: [], extreme: JZ_X,
         basis: { status: 'ok', flags: [JZ_SPLIT] } },
};

const pathOf = (u: string) => new URL(u, 'http://x').pathname;
const symsOf = (u: string) => decodeURIComponent(new URL(u, 'http://x').searchParams.get('symbols') || '').split(',').filter(Boolean);
let siCalls = 0;
function routedFetch() {
  siCalls = 0;
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (pathOf(url).endsWith(SI_PATH)) {
      siCalls += 1;
      const out: Record<string, unknown> = {};
      for (const s of symsOf(url)) if (SI[s]) out[s] = SI[s];
      return { ok: true, json: async () => ({ items: out, n: Object.keys(out).length, max_symbols: 200 }) } as unknown as Response;
    }
    if (pathOf(url).endsWith('/growth/tags')) return { ok: true, json: async () => ({ tags: {} }) } as unknown as Response;
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
}
const BASE = (parseGgw(clone(autoFixture)) as GgwBoard).rows[0];
const rowOf = (sym: string): GgwRow => ({ ...clone(BASE), symbol: sym, auto: null, aplus: null, tags: null });

describe('🩳 share-count flags print verbatim', { timeout: 20000 }, () => {
  beforeEach(() => { _resetShortInterestCache(); _resetGrowthTagsCache(); routedFetch(); });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetShortInterestCache(); _resetGrowthTagsCache(); });

  it('the served SMTK chip prints verbatim through ShortInterestChip, with its served title', async () => {
    render(<ShortInterestChip symbol="SMTK" />);
    const el = await screen.findByTestId('si-chip');
    expect(el.textContent).toBe(SMTK_CHIP);
    expect(el.getAttribute('title')).toBe(SMTK_TITLE);
    expect(el.className).toBe('cm-badge cm-badge-muted');
    expect(el.getAttribute('data-si-tier')).toBeNull();
  });

  it('the served SMTK chip prints verbatim through the 🎾 GgShortInterestLabel', async () => {
    render(<GgShortInterestLabel symbol="SMTK" testid="gg-si-SMTK" />);
    const el = await screen.findByTestId('gg-si-SMTK');
    expect(el.textContent).toBe(SMTK_CHIP);
    expect(el.getAttribute('title')).toBe(SMTK_TITLE);
    expect(el.className).toBe('cm-note gg-line gg-si-label');
  });

  it('the served SMTK chip prints verbatim in the 👀 Watch tags row', async () => {
    const c = render(<GgwTagsRow row={rowOf('SMTK')} />).container;
    await waitFor(() => expect(c.querySelector('[data-testid="ggw-tags-SMTK"] [data-testid="si-chip"]')).not.toBeNull());
    const chip = c.querySelector('[data-testid="ggw-tags-SMTK"] [data-testid="si-chip"]')!;
    expect(chip.textContent).toBe(SMTK_CHIP);
    expect(chip.getAttribute('title')).toBe(SMTK_TITLE);
  });

  it('a served extreme.short WITH flags prints verbatim on the 👀 Watch tile, its served title on hover [C6]', async () => {
    render(<GgSiExtremeNote symbol="JZ" testid="ggw-si-extreme-JZ" />);
    const el = await screen.findByTestId('ggw-si-extreme-JZ');
    expect(el.textContent).toBe(JZ_X.short);
    expect(el.getAttribute('title')).toBe(JZ_X.title);
    expect(el.className).toBe('ggw-chip ggw-si-extreme');
    expect(el.getAttribute('data-si-tier')).toBe('extreme');
  });

  it('the 🎾 label prints the served extreme.text with its flag; the Watch tags row drops the chip when EXTREME', async () => {
    render(<GgShortInterestLabel symbol="JZ" testid="gg-si-JZ" />);
    expect((await screen.findByTestId('gg-si-JZ')).textContent).toBe(JZ_X.text);
    const c = render(<GgwTagsRow row={rowOf('JZ')} />).container;
    await waitFor(() => expect(siCalls).toBeGreaterThan(0));
    await new Promise((r) => setTimeout(r, 120));
    expect(c.querySelector('[data-testid="ggw-tags-JZ"] [data-testid="si-chip"]')).toBeNull();
  });

  it('NEGATIVE: a block with no basis prints exactly the old strings (the note keeps its short form)', async () => {
    render(<><GgSiExtremeNote symbol="CLRO" testid="n-CLRO" /><ShortInterestChip symbol="CLRO" /></>);
    expect((await screen.findByTestId('n-CLRO')).textContent).toBe(PLAIN_X.short);
    expect(screen.getByTestId('n-CLRO').getAttribute('title')).toBe(PLAIN_X.title);
    expect(screen.getByTestId('si-chip').textContent).toBe(PLAIN_X.text);
  });

  it('NEGATIVE: the note never prints the longer card text; a stale block with a flagged note prints no note', async () => {
    render(<><GgSiExtremeNote symbol="JZ" testid="n-JZ" /><GgSiExtremeNote symbol="OLD" testid="n-OLD" /></>);
    expect((await screen.findByTestId('n-JZ')).textContent).not.toBe(JZ_X.text);
    await new Promise((r) => setTimeout(r, 120));
    expect(screen.queryByTestId('n-OLD')).toBeNull();
  });
});
