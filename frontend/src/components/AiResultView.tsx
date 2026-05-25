/* AiResultView — tiny markdown renderer for LLM research results.
 *
 * We don't want a full markdown library dependency for ~500 chars of
 * structured output. The LLM runner produces a known-shape document:
 *
 *     ## TL;DR
 *     paragraph
 *     ## Key findings
 *     - bullet
 *     - bullet
 *     ## Practical steps
 *     ...
 *     ## Suggested searches
 *     query 1
 *     query 2
 *
 * This component handles just enough syntax to render that cleanly:
 *   - `## heading`    → small bold subhead
 *   - `- item` / `* item` → bullet list (multi-line groups)
 *   - blank line     → paragraph break
 *   - everything else → paragraph text
 *
 * No inline emphasis (no **bold**, no *italic*) — Gemma tends to use
 * those sparingly and the absence of parsing is more predictable than
 * a partial implementation. */
import { useMemo } from 'react';

type Block =
  | { kind: 'heading'; text: string }
  | { kind: 'list';    items: string[] }
  | { kind: 'para';    text: string }
  | { kind: 'search';  query: string };

/** Split the markdown into ordered blocks. The "Suggested searches"
 *  section gets a special treatment — each line becomes a clickable
 *  search-query chip rather than a plain paragraph. */
function parse(md: string): Block[] {
  const lines = md.split('\n');
  const blocks: Block[] = [];
  let i = 0;
  let inSearches = false;
  let listBuf: string[] = [];
  let paraBuf: string[] = [];

  const flushList = () => {
    if (listBuf.length) {
      blocks.push({ kind: 'list', items: listBuf });
      listBuf = [];
    }
  };
  const flushPara = () => {
    if (paraBuf.length) {
      blocks.push({ kind: 'para', text: paraBuf.join(' ') });
      paraBuf = [];
    }
  };

  while (i < lines.length) {
    const raw = lines[i];
    const line = raw.trim();
    if (!line) {
      flushList();
      flushPara();
      i++;
      continue;
    }
    if (line.startsWith('## ')) {
      flushList();
      flushPara();
      const heading = line.slice(3).trim();
      blocks.push({ kind: 'heading', text: heading });
      inSearches = /^suggested searches/i.test(heading);
      i++;
      continue;
    }
    if (line.startsWith('- ') || line.startsWith('* ')) {
      flushPara();
      listBuf.push(line.slice(2));
      i++;
      continue;
    }
    if (inSearches) {
      // Each non-empty line under "Suggested searches" is a query chip.
      flushList(); flushPara();
      blocks.push({ kind: 'search', query: line });
      i++;
      continue;
    }
    paraBuf.push(line);
    i++;
  }
  flushList();
  flushPara();
  return blocks;
}

export function AiResultView({ markdown }: { markdown: string }) {
  const blocks = useMemo(() => parse(markdown || ''), [markdown]);
  return (
    <div style={{ fontSize: '0.86rem', lineHeight: 1.55, color: 'var(--ink, inherit)' }}>
      {blocks.map((b, i) => {
        if (b.kind === 'heading') {
          return (
            <h4
              key={i}
              style={{
                fontSize: '0.78rem',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                color: 'var(--cm-slate)',
                margin: i === 0 ? '0 0 0.3rem' : '0.7rem 0 0.3rem',
                fontWeight: 700,
              }}
            >
              {b.text}
            </h4>
          );
        }
        if (b.kind === 'list') {
          return (
            <ul key={i} style={{ paddingLeft: '1.1rem', margin: '0 0 0.5rem', display: 'grid', gap: '0.25rem' }}>
              {b.items.map((it, j) => <li key={j}>{it}</li>)}
            </ul>
          );
        }
        if (b.kind === 'search') {
          // Open a Google search in a new tab — the user can refine
          // from there if they want to use Perplexity / ChatGPT / etc.
          const url = `https://www.google.com/search?q=${encodeURIComponent(b.query)}`;
          return (
            <a
              key={i}
              href={url}
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'inline-block',
                margin: '0 0.3rem 0.3rem 0',
                padding: '2px 8px',
                fontSize: '0.74rem',
                background: 'rgba(59,130,246,0.08)',
                border: '1px solid rgba(59,130,246,0.3)',
                color: '#60a5fa',
                borderRadius: 3,
                textDecoration: 'none',
              }}
            >
              🔍 {b.query}
            </a>
          );
        }
        return (
          <p key={i} style={{ margin: '0 0 0.5rem' }}>{b.text}</p>
        );
      })}
    </div>
  );
}
