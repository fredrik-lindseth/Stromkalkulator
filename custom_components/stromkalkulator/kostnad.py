"""Kostnadskjernen: kroner per komponent for ett avregnet intervall.

Modulen er ren på samme måte som `avregning.py`: stdlib, `const` og
`avregning`, ingenting fra Home Assistant. Den vet ingenting om Store,
entiteter eller polling. Den får et ferdig avregnet intervall, satsene som
gjaldt der, og hvor mange kilowattimer måneden hadde bak seg da intervallet
begynte, og svarer med kroner.

To regler styrer resten:

- **Kroner regnes per intervall, ikke per poll.** Prisen er intervallets egen
  (A2.1 i avregningskontrakten), ikke den som sto på sensoren da vi spurte.
- **Fastledd er et periodebeløp.** Det er kroner per måned, ikke kroner per
  kilowattime, og det ganges derfor aldri med energi. Grenseflaten er
  `forlopt_andel_av_maaned` og `fastledd_belop`, og den tar tid inn og kroner
  ut. Sammenlign `kapasitetsledd_per_kwh` i data-dicten: den er en visningssats
  for Energy Dashboard, og ingen krone i denne modulen kommer fra den.

Alle beløp er inkl. mva, samme enhet som `spot_price` og
`NORGESPRIS_INKL_MVA` bruker ellers i integrasjonen (incident 004).

Tak-splitten er kontraktens 234odp5: krysser et intervall taket for
strømstøtte eller Norgespris, deles kilowattimene i én del under og én over
taket *før* prisen legges på. Det gjelder også det store deltaet som kommer
inn etter et sensorutfall, der hele timer kan lande i ett intervall.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from .avregning import OSLO, Tariff, krev_aware, varighet_sekunder
from .const import STROMSTOTTE_RATE

if TYPE_CHECKING:
    from .avregning import AvregnetIntervall

__all__ = [
    "Kroner",
    "Satser",
    "fastledd_belop",
    "forlopt_andel_av_maaned",
    "kroner_for_intervall",
    "maanedsvindu",
    "sekunder_forlopt_i_dogn",
    "stromstotte_per_kwh",
]

#: Slakken i identiteten «summen av delene er helheten». Ren flyttallsstøy.
SUM_SLAKK_KR: Final[float] = 1e-9


@dataclass(frozen=True, slots=True)
class Satser:
    """Satsene som gjaldt i ett avregnet intervall. Alt inkl. mva.

    `energiledd_inkl_mva` er tallet `dso.py` leverer, altså nettleiens
    energiledd med forbruksavgift og Enova oppi. `avgifter_inkl_mva` er den
    delen av det som er offentlige avgifter, slik at de to kan skilles i
    bokføringen uten at noen regner energileddet to ganger.
    """

    energiledd_inkl_mva: float
    avgifter_inkl_mva: float
    mva_sats: float
    norgespris_inkl_mva: float
    stromstotte_terskel: float
    stromstotte_max_kwh: float
    norgespris_max_kwh: float
    har_norgespris: bool

    @property
    def nett_energiledd_inkl_mva(self) -> float:
        """Energileddet uten de offentlige avgiftene.

        Negativt er ikke mulig med satser fra katalogen, men en overstyring
        under avgiftsnivået ville gitt det, og da er null det ærlige svaret:
        avgiftene er uansett det brukeren betaler.
        """
        return max(0.0, self.energiledd_inkl_mva - self.avgifter_inkl_mva)


@dataclass(frozen=True, slots=True)
class Kroner:
    """Kroner per komponent for ett intervall, eller en sum av flere.

    `strom_kr` er det kunden faktisk betaler for kraften, altså etter
    strømstøtte og etter Norgespris der den gjelder. `stromstotte_kr` står ved
    siden av som opplysning om hvor mye støtten utgjorde, ikke som et fradrag
    som skal trekkes en gang til.
    """

    strom_kr: float = 0.0
    stromstotte_kr: float = 0.0
    energiledd_dag_kr: float = 0.0
    energiledd_natt_kr: float = 0.0
    avgifter_kr: float = 0.0
    norgespris_kompensasjon_kr: float = 0.0
    norgespris_differanse_kr: float = 0.0
    kwh: float = 0.0
    kwh_uten_pris: float = 0.0

    @property
    def energiledd_kr(self) -> float:
        """Nettleiens energidel med offentlige avgifter.

        Dette er tallet `monthly_accumulated_cost_energiledd_kr` har vist hele
        tiden. Navnet er upresist, og feltene over er splitten som gjør det
        etterprøvbart framfor å bytte betydningen på et felt brukerne har
        statistikk på.
        """
        return self.energiledd_dag_kr + self.energiledd_natt_kr + self.avgifter_kr

    @property
    def energi_kr(self) -> float:
        """Alt som følger kilowattimene. Fastledd er ikke med; det er en periode."""
        return self.strom_kr + self.energiledd_kr

    def __add__(self, annen: Kroner) -> Kroner:
        return Kroner(*(getattr(self, f.name) + getattr(annen, f.name) for f in fields(self)))

    def __sub__(self, annen: Kroner) -> Kroner:
        return Kroner(*(getattr(self, f.name) - getattr(annen, f.name) for f in fields(self)))


#: Nullpunktet. Et intervall som ikke har bidratt med noe før, har bidratt med dette.
INGEN_KRONER: Final[Kroner] = Kroner()


def stromstotte_per_kwh(spot_inkl_mva: float, terskel: float) -> float:
    """Strømstøtte i kr/kWh for en gitt timepris.

    Forskrift § 5: 90 % av det spotprisen overstiger terskelen med. Terskelen
    er sonebevisst (incident 005) og kommer inn ferdig valgt.
    """
    if spot_inkl_mva <= terskel:
        return 0.0
    return (spot_inkl_mva - terskel) * STROMSTOTTE_RATE


def _under_tak(kwh: float, kwh_for: float, tak: float) -> float:
    """Hvor mange av intervallets kilowattimer som ligger under et månedstak.

    `kwh_for` er måneden bak intervallet. Et tak på 0 betyr at ordningen ikke
    gjelder i det hele tatt (fritidsbolig uten strømstøtte), ikke at alt er
    over taket med en gang.
    """
    if tak <= 0:
        return 0.0
    return min(kwh, max(0.0, tak - kwh_for))


def kroner_for_intervall(
    intervall: AvregnetIntervall,
    satser: Satser,
    *,
    kwh_for: float = 0.0,
) -> Kroner:
    """Kronene ett avregnet intervall står for.

    `kwh_for` er månedens kilowattimer før dette intervallet, og er det som
    avgjør hvor takene for strømstøtte og Norgespris faller inne i intervallet.

    Et intervall uten pris gir ingen kroner for kraften (C4: aldri null, aldri
    naboens pris), men energiledd og avgifter regnes like fullt. De avhenger av
    tariffen og datoen, ikke av spotprisen, og den vet vi.
    """
    kwh = intervall.kwh
    if kwh <= 0:
        return INGEN_KRONER

    dag = intervall.tariff is Tariff.DAG
    nett_energiledd = satser.nett_energiledd_inkl_mva * kwh
    grunn = Kroner(
        energiledd_dag_kr=nett_energiledd if dag else 0.0,
        energiledd_natt_kr=0.0 if dag else nett_energiledd,
        avgifter_kr=satser.avgifter_inkl_mva * kwh,
        kwh=kwh,
    )

    pris_eks_mva = intervall.nok_per_kwh_eks_mva
    if pris_eks_mva is None:
        # Kilowattimene er kjent, prisen er det ikke. De står synlig i
        # `kwh_uten_pris` framfor å bli priset med noe vi ikke har.
        return replace(grunn, kwh_uten_pris=kwh)

    spot = pris_eks_mva * (1 + satser.mva_sats)
    stotte_sats = stromstotte_per_kwh(spot, satser.stromstotte_terskel)
    kwh_med_stotte = _under_tak(kwh, kwh_for, satser.stromstotte_max_kwh)
    kwh_med_norgespris = _under_tak(kwh, kwh_for, satser.norgespris_max_kwh)

    spot_etter_stotte = spot * kwh - stotte_sats * kwh_med_stotte
    norgespris_linje = satser.norgespris_inkl_mva * kwh_med_norgespris + spot * (kwh - kwh_med_norgespris)

    if satser.har_norgespris:
        # Norgespris-kunder mottar ikke strømstøtte. Beløpet regnes likevel, for
        # sammenligningen mot alternativet er hele poenget med de to feltene.
        strom_kr = norgespris_linje
        stromstotte_kr = 0.0
    else:
        strom_kr = spot_etter_stotte
        stromstotte_kr = stotte_sats * kwh_med_stotte

    # Begge differansefeltene har samme fortegnsregel: alternativet minus det du
    # faktisk betaler. Positivt betyr at avtalen du har er den billigste.
    alternativ = spot_etter_stotte if satser.har_norgespris else norgespris_linje

    return Kroner(
        strom_kr=strom_kr,
        stromstotte_kr=stromstotte_kr,
        energiledd_dag_kr=grunn.energiledd_dag_kr,
        energiledd_natt_kr=grunn.energiledd_natt_kr,
        avgifter_kr=grunn.avgifter_kr,
        norgespris_kompensasjon_kr=(satser.norgespris_inkl_mva - spot) * kwh_med_norgespris,
        norgespris_differanse_kr=alternativ - strom_kr,
        kwh=kwh,
    )


# ---------------------------------------------------------------------------
# Fastledd: periodebeløp, ikke pris per kilowattime


def maanedsvindu(naa: datetime) -> tuple[datetime, datetime]:
    """Fakturamånedens start og slutt i UTC, for tidspunktet `naa`.

    Grensene settes i Europe/Oslo, for det er kalendermåneden nettselskapet
    fakturerer (A1, C3), og regnes deretter om til UTC slik at all varighet
    kan måles i absolutt tid.
    """
    lokal = krev_aware(naa, "naa").astimezone(OSLO)
    start = datetime(lokal.year, lokal.month, 1, tzinfo=OSLO)
    aar, mnd = (lokal.year + 1, 1) if lokal.month == 12 else (lokal.year, lokal.month + 1)
    slutt = datetime(aar, mnd, 1, tzinfo=OSLO)
    return start.astimezone(UTC), slutt.astimezone(UTC)


def forlopt_andel_av_maaned(naa: datetime) -> float:
    """Hvor stor del av fakturamåneden som er gått, mellom 0 og 1.

    Regnet i absolutt tid, så mars (743 timer) og oktober (745 timer) er ikke
    spesialtilfeller: nevneren er sekundene måneden faktisk har (3jebp9g).
    """
    start, slutt = maanedsvindu(naa)
    lengde = varighet_sekunder(start, slutt)
    if lengde <= 0:  # pragma: no cover - en måned uten lengde finnes ikke
        return 0.0
    gatt = varighet_sekunder(start, krev_aware(naa, "naa"))
    return min(1.0, max(0.0, gatt / lengde))


def sekunder_forlopt_i_dogn(naa: datetime) -> float:
    """Sekunder gått siden lokal midnatt, i absolutt tid.

    Døgnet med sommertidsskifte er 23 eller 25 timer langt, og det er det
    denne måler. Brukes til dagens andel av månedens fastledd.
    """
    lokal = krev_aware(naa, "naa").astimezone(OSLO)
    midnatt = datetime(lokal.year, lokal.month, lokal.day, tzinfo=OSLO)
    return max(0.0, varighet_sekunder(midnatt, lokal))


def sekunder_i_maaned(naa: datetime) -> float:
    """Sekundene fakturamåneden faktisk varer."""
    start, slutt = maanedsvindu(naa)
    return varighet_sekunder(start, slutt)


def fastledd_belop(kapasitetsledd: float | None, andel: float) -> float:
    """Fastleddet for en andel av måneden, i kroner.

    `kapasitetsledd` er kr/mnd. `None` er «ingen kjenner trinnet» (Egendefinert
    uten trinntabell, kontrakt §9), og da er beløpet null kroner, ikke et
    plausibelt tall uten kilde (incident 006). At det er ukjent sies av
    `fastledd_ukjent`, ikke av beløpet.

    Fylles trinntabellen inn den 20., gir dette hele månedens forløpte andel
    med en gang. Det er meningen: fastleddet påløper hele måneden, og et
    beløp som bare dekker dagene etter innfyllingen ville vært et stille hull
    i fakturaestimatet.
    """
    if kapasitetsledd is None:
        return 0.0
    return kapasitetsledd * min(1.0, max(0.0, andel))


def andel_av_maaned(sekunder: float, naa: datetime) -> float:
    """Så stor del av fakturamåneden et antall sekunder utgjør."""
    lengde = sekunder_i_maaned(naa)
    if lengde <= 0:  # pragma: no cover
        return 0.0
    return min(1.0, max(0.0, sekunder / lengde))
