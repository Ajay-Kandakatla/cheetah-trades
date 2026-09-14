/* OllamaChat — private chat with the local Ollama model, Ajay only.
 *
 *  Ajay 2026-09-14: "Can you build me a chat interface to talk to my Ollamma
 *  LLM the abliterated model. I wanna chat with it from this app but only
 *  available for me. ... I can upload images and talk to it."
 *  Then: "Can you let me connect it via the hermes setup so I can chat with
 *  it and make it do things for me via the chat?"
 *
 *  TWO MODES, one page:
 *   Model — talks straight to Ollama (POST /ollama/chat). Fast, stateless,
 *           nothing but the model. History is the browser's.
 *   Agent — talks to Hermes Agent (POST /hermes/chat). Hermes runs the same
 *           model but WITH its tools: terminal on this Mac, browser, files,
 *           memory. Tool calls render as cards in the thread; if Hermes asks
 *           for approval the buttons appear inline. The conversation is a
 *           Hermes session (stored id kept here) so it remembers across
 *           reloads and across the terminal — the same session list Hermes
 *           itself shows.
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
 *   Server-sent events read with fetch + getReader so the Stop button can
 *   abort mid-answer (the backend then cancels the upstream generation —
 *   Ollama's, or Hermes's turn via session.interrupt).
 *
 *  IMAGES
 *   Attach (button, paste, or drop). Each is downscaled client-side to
 *   MAX_EDGE px JPEG before it leaves the browser — a 12 MB phone photo
 *   becomes ~300 KB, and the model's vision projector resizes to its own
 *   grid anyway so nothing is lost that it could have read. The data-URL
 *   prefix is stripped here because both backends want bare base64.
 *
 *  HISTORY
 *   localStorage, text only, one thread per mode. Images live in memory for
 *   the session; after a reload the message shows "📷 n". Clear wipes the
 *   thread (and in Agent mode starts a new Hermes session).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { MarkdownLite } from '../lib/markdownLite';

export type Mode = 'model' | 'agent';

export type ToolEvent = {
  tool_id?: string | null;
  name?: string | null;
  context?: string;
  args?: unknown;
  result?: unknown;
  duration_s?: number | null;
  done: boolean;
};

export type Approval = {
  request_id?: string;
  session_id?: string;
  command?: string;
  tool?: string;
  text?: string;
  choices?: string[];
  answered?: string;
};

export type OllamaMsg = {
  role: 'user' | 'assistant';
  content: string;
  /** Bare base64 (no data: prefix) — exactly what the API wants. */
  images?: string[];
  /** Survives a reload when the bytes do not. */
  imageCount?: number;
  thinking?: string;
  /** Agent mode: tool calls made during this turn, in order. */
  tools?: ToolEvent[];
  /** Agent mode: a pending or answered approval request. */
  approval?: Approval;
  /** Agent mode: status lines Hermes emitted (warnings, clarifications). */
  notes?: string[];
  /** Set on the assistant turn once the stream ends. */
  stats?: { eval_count?: number | null; total_duration?: number | null; input?: number | null; output?: number | null };
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

export type HermesStatus = {
  ok: boolean;
  base_url: string;
  reachable: boolean;
  token_set: boolean;
  reason: string | null;
};

export type HermesSession = {
  session_id: string;          // runtime id (this server process)
  stored_session_id: string;   // survives restarts — what we resume with
  model?: string | null;
  cwd?: string | null;
  tools?: string[] | null;
  approval_mode?: string | null;
};

export const STORAGE_KEY = 'pounce_ollama_v1';
export const AGENT_STORAGE_KEY = 'pounce_hermes_v1';
export const AGENT_SESSION_KEY = 'pounce_hermes_session_v1';
export const MAX_HISTORY = 200;
/** Model mode: messages actually sent back to Ollama each turn. */
export const CONTEXT_TURNS = 40;
export const MAX_IMAGES = 6;
export const MAX_EDGE = 1600;
export const JPEG_QUALITY = 0.88;

const DATA_URL_PREFIX = /^data:[^;]+;base64,/i;

/** Both backends take raw base64. The browser hands us data URLs. */
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

