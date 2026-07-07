import { useCallback, useEffect, useState } from 'react';

/* ==========================================================================
   /learning — Ajay's Learning Path.

   A personal, curriculum-ordered study page. Ajay pasted a NotebookLM-style
   study plan mapping his source list into a phased reading order (market
   mechanics → SMC → options/vol → synthesis). This renders it verbatim, with
   embedded videos/papers where we have a high-confidence source and
   "Search on YouTube" links everywhere the title was too generic to pin a
   canonical video (never guess a wrong URL).

   Owner-only feature ("learning"), further narrowed to Ajay in the nav (see
   backend/access/store.py build_menu). Progress is tracked per-source in
   localStorage — purely local, no backend.
   ========================================================================== */

type Source =
  | { n: number; title: string; kind: 'youtube'; videoId: string; note?: string }
  | { n: number; title: string; kind: 'youtube-search'; query: string; note?: string }
  | { n: number; title: string; kind: 'link'; url: string; label: string; embedUrl?: string; note?: string }
  | { n: number; title: string; kind: 'reference'; refNote: string; url?: string; label?: string; note?: string };

type Phase = {
  id: string;
  week: string;
  heading: string;
  sources: Source[];
};

/** Prerequisites — foundational topics the study plan assumes you already have.
 *  Rendered before Week 1. Each is one card (one progress item) that can carry a
 *  short researched blurb, an optional high-confidence video embed, an optional
 *  formula callout, curated links, and a YouTube search fallback. These fill the
 *  three gaps called out at the bottom of the plan. */
type Prereq = {
  id: string;
  badge: string;
  title: string;
  blurb: string;
  videoId?: string;
  formula?: string;
  links: { url: string; label: string }[];
  searchQuery?: string;
};

/** The arXiv annotation is a full paragraph in the original — preserved verbatim
 *  and rendered as prose under the source card rather than a one-line note. */
const ARXIV_PARAGRAPH =
  'The arXiv paper (1011.6402) — this is the hidden gem in your list. It’s Cont/Kukanov/Stoikov’s "The Price Impact of Order Book Events," which shows that short-term price changes are driven mainly by order flow imbalance (supply/demand imbalance at best bid/ask), with a linear relationship whose slope is inversely proportional to market depth.  This is the quantitative version of everything the SMC videos describe narratively — and since it’s a formula (OFI), it’s directly codeable in your Alpaca stack. Read it last in this phase, after the intuition-builders.';

