"""Release helper: CalVer versions (YY.MM.PATCH) from git tags, and the release zip.

The baseline (YY.MM) is the first two parts of "version" in manifest.json,
e.g. "26.11.0" -> baseline "26.11". Each release tags the next free patch:
26.11.0, 26.11.1, ... Bump the manifest to "26.12.0" to start a new series.

    python script/release.py next-version     # prints e.g. 26.11.3
    python script/release.py build 26.11.3    # writes dist/octa_ev_charger.zip
    python script/release.py notes 26.11.3    # release notes from commits since the last tag
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "octa_ev_charger"
COMPONENT = ROOT / "custom_components" / DOMAIN
DIST = ROOT / "dist"

RE_BASELINE = re.compile(r"^(\d{2})\.(\d{1,2})$")
RE_VERSION = re.compile(r"^(\d{2})\.(\d{1,2})\.(\d+)$")
# Commit subjects like "[ops]: add icon" or "[core] fix polling".
RE_PREFIX = re.compile(r"^\[([^\]]+)\]:?\s*(.+)$")
BOTS = ("dependabot[bot]", "github-actions[bot]")


def baseline_from_manifest(manifest_version: str) -> str:
    """'26.11.0' -> '26.11'."""
    match = RE_VERSION.match(manifest_version)
    if not match:
        raise ValueError(f"manifest version {manifest_version!r} is not YY.MM.PATCH")
    year, month, _ = match.groups()
    if not 1 <= int(month) <= 12:
        raise ValueError(f"month {month} in {manifest_version!r} is not 1-12")
    return f"{year}.{int(month)}"


def next_version(baseline: str, tags: Iterable[str]) -> str:
    """Next patch for the baseline; tags from other baselines are ignored."""
    if not RE_BASELINE.match(baseline):
        raise ValueError(f"baseline {baseline!r} is not YY.MM")
    patches = [
        int(m.group(3))
        for tag in tags
        if (m := RE_VERSION.match(tag.strip().removeprefix("v")))
        and f"{m.group(1)}.{int(m.group(2))}" == baseline
    ]
    return f"{baseline}.{max(patches) + 1 if patches else 0}"


def read_manifest_version(component: Path = COMPONENT) -> str:
    return json.loads((component / "manifest.json").read_text(encoding="utf-8"))["version"]


def git_tags() -> list[str]:
    out = subprocess.run(["git", "tag", "--list"], cwd=ROOT, capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"git tag failed (is {ROOT} a git repository?): {out.stderr.strip()}")
    return out.stdout.split()


def _git(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def previous_tag(cwd: Path = ROOT) -> str | None:
    """Most recent release tag reachable from HEAD (None for the first release)."""
    out = _git(
        "describe", "--tags", "--abbrev=0", "--match", "[0-9]*.[0-9]*.[0-9]*", "HEAD", cwd=cwd
    )
    tag = out.stdout.strip()
    return tag if out.returncode == 0 and RE_VERSION.match(tag) else None


def commits_since(tag: str | None, cwd: Path = ROOT) -> list[tuple[str, str, str]]:
    """(sha, subject, author) for commits after `tag` up to HEAD, oldest first, no merges."""
    rev = f"{tag}..HEAD" if tag else "HEAD"
    out = _git(
        "log", "--no-merges", "--topo-order", "--reverse", "--format=%H%x1f%s%x1f%an", rev, cwd=cwd
    )
    if out.returncode:
        raise SystemExit(f"git log failed: {out.stderr.strip()}")
    return [tuple(line.split("\x1f", 2)) for line in out.stdout.splitlines() if line]


def render_notes(
    version: str,
    previous: str | None,
    commits: list[tuple[str, str, str]],
    repo_url: str | None = None,
) -> str:
    """Markdown release notes, grouped by the commit prefix ([core], [ops], ...)."""
    groups: dict[str, list[str]] = {}
    for sha, subject, author in commits:
        if author in BOTS or subject.startswith(("Bump ", "build(deps)")):
            section, text = "Dependencies", subject
        elif match := RE_PREFIX.match(subject):
            section, text = match.group(1).strip().capitalize(), match.group(2).strip()
        else:
            section, text = "Other", subject
        ref = f"[`{sha[:7]}`]({repo_url}/commit/{sha})" if repo_url else f"`{sha[:7]}`"
        groups.setdefault(section, []).append(f"- {text} ({ref})")

    order = sorted(groups, key=lambda s: (s in ("Other", "Dependencies"), s == "Dependencies", s))
    lines: list[str] = []
    for section in order:
        lines += [f"### {section}", "", *groups[section], ""]
    if not commits:
        lines += ["No changes since the previous release.", ""]
    if repo_url and previous:
        lines.append(f"**Full changelog:** {repo_url}/compare/{previous}...{version}")
    elif repo_url:
        lines.append(f"**Full changelog:** {repo_url}/commits/{version}")
    return "\n".join(lines).rstrip() + "\n"


def repo_url_from_env() -> str | None:
    """https://github.com/owner/repo inside GitHub Actions, otherwise None."""
    server, repo = os.environ.get("GITHUB_SERVER_URL"), os.environ.get("GITHUB_REPOSITORY")
    return f"{server}/{repo}" if server and repo else None


def build_zip(version: str, component: Path = COMPONENT, dist: Path = DIST) -> Path:
    """Zip the integration for HACS (files at the zip root), with the manifest version set."""
    if not RE_VERSION.match(version):
        raise ValueError(f"version {version!r} is not YY.MM.PATCH")
    dist.mkdir(parents=True, exist_ok=True)
    target = dist / f"{DOMAIN}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(component.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            name = path.relative_to(component).as_posix()
            if name == "manifest.json":
                manifest = json.loads(path.read_text(encoding="utf-8"))
                manifest["version"] = version
                zf.writestr(name, json.dumps(manifest, indent=2) + "\n")
            else:
                zf.write(path, name)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("next-version", help="print the next version to release")
    build = sub.add_parser("build", help="write dist/octa_ev_charger.zip")
    build.add_argument("version")
    notes = sub.add_parser("notes", help="print release notes since the previous tag")
    notes.add_argument("version")
    args = parser.parse_args(argv)

    if args.command == "next-version":
        baseline = baseline_from_manifest(read_manifest_version())
        print(next_version(baseline, git_tags()))
    elif args.command == "notes":
        previous = previous_tag()
        print(
            render_notes(args.version, previous, commits_since(previous), repo_url_from_env()),
            end="",
        )
    else:
        print(build_zip(args.version))
    return 0


if __name__ == "__main__":
    sys.exit(main())
