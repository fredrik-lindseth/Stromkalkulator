#!/usr/bin/env python3
"""Check public Markdown for private references, editorial prose and broken links."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"_private", ".git", ".agents", ".codex", ".venv", "venv", "dist"}
PRIVATE = re.compile(
    r"(?i)(?:\b(?:stromkalkulator|strømkalkulator|hacs-stromkalkulator|hacs-strømkalkulator|"
    r"effektvakt|hacs-effektvakt)-[a-z0-9]{7}\b|"
    r"\b(?:https?://)?(?:[\w-]+\.)?(?:dcat|dogcats)(?:[./:][^\s<>)]*)?|"
    r"(?<![\w/])/(?:Users|home)/[^/\s`<>]+/)"
)
PROSE = re.compile(r"\b(?:vi|Vi|jeg|Jeg|[Ff]redrik|Testmiljøtasken|tasken|avgjørelse\s+for)\b")
RETIRED_LABEL = re.compile(r"\b(?:L3[abc]|K[012])\b")
URL = re.compile(r"(?:https?://|mailto:)[^\s<>]+")
INLINE_CODE = re.compile(r"(`+)(?!`)(.*?)(?<!`)\1")
# Keep the link label visible to the prose check, but mask its destination.
LINK = re.compile(r"!?\[([^\]]*)\]\(\s*(<[^>]*>|(?:[^()\s]|\([^()]*\))+)(?:\s+['\"][^\n]*?['\"])?\s*\)")
REFERENCE = re.compile(r"^\s{0,3}\[(?!\^)([^\]]+)\]:[ \t]*(<[^>]+>|\S+)", re.MULTILINE)
REF_USE = re.compile(r"!?\[(?!\^)([^\]\n]+)\]\[([^\]\n]*)\]")
ALLOW = ("Jeg har Norgespris",)


def mask(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)


def without_code(text: str) -> str:
    text = re.sub(
        r"(?ms)^\s{0,3}(`{3,}|~{3,})[^\n]*\n.*?^\s{0,3}\1[^\n]*(?:\n|$)", lambda m: mask(m.group()), text
    )
    return INLINE_CODE.sub(lambda m: mask(m.group()), text)


def prose_text(text: str) -> str:
    text = without_code(text)
    text = LINK.sub(lambda m: m.group().replace(m.group(2), mask(m.group(2))), text)
    text = REFERENCE.sub(lambda m: mask(m.group()), text)
    text = URL.sub(lambda m: mask(m.group()), text)
    for phrase in ALLOW:
        text = text.replace(phrase, mask(phrase))
    return text


def markdown_files(root: Path) -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            "*.md",
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return sorted(
        root / p for p in set(result.stdout.decode().split("\0")) if p and not (set(Path(p).parts) & EXCLUDED)
    )


def target_exists(root: Path, source: Path, target: str) -> bool:
    target = target.strip("<>")
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not parts.path:
        return True
    path = unquote(parts.path).replace(r"\ ", " ")
    return ((root / path.lstrip("/")) if path.startswith("/") else (source.parent / path)).exists()


def scan_file(root: Path, source: Path) -> list[str]:
    text = source.read_text(encoding="utf-8")
    rel = source.relative_to(root)
    findings: list[str] = []

    def report(pos: int, message: str) -> None:
        findings.append(f"{rel}:{text.count(chr(10), 0, pos) + 1}: {message}")

    release = None
    if rel.as_posix() == "CHANGELOG.md":
        release = re.search(r"(?m)^##\s+\[?(?!Unreleased\b|Ikke utgitt\b)\d", text, re.IGNORECASE)
    for match in PRIVATE.finditer(text):
        history = " i publisert historikk" if release and match.start() >= release.start() else ""
        report(match.start(), f"privat referanse{history}: {match.group()}")

    # Released sections are immutable history, but private references are reported separately.
    reviewed = text[: release.start()] if release else text
    for match in PROSE.finditer(prose_text(reviewed)):
        report(match.start(), f"redaksjonell prosa: {match.group()}")

    for match in RETIRED_LABEL.finditer(prose_text(reviewed)):
        report(match.start(), f"utgått arbeidsmerking: {match.group()}")

    visible = without_code(reviewed)
    definitions = {m.group(1).casefold(): m.group(2) for m in REFERENCE.finditer(visible)}
    for match in LINK.finditer(visible):
        if not target_exists(root, source, match.group(2)):
            report(match.start(), f"mangler lenkemål: {match.group(2)}")
    for match in REFERENCE.finditer(visible):
        if not target_exists(root, source, match.group(2)):
            report(match.start(), f"mangler lenkemål: {match.group(2)}")
    for match in REF_USE.finditer(visible):
        key = (match.group(2) or match.group(1)).casefold()
        if key not in definitions:
            report(match.start(), f"mangler lenkereferanse: {key}")
    return findings


def scan(root: Path) -> list[str]:
    return [finding for path in markdown_files(root) if path.is_file() for finding in scan_file(root, path)]


def main() -> int:
    findings = scan(ROOT)
    print("\n".join(findings))
    return int(bool(findings))


if __name__ == "__main__":
    sys.exit(main())