const PHASES: Phase[] = [
  {
    id: 'week-1-2',
    week: 'Week 1–2',
    heading: 'Market mechanics (why price moves)',
    sources: [
      {
        n: 1,
        title: 'Depth of Market (DOM) article',
        kind: 'youtube-search',
        query: 'Depth of Market DOM explained trading',
      },
      {
        n: 2,
        title: '“If You Don’t Understand The Order Book…” video',
        kind: 'youtube',
        videoId: 'qWN-VanDkT8',
      },
      {
        n: 3,
        title: 'C5 Heatmap Trading for Beginners',
        kind: 'youtube',
        videoId: 'GvJzspRHqCU',
        note: 'Bookmap’s official beginner heatmap walkthrough (their C5 course module).',
      },
      {
        n: 4,
        title: 'The arXiv paper (1011.6402) — The Price Impact of Order Book Events',
        kind: 'link',
        url: 'https://arxiv.org/abs/1011.6402',
        label: 'Open on arXiv',
        embedUrl: 'https://arxiv.org/pdf/1011.6402',
      },
    ],
  },
  {
    id: 'week-3-5',
    week: 'Week 3–5',
    heading: 'SMC layer (the institutional footprint)',
    sources: [
      {
        n: 5,
        title: 'Liquidity Sweep vs Liquidity Run',
        kind: 'youtube-search',
        query: 'Liquidity Sweep vs Liquidity Run SMC',
        note: 'learn the distinction first, it’s the most common source of bad entries',
      },
      {
        n: 6,
        title: 'Order Blocks & Liquidity Sweeps video',
        kind: 'youtube-search',
        query: 'Order Blocks and Liquidity Sweeps SMC',
      },
      {
        n: 7,
        title: 'Trading Liquidity Sweeps Like a Pro (entries)',
        kind: 'youtube-search',
        query: 'Trading Liquidity Sweeps Like a Pro entries',
      },
      {
        n: 8,
        title: 'smrtalgo PDF',
        kind: 'reference',
        refNote: 'PDF — reference your local copy',
        note: 'likely your FVG/structure reference',
      },
      {
        n: 9,
        title: 'The Confirmation Model: OB + FVG + Liquidity',
        kind: 'youtube-search',
        query: 'Confirmation Model Order Block FVG Liquidity entry',
        note: 'save this for last; it’s your capstone that stacks the three layers into one entry system',
      },
    ],
  },
  {
    id: 'week-6-7',
    week: 'Week 6–7',
    heading: 'Options/volatility layer (the probability map)',
    sources: [
      {
        n: 10,
        title: 'Learning the Greeks',
        kind: 'youtube-search',
        query: 'Learning the option Greeks explained',
      },
      {
        n: 11,
        title: 'Option Pricing & Volatility video',
        kind: 'youtube-search',
        query: 'Option pricing and volatility explained',
      },
      {
        n: 12,
        title: 'Natenberg interview + book review videos',
        kind: 'reference',
        refNote: 'Book — Option Volatility and Pricing (Sheldon Natenberg)',
        url: 'https://www.amazon.com/s?k=Option+Volatility+and+Pricing+Natenberg',
        label: 'Find the book on Amazon',
        note: '→ then actually read Option Volatility and Pricing (chapters on IV, theoretical pricing, and vol skew — skip the market-maker-specific chapters for now)',
      },
      {
        n: 13,
        title: 'Visualizing the Expected Move',
        kind: 'youtube-search',
        query: 'Visualizing the expected move options',
        note: 'this connects IV back to your swing charts as concrete price boundaries',
      },
    ],
  },
  {
    id: 'week-8',
    week: 'Week 8+',
    heading: 'Synthesis',
    sources: [
      {
        n: 14,
        title: 'Algorithmic trading (Wikipedia article)',
        kind: 'link',
        url: 'https://en.wikipedia.org/wiki/Algorithmic_trading',
        label: 'Open on Wikipedia',
        embedUrl: 'https://en.wikipedia.org/wiki/Algorithmic_trading',
        note: '→ then move from reading to building: define the ruleset (HTF bias → sweep → OB/FVG confluence → expected-move target/invalidation) and backtest it.',
      },
    ],
  },
];

