"""The biotech / therapeutics theme.

Ajay 2026-09-14, with a watchlist screenshot of green biotech against a red
tape: *"Do we have any bio and theraputics stocks especially these a bunch of
them are gaining momentun in this down trend market whcih is mostly red"*.

We did not — every existing theme was AI, hardware, energy, defence, crypto or
infosec. These tests pin the roster, the exclusions, and the two mistakes this
kind of roster invites: keeping a delisted name because it still has years of
price history, and letting "healthcare-adjacent" drift in.
"""
from sepa.universe import THEME_UNIVERSE, THEME_PRIORITY, THEME_BY_TICKER

BIO = THEME_UNIVERSE["biotech"]


def test_the_theme_exists_and_is_not_thin():
    assert len(BIO) >= 25, "a therapeutics median needs a real roster behind it"
    assert len(BIO) == len(set(BIO)), "no duplicates"


def test_his_screenshot_names_that_are_actually_therapeutics_are_in():
    """He showed SMMT, IOVA, BNTX and MRNA moving. All four are drug
    developers and all four must be on the board he asked for."""
    for s in ("SMMT", "IOVA", "BNTX", "MRNA"):
        assert s in BIO, f"{s} was on his screen and is a therapeutics name"


def test_NEGATIVE_the_non_therapeutics_from_his_screenshot_stay_out():
    """The line is "does its value sit in a drug pipeline". Two names on his
    own screenshot do not clear it, and including them because they appeared
    next to biotech is exactly how a theme becomes meaningless."""
    assert "ACHC" not in BIO, "Acadia is behavioural-health FACILITIES, an operator"
    assert "EL" not in BIO, "Estee Lauder is cosmetics — not healthcare at all"


def test_NEGATIVE_diagnostics_and_tools_are_not_therapeutics():
    """They sell TO drug developers; they do not develop drugs. Their revenue
    behaves like an industrial supplier's, not like a pipeline's."""
    for s in ("NTRA", "VCYT", "TWST"):
        assert s not in BIO, f"{s} is diagnostics/tools, not therapeutics"


def test_NEGATIVE_the_delisted_candidates_never_come_back():
    """THE INFOSEC LESSON, same week. Each of these carries YEARS of cached
    price history and would pass any bar-count check — and each stopped
    trading. Membership is validated by LAST BAR DATE.

    A dead name in a rotation roster is worse than an absent one: it reads
    flat forever and silently drags the theme's median toward zero.
    """
    dead = {
        "APLS": "2026-05-13", "CRNX": "2026-08-31", "FOLD": "2026-04-24",
        "SAVA": "2026-03-10", "DVAX": "2026-02-09", "BPMC": "2025-07-17",
        "SWTX": "2025-06-30", "ITCI": "2025-04-01", "BGNE": "2024-12-31",
    }
    for s, last_bar in dead.items():
        assert s not in BIO, f"{s} last traded {last_bar} — validated by DATE, not bar count"


def test_NEGATIVE_a_name_too_thin_to_move_a_median_stays_out():
    """GANX is genuinely a therapeutics company and was on his screen, but it
    trades ~$1M/day. One print would swing the theme's median."""
    assert "GANX" not in BIO


def test_priority_ranks_biotech_below_every_ai_theme():
    """His standing rule: AI-ecosystem winners lead any list. Biotech is the
    one theme here with no AI story at all, so it must not outrank them."""
    assert THEME_PRIORITY["biotech"] == 15
    for ai in ("ai_semis", "ai_power", "ai_infra", "semi_materials",
               "optical", "datacenter_build", "nuclear", "infosec"):
        assert THEME_PRIORITY[ai] < THEME_PRIORITY["biotech"], (
            f"{ai} must rank ahead of biotech"
        )


def test_biotech_names_are_not_claimed_by_another_theme():
    """A name in two rosters gets counted in two medians and tagged by
    whichever priority wins — silently changing both boards."""
    for s in BIO:
        owners = [t for t, names in THEME_UNIVERSE.items() if s in names]
        assert owners == ["biotech"], f"{s} is also in {[o for o in owners if o != 'biotech']}"


def test_every_biotech_name_resolves_to_the_theme_tag():
    for s in ("SMMT", "IOVA", "MRNA", "LQDA", "PTGX", "RARE"):
        assert THEME_BY_TICKER.get(s) == "biotech"
