/* ChatWidget — floating in-app chat with Claude.
 *
 *  Sits in the bottom-right corner of every page. Tap the bubble to
 *  open the conversation panel; tap again to collapse. The widget
 *  reads from usePageContext() so questions like "what's this stock
 *  doing?" can be answered against actual on-screen data.
 *
 *  Architecture:
 *   - Conversation state held in sessionStorage so it survives page
 *     navigations within the SPA but clears on a hard reload (the
 *     user typically wants a fresh chat after closing the tab).
 *   - POST /chat sends the message history + page context, returns
 *     Claude's full text reply. Non-streaming for now — can swap to
 *     SSE later if we want the typewriter effect.
 *   - Markdown rendered via a tiny inline renderer (matches the
 *     style of MarkdownLite in MacroContextModal — no new dependency).
 *
 *  Cost guardrails:
 *   - Backend rate limits to 20 messages/minute per IP.
 *   - Conversation hard-stops at 30 turns; "Clear" button resets.
 *   - max_tokens=1400 server-side keeps individual responses bounded.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { usePageContext } from '../hooks/usePageContext';

type Msg = { role: 'user' | 'assistant'; content: string; citations?: string[] };

const STORAGE_KEY = 'pounce_chat_v1';
const BRAIN_KEY = 'chat.brainMode';
const MAX_TURNS = 30;
const GOLD = '#d4af37';


function loadHistory(): Msg[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(-MAX_TURNS) : [];
  } catch { return []; }
}

function saveHistory(msgs: Msg[]): void {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(msgs.slice(-MAX_TURNS)));
  } catch { /* quota — ignore */ }
}


/* ── Tiny markdown renderer — same shape as MarkdownLite in MacroContextModal.
 * Supports: paragraphs, headings (## / ###), bullet lists (- / *), bold (**),
 * italics (*), inline code (`), fenced code (```), and bare URLs.
 * Anything fancier (tables, images, footnotes) renders as plain text. */