const PREREQS: Prereq[] = [
  {
    id: 'prereq-market-structure',
    badge: 'A',
    title: 'Market structure basics — BOS & CHoCH',
    blurb:
      'The Week 3–5 SMC videos assume you can already read structure. BOS (Break of Structure) = trend continuation — price closes beyond the prior swing in the trend direction. CHoCH (Change of Character) = the first sign of reversal — price breaks the swing that created the last BOS. Wicks don’t count; you need a body close.',
    videoId: 'U5DTamH28N0',
    links: [
      { url: 'https://dailypriceaction.com/blog/smc-market-structure/', label: 'SMC Market Structure: BoS & CHoCH made simple' },
      { url: 'https://www.mindmathmoney.com/articles/break-of-structure-change-of-character-explained', label: 'BOS vs CHoCH explained (Mind Math Money)' },
    ],
  },
  {
    id: 'prereq-risk-sizing',
    badge: 'B',
    title: 'Risk management & position sizing',
    blurb:
      'Nothing in the main list covers this — and it’s what actually determines survival. Cap risk at 1–2% of equity per trade: even 10 losses in a row only draws you down ~10–20%, a recoverable setback. Position size falls out of your stop distance, not your conviction.',
    formula: 'Risk $ = Account × risk%   →   Shares = Risk $ ÷ (Entry − Stop)\n\ne.g. $10,000 × 2% = $200 risk ; stop $2 below entry → 100 shares',
    links: [
      { url: 'https://www.britannica.com/money/calculating-position-size', label: 'Calculating position size (Britannica Money)' },
      { url: 'https://www.chartguys.com/articles/position-sizing', label: 'Position sizing for risk management (Chart Guys)' },
      { url: 'https://www.amazon.com/s?k=Van+Tharp+Trade+Your+Way+to+Financial+Freedom', label: 'Book — Van Tharp, Trade Your Way to Financial Freedom' },
    ],
    searchQuery: 'position sizing how much to risk per trade explained',
  },
  {
    id: 'prereq-backtesting',
    badge: 'C',
    title: 'Backtesting methodology (statistical validation)',
    blurb:
      'So “deterministic” means statistically validated, not just rule-based. The trap is backtest overfitting: try enough parameter combinations and a great-looking backtest is almost guaranteed — and under memory effects it produces negative out-of-sample returns, not zero. Report how many configurations you tried, hold out data, and walk-forward.',
    links: [
      { url: 'https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659', label: 'Pseudo-Mathematics & Financial Charlatanism — backtest overfitting (Bailey, Borwein, López de Prado, Zhu · AMS 2014)' },
      { url: 'https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf', label: 'The Probability of Backtest Overfitting (PDF)' },
    ],
    searchQuery: 'backtesting methodology walk-forward out-of-sample overfitting',
  },
];

const LS_KEY = 'learning-path-progress';

type Progress = Record<string, boolean>;

function loadProgress(): Progress {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? (JSON.parse(raw) as Progress) : {};
  } catch {
    return {};
  }
}

function YouTubeEmbed({ videoId, title }: { videoId: string; title: string }) {
  return (
    <div className="lp-embed">
      <iframe
        src={`https://www.youtube.com/embed/${videoId}`}
        title={title}
        loading="lazy"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      />
    </div>
  );
}

function FrameEmbed({ url, title }: { url: string; title: string }) {
  return (
    <div className="lp-embed lp-embed--doc">
      <iframe src={url} title={title} loading="lazy" />
    </div>
  );
}

function PrereqCard({
  p,
  done,
  onToggle,
}: {
  p: Prereq;
  done: boolean;
  onToggle: (id: string) => void;
}) {
  return (
    <article className={`lp-source lp-prereq${done ? ' lp-source--done' : ''}`}>
      <div className="lp-source__head">
        <span className="lp-source__num lp-prereq__badge mono">{p.badge}</span>
        <div className="lp-source__title">{p.title}</div>
        <label className="lp-source__check" title="Mark complete">
          <input type="checkbox" checked={done} onChange={() => onToggle(p.id)} />
          <span>{done ? 'Done' : 'Mark complete'}</span>
        </label>
      </div>

      <p className="lp-source__note">{p.blurb}</p>

      {p.formula && <pre className="lp-formula mono">{p.formula}</pre>}

      {p.videoId && <YouTubeEmbed videoId={p.videoId} title={p.title} />}

      <div className="lp-linkrow">
        {p.links.map((l) => (
          <a key={l.url} className="lp-btn lp-btn--ghost" href={l.url} target="_blank" rel="noreferrer noopener">
            {l.label} ↗
          </a>
        ))}
        {p.searchQuery && (
          <a
            className="lp-btn lp-btn--ghost"
            href={`https://www.youtube.com/results?search_query=${encodeURIComponent(p.searchQuery)}`}
            target="_blank"
            rel="noreferrer noopener"
          >
            Search this on YouTube ↗
          </a>
        )}
      </div>
    </article>
  );
}

