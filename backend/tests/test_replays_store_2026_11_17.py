"""🎬 Replays — the listing engine (replays spec §3.1 / §4 WP-BE, 2026-11-17).

Ajay 2026-11-17, verbatim: "Can you store the videos in to the app please". His 11-16 rule: "I only wanna see ones
from 4 AM to 8 pm please" → only `window == "04:00-20:00 ET"` sidecars are listed.

The fixtures mirror the real host folder (spec §1.1) key-for-key: the carried CENN A+ winner, a GP 🎾 potential with
its `rs` list + `potential`, the AMST biggest mover, an AIMD 👀 Watch reel, a same-day AKAN A+ winner and a same-day
A+ loser ("L −1R" with U+2212). NEGATIVES: 16:00 windows, missing window, sidecar-less mp4s, `.part.mp4` renders,
non-dict json, file ≠ stem, malformed cards (C9), traversal / symlink / unlisted files, malformed CSV.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
from pathlib import Path

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import constants as WC
from chart_maps.replays import constants as C
from chart_maps.replays import store as ST

DAY = "2026-11-17"
PREV = "2026-11-16"
BACKEND = Path(__file__).resolve().parents[1]
PKG = BACKEND / "chart_maps" / "replays"


def _strict(txt):
    def _refuse(tok):
        raise ValueError(f"non-JSON constant {tok}")
    return json.loads(txt, parse_constant=_refuse)


def _base(file, ring_id, symbol, setup, page, why, grade, move_pct, window=C.FULL_DAY_WINDOW, speed=24.0,
          minutes=40.05):
    return {"file": file, "ring_id": ring_id, "symbol": symbol, "setup": setup, "page": page, "why": why,
            "grade": grade, "speed": speed, "fps": 10, "frames": 24030, "minutes": minutes,
            "source": "built from 1-second bars", "move_pct": move_pct, "move_base": "fill", "trig_pct": move_pct,
            "fill_px": 0.1477, "story": f"{symbol} story line.", "render_sec": 25.2, "no_risk": False,
            "window": window}


def cenn_carried():
    return _base("CENN_reversal_squeeze_24x.mp4", f"{PREV}|CENN|reversal_squeeze|aplus", "CENN", "reversal_squeeze",
                 "gajjala", ["5-min A+ winner · rang 2026-11-16 17:46 ET, after the close"], "W +1R", 26.8)


def akan_winner():
    return _base("AKAN_reversal_squeeze_1mpage_24x.mp4", f"{DAY}|AKAN|reversal_squeeze|aplus", "AKAN",
                 "reversal_squeeze", "gajjala_1m", ["1-min A+ winner"], "W +1R", 18.1)


def gdhg_winner():
    return _base("GDHG_kiss_fly_1mpage_24x.mp4", f"{DAY}|GDHG|kiss_fly|aplus", "GDHG", "kiss_fly", "gajjala_1m",
                 ["1-min A+ winner"], "W +1R", 31.0)


def pavs_loser():
    return _base("PAVS_intraday_vcp_24x.mp4", f"{DAY}|PAVS|intraday_vcp|aplus", "PAVS", "intraday_vcp", "gajjala",
                 ["5-min A+ loser"], "L −1R", 2.0)


def amst_mover():
    return _base("AMST_reversal_squeeze_1mpage_24x.mp4", f"{DAY}|AMST|reversal_squeeze|potential", "AMST",
                 "reversal_squeeze", "gajjala_1m", [f"biggest mover of {DAY}"], "W +1R", 30.7)


def aimd_watch():
    return _base("AIMD_kiss_fly_1mpage_60x.mp4", f"{DAY}|AIMD|kiss_fly|potential", "AIMD", "kiss_fly", "gajjala_1m",
                 ["on your 👀 Watch · 1-min potential ring 04:46"], "W +1R", 3.0, speed=60.0, minutes=16.05)


def rs_side(symbol, first_stored, move):
    s = _base(f"{symbol}_reversal_squeeze_potential_24x.mp4", f"{DAY}|{symbol}|reversal_squeeze|potential", symbol,
              "reversal_squeeze", "gajjala",
              ["🎾 Reversal Squeeze potential · 5-min 09:46", "A+: none", "🧠 push on the Track record: none"],
              "W +1R", move)
    s["fill_px"] = None
    s["move_base"] = "first_trigger"
    s["plan_word"] = C.RS_WORD
    s["rs"] = [{"date": DAY, "symbol": symbol, "page": "gajjala", "first_seen_et": first_stored}]
    s["potential"] = {"id": s["ring_id"], "first_stored_et": first_stored, "trigger": 1.99, "stop": 1.91,
                      "page": "gajjala", "setup": "reversal_squeeze", "others": [], "doc_ids": []}
    return s


def write_side(folder: Path, side: dict, mp4=True, name=None, raw=None):
    folder.mkdir(parents=True, exist_ok=True)
    stem = (name or side["file"])[: -len(".mp4")]
    (folder / f"{stem}.json").write_text(raw if raw is not None else json.dumps(side, indent=1, default=str),
                                         encoding="utf-8")
    if mp4:
        (folder / side["file"]).write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * 64)


LEDGER_HEADER = ("date,symbol,page,first_seen_et,first_seen_mode,first_kind,first_trigger,first_stop,push_et,"
                 "push_grade,push_graded_on,went_aplus_et,aplus_lead_min,aplus_setup,aplus_trigger,aplus_stop,"
                 "aplus_grade,aplus_graded_on,other_page_aplus_et,other_page_aplus_setup,other_page_aplus_grade,"
                 "other_page_aplus_graded_on,triggered_et,stop_before_trigger,high_before_stop_px,"
                 "high_before_stop_pct,high_after_px,high_after_et,high_after_pct,close_1600_pct,close_2000_pct,"
                 "bars_through_et,video,note").split(",")


def write_ledger(root: Path, n_day=19, n_other=2):
    d = root / C.RS_SUB
    d.mkdir(parents=True, exist_ok=True)
    with open(d / C.LEDGER_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_HEADER)
        w.writeheader()
        for i in range(n_other):
            w.writerow({k: "" for k in LEDGER_HEADER} | {"date": "2026-11-13", "symbol": f"OLD{i}", "page": "gajjala"})
        for i in range(n_day):
            row = {k: "" for k in LEDGER_HEADER}
            row.update({"date": DAY, "symbol": f"S{i:02d}", "page": "gajjala_1m" if i % 2 else "gajjala",
                        "first_seen_et": "09:46", "first_kind": "armed", "first_trigger": "1.99",
                        "first_stop": "1.91", "high_after_pct": "44.7", "close_2000_pct": "19.6",
                        "video": f"S{i:02d}_reversal_squeeze_potential_24x.mp4"})
            w.writerow(row)


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "replays"
    day = r / C.VIDEOS_SUB / DAY
    for s in (cenn_carried(), akan_winner(), gdhg_winner(), pavs_loser(), amst_mover(), aimd_watch(),
              rs_side("GP", "10:05", 40.0), rs_side("AKAD", "09:46", 12.0)):
        write_side(day, s)
    (r / C.VIDEOS_SUB / "jobs.json").write_text("[]")
    (r / C.VIDEOS_SUB / "aplus_vs_cross_2026-11-02_to_11-13_12x.mp4").write_bytes(b"x" * 10)
    (day / ".sent").write_text("sent")
    write_ledger(r)
    return r


def _all_files(p):
    return [v["file"] for g in p.get("groups", []) for v in g["videos"]]


# ── constants ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_are_the_pipeline_literals_and_the_house_engines():
    assert C.FULL_DAY_WINDOW == "04:00-20:00 ET"
    assert C.RS_WORD == "🎾 Reversal Squeeze potential"
    assert C.MOVER_WHY_PREFIX == "biggest mover of"
    assert C.PAGE_WORDS == {"gajjala": WC.FRAME_WORDS["5m"], "gajjala_1m": WC.FRAME_WORDS["1m"]}
    assert C.SETUP_TEXT == {k: f"{e} {l}" for k, e, l in GC.SUBS if k in GC.SETUPS}
    assert set(C.SETUP_TEXT) == set(GC.SETUPS)
    assert [k for k, _ in C.GROUPS] == ["aplus_winners", "aplus_losers", "rs_potentials", "biggest_mover", "other"]
    assert C.VIDEO_HEADERS["Content-Encoding"] == "identity"
    assert "private" in C.VIDEO_HEADERS["Cache-Control"]
    assert C.LISTING_HEADERS == {"Cache-Control": "no-store"}


def test_NEGATIVE_setup_words_are_never_retyped_in_constants():
    src = (PKG / "constants.py").read_text(encoding="utf-8")
    for k, e, l in GC.SUBS:
        if k in GC.SETUPS:
            assert f'"{e} {l}"' not in src and f'"{l}"' not in src, (k, l)
    assert not re.search(r'["\']reversal_squeeze["\']\s*:', src)
    assert '"1-min"' not in src and '"5-min"' not in src


# ── accept rule ───────────────────────────────────────────────────────────────────────────────────────────────
def test_full_window_sidecars_are_listed_and_root_files_never_appear(root):
    lst = ST.read_day(DAY, root)
    names = sorted(v["file"] for v in lst["videos"])
    assert len(names) == 8 and lst["counts"]["videos"] == 8
    assert "jobs.json" not in str(names) and ".sent" not in names
    assert not any("aplus_vs_cross" in n for n in names)
    assert lst["files"] == frozenset(names)
    assert lst["counts"] == {"videos": 8, "skipped_window": 0, "no_sidecar": 0, "skipped_bad": 0}


def test_NEGATIVE_a_16_00_window_is_never_listed(root):
    d = root / C.VIDEOS_SUB / DAY
    s = akan_winner()
    s.update(file="ZZZ_kiss_fly_24x.mp4", window="04:00-16:00 ET")
    write_side(d, s)
    lst = ST.read_day(DAY, root)
    assert "ZZZ_kiss_fly_24x.mp4" not in lst["files"]
    assert lst["counts"]["skipped_window"] == 1
    assert lst["counts"]["no_sidecar"] == 0                      # its mp4 HAS a sidecar (window-skipped) — refix


def test_NEGATIVE_a_sidecar_with_no_window_is_never_listed(root):
    s = akan_winner()
    s["file"] = "NOWIN_kiss_fly_24x.mp4"
    del s["window"]
    write_side(root / C.VIDEOS_SUB / DAY, s)
    lst = ST.read_day(DAY, root)
    assert "NOWIN_kiss_fly_24x.mp4" not in lst["files"] and lst["counts"]["skipped_window"] == 1


def test_NEGATIVE_an_mp4_with_no_sidecar_is_never_listed(root):
    (root / C.VIDEOS_SUB / DAY / "LOOSE_6x.mp4").write_bytes(b"x")
    lst = ST.read_day(DAY, root)
    assert "LOOSE_6x.mp4" not in lst["files"] and lst["counts"]["no_sidecar"] == 1


def test_no_sidecar_counts_only_mp4s_that_truly_lack_one_the_11_13_shape(root):
    """Refix 2026-11-17: real 11-13 read no_sidecar 10 while 9 of those mp4s had a 16:00 sidecar. Now 9 → skipped_window,
    the 1 loose mp4 → no_sidecar."""
    d = root / C.VIDEOS_SUB / DAY
    for i in range(9):
        s = akan_winner()
        s.update(file=f"W{i}_kiss_fly_24x.mp4", window="04:00-16:00 ET")
        write_side(d, s)
    (d / "LOOSE_6x.mp4").write_bytes(b"x")
    lst = ST.read_day(DAY, root)
    assert lst["counts"] == {"videos": 8, "skipped_window": 9, "no_sidecar": 1, "skipped_bad": 0}
    assert not any(f.startswith("W") and f[1].isdigit() for f in lst["files"])


def test_NEGATIVE_a_window_skipped_sidecar_never_excuses_another_mp4(root):
    """A 16:00 sidecar whose `file` names a DIFFERENT loose mp4 (not its own stem) does not hide that mp4."""
    d = root / C.VIDEOS_SUB / DAY
    (d / "OTHER_6x.mp4").write_bytes(b"x")
    s = akan_winner()
    s.update(file="OTHER_6x.mp4", window="04:00-16:00 ET")
    write_side(d, s, mp4=False, name="STEM_kiss_fly_24x.mp4")
    lst = ST.read_day(DAY, root)
    assert lst["counts"]["skipped_window"] == 1 and lst["counts"]["no_sidecar"] == 1


def test_NEGATIVE_a_window_skipped_sidecar_without_its_mp4_changes_nothing(root):
    d = root / C.VIDEOS_SUB / DAY
    s = akan_winner()
    s.update(file="GONE_kiss_fly_24x.mp4", window="04:00-16:00 ET")
    write_side(d, s, mp4=False)
    lst = ST.read_day(DAY, root)
    assert lst["counts"] == {"videos": 8, "skipped_window": 1, "no_sidecar": 0, "skipped_bad": 0}


def test_NEGATIVE_a_bad_sidecar_still_leaves_its_mp4_in_no_sidecar(root):
    """Only window-skipped pairs are excused; a non-dict / malformed sidecar is not an accepted one."""
    d = root / C.VIDEOS_SUB / DAY
    s = akan_winner()
    s["file"] = "BAD_kiss_fly_24x.mp4"
    write_side(d, s, raw="[1, 2, 3]")
    lst = ST.read_day(DAY, root)
    assert lst["counts"]["skipped_bad"] == 1 and lst["counts"]["no_sidecar"] == 1


def test_NEGATIVE_a_sidecar_whose_file_is_not_its_stem(root):
    s = akan_winner()
    s["file"] = "OTHER_name_24x.mp4"
    write_side(root / C.VIDEOS_SUB / DAY, s, name="STEM_kiss_fly_24x.mp4")
    lst = ST.read_day(DAY, root)
    assert "OTHER_name_24x.mp4" not in lst["files"] and lst["counts"]["skipped_bad"] == 1


def test_NEGATIVE_a_render_in_flight_part_mp4_is_not_listed_until_the_mv(root):
    d = root / C.VIDEOS_SUB / DAY
    s = akan_winner()
    s["file"] = "PART_kiss_fly_24x.mp4"
    write_side(d, s, mp4=False)
    (d / "PART_kiss_fly_24x.part.mp4").write_bytes(b"x" * 10)
    lst = ST.read_day(DAY, root)
    assert "PART_kiss_fly_24x.mp4" not in lst["files"] and lst["counts"]["skipped_bad"] == 1
    os.rename(d / "PART_kiss_fly_24x.part.mp4", d / "PART_kiss_fly_24x.mp4")    # run.sh's mv
    assert "PART_kiss_fly_24x.mp4" in ST.read_day(DAY, root)["files"]


@pytest.mark.parametrize("raw", ["[1, 2]", "\"str\"", "not json {", ""])
def test_NEGATIVE_a_non_dict_or_broken_json_is_skipped_bad(root, raw):
    d = root / C.VIDEOS_SUB / DAY
    (d / "BAD_x_24x.json").write_text(raw)
    (d / "BAD_x_24x.mp4").write_bytes(b"x")
    lst = ST.read_day(DAY, root)
    assert "BAD_x_24x.mp4" not in lst["files"] and lst["counts"]["skipped_bad"] == 1
    assert lst["counts"]["videos"] == 8


def test_NEGATIVE_a_non_date_folder_is_ignored(root):
    write_side(root / C.VIDEOS_SUB / "_superseded", akan_winner())
    write_side(root / C.VIDEOS_SUB / "2026-11-17-old", akan_winner())
    assert ST.dates(root) == [DAY]


# ── C9: one bad card never 500s the listing ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("field,value", [("why", []), ("speed", None), ("minutes", "x"), ("ring_id", None),
                                         ("why", "a string"), ("why", [1])])
def test_NEGATIVE_one_malformed_card_drops_only_itself(root, field, value):
    s = aimd_watch()
    s["file"] = "MAL_kiss_fly_24x.mp4"
    s[field] = value
    write_side(root / C.VIDEOS_SUB / DAY, s)
    lst = ST.read_day(DAY, root)
    assert "MAL_kiss_fly_24x.mp4" not in lst["files"]
    assert lst["counts"]["skipped_bad"] == 1 and lst["counts"]["videos"] == 8
    p = ST.payload(DAY, root)
    assert p["state"] == "ready" and len(_all_files(p)) == 8
    assert len(p["rs"]["rows"]) == 19
    assert p["counts"]["skipped_bad"] == 1


# ── groups ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_group_of_the_five_shapes():
    assert ST.group_of(cenn_carried(), DAY) == "other"
    assert ST.group_of(amst_mover(), DAY) == "biggest_mover"
    assert ST.group_of(akan_winner(), DAY) == "aplus_winners"
    assert ST.group_of(pavs_loser(), DAY) == "aplus_losers"
    assert ST.group_of(rs_side("GP", "10:05", 1.0), DAY) == "rs_potentials"
    assert ST.group_of(aimd_watch(), DAY) == "other"
    nr = akan_winner()
    nr["grade"] = "no risk"
    assert ST.group_of(nr, DAY) == "other"                      # NEGATIVE: an A+ with no W/L grade
    only_rs = aimd_watch()
    only_rs["rs"] = []
    assert ST.group_of(only_rs, DAY) == "rs_potentials"           # an `rs` list alone marks a 🎾 job
    assert ST.group_of(cenn_carried(), PREV) == "aplus_winners"   # the same reel in its own day's folder


def test_carried_and_ring_day_are_served(root):
    cards = {v["file"]: v for v in ST.read_day(DAY, root)["videos"]}
    c = cards["CENN_reversal_squeeze_24x.mp4"]
    assert c["carried"] is True and c["ring_day"] == PREV and c["group"] == "other"
    a = cards["AKAN_reversal_squeeze_1mpage_24x.mp4"]
    assert a["carried"] is False and a["ring_day"] == DAY


def test_card_words_come_from_the_engines(root):
    cards = {v["file"]: v for v in ST.read_day(DAY, root)["videos"]}
    a = cards["AKAN_reversal_squeeze_1mpage_24x.mp4"]
    assert a["setup_text"] == C.SETUP_TEXT["reversal_squeeze"] and a["page_text"] == WC.FRAME_WORDS["1m"]
    assert a["speed_text"] == "24x" and a["length_text"] == "40 min"
    assert a["src"] == f"{C.API_PATH}/video/{DAY}/AKAN_reversal_squeeze_1mpage_24x.mp4"
    assert a["plan_word"] is None and a["potential"] is None
    w = cards["AIMD_kiss_fly_1mpage_60x.mp4"]
    assert w["speed_text"] == "60x" and w["length_text"] == "16 min"
    gp = cards["GP_reversal_squeeze_potential_24x.mp4"]
    assert gp["plan_word"] == C.RS_WORD
    assert gp["potential"] == {"first_stored_et": "10:05", "trigger": 1.99, "stop": 1.91,
                               "page_text": WC.FRAME_WORDS["5m"], "setup_text": C.SETUP_TEXT["reversal_squeeze"]}
    assert cards["PAVS_intraday_vcp_24x.mp4"]["grade"] == "L −1R"


def test_payload_groups_in_order_and_order_inside_groups(root):
    p = ST.payload(DAY, root)
    assert p["state"] == "ready"
    assert [g["key"] for g in p["groups"]] == ["aplus_winners", "aplus_losers", "rs_potentials", "biggest_mover",
                                               "other"]
    assert [g["label"] for g in p["groups"]] == [l for _, l in C.GROUPS]
    by = {g["key"]: [v["symbol"] for v in g["videos"]] for g in p["groups"]}
    assert by["aplus_winners"] == ["GDHG", "AKAN"]                 # move_pct desc
    assert by["rs_potentials"] == ["AKAD", "GP"]                   # first stored asc
    assert by["other"] == ["CENN", "AIMD"]
    assert by["biggest_mover"] == ["AMST"]


def test_NEGATIVE_empty_groups_are_omitted(tmp_path):
    r = tmp_path / "r"
    write_side(r / C.VIDEOS_SUB / DAY, pavs_loser())
    p = ST.payload(DAY, r)
    assert [g["key"] for g in p["groups"]] == ["aplus_losers"]


def test_order_puts_unknown_move_last(tmp_path):
    r = tmp_path / "r"
    a, b = akan_winner(), gdhg_winner()
    a["move_pct"] = None
    write_side(r / C.VIDEOS_SUB / DAY, a)
    write_side(r / C.VIDEOS_SUB / DAY, b)
    p = ST.payload(DAY, r)
    assert [v["symbol"] for v in p["groups"][0]["videos"]] == ["GDHG", "AKAN"]


# ── dates ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_dates_desc_and_NEGATIVE_folders_with_nothing_listable(root):
    write_side(root / C.VIDEOS_SUB / "2026-11-13", pavs_loser())
    s = pavs_loser()
    s["window"] = "04:00-16:00 ET"
    write_side(root / C.VIDEOS_SUB / "2026-11-12", s)             # only 16:00 sidecars → dropped
    (root / C.VIDEOS_SUB / "2026-11-11").mkdir()
    (root / C.VIDEOS_SUB / "2026-11-11" / "X_6x.mp4").write_bytes(b"x")   # mp4s, no sidecars → dropped
    assert ST.dates(root) == [DAY, "2026-11-13"]


# ── cache ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_cache_reparses_only_when_the_folder_key_moves(root, monkeypatch):
    real = ST._read_sidecar
    n = {"c": 0}

    def counting(p):
        n["c"] += 1
        return real(p)
    monkeypatch.setattr(ST, "_read_sidecar", counting)
    d = root / C.VIDEOS_SUB / DAY
    ST.read_day(DAY, root)
    first = n["c"]
    assert first == 8
    ST.read_day(DAY, root)
    assert n["c"] == first                                         # same key → json not read again
    p = d / "AKAN_reversal_squeeze_1mpage_24x.json"
    s = json.loads(p.read_text())
    s["grade"] = "L −1R"
    p.write_text(json.dumps(s))
    st = os.stat(p)
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))
    lst = ST.read_day(DAY, root)
    assert n["c"] > first
    assert {v["file"]: v["grade"] for v in lst["videos"]}["AKAN_reversal_squeeze_1mpage_24x.mp4"] == "L −1R"
    (d / "GP_reversal_squeeze_potential_24x.mp4").unlink()
    assert "GP_reversal_squeeze_potential_24x.mp4" not in ST.read_day(DAY, root)["files"]
    import shutil
    shutil.rmtree(d)
    assert ST.read_day(DAY, root)["videos"] == []
    assert (str(root), DAY) not in ST._DAY_CACHE


def test_folder_key_is_none_when_missing(tmp_path):
    assert ST.folder_key(tmp_path / "nope") is None
    (tmp_path / "d").mkdir()
    k = ST.folder_key(tmp_path / "d")
    assert isinstance(k, tuple) and len(k) == 4


# ── ledger ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_ledger_rows_only_the_day_strings_only_page_mapped(root):
    rows = ST.ledger_rows(DAY, root)
    assert len(rows) == 19
    assert all(set(r) == {"cells"} for r in rows)
    assert [r["cells"]["symbol"] for r in rows] == [f"S{i:02d}" for i in range(19)]   # file order
    assert all(isinstance(v, str) for r in rows for v in r["cells"].values())
    assert list(rows[0]["cells"]) == [k for k, _ in C.RS_COLUMNS]
    assert rows[0]["cells"]["page"] == WC.FRAME_WORDS["5m"] and rows[1]["cells"]["page"] == WC.FRAME_WORDS["1m"]
    assert rows[0]["cells"]["went_aplus_et"] == C.RS_EMPTY_CELL
    assert rows[0]["cells"]["high_after_pct"] == "44.7"
    assert ST.ledger_rows("2026-11-13", root)[0]["cells"]["symbol"] == "OLD0"


def test_NEGATIVE_missing_ledger_is_empty(tmp_path):
    assert ST.ledger_rows(DAY, tmp_path) == []


def test_NEGATIVE_malformed_csv_is_empty_and_flagged(root):
    p = root / C.RS_SUB / C.LEDGER_FILE
    p.write_text('date,symbol\n2026-11-17,"AB"C\n', encoding="utf-8")
    rows, err = ST.ledger_read(DAY, root)
    assert rows == [] and err is True
    body = ST.payload(DAY, root)
    assert body["state"] == "ready" and body["counts"]["ledger_error"] is True
    assert body["rs"]["rows"] == [] and body["rs"]["text"] == C.RS_EMPTY_TEXT


# ── payload ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_payload_ready_shape(root):
    p = ST.payload(None, root)
    assert p["date"] == DAY and p["dates"] == [DAY]
    assert p["title"] == C.TITLE and p["tab"] == C.TAB
    assert p["window"] == C.FULL_DAY_WINDOW and p["window_note"] == C.WINDOW_NOTE
    assert set(p["counts"]) == {"videos", "skipped_window", "no_sidecar", "skipped_bad"}
    assert p["rs"]["title"] == C.RS_TITLE and p["rs"]["note"] == C.RS_NOTE
    assert p["rs"]["columns"] == [{"key": k, "label": l} for k, l in C.RS_COLUMNS]
    assert len(p["rs"]["rows"]) == 19 and p["rs"]["text"] is None
    assert "files" not in p
    _strict(json.dumps(p, allow_nan=True))


def test_NEGATIVE_nan_in_a_sidecar_is_served_as_null(tmp_path):
    r = tmp_path / "r"
    s = akan_winner()
    s["move_pct"] = float("nan")
    s["fill_px"] = float("inf")
    write_side(r / C.VIDEOS_SUB / DAY, s, raw=json.dumps(s, allow_nan=True))
    assert "NaN" in (r / C.VIDEOS_SUB / DAY / "AKAN_reversal_squeeze_1mpage_24x.json").read_text()
    p = ST.payload(DAY, r)
    v = p["groups"][0]["videos"][0]
    assert v["move_pct"] is None and v["fill_px"] is None
    _strict(json.dumps(p, allow_nan=True))


def test_empty_and_no_folder_shapes(tmp_path):
    p = ST.payload(None, tmp_path / "missing")
    assert p == {"title": C.TITLE, "tab": C.TAB, "state": "no_folder", "text": C.NO_FOLDER_TEXT, "dates": [],
                 "date": None}
    r = tmp_path / "r"
    (r / C.VIDEOS_SUB).mkdir(parents=True)
    e = ST.payload(None, r)
    assert e["state"] == "empty" and e["text"] == C.EMPTY_DAY_TEXT and e["groups"] == [] and e["date"] is None
    assert e["rs"]["text"] == C.RS_EMPTY_TEXT


def test_C8_a_well_formed_unknown_day_is_kept(root):
    p = ST.payload("2026-11-99", root)
    assert p["state"] == "empty" and p["date"] == "2026-11-99" and p["dates"] == [DAY]
    assert p["text"] == C.EMPTY_DAY_TEXT and p["rs"]["rows"] == []


@pytest.mark.parametrize("bad", ["17-11-2026", "2026-11-17\n", "../2026", "", "２０２６-１１-１７"])
def test_NEGATIVE_a_malformed_day_falls_back_to_the_newest(root, bad):
    assert ST.payload(bad, root)["date"] == DAY


# ── resolve_video ─────────────────────────────────────────────────────────────────────────────────────────────
def test_resolve_video_a_listed_file(root):
    p = ST.resolve_video(DAY, "AKAN_reversal_squeeze_1mpage_24x.mp4", root)
    assert p is not None and p.is_file() and p.name == "AKAN_reversal_squeeze_1mpage_24x.mp4"


@pytest.mark.parametrize("day,name", [
    (DAY, ".."), (DAY, "../x.mp4"), (DAY, "x/y.mp4"), (DAY, "/etc/passwd"), (DAY, "/tmp/a.mp4"),
    (DAY, "AKAN_reversal_squeeze_1mpage_24x.json"), (DAY, "AKAN_reversal_squeeze_1mpage_24x.part.mp4"),
    (DAY, "akan_reversal_squeeze_1mpage_24x.mp4"), (DAY, "OLD_1600_24x.mp4"), ("..", "x.mp4"),
    ("2026-11-99", "x.mp4"), ("2026-11-17/..", "AKAN_reversal_squeeze_1mpage_24x.mp4"), (DAY, ".sent"),
])
def test_NEGATIVE_resolve_video_refuses(root, day, name):
    s = akan_winner()
    s.update(file="OLD_1600_24x.mp4", window="04:00-16:00 ET")
    write_side(root / C.VIDEOS_SUB / DAY, s)                       # exists on disk, unlisted (16:00)
    assert (root / C.VIDEOS_SUB / DAY / "OLD_1600_24x.mp4").is_file()
    assert ST.resolve_video(day, name, root) is None


def test_NEGATIVE_a_symlink_out_of_the_folder_is_refused(root, tmp_path):
    outside = tmp_path / "secret.mp4"
    outside.write_bytes(b"secret")
    d = root / C.VIDEOS_SUB / DAY
    s = akan_winner()
    s["file"] = "LINK_kiss_fly_24x.mp4"
    write_side(d, s, mp4=False)
    os.symlink(outside, d / "LINK_kiss_fly_24x.mp4")
    assert "LINK_kiss_fly_24x.mp4" in ST.read_day(DAY, root)["files"]     # the name is listed …
    assert ST.resolve_video(DAY, "LINK_kiss_fly_24x.mp4", root) is None    # … the bytes are never served


def test_root_comes_from_the_env(monkeypatch, root):
    monkeypatch.setenv(C.ROOT_ENV, str(root))
    assert ST.root_dir() == root
    assert ST.payload()["date"] == DAY
    monkeypatch.delenv(C.ROOT_ENV)
    assert ST.root_dir() == Path(C.ROOT_DEFAULT)
