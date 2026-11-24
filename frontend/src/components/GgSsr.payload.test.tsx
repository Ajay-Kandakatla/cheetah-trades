import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgSsrChip, GgSsrFault, GgSsrLabel } from './GgSsr';
import { _resetSsrCache, SSR_CHUNK } from '../hooks/useSsr';
import { parseSsr } from '../lib/ssr';

/* ⛔ The served payload through the real components (2026-11-23, spec ssr §4 W4).
 *
 * Reads the golden the backend test pins `payload()` against (backend/tests/fixtures/ssr_payload_2026_11_24.json,
 * `{"now": …, "symbols": […], "payload": {…}}`, owned by W1), or a live body: SSR_LIVE_PAYLOAD=<abs path> (the raw
 * GET /short-interest/ssr JSON, or the same `{payload}` wrapper). Every served item prints its chip, its short and its
 * label through the real components ONLY where that form is served — a null form renders nothing; hover = its title.
 * Every asked name the payload does not serve as an item (off, a quiet unknown) renders nothing. No skip: a missing
 * file FAILS. */

const NODE = { fs: 'node:fs', path: 'node:path', url: 'node:url' };
const ENV: string | undefined = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.SSR_LIVE_PAYLOAD;

async function load(): Promise<Record<string, any>> {
  const fs = await import(/* @vite-ignore */ NODE.fs);
  const path = await import(/* @vite-ignore */ NODE.path);
  const url = await import(/* @vite-ignore */ NODE.url);
  const here = path.dirname(url.fileURLToPath(import.meta.url));
  const file: string = ENV
    ? (path.isAbsolute(ENV) ? ENV : path.resolve((globalThis as any).process.cwd(), ENV))
    : path.resolve(here, '../../../backend/tests/fixtures/ssr_payload_2026_11_24.json');
  if (!fs.existsSync(file)) throw new Error(`ssr payload not found: ${file}`);
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
const tick = () => new Promise((r) => setTimeout(r, 5));

describe('⛔ served payload → chip, short, label, fault, verbatim', () => {
  beforeEach(() => _resetSsrCache());
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetSsrCache(); });

  it('the payload file exists and parses as the ssr payload (fails loudly, never skips); SSR_CHUNK == max_symbols', async () => {
    const p = await load();
    expect(p.kind).toBe('ssr_rule_201');
    expect(parseSsr(p)).not.toBeNull();
    expect(SSR_CHUNK).toBe(p.max_symbols);
    if (!ENV) {
      /* the golden (spec §4 W1 step 5, pinned at 2026-11-23 14:00 ET) */
      expect(p.status).toBe('ok');
      expect(p.items.GIPR?.state).toBe('on');
      expect(p.items.GIPR?.source).toBe('official');
      expect(p.items.AKAN?.state).toBe('on');
      expect(p.items.AKAN?.source).toBe('computed');
      expect(p.items.GP?.retriggered).toBe(true);
      expect(p.items.PXED?.state).toBe('unknown');
      expect(p.items.PXED?.chip).toBeNull();
      expect(p.items.PXED?.short).toBeNull();
      expect(servedText(p.items.PXED?.label)).toBe(true);
      expect(p.items.AAPL).toBeUndefined();
      expect(p.states.AAPL).toBe('off');
      expect(p.items.ZZCO).toBeUndefined();
      expect(p.states.ZZCO).toBe('unknown');
      expect(p.whys.ZZCO).toBe('computed_only');
    }
  });

  it('every served item prints exactly the forms served for it through the real components; a null form draws nothing', async () => {
    const p = await load();
    const items = Object.entries(p.items as Record<string, any>).filter(([, v]) => v && typeof v === 'object');
    if (!ENV) {
      expect(items.filter(([, v]) => v.state === 'on').length).toBeGreaterThan(0);
      expect(items.filter(([, v]) => v.state === 'unknown').length).toBeGreaterThan(0);
    }
    for (const [key, it] of items) {
      _resetSsrCache();
      stub(p);
      const { unmount } = render(<>
        <span data-testid="anchor" />
        <GgSsrChip symbol={key} testid="c" />
        <GgSsrChip symbol={key} testid="s" form="short" />
        <GgSsrLabel symbol={key} testid="l" />
      </>);
      await screen.findByTestId('anchor');
      if (servedText(it.label)) await screen.findByTestId('l');
      else if (servedText(it.chip)) await screen.findByTestId('c');
      await tick();
      for (const [id, form] of [['c', 'chip'], ['s', 'short'], ['l', 'label']] as const) {
        const el = screen.queryByTestId(id);
        if (servedText(it[form])) {
          expect(el, `${key} ${form}`).not.toBeNull();
          expect(el!.textContent, `${key} ${form}`).toBe(it[form]);
          expect(el!.getAttribute('title'), `${key} ${form}`).toBe(it.title);
          expect(el!.getAttribute('data-ssr-state'), `${key} ${form}`).toBe(it.state);
        } else {
          expect(el, `${key} ${form} is served null → nothing`).toBeNull();
        }
      }
      if (it.state === 'unknown') {
        expect(screen.queryByTestId('c'), `${key} unknown → no chip`).toBeNull();
        expect(screen.queryByTestId('s'), `${key} unknown → no short`).toBeNull();
      }
      unmount();
      vi.unstubAllGlobals();
    }
  });

  it('NEGATIVE: every asked name with no item (off, a quiet unknown) renders nothing on any form', async () => {
    const p = await load();
    const states = (p.states && typeof p.states === 'object') ? p.states as Record<string, string> : {};
    const missing = Object.keys(states).filter((k) => !(k in (p.items || {})));
    if (!ENV) expect(missing.sort()).toEqual(expect.arrayContaining(['AAPL', 'ZZCO']));
    for (const key of [...missing, 'ZZZZZZZZZ']) {
      _resetSsrCache();
      stub(p);
      const { container, unmount } = render(<div className="row"><GgSsrChip symbol={key} testid="c" lead />
        <GgSsrChip symbol={key} testid="s" form="short" lead /><GgSsrLabel symbol={key} testid="l" /></div>);
      await new Promise((r) => setTimeout(r, 20));
      expect(container.innerHTML, key).toBe('<div class="row"></div>');
      unmount();
      vi.unstubAllGlobals();
    }
  });

  it('the fault line prints the served fault_text verbatim, or nothing when it is null', async () => {
    const p = await load();
    stub(p);
    const first = Object.keys(p.items || {})[0] || 'AKAN';
    const { container } = render(<><span data-testid="anchor" /><GgSsrChip symbol={first} testid="c" /><GgSsrFault testid="f" /></>);
    await screen.findByTestId('anchor');
    await new Promise((r) => setTimeout(r, 20));
    const el = screen.queryByTestId('f');
    if (servedText(p.fault_text)) expect(el?.textContent).toBe(p.fault_text);
    else {
      expect(el).toBeNull();
      expect(container.querySelector('.gg-ssr-fault')).toBeNull();
    }
  });
});
