"""Vakt mot at strings.json og translations/*.json driver fra hverandre.

`strings.json` er malen, men det er `translations/nb.json` norske brukere
faktisk får servert. Driver de fra hverandre, ser brukeren gammel eller feil
tekst, og ingenting sier fra. Det har skjedd før: i 1.14.0 manglet nb.json hele
issues-seksjonen, så norske brukere fikk engelske repair-varsler, og i
september 2026 sto det «(inkl. avgifter)» i nb.json der energileddet skal føres
inn eks. mva og avgifter.

Paritetstestene i test_config_flow.py sammenligner bare nøkkelsettene på ett
nivå (sensorer, feilkoder, steg, issues). Driften her lå i bladnøkler under
`data_description`, som de aldri så. Denne filen sammenligner hele treet flatet
ut, så et nytt felt i ett steg ikke kan mangle i et annet språk.

Testene har ingen skip-vei med vilje. En vakt som hopper stille over seg selv
er ingen vakt.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

KOMPONENT = Path(__file__).parent.parent / "custom_components" / "stromkalkulator"
STRINGS = KOMPONENT / "strings.json"
OVERSETTELSER = KOMPONENT / "translations"

PLASSHOLDER = re.compile(r"\{[a-z_]+\}")


def _flat(node: object, sti: str = "") -> dict[str, str]:
    """Flat ut hele JSON-treet til {punktsti: tekst}."""
    if isinstance(node, dict):
        flatet: dict[str, str] = {}
        for nokkel, verdi in node.items():
            flatet.update(_flat(verdi, f"{sti}.{nokkel}" if sti else nokkel))
        return flatet
    return {sti: str(node)}


def _last(sti: Path) -> dict[str, str]:
    return _flat(json.loads(sti.read_text(encoding="utf-8")))


def _sprakfiler() -> list[Path]:
    filer = sorted(OVERSETTELSER.glob("*.json"))
    assert filer, f"fant ingen oversettelsesfiler i {OVERSETTELSER}"
    return filer


SPRAKFILER = _sprakfiler()


def test_strings_og_oversettelser_finnes() -> None:
    """En flyttet eller omdøpt fil skal felle vakten, ikke tømme den."""
    assert STRINGS.is_file(), f"{STRINGS} mangler"
    navn = {fil.name for fil in SPRAKFILER}
    assert {"nb.json", "en.json"} <= navn, f"mangler språkfil, fant bare {navn}"


@pytest.mark.parametrize("sprakfil", SPRAKFILER, ids=lambda p: p.name)
def test_samme_noekler_som_strings(sprakfil: Path) -> None:
    """Hver nøkkel i malen må finnes i språkfilen, og omvendt.

    En nøkkel som bare finnes i strings.json gir rå nøkkeltekst i brukerflaten
    for det språket. En som bare finnes i språkfilen er død tekst ingen ser.
    """
    mal = _last(STRINGS)
    oversatt = _last(sprakfil)

    mangler = sorted(set(mal) - set(oversatt))
    ekstra = sorted(set(oversatt) - set(mal))

    assert not mangler, f"{sprakfil.name} mangler nøkler fra strings.json: {mangler}"
    assert not ekstra, f"{sprakfil.name} har nøkler strings.json ikke har: {ekstra}"


@pytest.mark.parametrize("sprakfil", SPRAKFILER, ids=lambda p: p.name)
def test_ingen_tomme_tekster(sprakfil: Path) -> None:
    tomme = sorted(nokkel for nokkel, tekst in _last(sprakfil).items() if not tekst.strip())
    assert not tomme, f"{sprakfil.name} har tomme tekster: {tomme}"


@pytest.mark.parametrize("sprakfil", SPRAKFILER, ids=lambda p: p.name)
def test_samme_plassholdere_som_strings(sprakfil: Path) -> None:
    """{dso}, {timer} og resten må overleve oversettelsen.

    En plassholder som er skrevet feil eller falt ut gir enten en tom setning
    eller en KeyError når Home Assistant formaterer teksten.
    """
    mal = _last(STRINGS)
    oversatt = _last(sprakfil)

    avvik: dict[str, tuple[list[str], list[str]]] = {}
    for nokkel in sorted(set(mal) & set(oversatt)):
        i_mal = set(PLASSHOLDER.findall(mal[nokkel]))
        i_oversatt = set(PLASSHOLDER.findall(oversatt[nokkel]))
        if i_mal != i_oversatt:
            avvik[nokkel] = (sorted(i_mal), sorted(i_oversatt))

    assert not avvik, f"{sprakfil.name} har avvikende plassholdere (mal, oversatt): {avvik}"


def test_nb_er_ordrett_lik_strings() -> None:
    """Malen er skrevet på norsk, så nb.json skal være en kopi av den.

    Dette er vakten som fanger tekstdrift, ikke bare manglende nøkler. Endrer du
    en norsk tekst, endre den begge steder i samme commit.
    """
    mal = _last(STRINGS)
    nb = _last(OVERSETTELSER / "nb.json")

    drift = sorted(nokkel for nokkel in set(mal) & set(nb) if mal[nokkel] != nb[nokkel])
    assert not drift, f"nb.json har drevet fra strings.json på: {drift}"


TRINN_PAR = re.compile(r"\d+(?:[.,]\d+)?\s*:\s*\d")

FASTLEDD_NOKLER = ("kapasitetstrinn", "trinntabell", "egendefinert_fastledd")


@pytest.mark.parametrize("sprakfil", [STRINGS, *SPRAKFILER], ids=lambda p: p.name)
def test_ingen_belop_i_trinneksemplene(sprakfil: Path) -> None:
    """Formateksempelet for kapasitetstrinn skal ikke inneholde tall.

    Eksempelet var lenge «2:155,5:250,10:415», som er BKKs faktiske trinn 1 til
    3, i en setning som påsto at det ikke var priser. Brukeren blir bedt om å
    hente sine egne trinn fra sin egen prisliste, og får da servert tre beløp
    som ser ut som fasit. Det er incident 006 en gang til, denne gangen med
    brukeren som den som taster inn malen: kapasitetsleddet er et fast
    månedsbeløp, så et kopiert trinn slår rett inn i månedskostnaden.

    Vi har ingen prisliste for Egendefinert, så et eksempel med beløp i måtte
    lånes fra et annet nettselskap. Formen «kW-grense:kr/mnd» sier det samme
    uten å kunne tastes inn.
    """
    tekster = _flat(json.loads(sprakfil.read_text(encoding="utf-8")))
    med_belop = {
        nokkel: tekst
        for nokkel, tekst in tekster.items()
        if any(ord_ in nokkel for ord_ in FASTLEDD_NOKLER) and TRINN_PAR.search(tekst)
    }
    assert not med_belop, (
        f"{sprakfil.name} har tall i et kapasitetstrinn-eksempel: {sorted(med_belop)}. "
        "Skriv formen i stedet, for eksempel «kW-grense:kr/mnd»."
    )
