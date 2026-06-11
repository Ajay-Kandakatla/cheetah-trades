/* Collapsible — tuck verbose card content behind a "more" toggle (Ajay
 * 2026-06-11: "add collapsible features to verbose content on cards").
 *
 * Two shapes:
 *   <Collapsible label="why">…long block…</Collapsible>
 *     — content hidden behind a small ▸ button; the LABEL says what's inside.
 *   <ClampText lines={2}>…long prose…</ClampText>
 *     — prose shown line-clamped with an inline "more" that releases the clamp.
 *
 * Both are plain buttons with aria-expanded (screen-reader + keyboard OK),
 * stopPropagation'd so they compose inside clickable cards without firing
 * the card's own onClick. */
import { useState } from 'react';

export function Collapsible({ label = 'more', children, defaultOpen = false }: {
  label?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <span style={{ display: 'block' }} onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        aria-expanded={open}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen((v) => !v); }}
        className="mono"
        style={{
          fontSize: '0.72rem', padding: '2px 9px', borderRadius: 6, cursor: 'pointer',
          background: 'transparent', color: 'var(--ink-muted, #94a3b8)',
          border: '1px solid var(--hairline, #2a2a2a)', minHeight: 26,
        }}
      >
        {open ? `▾ ${label}` : `▸ ${label}`}
      </button>
      {open && <span style={{ display: 'block', marginTop: 6 }}>{children}</span>}
    </span>
  );
}

export function ClampText({ lines = 2, children, style }: {
  lines?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  const [open, setOpen] = useState(false);
  return (
    <span style={{ display: 'block' }} onClick={(e) => e.stopPropagation()}>
      <span
        style={{
          display: open ? 'block' : '-webkit-box',
          WebkitLineClamp: open ? undefined : lines,
          WebkitBoxOrient: 'vertical' as const,
          overflow: open ? 'visible' : 'hidden',
          ...style,
        }}
      >
        {children}
      </span>
      <button
        type="button"
        aria-expanded={open}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen((v) => !v); }}
        style={{
          fontSize: '0.7rem', padding: 0, marginTop: 2, cursor: 'pointer',
          background: 'transparent', border: 'none',
          color: 'var(--ink-muted, #94a3b8)', textDecoration: 'underline',
        }}
      >
        {open ? 'less' : 'more'}
      </button>
    </span>
  );
}
