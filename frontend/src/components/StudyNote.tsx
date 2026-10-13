/**
 * A measured study's verdict, COLLAPSED to its headline.
 *
 * Ajay 2026-09-16, looking at a Chart Maps board carrying three of these at
 * full height: "I see two rules also with icons ... can you collapse all of
 * these please?" — four paragraphs each, stacked, pushed the charts off the
 * screen.
 *
 * WHAT MUST NOT CHANGE: the HEADLINE stays visible, always, unfolded. These
 * banners exist so an ordering that measured `no_signal` is never read as a
 * prediction it did not earn — hiding the verdict itself would defeat them.
 * Only the justification folds. The verdict line is the summary.
 *
 * Native <details>/<summary>: keyboard-operable and findable by the browser's
 * own in-page search with no JS of ours. The open/closed choice is remembered
 * per study id in localStorage, so a study he has opened stays open across
 * reloads and a board he has tidied stays tidy. Storage is best-effort — a
 * private window or blocked site data must render the page exactly the same,
 * just without the memory.
 *
 * `freshKey` (2026-10-12, Ajay's "yes" to "Open the top line by default, or
 * when a new batch arrives?"): the newest SERVED stamp of the thing a note
 * folds. With it, the note opens for a viewer who never folded it, and
 * re-opens when the key is newer than the one stored at his last fold
 * (`cm.study.fresh.<id>`); otherwise his fold is kept. Without it the rule
 * above is unchanged, byte for byte.
 */
import { useCallback, useEffect, useState, type ReactNode } from 'react';

const KEY = 'cm.study.open.';
const KEY_FRESH = 'cm.study.fresh.';

function remembered(id: string, fallback: boolean): boolean {
  try {
    const v = localStorage.getItem(KEY + id);
    return v === null ? fallback : v === '1';
  } catch {
    return fallback;
  }
}

/** The raw remembered fold: null (never folded, or no storage), '1' or '0'. */
function rememberedRaw(id: string): string | null {
  try {
    const v = localStorage.getItem(KEY + id);
    return v === '1' || v === '0' ? v : null;
  } catch {
    return null;
  }
}

/** The fresh key stored at his last fold; null when absent, unreadable or not
 *  a string. */
function rememberedFresh(id: string): string | null {
  try {
    const v: unknown = localStorage.getItem(KEY_FRESH + id);
    return typeof v === 'string' && v ? v : null;
  } catch {
    return null;
  }
}

function rememberFresh(id: string, key: string): void {
  try {
    localStorage.setItem(KEY_FRESH + id, key);
  } catch {
    /* blocked store — the note just re-opens next time */
  }
}

/** Open state for a note that carries a fresh key: never folded → open; his
 *  remembered open → open; folded → stays folded unless the served key is
 *  newer than the one stored when he folded (ISO stamps compare as strings). */
function freshOpen(id: string, freshKey: string): boolean {
  const v = rememberedRaw(id);
  if (v === null || v === '1') return true;
  const f = rememberedFresh(id);
  return f === null || freshKey > f;
}

function remember(id: string, open: boolean): void {
  try {
    localStorage.setItem(KEY + id, open ? '1' : '0');
  } catch {
    /* private window, blocked site data — the fold still works, it just forgets */
  }
}

export type StudyNoteProps = {
  /** Stable id for the remembered open/closed state — never the headline text,
   *  which changes every time a study is re-run. */
  id: string;
  /** The served verdict line. Always visible. */
  headline: string;
  /** The served justification. Folded. */
  body?: string | null;
  fallbackNote?: string | null;
  limits?: string | null;
  /** Extra served lines (e.g. the band-structure scope sentence). Folded. */
  extra?: string | null;
  /** Its own testId — the scope sentence was pinned by name before it folded,
   *  and a pin that moves silently is a pin that stops protecting anything. */
  extraTestId?: string;
  /** Wrapper class, so each study keeps its own left-border colour. */
  className?: string;
  testId?: string;
  /** Default fold state; collapsed unless a study explicitly wants otherwise. */
  defaultOpen?: boolean;
  /** Arbitrary folded content, for a verdict with more served fields than the
   *  four named ones (the Bonde banner has seven). Rendered after them. */
  children?: ReactNode;
  /** Marker glyph in front of the headline (⛔, 🪜 …). Stays with the verdict,
   *  above the fold, because it is part of how he recognises the read. */
  glyph?: string;
  /** Element for the headline itself — 'strong' by default; a board that
   *  opened on an <h3> keeps its heading level for screen readers. */
  headingAs?: 'strong' | 'h3';
  /** The newest served stamp of the thing this note folds; when present the
   *  note opens for a viewer who never folded it, and re-opens when this key
   *  is newer than the one stored at his last fold. */
  freshKey?: string | null;
};

export function StudyNote({
  id, headline, body, fallbackNote, limits, extra, extraTestId,
  className = '', testId, defaultOpen = false, children, glyph,
  headingAs = 'strong', freshKey,
}: StudyNoteProps) {
  const [open, setOpen] = useState<boolean>(defaultOpen);

  // Read the remembered state AFTER mount: reading storage during render makes
  // the first paint depend on it, and a throwing accessor would take the board
  // down instead of one fold.
  // `freshKey` is a dependency: a newer batch served while the note is mounted
  // re-opens it in place; a refetch of the same batch is the same string → no-op.
  useEffect(() => {
    const fresh = typeof freshKey === 'string' && freshKey ? freshKey : null;
    setOpen(fresh == null ? remembered(id, defaultOpen) : freshOpen(id, fresh));
  }, [id, defaultOpen, freshKey]);

  const onToggle = useCallback((e: React.SyntheticEvent<HTMLDetailsElement>) => {
    const next = e.currentTarget.open;
    setOpen(next);
    remember(id, next);
    if (typeof freshKey === 'string' && freshKey) rememberFresh(id, freshKey);
  }, [id, freshKey]);

  const has = Boolean(body || fallbackNote || limits || extra || children);
  const Head = headingAs;
  const head = (
    <Head className={headingAs === 'h3' ? 'cm-study-title' : undefined}
          style={{ flex: '1 1 auto' }}>
      {glyph ? `${glyph} ` : ''}{headline}
    </Head>
  );

  // Nothing to fold: render the verdict as a plain note rather than a
  // <details> with an empty drawer that opens onto nothing.
  if (!has) {
    return (
      <div className={`cm-note cm-study ${className}`.trim()} data-testid={testId}>
        {head}
      </div>
    );
  }

  return (
    <details
      className={`cm-note cm-study ${className}`.trim()}
      data-testid={testId}
      open={open}
      onToggle={onToggle}
    >
      <summary className="cm-study-head">
        {head}
        <span className="cm-study-more" aria-hidden="true">
          {open ? 'less' : 'why'}
        </span>
      </summary>
      {body ? <p>{body}</p> : null}
      {fallbackNote ? <p>{fallbackNote}</p> : null}
      {limits ? <p className="cm-dim">{limits}</p> : null}
      {extra ? <p className="cm-dim" data-testid={extraTestId}>{extra}</p> : null}
      {children}
    </details>
  );
}

export default StudyNote;
