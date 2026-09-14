/* OllamaChat — private chat with the local Ollama model, Ajay only.
 *
 *  Ajay 2026-09-14: "Can you build me a chat interface to talk to my Ollamma
 *  LLM the abliterated model. I wanna chat with it from this app but only
 *  available for me. ... I can upload images and talk to it."
 *
 *  WHO CAN SEE IT
 *   The route is behind PrimaryAdminRoute (App.tsx) which reads the
 *   `is_primary_admin` boolean from /auth/me. That flag is TRUE FOR ONE
 *   ADDRESS — not the house-owner `is_admin` flag, which Vineetha also
 *   carries. The page then double-checks with GET /ollama/me and renders
 *   the stealth 404 on anything but 200, so even a bookmarked URL says
 *   nothing to anyone else. The email itself never appears here.
 *
 *  HOW A MESSAGE FLOWS
 *   POST /ollama/chat with the whole visible history → server-sent events
 *   {"delta"} / {"thinking"} / {"done"} / {"error"}. Read with fetch +
 *   getReader so the Stop button can abort mid-answer (the backend then
 *   cancels the upstream generation and frees the GPU).
 *
 *  IMAGES
 *   Attach (button, paste, or drop). Each is downscaled client-side to
 *   MAX_EDGE px JPEG before it leaves the browser — a 12 MB phone photo
 *   becomes ~300 KB, and the model's vision projector resizes to its own
 *   grid anyway so nothing is lost that it could have read. The data-URL
 *   prefix is stripped here because Ollama wants bare base64.
 *
 *  HISTORY
 *   localStorage, text only. Images live in memory for the session; after
 *   a reload the message shows "📷 n" instead of re-sending a photo the
 *   model has already answered. Clear wipes both.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { MarkdownLite } from '../lib/markdownLite';

export type OllamaMsg = {
  role: 'user' | 'assistant';
  content: string;
  /** Bare base64 (no data: prefix) — exactly what the API wants. */
  images?: string[];
  /** Survives a reload when the bytes do not. */
  imageCount?: number;
  thinking?: string;
  /** Set on the assistant turn once the stream ends. */
  stats?: { eval_count?: number | null; total_duration?: number | null };
  error?: string;
};

export type OllamaStatus = {
  ok: boolean;
  model: string;
  reachable: boolean;
  resident: boolean;
  version: string | null;
  capabilities: string[];
  context_length: number | null;
};

export const STORAGE_KEY = 'pounce_ollama_v1';
export const MAX_HISTORY = 200;
/** Messages actually sent back to the model each turn. */
export const CONTEXT_TURNS = 40;
export const MAX_IMAGES = 6;
export const MAX_EDGE = 1600;
export const JPEG_QUALITY = 0.88;

const DATA_URL_PREFIX = /^data:[^;]+;base64,/i;

/** Ollama takes raw base64. The browser hands us data URLs. */
export function stripDataUrl(s: string): string {
  return s.replace(DATA_URL_PREFIX, '');
}

/** Parse one SSE chunk buffer into events + the unconsumed remainder. */
export function parseSse(buffer: string): { events: Record<string, unknown>[]; rest: string } {
  const events: Record<string, unknown>[] = [];
  const parts = buffer.split('\n\n');
  const rest = parts.pop() ?? '';
  for (const block of parts) {
    for (const line of block.split('\n')) {
      if (!line.startsWith('data:')) continue;
      try { events.push(JSON.parse(line.slice(5).trim())); } catch { /* partial */ }
    }
  }
  return { events, rest };
}

export function fmtDuration(ns?: number | null): string {
  if (!ns || ns <= 0) return '';
  const s = ns / 1e9;
  return s < 10 ? `${s.toFixed(1)}s` : `${Math.round(s)}s`;
}

export function tokPerSec(evalCount?: number | null, totalNs?: number | null): string {
  if (!evalCount || !totalNs) return '';
  return `${(evalCount / (totalNs / 1e9)).toFixed(0)} tok/s`;
}

