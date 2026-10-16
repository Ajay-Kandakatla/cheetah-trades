/* DojiSweepBoardNote against the LIVE 🕯️ boards (2026-10-16).
 *
 * Ajay 2026-10-16, verbatim: "create me a new tab for Doji candle after a
 * sweep. For any stocks after a down trend. May be from all chart maps
 * especially on the 60% 70% down stocks".
 *
 * The live fixture components/__fixtures__/doji_sweep_live_2026_10_16.json is
 * CAPTURED by the main session from the throwaway api (BUILD_SPEC6 §5.5 step 8:
 * `{"_recipe", "boards": {default, w52_70, reclaimed, body10, sort_test}}`, each
 * the whole `/chart-maps?tab=doji_sweep…&limit=24` response) and never
 * hand-edited. Until it exists the live block SKIPS. When it runs, every
 * captured board must render with no NaN / undefined / None / b-word, the
 * header must print the served header byte for byte, and every chip must
 * carry a served label — the note composes nothing.
 *
 * The checker itself is proven on the WP-B golden (present in the repo) and on
 * NEGATIVE mutations of it, so a live run that passes means the live payload
 * passed, never that the checker was blind. */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import DojiSweepBoardNote from './DojiSweepBoardNote';
import type { CmDojiSweepBoard } from '../lib/dojiSweep';
import type { CmSort } from '../lib/chartMaps';

type Payload = { doji_sweep_board: CmDojiSweepBoard | null; sorts?: CmSort[] | null; sort?: string | null };
type Item = { key: string; label: string };
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

/* tsc-safe fixture read (the DojiSweepBoardNote.test precedent): no node types
 * in the app's tsconfig, so `node:fs` is imported dynamically; paths are
 * relative to frontend/ (vitest's cwd). */
async function readJsonIfPresent(rel: string): Promise<any | null> {
  try {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    const p = `${root}/${rel}`;
    return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null;
  } catch {
    return null;
  }
}
const LIVE_PATH = 'src/components/__fixtures__/doji_sweep_live_2026_10_16.json';
const LIVE: { _recipe?: unknown; boards?: Record<string, Payload> } | null = await readJsonIfPresent(LIVE_PATH);
const GOLDEN: Record<string, Payload> | null =
  await readJsonIfPresent('src/components/__fixtures__/doji_sweep_board_golden_2026_10_16.json');
const LIVE_KEYS = ['default', 'w52_70', 'reclaimed', 'body10', 'sort_test'];

/* the b-word is spelt in two halves so the word itself never sits in this file */
const BAD_WORDS = new RegExp(`${['bou', 'nc'].join('')}|NaN|undefined|None`);
const B_WORD = new RegExp(['bou', 'nc'].join(''), 'i');   // any case; "None" stays case-sensitive ("none of the three reads" is served)

afterEach(() => cleanup());

/** Render one served payload and list what is wrong with it (empty = clean). */
function liveErrors(name: string, p: Payload): string[] {
  const errs: string[] = [];
  const b = p?.doji_sweep_board;
  if (!b || typeof b.header !== 'string') return [`${name}: no doji_sweep_board with a string header`];
  const { container } = render(<DojiSweepBoardNote board={b} sorts={p.sorts ?? null} sort={p.sort ?? null}
                                                   onSort={() => {}} onToggleFilter={() => {}} onBody={() => {}} />);
  try {
    const text = container.textContent || '';
    const bad = BAD_WORDS.exec(text) || B_WORD.exec(text);
    if (bad) errs.push(`${name}: the rendered note says "${bad[0]}"`);
    const header = container.querySelector('[data-testid="cm-dj-header"]');
    if (!header) errs.push(`${name}: cm-dj-header is not rendered`);
    else if (header.textContent !== b.header) errs.push(`${name}: cm-dj-header "${header.textContent}" != the served header "${b.header}"`);
    const items: Item[] = Array.isArray((b.filters as { items?: Item[] } | null)?.items) ? (b.filters as { items: Item[] }).items : [];
    const served = new Map(items.map((i) => [i.key, i.label]));
    const boxes = Array.from(container.querySelectorAll<HTMLInputElement>('input[data-testid^="cm-dj-filter-"]'))
      .filter((x) => x.getAttribute('data-testid') !== 'cm-dj-filter-mode');
    if (b.state === 'ready' && boxes.length !== items.length) errs.push(`${name}: ${boxes.length} chips rendered, ${items.length} served`);
    for (const box of boxes) {
      const key = (box.getAttribute('data-testid') || '').slice('cm-dj-filter-'.length);
      const label = served.get(key);
      const txt = box.closest('label')?.textContent || '';
      if (label == null) errs.push(`${name}: chip "${key}" is not a served chip`);
      else if (!txt.includes(label)) errs.push(`${name}: chip "${key}" reads "${txt}", not the served label "${label}"`);
    }
  } finally {
    cleanup();
  }
  return errs;
}

