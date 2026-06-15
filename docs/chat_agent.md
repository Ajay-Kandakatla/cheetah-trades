# In-app chat — the portfolio-aware Minervini agent

_Added 2026-06-15. Ajay: "I do not want my chat to keep saying I cannot give
financial advice. I want it to act like my agent based on this app… always
remember my current portfolio# … answer based on Minervini."_

## What changed

The floating chat widget has two modes. Both were effectively **stateless about
positions** — a fresh blank-slate model each turn that didn't know what Ajay
held, and the regular mode carried a *hardcoded* "$40k cash at Fidelity" line
that went stale the moment he bought anything. The regular mode also tended to
hedge with "I'm not a financial advisor" boilerplate that's pure noise on his
own self-hosted tool.

Two fixes:

1. **Live portfolio memory (both modes).** Every turn now injects his real
   current holdings — positions, cost basis, live P/L, day move, and weight —
   into the model's context. He no longer has to re-state what he owns.
2. **Agent reframe (regular `/chat`).** The system prompt now frames the model
   as *his Minervini trading agent*, not a generic assistant or compliance bot:
   decisive, position-aware, book-grounded, and explicitly told **not** to add
   "not financial advice / consult a professional" disclaimers.

## How it works

| Piece | File | Role |
|-------|------|------|
| Snapshot builder | `backend/chat/portfolio_context.py` | `live_portfolio_block(email)` → compact text from `portfolio.api.build_summary` (quote-cached ~60s). **Soft-fails to `None`** on any error. |
| Agent persona | `backend/chat/prompt.py` | `SYSTEM_PROMPT_BASE` (agent framing) + `build_system_prompt(page_context, portfolio_block)` injects the snapshot right after the persona. |
| Regular endpoint | `backend/chat/api.py` `POST /chat` | Builds the block from the authenticated `email`, passes it to the prompt. |
| Brain endpoint | `backend/brain/api.py` `POST /brain/ask` | Also injects the block — **labelled app state, never a book source to cite.** The persona's grounding/citation contract is untouched. |

### Mode split — deliberate

- **Regular `/chat`** is the *agent*: applies Minervini's rules to his actual
  positions, gives a clear read + next action, no reflexive disclaimers. This is
  the default mode (`brainMode` defaults off).
- **Brain `/brain/ask`** (🧠 toggle) stays the strict **book-citation scholar**:
  answers only from retrieved Minervini passages, every claim cited, never
  invents numbers/pages. Those grounding rules are the product and are
  source-guard-locked in `tests/test_brain_contracts.py` — we did **not** weaken
  them. The portfolio block just lets it restate book rules *against his actual
  holdings* instead of generic examples.

## The line we hold

Disclaimer suppression is about **tone**, not substance. The agent still:

- applies a documented methodology (Minervini SEPA), not freelance hot takes;
- does **not invent** numbers, thresholds, or prices (Rule #1 spirit preserved);
- points to the app's deterministic engines (scanner, per-holding diagnosis,
  Auto-Pilot exit engine) for the exact mechanical sell tripwires.

It is a decision-support agent over his own data and his own chosen method — not
a substitute for his judgment, and it never moves money.

## Privacy / safety notes

- The snapshot is built from the **authenticated user's** email
  (`current_user_email`); a user only ever sees their own positions.
- `live_portfolio_block` never raises into a chat turn — a Mongo outage or quote
  failure just omits the block (positions simply aren't shown that turn).
- No portfolio data is logged in the snapshot path.

## Tests

- `backend/tests/test_chat_portfolio_context.py` — block formatting + the full
  soft-fail matrix (no holdings, db down, empty email, missing quote fields) +
  agent-framing / disclaimer-suppression guards on the persona.
- `backend/tests/test_brain_ask.py` — portfolio block reaches the brain prompt,
  labelled non-book; omitted when absent.

Run: `cd backend && .venv/bin/python -m pytest tests/test_chat_portfolio_context.py tests/test_brain_ask.py -q`
