"""⛔ The house reader for NYSE Group's short sale circuit breaker file (2026-11-23).

NYSE publishes its daily Rule 201 list as a real OLE2 / BIFF8 `.xls` (one sheet `SSR_data`, every cell an SST string).
`xlrd`, `openpyxl` and `olefile` are NOT installed in the host venv (3.9) or the api container (3.11), so this is a
stdlib-only (`struct`) port of the proven prototype (scratchpad `ssr/probe/biff_probe.py`, which parsed the 11/20 and
11/23 files, incl. the 11/20 file's two SST CONTINUE records).

`read_rows(data) -> list[list[Optional[str]]]` — the FIRST worksheet's grid, strings only. A non-string cell
(NUMBER / RK / LABEL / FORMULA / BOOLERR) reads None. Anything the reader cannot trust raises `ValueError(reason)` —
an unreadable file is an ERROR, never an empty grid.

Scope (spec §3.4, §6.14): all-SST-string sheets in a regular (not mini-stream) workbook stream with no DIFAT chain.
A layout change raises, and the NYSE source then reads failed.
"""
from __future__ import annotations

import struct
from typing import List, Optional

MAX_BYTES = 2_000_000            # input cap (== ssr_lists.SL_MAX_BYTES)
MAX_CELLS = 200_000              # grid cap (cells and SST strings)

_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
_FREE, _END = 0xFFFFFFFF, 0xFFFFFFFE
_STREAMS = ("Workbook", "Book")

_BOF = 0x0809
_EOF = 0x000A
_SST = 0x00FC
_CONTINUE = 0x003C
_LABELSST = 0x00FD
_NONSTRING = (0x0203, 0x027E, 0x0204, 0x0006, 0x0205)   # NUMBER, RK, LABEL, FORMULA, BOOLERR → None
_BOF_WORKSHEET = 0x0010


