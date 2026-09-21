"""Energy + nuclear roster additions (2026-09-21).

Ajay: "can you add x energy and then other small energy companies in to our
list please".

XE is X-Energy Inc, which listed 2026-04-24 — the SMR/TRISO-fuel name. The
rest of the nuclear addition is the FUEL CYCLE behind the reactors already on
the roster; the energy addition is the small end of E&P, which the roster had
none of (every prior name is a major, a refiner or midstream).

Every added name was validated in the api container on 2026-09-21: it
resolves, it is not delisted, it carries a bar dated 2026-09-19 or later, and
its 50-day median dollar volume is recorded in
docs/sepa/energy_universe_2026_09_21.md. The NEGATIVE tests below are the
other half of that validation: the names that FAILED it must never drift in.
"""
from sepa.universe import (_EXPECTED_COUNTS, THEME_BY_TICKER, THEME_PRIORITY,
                           THEME_UNIVERSE)

ADDED_NUCLEAR = ("XE", "CCJ", "UEC", "DNN", "NXE", "URG", "EU", "LTBR", "ASPI")
ADDED_ENERGY = ("SM", "MGY", "CRGY", "GPOR", "NOG", "TALO", "REPX",
                "VTS", "EGY", "WTI", "REI")

# Failed validation 2026-09-21 — each for a DIFFERENT reason, so each is its
# own regression: a future sweep must not quietly re-add any of them.
DEAD_BARS = ("VTLE", "CIVI", "BRY")        # last bar months old (the MRO/HES/CTRA rule)
TOO_THIN = ("AMPY", "KGEI", "NPWR")        # under the boards' tradeable floor
NOT_AN_OPERATING_COMPANY = ("SRUUF",)      # Sprott physical uranium TRUST
NOT_ENERGY = ("PEN",)                      # Penumbra — a medical-device company


def test_xe_is_on_the_nuclear_roster_because_he_named_it():
    assert "XE" in THEME_UNIVERSE["nuclear"]
    assert THEME_BY_TICKER.get("XE") == "nuclear"


def test_the_fuel_cycle_names_tag_as_nuclear():
    for sym in ADDED_NUCLEAR:
        assert sym in THEME_UNIVERSE["nuclear"], sym
        assert THEME_BY_TICKER.get(sym) == "nuclear", sym


def test_the_small_energy_names_tag_as_energy():
    for sym in ADDED_ENERGY:
        assert sym in THEME_UNIVERSE["energy"], sym
        assert THEME_BY_TICKER.get(sym) == "energy", sym


def test_the_energy_roster_finally_has_a_small_end():
    """The point of the ask. Before this the smallest energy name was a
    multi-billion midstream; a small-cap energy move could not tag as energy."""
    assert len(THEME_UNIVERSE["energy"]) >= 30


def test_NEGATIVE_names_whose_price_history_is_dead_are_not_on_any_roster():
    every = {t for names in THEME_UNIVERSE.values() for t in names}
    for sym in DEAD_BARS:
        assert sym not in every, (
            f"{sym} has no recent bar — it would read as a flat 0% on every "
            "window, the same trap MRO / HES / CTRA are excluded for")


def test_NEGATIVE_names_under_the_tradeable_floor_are_not_on_any_roster():
    every = {t for names in THEME_UNIVERSE.values() for t in names}
    for sym in TOO_THIN:
        assert sym not in every, f"{sym} measured too thin on 2026-09-21"


def test_NEGATIVE_a_commodity_trust_is_not_an_energy_company():
    every = {t for names in THEME_UNIVERSE.values() for t in names}
    for sym in NOT_AN_OPERATING_COMPANY:
        assert sym not in every, f"{sym} is a physical trust, not an operator"


def test_NEGATIVE_a_ticker_that_merely_looks_energy_is_not_on_a_roster():
    """PEN reads like a uranium ticker and is Penumbra, a medical-device
    company. It was in the 2026-09-21 candidate sweep and validation caught
    it — the reason every candidate is checked by NAME, not by symbol."""
    every = {t for names in THEME_UNIVERSE.values() for t in names}
    for sym in NOT_ENERGY:
        assert sym not in every, f"{sym} is not an energy company"


def test_NEGATIVE_no_added_name_lands_in_two_rosters():
    """THEME_BY_TICKER is last-wins, so a duplicate silently retags a name and
    changes its sort priority. UUUU is the live temptation here: it is a
    uranium producer AND a rare-earth producer, and it stays in rare_earth."""
    names = [t for v in THEME_UNIVERSE.values() for t in v]
    assert len(names) == len(set(names)), \
        [t for t in set(names) if names.count(t) > 1]
    assert THEME_BY_TICKER.get("UUUU") == "rare_earth"


