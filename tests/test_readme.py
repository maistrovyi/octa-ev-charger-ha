"""README links and images point at files that exist in the repo."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
# Absolute links so images also render when HACS shows the README inside Home Assistant.
RAW = "https://raw.githubusercontent.com/maistrovyi/octa-ev-charger-ha/main/"

raw_paths = sorted(set(re.findall(re.escape(RAW) + r"([^\"')\s]+)", README)))
relative_paths = sorted(
    {
        target.split("#")[0]
        for target in re.findall(r"\]\(([^)]+)\)", README)
        if not target.startswith(("http://", "https://", "#", "mailto:"))
    }
)


def test_readme_has_images() -> None:
    assert any(p.startswith("docs/images/") for p in raw_paths)
    assert "custom_components/octa_ev_charger/brand/icon@2x.png" in raw_paths


@pytest.mark.parametrize("path", raw_paths)
def test_raw_links_exist(path: str) -> None:
    assert (ROOT / path).is_file(), path


@pytest.mark.parametrize("path", relative_paths)
def test_relative_links_exist(path: str) -> None:
    assert (ROOT / path).exists(), path


def test_no_relative_images() -> None:
    """Relative <img> paths break in HACS; use the raw.githubusercontent.com URL."""
    for src in re.findall(r'<img[^>]+src="([^"]+)"', README):
        assert src.startswith(RAW), src
