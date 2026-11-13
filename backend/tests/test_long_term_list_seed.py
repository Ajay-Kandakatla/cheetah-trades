"""📅 Long Term (2026-11-12) — his saved list, byte-identical, strict JSON, read-only."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from long_term_list import constants as C
from long_term_list import seed as SD

PKG = Path(SD.__file__).parent


def test_seed_sha_is_pinned():
    assert hashlib.sha256(C.SEED_FILE.read_bytes()).hexdigest() == C.SEED_SHA256
    assert C.SEED_SHA256.startswith("74ecc4e3")


def test_counts_9_categories_109_unique_74_screened():
    s = SD.load()
    assert len(SD.categories(s)) == 9
    assert len(SD.unique_names(s)) == 109
    assert len(SD.screened_names(s)) == 74
    assert len(SD.pankaj_entries(s)) == 40


def test_chips_multi_category_names():
    ch = SD.chips(SD.load())
    assert ch["XNCR"] == ["bonde", "hot"]
    assert ch["ANET"] == ["capital_quality", "bonde", "pankaj"]
    assert ch["NVDA"] == ["quiet_strong", "pankaj"]
    assert ch["FIGS"] == ["s2_growth", "hot"]
    assert ch["LUNR"] == ["fallen_growers", "accel_after_fall"]


def test_quiet_strong_names_after_the_critique():
    assert SD.category_names(SD.load(), "quiet_strong") == [
        "HLNE", "NVDA", "META", "GOOGL", "NXT", "MPWR", "XPEL", "EPRT", "MGY", "CTRE"]


def test_name_symbol_dict_and_string():
    assert SD.name_symbol("amd") == "AMD"
    ent = {"sym": "BRK-B", "sheet_symbol": "BRK.B", "tier": "A"}
    assert SD.name_symbol(ent) == "BRK-B"
    pk = SD.pankaj_entries(SD.load())
    assert pk["BRK-B"]["sheet_symbol"] == "BRK.B"
    assert pk["TSM"]["sheet_symbol"] == "TSM"
    assert pk["TSM"]["zones"]["Agg"] == (400.0, 410.0)
    assert pk["INTU"]["zones"]["C3"] == (None, None)


def test_zone_order():
    assert SD.zone_order(SD.load()) == ("Agg", "C1", "C2", "C3")


def _temp_copy(tmp_path, mutate=None, text=None):
    data = json.loads(C.SEED_FILE.read_text(encoding="utf-8"))
    if mutate:
        mutate(data)
    p = tmp_path / "seed.json"
    p.write_text(text if text is not None else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_negative_zone_key_set_mismatch_raises(tmp_path):
    def mut(d):
        pk = next(c for c in d["categories"] if c["key"] == "pankaj")
        pk["names"][3]["zones"] = {"Agg": [1, 2], "C1": [1, 2], "C2": [1, 2], "C9": [1, 2]}
    with pytest.raises(SD.SeedChanged):
        SD.load(_temp_copy(tmp_path, mut), sha=None)


def test_negative_nan_literal_raises_strict_parse(tmp_path):
    text = C.SEED_FILE.read_text(encoding="utf-8").replace("\n       null,", "\n       NaN,", 1)
    assert "NaN" in text
    with pytest.raises(SD.SeedChanged, match="strict JSON"):
        SD.load(_temp_copy(tmp_path, text=text), sha=None)


def test_negative_unknown_category_key_raises(tmp_path):
    def mut(d):
        d["categories"].append({"key": "tenth_list", "label": "x", "names": ["AAA"]})
    with pytest.raises(SD.SeedChanged, match="tenth_list"):
        SD.load(_temp_copy(tmp_path, mut), sha=None)


def test_negative_sha_mismatch_raises(tmp_path):
    with pytest.raises(SD.SeedChanged, match="sha256"):
        SD.load(_temp_copy(tmp_path))      # re-serialized -> different bytes


def test_negative_pankaj_entries_carry_no_action():
    for ent in SD.pankaj_entries(SD.load()).values():
        assert "action" not in ent
        assert set(ent) == {"sym", "sheet_symbol", "tier", "zt", "zones"}


def test_negative_package_never_opens_the_seed_for_writing():
    write = re.compile(r"open\([^)]*['\"](w|a|r\+|wb|ab|x)['\"]|write_text|write_bytes|json\.dump\(|\.unlink\(")
    assert not write.search((PKG / "seed.py").read_text(encoding="utf-8"))
    for f in PKG.glob("*.py"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if "SEED_FILE" in line or "seed_2026_11_12" in line:
                assert not write.search(line), (f.name, line)


def test_his_words_verbatim():
    s = SD.load()
    words = SD.his_words(s)
    assert words[0] == s["source"]
    assert any(w.startswith("Yeah I wanna find out the ones that are actually great") for w in words)
    assert len(words) == 4


def test_load_baseline_missing_never_raises(tmp_path):
    out = SD.load_baseline(tmp_path / "nope.json")
    assert out == {"reason": "no baseline file"}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert "reason" in SD.load_baseline(bad)
