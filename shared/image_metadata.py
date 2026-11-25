"""
Remove hidden metadata from uploaded photos (ADR-0015, privacy design §8.8, task G-3).

Why this exists
---------------
A phone photo carries more than the picture. Its EXIF block usually holds the
**GPS position** where it was taken (often the person's home), the **time**,
and the **phone model and serial number**. A citizen who photographs a
flooded street to ask for help does not expect to hand their exact address
and device to every provider who opens the photo. So every image is cleaned
before it is stored.

How it works (no image library needed)
--------------------------------------
JPEG, PNG and WebP files are sequences of labelled blocks ("segments" in
JPEG, "chunks" in PNG and WebP). The picture lives in some blocks; metadata
lives in others. This module walks the blocks and keeps only those on an
**allow-list** of picture and colour blocks. Everything else is dropped —
including block types invented after this was written, which is why it is an
allow-list and not a block-list. Bytes after the end of the image are dropped
too (some phones append extra pictures or data there).

The pixels are copied byte for byte, so quality is unchanged and the file
gets slightly smaller.

One thing is kept on purpose: the **orientation** flag. Phones store photos
sideways and record "rotate 90°" in EXIF; without it, the photo shows on its
side. For a JPEG, a new, minimal EXIF block holding ONLY that flag replaces
the original. (PNG and WebP viewers rarely honour EXIF orientation, so for
them it is simply dropped.)

What this does NOT do (still open in G-3)
-----------------------------------------
- **Resize** large photos (`IMAGE_MAX_DIMENSION`) or **re-encode** the pixels,
  as the design asks. Both need an image library (Pillow), which is not a
  dependency yet.
- Clean **PDF** metadata (author, software). PDFs pass through unchanged.
- Hide what is visible **in** the picture (faces, house numbers, number
  plates) — that is FFP work.

Errors
------
A file whose bytes do not match its declared type, or whose structure is
broken, raises :class:`ImageError`; the upload endpoint turns that into a
422. Refusing is the safe choice: a file we cannot walk is a file we cannot
clean.

Standard library only, so it can be tested without the app.
"""

from __future__ import annotations

import struct
import zlib

__all__ = ["IMAGE_TYPES", "ImageError", "strip_metadata"]

IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


class ImageError(ValueError):
    """The file cannot be read as the image type it claims to be."""


def strip_metadata(data: bytes, content_type: str) -> bytes:
    """Return `data` without metadata if it is an image; otherwise unchanged."""
    if content_type == "image/jpeg":
        return _jpeg(data)
    if content_type == "image/png":
        return _png(data)
    if content_type == "image/webp":
        return _webp(data)
    return data


# ---------------------------------------------------------------------------
#  JPEG
# ---------------------------------------------------------------------------
#
# A JPEG is: FFD8 (start), then segments `FF <marker> <2-byte length> <body>`,
# then the compressed picture after an SOS segment, then FFD9 (end).
# Progressive JPEGs have several SOS segments with tables in between, so the
# walk continues after each scan until FFD9.

_SOI, _EOI, _SOS = 0xD8, 0xD9, 0xDA
_COM = 0xFE
# Markers with no length field: TEM and the restart markers RST0–RST7.
_STANDALONE = {0x01, *range(0xD0, 0xD8)}

_ORIENTATION_TAG = 0x0112


def _jpeg(data: bytes) -> bytes:
    if not data.startswith(b"\xff\xd8\xff"):
        raise ImageError("not a JPEG file")
    out = [b"\xff\xd8"]
    pos = 2
    n = len(data)
    while True:
        if pos >= n or data[pos] != 0xFF:
            raise ImageError("broken JPEG: expected a marker")
        while pos < n and data[pos] == 0xFF:  # fill bytes before a marker
            pos += 1
        if pos >= n:
            raise ImageError("broken JPEG: ends inside a marker")
        marker = data[pos]
        pos += 1

        if marker == _EOI:
            out.append(b"\xff\xd9")
            return b"".join(out)  # anything after the end is dropped
        if marker in _STANDALONE:
            out.append(bytes((0xFF, marker)))
            continue
        if marker == _SOI:
            raise ImageError("broken JPEG: second start marker")

        if pos + 2 > n:
            raise ImageError("broken JPEG: missing segment length")
        (length,) = struct.unpack(">H", data[pos:pos + 2])
        if length < 2 or pos + length > n:
            raise ImageError("broken JPEG: segment runs past the end")
        body = data[pos + 2:pos + length]
        pos += length

        kept = _jpeg_keep(marker, body)
        if kept is not None:
            out.append(bytes((0xFF, marker)) + struct.pack(">H", len(kept) + 2) + kept)

        if marker == _SOS:
            # Copy the compressed data up to the next real marker. Inside it,
            # FF is followed by 00 (an escaped FF) or by a restart marker.
            start = pos
            while True:
                j = data.find(b"\xff", pos)
                if j < 0 or j + 1 >= n:
                    raise ImageError("broken JPEG: picture data has no end marker")
                nxt = data[j + 1]
                if nxt == 0x00 or 0xD0 <= nxt <= 0xD7:
                    pos = j + 2
                    continue
                out.append(data[start:j])
                pos = j
                break


