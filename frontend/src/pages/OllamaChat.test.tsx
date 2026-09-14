/**
 * /ollama — private local-model chat.
 *
 * The contracts that matter: the stealth 404 (a stranger sees nothing, not
 * even a composer), the image path (bare base64 leaves the browser, never a
 * data: URL — Ollama would silently fail to decode it), the stream relay
 * (thinking / delta / done / error land in the right places), and that the
 * admin address is nowhere in this page's source.
 */
import { fireEvent, render, screen, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import OllamaChat, {
  STORAGE_KEY, MAX_IMAGES, stripDataUrl, parseSse, fmtDuration, tokPerSec,
} from './OllamaChat';

const ME_OK = {
  ok: true, model: 'huihui_ai/test:27b', reachable: true, resident: true,
  version: '0.33.3', capabilities: ['completion', 'vision', 'thinking'], context_length: 262144,
};

function sse(events: object[]): string {
  return events.map(e => `data: ${JSON.stringify(e)}\n\n`).join('');
}

function streamResponse(chunks: string[], opts: { hang?: boolean } = {}) {
  const enc = new TextEncoder();
  let ctrl: ReadableStreamDefaultController<Uint8Array> | null = null;
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      ctrl = c;
      for (const ch of chunks) c.enqueue(enc.encode(ch));
      if (!opts.hang) c.close();
    },
  });
  return { res: new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }), close: () => ctrl?.close() };
}

type Call = { url: string; init?: RequestInit };
let calls: Call[] = [];

function mockFetch(handlers: Record<string, (init?: RequestInit) => Response | Promise<Response>>) {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const key = Object.keys(handlers).find(k => url.endsWith(k));
    if (!key) return new Response('{}', { status: 500 });
    return handlers[key](init);
  }));
}

function lastBody(suffix: string): any {
  const c = [...calls].reverse().find(x => x.url.endsWith(suffix));
  return c?.init?.body ? JSON.parse(String(c.init.body)) : null;
}

/* The shared test setup leaves localStorage as a partial stub — give this
 * file a real in-memory one so persistence assertions mean something. */
function mem(): Storage {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(),
    key: (i: number) => Array.from(m.keys())[i] ?? null,
    get length() { return m.size; },
  } as Storage;
}

