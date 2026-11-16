/* ➕/➖ Watch on every card (2026-11-15). Ajay: "can you add an add to watch list button on all the stocks to move them
 * and also remove button from watch list too." NEGATIVES: owner_only / error / junk render nothing; the click never
 * bubbles into the card's link; ➕ is disabled at the cap while ➖ still works; ONE list GET for many cards; the list
 * moves only on the server's answer (never optimistic). */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgWatchButton } from './GgWatchButton';
import { GGW_LIST_PATH, ggwHas, ggwTitle, loadGgwList, parseGgwList, resetGgwList, toggleGgw } from '../lib/ggWatchList';

const LABELS = { add: '➕ Watch', remove: '➖ Watch', add_title: "Add {sym} to 👀 Gajjala's Watch",
  remove_title: "Remove {sym} from 👀 Gajjala's Watch" };
const list = (symbols: string[], full = false) => ({ state: 'ok', symbols, max: 12, full,
  full_text: 'Your watch holds 12 tickers — remove one to add another', labels: LABELS });

type Call = { url: string; method: string };
let calls: Call[];

function mockFetch(listBody: unknown, writes: Record<string, unknown> = {}) {
  calls = [];
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const c = { url: String(url), method: init?.method ?? 'GET' };
    calls.push(c);
    const body = c.method === 'GET' ? listBody : writes[c.method];
    return Promise.resolve({ ok: true, json: () => Promise.resolve(typeof body === 'function' ? (body as any)(c) : body) });
  }));
}

