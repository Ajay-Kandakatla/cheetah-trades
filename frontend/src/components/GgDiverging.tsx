/* GgDiverging — 🌱 the Diverging forming-read sub on 🚩 Gajjala's 5-min tab (2026-11-18, diverging spec §3.9).
 *
 * Ajay 2026-11-18: "For the divergence thing create a separate tab that are potentially diverging with uptrend and volume
 * breakout." · "Are you building that now?"
 *
 * GgDivergingPanel — above the cards, drawn from the SERVED block only (diverging_tab.block) on the generic gg-dv* classes:
 * the served title, his words, his two picks, the cohort / window / bars / order lines, the empty line, the listings that
 * drew no card, the served fault line, the served rule folded, the served honesty LAST. The listed names are ordinary served
 * tiles (the house card grid). A forming read, never an entry: no alert, no gate, no record, no trade. UNMEASURED.
 * This file types no word and no number except the ⓘ fallback summary; every string passes the servedText guard (a NaN /
 * undefined / number / empty string prints nothing). */
import { Link } from 'react-router-dom';
import { ggHref, type GgDivergingBlock } from '../lib/gajjala';
import '../styles/gajjala.css';

/** The board's servedText guard (GajjalaBoard keeps its trailing export line fixed — copied, as GgDivergence does): a served
 *  line prints only when it is a non-empty string — NaN / undefined / null / a number prints nothing. */
function servedText(v: unknown): v is string {
  return typeof v === 'string' && v.trim() !== '';
}

/** 🌱 the panel above the cards. A null / absent block (an older API, or a read fault — the board's served empty note says
 *  so) draws nothing. */
export function GgDivergingPanel({ block }: { block: GgDivergingBlock | null | undefined }) {
  if (!block || typeof block !== 'object') return null;
  const picks = (Array.isArray(block.pick_texts) ? block.pick_texts : []).filter(servedText);
  const chartless = (Array.isArray(block.chartless) ? block.chartless : [])
    .filter((c) => !!c && typeof c === 'object' && servedText(c.state_label));
  const showEmpty = block.n === 0 && !chartless.length && servedText(block.empty_text);
  return (
    <section className="gg-dv" data-testid="gg-dg">
      {servedText(block.title) ? <h3 className="gg-dv-title" data-testid="gg-dg-title">{block.title}</h3> : null}
      {servedText(block.ask_text) ? (
        <blockquote className="gg-dv-ask gg-muted" data-testid="gg-dg-ask">{block.ask_text}</blockquote>
      ) : null}
      {picks.map((p, i) => (
        <blockquote key={`pick-${i}`} className="gg-dv-ask gg-muted" data-testid={`gg-dg-pick-${i}`}>{p}</blockquote>
      ))}
      {servedText(block.cohort_text) ? <p className="gg-dv-line gg-muted" data-testid="gg-dg-cohort">{block.cohort_text}</p> : null}
      {servedText(block.window_text) ? <p className="gg-dv-line gg-muted" data-testid="gg-dg-window">{block.window_text}</p> : null}
      {servedText(block.bars_text) ? <p className="gg-dv-line gg-muted" data-testid="gg-dg-bars">{block.bars_text}</p> : null}
      {servedText(block.order_note) ? <p className="gg-dv-line gg-muted" data-testid="gg-dg-order">{block.order_note}</p> : null}
      {showEmpty ? <p className="gg-dv-line" data-testid="gg-dg-empty">{block.empty_text}</p> : null}
      {chartless.map((c, i) => {
        const href = ggHref(c.href);
        const key = servedText(c.symbol) ? c.symbol : String(i);
        return (
          <p key={`${key}-${i}`} className="gg-dv-line gg-dv-chartless" data-testid={`gg-dg-chartless-${key}`}>
            {href ? <Link to={href}>{c.state_label}</Link> : c.state_label}
          </p>
        );
      })}
      {servedText(block.faults_text) ? <p className="gg-dv-line cm-note" data-testid="gg-dg-faults">{block.faults_text}</p> : null}
      {servedText(block.rule_text) ? (
        <details className="gg-dv-rule" data-testid="gg-dg-rule">
          <summary>{servedText(block.rule_label) ? block.rule_label : 'ⓘ'}</summary>
          <p className="gg-dv-line">{block.rule_text}</p>
        </details>
      ) : null}
      {servedText(block.honesty) ? <p className="gg-dv-line gg-muted" data-testid="gg-dg-honesty">{block.honesty}</p> : null}
    </section>
  );
}