function SourceCard({
  s,
  done,
  onToggle,
}: {
  s: Source;
  done: boolean;
  onToggle: (n: number) => void;
}) {
  return (
    <article className={`lp-source${done ? ' lp-source--done' : ''}`}>
      <div className="lp-source__head">
        <span className="lp-source__num mono">{s.n}</span>
        <div className="lp-source__title">{s.title}</div>
        <label className="lp-source__check" title="Mark complete">
          <input type="checkbox" checked={done} onChange={() => onToggle(s.n)} />
          <span>{done ? 'Done' : 'Mark complete'}</span>
        </label>
      </div>

      {s.note && <p className="lp-source__note">{s.note}</p>}

      {s.kind === 'youtube' && <YouTubeEmbed videoId={s.videoId} title={s.title} />}

      {s.kind === 'link' && (
        <>
          {s.embedUrl && <FrameEmbed url={s.embedUrl} title={s.title} />}
          <a className="lp-btn" href={s.url} target="_blank" rel="noreferrer noopener">
            {s.label} ↗
          </a>
        </>
      )}

      {s.kind === 'youtube-search' && (
        <a
          className="lp-btn lp-btn--ghost"
          href={`https://www.youtube.com/results?search_query=${encodeURIComponent(s.query)}`}
          target="_blank"
          rel="noreferrer noopener"
        >
          Search this on YouTube ↗
        </a>
      )}

      {s.kind === 'reference' && (
        <div className="lp-ref">
          <span className="lp-ref__tag">{s.refNote}</span>
          {s.url && s.label && (
            <a className="lp-btn lp-btn--ghost" href={s.url} target="_blank" rel="noreferrer noopener">
              {s.label} ↗
            </a>
          )}
        </div>
      )}
    </article>
  );
}

export default function LearningPathPage() {
  const [progress, setProgress] = useState<Progress>({});

  useEffect(() => {
    setProgress(loadProgress());
  }, []);

  const toggle = useCallback((key: string | number) => {
    setProgress((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      try {
        localStorage.setItem(LS_KEY, JSON.stringify(next));
      } catch {
        /* private mode / quota — non-fatal, progress just won't persist */
      }
      return next;
    });
  }, []);

  const total = PREREQS.length + PHASES.reduce((a, p) => a + p.sources.length, 0);
  const doneCount = Object.values(progress).filter(Boolean).length;

  return (
    <div className="lp-page">
      <PageStyles />

      <div className="lp-title">
        <div className="eyebrow">Personal study</div>
        <h1 className="display lp-h1">Ajay&rsquo;s Learning Path</h1>
        <p className="lede">
          This makes it much clearer &mdash; your notebook already covers all three pillars.
          Here&rsquo;s your exact source list mapped into a study order, plus the gaps worth filling.
        </p>
        <div className="lp-progress">
          <div className="lp-progress__bar">
            <span style={{ width: total ? `${(doneCount / total) * 100}%` : 0 }} />
          </div>
          <span className="lp-progress__label mono">
            {doneCount}/{total} complete
          </span>
        </div>
      </div>

      <section className="lp-phase lp-prereqs">
        <div className="lp-phase__head">
          <span className="lp-phase__week lp-prereqs__week mono">Prerequisites</span>
          <h2 className="lp-phase__heading">Foundations to have before Week 1</h2>
        </div>
        <p className="lp-prose lp-prereqs__intro">
          These fill the three gaps flagged at the bottom of the plan &mdash; the study order
          quietly assumes them. Get comfortable here first, then start the phases.
        </p>
        <div className="lp-phase__sources">
          {PREREQS.map((p) => (
            <PrereqCard key={p.id} p={p} done={!!progress[p.id]} onToggle={toggle} />
          ))}
        </div>
      </section>

      {PHASES.map((phase) => (
        <section key={phase.id} className="lp-phase">
          <div className="lp-phase__head">
            <span className="lp-phase__week mono">{phase.week}</span>
            <h2 className="lp-phase__heading">{phase.heading}</h2>
          </div>
          <div className="lp-phase__sources">
            {phase.sources.map((s) => (
              <div key={s.n}>
                <SourceCard s={s} done={!!progress[s.n]} onToggle={toggle} />
                {s.n === 4 && <p className="lp-prose">{ARXIV_PARAGRAPH}</p>}
              </div>
            ))}
          </div>
        </section>
      ))}

      <section className="lp-gaps">
        <h2 className="lp-gaps__heading">Gaps in your notebook worth adding as sources</h2>
        <p className="lp-prose">
          Gaps in your notebook worth adding as sources: something on{' '}
          <strong>market structure basics</strong> (BOS/CHoCH &mdash; the SMC videos assume it),{' '}
          <strong>risk management/position sizing</strong> (nothing in your list covers it, and
          it&rsquo;s what actually determines survival), and a <strong>backtesting methodology</strong>{' '}
          source so &ldquo;deterministic&rdquo; means statistically validated, not just rule-based.
        </p>
      </section>

      <aside className="lp-tip">
        <span className="lp-tip__mark">Tip</span>
        <p>
          A nice NotebookLM trick: once you&rsquo;ve studied in this order, ask it to generate
          quizzes per phase &mdash; recall testing beats re-watching.
        </p>
      </aside>
    </div>
  );
}