def _ole_stream(b: bytes) -> bytes:
    if len(b) < 512:
        raise ValueError("truncated")
    if b[:8] != _MAGIC:
        raise ValueError("bad magic")
    shift = struct.unpack_from("<H", b, 0x1E)[0]
    if shift not in (9, 12):
        raise ValueError("sector size")
    ssz = 1 << shift
    n_fat = struct.unpack_from("<I", b, 0x2C)[0]
    dir_start = struct.unpack_from("<I", b, 0x30)[0]
    mini_cut = struct.unpack_from("<I", b, 0x38)[0]
    n_difat = struct.unpack_from("<I", b, 0x48)[0]
    if n_difat or n_fat > 109:
        raise ValueError("difat chain")
    difat = struct.unpack_from("<109I", b, 0x4C)

    def sect(i: int) -> bytes:
        lo = (i + 1) * ssz
        hi = lo + ssz
        if hi > len(b):
            raise ValueError("truncated")
        return b[lo:hi]

    fat: list = []
    for s in difat[:n_fat]:
        if s in (_FREE, _END):
            continue
        fat.extend(struct.unpack("<%dI" % (ssz // 4), sect(s)))
    if not fat:
        raise ValueError("no fat")

    def chain(start: int) -> bytes:
        out, seen, s = [], set(), start
        while s not in (_END, _FREE):
            if s in seen or s >= len(fat):
                raise ValueError("broken fat chain")
            seen.add(s)
            out.append(sect(s))
            s = fat[s]
        return b"".join(out)

    d = chain(dir_start)
    for i in range(0, len(d) - 127, 128):
        e = d[i:i + 128]
        nlen = struct.unpack_from("<H", e, 0x40)[0]
        if nlen > 64:
            continue
        name = e[:max(0, nlen - 2)].decode("utf-16-le", "replace")
        typ = e[0x42]
        start, size = struct.unpack_from("<II", e, 0x74)
        if typ == 2 and name in _STREAMS:
            if size < mini_cut:
                raise ValueError("ministream")
            data = chain(start)
            if len(data) < size:
                raise ValueError("short stream")
            return data[:size]
    raise ValueError("no workbook stream")


def _records(wb: bytes):
    pos = 0
    n = len(wb)
    while pos + 4 <= n:
        rid, ln = struct.unpack_from("<HH", wb, pos)
        if pos + 4 + ln > n:
            raise ValueError("truncated record")
        yield rid, wb[pos + 4: pos + 4 + ln]
        pos += 4 + ln


def _read_sst(chunks: list) -> list:
    """The SST over [SST data, CONTINUE data, …]; a string split across a CONTINUE restarts with a flags byte."""
    ci, pos = 0, 8
    _total, uniq = struct.unpack_from("<II", chunks[0], 0)
    if uniq > MAX_CELLS:
        raise ValueError("too many strings")
    out = []
    for _ in range(uniq):
        if pos >= len(chunks[ci]):
            ci += 1
            pos = 0
        cch = struct.unpack_from("<H", chunks[ci], pos)[0]
        pos += 2
        flags = chunks[ci][pos]
        pos += 1
        wide = flags & 1
        runs = ext = 0
        if flags & 8:
            runs = struct.unpack_from("<H", chunks[ci], pos)[0]
            pos += 2
        if flags & 4:
            ext = struct.unpack_from("<I", chunks[ci], pos)[0]
            pos += 4
        parts = []
        left = cch
        while left > 0:
            avail = len(chunks[ci]) - pos
            take = min(left, avail // (2 if wide else 1)) if avail > 0 else 0
            if take == 0:
                ci += 1
                pos = 0
                wide = chunks[ci][pos] & 1
                pos += 1
                continue
            raw = chunks[ci][pos: pos + take * (2 if wide else 1)]
            parts.append(raw.decode("utf-16-le" if wide else "latin-1"))
            pos += len(raw)
            left -= take
        skip = runs * 4 + ext
        while skip > 0:
            avail = len(chunks[ci]) - pos
            if avail <= 0:
                ci += 1
                pos = 0
                continue
            t = min(skip, avail)
            pos += t
            skip -= t
        out.append("".join(parts))
    return out


def read_rows(data: bytes) -> List[List[Optional[str]]]:
    """The first worksheet's grid, strings only. Raises ValueError(reason); never returns a partial or empty grid
    for a file it could not read."""
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("not bytes")
    b = bytes(data)
    if not b:
        raise ValueError("empty")
    if len(b) > MAX_BYTES:
        raise ValueError("oversize")
    try:
        wb = _ole_stream(b)
        sst_chunks: list = []
        last_sst = False
        cells: dict = {}
        depth = 0
        sheet_state = 0          # 0 = before the first worksheet, 1 = inside it, 2 = done
        sheet_depth = 0
        for rid, rec in _records(wb):
            if rid == _SST:
                sst_chunks = [rec]
                last_sst = True
                continue
            if rid == _CONTINUE and last_sst:
                sst_chunks.append(rec)
                continue
            last_sst = False
            if rid == _BOF:
                depth += 1
                if sheet_state == 0 and len(rec) >= 4 and struct.unpack_from("<H", rec, 2)[0] == _BOF_WORKSHEET:
                    sheet_state, sheet_depth = 1, depth
                continue
            if rid == _EOF:
                if sheet_state == 1 and depth == sheet_depth:
                    sheet_state = 2
                    break
                depth -= 1
                continue
            if sheet_state != 1 or depth != sheet_depth:
                continue
            if rid == _LABELSST:
                r, c, _xf, idx = struct.unpack_from("<HHHI", rec, 0)
                cells[(r, c)] = idx
            elif rid in _NONSTRING:
                r, c = struct.unpack_from("<HH", rec, 0)
                cells.setdefault((r, c), None)
            else:
                continue
            if len(cells) > MAX_CELLS:
                raise ValueError("too many cells")
        if sheet_state == 0:
            raise ValueError("no worksheet")
        if sheet_state == 1:
            raise ValueError("truncated sheet")
        sst = _read_sst(sst_chunks) if sst_chunks else []
    except ValueError:
        raise
    except (struct.error, IndexError, UnicodeDecodeError, OverflowError, MemoryError) as exc:
        raise ValueError("unreadable: %s" % type(exc).__name__)
    if not cells:
        return []
    nrow = max(r for r, _ in cells) + 1
    ncol = max(c for _, c in cells) + 1
    if nrow * ncol > MAX_CELLS:
        raise ValueError("too many cells")
    grid: List[List[Optional[str]]] = [[None] * ncol for _ in range(nrow)]
    for (r, c), idx in cells.items():
        if idx is None:
            continue
        if idx >= len(sst):
            raise ValueError("sst index out of range")
        grid[r][c] = sst[idx]
    return grid