beforeEach(() => { resetGgwList(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('➕/➖ parse + helpers', () => {
  it('the served list parses; NEGATIVE: owner_only, error, junk and missing labels → null', () => {
    expect(parseGgwList(list(['OMH']))?.symbols).toEqual(['OMH']);
    for (const junk of [null, 3, 'x', [], {}, { state: 'owner_only', reason: 'r', title: 't' },
      { state: 'error', reason: 'x' }, { ...list([]), labels: null }, { ...list([]), symbols: 'OMH' }]) {
      expect(parseGgwList(junk)).toBeNull();
    }
  });
  it('membership folds case; the title fills {sym}', () => {
    expect(ggwHas(['OMH'], 'omh')).toBe(true);
    expect(ggwHas(['OMH'], 'AMD')).toBe(false);
    expect(ggwHas(['OMH'], '  ')).toBe(false);
    expect(ggwTitle(LABELS.add_title, 'RAIN')).toBe("Add RAIN to 👀 Gajjala's Watch");
    expect(GGW_LIST_PATH).toBe('/chart-maps/gajjala-watch/symbols');
  });
});

describe('➕/➖ button', () => {
  it('on the list → ➖, off → ➕; ONE list GET for many cards', async () => {
    mockFetch(list(['OMH']));
    render(<><GgWatchButton symbol="OMH" /><GgWatchButton symbol="AMD" /><GgWatchButton symbol="RAIN" /></>);
    expect(await screen.findByTestId('ggw-card-btn-OMH')).toHaveTextContent('➖ Watch');
    expect(screen.getByTestId('ggw-card-btn-AMD')).toHaveTextContent('➕ Watch');
    expect(screen.getByTestId('ggw-card-btn-AMD')).toHaveAttribute('title', "Add AMD to 👀 Gajjala's Watch");
    expect(calls.filter((c) => c.url.endsWith(GGW_LIST_PATH))).toHaveLength(1);
  });

  it('NEGATIVE: owner_only, error and a failed fetch render nothing', async () => {
    for (const body of [{ state: 'owner_only', reason: 'Shown to the account owner only.', title: 't' },
      { state: 'error', reason: 'x', title: 't' }]) {
      resetGgwList();
      mockFetch(body);
      const { container, unmount } = render(<GgWatchButton symbol="OMH" />);
      await waitFor(() => expect(calls.length).toBe(1));
      await act(async () => { await Promise.resolve(); });
      expect(container).toBeEmptyDOMElement();
      unmount();
    }
    resetGgwList();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('down'))));
    const { container } = render(<GgWatchButton symbol="OMH" />);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(container).toBeEmptyDOMElement();
  });

  it('➕ POSTs the symbol route and the click never reaches the card link; the list moves on the answer only', async () => {
    let listNow = ['OMH'];
    mockFetch(() => list(listNow), {
      POST: () => { listNow = ['OMH', 'AMD']; return { state: 'added', symbols: listNow, symbol: 'AMD', text: '👀 AMD added to your watch' }; },
    });
    const parent = vi.fn();
    render(<div onClick={parent}><GgWatchButton symbol="AMD" /></div>);
    const btn = await screen.findByTestId('ggw-card-btn-AMD');
    fireEvent.click(btn);
    expect(btn).toHaveTextContent('➕ Watch');                 // NEGATIVE: never optimistic
    expect(btn).toBeDisabled();
    await waitFor(() => expect(screen.getByTestId('ggw-card-btn-AMD')).toHaveTextContent('➖ Watch'));
    expect(parent).not.toHaveBeenCalled();
    const post = calls.find((c) => c.method === 'POST')!;
    expect(post.url).toContain('/chart-maps/gajjala-watch/symbols/AMD');
    expect(screen.getByTestId('ggw-card-btn-AMD')).toHaveAttribute('title', '👀 AMD added to your watch');
  });

  it('➖ DELETEs; NEGATIVE: a failed write leaves the list as it was', async () => {
    mockFetch(list(['OMH']), { DELETE: { state: 'error', symbols: [], symbol: 'OMH', text: 'The watch list could not be saved — try again' } });
    render(<GgWatchButton symbol="OMH" />);
    fireEvent.click(await screen.findByTestId('ggw-card-btn-OMH'));
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true));
    await waitFor(() => expect(screen.getByTestId('ggw-card-btn-OMH')).not.toBeDisabled());
    expect(screen.getByTestId('ggw-card-btn-OMH')).toHaveTextContent('➖ Watch');
  });

  it('NEGATIVE: at the cap ➕ is disabled with the served sentence, ➖ still works', async () => {
    mockFetch(list(['OMH'], true));
    render(<><GgWatchButton symbol="OMH" /><GgWatchButton symbol="AMD" /></>);
    const add = await screen.findByTestId('ggw-card-btn-AMD');
    expect(add).toBeDisabled();
    expect(add).toHaveAttribute('title', 'Your watch holds 12 tickers — remove one to add another');
    expect(screen.getByTestId('ggw-card-btn-OMH')).not.toBeDisabled();
  });

  it('review fix: BRK-B on a card matches BRK.B on the list → ➖ (the backend fold)', async () => {
    expect(ggwHas(['BRK.B'], 'brk-b')).toBe(true);
    expect(ggwHas(['BRK.B'], 'BRKB')).toBe(false);           // NEGATIVE: the fold joins separators, never drops them
    mockFetch(list(['BRK.B']));
    render(<GgWatchButton symbol="BRK-B" />);
    expect(await screen.findByTestId('ggw-card-btn-BRK-B')).toHaveTextContent('➖ Watch');
  });

  it('review fix: NEGATIVE — a failed refresh after a good write keeps every button', async () => {
    let n = 0;
    vi.stubGlobal('fetch', vi.fn((_url: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ state: 'added', symbols: ['OMH', 'AMD'], symbol: 'AMD', text: 'ok' }) });
      }
      n += 1;
      if (n === 1) return Promise.resolve({ ok: true, json: () => Promise.resolve(list(['OMH'])) });
      return Promise.resolve({ ok: false, json: () => Promise.resolve(null) });     // 502 on the refresh
    }));
    render(<><GgWatchButton symbol="OMH" /><GgWatchButton symbol="AMD" /></>);
    fireEvent.click(await screen.findByTestId('ggw-card-btn-AMD'));
    await waitFor(() => expect(n).toBe(2));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(screen.getByTestId('ggw-card-btn-AMD')).toHaveTextContent('➖ Watch');
    expect(screen.getByTestId('ggw-card-btn-OMH')).toBeInTheDocument();
  });

  it('review fix: NEGATIVE — a failed FIRST read retries at the next mount', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('down'))));
    const a = render(<GgWatchButton symbol="OMH" />);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(a.container).toBeEmptyDOMElement();
    a.unmount();
    mockFetch(list(['OMH']));
    render(<GgWatchButton symbol="OMH" />);
    expect(await screen.findByTestId('ggw-card-btn-OMH')).toHaveTextContent('➖ Watch');
  });

  it('review fix: NEGATIVE — a list read started before a write never overwrites the write', async () => {
    const pending: Array<(v: unknown) => void> = [];
    vi.stubGlobal('fetch', vi.fn((_url: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ state: 'added', symbols: ['OMH', 'AMD'], symbol: 'AMD', text: 'ok' }) });
      }
      return new Promise((res) => pending.push(res));
    }));
    render(<GgWatchButton symbol="AMD" />);
    await waitFor(() => expect(pending.length).toBe(1));
    pending.shift()!({ ok: true, json: () => Promise.resolve(list(['OMH'])) });
    await screen.findByTestId('ggw-card-btn-AMD');
    void loadGgwList(true);                                   // a stale read (sees no AMD) goes out…
    await act(async () => { await toggleGgw('AMD'); });       // …then the write lands and starts its own read
    await waitFor(() => expect(pending.length).toBe(2));
    await act(async () => { pending[1]({ ok: true, json: () => Promise.resolve(list(['OMH', 'AMD'])) }); });
    await act(async () => { pending[0]({ ok: true, json: () => Promise.resolve(list(['OMH'])) }); });   // stale lands last
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(screen.getByTestId('ggw-card-btn-AMD')).toHaveTextContent('➖ Watch');
  });

  it('review fix: NEGATIVE — the answer sentence leaves the title once a later read moves the name', async () => {
    let listNow = ['OMH'];
    mockFetch(() => list(listNow), { POST: () => { listNow = ['OMH', 'AMD']; return { state: 'added', symbols: listNow, symbol: 'AMD', text: '👀 AMD added to your watch' }; } });
    render(<GgWatchButton symbol="AMD" />);
    fireEvent.click(await screen.findByTestId('ggw-card-btn-AMD'));
    await waitFor(() => expect(screen.getByTestId('ggw-card-btn-AMD')).toHaveAttribute('title', '👀 AMD added to your watch'));
    listNow = ['OMH'];                                         // removed on the 👀 board
    await act(async () => { await loadGgwList(true); });
    const b = screen.getByTestId('ggw-card-btn-AMD');
    expect(b).toHaveTextContent('➕ Watch');
    expect(b).toHaveAttribute('title', "Add AMD to 👀 Gajjala's Watch");
  });
});