/* Scoped styles — kept in-component (like several other pages) so the page is
   self-contained. All colors come from the design tokens so light/dark just
   work. */
function PageStyles() {
  return (
    <style>{`
      .lp-page { max-width: 860px; margin: 0 auto; padding: 0 0 var(--s-9); }
      .lp-title { padding: var(--s-6) 0 var(--s-5); }
      .lp-h1 { margin: var(--s-2) 0 var(--s-3); }
      .lp-title .lede { max-width: var(--content-prose); }

      .lp-progress { display: flex; align-items: center; gap: var(--s-3); margin-top: var(--s-5); }
      .lp-progress__bar { flex: 1; height: 6px; background: var(--bg-sunken); border-radius: var(--r-2); overflow: hidden; }
      .lp-progress__bar > span { display: block; height: 100%; background: var(--gold); transition: width var(--dur-med) var(--ease-soft); }
      .lp-progress__label { font-size: var(--fs-small); color: var(--ink-subtle); white-space: nowrap; }

      .lp-phase { margin-top: var(--s-7); }
      .lp-phase__head { display: flex; align-items: baseline; gap: var(--s-3); flex-wrap: wrap;
        padding-bottom: var(--s-3); border-bottom: 1px solid var(--gold-hairline); margin-bottom: var(--s-4); }
      .lp-phase__week { font-size: var(--fs-eyebrow); letter-spacing: var(--tracking-eyebrow); text-transform: uppercase;
        color: var(--gold-strong); background: var(--gold-faint); padding: 3px 8px; border-radius: var(--r-2); }
      .lp-phase__heading { font-size: var(--fs-h3); font-weight: 600; color: var(--ink); margin: 0; }

      .lp-phase__sources { display: flex; flex-direction: column; gap: var(--s-4); }

      .lp-source { background: var(--bg-surface); border: 1px solid var(--hairline); border-radius: var(--r-2);
        padding: var(--s-4); transition: border-color var(--dur-fast) var(--ease-soft); }
      .lp-source--done { opacity: 0.66; }
      .lp-source--done .lp-source__title { text-decoration: line-through; text-decoration-color: var(--gold-hairline); }

      .lp-source__head { display: flex; align-items: center; gap: var(--s-3); }
      .lp-source__num { flex: none; width: 28px; height: 28px; display: grid; place-items: center;
        font-size: var(--fs-small); font-weight: 600; color: var(--gold-strong);
        border: 1px solid var(--gold-hairline); border-radius: 999px; }
      .lp-source__title { flex: 1; font-size: var(--fs-h4); font-weight: 600; color: var(--ink); line-height: var(--lh-snug); }
      .lp-source__check { flex: none; display: inline-flex; align-items: center; gap: 6px; cursor: pointer;
        font-size: var(--fs-small); color: var(--ink-subtle); user-select: none; }
      .lp-source__check input { accent-color: var(--gold); width: 15px; height: 15px; cursor: pointer; }

      .lp-source__note { margin: var(--s-3) 0 0; padding-left: calc(28px + var(--s-3)); font-size: var(--fs-body);
        color: var(--ink-muted); line-height: var(--lh-normal); }

      .lp-embed { position: relative; margin-top: var(--s-4); aspect-ratio: 16 / 9; width: 100%;
        background: var(--bg-sunken); border-radius: var(--r-2); overflow: hidden; }
      .lp-embed iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
      .lp-embed--doc { aspect-ratio: 4 / 3; }

      .lp-btn { display: inline-flex; align-items: center; gap: 6px; margin-top: var(--s-4);
        padding: 8px 14px; font-size: var(--fs-small); font-weight: 600; text-decoration: none;
        color: var(--bg); background: var(--gold); border-radius: var(--r-2);
        transition: background var(--dur-fast) var(--ease-soft); }
      .lp-btn:hover { background: var(--gold-strong); }
      .lp-btn--ghost { color: var(--gold-strong); background: transparent; border: 1px solid var(--gold-hairline); }
      .lp-btn--ghost:hover { background: var(--gold-faint); }

      .lp-ref { display: flex; align-items: center; gap: var(--s-4); flex-wrap: wrap; margin-top: var(--s-4); }
      .lp-ref__tag { font-size: var(--fs-small); color: var(--ink-subtle); background: var(--bg-sunken);
        border: 1px dashed var(--hairline-strong); border-radius: var(--r-2); padding: 6px 10px; }
      .lp-ref .lp-btn { margin-top: 0; }

      .lp-prose { max-width: var(--content-prose); margin: var(--s-4) 0 0; font-size: var(--fs-body);
        color: var(--ink-muted); line-height: var(--lh-loose); }

      .lp-gaps { margin-top: var(--s-8); padding-top: var(--s-5); border-top: 1px solid var(--hairline); }
      .lp-gaps__heading { font-size: var(--fs-h3); font-weight: 600; color: var(--ink); margin: 0; }

      .lp-tip { display: flex; gap: var(--s-4); align-items: flex-start; margin-top: var(--s-6);
        padding: var(--s-4) var(--s-5); background: var(--gold-faint); border: 1px solid var(--gold-hairline);
        border-radius: var(--r-2); }
      .lp-tip__mark { flex: none; font-size: var(--fs-eyebrow); letter-spacing: var(--tracking-eyebrow);
        text-transform: uppercase; font-weight: 700; color: var(--gold-strong); padding-top: 3px; }
      .lp-tip p { margin: 0; font-size: var(--fs-body); color: var(--ink-muted); line-height: var(--lh-normal); }

      /* Prerequisites — visually marked as foundations (tinted, gold rail). */
      .lp-prereqs { margin-top: var(--s-6); }
      .lp-prereqs__week { color: var(--bg); background: var(--gold); }
      .lp-prereqs__intro { margin-top: 0; margin-bottom: var(--s-4); }
      .lp-prereq { border-left: 3px solid var(--gold); }
      .lp-prereq__badge { color: var(--bg); background: var(--gold); border-color: var(--gold); }

      .lp-formula { margin: var(--s-4) 0 0; padding: var(--s-3) var(--s-4); white-space: pre-wrap;
        font-size: var(--fs-small); line-height: var(--lh-normal); color: var(--ink);
        background: var(--bg-sunken); border: 1px solid var(--hairline); border-radius: var(--r-2); overflow-x: auto; }

      .lp-linkrow { display: flex; flex-direction: column; align-items: flex-start; gap: var(--s-3); margin-top: var(--s-4); }
      .lp-linkrow .lp-btn { margin-top: 0; }

      @media (max-width: 640px) {
        .lp-source__note { padding-left: 0; }
        .lp-source__check span { display: none; }
      }
    `}</style>
  );
}
