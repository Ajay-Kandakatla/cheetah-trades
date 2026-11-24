"""⛔ SSR — the house BIFF8 reader for NYSE Group's short sale circuit breaker file (2026-11-24 branch; ask 2026-11-23).

Ajay 2026-11-23, verbatim: "No shorting at the bid (SEC short-sale restriction) Can we check or this for other stocks
too?"

Spec: scratchpad ssr/spec.md §3.4, W2. The two .xls files under tests/fixtures/ssr/ are VERBATIM NYSE answers
(fetched 2026-11-23); every damaged buffer here is built from them in the test and named SYNTHETIC.
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from short_interest import biff_rows as B

FIX = Path(__file__).resolve().parent / "fixtures" / "ssr"
NYSE_HEADER = ['Trigger Date', 'Issue Symbol', 'Issue Name', 'Primary Exchange', 'SSR State', 'Trigger Time',
               'Anticipated Deactivation Date']


def _b(name: str) -> bytes:
    return (FIX / name).read_bytes()


def _hdr(b: bytes):
    ssz = 1 << struct.unpack_from("<H", b, 0x1E)[0]
    n_fat = struct.unpack_from("<I", b, 0x2C)[0]
    dir_start = struct.unpack_from("<I", b, 0x30)[0]
    difat = struct.unpack_from("<109I", b, 0x4C)
    return ssz, n_fat, dir_start, difat


def _set_fat(b: bytes, index: int, value: int) -> bytes:
    """SYNTHETIC: rewrite one FAT entry of a real file."""
    ssz, _n, _d, difat = _hdr(b)
    per = ssz // 4
    sec = difat[index // per]
    off = (sec + 1) * ssz + (index % per) * 4
    out = bytearray(b)
    struct.pack_into("<I", out, off, value)
    return bytes(out)


def _fat(b: bytes) -> list:
    ssz, n_fat, _d, difat = _hdr(b)
    fat = []
    for s in difat[:n_fat]:
        fat.extend(struct.unpack_from("<%dI" % (ssz // 4), b, (s + 1) * ssz))
    return fat


def _workbook_entry(b: bytes):
    """(offset of the Workbook dir entry in the file, start sector, size)."""
    ssz, _n, dir_start, _difat = _hdr(b)
    off = (dir_start + 1) * ssz
    for i in range(ssz // 128):
        e = b[off + i * 128: off + (i + 1) * 128]
        nlen = struct.unpack_from("<H", e, 0x40)[0]
        if e[:max(0, nlen - 2)].decode("utf-16-le", "replace") == "Workbook":
            start, size = struct.unpack_from("<II", e, 0x74)
            return off + i * 128, start, size
    raise AssertionError("no Workbook entry in the first directory sector")


# ═════════════════════════════════════════════ the two real files
def test_the_11_23_file_reads_115_grid_rows_with_the_exact_header_and_agl_first():
    g = B.read_rows(_b("nyse_ssr20261123.xls"))
    assert len(g) == 115
    assert g[0] == NYSE_HEADER
    assert g[1] == ['11/23/2026', 'AGL', 'agilon health, inc.', 'NYSE', 'A', '09:37:47', '11/25/2026']
    assert all(len(r) == 7 and all(isinstance(c, str) and c for c in r) for r in g)


def test_the_11_20_file_reads_331_grid_rows_with_aac_ws_first():
    g = B.read_rows(_b("nyse_ssr20261120.xls"))
    assert len(g) == 331
    assert g[0] == NYSE_HEADER
    assert g[1][:2] == ['11/20/2026', 'AAC WS'] and g[1][3:] == ['NYSE', 'A', '15:38:33', '11/24/2026']
    assert g[1][2].startswith("Ares Acquisition Corporation III Redeemable warrants")
    assert all(len(r) == 7 and all(isinstance(c, str) and c for c in r) for r in g)
    assert len({r[1] for r in g[1:]}) == 330                     # no symbol twice


def test_the_11_20_file_exercises_the_sst_continue_path():
    b = _b("nyse_ssr20261120.xls")
    recs = [rid for rid, _ in B._records(B._ole_stream(b))]
    i = recs.index(0x00FC)
    assert recs[i + 1] == 0x003C and recs[i + 2] == 0x003C          # SST + two CONTINUE records
    g = B.read_rows(b)
    names = [r[2] for r in g[1:]]
    assert all(n.isprintable() for n in names)                       # a mis-joined split would leak flag bytes
    assert len({c for r in g for c in r}) > 900                      # strings from all three chunks are reached


# ═════════════════════════════════════════════ NEGATIVES — every damaged input raises, never an empty grid
@pytest.mark.parametrize("cut", [0.25, 0.5, 0.9, 0.995])
def test_NEGATIVE_truncated_bytes_raise(cut):
    b = _b("nyse_ssr20261120.xls")
    with pytest.raises(ValueError):
        B.read_rows(b[: int(len(b) * cut)])


def test_NEGATIVE_a_buffer_shorter_than_the_header_raises():
    with pytest.raises(ValueError, match="truncated"):
        B.read_rows(_b("nyse_ssr20261123.xls")[:300])


def test_NEGATIVE_bad_magic_raises():
    b = bytearray(_b("nyse_ssr20261123.xls"))
    b[0] ^= 0xFF
    with pytest.raises(ValueError, match="bad magic"):
        B.read_rows(bytes(b))


def test_NEGATIVE_an_html_body_raises():
    with pytest.raises(ValueError):
        B.read_rows(b"<html><body>Not Found</body></html>" + b" " * 600)


def test_NEGATIVE_a_flipped_fat_entry_that_loops_raises():
    b = _b("nyse_ssr20261123.xls")
    _off, start, _size = _workbook_entry(b)
    with pytest.raises(ValueError, match="broken fat chain"):
        B.read_rows(_set_fat(b, start, start))                       # SYNTHETIC: the stream's first sector points at itself


def test_NEGATIVE_a_fat_entry_pointing_past_the_table_raises():
    b = _b("nyse_ssr20261123.xls")
    _off, start, _size = _workbook_entry(b)
    with pytest.raises(ValueError, match="broken fat chain"):
        B.read_rows(_set_fat(b, start, 0x00FFFFFF))


def test_NEGATIVE_a_chain_cut_short_raises():
    b = _b("nyse_ssr20261123.xls")
    _off, start, _size = _workbook_entry(b)
    nxt = _fat(b)[start]
    assert nxt not in (0xFFFFFFFE, 0xFFFFFFFF)
    with pytest.raises(ValueError, match="short stream"):
        B.read_rows(_set_fat(b, start, 0xFFFFFFFE))                  # SYNTHETIC: end of chain after one sector


def test_NEGATIVE_an_empty_buffer_raises():
    with pytest.raises(ValueError, match="empty"):
        B.read_rows(b"")


def test_NEGATIVE_a_3_mb_buffer_raises():
    with pytest.raises(ValueError, match="oversize"):
        B.read_rows(_b("nyse_ssr20261123.xls") + b"\0" * 3_000_000)


def test_NEGATIVE_not_bytes_raises():
    with pytest.raises(ValueError, match="not bytes"):
        B.read_rows("d0cf11e0")


def test_NEGATIVE_a_difat_chain_raises():
    b = bytearray(_b("nyse_ssr20261123.xls"))
    struct.pack_into("<I", b, 0x48, 1)
    with pytest.raises(ValueError, match="difat chain"):
        B.read_rows(bytes(b))


def test_NEGATIVE_a_workbook_under_the_mini_stream_cutoff_raises():
    b = bytearray(_b("nyse_ssr20261123.xls"))
    off, _start, _size = _workbook_entry(bytes(b))
    struct.pack_into("<I", b, off + 0x78, 100)                       # SYNTHETIC: size under the 4,096 cutoff
    with pytest.raises(ValueError, match="ministream"):
        B.read_rows(bytes(b))


def test_NEGATIVE_no_workbook_stream_raises():
    b = bytearray(_b("nyse_ssr20261123.xls"))
    off, _start, _size = _workbook_entry(bytes(b))
    b[off: off + 2] = "X".encode("utf-16-le")                         # SYNTHETIC: rename the stream
    with pytest.raises(ValueError, match="no workbook stream"):
        B.read_rows(bytes(b))


def test_NEGATIVE_an_sst_index_out_of_range_raises(monkeypatch):
    real = B._read_sst
    monkeypatch.setattr(B, "_read_sst", lambda chunks: real(chunks)[:10])
    with pytest.raises(ValueError, match="sst index out of range"):
        B.read_rows(_b("nyse_ssr20261123.xls"))


def test_NEGATIVE_more_than_max_cells_raises(monkeypatch):
    monkeypatch.setattr(B, "MAX_CELLS", 100)
    with pytest.raises(ValueError, match="too many"):
        B.read_rows(_b("nyse_ssr20261123.xls"))


def test_a_non_string_cell_reads_none():
    """SYNTHETIC: one LABELSST record of the real stream re-typed as a NUMBER record → that cell reads None."""
    b = _b("nyse_ssr20261123.xls")
    wb = B._ole_stream(b)
    pos = 0
    target = None
    while pos + 4 <= len(wb):
        rid, ln = struct.unpack_from("<HH", wb, pos)
        if rid == 0x00FD:
            r, c = struct.unpack_from("<HH", wb, pos + 4)
            if (r, c) == (1, 1):
                target = pos
                break
        pos += 4 + ln
    assert target is not None
    ssz, _n, _d, _difat = _hdr(b)
    _off, start, _size = _workbook_entry(b)
    fat = _fat(b)
    s, k = start, target
    while k >= ssz:                                                  # locate the record's type field in the file
        s, k = fat[s], k - ssz
    out = bytearray(b)
    file_off = (s + 1) * ssz + k
    assert struct.unpack_from("<H", out, file_off)[0] == 0x00FD
    struct.pack_into("<H", out, file_off, 0x0203)
    g = B.read_rows(bytes(out))
    assert g[1][1] is None and g[1][0] == '11/23/2026'


def test_the_reader_is_stdlib_only():
    src = (Path(B.__file__)).read_text()
    for mod in ("xlrd", "openpyxl", "olefile", "pandas"):
        assert "import %s" % mod not in src and "from %s" % mod not in src
