"""Brand images (custom_components/octa_ev_charger/brand/), shown by Home Assistant 2026.3+."""

from __future__ import annotations

from pathlib import Path
import struct

import pytest

BRAND = Path(__file__).parents[1] / "custom_components" / "octa_ev_charger" / "brand"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
COLOR_TYPE_RGBA = 6


def _png_header(path: Path) -> tuple[int, int, int]:
    """(width, height, color type) from the IHDR chunk."""
    data = path.read_bytes()[:33]
    assert data[:8] == PNG_SIGNATURE, f"{path.name} is not a PNG"
    width, height, _depth, color_type = struct.unpack(">IIBB", data[16:26])
    return width, height, color_type


@pytest.mark.parametrize(("name", "size"), [("icon.png", 256), ("icon@2x.png", 512)])
def test_icon_size_and_format(name: str, size: int) -> None:
    """Home Assistant requires square 256 px / 512 px PNG icons."""
    assert _png_header(BRAND / name) == (size, size, COLOR_TYPE_RGBA)


@pytest.mark.parametrize("name", ["icon.png", "icon@2x.png"])
def test_icon_has_transparent_corners(name: str) -> None:
    """Round logo: corners transparent (no white box), centre opaque."""
    image_module = pytest.importorskip("PIL.Image")
    with image_module.open(BRAND / name) as img:
        alpha = img.getchannel("A")
        w, h = img.size
        assert [alpha.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))] == [
            0,
            0,
            0,
            0,
        ]
        assert alpha.getpixel((w // 2, h // 2)) == 255


def test_only_known_brand_files() -> None:
    allowed = {
        f"{dark}{kind}{hi}.png"
        for dark in ("", "dark_")
        for kind in ("icon", "logo")
        for hi in ("", "@2x")
    }
    assert {p.name for p in BRAND.iterdir()} <= allowed


async def test_home_assistant_serves_local_icon(hass, hass_client) -> None:
    """HA 2026.3+ serves brand/icon.png through /api/brands (skipped on older HA)."""
    pytest.importorskip("homeassistant.components.brands")
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "brands", {})
    client = await hass_client()
    resp = await client.get("/api/brands/integration/octa_ev_charger/icon.png")
    assert resp.status == 200
    assert await resp.read() == (BRAND / "icon.png").read_bytes()
