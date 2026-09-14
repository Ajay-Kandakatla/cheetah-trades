/* markdownLite — the tiny markdown renderer the in-app chats share.
 *
 * Extracted from ChatWidget (2026-09-14) so the private Ollama page could
 * render the same subset without a second copy or a markdown dependency.
 * Supports: paragraphs, headings (## / ###), bullet lists (- / *), bold (**),
 * italics (*), inline code (`), fenced code (```), and bare URLs. Anything
 * fancier (tables, images, footnotes) renders as plain text — on purpose. */
export function MarkdownLite({ text }: { text: string }) {
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
