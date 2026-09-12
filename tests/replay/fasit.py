"""Uavhengig fasit for avregningen, regnet rett fra hendelsene.

Dette er en andre implementasjon av `docs/kontrakter/avregning.md`, skrevet
for å være uenig med produksjonskoden når produksjonskoden tar feil. Den
importerer derfor ikke `custom_components/` i det hele tatt, verken
`avregning.py` eller `const.py`, og satsene står som tall i `Satser` under.
Tallene er de samme som `scripts/research/verify_invoice_hourly.py` bruker,
altså de som er etterprøvd mot ekte BKK-fakturaer, ikke de som er lest ut av
`dso.py`. En sats som driver i `dso.py` skal gi rødt her, ikke grønt.

Bare stdlib. Ingen HA, ingen pytest, ingen produksjonsimport.

Hva den kan:

* `Fasit.bokfor(observed_at, teller_kwh)` tar en avlesning av en kumulativ
  teller, regner deltaet mot forrige og fordeler det jevnt over tid på
  UTC-timene vinduet dekker (C1).
* `Fasit.prisprove(avlest_kl, verdi)` tar en prisavlesning og tilordner den
  prisruten polltiden faller i, hvis polltiden ligger minst
  `PRIS_SETTLE_SEKUNDER` etter rutestart (A2.1).
* `Fasit.avregning()` summerer kronene per felt i felttabellen: energiledd
  dag og natt, forbruksavgift, enova, Norgespris eller strømstøtte, og
  fastledd for seg.

Hva den ikke gjør: den kjenner ikke poll som begrep utover prisrutene, og den
har ingen tilstand som avhenger av rekkefølgen hendelsene kommer i utover
telleren selv. Det er hele poenget: er fasiten og coordinatoren uenige om et
tall, er det coordinatoren som har latt polltiden bestemme.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

OSLO = ZoneInfo("Europe/Oslo")

AVREGNINGSINTERVALL_MINUTTER = 60
PRISRUTE_MINUTTER = 15
PRIS_SETTLE_SEKUNDER = 60

# Grensene fra const.py, gjentatt her fordi fasiten ikke importerer den.
MAX_ENERGY_DELTA_KWH = 100.0

BEVARING_SLAKK_KWH = 1e-9


class Kvalitet(StrEnum):
    """Priskvaliteten på et avregnet intervall (B3)."""

    KOMPLETT = "komplett"
    DELVIS_PRIS = "delvis_pris"
    UTEN_PRIS = "uten_pris"


class Tariff(StrEnum):
    DAG = "dag"
    NATT = "natt"


class Utfall(StrEnum):
    """Hva som skjedde med en avlesning."""

    BOKFORT = "bokfort"
    BASELINE = "baseline"
    DUPLIKAT = "duplikat"
    FORSINKET = "forsinket"
    NULLVINDU = "nullvindu"
    NEGATIVT = "negativt"
    FOR_STORT = "for_stort"


# BKK 2026, inkl. mva der ikke annet står. Kilde: fakturaene i docs/fakturaer/
# og tabellen i scripts/research/verify_invoice_hourly.py.
BKK_KAPASITETSTRINN_2026: tuple[tuple[float, int], ...] = (
    (2.0, 155),
    (5.0, 250),
    (10.0, 415),
    (15.0, 600),
    (20.0, 770),
    (25.0, 940),
    (50.0, 1800),
    (75.0, 2650),
    (100.0, 3500),
    (float("inf"), 6900),
)

HELLIGDAGER_2026: frozenset[date] = frozenset(
    {
        date(2026, 1, 1),
        date(2026, 4, 2),
        date(2026, 4, 3),
        date(2026, 4, 5),
        date(2026, 4, 6),
        date(2026, 5, 1),
        date(2026, 5, 14),
        date(2026, 5, 17),
        date(2026, 5, 24),
        date(2026, 5, 25),
        date(2026, 12, 25),
        date(2026, 12, 26),
    }
)


@dataclass(frozen=True, slots=True)
class Satser:
    """Alt fasiten trenger å vite om avtale, nettselskap og avgiftsår."""

    energiledd_dag_inkl_mva: float = 0.35963
    energiledd_natt_inkl_mva: float = 0.13125
    forbruksavgift_inkl_mva: float = 0.08913
    enova_inkl_mva: float = 0.0125
    mva_faktor: float = 1.25
    dag_fra_time: int = 6
    dag_til_time: int = 22
    helligdager: frozenset[date] = HELLIGDAGER_2026
    kapasitetstrinn: tuple[tuple[float, int], ...] = BKK_KAPASITETSTRINN_2026

    # Avtale. Enten Norgespris eller strømstøtte, aldri begge.
    har_norgespris: bool = True
    norgespris_inkl_mva: float = 0.50
    norgespris_maks_kwh: int = 5000
    stromstotte_terskel_inkl_mva: float = 0.9625
    stromstotte_andel: float = 0.90
    stromstotte_maks_kwh: int = 5000

    def tariff(self, start_utc: datetime) -> Tariff:
        """Dag eller natt, avgjort av intervallets start i Europe/Oslo (A1)."""
        lokal = start_utc.astimezone(OSLO)
        if lokal.weekday() >= 5 or lokal.date() in self.helligdager:
            return Tariff.NATT
        if self.dag_fra_time <= lokal.hour < self.dag_til_time:
            return Tariff.DAG
        return Tariff.NATT

    def kapasitetsledd(self, snitt_kw: float) -> tuple[int, float]:
        """(kr/mnd, trinngrense) for et snitt av de tre høyeste døgnmaksene."""
        for grense, kr in self.kapasitetstrinn:
            if snitt_kw <= grense:
                return kr, grense
        kr, grense = self.kapasitetstrinn[-1][1], self.kapasitetstrinn[-1][0]
        return kr, grense


def krev_aware(tidspunkt: datetime, hva: str = "tidspunkt") -> datetime:
    """Kast på naiv datetime. En naiv tid er en programmeringsfeil (B1)."""
    if tidspunkt.tzinfo is None or tidspunkt.tzinfo.utcoffset(tidspunkt) is None:
        raise ValueError(f"{hva} må være tidssoneklar, fikk {tidspunkt!r}")
    return tidspunkt.astimezone(UTC)


def intervallstart(tidspunkt: datetime) -> datetime:
    """UTC-starten på avregningsintervallet tidspunktet ligger i."""
    utc = krev_aware(tidspunkt)
    return utc.replace(minute=0, second=0, microsecond=0)


def prisrutestart(tidspunkt: datetime, opplosning_minutter: int = PRISRUTE_MINUTTER) -> datetime:
    """UTC-starten på prisruten tidspunktet ligger i (A2.1)."""
    utc = krev_aware(tidspunkt)
    minutt = (utc.minute // opplosning_minutter) * opplosning_minutter
    return utc.replace(minute=minutt, second=0, microsecond=0)


def fordel_delta(fra: datetime, til: datetime, delta_kwh: float) -> dict[datetime, float]:
    """Fordel et målerdelta jevnt over tid på intervallene `(fra, til]` dekker.

    Regnet på epoch-sekunder, aldri på veggklokken, så sommertidsskiftene er
    vanlige timer (C3). Summen av verdiene er `delta_kwh` innenfor
    flyttallsslakk (C2.1).
    """
    fra = krev_aware(fra, "fra")
    til = krev_aware(til, "til")
    spenn = til.timestamp() - fra.timestamp()
    if spenn <= 0:
        return {}

    ut: dict[datetime, float] = {}
    kant = intervallstart(fra)
    while kant < til:
        neste = kant + timedelta(minutes=AVREGNINGSINTERVALL_MINUTTER)
        overlapp_start = max(kant.timestamp(), fra.timestamp())
        overlapp_slutt = min(neste.timestamp(), til.timestamp())
        sekunder = overlapp_slutt - overlapp_start
        if sekunder > 0:
            ut[kant] = ut.get(kant, 0.0) + delta_kwh * sekunder / spenn
        kant = neste
    return ut


@dataclass(frozen=True, slots=True)
class FasitIntervall:
    """Ett avregnet intervall, felt for felt etter B3."""

    start_utc: datetime
    kwh: float
    pris_nok_per_kwh_eks_mva: float | None
    pris_prover: int
    pris_prover_ventet: int
    tariff: Tariff
    kvalitet: Kvalitet

    @property
    def slutt_utc(self) -> datetime:
        return self.start_utc + timedelta(minutes=AVREGNINGSINTERVALL_MINUTTER)

    @property
    def lokal(self) -> datetime:
        return self.start_utc.astimezone(OSLO)

    @property
    def lokal_maned(self) -> str:
        return self.lokal.strftime("%Y-%m")

    @property
    def lokal_dato(self) -> str:
        return self.lokal.strftime("%Y-%m-%d")

    @property
    def lokal_time(self) -> int:
        return self.lokal.hour


@dataclass(frozen=True, slots=True)
class Avregning:
    """Summen av en måned, felt for felt etter felttabellen i A0."""

    maned: str
    kwh_total: float
    kwh_dag: float
    kwh_natt: float
    kwh_uten_pris: float
    kwh_delvis_pris: float
    avvist_kwh: float
    energiledd_dag_kr: float
    energiledd_natt_kr: float
    forbruksavgift_kr: float
    enovaavgift_kr: float
    stotte_kr: float
    kapasitetsledd_kr: float
    kapasitet_snitt_kw: float
    kapasitet_grense_kw: float
    intervaller: int

    @property
    def nettleie_kr(self) -> float:
        """Energiledd + avgifter + fastledd, altså BKKs nettleielinje."""
        return (
            self.energiledd_dag_kr
            + self.energiledd_natt_kr
            + self.forbruksavgift_kr
            + self.enovaavgift_kr
            + self.kapasitetsledd_kr
        )

    @property
    def total_kr(self) -> float:
        return self.nettleie_kr + self.stotte_kr


@dataclass(slots=True)
class _Bokfort:
    kwh: float = 0.0


class Fasit:
    """Bok som tar imot avlesninger og prisprøver og regner fasiten."""

    def __init__(
        self,
        satser: Satser | None = None,
        *,
        opplosning_minutter: int = PRISRUTE_MINUTTER,
        maks_delta_kwh: float = MAX_ENERGY_DELTA_KWH,
    ) -> None:
        self.satser = satser or Satser()
        self.opplosning_minutter = opplosning_minutter
        self.maks_delta_kwh = maks_delta_kwh
        self._poster: dict[datetime, _Bokfort] = {}
        self._ruter: dict[datetime, float] = {}
        self._sist: tuple[datetime, float] | None = None
        self._avvist_kwh = 0.0
        self.utfall: list[Utfall] = []

    # -- pris ------------------------------------------------------------

    def prisprove(self, avlest_kl: datetime, verdi: float | None) -> datetime | None:
        """Registrer en prisavlesning. Returner ruten den traff, eller None.

        Reglene er A2.1: ruten er den polltiden faller i, prøven må ligge minst
        `PRIS_SETTLE_SEKUNDER` etter rutestart, og siste godkjente prøve i en
        rute er den som gjelder.
        """
        if verdi is None:
            return None
        avlest_kl = krev_aware(avlest_kl, "avlest_kl")
        rute = prisrutestart(avlest_kl, self.opplosning_minutter)
        if avlest_kl.timestamp() - rute.timestamp() < PRIS_SETTLE_SEKUNDER:
            return None
        self._ruter[rute] = verdi
        return rute

    def _pris_for(self, start_utc: datetime) -> tuple[float | None, int]:
        """Uvektet snitt av rutene med prøve, og antall slike ruter."""
        slutt = start_utc + timedelta(minutes=AVREGNINGSINTERVALL_MINUTTER)
        verdier = [v for r, v in self._ruter.items() if start_utc <= r < slutt]
        if not verdier:
            return None, 0
        return sum(verdier) / len(verdier), len(verdier)

    @property
    def prover_ventet(self) -> int:
        return AVREGNINGSINTERVALL_MINUTTER // self.opplosning_minutter

    # -- energi ----------------------------------------------------------

    def bokfor(self, observed_at: datetime, teller_kwh: float) -> Utfall:
        """Bokfør en avlesning av den kumulative telleren (B1, C1, C2)."""
        observed_at = krev_aware(observed_at, "observed_at")
        if self._sist is None:
            self._sist = (observed_at, teller_kwh)
            return self._noter(Utfall.BASELINE)

        forrige_tid, forrige_verdi = self._sist
        if observed_at == forrige_tid and teller_kwh == forrige_verdi:
            return self._noter(Utfall.DUPLIKAT)
        if observed_at < forrige_tid:
            return self._noter(Utfall.FORSINKET)
        if observed_at == forrige_tid:
            # Samme observasjonstid, ulik teller: vinduet har lengde null (C1).
            return self._noter(Utfall.NULLVINDU)

        delta = teller_kwh - forrige_verdi
        if delta < 0:
            self._sist = (observed_at, teller_kwh)
            return self._noter(Utfall.NEGATIVT)
        if delta >= self.maks_delta_kwh:
            self._avvist_kwh += delta
            self._sist = (observed_at, teller_kwh)
            return self._noter(Utfall.FOR_STORT)

        for start, kwh in fordel_delta(forrige_tid, observed_at, delta).items():
            self._poster.setdefault(start, _Bokfort()).kwh += kwh
        self._sist = (observed_at, teller_kwh)
        return self._noter(Utfall.BOKFORT)

    def bokfor_intervall(self, start_utc: datetime, kwh: float) -> None:
        """Legg energi rett i ett intervall, uten teller.

        Brukes når fasiten mates fra Elhubs intervallenergi, der kilowattimene
        allerede er fordelt av nettselskapet. Går utenom C1, for det er ikke en
        avlesning; det er fasiten C1 skal treffe.
        """
        self._poster.setdefault(intervallstart(start_utc), _Bokfort()).kwh += kwh

    def _noter(self, utfall: Utfall) -> Utfall:
        self.utfall.append(utfall)
        return utfall

    # -- resultat --------------------------------------------------------

    def intervaller(self) -> list[FasitIntervall]:
        """Alle bokførte intervaller, sortert på UTC-start."""
        ut: list[FasitIntervall] = []
        for start in sorted(self._poster):
            pris, prover = self._pris_for(start)
            if prover == 0:
                kvalitet = Kvalitet.UTEN_PRIS
            elif prover < self.prover_ventet:
                kvalitet = Kvalitet.DELVIS_PRIS
            else:
                kvalitet = Kvalitet.KOMPLETT
            ut.append(
                FasitIntervall(
                    start_utc=start,
                    kwh=self._poster[start].kwh,
                    pris_nok_per_kwh_eks_mva=pris,
                    pris_prover=prover,
                    pris_prover_ventet=self.prover_ventet,
                    tariff=self.satser.tariff(start),
                    kvalitet=kvalitet,
                )
            )
        return ut

    def avregning(self, maned: str | None = None) -> Avregning:
        """Summer kronene for én fakturamåned (default: den eneste som finnes)."""
        alle = self.intervaller()
        maneder = {i.lokal_maned for i in alle}
        if maned is None:
            if len(maneder) > 1:
                raise ValueError(f"Flere måneder i boken: {sorted(maneder)}. Oppgi hvilken.")
            maned = next(iter(maneder), "")
        rader = [i for i in alle if i.lokal_maned == maned]
        return self._summer(maned, rader)

    def _summer(self, maned: str, rader: list[FasitIntervall]) -> Avregning:
        s = self.satser
        kwh_dag = sum(i.kwh for i in rader if i.tariff is Tariff.DAG)
        kwh_natt = sum(i.kwh for i in rader if i.tariff is Tariff.NATT)
        kwh_total = kwh_dag + kwh_natt

        # Fastledd: BKK tar snittet av de tre høyeste døgnmaksene, og
        # døgnmaksen er den høyeste timesenergien det døgnet (kWh/h = kW).
        maks_per_dato: dict[str, float] = {}
        for i in rader:
            if i.kwh > maks_per_dato.get(i.lokal_dato, 0.0):
                maks_per_dato[i.lokal_dato] = i.kwh
        topp3 = sorted(maks_per_dato.values(), reverse=True)[:3]
        snitt_kw = sum(topp3) / len(topp3) if topp3 else 0.0
        kap_kr, kap_grense = s.kapasitetsledd(snitt_kw)

        stotte = self._stotte(rader)

        return Avregning(
            maned=maned,
            kwh_total=kwh_total,
            kwh_dag=kwh_dag,
            kwh_natt=kwh_natt,
            kwh_uten_pris=sum(i.kwh for i in rader if i.kvalitet is Kvalitet.UTEN_PRIS),
            kwh_delvis_pris=sum(i.kwh for i in rader if i.kvalitet is Kvalitet.DELVIS_PRIS),
            avvist_kwh=self._avvist_kwh,
            energiledd_dag_kr=kwh_dag * s.energiledd_dag_inkl_mva,
            energiledd_natt_kr=kwh_natt * s.energiledd_natt_inkl_mva,
            forbruksavgift_kr=kwh_total * s.forbruksavgift_inkl_mva,
            enovaavgift_kr=kwh_total * s.enova_inkl_mva,
            stotte_kr=stotte,
            kapasitetsledd_kr=float(kap_kr),
            kapasitet_snitt_kw=snitt_kw,
            kapasitet_grense_kw=kap_grense,
            intervaller=len(rader),
        )

    def _stotte(self, rader: list[FasitIntervall]) -> float:
        """Norgespris-kompensasjon eller strømstøtte, i kroner inkl. mva.

        Negativt tall er penger tilbake til kunden, samme fortegn som på
        fakturaen. Et intervall uten pris gir null bidrag og fylles ikke inn
        senere (C4); kilowattimene står igjen i `kwh_uten_pris`.

        Taket er per måned og treffer kilowattimene i kronologisk rekkefølge:
        de første `maks_kwh` får støtte, resten ikke.
        """
        s = self.satser
        maks = s.norgespris_maks_kwh if s.har_norgespris else s.stromstotte_maks_kwh
        brukt = 0.0
        sum_kr = 0.0
        for i in rader:
            if i.pris_nok_per_kwh_eks_mva is None:
                brukt += i.kwh
                continue
            under_tak = max(0.0, min(i.kwh, maks - brukt))
            brukt += i.kwh
            if under_tak <= 0:
                continue
            spot_inkl = i.pris_nok_per_kwh_eks_mva * s.mva_faktor
            if s.har_norgespris:
                # Symmetrisk: er spot under 50 øre, betaler kunden mellomlegget.
                sum_kr += (s.norgespris_inkl_mva - spot_inkl) * under_tak
            elif spot_inkl > s.stromstotte_terskel_inkl_mva:
                sum_kr -= (spot_inkl - s.stromstotte_terskel_inkl_mva) * s.stromstotte_andel * under_tak
        return sum_kr


class Hendelseslogg:
    """Hendelsene en replay består av, i den rekkefølgen de skjedde.

    Harnesset spiller dem inn i coordinatoren gjennom HAs state-maskin, fasiten
    regner på dem direkte. Begge ser nøyaktig de samme hendelsene; det er det
    som gjør sammenligningen verdt noe.

    Oppslagene er binærsøk, ikke gjennomgang. En måned med måling hvert minutt
    og poll hvert minutt gir 44 000 oppslag mot 44 000 hendelser, og lineært
    søk ville gjort replayen kvadratisk.
    """

    def __init__(self) -> None:
        self.malinger: list[tuple[datetime, float]] = []
        self.priser: list[tuple[datetime, float]] = []

    def mal(self, observed_at: datetime, teller_kwh: float) -> None:
        self.malinger.append((krev_aware(observed_at, "observed_at"), teller_kwh))

    def pris(self, rutestart: datetime, nok_per_kwh_eks_mva: float) -> None:
        self.priser.append((krev_aware(rutestart, "rutestart"), nok_per_kwh_eks_mva))

    def sorter(self) -> None:
        """Sorter begge listene. Kall denne når hendelser er lagt inn i uorden."""
        self.malinger.sort(key=lambda m: m[0])
        self.priser.sort(key=lambda p: p[0])

    def teller_ved(self, tidspunkt: datetime) -> tuple[datetime, float] | None:
        """Siste måling med `observed_at <= tidspunkt`."""
        i = bisect_right(self.malinger, tidspunkt, key=lambda m: m[0])
        return self.malinger[i - 1] if i else None

    def pris_ved(self, tidspunkt: datetime) -> float | None:
        """Prisen sensoren viser: verdien for den sist publiserte prisruten."""
        i = bisect_right(self.priser, tidspunkt, key=lambda p: p[0])
        return self.priser[i - 1][1] if i else None
