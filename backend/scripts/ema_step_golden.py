"""👀 Gajjala's Watch LIVE — the EMA step golden (2026-11-16, spec ggw_live §3.3, critique C3).

Ajay 2026-11-16, verbatim: "Can you make the watch list charts live please" · "Realtime updates.. Like the 1 min chart I
need it to be live live.. per sec change".

READ-ONLY and deterministic. Writes ONE fixture (`--out`) that the backend test and the FE `ggwEma.test.ts` read: for
spans 9 and 21, `N` closes and the 9 / 21 EMA of the ONE engine (`orderflow.signals.ema` = pandas
`ewm(span, adjust=False).mean()`) at full precision.

The series is built SEQUENTIALLY: ordinary rows are a random walk inside [PRICE_MIN, PRICE_MAX] rounded to 4 dp; at
`EQUAL_ROWS` chosen indices `i` (never 0) the close is set to `ema(closes[:i]).iloc[-1]` from the SAME engine on the
PREFIX — exempt from the 4-dp rounding — so `closes[i] == ema[i-1]` holds bit-exactly (the adjust=False recursion is
causal; the generator asserts prefix == full instead of assuming it). Seeds are tried from `--seed` (at most
`--max-seeds`) until, for BOTH spans: n_equal ≥ EQUAL_ROWS, n_unguarded_differs ≥ 1 (the plain step WITHOUT pandas'
equal-value guard differs from `ema[i]` at raw precision on an equal row — the guard is load-bearing) and
n_alpha2_fails ≥ 1 (the step with α = 2/span fails the 6-dp equality — the wrong α is caught). No seed → exit 2.

`--check` recomputes the EMA from the committed closes (bit-exact) AND the three counts (equal to the committed ones);
a pandas kernel change fails here first. Exit 1 on any mismatch.

    python scripts/ema_step_golden.py --out tests/fixtures/gajjala/ema_step_golden_2026_11_16.json
    python scripts/ema_step_golden.py --check --fixture tests/fixtures/gajjala/ema_step_golden_2026_11_16.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from chart_maps.gajjala import constants as GC  # noqa: E402
from orderflow.signals import ema  # noqa: E402

GENERATED_BY = "backend/scripts/ema_step_golden.py"
SPANS = (GC.EMA_FAST, GC.EMA_SLOW)                     # the watch's 9 / 21 EMA (constants by name)
N_DEFAULT = 300
EQUAL_ROWS = 10                                        # spec §3.3: ≥ 10 equal rows per span
PRICE_MIN, PRICE_MAX = 0.01, 500.0                     # spec §3.3: a random walk in 0.01–500
CLOSE_DP = 4                                           # ordinary closes rounded to 4 dp
DISPLAY_DP = 6                                         # = bars._masked_ema's round(·, 6)
DEFAULT_FIXTURE = (Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "gajjala"
                   / "ema_step_golden_2026_11_16.json")


# ── the step (re-typed from spec §3.4 ggwEmaStep — the FE's formula) ──────────────────────────────────────────────
def alpha(span: int) -> float:
    """pandas' com → alpha for `span`: 1 / (1 + (span − 1) / 2)."""
    return 1.0 / (1.0 + (span - 1) / 2.0)


def step(prev: float, close: float, a: float, guard: bool = True) -> float:
    """pandas adjust=False, normalized: ((1−α)·prev + α·close) / ((1−α) + α); `guard` = pandas' equal-value guard."""
    if guard and prev == close:
        return prev
    return ((1.0 - a) * prev + a * close) / ((1.0 - a) + a)


def ema_list(closes, span: int) -> list:
    return [float(x) for x in ema(pd.Series(closes, dtype=float), span).tolist()]


# ── the counts ────────────────────────────────────────────────────────────────────────────────────────────────────
def counts(closes, ema_vals, span: int) -> dict:
    a = alpha(span)
    a2 = 2.0 / span
    n_equal = n_unguarded = n_a2 = 0
    for i in range(1, len(closes)):
        prev, c, e = ema_vals[i - 1], closes[i], ema_vals[i]
        if c == prev:
            n_equal += 1
            if step(prev, c, a, guard=False) != e:
                n_unguarded += 1
        if round(step(prev, c, a2), DISPLAY_DP) != round(e, DISPLAY_DP):
            n_a2 += 1
    return {"n_equal": n_equal, "n_unguarded_differs": n_unguarded, "n_alpha2_fails": n_a2}