def test_the_theme_count_bound_still_covers_the_roster():
    names = {t for v in THEME_UNIVERSE.values() for t in v}
    lo, hi = _EXPECTED_COUNTS["themes"]
    assert lo <= len(names) <= hi, (len(names), lo, hi)


def test_both_rosters_keep_their_sort_priority():
    """Adding names must not reorder the themes he reads."""
    assert THEME_PRIORITY["nuclear"] == 5
    assert THEME_PRIORITY["energy"] == 6


# ---------------------------------------------------------------------------
# Critical minerals + Greenland (same day, same ask, same validation)
#
# Ajay: "Do we have critical minerals in our list?" then "Also greenland
# minerals or greenland related mineral companies".
# ---------------------------------------------------------------------------
ADDED_MINERALS = ("CRML", "ALB", "SQM", "LAC", "SGML", "ABAT", "FCX", "SCCO",
                  "TECK", "HBM", "ERO", "IE", "NAK", "PPTA", "UAMY", "TROX",
                  "IPX", "NB", "IDR")

# Greenland names with NO US listing in this app's price data (London/Toronto).
GREENLAND_UNPRICEABLE = ("AMRQ", "AMQ", "BLUJ", "EGDFF", "TANB")
MINERALS_DEAD_BARS = ("TMRC", "PLL", "LITM", "ARMN")
MINERALS_TOO_THIN = ("KRO", "USAU", "WWR", "GPHOF", "GLND")


def test_the_critical_minerals_roster_exists_and_is_ranked():
    assert "critical_minerals" in THEME_UNIVERSE
    assert THEME_PRIORITY["critical_minerals"] == 14
    # Directly behind rare_earth, the story it widens.
    assert THEME_PRIORITY["critical_minerals"] == THEME_PRIORITY["rare_earth"] + 1


def test_every_critical_mineral_name_tags_to_that_roster():
    for sym in ADDED_MINERALS:
        assert sym in THEME_UNIVERSE["critical_minerals"], sym
        assert THEME_BY_TICKER.get(sym) == "critical_minerals", sym


def test_CRML_is_the_greenland_name_and_it_is_tagged():
    """Critical Metals Corp — the Tanbreez rare-earth project. The only
    liquid US-listed Greenland name in this app's data on 2026-09-21."""
    assert THEME_BY_TICKER.get("CRML") == "critical_minerals"


def test_NEGATIVE_greenland_names_this_app_cannot_price_are_not_on_a_roster():
    every = {t for names in THEME_UNIVERSE.values() for t in names}
    for sym in GREENLAND_UNPRICEABLE:
        assert sym not in every, (
            f"{sym} returns no US bars — it lists in London or Toronto and "
            "every window would read as unknown")


def test_NEGATIVE_GLND_is_not_the_greenland_minerals_name():
    """Named 'Greenland Energy Co' and it is a $52M shell at ~$1M/day — under
    the tradeable floor, and an energy shell rather than a miner. The name
    looking right is exactly why candidates are validated, not assumed."""
    every = {t for names in THEME_UNIVERSE.values() for t in names}
    assert "GLND" not in every


def test_NEGATIVE_dead_or_thin_mineral_names_are_not_on_a_roster():
    every = {t for names in THEME_UNIVERSE.values() for t in names}
    for sym in MINERALS_DEAD_BARS + MINERALS_TOO_THIN:
        assert sym not in every, sym


def test_rare_earth_is_untouched_and_UUUU_stays_there():
    """The wider roster does not absorb the rare earths. UUUU is the live
    disjointness temptation: a uranium producer, a rare-earth producer AND
    the third name in the Greenland headline cohort on the POTUS tab."""
    assert THEME_UNIVERSE["rare_earth"] == ["MP", "USAR", "UUUU", "METC"]
    assert THEME_BY_TICKER.get("UUUU") == "rare_earth"


def test_the_themes_below_critical_minerals_shifted_by_exactly_one():
    """The file's own rule when a theme is inserted: everything below shifts
    one rank, relative order unchanged."""
    assert THEME_PRIORITY["infosec"] == 15
    assert THEME_PRIORITY["crypto"] == 16
    assert THEME_PRIORITY["biotech"] == 17
