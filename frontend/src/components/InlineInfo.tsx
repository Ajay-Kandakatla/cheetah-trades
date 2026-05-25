import { useState, useRef, useEffect, type ReactNode } from 'react';

/* ==========================================================================
   InlineInfo — tiny clickable ⓘ icon with a popover.
   Use inline next to a metric/header to explain what it means.
   Works on touch (tap to toggle) and mouse (hover or click).
   ========================================================================== */

type Props = {
  /** Tooltip body — can be plain text or rich JSX. */
  children: ReactNode;
  /** Optional accessible label for the trigger. */
  label?: string;
  /** Where to anchor the popover relative to the icon. */
  position?: 'top' | 'bottom' | 'right' | 'left';
};

export function InlineInfo({ children, label = 'More info', position = 'bottom' }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  // Click outside to close
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <span ref={ref} className="inline-info">
      <button
        type="button"
        className="inline-info__trigger"
        aria-label={label}
        aria-expanded={open}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={(e) => {
          // Don't close if cursor moved into the popover
          const next = e.relatedTarget as HTMLElement | null;
          if (!next || !ref.current?.contains(next)) setOpen(false);
        }}
        onClick={(e) => {
          e.stopPropagation();
          setOpen(!open);
        }}
      >
        ⓘ
      </button>
      {open && (
        <span
          className={`inline-info__popover inline-info__popover--${position}`}
          role="tooltip"
          onMouseLeave={() => setOpen(false)}
        >
          {children}
        </span>
      )}
    </span>
  );
}
