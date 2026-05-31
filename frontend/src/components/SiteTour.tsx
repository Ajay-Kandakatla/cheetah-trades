/* SiteTour — lightweight onboarding walkthrough (no external dependency).
   Spotlights real UI elements with a dim cutout + a stepped tooltip.

   - Auto-starts for first-time visitors (localStorage flag); the page wires
     that. Replayable on demand via the 🎓 Tour button.
   - Targets stable container classes; a step whose target isn't on screen
     falls back to a centered card, so it never breaks if (say) no scan has
     run yet.
   Added 2026-05-30 per user request. */
import { useCallback, useEffect, useState } from 'react';

export const TOUR_DONE_KEY = 'cheetah_tour_v1_done';

type Step = {
  selector?: string;          // CSS target; omit → centered card
  title: string;
  body: string;
};

const STEPS: Step[] = [
  {
    title: '👋 Welcome to Pounce',
    body: "Your SEPA stock screener — Minervini's Specific Entry Point Analysis. Here's a 60-second tour of how to use it. You can replay this anytime from the 🎓 Tour button up top.",
  },
  {
    selector: '.sepa-hero__market',
    title: '1 · Market regime first',
    body: 'Always glance here first. It tells you whether the broad market is safe to be long — even great setups fail in a hostile tape.',
  },
  {
    selector: '.sepa-hero__stats',
    title: '2 · Your daily numbers',
    body: 'Candidates = buyable right now. Qualifiers = watchlist (passed the Trend Template). Analyzed / Universe = how many names were scanned.',
  },
  {
    selector: '.sepa-hero__actions',
    title: '3 · Run a scan',
    body: "Fast Scan joins cached research with today's prices (~30s). Full Scan re-runs every name from scratch — slower, but refreshes the research cache.",
  },
  {
    selector: '.sepa-univ',
    title: '4 · Pick your universe',
    body: 'Mix & match building blocks — Curated, S&P 500, Russell 3000, Micro-caps, ETFs. Overlaps are deduped automatically; a subset already inside a broader pick is dimmed with “⊂ incl”.',
  },
  {
    selector: '.sepa-filterbar',
    title: '5 · Narrow the list',
    body: 'Filter by rating, stage, setup, whales, momentum and more. Any active filter glows amber, and a “● N filters on” badge shows how many are engaged.',
  },
  {
    selector: '.sepa-card',
    title: '6 · Read a candidate',
    body: 'Each card shows the score/rating, Minervini trend, volume + 🐋 whale chips, and a timed entry/exit verdict (ENTER / WAIT / AVOID). Tap any chip to drill in.',
  },
  {
    selector: '.stops-panel',
    title: '7 · Entry + stops menu',
    body: 'The buy point plus every stop method (Structure / Minervini / ATR) sorted tightest → widest — you pick your line in the sand. Hover a row for the $ risk per share.',
  },
  {
    title: '🚀 You’re set',
    body: 'Click any card for the full breakdown — chart, fundamentals, whales, options, catalyst. Replay this tour anytime via 🎓 Tour at the top. Happy hunting!',
  },
];

const TIP_W = 340;

export function SiteTour({ onClose }: { onClose: () => void }) {
  const [idx, setIdx] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const step = STEPS[idx];
  const centered = !step.selector || !rect;

  const measure = useCallback(() => {
    if (!step.selector) { setRect(null); return; }
    const el = document.querySelector(step.selector);
    setRect(el ? el.getBoundingClientRect() : null);
  }, [step.selector]);

  const finish = useCallback(() => {
    try { localStorage.setItem(TOUR_DONE_KEY, '1'); } catch { /* ignore */ }
    onClose();
  }, [onClose]);

  const next = useCallback(
    () => setIdx((i) => (i < STEPS.length - 1 ? i + 1 : (finish(), i))),
    [finish],
  );
  const prev = useCallback(() => setIdx((i) => Math.max(0, i - 1)), []);

  // Scroll the target into view + measure (twice: now, and after the scroll
  // animation settles).
  useEffect(() => {
    if (step.selector) {
      const el = document.querySelector(step.selector);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    measure();
    const t = setTimeout(measure, 400);
    return () => clearTimeout(t);
  }, [idx, measure, step.selector]);

  // Keep the spotlight glued to the target on scroll/resize + keyboard nav.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') finish();
      else if (e.key === 'ArrowRight') next();
      else if (e.key === 'ArrowLeft') prev();
    };
    window.addEventListener('resize', measure);
    window.addEventListener('scroll', measure, true);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('resize', measure);
      window.removeEventListener('scroll', measure, true);
      window.removeEventListener('keydown', onKey);
    };
  }, [measure, finish, next, prev]);

  // Tooltip position.
  let tipStyle: React.CSSProperties;
  if (centered) {
    tipStyle = { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' };
  } else {
    const left = Math.min(Math.max(rect!.left, 12), window.innerWidth - TIP_W - 12);
    const placeBelow = window.innerHeight - rect!.bottom > 230;
    tipStyle = placeBelow
      ? { top: rect!.bottom + 14, left }
      : { top: rect!.top - 14, left, transform: 'translateY(-100%)' };
  }

  return (
    <div className="tour" role="dialog" aria-modal="true" aria-label="Site tour">
      {centered ? (
        <div className="tour__dim" onClick={finish} />
      ) : (
        <div
          className="tour__spot"
          style={{
            top: rect!.top - 8, left: rect!.left - 8,
            width: rect!.width + 16, height: rect!.height + 16,
          }}
        />
      )}
      <div className="tour__tip" style={{ ...tipStyle, width: TIP_W }}>
        <div className="tour__step">{idx + 1} / {STEPS.length}</div>
        <div className="tour__title">{step.title}</div>
        <div className="tour__body">{step.body}</div>
        <div className="tour__nav">
          <button className="tour__skip" onClick={finish}>Skip tour</button>
          <span style={{ flex: 1 }} />
          {idx > 0 && <button className="tour__btn" onClick={prev}>Back</button>}
          <button className="tour__btn tour__btn--primary" onClick={next}>
            {idx < STEPS.length - 1 ? 'Next →' : 'Done'}
          </button>
        </div>
      </div>
    </div>
  );
}
