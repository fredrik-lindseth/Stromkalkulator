"""Vakt for tallene dokumentasjonen oppgir om DSO_LIST.

Antall nettselskap sto skrevet for hånd i sju dokumenter og hadde drevet fra
hverandre: 74, «70 av 75», «70 av 76» og en fotnote med 68, alle om det samme.
Her telles det ut av `DSO_LIST` og `docs/fakturaer/`, og hver påstand plukkes
ut med regex og sammenlignes. Endrer du et nettselskap, feller denne testen
tekstene som ikke er oppdatert. Den dekker også AGENTS.md og docstringene i
tests/test_fastledd_metoder.py, som drev fra hverandre på samme vis.

Tellemåten er den samme som [^antall] i docs/galskapen.md beskriver:

- *oppføringer*: alt i `DSO_LIST`.
- *valgbare*: uten `Egendefinert` og uten utfasede samleoppføringer
  (`supported: False`, som står igjen bare for å gi et repair-varsel).
- *nettselskap*: valgbare, der et selskap som er delt i flere prisområder
  (`delt_i`) teller som ett.

Nederst voktes antall entiteter i docs/sensorer.md på samme vis, talt ut av
plattformfilene. Overskriften der sa 53 sensorer mens HA registrerte 50, og
det er samme slags drift.
"""

from __future__ import annotations

import ast
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
    dso_id: entry for dso_id, entry in DSO_LIST.items() if dso_id != "custom" and entry.get("supported", True)
}
# Et selskap som er delt i prisområder ligger som én oppføring per område.
DELTE_EKSTRAOPPFORINGER = sum(len(entry["delt_i"]) - 1 for entry in DSO_LIST.values() if "delt_i" in entry)

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
        "AGENTS.md",
        r"hvorfor (\d+) nettselskap tolker samme NVE-regel på (\d+) måter",
        (ANTALL_SELSKAP, ANTALL_SELSKAP),
    ),
    (
        "README.en.md",
        r"The grid company list has (\d+) entries with rates, covering (\d+) grid companies",
        (ANTALL_VALGBARE, ANTALL_SELSKAP),
    ),
    (
        "tests/test_fastledd_metoder.py",
        r"dekker (\d+) av de (\d+) valgbare oppføringene",
        (ANTALL_NVE_MODELL, ANTALL_VALGBARE),
    ),
    (
        "tests/test_fastledd_metoder.py",
        r"(\d+) oppføringer skal oppføre seg helt som før",
        (ANTALL_NVE_MODELL,),
    ),
    (
        "docs/fakturaer/referanse.md",
        r"\| BKK +\| NO5 +\| Standard +\| (\d+) ",
        (ANTALL_FAKTURARAPPORTER,),
    ),
]


@pytest.mark.parametrize(("sti", "monster", "ventet"), PASTANDER, ids=lambda v: str(v)[:60])
def test_dokumenttall_stemmer_med_dso_list(sti: str, monster: str, ventet: tuple[int, ...]) -> None:
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
    energiledd = 600 * compute_energiledd_inkl_mva(dag, sone) + 400 * compute_energiledd_inkl_mva(natt, sone)

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
    # Overskriften teller ulike priser, ikke oppføringer: to par deler sum.
    assert _tall("docs/galskapen.md", r"## Én husholdning, (\d+) priser") == (len(set(summer)),)
    assert _tall("docs/galskapen.md", r"(\d+) av de (\d+) summene er unike") == (
        unike,
        len(summer),
    )


# ---------------------------------------------------------------------------
# Antall entiteter i docs/sensorer.md
#
# Samme drift som nettselskapstallene: overskriften sa 53 sensorer, mens ekte
# HA registrerer 50 sensorer, 4 binærsensorer og 1 knapp. Her telles det ut av
# plattformfilene, slik at en ny sensor feller teksten som ikke ble oppdatert.


PLATTFORMER = {"sensor": "sensor.py", "binary_sensor": "binary_sensor.py", "button": "button.py"}
KOMPONENT = ROT / "custom_components" / "stromkalkulator"


