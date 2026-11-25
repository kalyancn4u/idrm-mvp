"""Photo metadata removal (ADR-0015, G-3) — pure, no database, no image library.

The files are built byte by byte, so each test shows exactly which block
goes in and which comes out. The stripper never decodes pixels, so the
"picture" bytes here are stand-ins.
"""

from __future__ import annotations

import struct
import zlib

import pytest

from shared.image_metadata import ImageError, strip_metadata

GPS_TEXT = b"GPS 17.3850N 78.4867E"   # stands in for a real GPS block
SERIAL = b"SN-PHONE-12345"


# ---------------------------------------------------------------------------
#  Builders
# ---------------------------------------------------------------------------

def seg(marker: int, body: bytes) -> bytes:
    return bytes((0xFF, marker)) + struct.pack(">H", len(body) + 2) + body


def tiff(orientation: int | None, *, little: bool = False, extra: bytes = GPS_TEXT) -> bytes:
    """A TIFF/EXIF body: IFD0 with Orientation (optional) and a Make tag, then extra data."""
    e = "<" if little else ">"
    head = (b"II*\x00" if little else b"MM\x00*") + struct.pack(e + "I", 8)
    entries = []
    if orientation is not None:
        entries.append(struct.pack(e + "HHIH2x", 0x0112, 3, 1, orientation))
    entries.append(struct.pack(e + "HHII", 0x010F, 2, len(SERIAL), 0))  # Make (value elsewhere)
    ifd = struct.pack(e + "H", len(entries)) + b"".join(entries) + struct.pack(e + "I", 0)
    return head + ifd + extra + SERIAL