def counts_hold(cnt: dict) -> bool:
    return cnt["n_equal"] >= EQUAL_ROWS and cnt["n_unguarded_differs"] >= 1 and cnt["n_alpha2_fails"] >= 1


# ── the series ────────────────────────────────────────────────────────────────────────────────────────────────────
def series(rng: random.Random, span: int, n: int) -> tuple:
    """(closes, equal indices): a 4-dp random walk + EQUAL_ROWS rows set to the prefix EMA (unrounded). ([], set())
    when `n` is too short to hold EQUAL_ROWS equal rows (never i = 0)."""
    if n - 1 < EQUAL_ROWS:
        return [], set()
    eq = set(rng.sample(range(1, n), EQUAL_ROWS))
    p = rng.uniform(1.0, 100.0)
    out: list = []
    for i in range(n):
        if i in eq:
            out.append(float(ema(pd.Series(out, dtype=float), span).iloc[-1]))
            continue
        p = min(PRICE_MAX, max(PRICE_MIN, p * (1.0 + rng.gauss(0.0, 0.01))))
        out.append(round(p, CLOSE_DP))
    return out, eq


def build(seed: int, n: int) -> "dict | None":
    rng = random.Random(seed)
    spans: dict = {}
    for span in SPANS:
        closes, eq = series(rng, span, n)
        if not closes:
            return None
        vals = ema_list(closes, span)
        drift = sorted(i for i in eq if closes[i] != vals[i - 1])   # prefix == full, asserted (never assumed)
        if drift:
            raise AssertionError(f"span {span}: prefix EMA != full-series EMA at rows {drift}")
        cnt = counts(closes, vals, span)
        if not counts_hold(cnt):
            return None
        spans[str(span)] = {"closes": closes, "ema": vals, **cnt}
    return {"generated_by": GENERATED_BY, "pandas": pd.__version__, "seed": seed, "spans": spans}


def generate(seed: int, max_seeds: int, n: int) -> "dict | None":
    for s in range(seed, seed + max(0, int(max_seeds))):
        fx = build(s, n)
        if fx is not None:
            return fx
    return None


def check(fx: dict) -> list:
    """Every mismatch between the committed fixture and a recompute (empty = reproduced bit-exactly)."""
    bad: list = []
    spans = fx.get("spans") if isinstance(fx, dict) else None
    if not isinstance(spans, dict) or set(spans) != {str(s) for s in SPANS}:
        return [f"spans {sorted(spans) if isinstance(spans, dict) else spans!r} != {[str(s) for s in SPANS]}"]
    for key, blk in spans.items():
        span = int(key)
        closes, committed = blk.get("closes"), blk.get("ema")
        vals = ema_list(closes, span)
        if vals != committed:
            n_diff = sum(1 for x, y in zip(vals, committed or []) if x != y)
            bad.append(f"span {key}: ema differs on {n_diff} row(s)")
        cnt = counts(closes, committed if isinstance(committed, list) else vals, span)
        for k, v in cnt.items():
            if blk.get(k) != v:
                bad.append(f"span {key}: {k} recomputed {v} != committed {blk.get(k)}")
        if not counts_hold(cnt):
            bad.append(f"span {key}: counts {cnt} below {EQUAL_ROWS}+/1+/1+")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-seeds", type=int, default=1000)
    ap.add_argument("--n", type=int, default=N_DEFAULT)
    ap.add_argument("--out", type=Path, default=None, help="write the fixture here (default: print to stdout)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    args = ap.parse_args(argv)
    if args.check:
        fx = json.loads(args.fixture.read_text(encoding="utf-8"))
        bad = check(fx)
        if bad:
            for b in bad:
                print(b, file=sys.stderr)
            return 1
        print(f"fixture reproduced bit-exactly (counts {EQUAL_ROWS}+/1+/1+ per span)")
        return 0
    fx = generate(args.seed, args.max_seeds, args.n)
    if fx is None:
        print(f"no seed in [{args.seed}, {args.seed + args.max_seeds}) holds the counts "
              f"({EQUAL_ROWS}+ equal / 1+ unguarded differs / 1+ alpha 2/span fails) at N={args.n}", file=sys.stderr)
        return 2
    text = json.dumps(fx, indent=None, separators=(",", ":")) + "\n"
    if args.out is None:
        sys.stdout.write(text)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"seed {fx['seed']} → {args.out}: " + ", ".join(
            f"span {k} {b['n_equal']}/{b['n_unguarded_differs']}/{b['n_alpha2_fails']}" for k, b in fx["spans"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
