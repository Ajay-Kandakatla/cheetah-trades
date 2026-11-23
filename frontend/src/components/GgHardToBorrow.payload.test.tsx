import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgHardToBorrowChip, GgHardToBorrowFault, GgHardToBorrowLabel } from './GgHardToBorrow';
import { _resetRegShoCache } from '../hooks/useRegSho';
import { parseRegSho } from '../lib/regSho';

/* 🔒 The served payload through the real components (2026-11-22, spec htb §4 fe).
 *
 * Reads the golden the backend test pins `payload()` against (backend/tests/fixtures/reg_sho_payload_2026_11_22.json,
 * `{"now": …, "payload": {…}}`, owned by the `be` package), or a live body: REG_SHO_LIVE_PAYLOAD=<abs path> (the raw
 * GET /short-interest/reg-sho JSON, or the same `{payload}` wrapper). For every `on` item the real chip prints its `chip`
 * and its `short`, the real label prints its `label`, hover = its `title`. No skip: a missing file FAILS. */

const NODE = { fs: 'node:fs', path: 'node:path', url: 'node:url' };
const ENV: string | undefined = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.REG_SHO_LIVE_PAYLOAD;

async function load(): Promise<Record<string, any>> {
  const fs = await import(/* @vite-ignore */ NODE.fs);
  const path = await import(/* @vite-ignore */ NODE.path);
  const url = await import(/* @vite-ignore */ NODE.url);
  const here = path.dirname(url.fileURLToPath(import.meta.url));
  const file: string = ENV
    ? (path.isAbsolute(ENV) ? ENV : path.resolve((globalThis as any).process.cwd(), ENV))
    : path.resolve(here, '../../../backend/tests/fixtures/reg_sho_payload_2026_11_22.json');
  if (!fs.existsSync(file)) throw new Error(`reg-sho payload not found: ${file}`);
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

describe('🔒 served payload → chip, short, label, verbatim', () => {
  beforeEach(() => _resetRegShoCache());
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetRegShoCache(); });

  it('the payload file exists and parses as the reg-sho payload (fails loudly, never skips)', async () => {
    const p = await load();
    expect(p.kind).toBe('reg_sho_threshold');
    expect(parseRegSho(p)).not.toBeNull();
    if (!ENV) {
      /* the golden (11-20 Nasdaq + NYSE, 11-19 Cboe): AKAN is on the Nasdaq list, AKANW is not */
      expect(p.items.AKAN?.state).toBe('on');
      expect(p.items.AKANW).toBeUndefined();
    }
  });

  it('every `on` item renders its served chip, short and label through the real components', async () => {
    const p = await load();
    const on = Object.entries(p.items as Record<string, any>).filter(([, v]) => v && v.state === 'on');
    if (!ENV) expect(on.length).toBeGreaterThan(0);
    for (const [key, it] of on) {
      _resetRegShoCache();
      stub(p);
      const { unmount } = render(<>
        <GgHardToBorrowChip symbol={key} testid="c" />
        <GgHardToBorrowChip symbol={key} testid="s" form="short" />
        <GgHardToBorrowLabel symbol={key} testid="l" />
      </>);
      const c = await screen.findByTestId('c');
      expect(c.textContent, key).toBe(it.chip);
      expect(c.getAttribute('title'), key).toBe(it.title);
      expect(c.classList.contains('gg-htb-stale'), key).toBe(it.stale === true);
      expect(screen.getByTestId('s').textContent, key).toBe(it.short);
      expect(screen.getByTestId('l').textContent, key).toBe(it.label);
      expect(screen.getByTestId('l').getAttribute('title'), key).toBe(it.title);
      unmount();
      vi.unstubAllGlobals();
    }
  });

  it('the served fault_text prints verbatim when served, and nothing when null', async () => {
    const p = await load();
    stub(p);
    render(<><span data-testid="anchor" /><GgHardToBorrowFault testid="f" /></>);
    await screen.findByTestId('anchor');
    await new Promise((r) => setTimeout(r, 20));
    const f = screen.queryByTestId('f');
    if (typeof p.fault_text === 'string' && p.fault_text.trim()) expect(f?.textContent).toBe(p.fault_text);
    else expect(f).toBeNull();
  });
});