def jpeg(*, orientation: int | None = 6, little: bool = False, trailer: bytes = b"") -> bytes:
    scan = b"\x12\x34\xff\x00\x56\xff\xd0\x78\x9a"  # an escaped FF and a restart marker
    return (
        b"\xff\xd8"
        + seg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
        + seg(0xE1, b"Exif\x00\x00" + tiff(orientation, little=little))
        + seg(0xE1, b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta>" + GPS_TEXT + b"</x:xmpmeta>")
        + seg(0xE2, b"ICC_PROFILE\x00\x01\x01colour")
        + seg(0xE2, b"MPF\x00" + SERIAL)
        + seg(0xED, b"Photoshop 3.0\x00" + GPS_TEXT)
        + seg(0xEE, b"Adobe\x00\x64\x00\x00\x00\x00\x01")
        + seg(0xFE, b"taken at my house " + GPS_TEXT)
        + seg(0xDB, b"\x00" + bytes(64))                  # quantisation table
        + seg(0xC0, b"\x08\x00\x10\x00\x10\x01\x01\x11\x00")  # frame header
        + seg(0xC4, b"\x00" + bytes(16))                  # Huffman table
        + seg(0xDA, b"\x01\x01\x00\x00\x3f\x00")          # scan header
        + scan
        + b"\xff\xd9"
        + trailer
    )


def png_chunk(ctype: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", zlib.crc32(ctype + data))


def png(*, trailer: bytes = b"") -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + png_chunk(b"sRGB", b"\x00")
        + png_chunk(b"tEXt", b"Comment\x00" + GPS_TEXT)
        + png_chunk(b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00" + GPS_TEXT)
        + png_chunk(b"eXIf", tiff(6))
        + png_chunk(b"tIME", b"\x07\xea\x0b\x19\x0c\x00\x00")
        + png_chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + png_chunk(b"IEND", b"")
        + trailer
    )


def riff_chunk(fourcc: bytes, data: bytes) -> bytes:
    return fourcc + struct.pack("<I", len(data)) + data + (b"\x00" if len(data) & 1 else b"")


def webp(*, extended: bool = True, trailer: bytes = b"") -> bytes:
    if extended:
        flags = 0x20 | 0x08 | 0x04  # ICC + EXIF + XMP
        chunks = (
            riff_chunk(b"VP8X", bytes((flags, 0, 0, 0)) + b"\x00\x00\x00\x00\x00\x00")
            + riff_chunk(b"ICCP", b"colour")
            + riff_chunk(b"VP8 ", b"picture-bytes")
            + riff_chunk(b"EXIF", tiff(6))
            + riff_chunk(b"XMP ", b"<x:xmpmeta>" + GPS_TEXT + b"</x:xmpmeta>")
        )
    else:
        chunks = riff_chunk(b"VP8L", b"lossless-picture")
    body = b"WEBP" + chunks
    return b"RIFF" + struct.pack("<I", len(body)) + body + trailer


def no_metadata(out: bytes) -> None:
    assert GPS_TEXT not in out
    assert SERIAL not in out
    assert b"xmpmeta" not in out


# ---------------------------------------------------------------------------
#  JPEG
# ---------------------------------------------------------------------------

def test_jpeg_drops_gps_device_comment_xmp_and_trailer():
    out = strip_metadata(jpeg(trailer=b"EXTRA" + GPS_TEXT), "image/jpeg")
    no_metadata(out)
    assert b"taken at my house" not in out
    assert b"Photoshop" not in out and b"MPF\x00" not in out
    assert out.endswith(b"\xff\xd9")


def test_jpeg_keeps_picture_and_colour_segments_byte_for_byte():
    src = jpeg()
    out = strip_metadata(src, "image/jpeg")
    for keep in (b"JFIF\x00", b"ICC_PROFILE\x00", b"Adobe\x00",
                 b"\xff\xdb", b"\xff\xc0", b"\xff\xc4", b"\xff\xda",
                 b"\x12\x34\xff\x00\x56\xff\xd0\x78\x9a\xff\xd9"):
        assert keep in out
    assert len(out) < len(src)


@pytest.mark.parametrize("little", [False, True])
def test_jpeg_keeps_only_the_orientation(little):
    out = strip_metadata(jpeg(orientation=6, little=little), "image/jpeg")
    exif = out[out.index(b"Exif\x00\x00"):]
    assert exif[6:10] == b"MM\x00*"
    tag, typ, count, value = struct.unpack(">HHIH", exif[16:26])
    assert (tag, typ, count, value) == (0x0112, 3, 1, 6)
    assert struct.unpack(">H", exif[14:16])[0] == 1  # exactly one entry


@pytest.mark.parametrize("orientation", [None, 1])
def test_jpeg_upright_photo_gets_no_exif_at_all(orientation):
    out = strip_metadata(jpeg(orientation=orientation), "image/jpeg")
    assert b"Exif" not in out


def test_jpeg_is_idempotent():
    once = strip_metadata(jpeg(), "image/jpeg")
    assert strip_metadata(once, "image/jpeg") == once


@pytest.mark.parametrize("bad", [
    b"\x89PNG\r\n\x1a\n",              # a PNG sent as JPEG
    b"\xff\xd8\xff\xe0\x00",           # cut off inside a length
    jpeg()[:-2],                       # no end marker
    b"\xff\xd8\xff\xe0\x00\x01",       # length smaller than its own field
])
def test_jpeg_refuses_what_it_cannot_walk(bad):
    with pytest.raises(ImageError):
        strip_metadata(bad, "image/jpeg")


# ---------------------------------------------------------------------------
#  PNG
# ---------------------------------------------------------------------------

def test_png_drops_text_exif_time_and_trailer():
    out = strip_metadata(png(trailer=GPS_TEXT), "image/png")
    no_metadata(out)
    for gone in (b"tEXt", b"iTXt", b"eXIf", b"tIME"):
        assert gone not in out
    for kept in (b"IHDR", b"sRGB", b"IDAT", b"IEND"):
        assert kept in out
    assert out.endswith(png_chunk(b"IEND", b""))


def test_png_refuses_bad_checksum_and_wrong_type():
    broken = bytearray(png())
    broken[40] ^= 0xFF
    with pytest.raises(ImageError):
        strip_metadata(bytes(broken), "image/png")
    with pytest.raises(ImageError):
        strip_metadata(jpeg(), "image/png")


def test_png_refuses_unknown_critical_chunk():
    src = png().replace(png_chunk(b"IEND", b""), png_chunk(b"ZZZZ", b"x") + png_chunk(b"IEND", b""))
    with pytest.raises(ImageError):
        strip_metadata(src, "image/png")


# ---------------------------------------------------------------------------
#  WebP
# ---------------------------------------------------------------------------

def test_webp_drops_exif_xmp_and_clears_their_flags():
    out = strip_metadata(webp(trailer=GPS_TEXT), "image/webp")
    no_metadata(out)
    assert b"EXIF" not in out and b"XMP " not in out
    assert out[20] == 0x20  # VP8X flags: only ICC left
    assert struct.unpack("<I", out[4:8])[0] == len(out) - 8  # RIFF size rewritten
    assert b"picture-bytes" in out and b"ICCP" in out


def test_webp_simple_format_is_unchanged():
    src = webp(extended=False)
    assert strip_metadata(src, "image/webp") == src


def test_webp_refuses_wrong_type():
    with pytest.raises(ImageError):
        strip_metadata(png(), "image/webp")


# ---------------------------------------------------------------------------
#  Other types
# ---------------------------------------------------------------------------

def test_pdf_passes_through_unchanged():
    pdf = b"%PDF-1.4\n/Author (Someone)\n%%EOF"
    assert strip_metadata(pdf, "application/pdf") == pdf