describe('🕯️ live-board checker — proven on the WP-B golden (2026-10-16)', () => {
  it.skipIf(!GOLDEN)('every golden board passes the checker', () => {
    for (const [k, p] of Object.entries(GOLDEN || {})) {
      if (k.startsWith('_')) continue;
      expect(liveErrors(k, p), k).toEqual([]);
    }
  });

  it.skipIf(!GOLDEN)('NEGATIVE: a NaN / undefined / None / b-word in a served line is caught', () => {
    const base = (GOLDEN as Record<string, Payload>).default;
    for (const bad of ['NaN', 'undefined', 'None', ['Bou', 'nce'].join('')]) {
      const p = clone(base);
      p.doji_sweep_board!.header = `${p.doji_sweep_board!.header} ${bad}`;
      expect(liveErrors('mutated', p).join('\n'), bad).toMatch(/the rendered note says/);
      const q = clone(base);
      q.doji_sweep_board!.study = { ...q.doji_sweep_board!.study, text: `${q.doji_sweep_board!.study.text} ${bad}` };
      expect(liveErrors('mutated', q).join('\n'), `study ${bad}`).toMatch(/the rendered note says/);
    }
  });

  it.skipIf(!GOLDEN)('NEGATIVE: a board with no header, or no board, is reported — never passed silently', () => {
    const base = (GOLDEN as Record<string, Payload>).default;
    const p = clone(base) as any;
    delete p.doji_sweep_board.header;
    expect(liveErrors('no-header', p)).toEqual(['no-header: no doji_sweep_board with a string header']);
    expect(liveErrors('null', { doji_sweep_board: null })).toEqual(['null: no doji_sweep_board with a string header']);
  });

  it.skipIf(!GOLDEN)('NEGATIVE: a chip the server did not serve is caught', () => {
    const base = (GOLDEN as Record<string, Payload>).default;
    const p = clone(base) as any;
    const items = p.doji_sweep_board.filters.items as Item[];
    expect(items.length).toBeGreaterThan(0);
    const extra = { ...items[0], key: 'zz_unserved' };
    p.doji_sweep_board.filters.items = [...items, extra];
    p.doji_sweep_board.filters.keys = [...(p.doji_sweep_board.filters.keys || []), 'zz_unserved'];
    const errs = liveErrors('extra-chip', p);
    // The note only knows DJ_FILTER_KEYS, so the unknown key is dropped by the note → a count mismatch.
    expect(errs.join('\n')).toMatch(/chips rendered, \d+ served/);
  });
});

describe.skipIf(!LIVE)('🕯️ live boards (fixture captured from the throwaway api, BUILD_SPEC6 §5.5 step 8)', () => {
  it('the fixture carries every captured view and its recipe', () => {
    expect(LIVE?._recipe).toBeTruthy();
    for (const k of LIVE_KEYS) expect(LIVE?.boards?.[k], k).toBeTruthy();
  });

  it('every captured board renders clean: no NaN / undefined / None / b-word, header == served, chips == served labels', () => {
    for (const k of LIVE_KEYS) {
      const p = LIVE?.boards?.[k] as Payload;
      expect(liveErrors(k, p), k).toEqual([]);
      expect(p.doji_sweep_board?.state, k).toBe('ready');
    }
  });
});
