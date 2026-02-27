import base64

from app.utils.image_tools import get_image_dimensions


PNG_20X20 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAAKUlEQVR4nGP8z0A+YKJAL8Oo"
    "ZhIBE6kakMGoZhIBE6kakMGoZhIBRZoBIpwBJy3phGMAAAAASUVORK5CYII="
)


def test_parse_png_dimensions() -> None:
    assert get_image_dimensions(PNG_20X20) == (20, 20)
