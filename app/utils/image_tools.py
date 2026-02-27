from __future__ import annotations


def get_image_dimensions(image_bytes: bytes) -> tuple[int, int] | None:
    if len(image_bytes) < 24:
        return None

    png = _parse_png_dimensions(image_bytes)
    if png:
        return png

    jpeg = _parse_jpeg_dimensions(image_bytes)
    if jpeg:
        return jpeg

    return None


def _parse_png_dimensions(image_bytes: bytes) -> tuple[int, int] | None:
    signature = b"\x89PNG\r\n\x1a\n"
    if not image_bytes.startswith(signature):
        return None

    width = int.from_bytes(image_bytes[16:20], "big", signed=False)
    height = int.from_bytes(image_bytes[20:24], "big", signed=False)
    if width <= 0 or height <= 0:
        return None
    return width, height


def _parse_jpeg_dimensions(image_bytes: bytes) -> tuple[int, int] | None:
    if not image_bytes.startswith(b"\xff\xd8"):
        return None

    i = 2
    size = len(image_bytes)
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }

    while i + 9 < size:
        if image_bytes[i] != 0xFF:
            i += 1
            continue

        marker = image_bytes[i + 1]
        i += 2

        if marker in {0xD8, 0xD9}:  # SOI, EOI
            continue

        if i + 1 >= size:
            break
        segment_length = int.from_bytes(image_bytes[i : i + 2], "big", signed=False)
        if segment_length < 2 or i + segment_length > size:
            break

        if marker in sof_markers and i + 7 < size:
            height = int.from_bytes(image_bytes[i + 3 : i + 5], "big", signed=False)
            width = int.from_bytes(image_bytes[i + 5 : i + 7], "big", signed=False)
            if width > 0 and height > 0:
                return width, height

        i += segment_length

    return None
