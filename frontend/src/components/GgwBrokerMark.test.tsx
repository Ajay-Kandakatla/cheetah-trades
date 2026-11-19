/* 🚫 GgwBrokerMark — the 👀 Watch's one-way broker mark (2026-11-19, spec watchfid §3.3 / §4 WP-C tests 3–4).
 * ggwMarkNotEligible over a recorded fetch; the button over the REAL hook with a routed global fetch. Every word is a
 * stand-in for a served one. NEGATIVES: a failed POST never DELETEs (served detail / 404 → nothing); a failed or thrown
 * DELETE → GGW_FETCH_FAILED; NEVER a DELETE on the broker route; no block / a fault block → no button; a double click →
 * ONE POST. */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { API } from '../lib/apiBase';
import { GG_BROKER_PATH } from '../lib/gajjala';
import { GGW_FETCH_FAILED, ggwSymbolPath, type GgwRow } from '../lib/gajjalaWatch';
import { GGW_LIST_PATH } from '../lib/ggWatchList';
import type { GgwBroker } from '../lib/ggwBroker';
import { GgwBrokerButton, GgwBrokerHead, ggwMarkNotEligible, useGgwBrokerMark } from './GgwBrokerMark';

type Call = { url: string; method: string; body?: string; headers?: unknown };
const res = (status: number, body?: unknown, opts: { badJson?: boolean } = {}) => ({
  ok: status >= 200 && status < 300, status,
  json: async () => { if (opts.badJson || body === undefined) throw new Error('no body'); return body; },
} as unknown as Response);
function recorder(post: () => Response | Promise<Response>, del: () => Response | Promise<Response>) {
  const calls: Call[] = [];
  const fn = vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method ?? 'GET').toUpperCase();
    calls.push({ url, method, body: typeof init?.body === 'string' ? init.body : undefined, headers: init?.headers });
    if (method === 'POST') return post();
    if (method === 'DELETE') return del();
    return res(200, { state: 'ok', symbols: [] });
  });
  return { calls, fn: fn as unknown as typeof fetch };
}
const POST_URL = `${API}${GG_BROKER_PATH}`;
const DEL_URL = (s: string) => `${API}${ggwSymbolPath(s)}`;
const neverBrokerDelete = (calls: Call[]) =>
  expect(calls.filter((c) => c.method === 'DELETE' && c.url.includes(GG_BROKER_PATH))).toHaveLength(0);

describe('🚫 ggwMarkNotEligible', () => {
  it('POST his 🚫 list {symbol}, THEN DELETE the Watch name — exact URLs, order and body; the served answer text', async () => {
    const r = recorder(() => res(200, { state: 'ok' }), () => res(200, { state: 'removed', text: 'served removed words' }));
    const out = await ggwMarkNotEligible(' AZI ', r.fn);
    expect(out).toEqual({ ok: true, text: 'served removed words', err: null });
    expect(r.calls.map((c) => [c.method, c.url])).toEqual([['POST', POST_URL], ['DELETE', DEL_URL('AZI')]]);
    expect(JSON.parse(r.calls[0].body!)).toEqual({ symbol: 'AZI' });
    expect(r.calls[1].body).toBeUndefined();
    neverBrokerDelete(r.calls);
  });
  it('NEGATIVE: POST 503 with a served detail → NO DELETE, err = the served detail', async () => {
    const r = recorder(() => res(503, { detail: 'served write fault' }), () => res(200, {}));
    expect(await ggwMarkNotEligible('AZI', r.fn)).toEqual({ ok: false, text: null, err: 'served write fault' });
    expect(r.calls.map((c) => c.method)).toEqual(['POST']);
  });
  it('NEGATIVE: POST 503 without a served detail → NO DELETE, err null (the FE types no word)', async () => {
    for (const body of [{}, { detail: 3 }, { detail: ' ' }, undefined]) {
      const r = recorder(() => res(503, body), () => res(200, {}));
      expect(await ggwMarkNotEligible('AZI', r.fn)).toEqual({ ok: false, text: null, err: null });
      expect(r.calls.map((c) => c.method)).toEqual(['POST']);
    }
  });
  it('NEGATIVE: POST 404 (not the owner — stealth) → NO DELETE, err null', async () => {
    const r = recorder(() => res(404, { detail: 'Not Found' }), () => res(200, {}));
    expect(await ggwMarkNotEligible('AZI', r.fn)).toEqual({ ok: false, text: null, err: null });
    expect(r.calls.map((c) => c.method)).toEqual(['POST']);
  });
  it('NEGATIVE [C6]: DELETE 500 → {ok:true, text:null, err:GGW_FETCH_FAILED}; a thrown DELETE → the same', async () => {
    const a = recorder(() => res(200, {}), () => res(500, { text: 'never printed' }));
    expect(await ggwMarkNotEligible('AZI', a.fn)).toEqual({ ok: true, text: null, err: GGW_FETCH_FAILED });
    const b = recorder(() => res(200, {}), () => { throw new Error('net'); });
    expect(await ggwMarkNotEligible('AZI', b.fn)).toEqual({ ok: true, text: null, err: GGW_FETCH_FAILED });
    neverBrokerDelete(a.calls);
    neverBrokerDelete(b.calls);
  });
  it('a 204 empty DELETE body → text null, err null, no throw', async () => {
    const r = recorder(() => res(200, {}), () => res(204, undefined, { badJson: true }));
    await expect(ggwMarkNotEligible('AZI', r.fn)).resolves.toEqual({ ok: true, text: null, err: null });
  });
  it('NEGATIVE: a blank symbol → no request at all', async () => {
    const r = recorder(() => res(200, {}), () => res(200, {}));
    expect(await ggwMarkNotEligible('  ', r.fn)).toEqual({ ok: false, text: null, err: null });
    expect(r.calls).toHaveLength(0);
  });
});

