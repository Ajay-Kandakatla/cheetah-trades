/* 🧹 GgFold — the ⓘ toggle, the hidden-but-mounted body and the closed-fold state lines for 🚩 Gajjala's landing
 * (2026-11-24, ggclean spec §3.2).
 *
 * Ajay 2026-11-24, three messages with screenshots:
 *   "Hide all of this nouce besides the scan button and log trade button no explantions on the landing pages anymor"
 *   "Add all of this too"
 *   "Collapse all of this too"
 *
 * GgFoldToggle — the small ⓘ button (aria-expanded / aria-controls); a null key renders nothing. Counts opens
 *   (trackFeature) so lines he never opens can later be judged on a number.
 * GgFoldBody — the text stays MOUNTED; closed = the `hidden` attribute on one wrapper (ggFold.css carries the display
 *   twin, this app has no global [hidden] rule). A null key = a bare fragment: the DOM-identical path for 🧪 / 1-min.
 *   Several bodies may share one key (segments); one carries the `id` the toggle controls.
 * GgSubState — while a sub's fold is CLOSED, the served empty / chartless / fault lines that would otherwise hide with
 *   the panel; open, the panel prints them in place (never twice on screen).
 * Key resolution [fixed: C5]: both hooks are called unconditionally, first lines of the body — never useContext in a
 * ternary. This file types one word, GG_FOLD_TITLE; every other printed string is served. */
import { createContext, useContext, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ggHref } from '../lib/gajjala';
import { useGgFold, type GgFoldState } from '../lib/ggFold';
import { trackFeature } from '../lib/usageTracker';
import '../styles/ggFold.css';

/** The active sub's fold key; null = no fold here. */
export const GgSubFoldContext = createContext<string | null>(null);
/** The Chart Maps page's header rows for 🚩 (null on every other tab). */
export const GgHeadPageContext = createContext<ReactNode>(null);

export const GG_FOLD_GLYPH = 'ⓘ';
export const GG_FOLD_TITLE = 'details';          // title + aria-label — the ONLY typed word

/** The board's servedText guard (copied per file by house rule): a non-empty string, else nothing prints. */
function servedText(v: unknown): v is string {
  return typeof v === 'string' && v.trim() !== '';
}

/** The fold of the sub this component renders under (GgSubFoldContext); no provider → no fold. */
export function useGgSubFold(): GgFoldState {
  return useGgFold(useContext(GgSubFoldContext));
}

export function GgFoldToggle({ k, testid, controls }: { k?: string | null; testid?: string; controls?: string }) {
  const ctx = useContext(GgSubFoldContext);
  const key = k !== undefined ? k : ctx;
  const f = useGgFold(key);
  if (key === null) return null;
  const onClick = () => {
    const opening = !f.open;
    f.toggle();
    if (opening) trackFeature(`gg-fold:${key}`);
  };
  return (
    <button type="button" className="gg-fold-toggle" data-testid={testid} aria-expanded={f.open} aria-controls={controls}
            title={GG_FOLD_TITLE} aria-label={GG_FOLD_TITLE} onClick={onClick}>
      {GG_FOLD_GLYPH}
    </button>
  );
}

export function GgFoldBody({ k, id, testid, children }: { k?: string | null; id?: string; testid?: string; children?: ReactNode }) {
  const ctx = useContext(GgSubFoldContext);
  const key = k !== undefined ? k : ctx;
  const f = useGgFold(key);
  if (key === null) return <>{children}</>;
  return (
    <div className="gg-fold-body" id={id} data-testid={testid} data-fold={key} hidden={!f.open}>
      {children}
    </div>
  );
}

export type GgSubStateLine = { kind: 'empty' | 'chartless' | 'faults' | 'fault'; key: string; text: string; href?: string | null };

const KIND_CLASS: Record<GgSubStateLine['kind'], string> = {
  empty: 'gg-dv-line',
  chartless: 'gg-dv-line gg-dv-chartless',
  faults: 'gg-dv-line cm-note',
  fault: 'gg-dv-line cm-note cm-note-err',
};

function lineTestid(l: GgSubStateLine, key: string): string {
  if (l.kind === 'empty') return 'gg-substate-empty';
  if (l.kind === 'faults') return 'gg-substate-faults';
  if (l.kind === 'chartless') return `gg-substate-chartless-${key}`;
  return `gg-substate-fault-${key}`;
}

/** The served state lines of a sub, printed only WHILE ITS FOLD IS CLOSED. No fold, open fold, or no served line → nothing. */
export function GgSubState({ lines }: { lines: GgSubStateLine[] }) {
  const f = useGgSubFold();
  if (!f.on || f.open || !Array.isArray(lines) || !lines.length) return null;
  const kept = lines.filter((l): l is GgSubStateLine =>
    !!l && typeof l === 'object' && Object.prototype.hasOwnProperty.call(KIND_CLASS, l.kind) && servedText(l.text));
  if (!kept.length) return null;
  return (
    <div className="gg-dv gg-substate" data-testid="gg-substate">
      {kept.map((l, i) => {
        const key = servedText(l.key) ? l.key : String(i);
        const href = l.kind === 'chartless' ? ggHref(l.href) : null;
        return (
          <p key={`${l.kind}-${key}-${i}`} className={KIND_CLASS[l.kind]} data-testid={lineTestid(l, key)}>
            {href ? <Link to={href}>{l.text}</Link> : l.text}
          </p>
        );
      })}
    </div>
  );
}
