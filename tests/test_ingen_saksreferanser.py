"""Vokter at interne saksnøkler ikke havner i det publiserte repoet.

Sakene spores i en privat tracker. En nøkkel i en kommentar eller doc peker på
noe ingen utenfor kan åpne, og lekker samtidig hva som er under arbeid. Skriv
heller hva saken gjelder, eller at noe spores som egen sak.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Nøkkelen er navnerommet pluss en base36-hale på fire til åtte tegn. Vanlige
# ord med samme form står i unntakslisten; `(?![-\w])` slipper gjennom
# lengre sammensetninger som URL-slugger.
SAKSNOKKEL = re.compile(r"\bstromkalkulator-(?!pakken\b)[0-9a-z]{4,8}(?![-\w])")


def _sporede_filer() -> list[Path]:
    try:
        ut = subprocess.run(
            ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True, text=True
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("Ikke en git-utsjekk")
    return [REPO / navn for navn in ut.split("\0") if navn]


def test_ingen_interne_saksnokler() -> None:
    funn = []
    for fil in _sporede_filer():
        try:
            tekst = fil.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for nr, linje in enumerate(tekst.splitlines(), start=1):
            for treff in SAKSNOKKEL.findall(linje):
                funn.append(f"{fil.relative_to(REPO)}:{nr}: {treff}")
    assert not funn, "Interne saksnøkler i repoet:\n" + "\n".join(funn)