def _jpeg_keep(marker: int, body: bytes) -> bytes | None:
    """The body to write for this segment, or None to drop it."""
    if 0xE0 <= marker <= 0xEF:  # APP0–APP15: application data, mostly metadata
        if marker == 0xE0:  # JFIF / JFXX: pixel density, needed by some decoders
            return body
        if marker == 0xE1 and body.startswith(b"Exif\x00\x00"):
            return _orientation_only_exif(body[6:])
        if marker == 0xE2 and body.startswith(b"ICC_PROFILE\x00"):
            return body  # colour profile: describes colours, not people
        if marker == 0xEE and body.startswith(b"Adobe"):
            return body  # tells the decoder how colours were encoded
        return None  # XMP, IPTC/Photoshop, MPF, maker data, anything unknown
    if marker == _COM:
        return None  # free-text comment
    return body  # tables, frame and scan headers: the picture itself


def _orientation_only_exif(tiff: bytes) -> bytes | None:
    """A minimal EXIF body holding only the orientation flag, or None."""
    try:
        if tiff[:4] == b"II*\x00":
            end = "<"
        elif tiff[:4] == b"MM\x00*":
            end = ">"
        else:
            return None
        (ifd,) = struct.unpack(end + "I", tiff[4:8])
        (count,) = struct.unpack(end + "H", tiff[ifd:ifd + 2])
        for i in range(count):
            entry = tiff[ifd + 2 + 12 * i:ifd + 14 + 12 * i]
            tag, typ, num = struct.unpack(end + "HHI", entry[:8])
            if tag == _ORIENTATION_TAG and typ == 3 and num == 1:
                (value,) = struct.unpack(end + "H", entry[8:10])
                break
        else:
            return None
    except struct.error:
        return None  # unreadable EXIF: drop it rather than fail the upload
    if not 2 <= value <= 8:  # 1 means "upright": no flag needed
        return None
    return (
        b"Exif\x00\x00"
        + b"MM\x00*" + struct.pack(">I", 8)         # big-endian TIFF, first IFD at 8
        + struct.pack(">H", 1)                       # one entry
        + struct.pack(">HHIH2x", _ORIENTATION_TAG, 3, 1, value)
        + struct.pack(">I", 0)                       # no further IFD
    )


# ---------------------------------------------------------------------------
#  PNG
# ---------------------------------------------------------------------------
#
# A PNG is an 8-byte signature, then chunks `<4-byte length> <type> <data>
# <CRC>`, ending with IEND. Text (tEXt, zTXt, iTXt), EXIF (eXIf) and the
# modification time (tIME) are dropped.

_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_PNG_KEEP = {
    b"IHDR", b"PLTE", b"IDAT", b"IEND",                      # the picture
    b"tRNS", b"gAMA", b"cHRM", b"sRGB", b"iCCP", b"sBIT",    # colour
    b"cICP", b"mDCV", b"cLLI", b"bKGD", b"pHYs",
    b"acTL", b"fcTL", b"fdAT",                               # animation (APNG)
}


def _png(data: bytes) -> bytes:
    if not data.startswith(_PNG_SIG):
        raise ImageError("not a PNG file")
    out = [_PNG_SIG]
    pos = len(_PNG_SIG)
    n = len(data)
    while True:
        if pos + 8 > n:
            raise ImageError("broken PNG: no IEND chunk")
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        end = pos + 12 + length
        if end > n:
            raise ImageError("broken PNG: chunk runs past the end")
        chunk = data[pos:end]
        (crc,) = struct.unpack(">I", chunk[-4:])
        if zlib.crc32(chunk[4:-4]) != crc:
            raise ImageError(f"broken PNG: bad checksum in {ctype!r}")
        if ctype in _PNG_KEEP:
            out.append(chunk)
        elif 0x41 <= ctype[0] <= 0x5A:  # upper-case first letter: "critical"
            raise ImageError(f"PNG uses an unknown critical chunk {ctype!r}")
        pos = end
        if ctype == b"IEND":
            return b"".join(out)  # anything after the end is dropped


# ---------------------------------------------------------------------------
#  WebP
# ---------------------------------------------------------------------------
#
# A WebP is a RIFF file: "RIFF" <size> "WEBP", then chunks `<fourcc> <size>
# <data>` padded to an even length. Metadata can only appear in the extended
# format (a VP8X chunk first), as EXIF and "XMP " chunks; VP8X also carries
# flags saying whether they are present, so those flags are cleared.

_WEBP_KEEP = {b"VP8X", b"VP8 ", b"VP8L", b"ALPH", b"ICCP", b"ANIM", b"ANMF"}
_VP8X_EXIF, _VP8X_XMP = 0x08, 0x04


def _webp(data: bytes) -> bytes:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ImageError("not a WebP file")
    (riff_size,) = struct.unpack("<I", data[4:8])
    end_of_riff = 8 + riff_size
    if end_of_riff > len(data):
        raise ImageError("broken WebP: shorter than its header says")
    chunks = []
    pos = 12
    while pos < end_of_riff:
        if pos + 8 > end_of_riff:
            raise ImageError("broken WebP: truncated chunk header")
        fourcc, size = struct.unpack("<4sI", data[pos:pos + 8])
        padded = size + (size & 1)
        if pos + 8 + padded > end_of_riff:
            raise ImageError("broken WebP: chunk runs past the end")
        chunk = data[pos:pos + 8 + padded]
        if fourcc == b"VP8X" and size >= 1:
            flags = chunk[8] & ~(_VP8X_EXIF | _VP8X_XMP)
            chunk = chunk[:8] + bytes((flags,)) + chunk[9:]
        if fourcc in _WEBP_KEEP:
            chunks.append(chunk)
        pos += 8 + padded
    if not any(c[:4] in (b"VP8 ", b"VP8L", b"ANMF") for c in chunks):
        raise ImageError("broken WebP: no picture data")
    body = b"WEBP" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body  # trailing bytes dropped
