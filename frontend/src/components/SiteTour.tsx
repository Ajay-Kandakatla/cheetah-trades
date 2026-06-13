/* SiteTour — lightweight onboarding walkthrough (no external dependency).
   Spotlights real UI elements with a dim cutout + a stepped tooltip.

   - Auto-starts for first-time visitors (localStorage flag); the page wires
     that. Replayable on demand via the in-page 🎓 Tour button or the global
     🧭 floating launcher (TourLauncher.tsx), which routes to /sepa and fires
     a 'cheetah:start-tour' event the page listens for.
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
    body: "Your SEPA stock screener — Minervini's Specific Entry Point Analysis. Here's a 60-second tour. Replay it anytime from the 🧭 button at the bottom-left of any page.",
  },
  {
    selector: '.sepa-hero__market',
    title: '1 · Market regime first',
    body: 'Always glance here first. It tells you whether the broad market is safe to be long — even great setups fail in a hostile tape.',
  },
  {
    selector: '.sepa-hero__stats',
    title: '2 · Buyable vs. watchlist',
    body: 'Candidates = buyable right now (the strict book gate). Qualifiers = your watchlist — names that passed the Trend Template and are coiling, waiting to fire. Analyzed / Universe = how many were scanned.',
  },
  {
    selector: '.sepa-hero__actions',
    title: '3 · Run a scan',
    body: "Fast Scan joins cached research with today's prices (~30s). Full Scan re-runs every name from scratch — slower, but refreshes the research cache.",
  },
  {
    selector: '.sepa-univ',
    title: '4 · Pick your universe',
    body: 'Mix & match building blocks — Curated, S&P 500, Russell 3000, Micro-caps, ETFs. Overlaps dedupe automatically; a subset already inside a broader pick is dimmed with “⊂ incl”.',
  },
  {
    selector: '.sepa-filterbar',
    title: '5 · Buyable by default',
    body: 'The list opens filtered to Minervini-buyable names. On quiet days that can be empty — normal, there’s nothing to buy. Widen the 🟢 decision chip (Enter → All) to see every qualifier, or filter by rating, stage, whales, momentum. Active filters glow amber.',
  },
  {
    selector: '.sepa-card',
    title: '6 · Read a candidate',
    body: 'Each card leads with price, a timed ENTER / WAIT / AVOID verdict, the setup and the stop. Tap any chip to drill in; tap the symbol for the full detail page.',
  },
  {
    selector: '.vol-trend',
    title: '7 · Volume trend',
    body: "Volume is the tell you can't fake. Green bars are up-volume days, red are down; rising green above the dashed 50-day average means institutions are accumulating. Pairs with the single-day pivot gauge above it.",
  },
  {
    selector: '.stops-panel',
    title: '8 · Entry + stops',
    body: 'The buy point plus every stop method (Structure / Minervini / ATR) sorted tightest → widest — you pick your line in the sand. Hover a row for the $ risk per share.',
  },
  {
    title: '🧠 Ask Minervini anytime',
    body: 'Tap the gold chat button (bottom-right) to ask the in-app Minervini brain — it answers from his two books with page citations and can read whatever chart you’re viewing. Replay this tour from the 🧭 button bottom-left. Happy hunting!',
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
