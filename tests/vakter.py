"""Kildekodevakter: regler som må holde i koden, ikke bare i tallene.

To tester bruker skanneren her. `TestDimensjoner` i test_kostnad.py passer på at
ingen krone i hele pakken regnes av et fastledd per kilowattime, og
`TestSensorerRegnerIkkeSelv` i test_sensor_classes.py passer på at sensor.py
ikke ganger månedens satser med månedens kilowattimer. Samme regel sett fra hver
sin kant, men ulikt omfang: coordinatoren og kostnadskjernen *skal* gange satser
med kilowattimer, det er jobben deres, så den andre vakten gjelder bare
sensor.py. Derfor to tester, én skanner.

Skanneren leser koden som syntakstre og ikke som tekst. Tekstversjonen felte
bare den skrivemåten som sto der da vakten ble skrevet, og gikk grønt på den
stilen sensor.py faktisk er skrevet i (`_tall(data, "energiledd_dag") * kwh`).
En vakt som bare kjenner igjen gårsdagens formulering vokter ingenting.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

#: Roten til integrasjonen, funnet fra denne filen og ikke fra arbeidskatalogen.
PAKKEN = Path(__file__).resolve().parent.parent / "custom_components" / "stromkalkulator"


def _navn_i(node: ast.AST) -> set[str]:
    """Alle navn et uttrykk nevner: variabler, attributter og strengnøkler.

    Strengene er med fordi feltnavnene i data-dicten er strenger i koden:
    `_tall(data, "energiledd_dag")` og `data.get("energiledd_dag", 0)` nevner
    satsen like tydelig som en lokal variabel med samme navn.
    """
    navn: set[str] = set()
    for barn in ast.walk(node):
        if isinstance(barn, ast.Name):
            navn.add(barn.id)
        elif isinstance(barn, ast.Attribute):
            navn.add(barn.attr)
        elif isinstance(barn, ast.Constant) and isinstance(barn.value, str):
            navn.add(barn.value)
    return navn


def ganget_med(kilde: str, navn: Iterable[str]) -> list[str]:
    """Navnene fra `navn` som står i en gangeoperasjon i `kilde`.

    Begge operandrekkefølger teller, for `sats * kwh` og `kwh * sats` er samme
    regnestykke. Treffet er eksakt på navnet, så `previous_month_energiledd_dag`
    går fri av `energiledd_dag` uten at vi trenger ordgrenser i et regex.
    """
    sokt = set(navn)
    treff: set[str] = set()
    for node in ast.walk(ast.parse(kilde)):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            treff |= (_navn_i(node.left) | _navn_i(node.right)) & sokt
        elif isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Mult):
            treff |= (_navn_i(node.target) | _navn_i(node.value)) & sokt
    return sorted(treff)


def ganget_med_i_pakken(navn: Iterable[str]) -> dict[str, list[str]]:
    """Samme skanning over hver Python-fil i integrasjonen, per filnavn."""
    funn: dict[str, list[str]] = {}
    for fil in sorted(PAKKEN.rglob("*.py")):
        treff = ganget_med(fil.read_text(encoding="utf-8"), navn)
        if treff:
            funn[fil.name] = treff
    return funn