/** One line for a tool card's summary: `terminal · uname -a · 0.2s`. */
export function toolSummary(t: ToolEvent): string {
  const bits = [t.name || 'tool'];
  if (t.context) bits.push(t.context);
  else if (t.args && typeof t.args === 'object') {
    const a = t.args as Record<string, unknown>;
    const first = a.command ?? a.path ?? a.url ?? a.query ?? a.pattern;
    if (typeof first === 'string') bits.push(first);
  }
  if (t.done && typeof t.duration_s === 'number') bits.push(`${t.duration_s < 10 ? t.duration_s.toFixed(1) : Math.round(t.duration_s)}s`);
  return bits.join(' · ');
}

export function toolResultText(r: unknown): string {
  if (r == null) return '';
  if (typeof r === 'string') return r;
  if (typeof r === 'object') {
    const o = r as Record<string, unknown>;
    if (typeof o.output === 'string') return o.output;
    if (typeof o.text === 'string') return o.text;
    if (typeof o.content === 'string') return o.content;
    try { return JSON.stringify(r, null, 1); } catch { return String(r); }
  }
  return String(r);
}

function storageKeyFor(mode: Mode): string {
  return mode === 'agent' ? AGENT_STORAGE_KEY : STORAGE_KEY;
}

function loadHistory(mode: Mode): OllamaMsg[] {
  try {
    const raw = window.localStorage.getItem(storageKeyFor(mode));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(-MAX_HISTORY) : [];
  } catch { return []; }
}

function saveHistory(mode: Mode, msgs: OllamaMsg[]): void {
  try {
    const slim = msgs.slice(-MAX_HISTORY).map(m => {
      if (!m.images?.length) return m;
      const { images, ...rest } = m;
      return { ...rest, imageCount: images.length };
    });
    if (!slim.length) window.localStorage.removeItem(storageKeyFor(mode));
    else window.localStorage.setItem(storageKeyFor(mode), JSON.stringify(slim));
  } catch { /* quota — ignore */ }
}

function loadSession(): HermesSession | null {
  try {
    const raw = window.localStorage.getItem(AGENT_SESSION_KEY);
    return raw ? JSON.parse(raw) as HermesSession : null;
  } catch { return null; }
}