const BLOCK: GgwBroker = {
  toggle: '🚫', text: '🚫 served broker word', title: 'served mark title', editable: true,
  fault_text: null, auto_text: null, auto_fault_text: null,
};
const row = (sym: string, broker_text: string | null = null, tags: GgwRow['tags'] = null): GgwRow => ({
  symbol: sym, state: 'ok', text: null, from_session: null, as_of_et: null, stale: false, frames: [], rang: [],
  auto: null, aplus: null, tags, broker_text,
});

function Harness({ r, block, onDone = () => {} }: { r: GgwRow; block: GgwBroker | null; onDone?: (t: string | null) => void }) {
  const m = useGgwBrokerMark(onDone);
  return (
    <div>
      <GgwBrokerHead block={block} err={m.err} />
      <GgwBrokerButton row={r} block={block} busy={m.busy} onMark={m.mark} />
    </div>
  );
}

describe('🚫 GgwBrokerButton', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('renders only with the SERVED block editable: served toggle, title and aria-label', () => {
    const { container } = render(<GgwBrokerButton row={row('AZI')} block={BLOCK} busy={false} onMark={() => {}} />);
    const b = screen.getByTestId('ggw-broker-mark-AZI');
    expect(b.tagName).toBe('BUTTON');
    expect(b.getAttribute('type')).toBe('button');
    expect(b.className).toBe('ggw-btn ggw-broker-mark');
    expect(b.textContent).toBe(BLOCK.toggle);
    expect(b.getAttribute('title')).toBe(BLOCK.title);
    expect(b.getAttribute('aria-label')).toBe(BLOCK.title);
    expect(container.childElementCount).toBe(1);
  });
  it('no served title → the served word is the hover', () => {
    render(<GgwBrokerButton row={row('AZI')} block={{ ...BLOCK, title: null }} busy={false} onMark={() => {}} />);
    expect(screen.getByTestId('ggw-broker-mark-AZI').getAttribute('title')).toBe(BLOCK.text);
  });
  it('NEGATIVE: block null (non-owner / older server) → nothing; a fault block (editable false) → nothing', () => {
    const a = render(<GgwBrokerButton row={row('AZI')} block={null} busy={false} onMark={() => {}} />);
    expect(a.container.innerHTML).toBe('');
    cleanup();
    const b = render(<GgwBrokerButton row={row('AZI')} block={{ ...BLOCK, editable: false, fault_text: 'served fault' }}
                                      busy={false} onMark={() => {}} />);
    expect(b.container.innerHTML).toBe('');
  });
  it('aria-pressed true on a row with a served word (row or card tags); false otherwise', () => {
    render(<>
      <GgwBrokerButton row={row('AZI', '🚫 served broker word')} block={BLOCK} busy={false} onMark={() => {}} />
      <GgwBrokerButton row={row('OMH', null, { on_board: true, setups: [], stages: null, float: null, broker_text: '🚫 tags word',
        trader_text: null, promo_text: null })} block={BLOCK} busy={false} onMark={() => {}} />
      <GgwBrokerButton row={row('AMD')} block={BLOCK} busy={false} onMark={() => {}} />
      <GgwBrokerButton row={row('NVDA', ' ')} block={BLOCK} busy={false} onMark={() => {}} />
    </>);
    expect(screen.getByTestId('ggw-broker-mark-AZI').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('ggw-broker-mark-OMH').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('ggw-broker-mark-AMD').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByTestId('ggw-broker-mark-NVDA').getAttribute('aria-pressed')).toBe('false');
  });
  it('disabled while busy; a click hands the row symbol to onMark', () => {
    const onMark = vi.fn();
    const a = render(<GgwBrokerButton row={row('AZI')} block={BLOCK} busy onMark={onMark} />);
    expect((screen.getByTestId('ggw-broker-mark-AZI') as HTMLButtonElement).disabled).toBe(true);
    a.unmount();
    render(<GgwBrokerButton row={row('AZI')} block={BLOCK} busy={false} onMark={onMark} />);
    fireEvent.click(screen.getByTestId('ggw-broker-mark-AZI'));
    expect(onMark).toHaveBeenCalledWith('AZI');
  });
  it('a double click → ONE POST, one DELETE; the served answer reaches onDone; the shared list is re-read', async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((r) => { release = r; });
    const calls: Call[] = [];
    vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
      const method = (init?.method ?? 'GET').toUpperCase();
      calls.push({ url: String(u), method });
      if (method === 'POST') { await gate; return res(200, {}); }
      if (method === 'DELETE') return res(200, { state: 'removed', text: 'served removed words' });
      return res(200, { state: 'ok', symbols: [] });
    }));
    const onDone = vi.fn();
    render(<Harness r={row('AZI')} block={BLOCK} onDone={onDone} />);
    const b = screen.getByTestId('ggw-broker-mark-AZI');
    fireEvent.click(b);
    fireEvent.click(b);
    await waitFor(() => expect((b as HTMLButtonElement).disabled).toBe(true));
    fireEvent.click(b);
    await act(async () => { release(); });
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
    expect(onDone).toHaveBeenCalledWith('served removed words');
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1);
    expect(calls.filter((c) => c.method === 'DELETE').map((c) => c.url)).toEqual([DEL_URL('AZI')]);
    await waitFor(() => expect(calls.some((c) => c.method === 'GET' && c.url === `${API}${GGW_LIST_PATH}`)).toBe(true));
    expect((b as HTMLButtonElement).disabled).toBe(false);
    neverBrokerDelete(calls);
  });
  it('NEGATIVE: two marks in the SAME tick (before the disabled state renders) → ONE POST (the ref guard)', async () => {
    const calls: Call[] = [];
    vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
      const method = (init?.method ?? 'GET').toUpperCase();
      calls.push({ url: String(u), method });
      if (method === 'DELETE') return res(200, { text: 'served' });
      return res(200, { state: 'ok', symbols: [] });
    }));
    const onDone = vi.fn();
    function Twice() {
      const m = useGgwBrokerMark(onDone);
      return <button type="button" data-testid="twice" onClick={() => { m.mark('AZI'); m.mark('AZI'); }} />;
    }
    render(<Twice />);
    fireEvent.click(screen.getByTestId('twice'));
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1);
    expect(calls.filter((c) => c.method === 'DELETE')).toHaveLength(1);
  });
  it('NEGATIVE [C6]: a failed DELETE prints GGW_FETCH_FAILED in ggw-broker-err; onDone still fires (null)', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_u: RequestInfo | URL, init?: RequestInit) => {
      const method = (init?.method ?? 'GET').toUpperCase();
      if (method === 'POST') return res(200, {});
      if (method === 'DELETE') return res(500, {});
      return res(200, { state: 'ok', symbols: [] });
    }));
    const onDone = vi.fn();
    render(<Harness r={row('AZI')} block={BLOCK} onDone={onDone} />);
    fireEvent.click(screen.getByTestId('ggw-broker-mark-AZI'));
    await waitFor(() => expect(screen.getByTestId('ggw-broker-err').textContent).toBe(GGW_FETCH_FAILED));
    expect(onDone).toHaveBeenCalledWith(null);
  });
});

describe('🚫 GgwBrokerHead', () => {
  afterEach(() => cleanup());
  it('prints the served lines verbatim, in order', () => {
    const { container } = render(<GgwBrokerHead block={{ ...BLOCK, fault_text: 'served fault', auto_text: 'served kept off',
      auto_fault_text: 'served auto fault' }} err="served err" />);
    expect(Array.from(container.children).map((e) => [e.getAttribute('data-testid'), e.textContent])).toEqual([
      ['ggw-broker-fault', 'served fault'], ['ggw-broker-auto', 'served kept off'],
      ['ggw-broker-auto-fault', 'served auto fault'], ['ggw-broker-err', 'served err'],
    ]);
  });
  it('NEGATIVE: nothing served (or no block) → nothing', () => {
    expect(render(<GgwBrokerHead block={BLOCK} err={null} />).container.innerHTML).toBe('');
    cleanup();
    expect(render(<GgwBrokerHead block={null} err={null} />).container.innerHTML).toBe('');
  });
});
