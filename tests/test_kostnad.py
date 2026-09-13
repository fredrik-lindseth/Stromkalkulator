"""Tester for kostnadskjernen: kroner per intervall og fastledd som periodebeløp.

Første halvdel prøver `kostnad.py` alene, uten Home Assistant og uten
coordinator. Andre halvdel kjører de samme reglene gjennom coordinatoren, der
tallene faktisk havner i sensorene.

Den bærende regelen er at ingen krone regnes ved å gange en kr/kWh-sats for
fastledd med kilowattimer. Fastledd er kroner per måned. `TestDimensjoner`
holder den regelen i sjakk i selve kildekoden, ikke bare i resultatene.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from stromkalkulator.avregning import (
    OSLO,
    Avlesning,
    AvregnetIntervall,
    Intervallkvalitet,
    Prisintervall,
    Priskilde,
    Revisjon,
    Tariff,
)
from stromkalkulator.kostnad import (
    INGEN_KRONER,
    Satser,
    andel_av_maaned,
    fastledd_belop,
    forlopt_andel_av_maaned,
    kroner_for_intervall,
    maanedsvindu,
    sekunder_forlopt_i_dogn,
    stromstotte_per_kwh,
)

from tests.conftest import _make_entry, _make_hass, _make_state, _run_update

_real_datetime = datetime

#: Standard mva-sone, Norgespris 0,50 kr/kWh inkl. mva, strømstøtteterskel
#: 0,9625 kr/kWh inkl. mva. Energileddet er BKKs dagsats med avgifter oppi.
SATSER = Satser(
    energiledd_inkl_mva=0.50,
    avgifter_inkl_mva=0.30,
    mva_sats=0.25,
    norgespris_inkl_mva=0.50,
    stromstotte_terskel=0.9625,
    stromstotte_max_kwh=5000.0,
    norgespris_max_kwh=5000.0,
    har_norgespris=False,
)


def _intervall(kwh, *, pris_eks_mva=1.00, tariff=Tariff.DAG, start=None):
    """Et ferdig avregnet intervall, slik boken leverer dem."""
    start = start or datetime(2026, 6, 15, 10, 0, tzinfo=UTC)
    pris = (
        None
        if pris_eks_mva is None
        else Prisintervall(
            start_utc=start,
            slutt_utc=start + timedelta(hours=1),
            nok_per_kwh_eks_mva=pris_eks_mva,
            omrade="NO5",
            opplosning_minutter=15,
            kilde=Priskilde.SENSOR,
            revisjon=Revisjon.UKJENT,
            pris_prover=4,
            pris_prover_ventet=4,
        )
    )
    return AvregnetIntervall(
        start_utc=start,
        slutt_utc=start + timedelta(hours=1),
        kwh=kwh,
        lokal_maned="2026-06",
        lokal_time=12,
        tariff=tariff,
        pris=pris,
        regelkilde="catalog:bkk:2026",
        kvalitet=Intervallkvalitet.KOMPLETT if pris else Intervallkvalitet.UTEN_PRIS,
        apen=False,
    )


class TestTakgrense:
    """Taket deler kilowattimene, det slår ikke av en bryter (234odp5)."""

    def test_eksakt_takgrense_deler_intervallet(self):
        """Et intervall som krysser taket prises halvt under og halvt over."""
        satser = replace(SATSER, har_norgespris=True)
        intervall = _intervall(10.0, pris_eks_mva=2.00)  # 2,50 inkl. mva
        kroner = kroner_for_intervall(intervall, satser, kwh_for=4995.0)

        # 5 kWh til Norgespris (0,50), 5 kWh til spot (2,50).
        assert kroner.strom_kr == pytest.approx(5 * 0.50 + 5 * 2.50)
        assert kroner.norgespris_kompensasjon_kr == pytest.approx(5 * (0.50 - 2.50))

    def test_kilowattimen_som_treffer_taket_noyaktig_er_med(self):
        """Står måneden på 4999 og intervallet er 1 kWh, er hele under taket."""
        satser = replace(SATSER, har_norgespris=True)
        kroner = kroner_for_intervall(_intervall(1.0, pris_eks_mva=2.00), satser, kwh_for=4999.0)
        assert kroner.strom_kr == pytest.approx(0.50)

    def test_forste_kilowattime_over_taket_er_ute(self):
        """Står måneden på taket, er hele intervallet over."""
        satser = replace(SATSER, har_norgespris=True)
        kroner = kroner_for_intervall(_intervall(1.0, pris_eks_mva=2.00), satser, kwh_for=5000.0)
        assert kroner.strom_kr == pytest.approx(2.50)
        assert kroner.norgespris_kompensasjon_kr == 0.0

    def test_stromstotten_stopper_ogsaa_paa_kilowattimen(self):
        """Samme deling for strømstøttens tak, som har sitt eget tall."""
        satser = replace(SATSER, stromstotte_max_kwh=1000.0)
        kroner = kroner_for_intervall(_intervall(10.0, pris_eks_mva=2.00), satser, kwh_for=995.0)
        stotte = stromstotte_per_kwh(2.50, satser.stromstotte_terskel)
        assert kroner.stromstotte_kr == pytest.approx(5 * stotte)
        assert kroner.strom_kr == pytest.approx(10 * 2.50 - 5 * stotte)

    def test_uten_stromstotteordning_gis_ingen_stotte(self):
        """Fritidsbolig uten ordning har tak 0, og det betyr ingen støtte i det hele tatt."""
        satser = replace(SATSER, stromstotte_max_kwh=0.0)
        kroner = kroner_for_intervall(_intervall(10.0, pris_eks_mva=2.00), satser, kwh_for=0.0)
        assert kroner.stromstotte_kr == 0.0
        assert kroner.strom_kr == pytest.approx(25.0)


class TestGjenopptattDelta:
    """Et stort delta etter et utfall er flere intervaller, ikke ett stort tall."""

    def test_nitti_kilowattimer_fordelt_over_taket(self):
        """90 kWh som krysser taket får ikke hele mengden på den ene siden.

        Etter et sensorutfall kommer hele gapet som ett delta. Boken fordeler
        det over intervallene, og hvert intervall deles mot taket for seg. Uten
        delingen ville alle 90 blitt priset etter månedstotalen etterpå.
        """
        satser = replace(SATSER, har_norgespris=True)
        # Ni timer à 10 kWh, måneden står på 4950 når de starter.
        kwh_for = 4950.0
        under = 0.0
        for _ in range(9):
            kroner = kroner_for_intervall(_intervall(10.0, pris_eks_mva=2.00), satser, kwh_for=kwh_for)
            # Norgespris-delen er 0,50 per kWh under taket.
            under += kroner.norgespris_kompensasjon_kr / (0.50 - 2.50)
            kwh_for += 10.0
        assert under == pytest.approx(50.0)


class TestManglendePris:
    """Et intervall uten pris gir ingen kraftkroner, men nettleien er kjent."""

    def test_uten_pris_ingen_kraft_men_energiledd(self):
        kroner = kroner_for_intervall(_intervall(4.0, pris_eks_mva=None), SATSER, kwh_for=0.0)
        assert kroner.strom_kr == 0.0
        assert kroner.kwh_uten_pris == pytest.approx(4.0)
        # Energileddet avhenger av tariffen og datoen, ikke av spotprisen.
        assert kroner.energiledd_dag_kr == pytest.approx(4.0 * 0.20)
        assert kroner.avgifter_kr == pytest.approx(4.0 * 0.30)

    def test_nullforbruk_gir_ingen_kroner(self):
        assert kroner_for_intervall(_intervall(0.0), SATSER, kwh_for=0.0) == INGEN_KRONER


class TestKronerAlgebra:
    """Delene summerer til helheten, og differansen er en Kroner."""

    def test_energileddet_er_summen_av_delene(self):
        kroner = kroner_for_intervall(_intervall(3.0, tariff=Tariff.NATT), SATSER, kwh_for=0.0)
        assert kroner.energiledd_natt_kr > 0
        assert kroner.energiledd_dag_kr == 0.0
        assert kroner.energiledd_kr == pytest.approx(
            kroner.energiledd_dag_kr + kroner.energiledd_natt_kr + kroner.avgifter_kr
        )

    def test_differansen_er_feltvis(self):
        en = kroner_for_intervall(_intervall(2.0), SATSER, kwh_for=0.0)
        to = kroner_for_intervall(_intervall(5.0), SATSER, kwh_for=0.0)
        diff = to - en
        assert diff.kwh == pytest.approx(3.0)
        assert (en + diff).strom_kr == pytest.approx(to.strom_kr)


class TestFastleddErPeriodebelop:
    """Fastledd er kroner per måned, aldri kroner per kilowattime."""

    def test_hele_maaneden_gir_hele_belopet(self):
        slutt = datetime(2026, 7, 1, tzinfo=OSLO)
        assert forlopt_andel_av_maaned(slutt - timedelta(seconds=1)) == pytest.approx(1.0, abs=1e-6)
        assert fastledd_belop(155, 1.0) == pytest.approx(155.0)

    def test_halve_maaneden_gir_halve_belopet(self):
        midt = datetime(2026, 6, 16, tzinfo=OSLO)
        assert forlopt_andel_av_maaned(midt) == pytest.approx(0.5)
        assert fastledd_belop(155, 0.5) == pytest.approx(77.5)

    def test_ukjent_trinn_gir_null_kroner(self):
        """Egendefinert uten trinntabell: null kroner, ikke et plausibelt tall."""
        assert fastledd_belop(None, 0.5) == 0.0

    def test_maanedsstart_gir_ingenting(self):
        assert forlopt_andel_av_maaned(datetime(2026, 6, 1, tzinfo=OSLO)) == 0.0


class TestSommertid:
    """Absolutt tid, ikke veggklokke (3jebp9g)."""

    def test_mars_har_743_timer(self):
        start, slutt = maanedsvindu(datetime(2026, 3, 15, tzinfo=OSLO))
        assert (slutt - start).total_seconds() == 743 * 3600

    def test_oktober_har_745_timer(self):
        start, slutt = maanedsvindu(datetime(2026, 10, 15, tzinfo=OSLO))
        assert (slutt - start).total_seconds() == 745 * 3600

    def test_andelen_bruker_manedens_egen_lengde(self):
        """Midt i mars er ikke det samme som halve mars, og det skal det ikke være.

        Nevneren er sekundene måneden faktisk har. Med en veggklokke-nevner
        ville mars fått 744 timer og andelen blitt for liten hele måneden.
        """
        naa = datetime(2026, 3, 16, 12, tzinfo=OSLO)
        forventet = (15 * 24 + 12) * 3600 / (743 * 3600)
        assert forlopt_andel_av_maaned(naa) == pytest.approx(forventet)

    def test_vaardogn_er_23_timer(self):
        """29. mars: klokken går fra 02 til 03, så døgnet er 23 timer."""
        assert sekunder_forlopt_i_dogn(datetime(2026, 3, 30, tzinfo=OSLO) - timedelta(seconds=1)) == (
            pytest.approx(23 * 3600 - 1)
        )

    def test_hostdogn_er_25_timer(self):
        """25. oktober: 02 kommer to ganger, så døgnet er 25 timer."""
        assert sekunder_forlopt_i_dogn(datetime(2026, 10, 26, tzinfo=OSLO) - timedelta(seconds=1)) == (
            pytest.approx(25 * 3600 - 1)
        )

    def test_dogn_og_maaned_henger_sammen_over_skiftet(self):
        # Klokken 23 den 25. oktober er 24 timer etter midnatt, ikke 23: timen
        # som kom en gang til ligger bak oss.
        naa = datetime(2026, 10, 25, 23, tzinfo=OSLO)
        andel = andel_av_maaned(sekunder_forlopt_i_dogn(naa), naa)
        assert andel == pytest.approx(24 * 3600 / (745 * 3600))


#: Roten til integrasjonen, funnet fra denne filen og ikke fra arbeidskatalogen.
PAKKEN = Path(__file__).resolve().parent.parent / "custom_components" / "stromkalkulator"

#: Navn som bærer et fastledd fordelt ut per kilowattime. Tallene finnes for
#: visning: de forteller hva timen koster akkurat nå. Ganges et av dem med noe
#: som helst, er resultatet kroner regnet fra et per-kWh-fastledd, og det er
#: nettopp dimensjonsfeilen 33f81xu handler om. `total_price`-familien er med
#: fordi summene har `fastledd_per_kwh` i seg.
FASTLEDD_PER_KWH_NAVN = (
    "fastledd_per_kwh",
    "kapasitetsledd_per_kwh",
    "total_price",
    "total_price_uten_stotte",
    "total_price_inkl_avgifter",
    "total_pris_norgespris",
)

#: Kilowattime-variabler. En av disse på den ene siden av en gangeoperasjon og
#: hva som helst på den andre er grunn nok til å se etter.
KWH_NAVN = ("energy_kwh", "energi_kwh")


class TestDimensjoner:
    """Ingen krone i integrasjonen kommer fra en fastledd-sats per kWh."""

    @staticmethod
    def _treff(kilde: str) -> list[str]:
        """Gangeoperasjoner som lager kroner av et per-kWh-fastledd.

        Begge operandrekkefølger teller: `sats * kwh` og `kwh * sats` er samme
        feil. Ordgrensene gjør at `total_price` ikke fanger
        `total_price_uten_stotte`, som står i listen for seg.
        """
        monstre = [rf"\b{navn}\b\s*\*" for navn in FASTLEDD_PER_KWH_NAVN]
        monstre += [rf"\*\s*\b{navn}\b" for navn in FASTLEDD_PER_KWH_NAVN]
        monstre += [rf"\b{navn}\b\s*\*" for navn in KWH_NAVN]
        monstre += [rf"\*\s*\b{navn}\b" for navn in KWH_NAVN]
        return re.findall("|".join(monstre), kilde)

    def test_ingen_kroner_fra_fastledd_per_kwh(self):
        """Vakten leser hele integrasjonen, ikke bare coordinator.py.

        En ny fil, eller den samme feilen skrevet med operandene i motsatt
        rekkefølge, gikk fri før. sensor.py ganger fortsatt kilowattimer med
        energiledd, avgifter og øyeblikksstøtte, og de treffer ikke her: det er
        satser per kWh, som er riktig dimensjon. Fanges gjør det den dagen L3c
        skulle gange `total_price` eller `kapasitetsledd_per_kwh` med noe.
        """
        funn = {}
        for fil in sorted(PAKKEN.rglob("*.py")):
            treff = self._treff(fil.read_text(encoding="utf-8"))
            if treff:
                funn[fil.name] = treff
        assert funn == {}, f"kroner regnet fra per-kWh-fastledd: {funn}"

    def test_vakten_ser_begge_operandrekkefolger(self):
        """Mutasjonsprøven, som kode: begge skrivemåter skal fanges."""
        assert self._treff("kr = fastledd_per_kwh * energy_kwh")
        assert self._treff("kr = energy_kwh * fastledd_per_kwh")
        assert self._treff("kr = total_price * kwh")
        assert self._treff("kr = kwh * kapasitetsledd_per_kwh")
        # Satser per kWh er riktig dimensjon og skal gå fri.
        assert not self._treff("kr = total_kwh * forbruksavgift_inkl")

    def test_kostnadskjernen_kjenner_ikke_energien_til_fastleddet(self):
        """`fastledd_belop` tar en andel av en periode, ikke kilowattimer."""
        assert fastledd_belop(155, 0.25) == fastledd_belop(155, 0.25)
        assert fastledd_belop(155, 2.0) == 155.0  # klippes, en måned er en måned


# ---------------------------------------------------------------------------
# Gjennom coordinatoren


def _coordinator(coord_module, **entry_kw):
    hass = _make_hass(power_w=entry_kw.pop("power_w", 6000), spot_price=entry_kw.pop("spot_price", 1.50))
    return coord_module.NettleieCoordinator(hass, _make_entry(**entry_kw)), hass


class TestMinuttpoll:
    """Vanlig drift: ett minutt av gangen."""

    def test_maanedskostnaden_er_en_akkumulator(self, coord_module):
        """`monthly_cost_kr` og `monthly_accumulated_cost_kr` er samme tall.

        De var to veier til samme beløp og kunne svare ulikt. Nå er det én
        bok, og begge feltene leser den (33f81xu).
        """
        coord, _ = _coordinator(coord_module)
        start = _real_datetime(2026, 6, 15, 12, 0)
        for i in range(10):
            data = _run_update(coord_module, coord, now=start + timedelta(minutes=i))

        assert data["monthly_cost_kr"] == pytest.approx(data["monthly_accumulated_cost_kr"], abs=0.01)
        assert data["monthly_accumulated_cost_kr"] == pytest.approx(
            data["monthly_accumulated_cost_strom_kr"]
            + data["monthly_accumulated_cost_energiledd_kr"]
            + data["monthly_accumulated_cost_kapasitetsledd_kr"],
            abs=1e-6,
        )

    def test_energileddet_er_summen_av_splitten(self, coord_module):
        """Feltet med det upresise navnet er dag + natt + avgifter, målt."""
        coord, _ = _coordinator(coord_module)
        start = _real_datetime(2026, 6, 15, 12, 0)
        for i in range(5):
            data = _run_update(coord_module, coord, now=start + timedelta(minutes=i))

        assert data["monthly_accumulated_cost_energiledd_kr"] == pytest.approx(
            data["monthly_energiledd_dag_kr"]
            + data["monthly_energiledd_natt_kr"]
            + data["monthly_avgifter_kr"],
            abs=1e-6,
        )
        assert data["monthly_energiledd_dag_kr"] > 0
        assert data["monthly_avgifter_kr"] > 0

    def test_polltakten_endrer_ikke_fastleddet(self, coord_module):
        """Ett minutt eller fem: fastleddet er det samme ved samme klokkeslett."""
        start = _real_datetime(2026, 6, 15, 12, 0)
        slutt = start + timedelta(minutes=30)
        belop = []
        for takt in (1, 5):
            coord, _ = _coordinator(coord_module)
            tid = start
            while tid <= slutt:
                data = _run_update(coord_module, coord, now=tid)
                tid += timedelta(minutes=takt)
            belop.append(data["monthly_accumulated_cost_kapasitetsledd_kr"])
        assert belop[0] == pytest.approx(belop[1])


class TestNullforbruk:
    """Et anlegg uten forbruk betaler fortsatt fastledd."""

    def test_fastleddet_paaloper_uten_en_eneste_kilowattime(self, coord_module):
        coord, _ = _coordinator(coord_module, power_w=0)
        start = _real_datetime(2026, 6, 15, 12, 0)
        _run_update(coord_module, coord, now=start)
        data = _run_update(coord_module, coord, now=start + timedelta(minutes=1))

        assert data["monthly_consumption_total_kwh"] == 0.0
        assert data["monthly_accumulated_cost_strom_kr"] == 0.0
        assert data["monthly_accumulated_cost_energiledd_kr"] == 0.0
        assert data["monthly_accumulated_cost_kapasitetsledd_kr"] > 0
        assert data["monthly_cost_kr"] == pytest.approx(
            data["monthly_accumulated_cost_kapasitetsledd_kr"], abs=0.01
        )


class TestTrinnskifte:
    """Månedens sluttrinn gjelder hele måneden."""

    def test_trinnskifte_midt_i_maaneden_gjelder_bakover(self, coord_module):
        """Et nytt trinn den 15. fakturerer hele måneden, ikke halve.

        Den gamle akkumulatoren tidsvektet trinnene mot hverandre og endte midt
        imellom. Nettselskapet fakturerer månedens trinn for hele måneden.
        """
        coord, _ = _coordinator(coord_module, power_w=0)
        start = _real_datetime(2026, 6, 15, 12, 0)
        forst = _run_update(coord_module, coord, now=start)
        lavt = forst["kapasitetsledd"]

        # Tre døgn med høy topp løfter trinnet.
        coord._daily_max_power = {
            "2026-06-10": coord_module.DailyMaxEntry(kw=9.0, hour=8),
            "2026-06-11": coord_module.DailyMaxEntry(kw=9.0, hour=8),
            "2026-06-12": coord_module.DailyMaxEntry(kw=9.0, hour=8),
        }
        data = _run_update(coord_module, coord, now=start + timedelta(minutes=1))

        assert data["kapasitetsledd"] > lavt
        andel = forlopt_andel_av_maaned(
            _real_datetime(2026, 6, 15, 12, 1, tzinfo=OSLO),
        )
        assert data["monthly_accumulated_cost_kapasitetsledd_kr"] == pytest.approx(
            data["kapasitetsledd"] * andel, abs=1e-3
        )

    def test_fastledd_ukjent_gir_null_og_flagg(self, coord_module):
        """Egendefinert uten trinntabell: ingen kroner, og det sies med et flagg."""
        coord, _ = _coordinator(
            coord_module,
            dso_id="custom",
            extra_data={"energiledd_dag": 0.20, "energiledd_natt": 0.10},
        )
        data = _run_update(coord_module, coord, now=_real_datetime(2026, 6, 15, 12, 0))
        assert data["fastledd_ukjent"] is True
        assert data["monthly_accumulated_cost_kapasitetsledd_kr"] == 0.0

    def test_utfylt_trinntabell_tetter_hullet_med_en_gang(self, coord_module):
        """Fylles tabellen inn den 20., dekkes hele måneden, ikke bare resten.

        Dommen over K3 (funn 5) fant at akkumulatoren sto på null så lenge
        fastleddet var ukjent, og at de nitten dagene før innfyllingen manglet
        uten at noe sa fra. Beløpet regnes nå av klokken, ikke av summen av
        tidsbiter, så det er tett i det tabellen kommer inn.
        """
        coord, _ = _coordinator(
            coord_module,
            dso_id="custom",
            extra_data={"energiledd_dag": 0.20, "energiledd_natt": 0.10},
        )
        naa = _real_datetime(2026, 6, 20, 12, 0)
        _run_update(coord_module, coord, now=naa)

        coord.kapasitetstrinn = [(2.0, 155), (5.0, 250), (float("inf"), 415)]
        data = _run_update(coord_module, coord, now=naa + timedelta(minutes=1))

        assert data["fastledd_ukjent"] is False
        andel = forlopt_andel_av_maaned(_real_datetime(2026, 6, 20, 12, 1, tzinfo=OSLO))
        assert data["monthly_accumulated_cost_kapasitetsledd_kr"] == pytest.approx(155 * andel, abs=1e-3)
        # Nitten dager er mer enn halve juni, så beløpet er over halvparten.
        assert data["monthly_accumulated_cost_kapasitetsledd_kr"] > 155 / 2


class TestForstePollEtterManedsskifte:
    """Alle månedsfelt skal peke på samme måned (2ferkiq)."""

    def test_alle_maanedsfelt_peker_paa_juli(self, coord_module):
        coord, _ = _coordinator(coord_module)
        t0 = _real_datetime(2026, 6, 30, 23, 58)
        _run_update(coord_module, coord, now=t0)
        juni = _run_update(coord_module, coord, now=t0 + timedelta(minutes=1))
        juli = _run_update(coord_module, coord, now=_real_datetime(2026, 7, 1, 0, 1))

        assert juni["current_month"] == "2026-06"
        assert juli["current_month"] == "2026-07"
        assert juli["previous_month_name"] == "juni 2026"

        # Ett minutt inn i juli: forbruket er julis ene minutt, kostnaden er
        # julis, og fastleddet er julis andel. Ingen av dem er junis.
        assert juli["monthly_consumption_total_kwh"] == pytest.approx(0.1, abs=1e-6)
        assert juli["previous_month_consumption_total_kwh"] == pytest.approx(0.2, abs=1e-6)
        assert 0 < juli["monthly_accumulated_cost_kr"] < juni["monthly_accumulated_cost_kr"] / 10
        assert juli["monthly_accumulated_cost_kapasitetsledd_kr"] == pytest.approx(
            juli["kapasitetsledd"] * forlopt_andel_av_maaned(_real_datetime(2026, 7, 1, 0, 1, tzinfo=OSLO)),
            abs=1e-3,
        )
        # Topp-3 og tak-flagget er også julis: tomt og under taket.
        assert juli["top_3_days"] == {}
        assert juli["norgespris_over_tak"] is False

    def test_forrige_maaned_fakturerer_hele_fastleddet(self, coord_module):
        """Måneden som lukkes arkiverer sluttrinnet for hele måneden."""
        coord, _ = _coordinator(coord_module, power_w=0)
        t0 = _real_datetime(2026, 6, 30, 23, 58)
        _run_update(coord_module, coord, now=t0)
        _run_update(coord_module, coord, now=t0 + timedelta(minutes=1))
        juli = _run_update(coord_module, coord, now=_real_datetime(2026, 7, 1, 0, 1))

        assert juli["previous_month_cost_kr"] == pytest.approx(
            juli["previous_month_kapasitetsledd"], abs=0.01
        )


def _sensoren_borte(hass):
    """Slå effektsensoren av, slik et strømbrudd gjør, eller en HA som starter
    før måleren er oppe. Returnerer funksjonen som slår den på igjen."""
    ekte = hass.states.get.side_effect

    def uten(entity_id):
        return None if entity_id == "sensor.power" else ekte(entity_id)

    hass.states.get.side_effect = uten

    def tilbake():
        hass.states.get.side_effect = ekte

    return tilbake


class TestDognmaksOverManedsskifte:
    """Døgnmaks i en ny måned skal aldri bære en dag fra forrige måned.

    Boken arkiverer forrige måned først når en avlesning i den nye måneden
    bokføres. Uten avlesning står de gamle intervallene igjen etter at
    coordinatoren har rullert, og siste time i forrige måned lukkes akkurat
    da. Kapasitetsleddet er et fast månedsbeløp, så en toppdag som blir
    stående setter trinnet for hele den nye måneden, ikke bare for en dag.
    """

    @staticmethod
    def _kveld(coord_module, coord, dag, time=23):
        """Poll tre minutter inn i en time, så det finnes et åpent intervall."""
        for minutt in (57, 58, 59):
            _run_update(coord_module, coord, now=dag.replace(hour=time, minute=minutt))

    def test_forste_poll_uten_avlesning_arver_ikke_juni(self, coord_module):
        """Strømbrudd ved midnatt: julis døgnmaks skal være tom, ikke junis."""
        coord, hass = _coordinator(coord_module, power_w=20000)
        self._kveld(coord_module, coord, _real_datetime(2026, 6, 30))

        paa_igjen = _sensoren_borte(hass)
        juli = _run_update(coord_module, coord, now=_real_datetime(2026, 7, 1, 0, 1))

        assert juli["current_month"] == "2026-07"
        assert juli["top_3_days"] == {}
        assert coord._daily_max_power == {}
        # Timen hører til juni, og der skal den ligge.
        assert "2026-06-30" in juli["previous_month_top_3"]

        paa_igjen()
        videre = _run_update(coord_module, coord, now=_real_datetime(2026, 7, 1, 0, 2))
        assert "2026-06-30" not in videre["top_3_days"]
        assert "2026-06-30" not in coord._daily_max_power

    def test_forste_poll_med_avlesning_bokforer_bare_juli(self, coord_module):
        """Samme skifte med sensoren oppe: julis timer kommer, junis blir ute."""
        coord, _ = _coordinator(coord_module, power_w=20000)
        self._kveld(coord_module, coord, _real_datetime(2026, 6, 30))

        juli = _run_update(coord_module, coord, now=_real_datetime(2026, 7, 1, 0, 1))
        assert juli["top_3_days"] == {}

        senere = _run_update(coord_module, coord, now=_real_datetime(2026, 7, 1, 1, 1))
        assert list(senere["top_3_days"]) == ["2026-07-01"]

    def test_trinnet_i_juli_kommer_ikke_fra_junis_topp(self, coord_module):
        """Kroneleddet er det som gjør funnet dyrt: feil trinn hele måneden."""
        coord, hass = _coordinator(coord_module, power_w=20000)
        coord.kapasitetstrinn = [(0.5, 155), (2.0, 250), (float("inf"), 415)]
        self._kveld(coord_module, coord, _real_datetime(2026, 6, 30))

        paa_igjen = _sensoren_borte(hass)
        juli = _run_update(coord_module, coord, now=_real_datetime(2026, 7, 1, 0, 1))
        paa_igjen()

        # Junis siste time ligger over 0,5 kW. Lekker den inn, står julis
        # trinn på 250 fra første minutt, og fastleddet er et månedsbeløp.
        assert juli["previous_month_top_3"]["2026-06-30"].kw > 0.5
        assert juli["kapasitetsledd"] == 155

    def test_strombrudd_over_flere_polls_holder_juni_ute(self, coord_module):
        """Sensoren er borte fra før midnatt til et stykke inn i juli."""
        coord, hass = _coordinator(coord_module, power_w=20000)
        self._kveld(coord_module, coord, _real_datetime(2026, 6, 30), time=22)
        _run_update(coord_module, coord, now=_real_datetime(2026, 6, 30, 23, 1))
        assert "2026-06-30" in coord._daily_max_power

        paa_igjen = _sensoren_borte(hass)
        for naa in (
            _real_datetime(2026, 6, 30, 23, 30),
            _real_datetime(2026, 6, 30, 23, 59),
            _real_datetime(2026, 7, 1, 0, 1),
            _real_datetime(2026, 7, 1, 0, 3),
        ):
            data = _run_update(coord_module, coord, now=naa)
        assert data["top_3_days"] == {}

        paa_igjen()
        data = _run_update(coord_module, coord, now=_real_datetime(2026, 7, 1, 0, 5))
        assert "2026-06-30" not in data["top_3_days"]
        assert "2026-06-30" not in coord._daily_max_power

    def test_ingen_julidag_overgaar_junis_topp(self, coord_module):
        """Juli er en rolig måned. Da skal topp-3 være julis små dager.

        Uten filteret ville junis 20 kW stått til tre julidager slo den, og
        her gjør ingen av dem det.
        """
        coord, hass = _coordinator(coord_module, power_w=20000)
        self._kveld(coord_module, coord, _real_datetime(2026, 6, 30))

        paa_igjen = _sensoren_borte(hass)
        _run_update(coord_module, coord, now=_real_datetime(2026, 7, 1, 0, 1))
        paa_igjen()

        hass.states.get.side_effect = lambda eid: (
            _make_state(1000)
            if eid == "sensor.power"
            else (_make_state(1.50) if eid == "sensor.spot_price" else None)
        )
        for dag in (1, 2, 3):
            for minutt in (55, 56, 57, 58, 59):
                _run_update(coord_module, coord, now=_real_datetime(2026, 7, dag, 8, minutt))
            data = _run_update(coord_module, coord, now=_real_datetime(2026, 7, dag, 9, 1))

        assert set(data["top_3_days"]) == {"2026-07-01", "2026-07-02", "2026-07-03"}
        assert max(e.kw for e in data["top_3_days"].values()) < 2.0

    def test_omstart_i_ny_maaned_uten_maaler(self, coord_module):
        """HA starter 1. juli med junis bok lagret og måleren ikke oppe ennå."""
        lagret: dict = {}

        def skrivende_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)

            async def save(data):
                lagret.clear()
                lagret.update(data)

            store.async_save = AsyncMock(side_effect=save)
            store.async_remove = AsyncMock()
            return store

        def lesende_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=lagret)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=skrivende_store)
        coord, hass = _coordinator(coord_module, power_w=20000)
        self._kveld(coord_module, coord, _real_datetime(2026, 6, 30))
        asyncio.run(coord._save_stored_data())
        assert lagret["current_month"] == "2026-06"

        coord_module.Store = MagicMock(side_effect=lesende_store)
        coord_module.dt_util.now.return_value = _real_datetime(2026, 7, 1, 0, 1)
        gjenopptatt = coord_module.NettleieCoordinator(hass, _make_entry())
        asyncio.run(gjenopptatt._load_stored_data())

        _sensoren_borte(hass)
        data = _run_update(coord_module, gjenopptatt, now=_real_datetime(2026, 7, 1, 0, 1))
        assert data["current_month"] == "2026-07"
        assert data["top_3_days"] == {}

    def test_oktober_med_sommertidsskifte_starter_rent(self, coord_module):
        """Rulleringen inn i en måned som har et sommertidsskifte i seg."""
        coord, hass = _coordinator(coord_module, power_w=20000)
        self._kveld(coord_module, coord, _real_datetime(2026, 9, 30))

        paa_igjen = _sensoren_borte(hass)
        oktober = _run_update(coord_module, coord, now=_real_datetime(2026, 10, 1, 0, 1))
        assert oktober["top_3_days"] == {}
        paa_igjen()

        # Den doble timen 25. oktober skal registreres som oktoberdøgn, og
        # september skal fortsatt være ute.
        for minutt in (56, 57, 58, 59):
            naa = _real_datetime(2026, 10, 25, 2, minutt, tzinfo=OSLO, fold=0)
            _run_update(coord_module, coord, now=naa)
        for minutt in (1, 2, 3):
            naa = _real_datetime(2026, 10, 25, 2, minutt, tzinfo=OSLO, fold=1)
            _run_update(coord_module, coord, now=naa)
        data = _run_update(coord_module, coord, now=_real_datetime(2026, 10, 25, 3, 1, tzinfo=OSLO))

        assert "2026-09-30" not in data["top_3_days"]
        assert "2026-10-25" in data["top_3_days"]


class TestStoreOverlever:
    """Et bokført intervall bidrar ikke en gang til etter en omstart."""

    def test_kronene_regnes_ikke_dobbelt_etter_ny_bok(self, coord_module):
        coord, _ = _coordinator(coord_module)
        start = _real_datetime(2026, 6, 15, 12, 0)
        for i in range(5):
            data = _run_update(coord_module, coord, now=start + timedelta(minutes=i))
        strom = data["monthly_accumulated_cost_strom_kr"]

        # Samme poll en gang til: ingen ny energi, ingen nye kroner.
        igjen = _run_update(coord_module, coord, now=start + timedelta(minutes=4))
        assert igjen["monthly_accumulated_cost_strom_kr"] == pytest.approx(strom)


class TestOppgraderingFraSammenslaattEnergiledd:
    """En fil fra før splitten har bare summen, og den kan ikke deles i ettertid."""

    def test_gammel_sum_baeres_som_apningsbalanse(self, coord_module):
        lagret = {
            "current_month": "2026-06",
            "monthly_consumption": {"dag": 100.0, "natt": 50.0},
            "monthly_accumulated_cost_strom": 200.0,
            "monthly_accumulated_cost_energiledd": 80.0,
            "monthly_accumulated_cost_kapasitetsledd": 70.0,
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=dict(lagret))
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=make_store)
        coord, _ = _coordinator(coord_module)
        data = _run_update(coord_module, coord, now=_real_datetime(2026, 6, 15, 12, 0))

        # Summen står, men den er ikke delt i dag, natt og avgifter: den delen
        # av historikken finnes ikke.
        assert data["monthly_accumulated_cost_energiledd_kr"] == pytest.approx(80.0)
        assert data["monthly_energiledd_dag_kr"] == 0.0
        assert data["monthly_energiledd_natt_kr"] == 0.0
        assert data["monthly_avgifter_kr"] == 0.0

        # Det som bokføres etter oppgraderingen legger seg oppå, og identiteten
        # holder med åpningsbalansen medregnet.
        data = _run_update(coord_module, coord, now=_real_datetime(2026, 6, 15, 12, 1))
        assert data["monthly_energiledd_dag_kr"] > 0
        assert data["monthly_accumulated_cost_energiledd_kr"] == pytest.approx(
            80.0
            + data["monthly_energiledd_dag_kr"]
            + data["monthly_energiledd_natt_kr"]
            + data["monthly_avgifter_kr"],
            abs=1e-3,
        )


class TestTimesmaksFraBoken:
    """Døgnmaks leses av boken, ikke av en veggklokke-bøtte ved siden av."""

    def test_lukket_intervall_blir_dognmaks(self, coord_module):
        coord, _ = _coordinator(coord_module, power_w=0)
        coord._store_loaded = True
        felles = {"source_identity": "test:teller", "entity_id": "sensor.energi"}
        start = _real_datetime(2026, 6, 15, 11, 0, tzinfo=OSLO)
        coord._bok.bokfor(Avlesning(value_kwh=0.0, observed_at=start, **felles))
        coord._bok.bokfor(Avlesning(value_kwh=4.25, observed_at=start + timedelta(hours=1), **felles))

        _run_update(coord_module, coord, now=_real_datetime(2026, 6, 15, 12, 30))
        assert coord._daily_max_power["2026-06-15"].kw == pytest.approx(4.25)
        assert coord._daily_max_power["2026-06-15"].hour == 11

    def test_current_hour_energy_speiler_det_apne_intervallet(self, coord_module):
        coord, _ = _coordinator(coord_module)
        start = _real_datetime(2026, 6, 15, 12, 0)
        # Ett minutt av gangen: et pollvindu over seks minutter forkastes for
        # en effektbruker, og da ville intervallet stått tomt (kontrakt B1).
        for i in range(6):
            _run_update(coord_module, coord, now=start + timedelta(minutes=i))
        apent = coord._bok.intervall(
            _real_datetime(2026, 6, 15, 12, 0, tzinfo=OSLO),
            _real_datetime(2026, 6, 15, 12, 5, tzinfo=OSLO),
        )
        assert apent is not None
        assert coord._current_hour_energy == pytest.approx(apent.kwh)


def _hass_med_teller(verdier):
    """Hass-mock der energitelleren leser fra en liste som tømmes."""
    hass = MagicMock()

    def get_state(entity_id):
        if entity_id == "sensor.energy":
            return _make_state(verdier[-1], unit="kWh")
        if entity_id == "sensor.spot_price":
            return _make_state(1.50, unit="NOK/kWh", state_class=None)
        return None

    hass.states.get = MagicMock(side_effect=get_state)
    register = MagicMock()
    register.async_get = MagicMock(return_value=MagicMock(unique_id="maaler-1"))
    hass._entity_register = register
    return hass


class TestGjennomCoordinator:
    """Det store gjenopptatte deltaet, hele veien gjennom."""

    def test_nitti_kilowattimer_etter_utfall_deles_paa_intervallene(self, coord_module):
        """90 kWh som kommer inn på én gang fordeles, og prises per intervall.

        Kilowattimene skal havne i timene de tilhører, ikke i timen de kom inn
        i, og hver time skal prises for seg.
        """
        import stromkalkulator.inputadapter as adapter

        adapter.er = MagicMock()
        adapter.er.async_get = MagicMock(side_effect=lambda hass: hass._entity_register)

        verdier = [1000.0]
        hass = _hass_med_teller(verdier)
        entry = _make_entry(energy_sensor="sensor.energy", power_sensor=None)
        coord = coord_module.NettleieCoordinator(hass, entry)

        start = _real_datetime(2026, 6, 15, 3, 0)
        _run_update(coord_module, coord, now=start)

        # Ni timer senere kommer telleren tilbake med 90 kWh mer.
        verdier.append(1090.0)
        data = _run_update(coord_module, coord, now=start + timedelta(hours=9))

        assert data["monthly_consumption_total_kwh"] == pytest.approx(90.0, abs=0.01)
        # Ni timer fordelt over natt og dag: begge sider har fått kilowattimer.
        assert data["monthly_energiledd_natt_kr"] > 0
        assert data["monthly_energiledd_dag_kr"] > 0
        assert data["monthly_accumulated_cost_energiledd_kr"] == pytest.approx(
            data["monthly_energiledd_dag_kr"]
            + data["monthly_energiledd_natt_kr"]
            + data["monthly_avgifter_kr"],
            abs=1e-6,
        )


class TestSommertidGjennomCoordinator:
    """`elapsed_hours` måler absolutt tid over begge skiftene (3jebp9g).

    De rene funksjonene over er prøvd for seg. Denne går gjennom
    coordinatoren, for det var der veggklokkesubtraksjonen sto: med den gir
    vårskiftet seks minutter for ett ekte, og høstskiftet null for to.
    """

    def test_vaar_ett_ekte_minutt_er_ett_minutt_energi(self, coord_module):
        coord, _ = _coordinator(coord_module, power_w=6000)
        _run_update(coord_module, coord, now=_real_datetime(2026, 3, 29, 1, 59, tzinfo=OSLO))
        data = _run_update(coord_module, coord, now=_real_datetime(2026, 3, 29, 3, 0, tzinfo=OSLO))
        assert data["monthly_consumption_total_kwh"] == pytest.approx(0.1, abs=1e-6)

    def test_host_to_ekte_minutter_er_to_minutter_energi(self, coord_module):
        coord, _ = _coordinator(coord_module, power_w=6000)
        _run_update(coord_module, coord, now=_real_datetime(2026, 10, 25, 2, 58, tzinfo=OSLO, fold=0))
        data = _run_update(coord_module, coord, now=_real_datetime(2026, 10, 25, 2, 0, tzinfo=OSLO, fold=1))
        assert data["monthly_consumption_total_kwh"] == pytest.approx(0.2, abs=1e-6)
