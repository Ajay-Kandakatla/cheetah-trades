"""🎬 Replays tab — the compose pin (spec §3.2, WP-OPS, 2026-11-17).

Ajay 2026-11-17, verbatim: "Can you store the videos in to the app please"

The api (and ONLY the api) gets two READ-ONLY binds of the host replay folders written by
eod-audits/replays/run.sh, plus REPLAYS_DIR pointing at where they land. NEGATIVES: no replays mount on
cron / frontend / any other service, no replays bind is rw, no absolute /Users host path anywhere in the
file, the env equals the backend default. Each checker is also run against a mutated copy of the file so a
checker that silently passes everything fails here.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"

VIDEOS_BIND = "../eod-audits/replays/videos:/data/replays/videos:ro"
RS_BIND = "../eod-audits/replays/rs_potentials:/data/replays/rs_potentials:ro"
HOST_PREFIX = "../eod-audits/replays/"
ROOT_LITERAL = "/data/replays"


def _text() -> str:
    return COMPOSE.read_text()


def _doc(text: str | None = None) -> dict:
    return yaml.safe_load(_text() if text is None else text)


def _vols(doc: dict, service: str) -> list:
    return list((doc["services"][service] or {}).get("volumes") or [])


def _replays_binds(doc: dict, service: str) -> list:
    return [v for v in _vols(doc, service) if isinstance(v, str) and "replays" in v]


def _root_default() -> str:
    try:
        from chart_maps.replays import constants as RC
    except ImportError:
        return ROOT_LITERAL
    return RC.ROOT_DEFAULT


def check_api_binds(doc: dict) -> None:
    binds = _replays_binds(doc, "api")
    assert sorted(binds) == sorted([VIDEOS_BIND, RS_BIND]), binds
    for b in binds:
        assert b.startswith(HOST_PREFIX), b
        assert b.endswith(":ro"), b
        assert b.split(":")[1].startswith(ROOT_LITERAL + "/"), b


def check_no_rw(doc: dict) -> None:
    for name in doc["services"]:
        for b in _replays_binds(doc, name):
            parts = b.split(":")
            assert len(parts) == 3 and parts[2] == "ro", (name, b)


def check_only_api(doc: dict) -> None:
    for name in doc["services"]:
        if name == "api":
            continue
        assert _replays_binds(doc, name) == [], name
        env = (doc["services"][name] or {}).get("environment") or {}
        assert "REPLAYS_DIR" not in env, name


def check_no_users_literal(text: str) -> None:
    assert "/Users" not in text


def check_env(doc: dict) -> None:
    env = doc["services"]["api"]["environment"]
    assert env.get("REPLAYS_DIR") == _root_default()


# ── the real file ──────────────────────────────────────────────────────────────────────────────────────────────
def test_file_parses_and_has_the_services():
    doc = _doc()
    for name in ("api", "cron", "frontend"):
        assert name in doc["services"]


def test_api_carries_both_read_only_binds():
    check_api_binds(_doc())


def test_api_env_equals_the_backend_default():
    check_env(_doc())
    assert _doc()["services"]["api"]["environment"]["REPLAYS_DIR"] == ROOT_LITERAL


def test_backend_root_default_is_the_mount_root():
    RC = pytest.importorskip("chart_maps.replays.constants")
    assert RC.ROOT_DEFAULT == ROOT_LITERAL


def test_cron_and_frontend_carry_no_replays_mount():
    doc = _doc()
    assert _replays_binds(doc, "cron") == []
    assert _replays_binds(doc, "frontend") == []
    check_only_api(doc)


def test_no_replays_bind_is_writable():
    check_no_rw(_doc())


def test_no_absolute_users_path_in_the_file():
    check_no_users_literal(_text())


def test_existing_api_mounts_unchanged():
    vols = _vols(_doc(), "api")
    assert "cheetah-scans:/root/.cheetah" in vols
    assert "./backend/fidelity:/app/fidelity" in vols
    assert "./backend/oauth2-emails.txt:/app/oauth2-emails.txt" in vols
    assert len(vols) == 5


# ── NEGATIVES: each checker fails on a mutated file ───────────────────────────────────────────────────────────
def _mutate(old: str, new: str) -> str:
    text = _text()
    assert text.count(old) == 1, old
    return text.replace(old, new)


def test_negative_rw_bind_is_caught():
    bad = _doc(_mutate(VIDEOS_BIND, VIDEOS_BIND[: -len(":ro")] + ":rw"))
    with pytest.raises(AssertionError):
        check_no_rw(bad)
    with pytest.raises(AssertionError):
        check_api_binds(bad)


def test_negative_bind_without_mode_is_caught():
    bad = _doc(_mutate(RS_BIND, RS_BIND[: -len(":ro")]))
    with pytest.raises(AssertionError):
        check_no_rw(bad)


def test_negative_missing_bind_is_caught():
    bad = _doc(_mutate("      - " + RS_BIND + "\n", ""))
    with pytest.raises(AssertionError):
        check_api_binds(bad)


def test_negative_absolute_users_path_is_caught():
    text = _mutate(VIDEOS_BIND, "/Users/ajay/clinet-test/eod-audits/replays/videos:/data/replays/videos:ro")
    with pytest.raises(AssertionError):
        check_no_users_literal(text)
    with pytest.raises(AssertionError):
        check_api_binds(_doc(text))


def test_negative_mount_on_cron_is_caught():
    old = "      - ./backend/crontab:/app/crontab:ro\n"
    bad = _doc(_mutate(old, old + "      - " + VIDEOS_BIND + "\n"))
    with pytest.raises(AssertionError):
        check_only_api(bad)


def test_negative_mount_on_frontend_is_caught():
    doc = _doc()
    doc["services"]["frontend"]["volumes"] = [RS_BIND]
    with pytest.raises(AssertionError):
        check_only_api(doc)


def test_negative_env_drift_is_caught():
    bad = _doc(_mutate("REPLAYS_DIR: /data/replays", "REPLAYS_DIR: /data/replay"))
    with pytest.raises(AssertionError):
        check_env(bad)


def test_negative_env_missing_is_caught():
    bad = _doc(_mutate("      REPLAYS_DIR: /data/replays\n", ""))
    with pytest.raises(AssertionError):
        check_env(bad)
