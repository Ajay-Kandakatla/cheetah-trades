import { useEffect, useRef, useState } from 'react';

type Props = {
  title: string;
  children: React.ReactNode;
  /** If true, renders inline (next to a label) instead of the default
   *  absolute-positioned top-right corner pin. Use this whenever the icon
   *  should sit beside a heading/label rather than float in a container. */
  inline?: boolean;
};

export function InfoButton({ title, children, inline = false }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onEsc);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onEsc);
    };
  }, [open]);

  return (
    <div className={`info-button${inline ? ' info-button--inline' : ''}`} ref={ref}>
      <button
        type="button"
        className="info-button__trigger"
        aria-label={`What is ${title}?`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        ⓘ
      </button>
      {open && (
        <div className="info-button__pop" role="dialog" aria-label={title}>
          <div className="info-button__head">
            <div className="info-button__title">{title}</div>
            <button
              type="button"
              className="info-button__close"
              aria-label="Close"
              onClick={(e) => { e.stopPropagation(); setOpen(false); }}
            >×</button>
          </div>
          <div className="info-button__body">{children}</div>
        </div>
      )}
    </div>
  );
}
