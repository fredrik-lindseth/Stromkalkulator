"""Vakt for tallene dokumentasjonen oppgir om DSO_LIST.

Antall nettselskap sto skrevet for hånd i sju dokumenter og hadde drevet fra
hverandre: 74, «70 av 75», «70 av 76» og en fotnote med 68, alle om det samme.
Her telles det ut av `DSO_LIST` og `docs/fakturaer/`, og hver påstand i
dokumentene plukkes ut med regex og sammenlignes. Endrer du et nettselskap,
feller denne testen dokumentene som ikke er oppdatert.

Tellemåten er den samme som [^antall] i docs/galskapen.md beskriver:

- *oppføringer*: alt i `DSO_LIST`.
- *valgbare*: uten `Egendefinert` og uten utfasede samleoppføringer
  (`supported: False`, som står igjen bare for å gi et repair-varsel).
- *nettselskap*: valgbare, der et selskap som er delt i flere prisområder
  (`delt_i`) teller som ett.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from stromkalkulator.const import compute_energiledd_inkl_mva, resolve_avgiftssone
from stromkalkulator.dso import (
    DSO_LIST,
    FASTLEDD_TRINNBASERTE,
    finn_aktiv_periode,
    finn_kapasitetstrinn,
    hent_fastledd_metode,
)

ROT = Path(__file__).parent.parent

VALGBARE = {
    dso_id: entry
    for dso_id, entry in DSO_LIST.items()
    if dso_id != "custom" and entry.get("supported", True)
}
# Et selskap som er delt i prisområder ligger som én oppføring per område.
DELTE_EKSTRAOPPFORINGER = sum(
    len(entry["delt_i"]) - 1 for entry in DSO_LIST.values() if "delt_i" in entry
)

ANTALL_OPPFORINGER = len(DSO_LIST)
ANTALL_VALGBARE = len(VALGBARE)
ANTALL_SELSKAP = ANTALL_VALGBARE - DELTE_EKSTRAOPPFORINGER
AVVIKERE = [e for e in VALGBARE.values() if "fastledd_metode" in e]
ANTALL_NVE_MODELL = ANTALL_VALGBARE - len(AVVIKERE)
MED_KW_TRINN = {
    dso_id: entry
    for dso_id, entry in VALGBARE.items()
    if hent_fastledd_metode(entry) in FASTLEDD_TRINNBASERTE
}

_SONER = Counter(resolve_avgiftssone(entry) for entry in VALGBARE.values())

ANTALL_FAKTURARAPPORTER = len(list((ROT / "docs" / "fakturaer").glob("bkk-*.md")))


def _flat(sti: str) -> str:
    """Filinnholdet med all whitespace kollapset, så regex krysser linjebrudd."""
    return re.sub(r"\s+", " ", (ROT / sti).read_text(encoding="utf-8"))


def _tall(sti: str, monster: str) -> tuple[int, ...]:
    treff = re.findall(monster, _flat(sti))
    assert len(treff) == 1, f"{sti}: {monster!r} traff {len(treff)} ganger, ventet 1"
    funn = treff[0]
    if isinstance(funn, str):
        funn = (funn,)
    return tuple(int(t) for t in funn)


# (sti, regex, ventede tall) - regexen skal treffe nøyaktig én gang i filen.
PASTANDER: list[tuple[str, str, tuple[int, ...]]] = [
    (
        "README.md",
        r"Nettselskapslisten har (\d+) oppføringer med satser, som dekker (\d+) nettselskap",
        (ANTALL_VALGBARE, ANTALL_SELSKAP),
    ),
    (
        "docs/contributing.md",
        r"Nettselskapslisten har (\d+) oppføringer med satser, som dekker (\d+) norske",
        (ANTALL_VALGBARE, ANTALL_SELSKAP),
    ),
    (
        "docs/galskapen.md",
        r"`DSO_LIST` i `dso\.py` har (\d+) oppføringer",
        (ANTALL_OPPFORINGER,),
    ),
    (
        "docs/galskapen.md",
        r"Igjen står (\d+) valgbare oppføringer",
        (ANTALL_VALGBARE,),
    ),
    (
        "docs/galskapen.md",
        r"De dekker (\d+) nettselskap",
        (ANTALL_SELSKAP,),
    ),
    (
        "docs/galskapen.md",
        r"(\d+) av de (\d+) oppføringene bruker den",
        (ANTALL_NVE_MODELL, ANTALL_VALGBARE),
    ),
    (
        "docs/galskapen.md",
        r"`TRE_DØGNMAX_MND` \((\d+) av de (\d+)",
        (ANTALL_NVE_MODELL, ANTALL_VALGBARE),
    ),
    (
        "docs/galskapen.md",
        r"Av de (\d+) oppføringene ligger (\d+) i standardsonen, "
        r"(\d+) i Nord-Norge og (\d+) i tiltakssonen",
        (
            ANTALL_VALGBARE,
            _SONER["standard"],
            _SONER["nord_norge"],
            _SONER["tiltakssone"],
        ),
    ),
    (
        "docs/beregninger.md",
        r"(\d+) av de (\d+) valgbare oppføringene i `dso\.py` bruker den",
        (ANTALL_NVE_MODELL, ANTALL_VALGBARE),
    ),
    (
        "docs/beregninger.md",
        r"\(default\) \| (\d+) oppføringer",
        (ANTALL_NVE_MODELL,),
    ),
    (
        "docs/begrensninger.md",
        r"(\d+) av de (\d+) valgbare oppføringene i `dso\.py` bruker den",
        (ANTALL_NVE_MODELL, ANTALL_VALGBARE),
    ),
    (
        "docs/sensorer.md",
        r"For de (\d+) oppføringene som bruker NVE-modellen",
        (ANTALL_NVE_MODELL,),
    ),
    (
        "docs/begrensninger.md",
        r"BKK \(NO5\), verifisert mot (\d+) fakturaer",
        (ANTALL_FAKTURARAPPORTER,),
    ),
    (
        "docs/fakturaer/referanse.md",
        r"\| BKK +\| NO5 +\| Standard +\| (\d+) ",
        (ANTALL_FAKTURARAPPORTER,),
    ),
]


@pytest.mark.parametrize(("sti", "monster", "ventet"), PASTANDER, ids=lambda v: str(v)[:60])
def test_dokumenttall_stemmer_med_dso_list(
    sti: str, monster: str, ventet: tuple[int, ...]
) -> None:
    """Tallet i dokumentet er det samme som en telling av kilden gir."""
    assert _tall(sti, monster) == ventet


def test_fem_avvikere_fra_nve_modellen() -> None:
    """Dokumentene sier «de fem andre» flere steder. Her er de fem."""
    assert len(AVVIKERE) == 5


def _husholdningssum(entry: dict[str, Any]) -> float:
    """Nettleie for galskapen.md-husholdningen: 600 kWh dag, 400 natt, 5,0 kW, juli."""
    sone = resolve_avgiftssone(entry)
    dag = entry["energiledd_dag_eks_mva"]
    natt = entry["energiledd_natt_eks_mva"]
    periode = finn_aktiv_periode(entry.get("energiledd_perioder", []), "07-15")
    if periode is not None:
        dag, natt = periode["dag_eks_mva"], periode["natt_eks_mva"]
    energiledd = 600 * compute_energiledd_inkl_mva(
        dag, sone
    ) + 400 * compute_energiledd_inkl_mva(natt, sone)

    trinn = entry["kapasitetstrinn"]
    if trinn and isinstance(trinn[0], dict):
        trinn = [(rad["max"], rad["pris"]) for rad in trinn]
    fastledd, _, _ = finn_kapasitetstrinn(trinn, 5.0, entry.get("terskel_inkludert", True))
    return round(energiledd + fastledd, 2)


def test_unike_husholdningssummer_i_galskapen() -> None:
    """«67 av de 71 oppføringene med kW-trinn gir sin egen unike sum.»"""
    summer = [_husholdningssum(entry) for entry in MED_KW_TRINN.values()]
    teller = Counter(summer)
    unike = sum(1 for sum_kr in summer if teller[sum_kr] == 1)

    assert _tall(
        "docs/galskapen.md",
        r"(\d+) av de (\d+) oppføringene med kW-trinn gir sin egen unike sum",
    ) == (unike, len(summer))
    assert _tall("docs/galskapen.md", r"så N = (\d+)") == (len(summer),)
    assert _tall("docs/galskapen.md", r"(\d+) av de (\d+) summene er unike") == (
        unike,
        len(summer),
    )