beforeEach(() => {
  vi.stubGlobal('localStorage', mem());
  // jsdom's Image never loads; make it fail fast so fileToBase64 takes the
  // no-downscale path and we can assert on the exact bytes.
  vi.stubGlobal('Image', class {
    onload: null | (() => void) = null;
    onerror: null | (() => void) = null;
    width = 0; height = 0;
    set src(_: string) { setTimeout(() => this.onerror?.(), 0); }
  });
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('pure helpers', () => {
  it('stripDataUrl removes only the data: prefix', () => {
    expect(stripDataUrl('data:image/png;base64,AAAA')).toBe('AAAA');
    expect(stripDataUrl('data:image/jpeg;base64,/9j/4AAQ')).toBe('/9j/4AAQ');
    expect(stripDataUrl('AAAA')).toBe('AAAA');
    expect(stripDataUrl('')).toBe('');
  });

  it('parseSse returns complete events and keeps the partial tail', () => {
    const { events, rest } = parseSse('data: {"delta":"a"}\n\ndata: {"del');
    expect(events).toEqual([{ delta: 'a' }]);
    expect(rest).toBe('data: {"del');
    const again = parseSse(rest + 'ta":"b"}\n\n');
    expect(again.events).toEqual([{ delta: 'b' }]);
    expect(again.rest).toBe('');
  });

  it('parseSse ignores non-data lines and broken json', () => {
    const { events } = parseSse(': comment\n\ndata: {oops}\n\ndata: {"done":true}\n\n');
    expect(events).toEqual([{ done: true }]);
  });

  it('formats duration and throughput', () => {
    expect(fmtDuration(2_000_000_000)).toBe('2.0s');
    expect(fmtDuration(14_400_000_000)).toBe('14s');
    expect(fmtDuration(null)).toBe('');
    expect(tokPerSec(100, 2_000_000_000)).toBe('50 tok/s');
    expect(tokPerSec(null, 1)).toBe('');
  });
});

describe('gate', () => {
  it('renders the stealth 404 and no composer when /ollama/me is 404', async () => {
    mockFetch({ '/ollama/me': () => new Response('{"detail":"Not Found"}', { status: 404 }) });
    render(<OllamaChat />);
    expect(await screen.findByText('404')).toBeTruthy();
    expect(screen.queryByPlaceholderText(/Message/)).toBeNull();
    expect(calls.some(c => c.url.endsWith('/ollama/warm'))).toBe(false);
  });

  it('shows the model + resident status for the admin', async () => {
    mockFetch({ '/ollama/me': () => new Response(JSON.stringify(ME_OK), { status: 200 }) });
    render(<OllamaChat />);
    expect(await screen.findByText('huihui_ai/test:27b')).toBeTruthy();
    expect(screen.getByText('resident · pinned')).toBeTruthy();
    expect(screen.getByText('vision')).toBeTruthy();
    expect(calls.some(c => c.url.endsWith('/ollama/warm'))).toBe(false);
  });

  it('warms the model when reachable but not resident', async () => {
    mockFetch({
      '/ollama/me': () => new Response(JSON.stringify({ ...ME_OK, resident: false }), { status: 200 }),
      '/ollama/warm': () => new Response('{"ok":true}', { status: 200 }),
    });
    render(<OllamaChat />);
    await waitFor(() => expect(calls.some(c => c.url.endsWith('/ollama/warm'))).toBe(true));
    expect(await screen.findByText('resident · pinned')).toBeTruthy();
  });

  it('says so when Ollama is down', async () => {
    mockFetch({ '/ollama/me': () => new Response(JSON.stringify({ ...ME_OK, reachable: false, resident: false }), { status: 200 }) });
    render(<OllamaChat />);
    expect(await screen.findByText(/not reachable/)).toBeTruthy();
  });
});

describe('chat', () => {
  it('streams thinking, deltas and the done stats into the assistant turn', async () => {
    const { res } = streamResponse([
      sse([{ thinking: 'let me ' }, { thinking: 'see' }]),
      'data: {"delta":"Hel',           // split mid-event on purpose
      'lo"}\n\n',
      sse([{ delta: ' there' }, { done: true, eval_count: 20, total_duration: 4_000_000_000 }]),
    ]);
    mockFetch({
      '/ollama/me': () => new Response(JSON.stringify(ME_OK), { status: 200 }),
      '/ollama/chat': () => res,
    });
    render(<OllamaChat />);
    const ta = await screen.findByPlaceholderText(/Message/);
    fireEvent.change(ta, { target: { value: 'hi' } });
    fireEvent.keyDown(ta, { key: 'Enter' });

    expect(await screen.findByText('Hello there')).toBeTruthy();
    expect(screen.getByText('let me see')).toBeTruthy();
    expect(screen.getByText(/4\.0s\s+5 tok\/s/)).toBeTruthy();

    const body = lastBody('/ollama/chat');
    expect(body.messages).toEqual([{ role: 'user', content: 'hi' }]);
    expect(body.think).toBe(true);
    // Persisted, text only.
    const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY)!);
    expect(saved.length).toBe(2);
    expect(saved[1].content).toBe('Hello there');
  });

  it('Shift+Enter does not send', async () => {
    mockFetch({ '/ollama/me': () => new Response(JSON.stringify(ME_OK), { status: 200 }) });
    render(<OllamaChat />);
    const ta = await screen.findByPlaceholderText(/Message/);
    fireEvent.change(ta, { target: { value: 'hi' } });
    fireEvent.keyDown(ta, { key: 'Enter', shiftKey: true });
    expect(calls.some(c => c.url.endsWith('/ollama/chat'))).toBe(false);
  });

  it('renders an error event inline and keeps the composer usable', async () => {
    const { res } = streamResponse([sse([{ error: 'cannot reach Ollama at x' }])]);
    mockFetch({
      '/ollama/me': () => new Response(JSON.stringify(ME_OK), { status: 200 }),
      '/ollama/chat': () => res,
    });
    render(<OllamaChat />);
    const ta = await screen.findByPlaceholderText(/Message/);
    fireEvent.change(ta, { target: { value: 'hi' } });
    fireEvent.keyDown(ta, { key: 'Enter' });
    expect(await screen.findByText('cannot reach Ollama at x')).toBeTruthy();
    await waitFor(() => expect((screen.getByPlaceholderText(/Message/) as HTMLTextAreaElement).disabled).toBe(false));
  });

  it('a 404 mid-session flips to the stealth page', async () => {
    mockFetch({
      '/ollama/me': () => new Response(JSON.stringify(ME_OK), { status: 200 }),
      '/ollama/chat': () => new Response('{"detail":"Not Found"}', { status: 404 }),
    });
    render(<OllamaChat />);
    const ta = await screen.findByPlaceholderText(/Message/);
    fireEvent.change(ta, { target: { value: 'hi' } });
    fireEvent.keyDown(ta, { key: 'Enter' });
    expect(await screen.findByText('404')).toBeTruthy();
  });

  it('Stop aborts the stream and returns the Send button', async () => {
    const { res } = streamResponse([sse([{ delta: 'partial' }])], { hang: true });
    mockFetch({
      '/ollama/me': () => new Response(JSON.stringify(ME_OK), { status: 200 }),
      '/ollama/chat': () => res,
    });
    render(<OllamaChat />);
    const ta = await screen.findByPlaceholderText(/Message/);
    fireEvent.change(ta, { target: { value: 'hi' } });
    fireEvent.keyDown(ta, { key: 'Enter' });
    expect(await screen.findByText('partial')).toBeTruthy();
    const stop = await screen.findByRole('button', { name: 'Stop' });
    fireEvent.click(stop);
    expect(await screen.findByRole('button', { name: 'Send' })).toBeTruthy();
    const init = [...calls].reverse().find(c => c.url.endsWith('/ollama/chat'))!.init!;
    expect((init.signal as AbortSignal).aborted).toBe(true);
    expect(screen.getByText('partial')).toBeTruthy();       // what arrived stays
  });

  it('Clear wipes the thread and storage', async () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([{ role: 'user', content: 'old' }, { role: 'assistant', content: 'reply' }]));
    mockFetch({ '/ollama/me': () => new Response(JSON.stringify(ME_OK), { status: 200 }) });
    render(<OllamaChat />);
    expect(await screen.findByText('old')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(screen.queryByText('old')).toBeNull();
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('think toggle is sent through and remembered', async () => {
    const { res } = streamResponse([sse([{ delta: 'x', }, { done: true }])]);
    mockFetch({
      '/ollama/me': () => new Response(JSON.stringify(ME_OK), { status: 200 }),
      '/ollama/chat': () => res,
    });
    render(<OllamaChat />);
    const ta = await screen.findByPlaceholderText(/Message/);
    fireEvent.click(screen.getByLabelText('think'));
    fireEvent.change(ta, { target: { value: 'hi' } });
    fireEvent.keyDown(ta, { key: 'Enter' });
    await screen.findByText('x');
    expect(lastBody('/ollama/chat').think).toBe(false);
    expect(window.localStorage.getItem(`${STORAGE_KEY}.think`)).toBe('0');
  });
});

describe('images', () => {
  const PNG_B64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
  function pngFile(name = 'a.png') {
    const bytes = Uint8Array.from(atob(PNG_B64), c => c.charCodeAt(0));
    return new File([bytes], name, { type: 'image/png' });
  }

  it('attaches a file as BARE base64 — no data: prefix leaves the browser', async () => {
    const { res } = streamResponse([sse([{ delta: 'Red' }, { done: true }])]);
    mockFetch({
      '/ollama/me': () => new Response(JSON.stringify(ME_OK), { status: 200 }),
      '/ollama/chat': () => res,
    });
    render(<OllamaChat />);
    await screen.findByPlaceholderText(/Message/);
    const input = screen.getByTestId('ol-file') as HTMLInputElement;
    await act(async () => { fireEvent.change(input, { target: { files: [pngFile()] } }); });
    expect(await screen.findByAltText('pending 1')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Send' }));   // image only, no text
    expect(await screen.findByText('Red')).toBeTruthy();
    const body = lastBody('/ollama/chat');
    expect(body.messages[0].images).toEqual([PNG_B64]);
    expect(String(body.messages[0].images[0]).startsWith('data:')).toBe(false);
    expect(screen.getByAltText('attached 1')).toBeTruthy();

    // Storage keeps the count, never the bytes.
    const saved = window.localStorage.getItem(STORAGE_KEY)!;
    expect(saved).not.toContain(PNG_B64);
    expect(JSON.parse(saved)[0].imageCount).toBe(1);
  });

  it('caps attachments at MAX_IMAGES and ignores non-images', async () => {
    mockFetch({ '/ollama/me': () => new Response(JSON.stringify(ME_OK), { status: 200 }) });
    render(<OllamaChat />);
    await screen.findByPlaceholderText(/Message/);
    const input = screen.getByTestId('ol-file') as HTMLInputElement;
    const files = Array.from({ length: MAX_IMAGES + 3 }, (_, i) => pngFile(`${i}.png`));
    files.push(new File(['x'], 'notes.txt', { type: 'text/plain' }));
    await act(async () => { fireEvent.change(input, { target: { files } }); });
    await waitFor(() => expect(screen.getAllByAltText(/pending/).length).toBe(MAX_IMAGES));
    expect((screen.getByTitle('Attach images') as HTMLButtonElement).disabled).toBe(true);
  });

  it('the × removes one pending image', async () => {
    mockFetch({ '/ollama/me': () => new Response(JSON.stringify(ME_OK), { status: 200 }) });
    render(<OllamaChat />);
    await screen.findByPlaceholderText(/Message/);
    const input = screen.getByTestId('ol-file') as HTMLInputElement;
    await act(async () => { fireEvent.change(input, { target: { files: [pngFile('1.png'), pngFile('2.png')] } }); });
    await waitFor(() => expect(screen.getAllByAltText(/pending/).length).toBe(2));
    fireEvent.click(screen.getAllByLabelText('remove image')[0]);
    expect(screen.getAllByAltText(/pending/).length).toBe(1);
  });

  it('shows the 📷 count for restored messages whose bytes are gone', async () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([{ role: 'user', content: 'look', imageCount: 2 }]));
    mockFetch({ '/ollama/me': () => new Response(JSON.stringify(ME_OK), { status: 200 }) });
    render(<OllamaChat />);
    expect(await screen.findByText('📷 2')).toBeTruthy();
  });
});