function loadHistory(): OllamaMsg[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(-MAX_HISTORY) : [];
  } catch { return []; }
}

function saveHistory(msgs: OllamaMsg[]): void {
  try {
    const slim = msgs.slice(-MAX_HISTORY).map(m => {
      if (!m.images?.length) return m;
      const { images, ...rest } = m;
      return { ...rest, imageCount: images.length };
    });
    if (!slim.length) window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, JSON.stringify(slim));
  } catch { /* quota — ignore */ }
}

/** Downscale to MAX_EDGE and re-encode as JPEG; returns bare base64. */
export async function fileToBase64(file: File): Promise<string> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
  if (typeof document === 'undefined' || typeof Image === 'undefined') return stripDataUrl(dataUrl);
  const img = new Image();
  const loaded = await new Promise<boolean>((resolve) => {
    const t = setTimeout(() => resolve(false), 4000);   // never hang the composer
    img.onload = () => { clearTimeout(t); resolve(true); };
    img.onerror = () => { clearTimeout(t); resolve(false); };
    img.src = dataUrl;
  });
  if (!loaded) return stripDataUrl(dataUrl);
  const scale = Math.min(1, MAX_EDGE / Math.max(img.width, img.height));
  if (scale === 1 && file.size < 1_500_000) return stripDataUrl(dataUrl);
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(img.width * scale);
  canvas.height = Math.round(img.height * scale);
  const ctx = canvas.getContext('2d');
  if (!ctx) return stripDataUrl(dataUrl);
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return stripDataUrl(canvas.toDataURL('image/jpeg', JPEG_QUALITY));
}

function NotFound() {
  return (
    <div style={{ padding: '4rem 1.5rem', textAlign: 'center', color: '#888' }}>
      <h1 style={{ fontSize: '1.4rem', fontFamily: 'serif', fontStyle: 'italic' }}>404</h1>
      <p>Not found.</p>
    </div>
  );
}