function MarkdownLite({ text }: { text: string }) {
  const lines = text.split('\n');
  const out: JSX.Element[] = [];
  let i = 0;
  let inCode = false;
  let codeBuf: string[] = [];

  const renderInline = (s: string, key: string) => {
    // Code spans
    const parts = s.split(/(`[^`]+`)/g);
    return parts.map((p, idx) => {
      if (p.startsWith('`') && p.endsWith('`')) {
        return <code key={`${key}-c${idx}`} style={{
          background: 'rgba(255,255,255,0.08)',
          padding: '1px 4px', borderRadius: 3,
          fontFamily: 'ui-monospace, monospace', fontSize: '0.86em',
        }}>{p.slice(1, -1)}</code>;
      }
      // Bold then italics
      const withBold = p.split(/(\*\*[^*]+\*\*)/g).map((b, bi) => {
        if (b.startsWith('**') && b.endsWith('**')) {
          return <strong key={`${key}-b${idx}-${bi}`}>{b.slice(2, -2)}</strong>;
        }
        return <span key={`${key}-s${idx}-${bi}`}>{b}</span>;
      });
      return <span key={`${key}-p${idx}`}>{withBold}</span>;
    });
  };

  while (i < lines.length) {
    const ln = lines[i];
    // Fenced code block
    if (ln.startsWith('```')) {
      if (!inCode) {
        inCode = true;
        codeBuf = [];
        i++; continue;
      } else {
        out.push(
          <pre key={`pre-${i}`} style={{
            background: 'rgba(0,0,0,0.35)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 4,
            padding: '0.5rem 0.7rem',
            margin: '0.3rem 0',
            overflowX: 'auto',
            fontFamily: 'ui-monospace, monospace',
            fontSize: '0.78rem',
            lineHeight: 1.45,
            color: '#cfcfd4',
          }}>{codeBuf.join('\n')}</pre>
        );
        inCode = false;
        i++; continue;
      }
    }
    if (inCode) {
      codeBuf.push(ln);
      i++; continue;
    }
    // Headings
    if (ln.startsWith('### ')) {
      out.push(<h4 key={`h-${i}`} style={{ margin: '0.5rem 0 0.2rem', fontSize: '0.94rem' }}>{renderInline(ln.slice(4), `h-${i}`)}</h4>);
      i++; continue;
    }
    if (ln.startsWith('## ')) {
      out.push(<h3 key={`h-${i}`} style={{ margin: '0.5rem 0 0.2rem', fontSize: '1rem' }}>{renderInline(ln.slice(3), `h-${i}`)}</h3>);
      i++; continue;
    }
    // Bullet list — consume consecutive bullets into one <ul>
    if (/^[-*]\s+/.test(ln)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*]\s+/, ''));
        i++;
      }
      out.push(
        <ul key={`ul-${i}`} style={{ margin: '0.2rem 0 0.3rem 1rem', padding: 0 }}>
          {items.map((it, ix) => (
            <li key={ix} style={{ marginBottom: 1, lineHeight: 1.45 }}>{renderInline(it, `ul-${i}-${ix}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    // Blank line = paragraph break
    if (!ln.trim()) {
      out.push(<div key={`gap-${i}`} style={{ height: 4 }} />);
      i++; continue;
    }
    // Default paragraph
    out.push(<p key={`p-${i}`} style={{ margin: '0.15rem 0', lineHeight: 1.5 }}>{renderInline(ln, `p-${i}`)}</p>);
    i++;
  }
  return <>{out}</>;
}


export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState<Msg[]>(() => loadHistory());
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // 🧠 Minervini brain mode — when on, messages go to /brain/ask (RAG over
  // the two books) instead of /chat. Persisted so the preference sticks
  // across reloads (localStorage, unlike the sessionStorage conversation).
  const [brainMode, setBrainMode] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    try { return window.localStorage.getItem(BRAIN_KEY) === '1'; } catch { return false; }
  });
  // Set when /brain/ask answers {not_ingested: true} — the corpus index
  // hasn't been built on this server. Inline note, not an error.
  const [brainNote, setBrainNote] = useState<string | null>(null);
  const { context } = usePageContext();
  const location = useLocation();
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  // Snapshot of "where the user is right now" — gets sent with every
  // chat turn. Combines the URL + the page-supplied data so Claude knows
  // both the route AND the structured state.
  const sendContext = useMemo(() => ({
    path:  location.pathname + location.search,
    ...(context || {}),
  }), [location, context]);

  // Persist conversation across nav so the user can ask follow-ups
  // after clicking a chart, etc.
  useEffect(() => {
    saveHistory(history);
  }, [history]);

  // Auto-scroll on new messages.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [history, sending, open, brainNote]);

  // Focus the input when the panel opens (mobile: avoid auto-keyboard).
  useEffect(() => {
    if (open && window.innerWidth > 720) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const send = async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;
    if (history.length >= MAX_TURNS) {
      setErr(`Conversation hit ${MAX_TURNS} turns — clear to continue.`);
      return;
    }
    setErr(null);
    setBrainNote(null);
    const next: Msg[] = [...history, { role: 'user', content: trimmed }];
    setHistory(next);
    setInput('');
    setSending(true);
    try {
      // Brain mode → /brain/ask (book RAG); off → /chat, exactly as before.
      const r = brainMode
        ? await fetch(`${API}/brain/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              question: trimmed,
              // Last 6 prior turns, in the brain endpoint's {role, text} shape.
              history: history.slice(-6).map((m) => ({ role: m.role, text: m.content })),
              // Same page-context the regular chat sends, serialized — only
              // when the page actually published context.
              app_context: context?.page ? JSON.stringify(sendContext) : undefined,
            }),
          })
        : await fetch(`${API}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              messages:     next,
              page_context: sendContext,
            }),
          });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        if (r.status === 429) {
          setErr('Too fast — limit is 20 messages/min. Wait a minute.');
        } else if (r.status === 503) {
          setErr('Claude API not configured on the backend.');
        } else {
          setErr(j?.detail || `HTTP ${r.status}`);
        }
        return;
      }
      const j = await r.json();
      if (brainMode && j?.not_ingested) {
        setBrainNote(
          'The book index hasn’t been built on this server yet, so I can’t '
          + 'search Minervini’s pages. Toggle 🧠 off for regular chat, or run '
          + 'the book ingest on the backend.',
        );
        return;
      }
      const text = brainMode ? (j?.answer || j?.text) : (j?.ok && j.text);
      if (text) {
        const citations: string[] | undefined = brainMode && Array.isArray(j?.citations)
          ? j.citations.filter((c: unknown): c is string => typeof c === 'string')
          : undefined;
        setHistory((h) => [...h, {
          role: 'assistant',
          content: text,
          ...(citations && citations.length ? { citations } : {}),
        }]);
      } else {
        setErr(brainMode ? 'Empty response from the brain.' : 'Empty response from Claude.');
      }
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setSending(false);
    }
  };

  const clear = () => {
    setHistory([]);
    setErr(null);
    setBrainNote(null);
    try { window.sessionStorage.removeItem(STORAGE_KEY); } catch { /* */ }
  };

  const toggleBrain = () => {
    setBrainMode((b) => {
      const on = !b;
      try { window.localStorage.setItem(BRAIN_KEY, on ? '1' : '0'); } catch { /* */ }
      return on;
    });
  };

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter = send; Shift+Enter = newline. Matches the convention from
    // Slack, iMessage, Claude.ai, ChatGPT — what users expect from a
    // chat textarea. Cmd/Ctrl+Enter also still sends as a holdover for
    // muscle memory from the previous keymap, since some users got used
    // to it before the convention was fixed (2026-05-21).
    if (e.key === 'Enter' && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <>
      {/* Floating launcher — always visible */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open chat with Claude"
          style={{
            position: 'fixed',
            right: 'max(env(safe-area-inset-right), 14px)',
            bottom: 'max(env(safe-area-inset-bottom), 14px)',
            zIndex: 999,
            width: 52, height: 52,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #d4af37 0%, #b8941f 100%)',
            color: '#1a1a1a',
            border: '1px solid rgba(212,175,55,0.6)',
            boxShadow: '0 6px 24px rgba(0,0,0,0.45), 0 0 0 1px rgba(212,175,55,0.3)',
            cursor: 'pointer',
            fontSize: 22,
            fontFamily: 'inherit',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          {/* Chat bubble + AI spark — the Minervini brain, not a plain emoji. */}
          <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true" style={{ display: 'block' }}>
            <path
              d="M4.5 3.5 H19.5 A1.5 1.5 0 0 1 21 5 V14.5 A1.5 1.5 0 0 1 19.5 16 H11 L6.8 20 V16 H4.5 A1.5 1.5 0 0 1 3 14.5 V5 A1.5 1.5 0 0 1 4.5 3.5 Z"
              fill="#1a1a1a"
            />
            <path
              d="M12 6.2 L13 8.7 L15.5 9.7 L13 10.7 L12 13.2 L11 10.7 L8.5 9.7 L11 8.7 Z"
              fill="#d4af37"
            />
          </svg>
        </button>
      )}

      {/* Conversation panel */}
      {open && (
        <div
          role="dialog"
          aria-label="Chat with Claude"
          style={{
            position: 'fixed',
            right: 'max(env(safe-area-inset-right), 12px)',
            bottom: 'max(env(safe-area-inset-bottom), 12px)',
            zIndex: 999,
            width: 'min(380px, calc(100vw - 24px))',
            maxHeight: 'min(70vh, 640px)',
            display: 'flex', flexDirection: 'column',
            background: '#141416',
            border: '1px solid rgba(212,175,55,0.35)',
            borderRadius: 12,
            boxShadow: '0 16px 48px rgba(0,0,0,0.6)',
            color: '#e6e6e6',
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '0.55rem 0.75rem',
            background: 'rgba(212,175,55,0.06)',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
          }}>
            <div>
              <div style={{
                fontSize: '0.62rem', color: '#d4af37',
                letterSpacing: '0.1em', textTransform: 'uppercase',
                fontWeight: 700,
              }}>
                💬 Pounce AI · Claude
              </div>
              {context?.page ? (
                <div style={{ fontSize: '0.68rem', color: '#9a9aa3' }}>
                  context: <strong style={{ color: '#cfcfd4' }}>{String(context.page)}</strong>
                  {context.symbol ? <> · {String(context.symbol)}</> : null}
                </div>
              ) : (
                <div style={{ fontSize: '0.68rem', color: '#6a6a72' }}>
                  no page context (general chat)
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              {/* 🧠 Minervini brain mode pill — gold-tinted while active.
                  Routes messages to /brain/ask (RAG over TLSW + TTLAC)
                  instead of the general /chat endpoint. */}
              <button
                type="button" onClick={toggleBrain}
                aria-pressed={brainMode}
                title={brainMode
                  ? 'Minervini brain ON — answers come from the books, with page citations. Click to switch back to regular chat.'
                  : 'Ask the books — answers grounded in TLSW + TTLAC with page citations.'}
                style={{
                  background: brainMode ? 'rgba(212,175,55,0.18)' : 'transparent',
                  border: brainMode
                    ? `1px solid rgba(212,175,55,0.55)`
                    : '1px solid rgba(255,255,255,0.15)',
                  color: brainMode ? GOLD : '#9a9aa3',
                  padding: '2px 9px', borderRadius: 999,
                  fontSize: '0.7rem', cursor: 'pointer', fontFamily: 'inherit',
                  fontWeight: brainMode ? 700 : 400,
                  whiteSpace: 'nowrap',
                }}
              >
                🧠 Minervini
              </button>
              {history.length > 0 && (
                <button
                  type="button" onClick={clear}
                  title="Clear conversation"
                  style={{
                    background: 'transparent',
                    border: '1px solid rgba(255,255,255,0.15)',
                    color: '#9a9aa3', padding: '2px 8px', borderRadius: 4,
                    fontSize: '0.72rem', cursor: 'pointer', fontFamily: 'inherit',
                  }}
                >
                  clear
                </button>
              )}
              {/* Minimize — collapses the panel back to the floating bubble
                  WITHOUT clearing the conversation. Functionally identical
                  to ✕ today (sessionStorage already persists), but the
                  separate button signals to the user that their conversation
                  is preserved. The ✕ doesn't communicate "you'll keep your
                  history" the same way a minimize icon does. */}
              <button
                type="button" onClick={() => setOpen(false)}
                aria-label="Minimize chat (conversation preserved)"
                title="Minimize · keep conversation"
                style={{
                  background: 'transparent',
                  border: '1px solid rgba(255,255,255,0.15)',
                  color: '#cfcfd4', padding: '2px 8px', borderRadius: 4,
                  fontSize: '0.85rem', cursor: 'pointer', fontFamily: 'inherit',
                  lineHeight: 1,
                }}
              >
                {/* "_" character drawn slightly higher for visual balance
                    with the X. Using an em dash + bottom-align would also
                    work but renders inconsistently across phone browsers. */}
                <span style={{ display: 'inline-block', verticalAlign: 'middle' }}>−</span>
              </button>
              <button
                type="button" onClick={() => { setOpen(false); }}
                aria-label="Close chat"
                title="Close · conversation kept until tab close"
                style={{
                  background: 'transparent',
                  border: '1px solid rgba(255,255,255,0.15)',
                  color: '#cfcfd4', padding: '2px 8px', borderRadius: 4,
                  fontSize: '0.85rem', cursor: 'pointer', fontFamily: 'inherit',
                }}
              >
                ✕
              </button>
            </div>
          </div>

          {/* Message list */}
          <div
            ref={scrollRef}
            style={{
              flex: 1, minHeight: 0, overflowY: 'auto',
              padding: '0.7rem 0.75rem 0.5rem',
              display: 'flex', flexDirection: 'column', gap: '0.5rem',
              fontSize: '0.82rem',
            }}
          >
            {history.length === 0 && (
              <div style={{
                color: '#9a9aa3', fontSize: '0.78rem', lineHeight: 1.5,
                padding: '0.4rem 0',
              }}>
                Ask anything about what's on screen — a candidate's SEPA
                score, the chatter momentum chip, a setup's R:R, a chart
                pattern. I have your current page state and your trading
                style as context.
                <div style={{ marginTop: 6, fontSize: '0.72rem', color: '#6a6a72' }}>
                  <kbd style={{ fontFamily: 'monospace' }}>Enter</kbd> sends ·
                  {' '}<kbd style={{ fontFamily: 'monospace' }}>Shift</kbd>+<kbd style={{ fontFamily: 'monospace' }}>Enter</kbd> newline.
                </div>
              </div>
            )}

            {history.map((m, i) => (
              <div
                key={i}
                style={{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '92%',
                  padding: '0.45rem 0.6rem',
                  borderRadius: 8,
                  background: m.role === 'user'
                    ? 'rgba(59,130,246,0.12)'
                    : 'rgba(20,20,22,0.6)',
                  border: m.role === 'user'
                    ? '1px solid rgba(59,130,246,0.3)'
                    : '1px solid rgba(255,255,255,0.06)',
                }}
              >
                {m.role === 'user' ? (
                  <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.45 }}>{m.content}</div>
                ) : (
                  <>
                    <MarkdownLite text={m.content} />
                    {/* Book citations from /brain/ask — rendered verbatim
                        (e.g. "TLSW p.299", "TTLAC §9 (ebook p.142)") as
                        muted chips under the answer. */}
                    {m.citations && m.citations.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
                        {m.citations.map((c, ci) => (
                          <span
                            key={ci}
                            style={{
                              fontSize: '0.64rem', color: '#9a9aa3',
                              background: 'rgba(255,255,255,0.05)',
                              border: '1px solid rgba(255,255,255,0.1)',
                              borderRadius: 999, padding: '1px 7px',
                              fontFamily: 'ui-monospace, monospace',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            ))}

            {brainNote && (
              <div style={{
                alignSelf: 'flex-start',
                maxWidth: '92%',
                fontSize: '0.76rem', color: '#cdbb7a', lineHeight: 1.5,
                background: 'rgba(212,175,55,0.07)',
                border: '1px solid rgba(212,175,55,0.25)',
                borderRadius: 8,
                padding: '0.45rem 0.6rem',
              }}>
                📚 {brainNote}
              </div>
            )}

            {sending && (
              <div style={{
                alignSelf: 'flex-start',
                fontSize: '0.78rem', color: '#9a9aa3',
                padding: '0.3rem 0.5rem', fontStyle: 'italic',
              }}>
                {brainMode ? 'Searching the books…' : 'Claude is thinking…'}
              </div>
            )}
          </div>

          {/* Composer */}
          {err && (
            <div style={{
              fontSize: '0.74rem', color: '#fca5a5',
              padding: '0.3rem 0.75rem',
              background: 'rgba(239,68,68,0.06)',
              borderTop: '1px solid rgba(239,68,68,0.2)',
            }}>
              {err}
            </div>
          )}
          <div style={{
            display: 'flex', gap: 6, alignItems: 'flex-end',
            padding: '0.5rem 0.6rem 0.6rem',
            borderTop: '1px solid rgba(255,255,255,0.06)',
          }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKey}
              placeholder={sending ? 'sending…' : brainMode ? 'Ask the books…' : 'Ask about this page…'}
              disabled={sending}
              rows={2}
              style={{
                flex: 1,
                background: 'rgba(20,20,22,0.6)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: '#e6e6e6',
                padding: '0.4rem 0.55rem',
                borderRadius: 6,
                fontFamily: 'inherit',
                fontSize: '0.82rem',
                lineHeight: 1.4,
                resize: 'none',
                minHeight: 38, maxHeight: 120,
              }}
            />
            <button
              type="button"
              onClick={send}
              disabled={sending || !input.trim()}
              style={{
                padding: '0.5rem 0.7rem',
                background: sending || !input.trim() ? '#2a2a30' : '#d4af37',
                color: sending || !input.trim() ? '#6a6a72' : '#1a1a1a',
                border: 0, borderRadius: 6,
                fontFamily: 'inherit', fontWeight: 700, fontSize: '0.78rem',
                cursor: sending || !input.trim() ? 'default' : 'pointer',
              }}
            >
              Send
            </button>
          </div>
        </div>
      )}
    </>
  );
}