function saveSession(s: HermesSession | null): void {
  try {
    if (s) window.localStorage.setItem(AGENT_SESSION_KEY, JSON.stringify(s));
    else window.localStorage.removeItem(AGENT_SESSION_KEY);
  } catch { /* ignore */ }
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
  const [hermes, setHermes] = useState<HermesStatus | null>(null);
  const [mode, setMode] = useState<Mode>(() => {
    try { return window.localStorage.getItem(`${STORAGE_KEY}.mode`) === 'agent' ? 'agent' : 'model'; } catch { return 'model'; }
  });
  const [history, setHistory] = useState<OllamaMsg[]>(() => loadHistory(mode));
  const [session, setSession] = useState<HermesSession | null>(() => loadSession());
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
  const modeRef = useRef<Mode>(mode);
  modeRef.current = mode;

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

  // Agent-mode probe, only once the gate is open and only in agent mode.
  useEffect(() => {
    if (gate !== 'ok' || mode !== 'agent') return;
    let alive = true;
    fetch(`${API}/hermes/me`, { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .then((j: HermesStatus | null) => { if (alive && j) setHermes(j); })
      .catch(() => { /* status line stays honest */ });
    return () => { alive = false; };
  }, [gate, mode]);

  useEffect(() => { saveHistory(mode, history); }, [mode, history]);
  useEffect(() => { saveSession(session); }, [session]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ block: 'end' }); }, [history, streaming]);
  useEffect(() => {
    try { window.localStorage.setItem(`${STORAGE_KEY}.think`, think ? '1' : '0'); } catch { /* ignore */ }
  }, [think]);

  const switchMode = (next: Mode) => {
    if (next === mode || streaming) return;
    setMode(next);
    setHistory(loadHistory(next));
    try { window.localStorage.setItem(`${STORAGE_KEY}.mode`, next); } catch { /* ignore */ }
  };

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
    // so the read loop ends now rather than when the socket notices. In
    // agent mode also tell Hermes explicitly — the SSE disconnect does it
    // too, but only on its next tick.
    abortRef.current?.abort();
    abortRef.current = null;
    void readerRef.current?.cancel().catch(() => { /* already closed */ });
    readerRef.current = null;
    if (modeRef.current === 'agent' && session?.session_id) {
      fetch(`${API}/hermes/interrupt`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: session.session_id }),
      }).catch(() => { /* best effort */ });
    }
  }, [session]);

  const patchLast = useCallback((fn: (a: OllamaMsg) => OllamaMsg) => setHistory(h => {
    const copy = h.slice();
    const last = copy[copy.length - 1];
    if (last?.role === 'assistant') copy[copy.length - 1] = fn(last);
    return copy;
  }), []);

  /** Apply one SSE event (either backend) to the trailing assistant turn. */
  const applyEvent = useCallback((ev: Record<string, unknown>) => {
    if (typeof ev.delta === 'string') patchLast(a => ({ ...a, content: a.content + ev.delta }));
    else if (typeof ev.thinking === 'string') patchLast(a => ({ ...a, thinking: (a.thinking || '') + ev.thinking }));
    else if (typeof ev.interim === 'string') patchLast(a => ({ ...a, content: a.content + (a.content ? '\n\n' : '') + ev.interim + '\n\n' }));
    else if (ev.error) patchLast(a => ({ ...a, error: String(ev.error) }));
    else if (ev.session && typeof ev.session === 'object') {
      const s = ev.session as HermesSession;
      if (s.session_id) setSession(prev => ({ ...(prev || {} as HermesSession), ...s }));
    }
    else if (typeof ev.tool_generating === 'string') {
      patchLast(a => ({ ...a, tools: [...(a.tools || []), { name: ev.tool_generating as string, done: false }] }));
    }
    else if (ev.tool_start && typeof ev.tool_start === 'object') {
      const t = ev.tool_start as ToolEvent;
      patchLast(a => {
        const tools = (a.tools || []).slice();
        // Replace a trailing "generating" placeholder with the real call.
        const last = tools[tools.length - 1];
        if (last && !last.done && !last.tool_id && last.name === t.name) tools.pop();
        tools.push({ ...t, done: false });
        return { ...a, tools };
      });
    }
    else if (ev.tool_done && typeof ev.tool_done === 'object') {
      const t = ev.tool_done as ToolEvent;
      patchLast(a => {
        const tools = (a.tools || []).slice();
        const i = tools.findIndex(x => x.tool_id && x.tool_id === t.tool_id);
        if (i >= 0) tools[i] = { ...tools[i], ...t, done: true };
        else tools.push({ ...t, done: true });
        return { ...a, tools };
      });
    }
    else if (ev.approval && typeof ev.approval === 'object') {
      patchLast(a => ({ ...a, approval: ev.approval as Approval }));
    }
    else if (ev.status && typeof ev.status === 'object') {
      const s = ev.status as { kind?: string; text?: string };
      if (s.text) patchLast(a => ({ ...a, notes: [...(a.notes || []), `${s.kind ? s.kind + ': ' : ''}${s.text}`] }));
    }
    else if (ev.done) {
      const d = (typeof ev.done === 'object' ? ev.done : {}) as { text?: string; usage?: { input?: number; output?: number } };
      patchLast(a => ({
        ...a,
        // Hermes's final text is authoritative (deltas may include interim commentary).
        content: d.text ? d.text : a.content,
        stats: {
          eval_count: (ev.eval_count as number | null) ?? d.usage?.output ?? null,
          total_duration: (ev.total_duration as number | null) ?? null,
          input: d.usage?.input ?? null, output: d.usage?.output ?? null,
        },
      }));
    }
  }, [patchLast]);

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

    let url: string;
    let body: unknown;
    if (mode === 'agent') {
      url = `${API}/hermes/chat`;
      body = { text, session_id: session?.stored_session_id || null, images: pending.length ? pending : undefined };
    } else {
      url = `${API}/ollama/chat`;
      const context = next.slice(-CONTEXT_TURNS).map(m => ({
        role: m.role, content: m.content,
        ...(m.images?.length ? { images: m.images } : {}),
      }));
      body = { messages: context, think };
    }

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      if (res.status === 404) { setGate('denied'); return; }
      if (!res.ok || !res.body) {
        let detail = `HTTP ${res.status}`;
        try { detail = (await res.json())?.detail || detail; } catch { /* keep */ }
        patchLast(a => ({ ...a, error: detail }));
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
        for (const ev of events) applyEvent(ev);
      }
    } catch (e: unknown) {
      const aborted = (e as { name?: string })?.name === 'AbortError';
      if (!aborted) patchLast(a => ({ ...a, error: String((e as Error)?.message || e) }));
    } finally {
      setStreaming(false);
      abortRef.current = null;
      readerRef.current = null;
      taRef.current?.focus();
    }
  }, [input, pending, streaming, history, think, mode, session, applyEvent, patchLast]);

  const answerApproval = useCallback(async (choice: string) => {
    const last = history[history.length - 1];
    const ap = last?.approval;
    if (!ap?.request_id) return;
    const sid = ap.session_id || session?.session_id;
    patchLast(a => ({ ...a, approval: a.approval ? { ...a.approval, answered: choice } : a.approval }));
    try {
      await fetch(`${API}/hermes/approve`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sid, request_id: ap.request_id, choice }),
      });
    } catch { /* the stream will surface the outcome */ }
  }, [history, session, patchLast]);

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(); }
  };

  const clear = () => {
    stop();
    setHistory([]);
    try { window.localStorage.removeItem(storageKeyFor(mode)); } catch { /* ignore */ }
    if (mode === 'agent') setSession(null);
  };

  const statusLine = useMemo(() => {
    if (mode === 'agent') {
      if (!hermes) return null;
      if (!hermes.token_set) return { cls: 'ol-dot-off', text: 'bridge token not set' };
      if (!hermes.reachable) return { cls: 'ol-dot-off', text: hermes.reason || 'Hermes backend not running' };
      return { cls: 'ol-dot-on', text: session?.stored_session_id ? `session ${session.stored_session_id}` : 'connected · new session' };
    }
    if (!status) return null;
    if (!status.reachable) return { cls: 'ol-dot-off', text: 'Ollama not reachable — brew services start ollama' };
    if (!status.resident) return { cls: 'ol-dot-warm', text: 'loading model…' };
    return { cls: 'ol-dot-on', text: 'resident · pinned' };
  }, [mode, status, hermes, session]);

  if (gate === 'denied') return <NotFound />;
  if (gate === 'checking') return <div className="ol-page"><p className="lede">…</p></div>;

  const placeholder = mode === 'agent'
    ? 'Ask Hermes to do something… (Enter to send, Shift+Enter for a new line, paste or drop images)'
    : 'Message… (Enter to send, Shift+Enter for a new line, paste or drop images)';

  return (
    <div className="ol-page" onDrop={onDrop} onDragOver={e => e.preventDefault()}>
      <header className="ol-head">
        <div>
          <div className="eyebrow">Private · local model</div>
          <h1 className="display ol-title">{mode === 'agent' ? 'Hermes' : 'Ollama'}</h1>
        </div>
        <div className="ol-head-right">
          <div className="ol-mode" role="tablist" aria-label="Chat mode">
            <button type="button" role="tab" aria-selected={mode === 'model'}
                    className={mode === 'model' ? 'ol-mode-btn is-on' : 'ol-mode-btn'}
                    onClick={() => switchMode('model')} disabled={streaming}
                    title="Talk to the model directly">Model</button>
            <button type="button" role="tab" aria-selected={mode === 'agent'}
                    className={mode === 'agent' ? 'ol-mode-btn is-on' : 'ol-mode-btn'}
                    onClick={() => switchMode('agent')} disabled={streaming}
                    title="Talk to Hermes Agent — it can run commands, browse and edit files on this Mac">Agent</button>
          </div>
          <div className="ol-status" title={mode === 'agent'
            ? `${hermes?.base_url ?? ''}${session?.model ? ` · ${session.model}` : ''}${session?.cwd ? ` · ${session.cwd}` : ''}`
            : (status ? `${status.model}${status.version ? ` · Ollama ${status.version}` : ''}${status.context_length ? ` · ctx ${status.context_length.toLocaleString()}` : ''}` : '')}>
            {statusLine && <span className={`ol-dot ${statusLine.cls}`} aria-hidden="true" />}
            <span className="ol-model">{mode === 'agent' ? (session?.model || status?.model || 'Hermes Agent') : (status?.model ?? '—')}</span>
            {statusLine && <span className="ol-status-text">{statusLine.text}</span>}
            {mode === 'model' && status?.capabilities?.includes('vision') && <span className="ol-cap">vision</span>}
            {mode === 'agent' && <span className="ol-cap">tools</span>}
          </div>
        </div>
      </header>

      <div className="ol-thread" role="log" aria-live="polite">
        {history.length === 0 && (
          <p className="ol-empty">
            {mode === 'agent'
              ? 'Hermes runs on this Mac with its tools — terminal, browser, files, memory. Ask it to do something.'
              : 'Runs on this Mac. Nothing leaves it. Drop an image or type.'}
          </p>
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
            {m.tools?.length ? (
              <div className="ol-tools-list">
                {m.tools.map((t, k) => (
                  <details key={k} className={t.done ? 'ol-tool ol-tool-done' : 'ol-tool ol-tool-live'} open={!t.done}>
                    <summary><span className="ol-tool-glyph" aria-hidden="true">{t.done ? '▸' : '▹'}</span> {toolSummary(t)}{!t.done ? '…' : ''}</summary>
                    {t.done && <pre className="ol-tool-out">{toolResultText(t.result)}</pre>}
                  </details>
                ))}
              </div>
            ) : null}
            {m.approval && (
              <div className="ol-approval" role="group" aria-label="approval request">
                <div className="ol-approval-text">
                  Hermes wants to run{m.approval.tool ? ` ${m.approval.tool}` : ''}: <code>{m.approval.command || m.approval.text || '(see thread)'}</code>
                </div>
                {m.approval.answered
                  ? <div className="ol-approval-done">answered: {m.approval.answered}</div>
                  : (
                    <div className="ol-approval-btns">
                      {(m.approval.choices?.length ? m.approval.choices : ['once', 'deny']).map(c => (
                        <button key={c} type="button" className={c === 'deny' ? 'ol-btn ol-stop' : 'ol-btn ol-send'}
                                onClick={() => void answerApproval(c)}>{c}</button>
                      ))}
                    </div>
                  )}
              </div>
            )}
            {m.role === 'assistant'
              ? (m.content
                  ? <div className="ol-body"><MarkdownLite text={m.content} /></div>
                  : (streaming && i === history.length - 1 && !m.error
                      ? <span className="ol-cursor" aria-label="generating">▍</span>
                      : null))
              : <div className="ol-body ol-plain">{m.content}</div>}
            {m.notes?.length ? <div className="ol-notes">{m.notes.map((n, k) => <div key={k} className="ol-note">{n}</div>)}</div> : null}
            {m.error && <div className="ol-err">{m.error}</div>}
            {m.stats && (
              <div className="ol-meta">
                {fmtDuration(m.stats.total_duration)}{' '}
                {tokPerSec(m.stats.eval_count, m.stats.total_duration)}
                {m.stats.input != null && m.stats.output != null ? `${m.stats.input.toLocaleString()} in · ${m.stats.output.toLocaleString()} out` : ''}
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
            placeholder={placeholder}
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
          {mode === 'model' && (
            <label className="ol-toggle">
              <input type="checkbox" checked={think} onChange={e => setThink(e.target.checked)} />
              think
            </label>
          )}
          {mode === 'agent' && (
            <button type="button" className="ol-link" onClick={clear} disabled={streaming || (!history.length && !session)}>New session</button>
          )}
          <span className="ol-hint">{history.length ? `${history.length} messages` : ''}</span>
          <button type="button" className="ol-link" onClick={clear} disabled={!history.length}>Clear</button>
        </div>
      </div>
    </div>
  );
}
