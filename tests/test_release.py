"""Version numbering and release zip (script/release.py)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).parents[1]
_spec = importlib.util.spec_from_file_location("release", ROOT / "script" / "release.py")
release = importlib.util.module_from_spec(_spec)
sys.modules["release"] = release
_spec.loader.exec_module(release)


@pytest.mark.parametrize(
    ("manifest_version", "baseline"),
    [("26.11.0", "26.11"), ("27.1.0", "27.1"), ("27.01.0", "27.1"), ("26.12.7", "26.12")],
)
def test_baseline_from_manifest(manifest_version: str, baseline: str) -> None:
    assert release.baseline_from_manifest(manifest_version) == baseline


@pytest.mark.parametrize("bad", ["1.0.0", "26.11", "26.13.0", "26.0.0", "v26.11.0", "2026.11.0"])
def test_baseline_rejects_bad_versions(bad: str) -> None:
    with pytest.raises(ValueError):
        release.baseline_from_manifest(bad)


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ([], "26.11.0"),  # first release of the baseline
        (["26.11.0"], "26.11.1"),
        (["26.11.0", "26.11.1", "26.11.2"], "26.11.3"),
        (["26.11.9", "26.11.10"], "26.11.11"),  # numeric, not alphabetical
        (["26.11.2", "26.11.0"], "26.11.3"),  # order doesn't matter
        (["v26.11.4"], "26.11.5"),  # a leading v is tolerated
        (["26.10.7", "26.12.0", "1.0.0", "latest"], "26.11.0"),  # other series ignored
        (["26.11.0", "26.11.0-beta", "26.11"], "26.11.1"),  # non-matching tags ignored
    ],
)
def test_next_version(tags: list[str], expected: str) -> None:
    assert release.next_version("26.11", tags) == expected


def test_next_version_new_baseline_restarts_patch() -> None:
    assert release.next_version("26.12", ["26.11.0", "26.11.1"]) == "26.12.0"


def test_next_version_rejects_bad_baseline() -> None:
    with pytest.raises(ValueError):
        release.next_version("2026.11", [])


def test_repo_manifest_is_a_baseline() -> None:
    """The committed manifest holds the baseline with patch 0; releases set the real patch."""
    version = release.read_manifest_version()
    assert version.endswith(".0")
    release.baseline_from_manifest(version)


def test_build_zip(tmp_path: Path) -> None:
    component = tmp_path / "octa_ev_charger"
    (component / "translations").mkdir(parents=True)
    (component / "__pycache__").mkdir()
    (component / "manifest.json").write_text(json.dumps({"domain": "x", "version": "26.11.0"}))
    (component / "__init__.py").write_text("")
    (component / "translations" / "uk.json").write_text("{}")
    (component / "__pycache__" / "junk.pyc").write_bytes(b"\0")

    path = release.build_zip("26.11.4", component=component, dist=tmp_path / "dist")

    assert path == tmp_path / "dist" / "octa_ev_charger.zip"
    with zipfile.ZipFile(path) as zf:
        # HACS zip_release expects the integration's files at the zip root.
        assert sorted(zf.namelist()) == ["__init__.py", "manifest.json", "translations/uk.json"]
        assert json.loads(zf.read("manifest.json"))["version"] == "26.11.4"


def test_build_zip_of_real_integration(tmp_path: Path) -> None:
    path = release.build_zip("26.11.0", dist=tmp_path)
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert "translations/uk.json" in names
        assert all("__pycache__" not in n for n in names)
        assert json.loads(zf.read("manifest.json"))["domain"] == "octa_ev_charger"


def test_build_zip_rejects_bad_version(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        release.build_zip("1.0", dist=tmp_path)


def test_cli_next_version(tmp_path: Path) -> None:
    """End to end against a throwaway git repo with existing tags."""
    repo = tmp_path / "repo"
    (repo / "script").mkdir(parents=True)
    (repo / "custom_components" / "octa_ev_charger").mkdir(parents=True)
    (repo / "script" / "release.py").write_text((ROOT / "script" / "release.py").read_text())
    (repo / "custom_components" / "octa_ev_charger" / "manifest.json").write_text(
        json.dumps({"version": "26.11.0"})
    )

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x")
    for tag in ("26.11.0", "26.11.1", "26.10.5"):
        git("tag", tag)

    out = subprocess.run(
        [sys.executable, "script/release.py", "next-version"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert out.stdout.strip() == "26.11.2"


def test_cli_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(release, "DIST", tmp_path)
    monkeypatch.setattr(release.build_zip, "__defaults__", (release.COMPONENT, tmp_path))
    assert release.main(["build", "26.11.7"]) == 0
    assert capsys.readouterr().out.strip().endswith("octa_ev_charger.zip")
