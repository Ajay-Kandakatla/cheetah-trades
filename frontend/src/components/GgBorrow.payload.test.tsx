import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgBorrowChip, GgBorrowLabel } from './GgBorrow';
import { _resetBorrowCache, BR_CHUNK } from '../hooks/useBorrow';
import { parseBorrow } from '../lib/borrow';

/* 💸 The served payload through the real components (2026-11-22, spec borrow §4 fe part B) [C10].
 *
 * Reads the golden the backend test pins `payload()` against (backend/tests/fixtures/ibkr_borrow_payload_2026_11_22.json,
 * `{"now": …, "symbols": […], "payload": {…}}`, owned by the `be` package), or a live body:
 * IBKR_BORROW_LIVE_PAYLOAD=<abs path> (the raw GET /short-interest/borrow JSON, or the same `{payload}` wrapper). Every
 * served item prints its chip, its short and its label through the real components ONLY where that form is served — a
 * null form renders nothing; hover = its title. No skip: a missing file FAILS. */

const NODE = { fs: 'node:fs', path: 'node:path', url: 'node:url' };
const ENV: string | undefined = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.IBKR_BORROW_LIVE_PAYLOAD;

async function load(): Promise<Record<string, any>> {
  const fs = await import(/* @vite-ignore */ NODE.fs);
  const path = await import(/* @vite-ignore */ NODE.path);
  const url = await import(/* @vite-ignore */ NODE.url);
  const here = path.dirname(url.fileURLToPath(import.meta.url));
  const file: string = ENV
    ? (path.isAbsolute(ENV) ? ENV : path.resolve((globalThis as any).process.cwd(), ENV))
    : path.resolve(here, '../../../backend/tests/fixtures/ibkr_borrow_payload_2026_11_22.json');
  if (!fs.existsSync(file)) throw new Error(`borrow payload not found: ${file}`);
  const j = JSON.parse(fs.readFileSync(file, 'utf8'));
  const p = j && j.kind ? j : j?.payload;
  if (!p || typeof p !== 'object') throw new Error(`no payload in ${file}`);
  return p;
}

function stub(p: unknown) {
  const f = vi.fn(async () => ({ ok: true, json: async () => JSON.parse(JSON.stringify(p)) }) as unknown as Response);
  vi.stubGlobal('fetch', f);
  return f;
}
const servedText = (x: unknown): x is string => typeof x === 'string' && x.trim() !== '';

describe('💸 served payload → chip, short, label, verbatim', () => {
  beforeEach(() => _resetBorrowCache());
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetBorrowCache(); });

  it('the payload file exists and parses as the borrow payload (fails loudly, never skips); BR_CHUNK == max_symbols', async () => {
    const p = await load();
    expect(p.kind).toBe('ibkr_borrow');
    expect(parseBorrow(p)).not.toBeNull();
    expect(BR_CHUNK).toBe(p.max_symbols);
    if (!ENV) {
      /* the golden (the trimmed 2026-11-22 22:57:25 fixture): DBGI is listed, AKAN is not in the file, DBGIW is absent too */
      expect(p.status).toBe('ok');
      expect(p.items.DBGI?.state).toBe('listed');
      expect(p.items.AKAN?.state).toBe('absent');
      expect(p.items.AESG?.short).toBeNull();
    }
  });

  it('every served item prints exactly the forms served for it through the real components; a null form draws nothing', async () => {
    const p = await load();
    const items = Object.entries(p.items as Record<string, any>).filter(([, v]) => v && typeof v === 'object');
    if (!ENV) {
      expect(items.filter(([, v]) => v.state === 'listed').length).toBeGreaterThan(0);
      expect(items.filter(([, v]) => v.state === 'absent').length).toBeGreaterThan(0);
    }
    for (const [key, it] of items) {
      _resetBorrowCache();
      stub(p);
      const { unmount } = render(<>
        <span data-testid="anchor" />
        <GgBorrowChip symbol={key} testid="c" />
        <GgBorrowChip symbol={key} testid="s" form="short" />
        <GgBorrowLabel symbol={key} testid="l" />
      </>);
      await screen.findByTestId('anchor');
      if (servedText(it.label)) await screen.findByTestId('l');
      else if (servedText(it.chip)) await screen.findByTestId('c');
      await new Promise((r) => setTimeout(r, 5));
      for (const [id, form] of [['c', 'chip'], ['s', 'short'], ['l', 'label']] as const) {
        const el = screen.queryByTestId(id);
        if (servedText(it[form])) {
          expect(el, `${key} ${form}`).not.toBeNull();
          expect(el!.textContent, `${key} ${form}`).toBe(it[form]);
          expect(el!.getAttribute('title'), `${key} ${form}`).toBe(it.title);
          expect(el!.getAttribute('data-brw-state'), `${key} ${form}`).toBe(it.state);
          expect(el!.classList.contains('gg-brw-stale'), `${key} ${form}`).toBe(it.stale === true);
        } else {
          expect(el, `${key} ${form} is served null → nothing`).toBeNull();
        }
      }
      if (it.state === 'listed' && !ENV) {
        expect(servedText(it.chip), key).toBe(true);
        expect(servedText(it.label), key).toBe(true);
      }
      unmount();
      vi.unstubAllGlobals();
    }
  });

  it('NEGATIVE: an asked name the payload does not serve renders nothing on any form', async () => {
    const p = await load();
    stub(p);
    const { container } = render(<div className="row"><GgBorrowChip symbol="ZZZZZZZZZ" testid="c" lead />
      <GgBorrowChip symbol="ZZZZZZZZZ" testid="s" form="short" /><GgBorrowLabel symbol="ZZZZZZZZZ" testid="l" /></div>);
    await new Promise((r) => setTimeout(r, 20));
    expect(container.innerHTML).toBe('<div class="row"></div>');
  });
});
