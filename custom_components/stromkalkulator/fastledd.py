"""Fastleddregelen: fra tariff og effekttopper til kroner per måned.

Modulen er ren på samme måte som `kostnad.py`: ingenting fra Home Assistant og
ingen tilstand. Den samme regelen gjelder tre steder, og de skal ikke kunne
drive fra hverandre:

- inneværende måned, med tariffen katalogen har nå,
- en lukket måned som får en forsinket hale, med tariffen den ble lukket med,
- et lukket grunnlag som lastes fra lagring.

Hver av dem bygger en `Fastleddtariff` fra sin kilde og spør her. Tariffen
fryses i lagringen som et snapshot ved månedsslutt, så formatet til
`til_snapshot` og `fra_snapshot` er lagringsformat og må kunne leses av
eldre utgaver.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Final, cast

from .dso import (
    FASTLEDD_FEM_VEKTET_AR,
    FASTLEDD_MND_MAX,
    FASTLEDD_OV_TREFASE,
    FASTLEDD_TRINNBASERTE,
    finn_kapasitetstrinn,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .dso import FastleddLineaer, FastleddSikringstrinn, KapasitetstrinnTuple

__all__ = [
    "FASTLEDD_UKJENT_TEKST",
    "FEM_VEKTET_ANTALL_TOPPER",
    "SIKRINGSVALG_MANGLER_TEKST",
    "Fastleddtariff",
    "fastledd_belop_ukjent",
    "fastledd_for_grunnlag",
    "fastledd_grunnlag",
    "fastledd_ukjent",
    "lineart_fastledd",
    "ukestart",
    "utenfor_kildegrense",
    "vektet_kw",
]

FEM_VEKTET_ANTALL_TOPPER: Final = 5

# Trinnbeskrivelsene når det ikke finnes noe trinn å peke på. Diagnostikken
# slipper dem gjennom som kjent vokabular.
FASTLEDD_UKJENT_TEKST: Final = "fastledd ukjent"
SIKRINGSVALG_MANGLER_TEKST: Final = "sikringsstørrelse ikke valgt"


@dataclass(frozen=True, slots=True)
class Fastleddtariff:
    """Alt fastledd-oppslaget trenger fra nettselskapet og brukerens valg.

    `trinn` har `inf` som øvre grense på det åpne topptrinnet.
    `kildegrense_kw` er der kildens husholdningstabell slutter; grunnlag over
    den har ikke noe kildebekreftet beløp. `sikringstrinn` er brukerens valgte
    rad for OV_TREFASE og finnes bare for inneværende måned: en lukket måned
    beholder beløpet den ble lukket med.
    """

    metode: str
    mva_sats: float
    trinn: tuple[KapasitetstrinnTuple, ...] = ()
    terskel_inkludert: bool = True
    kildegrense_kw: float | None = None
    kildegrense_inkludert: bool = True
    lineaer: FastleddLineaer | None = None
    sesongfaktor: Mapping[int, float] = field(default_factory=dict)
    sikringstrinn: tuple[int, FastleddSikringstrinn] | None = None

    def til_snapshot(self) -> dict[str, Any]:
        """Tariffdelen av lagringens fastledd-snapshot. JSON har ingen `inf`."""
        return {
            "metode": self.metode,
            "kjent_fastledd_maks_kw": self.kildegrense_kw,
            "kjent_fastledd_maks_kw_inkludert": self.kildegrense_inkludert,
            "trinn": [[None if math.isinf(kw) else kw, kr] for kw, kr in self.trinn],
            "terskel_inkludert": self.terskel_inkludert,
            "lineaer": dict(self.lineaer) if self.lineaer else None,
            "sesongfaktor": {str(k): v for k, v in self.sesongfaktor.items()},
            "mva_sats": self.mva_sats,
        }

    @classmethod
    def fra_snapshot(cls, snapshot: Mapping[str, Any]) -> Fastleddtariff:
        """Tariffen en lukket måned ble regnet med, fra et validert snapshot."""
        kildegrense = snapshot.get("kjent_fastledd_maks_kw")
        lineaer = snapshot.get("lineaer")
        return cls(
            metode=str(snapshot["metode"]),
            mva_sats=float(snapshot.get("mva_sats", 0.0)),
            trinn=tuple((math.inf if kw is None else float(kw), float(kr)) for kw, kr in snapshot["trinn"]),
            terskel_inkludert=bool(snapshot["terskel_inkludert"]),
            kildegrense_kw=None if kildegrense is None else float(kildegrense),
            kildegrense_inkludert=bool(snapshot.get("kjent_fastledd_maks_kw_inkludert", True)),
            lineaer=cast("FastleddLineaer", lineaer) if lineaer else None,
            sesongfaktor={int(k): float(v) for k, v in snapshot.get("sesongfaktor", {}).items()},
        )


def ukestart(dag: date) -> date:
    """Mandagen i uken dagen ligger i."""
    return dag - timedelta(days=dag.weekday())


def vektet_kw(kw: float, dato: str, sesongfaktor: Mapping[int, float]) -> float:
    """Ukestoppens sesongvektede effekt.

    Vekten følger mandagen i uken, ikke toppens egen måned. Fjellnett:
    «Når ei uke går over et månedsskift, vil det være mandag i starten på
    uka som bestemmer hvilken sesongfaktor som effekten blir vekta med.»
    """
    try:
        dag = date.fromisoformat(dato)
    except ValueError:
        return kw
    return kw * sesongfaktor.get(ukestart(dag).month, 1.0)


def fastledd_grunnlag(
    tariff: Fastleddtariff,
    doegnmaks_kw: Iterable[float],
    ukestopper: Iterable[tuple[float, str]],
) -> float:
    """Effektverdien i kW som nettselskapets fastledd-metode legger til grunn.

    NVE-modellen bruker snittet av de tre høyeste døgnmaksene i måneden.
    `ukestopper` er (kW, toppens dato) og brukes bare av FEM_VEKTET_ÅR. De fem
    nettselskapene som avviker, er dokumentert i docs/beregninger.md.
    """
    if tariff.metode == FASTLEDD_MND_MAX:
        return max(doegnmaks_kw, default=0.0)
    if tariff.metode == FASTLEDD_FEM_VEKTET_AR:
        vektet = sorted((vektet_kw(kw, dato, tariff.sesongfaktor) for kw, dato in ukestopper), reverse=True)[
            :FEM_VEKTET_ANTALL_TOPPER
        ]
        if not vektet:
            return 0.0
        # Nettselskapet fakturerer effekten med to desimaler.
        return round(sum(vektet) / len(vektet), 2)
    topp = sorted(doegnmaks_kw, reverse=True)[:3]
    if not topp:
        return 0.0
    return sum(topp) / len(topp)


def utenfor_kildegrense(tariff: Fastleddtariff, grunnlag_kw: float) -> bool:
    """Om grunnlaget ligger der kilden ikke oppgir noe beløp."""
    grense = tariff.kildegrense_kw
    if grense is None:
        return False
    return grunnlag_kw > grense or (grunnlag_kw == grense and not tariff.kildegrense_inkludert)


def fastledd_ukjent(tariff: Fastleddtariff, grunnlag_kw: float) -> bool:
    """Om fastleddet er ukjent fordi ingen kjenner trinnene.

    Gjelder manglende trinntabell og fakturagrunnlag utenfor den
    kildebekreftede tariffen. Sensorer som bygger på fastleddet blir ukjent,
    framfor et plausibelt beløp uten kilde.
    """
    return (tariff.metode in FASTLEDD_TRINNBASERTE and not tariff.trinn) or utenfor_kildegrense(
        tariff, grunnlag_kw
    )


def fastledd_belop_ukjent(tariff: Fastleddtariff, grunnlag_kw: float) -> bool:
    """Om månedens fastleddbeløp er ukjent, av trinnene eller sikringsvalget."""
    return fastledd_ukjent(tariff, grunnlag_kw) or (
        tariff.metode == FASTLEDD_OV_TREFASE and tariff.sikringstrinn is None
    )


def lineart_fastledd(tariff: Fastleddtariff, grunnlag_kw: float) -> int:
    """Fastledd i kr/mnd inkl. mva for grunnbeløp + sats per kW."""
    if not tariff.lineaer:
        return 0
    aar_eks_mva = (
        tariff.lineaer["grunnbelop_aar_eks_mva"] + tariff.lineaer["sats_kw_aar_eks_mva"] * grunnlag_kw
    )
    maaned = aar_eks_mva / 12 * (1 + tariff.mva_sats)
    # Denne lineære metoden runder halve kroner opp. Innebygd round() gjør bankers
    # rounding og ville gitt 453 der nettselskapet fakturerer 453,75.
    return int(Decimal(maaned).quantize(Decimal(1), ROUND_HALF_UP))


def fastledd_for_grunnlag(tariff: Fastleddtariff, grunnlag_kw: float) -> tuple[float, int | None, str]:
    """Fastledd i kr/mnd for et effektgrunnlag.

    Returns: (pris, trinnummer, trinnbeskrivelse). Trinnummer er None der
    nettselskapet ikke har trinn, eller der sikringsstørrelsen mangler.
    """
    if fastledd_ukjent(tariff, grunnlag_kw):
        # Ingen gjetning: uten kildebekreftede trinn finnes det ikke noe
        # beløp å slå opp, og 0 her betyr «regnet uten fastledd», ikke
        # «fastleddet er null». Sensorene viser Ukjent.
        return 0, None, FASTLEDD_UKJENT_TEKST

    if tariff.metode == FASTLEDD_OV_TREFASE:
        if tariff.sikringstrinn is None:
            # Ingen gjetning: sikringsstørrelse kan ikke leses av en
            # effektsensor, og et plausibelt beløp ville skjult feilen.
            return 0, None, SIKRINGSVALG_MANGLER_TEKST
        nummer, trinn = tariff.sikringstrinn
        return trinn["kr_mnd"], nummer, trinn["label"]

    if tariff.metode == FASTLEDD_FEM_VEKTET_AR:
        return lineart_fastledd(tariff, grunnlag_kw), None, f"{grunnlag_kw:.2f} kW vektet årstopp"

    return finn_kapasitetstrinn(list(tariff.trinn), grunnlag_kw, tariff.terskel_inkludert)
