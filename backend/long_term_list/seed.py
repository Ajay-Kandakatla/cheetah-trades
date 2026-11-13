"""📅 Long Term — his saved list (the seed), read-only.

The seed is his 2026-11-12 list, committed BYTE-IDENTICAL at
`data/seed_2026_11_12.json` and pinned by sha256 (constants.SEED_SHA256). This
module only reads it: strict JSON (a NaN / Infinity literal fails loudly), a
sha mismatch fails loudly, a tenth category key fails loudly. Nothing in the
package ever opens the seed for writing.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from . import constants as C


class SeedChanged(Exception):
    """The seed on disk is not the file this tab was built for."""


def _refuse_nan(token):
    raise SeedChanged(f"seed is not strict JSON: {token} literal")


def load(path=None, *, sha: Optional[str] = "default") -> dict:
    """Parse the seed strictly; sha256 must equal C.SEED_SHA256 (pass sha=None
    to skip the sha check — tests of the strict parse only)."""
    p = Path(path) if path is not None else C.SEED_FILE
    raw = p.read_bytes()
    want = C.SEED_SHA256 if sha == "default" else sha
    try:
        data = json.loads(raw.decode("utf-8"), parse_constant=_refuse_nan)
    except SeedChanged:
        raise
    except Exception as exc:                                    # noqa: BLE001
        raise SeedChanged(f"seed unreadable: {exc}") from exc
    if want is not None:
        got = hashlib.sha256(raw).hexdigest()
        if got != want:
            raise SeedChanged(f"seed sha256 {got[:12]} is not the pinned {want[:12]}")
    if not isinstance(data, dict) or not isinstance(data.get("categories"), list):
        raise SeedChanged("seed has no categories list")
    for cat in data["categories"]:
        key = (cat or {}).get("key")
        if key not in C.CATEGORY_KEYS:
            raise SeedChanged(f"seed category {key!r} is not one of the known lists")
    zone_order(data)
    return data


def categories(seed) -> list:
    return list(seed.get("categories") or [])


def category(seed, key) -> Optional[dict]:
    for cat in categories(seed):
        if cat.get("key") == key:
            return cat
    return None


def name_symbol(item) -> str:
    """str -> itself; dict -> item["sym"] (the house symbol; his spelling stays in "sheet_symbol")."""
    if isinstance(item, dict):
        return str(item["sym"]).strip().upper()
    return str(item).strip().upper()


def chips(seed) -> dict:
    """SYM -> [category keys], file order."""
    out: dict = {}
    for cat in categories(seed):
        for item in cat.get("names") or []:
            sym = name_symbol(item)
            keys = out.setdefault(sym, [])
            if cat["key"] not in keys:
                keys.append(cat["key"])
    return out


def unique_names(seed) -> list:
    """Every saved symbol, first-appearance order."""
    return list(chips(seed).keys())


def screened_names(seed) -> list:
    """Unique over the eight screened lists — the forward record's headline names."""
    out = []
    for cat in categories(seed):
        if cat.get("key") not in C.SCREENED_KEYS:
            continue
        for item in cat.get("names") or []:
            sym = name_symbol(item)
            if sym not in out:
                out.append(sym)
    return out


def category_names(seed, key) -> list:
    cat = category(seed, key) or {}
    return [name_symbol(e) for e in cat.get("names") or []]


def pankaj_entries(seed) -> dict:
    """SYM -> {"sym","sheet_symbol","tier","zt","zones": {zone: (lo|None, hi|None)}}.
    His "Possible Action" column is NOT copied out (HIS CALL §7 #22)."""
    out: dict = {}
    cat = category(seed, C.PANKAJ_KEY) or {}
    for item in cat.get("names") or []:
        if not isinstance(item, dict):
            continue
        sym = name_symbol(item)
        zones = {}
        for zk, pair in (item.get("zones") or {}).items():
            pair = list(pair or [None, None]) + [None, None]
            zones[zk] = (pair[0], pair[1])
        out[sym] = {
            "sym": sym,
            "sheet_symbol": str(item.get("sheet_symbol") or sym),
            "tier": item.get("tier"),
            "zt": item.get("zt"),
            "zones": zones,
        }
    return out


def zone_order(seed) -> tuple:
    """The zone keys of the first 🧭 item ("Agg","C1","C2","C3"); every item
    must carry the same keys, else SeedChanged."""
    cat = category(seed, C.PANKAJ_KEY) or {}
    order = None
    for item in cat.get("names") or []:
        if not isinstance(item, dict):
            continue
        keys = tuple((item.get("zones") or {}).keys())
        if order is None:
            order = keys
        elif set(keys) != set(order) or len(keys) != len(order):
            raise SeedChanged(f"🧭 {item.get('sym')} carries zones {keys}, not {order}")
    return order or ()


def his_words(seed) -> list:
    """seed["source"] + every category's his_words, verbatim."""
    out = []
    src = seed.get("source")
    if isinstance(src, str) and src.strip():
        out.append(src)
    for cat in categories(seed):
        w = cat.get("his_words")
        if isinstance(w, str) and w.strip():
            out.append(w)
    return out


def load_baseline(path=None) -> dict:
    """The at-save baseline (WP-DATA writes it). Missing / unreadable ->
    {"reason": ...}; never raises."""
    p = Path(path) if path is not None else C.BASELINE_FILE
    try:
        data = json.loads(p.read_text(encoding="utf-8"), parse_constant=_refuse_nan)
        if not isinstance(data, dict):
            return {"reason": "baseline is not an object"}
        return data
    except FileNotFoundError:
        return {"reason": "no baseline file"}
    except Exception as exc:                                    # noqa: BLE001
        return {"reason": f"baseline unreadable: {exc}"}
