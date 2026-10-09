"""Eksportenergi prises i sin egen UTC-prisrute, aldri med naboens pris.

De siste tre timene beholdes for nye prøver og omstart. Eldre ruter foldes
inn i månedsbalanser med både kjent inntekt og energi uten prisgrunnlag.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from .avregning import LAGRINGSVINDU, Prisadapter, intervallstart, krev_aware, lokal_maned, prisrutestart

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass
class Eksportsum:
    """Kjent inntekt er en subtotal når noe av energien mangler pris."""

    kwh: float = 0.0
    inntekt_kr: float = 0.0
    kwh_uten_pris: float = 0.0


class Eksportbok:
    """En egen prisadapter lar eksporten overleve forbruksbokens rullering."""

    def __init__(self, pris: Prisadapter | None = None) -> None:
        self.pris = pris if pris is not None else Prisadapter()
        self._energi: dict[datetime, float] = {}
        self._ferdige: dict[str, Eksportsum] = {}

    def registrer_pris(self, avlest_kl: datetime, pris_eks_mva: float) -> None:
        """Samme godkjenningsregler som for forbruk; null og negativt er priser."""
        self.pris.registrer(avlest_kl, pris_eks_mva)

    def bokfor(self, fra: datetime, til: datetime, kwh: float) -> None:
        """Fordel effektmålingens energi etter faktisk tid i hver prisrute."""
        start = krev_aware(fra, "fra").astimezone(UTC)
        slutt = krev_aware(til, "til").astimezone(UTC)
        sekunder = (slutt - start).total_seconds()
        if sekunder <= 0 or kwh <= 0:
            return
        steg = timedelta(minutes=self.pris.opplosning_minutter)
        naa = start
        while naa < slutt:
            rute = prisrutestart(naa, self.pris.opplosning_minutter)
            ende = min(slutt, rute + steg)
            andel = kwh * (ende - naa).total_seconds() / sekunder
            self._energi[rute] = self._energi.get(rute, 0.0) + andel
            naa = ende

    def _bidrag(self, rute: datetime, kwh: float) -> Eksportsum:
        pris = self.pris.ruter_i(intervallstart(rute)).get(rute)
        return Eksportsum(
            kwh=kwh,
            inntekt_kr=kwh * pris if pris is not None else 0.0,
            kwh_uten_pris=kwh if pris is None else 0.0,
        )

    def maaned(self, maaned: str) -> Eksportsum:
        """Regn beholdte ruter på nytt når samme rute får en nyere prisprøve."""
        fast = self._ferdige.get(maaned, Eksportsum())
        svar = Eksportsum(**asdict(fast))
        for rute, kwh in self._energi.items():
            if lokal_maned(rute) == maaned:
                bidrag = self._bidrag(rute, kwh)
                svar.kwh += bidrag.kwh
                svar.inntekt_kr += bidrag.inntekt_kr
                svar.kwh_uten_pris += bidrag.kwh_uten_pris
        return svar

    def sett_apning(
        self, maaned: str, kwh: float, inntekt_kr: float, *, prisdekning_ukjent: bool = False
    ) -> None:
        """Tidligere lagrede summer beholdes uten å finne på intervallhistorikk."""
        self._ferdige[maaned] = Eksportsum(
            kwh=kwh, inntekt_kr=inntekt_kr, kwh_uten_pris=kwh if prisdekning_ukjent else 0.0
        )

    def avslutt_eldre(self, naa: datetime) -> None:
        """Fold inn gamle ruter før prisene slippes; ukjent energi beholdes."""
        grense = prisrutestart(krev_aware(naa, "naa")) - LAGRINGSVINDU
        for rute in list(self._energi):
            if rute < grense:
                bidrag = self._bidrag(rute, self._energi.pop(rute))
                fast = self._ferdige.setdefault(lokal_maned(rute), Eksportsum())
                fast.kwh += bidrag.kwh
                fast.inntekt_kr += bidrag.inntekt_kr
                fast.kwh_uten_pris += bidrag.kwh_uten_pris
        self.pris.glem_for(grense)

    def til_lagring(self) -> dict[str, Any]:
        """Separat nøkkel i samme entry-bundne Store som forbruksboken."""
        return {
            "pris": self.pris.til_lagring(),
            "energi": [{"start": rute.isoformat(), "kwh": kwh} for rute, kwh in sorted(self._energi.items())],
            "ferdige": {maaned: asdict(sum_) for maaned, sum_ in self._ferdige.items()},
        }

    @classmethod
    def fra_lagring(cls, raa: Mapping[str, Any]) -> Eksportbok:
        """Gjenopprett energi og dens egne prøver, også prisgap og minusinntekt."""

        def tall(verdi: Any, *, signert: bool = False) -> float:
            svar = float(verdi)
            if not math.isfinite(svar) or (not signert and svar < 0):
                raise ValueError("ugyldig eksportbeløp")
            return svar

        def tidspunkt(verdi: str) -> datetime:
            return krev_aware(datetime.fromisoformat(verdi), "lagret eksporttid").astimezone(UTC)

        # Prisadapteren deles med forbruksboken. Valider eksportens lagrede
        # prøver her, så en skadet prøve ikke blir NaN eller en naiv tidsnøkkel.
        for rad in raa["pris"].get("ruter", []):
            tidspunkt(rad["rutestart"])
            tidspunkt(rad["polltid"])
            tall(rad["verdi"], signert=True)
        bok = cls(Prisadapter.fra_lagring(raa["pris"]))
        bok._energi = {tidspunkt(rad["start"]): tall(rad["kwh"]) for rad in raa["energi"]}
        for maaned, sum_ in raa["ferdige"].items():
            if not isinstance(maaned, str) or len(maaned) != 7:
                raise ValueError("ugyldig eksportmåned")
            datetime.fromisoformat(f"{maaned}-01")
            kwh = tall(sum_["kwh"])
            uten_pris = tall(sum_["kwh_uten_pris"])
            if uten_pris > kwh + 1e-9:
                raise ValueError("prisgap større enn eksportenergien")
            bok._ferdige[maaned] = Eksportsum(kwh, tall(sum_["inntekt_kr"], signert=True), uten_pris)
        return bok