def _klassetre(fil: str) -> tuple[dict[str, ast.ClassDef], list[str]]:
    """Klassene i filen, og navnene som faktisk opprettes i `async_setup_entry`."""
    tre = ast.parse((KOMPONENT / fil).read_text(encoding="utf-8"))
    klasser = {node.name: node for node in tre.body if isinstance(node, ast.ClassDef)}
    opprettet: list[str] = []
    for node in ast.walk(tre):
        if not (isinstance(node, ast.AsyncFunctionDef) and node.name == "async_setup_entry"):
            continue
        for kall in ast.walk(node):
            if isinstance(kall, ast.Call) and isinstance(kall.func, ast.Name) and kall.func.id in klasser:
                opprettet.append(kall.func.id)
    assert opprettet, f"{fil}: fant ingen entiteter i async_setup_entry"
    return klasser, opprettet


def _arvet(klasser: dict[str, ast.ClassDef], navn: str, felt: str) -> ast.expr | None:
    """Verdien et klasseattributt har, hentet ned gjennom basene i samme fil."""
    node = klasser.get(navn)
    if node is None:
        return None
    for setning in node.body:
        if isinstance(setning, ast.AnnAssign) and isinstance(setning.target, ast.Name):
            if setning.target.id == felt:
                return setning.value
        elif (
            isinstance(setning, ast.Assign)
            and isinstance(setning.targets[0], ast.Name)
            and setning.targets[0].id == felt
        ):
            return setning.value
    for base in node.bases:
        if isinstance(base, ast.Name):
            verdi = _arvet(klasser, base.id, felt)
            if verdi is not None:
                return verdi
    return None


ANTALL_SENSORER = len(_klassetre("sensor.py")[1])
ANTALL_BINARSENSORER = len(_klassetre("binary_sensor.py")[1])
ANTALL_KNAPPER = len(_klassetre("button.py")[1])


def _sensorer_per_device() -> dict[str, tuple[int, int]]:
    """Device-gruppe til (aktive, totalt), talt ut av `sensor.py`."""
    klasser, opprettet = _klassetre("sensor.py")
    per_device: dict[str, tuple[int, int]] = {}
    for navn in opprettet:
        gruppe = _arvet(klasser, navn, "_device_group")
        assert isinstance(gruppe, ast.Name), f"{navn} mangler _device_group"
        flagg = _arvet(klasser, navn, "_attr_entity_registry_enabled_default")
        aktiv = 1 if flagg is None else int(bool(getattr(flagg, "value", True)))
        pa, totalt = per_device.get(gruppe.id, (0, 0))
        per_device[gruppe.id] = (pa + aktiv, totalt + 1)
    return per_device


PER_DEVICE = _sensorer_per_device()
ANTALL_AKTIVE = sum(pa for pa, _ in PER_DEVICE.values())

# Raden i tabellen øverst i docs/sensorer.md, per device-gruppe i sensor.py.
DEVICE_RADER = {
    "DEVICE_NETTLEIE": "Nettleie",
    "DEVICE_STROMSTOTTE": "Strømstøtte",
    "DEVICE_NORGESPRIS": "Norgespris",
    "DEVICE_MAANEDLIG": "Månedlig forbruk",
    "DEVICE_FORRIGE_MAANED": "Forrige måned",
    "DEVICE_EKSPORT": "Eksport",
}


def test_alle_device_gruppene_har_en_rad() -> None:
    """En ny device-gruppe uten rad ville gått upåaktet hen."""
    assert set(PER_DEVICE) == set(DEVICE_RADER)


def test_overskriften_i_sensorer_md_teller_riktig() -> None:
    """«53 sensorer totalt» var feil i begge retninger: 50 sensorer, og 4 binære."""
    assert _tall(
        "docs/sensorer.md",
        r"(\d+) devices og (\d+) entiteter: (\d+) sensorer, (\d+) binærsensorer "
        r"og (\d+) knapp\. (\d+) av sensorene",
    ) == (
        len(DEVICE_RADER),
        ANTALL_SENSORER + ANTALL_BINARSENSORER + ANTALL_KNAPPER,
        ANTALL_SENSORER,
        ANTALL_BINARSENSORER,
        ANTALL_KNAPPER,
        ANTALL_AKTIVE,
    )


@pytest.mark.parametrize(("gruppe", "rad"), sorted(DEVICE_RADER.items()))
def test_device_tabellen_stemmer_med_sensor_py(gruppe: str, rad: str) -> None:
    """Hver rad i tabellen telles ut av `sensor.py`, ikke skrevet av for hånd."""
    assert _tall("docs/sensorer.md", rf"\| {rad} +\| (\d+) +\| (\d+) +\|") == PER_DEVICE[gruppe]
