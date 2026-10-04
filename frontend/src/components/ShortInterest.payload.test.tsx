import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { ShortInterestChip } from './ShortInterestChip';
import { ShortInterestPanel } from './ShortInterestPanel';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetRulesInfoCache } from '../hooks/useRulesInfo';
import { SI_NOT_WARMED_TEXT } from '../lib/shortInterest';

/* 🩳 The served payload through the real components.
 *
 * Reads the SAME fixture the backend test pins si_block() against
 * (backend/tests/fixtures/short_interest_blocks_2026_10_03.json), or a live
 * payload in that shape: SI_LIVE_PAYLOAD=<path>/si_live_blocks.json (written
 * by backend/scripts/short_interest_live_check.py). For every case the chip
 * prints block.chip verbatim with block.title on hover (nothing when chip is
 * null), and the ticker panel prints block.rows in order. No skip: a missing
 * file FAILS, so a renamed fixture can never pass this silently. */

/* Node built-ins by a runtime specifier: the app tsconfig carries no node
 * types, and vitest runs this file under Node, so the import is typed `any`. */
const NODE = { fs: 'node:fs', path: 'node:path', url: 'node:url' };
const ENV: string | undefined = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.SI_LIVE_PAYLOAD;

type Case = {
  name: string;
  doc: Record<string, unknown> | null;
  block: { symbol?: string; chip: string | null; title: string; rows: { k: string; v: string }[] } | null;
};

async function load(): Promise<{ today: string; cases: Case[] }> {
  const fs = await import(/* @vite-ignore */ NODE.fs);
  const path = await import(/* @vite-ignore */ NODE.path);
  const url = await import(/* @vite-ignore */ NODE.url);
  const here = path.dirname(url.fileURLToPath(import.meta.url));
  const file: string = ENV
    ? (path.isAbsolute(ENV) ? ENV : path.resolve((globalThis as any).process.cwd(), ENV))
    : path.resolve(here, '../../../backend/tests/fixtures/short_interest_blocks_2026_10_03.json');
  if (!fs.existsSync(file)) throw new Error(`short-interest payload not found: ${file}`);
  const j = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!j || !Array.isArray(j.cases) || j.cases.length === 0) throw new Error(`no cases in ${file}`);
  return j;
}

function symOf(c: Case): string {
  const d = c.doc || {};
  return String(c.block?.symbol || d.symbol || d._id || c.name).toUpperCase();
}

function stub(sym: string, block: Case['block']) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/short-interest/map')) {
      const items = block ? { [sym]: block } : {};
      return { ok: true, json: async () => ({ items, n: block ? 1 : 0, max_symbols: 200 }) } as unknown as Response;
    }
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
}

describe('🩳 served payload → chip + panel, verbatim', () => {
  beforeEach(() => { _resetShortInterestCache(); _resetRulesInfoCache(); });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('the payload file exists and has cases (fails loudly, never skips)', async () => {
    expect((await load()).cases.length).toBeGreaterThan(0);
  });

  it('every case: chip text = block.chip, hover = block.title, panel rows = block.rows', async () => {
    const { cases } = await load();
    for (const c of cases) {
      const sym = symOf(c);
      _resetShortInterestCache();
      stub(sym, c.block);
      const { container, unmount } = render(<div><ShortInterestChip symbol={sym} /><ShortInterestPanel symbol={sym} /></div>);
      const panel = await screen.findByTestId('si-panel');
      if (c.block && typeof c.block.chip === 'string' && c.block.chip) {
        const chip = screen.getByTestId('si-chip');
        expect(chip.textContent, c.name).toBe(c.block.chip);
        expect(chip.getAttribute('title'), c.name).toBe(c.block.title);
      } else {
        expect(container.querySelector('[data-testid=si-chip]'), c.name).toBeNull();
      }
      if (c.block) {
        await waitFor(() => expect(panel.querySelectorAll('dt').length, c.name).toBe(c.block!.rows.length));
        const rows = Array.from(panel.querySelectorAll('dt')).map((dt, i) => ({
          k: dt.textContent, v: panel.querySelectorAll('dd')[i]?.textContent,
        }));
        expect(rows, c.name).toEqual(c.block.rows);
      } else {
        expect(panel.textContent, c.name).toContain(SI_NOT_WARMED_TEXT);
      }
      unmount();
      vi.unstubAllGlobals();
    }
  });
});
