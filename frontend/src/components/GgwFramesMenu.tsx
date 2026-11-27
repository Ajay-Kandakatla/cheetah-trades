/* GgwFramesMenu — 👀 Gajjala's Watch: the frames dropdown (2026-11-27, spec watch5m rev 2 §3.3, WP lib-frames).
 * Ajay: "Give me a drop down or multi select like button to toggle 1 mins and 15 mins 5 mins by default..".
 *
 * One button (the on-frames' SERVED labels + ▾) opens a small group of checkboxes, one per served frame, then the
 * "Average volume line" opt-in (his "not sure what the line on volume is its blocking my story.."). Mounted on the board
 * head and inside ⤢, each with its own choice. The ticks are ggwFramesOn(options, on): a stored frame that is not served
 * never shows ticked. The only frame still on is disabled (one frame always stays on). Not a <details> (the board already
 * has two). Stays open across ticks; closes on the button, a pointerdown outside, or Escape — Escape is caught on
 * `document` in the CAPTURE phase and stopped, so it closes this menu, not ⤢ (GgwStretch listens in the bubble phase).
 * Every word is a served label or a GGW_FRAMES_WORDS control word. */
import { useEffect, useRef, useState } from 'react';
import { GGW_FRAMES_WORDS, ggwFramesOn, ggwVolAvgTitle } from '../lib/ggwFrames';
import '../styles/ggwFrames.css';

export function GgwFramesMenu(p: {
  /** SERVED labels ("1-min", "5-min", "15-min"). */
  options: ReadonlyArray<{ tf: string; label: string }>;
  /** The RAW choice; ticks = ggwFramesOn(options tfs, on). */
  on: ReadonlyArray<string>;
  onToggle: (tf: string) => void;
  volAvg: boolean; onVolAvg: () => void;
  /** GGW_FRAMES_WORDS.boardTitle | stretchTitle */
  title: string;
  /** 'ggw-frames' (board) | 'ggw-sframes' (⤢) */
  testid: string;
}): JSX.Element | null {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      e.stopPropagation();
      setOpen(false);
    };
    const onDown = (e: Event) => {
      const el = root.current;
      if (el && e.target instanceof Node && el.contains(e.target)) return;
      setOpen(false);
    };
    document.addEventListener('keydown', onKey, true);
    document.addEventListener('pointerdown', onDown, true);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      document.removeEventListener('pointerdown', onDown, true);
    };
  }, [open]);

  if (!p.options.length) return null;
  const tfs = p.options.map((o) => o.tf);
  const ticked = ggwFramesOn(tfs, p.on);
  const text = p.options.filter((o) => ticked.includes(o.tf)).map((o) => o.label).join(' · ');
  const lone = ticked.length === 1 ? ticked[0] : null;

  return (
    <span className="ggw-frames" data-testid={p.testid} ref={root}>
      <button type="button" className="ggw-btn ggw-frames-btn" aria-haspopup="true" aria-expanded={open}
              title={p.title} data-testid={`${p.testid}-btn`} onClick={() => setOpen((o) => !o)}>
        {`${text} ▾`}
      </button>
      {open ? (
        <span className="ggw-frames-menu" role="group" aria-label={p.title} data-testid={`${p.testid}-menu`}>
          {p.options.map((o) => {
            const isLone = o.tf === lone;
            return (
              <label key={o.tf} className="ggw-frames-item">
                <input type="checkbox" checked={ticked.includes(o.tf)} disabled={isLone}
                       title={isLone ? GGW_FRAMES_WORDS.lastOn : undefined}
                       data-testid={`${p.testid}-${o.tf}`} onChange={() => { if (!isLone) p.onToggle(o.tf); }} />
                {o.label}
              </label>
            );
          })}
          <label className="ggw-frames-item ggw-frames-item--vol" title={ggwVolAvgTitle()}>
            <input type="checkbox" checked={p.volAvg} data-testid={`${p.testid}-volavg`} onChange={() => p.onVolAvg()} />
            {GGW_FRAMES_WORDS.volAvg}
          </label>
        </span>
      ) : null}
    </span>
  );
}
