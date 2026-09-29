import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { trackFeature } from '../lib/usageTracker';

type Props = {
  title: string;
  children: React.ReactNode;
  /** If true, renders inline (next to a label) instead of the default
   *  absolute-positioned top-right corner pin. Use this whenever the icon
   *  should sit beside a heading/label rather than float in a container. */
  inline?: boolean;
  /** Which edge the popover anchors to. 'left' (default) opens RIGHTWARD from
   *  the trigger — correct for triggers on the LEFT of the screen. Use 'right'
   *  for a trigger near the RIGHT edge so the popover opens LEFTWARD and doesn't
   *  run off-screen (the bug Ajay hit on the breakouts column ⓘ, 2026-06-17). */
  align?: 'left' | 'right';
  /** Render the popover as a FIXED sheet in a portal on <body> (2026-09-28).
   *  For a trigger inside a scrolling box — a table header in an
   *  `overflow: auto` wrapper clips an absolute popover by construction (the
   *  🔥 Hottest Quality ⓘ). Opening focuses the sheet's close button; Esc or ×
   *  returns focus to the trigger. Off by default: nothing else changes. */
  sheet?: boolean;
};

export function InfoButton({ title, children, inline = false, align = 'left', sheet = false }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  /* Esc and × close AND, on a sheet, hand focus back to the trigger — the
     sheet lives in a portal, so without this focus would land on <body>. */
  const closeAndReturn = () => {
    setOpen(false);
    if (sheet) triggerRef.current?.focus();
  };

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      const t = e.target as Node;
      // The sheet is portalled OUT of the wrapper, so it must be tested
      // separately — or every click inside it would count as "outside".
      if (!ref.current?.contains(t) && !popRef.current?.contains(t)) setOpen(false);
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') closeAndReturn();
    }
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onEsc);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onEsc);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (open && sheet) closeRef.current?.focus();
  }, [open, sheet]);

  const pop = open ? (
    <div className={`info-button__pop${sheet ? ' info-button__pop--sheet' : ''}`}
         role="dialog" aria-label={title} ref={popRef}>
      <div className="info-button__head">
        <div className="info-button__title">{title}</div>
        <button
          type="button"
          className="info-button__close"
          aria-label="Close"
          ref={closeRef}
          onClick={(e) => { e.stopPropagation(); closeAndReturn(); }}
        >×</button>
      </div>
      <div className="info-button__body">{children}</div>
    </div>
  ) : null;

  return (
    <div
      className={`info-button${inline ? ' info-button--inline' : ''}${align === 'right' ? ' info-button--align-right' : ''}`}
      ref={ref}
    >
      <button
        type="button"
        className="info-button__trigger"
        aria-label={`What is ${title}?`}
        aria-expanded={open}
        ref={triggerRef}
        onClick={() => setOpen((v) => {
          if (!v) trackFeature(`info:${title}`);   // which features the user explores
          return !v;
        })}
      >
        ⓘ
      </button>
      {pop && sheet && typeof document !== 'undefined' ? createPortal(pop, document.body) : pop}
    </div>
  );
}