export default function OllamaChat() {
  const [gate, setGate] = useState<'checking' | 'ok' | 'denied'>('checking');
  const [status, setStatus] = useState<OllamaStatus | null>(null);
  const [history, setHistory] = useState<OllamaMsg[]>(() => loadHistory());
  const [input, setInput] = useState('');
  const [pending, setPending] = useState<string[]>([]);   // bare base64 attachments
  const [streaming, setStreaming] = useState(false);
  const [think, setThink] = useState<boolean>(() => {
    try { return window.localStorage.getItem(`${STORAGE_KEY}.think`) !== '0'; } catch { return true; }
  });
  const abortRef = useRef<AbortController | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  // Gate + status probe. 404 → stealth page. Then warm the model so the
  // first real message never pays the 20 GB load.
  useEffect(() => {
    let alive = true;
    fetch(`${API}/ollama/me`, { cache: 'no-store' })
      .then(async r => {
        if (!alive) return;
        if (r.status === 404) { setGate('denied'); return; }
        if (!r.ok) { setGate('ok'); return; }
        const j = await r.json() as OllamaStatus;
        setStatus(j); setGate('ok');
        if (j.reachable && !j.resident) {
          fetch(`${API}/ollama/warm`, { method: 'POST' })
            .then(r2 => r2.ok ? r2.json() : null)
            .then(() => { if (alive) setStatus(s => s ? { ...s, resident: true } : s); })
            .catch(() => { /* status line stays honest */ });
        }
      })
      .catch(() => { if (alive) setGate('ok'); });
    return () => { alive = false; };
  }, []);

  useEffect(() => { saveHistory(history); }, [history]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ block: 'end' }); }, [history, streaming]);
  useEffect(() => {
    try { window.localStorage.setItem(`${STORAGE_KEY}.think`, think ? '1' : '0'); } catch { /* ignore */ }
  }, [think]);

  const addFiles = useCallback(async (files: FileList | File[] | null) => {
    if (!files) return;
    const list = Array.from(files).filter(f => f.type.startsWith('image/'));
    if (!list.length) return;
    const room = MAX_IMAGES - pending.length;
    const encoded = await Promise.all(list.slice(0, Math.max(0, room)).map(fileToBase64));
    setPending(p => [...p, ...encoded].slice(0, MAX_IMAGES));
  }, [pending.length]);

  const onPaste = useCallback((e: React.ClipboardEvent) => {
    const files = Array.from(e.clipboardData?.files ?? []).filter(f => f.type.startsWith('image/'));
    if (files.length) { e.preventDefault(); void addFiles(files); }
  }, [addFiles]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    void addFiles(e.dataTransfer?.files ?? null);
  }, [addFiles]);

  const stop = useCallback(() => {
    // Abort the fetch (drops the upstream generation) AND cancel the reader,
    // so the read loop ends now rather than when the socket notices.
    abortRef.current?.abort();
    abortRef.current = null;
    void readerRef.current?.cancel().catch(() => { /* already closed */ });
    readerRef.current = null;
  }, []);

  const send = useCallback(async () => {
    const text = input.trim();
    if ((!text && !pending.length) || streaming) return;
    const userMsg: OllamaMsg = { role: 'user', content: text };
    if (pending.length) userMsg.images = pending;
    const next = [...history, userMsg];
    setHistory([...next, { role: 'assistant', content: '' }]);
    setInput(''); setPending([]); setStreaming(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const context = next.slice(-CONTEXT_TURNS).map(m => ({
      role: m.role, content: m.content,
      ...(m.images?.length ? { images: m.images } : {}),
    }));

    const patch = (fn: (a: OllamaMsg) => OllamaMsg) => setHistory(h => {
      const copy = h.slice();
      const last = copy[copy.length - 1];
      if (last?.role === 'assistant') copy[copy.length - 1] = fn(last);
      return copy;
    });

    try {
      const res = await fetch(`${API}/ollama/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: context, think }),
        signal: ctrl.signal,
      });
      if (res.status === 404) { setGate('denied'); return; }
      if (!res.ok || !res.body) {
        let detail = `HTTP ${res.status}`;
        try { detail = (await res.json())?.detail || detail; } catch { /* keep */ }
        patch(a => ({ ...a, error: detail }));
        return;
      }
      const reader = res.body.getReader();
      readerRef.current = reader;
      const dec = new TextDecoder();
      let buf = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const { events, rest } = parseSse(buf);
        buf = rest;
        for (const ev of events) {
          if (typeof ev.delta === 'string') patch(a => ({ ...a, content: a.content + ev.delta }));
          else if (typeof ev.thinking === 'string') patch(a => ({ ...a, thinking: (a.thinking || '') + ev.thinking }));
          else if (ev.error) patch(a => ({ ...a, error: String(ev.error) }));
          else if (ev.done) patch(a => ({ ...a, stats: {
            eval_count: ev.eval_count as number | null,
            total_duration: ev.total_duration as number | null,
          } }));
        }
      }
    } catch (e: unknown) {
      const aborted = (e as { name?: string })?.name === 'AbortError';
      if (!aborted) patch(a => ({ ...a, error: String((e as Error)?.message || e) }));
    } finally {
      setStreaming(false);
      abortRef.current = null;
      readerRef.current = null;
      taRef.current?.focus();
    }
  }, [input, pending, streaming, history, think]);

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(); }
  };

  const clear = () => {
    stop();
    setHistory([]);
    try { window.localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
  };

  const statusLine = useMemo(() => {
    if (!status) return null;
    if (!status.reachable) return { cls: 'ol-dot-off', text: 'Ollama not reachable — brew services start ollama' };
    if (!status.resident) return { cls: 'ol-dot-warm', text: 'loading model…' };
    return { cls: 'ol-dot-on', text: 'resident · pinned' };
  }, [status]);

  if (gate === 'denied') return <NotFound />;
  if (gate === 'checking') return <div className="ol-page"><p className="lede">…</p></div>;

  return (
    <div className="ol-page" onDrop={onDrop} onDragOver={e => e.preventDefault()}>
      <header className="ol-head">
        <div>
          <div className="eyebrow">Private · local model</div>
          <h1 className="display ol-title">Ollama</h1>
        </div>
        <div className="ol-status" title={status ? `${status.model}${status.version ? ` · Ollama ${status.version}` : ''}${status.context_length ? ` · ctx ${status.context_length.toLocaleString()}` : ''}` : ''}>
          {statusLine && <span className={`ol-dot ${statusLine.cls}`} aria-hidden="true" />}
          <span className="ol-model">{status?.model ?? '—'}</span>
          {statusLine && <span className="ol-status-text">{statusLine.text}</span>}
          {status?.capabilities?.includes('vision') && <span className="ol-cap">vision</span>}
        </div>
      </header>

      <div className="ol-thread" role="log" aria-live="polite">
        {history.length === 0 && (
          <p className="ol-empty">Runs on this Mac. Nothing leaves it. Drop an image or type.</p>
        )}
        {history.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'ol-msg ol-user' : 'ol-msg ol-assistant'}>
            {m.images?.length ? (
              <div className="ol-thumbs">
                {m.images.map((b64, k) => (
                  <img key={k} className="ol-thumb" alt={`attached ${k + 1}`} src={`data:image/jpeg;base64,${b64}`} />
                ))}
              </div>
            ) : m.imageCount ? (
              <div className="ol-thumbs"><span className="ol-thumb-gone">📷 {m.imageCount}</span></div>
            ) : null}
            {m.thinking && (
              <details className="ol-think">
                <summary>thinking{streaming && i === history.length - 1 && !m.content ? '…' : ''}</summary>
                <pre>{m.thinking}</pre>
              </details>
            )}
            {m.role === 'assistant'
              ? (m.content
                  ? <div className="ol-body"><MarkdownLite text={m.content} /></div>
                  : (streaming && i === history.length - 1 && !m.error
                      ? <span className="ol-cursor" aria-label="generating">▍</span>
                      : null))
              : <div className="ol-body ol-plain">{m.content}</div>}
            {m.error && <div className="ol-err">{m.error}</div>}
            {m.stats && (
              <div className="ol-meta">
                {fmtDuration(m.stats.total_duration)}{' '}
                {tokPerSec(m.stats.eval_count, m.stats.total_duration)}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="ol-composer">
        {pending.length > 0 && (
          <div className="ol-thumbs ol-pending">
            {pending.map((b64, k) => (
              <span key={k} className="ol-pending-item">
                <img className="ol-thumb" alt={`pending ${k + 1}`} src={`data:image/jpeg;base64,${b64}`} />
                <button type="button" className="ol-x" aria-label="remove image"
                        onClick={() => setPending(p => p.filter((_, j) => j !== k))}>×</button>
              </span>
            ))}
          </div>
        )}
        <div className="ol-row">
          <button type="button" className="ol-btn ol-attach" title="Attach images"
                  onClick={() => fileRef.current?.click()} disabled={pending.length >= MAX_IMAGES}>
            📎
          </button>
          <input ref={fileRef} type="file" accept="image/*" multiple hidden
                 data-testid="ol-file"
                 onChange={e => { void addFiles(e.target.files); e.target.value = ''; }} />
          <textarea
            ref={taRef}
            className="ol-input"
            placeholder="Message… (Enter to send, Shift+Enter for a new line, paste or drop images)"
            value={input}
            rows={2}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKey}
            onPaste={onPaste}
            disabled={streaming}
            autoFocus
          />
          {streaming
            ? <button type="button" className="ol-btn ol-stop" onClick={stop}>Stop</button>
            : <button type="button" className="ol-btn ol-send" onClick={() => void send()}
                      disabled={!input.trim() && !pending.length}>Send</button>}
        </div>
        <div className="ol-tools">
          <label className="ol-toggle">
            <input type="checkbox" checked={think} onChange={e => setThink(e.target.checked)} />
            think
          </label>
          <span className="ol-hint">{history.length ? `${history.length} messages` : ''}</span>
          <button type="button" className="ol-link" onClick={clear} disabled={!history.length}>Clear</button>
        </div>
      </div>
    </div>
  );
}
