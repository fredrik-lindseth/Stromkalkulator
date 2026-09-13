"""Vakthold på input-sensorene: utfall, frossen teller, utløpt spotpris.

Bakgrunnen er konkret. HAN-leseren lå nede fra 29.07.2026 kl. 11 til 08.08
kl. 08, altså 237 timer, og integrasjonen rapporterte videre som om alt var i
orden. Det ble oppdaget ti dager for sent, da juli-fakturaen skulle verifiseres.
I september falt spotpris-sensoren ut fire ganger. Filen dekker begge modusene,
og den siste testen spiller av det ekte juli-utfallet time for time.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock

import pytest

from tests.conftest import _make_entry, _make_state

FIXTURES_DIR = Path(__file__).parent / "fixtures"

UTFALL = "utfall"
FROSSEN = "frossen"
SPOT_UTLOPT = "spot_utlopt"


class Sensorbenk:
    """Styrer hva hass.states.get returnerer for hver input-entitet.

    `sett(...)` tar tall, eller strengen "unavailable"/"unknown", eller None for
    en entitet som ikke finnes i det hele tatt.
    """

    def __init__(self) -> None:
        self.verdier: dict[str, object] = {
            "sensor.power": 5000,
            "sensor.spot_price": 1.20,
            "sensor.tpi": 1000.0,
        }

    def sett(self, entity_id: str, verdi: object) -> None:
        self.verdier[entity_id] = verdi

    #: Enheten hver sensor oppgir. Uten enhet antar adapteren rollens egen, og
    #: prissensoren får da et repair om å bekrefte antakelsen. Ekte sensorer
    #: har enhet, så benken skal ha det også.
    ENHETER: ClassVar[dict[str, str | None]] = {
        "sensor.power": "W",
        "sensor.spot_price": "NOK/kWh",
        "sensor.tpi": "kWh",
    }

    def get(self, entity_id: str):
        verdi = self.verdier.get(entity_id, "__mangler__")
        if verdi == "__mangler__" or verdi is None:
            return None
        return _make_state(verdi, unit=self.ENHETER.get(entity_id))


def _lag_coordinator(coord_module, benk: Sensorbenk, *, energy_sensor="sensor.tpi", **entry_kw):
    """Coordinator koblet til sensorbenken, med ferskt issue-registry-mock."""
    coord_module.ir = MagicMock()
    coord_module.ir.IssueSeverity.WARNING = "warning"
    hass = MagicMock()
    hass.states.get = MagicMock(side_effect=benk.get)
    entry = _make_entry(energy_sensor=energy_sensor, **entry_kw)
    return coord_module.NettleieCoordinator(hass, entry)


def _poll(coord_module, coordinator, now: datetime) -> dict:
    coord_module.dt_util.now.return_value = now
    return asyncio.run(coordinator._async_update_data())


def _typer(resultat: dict) -> set[str]:
    return {p["type"] for p in resultat["input_problemer"]}


def _issue_ids(ir_mock) -> list[str]:
    return [kall.args[2] for kall in ir_mock.async_create_issue.call_args_list]


def _slettede_issue_ids(ir_mock) -> list[str]:
    return [kall.args[2] for kall in ir_mock.async_delete_issue.call_args_list]


def _siste_plassholdere(ir_mock, issue_id: str) -> dict:
    """Teksten varselet står med nå, altså siste gang det ble skrevet."""
    kall = [k for k in ir_mock.async_create_issue.call_args_list if k.args[2] == issue_id]
    assert kall, f"{issue_id} ble aldri reist"
    return dict(kall[-1].kwargs["translation_placeholders"])


class TestUtfall:
    """Deteksjon 1: entiteten er unavailable eller unknown."""

    def test_kort_glipp_under_grace_gir_ingenting(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.power", "unavailable")
        resultat = _poll(coord_module, coord, start + timedelta(minutes=20))

        assert resultat["maaledata_problem"] is False
        assert resultat["input_problemer"] == []
        assert coord_module.ir.async_create_issue.call_count == 0

    def test_utfall_over_grace_gir_problem_og_issue(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.power", "unavailable")
        _poll(coord_module, coord, start + timedelta(minutes=20))
        resultat = _poll(coord_module, coord, start + timedelta(minutes=45))

        assert resultat["maaledata_problem"] is True
        problem = next(p for p in resultat["input_problemer"] if p["type"] == UTFALL)
        assert problem["input"] == "effekt"
        assert problem["entity_id"] == "sensor.power"
        assert problem["minutter"] == 45
        assert f"input_utfall_{coord.entry.entry_id}" in _issue_ids(coord_module.ir)

    def test_unknown_teller_som_utfall(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.spot_price", "unknown")
        resultat = _poll(coord_module, coord, start + timedelta(minutes=40))

        utfall = [p for p in resultat["input_problemer"] if p["type"] == UTFALL]
        assert [p["input"] for p in utfall] == ["spotpris"]

    def test_issue_skrives_ikke_om_naar_teksten_er_den_samme(self, coord_module):
        """Uendret utfall skal ikke skrive i issue-registeret hvert minutt.

        Polling er hvert minutt. Varselet skrives om når innholdet endrer seg,
        og innenfor samme viste varighet er det ingenting å endre.
        """
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.power", "unavailable")
        for minutter in (40, 41, 42):
            _poll(coord_module, coord, start + timedelta(minutes=minutter))

        utfall_issues = [i for i in _issue_ids(coord_module.ir) if i.startswith("input_utfall_")]
        assert len(utfall_issues) == 1

    def test_leverandorpris_varsler_ikke(self, coord_module):
        """Leverandørprisen mater en sammenligningssensor og skal ikke alarmere."""
        benk = Sensorbenk()
        benk.sett("sensor.elco_price", 1.4)
        coord = _lag_coordinator(coord_module, benk, electricity_company_price_sensor="sensor.elco_price")
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.elco_price", "unavailable")
        resultat = _poll(coord_module, coord, start + timedelta(minutes=45))

        assert resultat["maaledata_problem"] is False
        assert resultat["leverandorpris_gyldig"] is False

    def test_leverandorpris_gyldig_er_sann_naar_sensoren_leverer(self, coord_module):
        """Den andre retningen av testen over.

        `_input_er_gyldig` tar en rolle, ikke en entity-id, og kallet her sendte
        entity-id-en. Oppslaget traff da aldri, så attributtet sto False så
        lenge en leverandørprissensor var konfigurert, også når den leverte
        fint. Det er synlig på binary_sensor.maaledata_problem.
        """
        benk = Sensorbenk()
        benk.sett("sensor.elco_price", 1.4)
        benk.ENHETER = {**benk.ENHETER, "sensor.elco_price": "NOK/kWh"}
        coord = _lag_coordinator(coord_module, benk, electricity_company_price_sensor="sensor.elco_price")
        resultat = _poll(coord_module, coord, datetime(2026, 6, 15, 12, 0))

        assert resultat["leverandorpris_gyldig"] is True
        assert resultat["input_resultater"]["leverandorpris"]["type"] == "gyldig"

    def test_uten_leverandorprissensor_er_attributtet_none(self, coord_module):
        """Ingen sensor er ikke det samme som en sensor som svikter."""
        coord = _lag_coordinator(coord_module, Sensorbenk())
        resultat = _poll(coord_module, coord, datetime(2026, 6, 15, 12, 0))

        assert resultat["leverandorpris_gyldig"] is None

    def test_eksportmaaler_varsler(self, coord_module):
        benk = Sensorbenk()
        benk.sett("sensor.export_power", 0)
        coord = _lag_coordinator(coord_module, benk, export_power_sensor="sensor.export_power")
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.export_power", "unavailable")
        resultat = _poll(coord_module, coord, start + timedelta(minutes=40))

        assert [p["input"] for p in resultat["input_problemer"]] == ["eksport"]


class TestFrossenTeller:
    """Deteksjon 2: energitelleren rapporterer, men står stille."""

    def test_frossen_over_terskel_gir_problem(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)
        benk.sett("sensor.tpi", 1001.0)
        _poll(coord_module, coord, start + timedelta(minutes=1))

        # Telleren står stille, men sensoren rapporterer fint.
        resultat = _poll(coord_module, coord, start + timedelta(hours=2))
        assert _typer(resultat) == set()

        resultat = _poll(coord_module, coord, start + timedelta(hours=4))
        problem = next(p for p in resultat["input_problemer"] if p["type"] == FROSSEN)
        assert problem["input"] == "energi"
        assert problem["timer"] >= 3
        assert f"energi_frossen_{coord.entry.entry_id}" in _issue_ids(coord_module.ir)

    def test_terskel_er_konfigurerbar(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk, extra_data={"energi_frossen_timer": 24})
        assert coord.energi_frossen_terskel_timer == 24.0

        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)
        benk.sett("sensor.tpi", 1001.0)
        _poll(coord_module, coord, start + timedelta(minutes=1))

        # Hytte med hovedbryteren av: ti timer uten forbruk er ikke en feil.
        assert _typer(_poll(coord_module, coord, start + timedelta(hours=10))) == set()
        assert FROSSEN in _typer(_poll(coord_module, coord, start + timedelta(hours=26)))

    def test_ugyldig_terskel_faller_til_default(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk, extra_data={"energi_frossen_timer": "tre"})
        assert coord.energi_frossen_terskel_timer == 3.0

    def test_terskel_klippes_til_grensene(self, coord_module):
        benk = Sensorbenk()
        lav = _lag_coordinator(coord_module, benk, extra_data={"energi_frossen_timer": 0})
        hoy = _lag_coordinator(coord_module, benk, extra_data={"energi_frossen_timer": 900})
        assert lav.energi_frossen_terskel_timer == 1.0
        assert hoy.energi_frossen_terskel_timer == 48.0

    def test_fersk_installasjon_starter_klokken_naa(self, coord_module):
        """Ingen lagret historikk: telleren skal ikke meldes frossen umiddelbart."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        resultat = _poll(coord_module, coord, datetime(2026, 6, 15, 12, 0))

        assert coord._last_energy_increase == datetime(2026, 6, 15, 12, 0)
        assert _typer(resultat) == set()

    def test_restart_med_lagret_tidsstempel_fanger_utfallet(self, coord_module):
        """Etter omstart skal et døgn gammelt utfall meldes ved første poll."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        coord._last_energy_increase = datetime(2026, 6, 14, 12, 0)
        coord._store_loaded = True

        resultat = _poll(coord_module, coord, datetime(2026, 6, 15, 12, 0))
        problem = next(p for p in resultat["input_problemer"] if p["type"] == FROSSEN)
        assert problem["timer"] == 24.0

    def test_uten_energisensor_ingen_frossen_deteksjon(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk, energy_sensor=None)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)
        resultat = _poll(coord_module, coord, start + timedelta(hours=12))

        assert FROSSEN not in _typer(resultat)
        assert coord._last_energy_increase is None


class TestSpotUtlopt:
    """Deteksjon 3: spot-cachen er tom, så kostnaden slutter å akkumulere."""

    def test_spot_ugyldig_over_cache_gir_problem(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.spot_price", "unavailable")
        # Under to timer lever prisen på cachen, og kostnaden regnes fortsatt.
        resultat = _poll(coord_module, coord, start + timedelta(minutes=90))
        assert resultat["spot_price_valid"] is True
        assert SPOT_UTLOPT not in _typer(resultat)

        resultat = _poll(coord_module, coord, start + timedelta(hours=3))
        assert resultat["spot_price_valid"] is False
        assert SPOT_UTLOPT in _typer(resultat)
        assert f"spot_utfall_{coord.entry.entry_id}" in _issue_ids(coord_module.ir)


class TestOmstart:
    """Falske positiver rett etter at HA har startet, altså hos alle brukere."""

    def test_spot_uten_cache_varsler_ikke_med_en_gang(self, coord_module):
        """R2: spot-cachen er in-memory og tom ved oppstart.

        HA skriver restaurerte entiteter som unavailable til integrasjonen som
        eier dem har levert. Kommer vår første refresh før Nord Pool henter,
        er prisen ugyldig og cachen tom, og uten grace varsler vi hver eneste
        omstart.
        """
        benk = Sensorbenk()
        benk.sett("sensor.spot_price", "unavailable")
        coord = _lag_coordinator(coord_module, benk)

        start = datetime(2026, 6, 15, 12, 0)
        resultat = _poll(coord_module, coord, start)
        assert resultat["spot_price_valid"] is False
        assert _typer(resultat) == set()
        assert resultat["maaledata_problem"] is False
        assert _issue_ids(coord_module.ir) == []

        # Nord Pool kom seg opp, og da skal ingenting ha vært varslet.
        benk.sett("sensor.spot_price", 1.20)
        assert _typer(_poll(coord_module, coord, start + timedelta(minutes=1))) == set()

    def test_spot_borte_forbi_grace_varsler_likevel(self, coord_module):
        """Motprøve: grace er en utsettelse, ikke en avlysning."""
        benk = Sensorbenk()
        benk.sett("sensor.spot_price", "unavailable")
        coord = _lag_coordinator(coord_module, benk)

        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)
        resultat = _poll(coord_module, coord, start + timedelta(minutes=45))

        assert SPOT_UTLOPT in _typer(resultat)
        assert f"spot_utfall_{coord.entry.entry_id}" in _issue_ids(coord_module.ir)

    def test_lang_nedetid_gir_ikke_frossen_ved_forste_poll(self, coord_module):
        """O1: HA har vært av i to døgn, og da er baseline droppet som foreldet.

        Hytta som slås på igjen skal ikke møtes av et varsel om frossen måler.
        """
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        coord._store.async_load.return_value = {
            "last_energy_increase": "2026-06-13T12:00:00",
            "last_update": "2026-06-13T12:00:00",
            "last_tpi_kwh": 1000.0,
        }

        start = datetime(2026, 6, 15, 12, 0)
        coord_module.dt_util.now.return_value = start
        resultat = _poll(coord_module, coord, start)

        assert FROSSEN not in _typer(resultat)
        assert not [i for i in _issue_ids(coord_module.ir) if i.startswith("energi_frossen_")]
        assert coord._last_energy_increase == start


class TestStrombrudd:
    """Strømbrudd i huset: HA er av, og telleren står stille fordi den er strømløs.

    Vakthold som roper ulv hver gang strømmen har vært borte, blir slått av, og
    da er det verdiløst. Samme forveksling som resten av vaktholdet er ryddet
    for: at vi ikke har sett en økning er ikke det samme som at måleren står
    stille. Vi var blinde i gapet, så det gapet teller ikke.
    """

    @staticmethod
    def _coord_etter_strombrudd(coord_module, benk, start, timer_nede):
        nede_fra = start - timedelta(hours=timer_nede)
        coord = _lag_coordinator(coord_module, benk)
        coord._store.async_load.return_value = {
            # Siste økning kom 20 minutter før strømmen gikk. Uten den detaljen
            # ville et brudd på nøyaktig terskelen falle akkurat på grensen.
            "last_energy_increase": (nede_fra - timedelta(minutes=20)).isoformat(),
            "last_update": nede_fra.isoformat(),
            "last_tpi_kwh": 1000.0,
            "last_tpi_time": nede_fra.isoformat(),
        }
        # Telleren viser samme tall som før: den fikk ikke strøm den heller.
        benk.sett("sensor.tpi", 1000.0)
        return coord

    @pytest.mark.parametrize("timer_nede", [3, 12, 24])
    def test_strombrudd_gir_ikke_frossen_ved_forste_poll(self, coord_module, timer_nede):
        benk = Sensorbenk()
        start = datetime(2026, 1, 15, 6, 0)
        coord = self._coord_etter_strombrudd(coord_module, benk, start, timer_nede)

        resultat = _poll(coord_module, coord, start)

        assert FROSSEN not in _typer(resultat)
        assert not [i for i in _issue_ids(coord_module.ir) if i.startswith("energi_frossen_")]

    def test_frossen_meldes_likevel_tre_timer_etter_omstarten(self, coord_module):
        """Motprøve: står telleren stille etter at strømmen er tilbake, varsles det."""
        benk = Sensorbenk()
        start = datetime(2026, 1, 15, 6, 0)
        coord = self._coord_etter_strombrudd(coord_module, benk, start, 5)

        assert FROSSEN not in _typer(_poll(coord_module, coord, start))
        resultat = _poll(coord_module, coord, start + timedelta(hours=3, minutes=10))

        assert FROSSEN in _typer(resultat)
        assert f"energi_frossen_{coord.entry.entry_id}" in _issue_ids(coord_module.ir)

    def test_maaler_som_staar_stille_mens_ha_kjorer_varsles(self, coord_module):
        """Motprøve: uten nedetid er stillstand nettopp det vaktholdet er til for.

        Dette er HAN-leseren slik den sto sommeren 2026: entiteten rapporterte,
        tallet rørte seg ikke.
        """
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 1, 15, 6, 0)
        _poll(coord_module, coord, start)

        resultat = _poll(coord_module, coord, start + timedelta(hours=3, minutes=10))

        assert FROSSEN in _typer(resultat)
        assert f"energi_frossen_{coord.entry.entry_id}" in _issue_ids(coord_module.ir)


class TestEnRangering:
    """Én årsak skal gi ett varsel, ikke to."""

    def test_energisensor_borte_gir_bare_utfall(self, coord_module):
        """O2: unavailable energisensor slo ut både utfall og frossen.

        Rangeringen: står energi-inputen selv i utfall, eier utfalls-deteksjonen
        hendelsen. Frossen sier at sensoren rapporterer, og det gjør den ikke.
        """
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.tpi", "unavailable")
        resultat = _poll(coord_module, coord, start + timedelta(hours=4))

        assert [p["type"] for p in resultat["input_problemer"]] == [UTFALL]
        assert not [i for i in _issue_ids(coord_module.ir) if i.startswith("energi_frossen_")]

    def test_frossen_klokken_starter_paa_nytt_etter_utfall(self, coord_module):
        """Comebacket skal ikke bli et frossen-varsel i samme sekund.

        Telleren gikk sin gang mens vi var blinde. Det vi mistet melder utfallet,
        og et sprang som blir forkastet melder seg selv.
        """
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.tpi", "unavailable")
        _poll(coord_module, coord, start + timedelta(hours=10))

        # Måleren teller videre der ute, så spranget forkastes som outlier.
        benk.sett("sensor.tpi", 1400.0)
        resultat = _poll(coord_module, coord, start + timedelta(hours=10, minutes=1))
        assert FROSSEN not in _typer(resultat)
        assert coord._last_energy_increase == start + timedelta(hours=10, minutes=1)

    def test_spotutfall_erstatter_utfall_for_samme_sensor(self, coord_module):
        """Spot_utlopt sier alt utfallet sier, og i tillegg hva det koster."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.spot_price", "unavailable")
        resultat = _poll(coord_module, coord, start + timedelta(hours=3))

        assert _typer(resultat) == {SPOT_UTLOPT}


class TestForkastetDelta:
    """Deteksjon 4: kWh som ble kastet, skal synes som et fiksbart varsel."""

    def test_stort_sprang_gir_fiksbart_issue_med_kwh(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.tpi", 1145.4)
        _poll(coord_module, coord, start + timedelta(minutes=1))

        kall = next(
            k
            for k in coord_module.ir.async_create_issue.call_args_list
            if k.args[2] == f"energi_delta_forkastet_{coord.entry.entry_id}"
        )
        assert kall.kwargs["is_fixable"] is True
        plassholdere = kall.kwargs["translation_placeholders"]
        assert plassholdere["kwh"] == "145.4"
        assert plassholdere["sensor"] == "sensor.tpi"
        assert "15.06.2026" in plassholdere["forrige"]

    def test_plassholderen_peker_paa_forrige_avlesning(self, coord_module):
        """O3: hovedtilfellet er comebacket etter et langt utfall, ikke ett minutt.

        08.08.2026 sto telleren vår på samme tall i 237 timer mens måleren gikk
        videre. Varselet skal si hva spranget måles fra.
        """
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 7, 29, 10, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.tpi", "unavailable")
        _poll(coord_module, coord, start + timedelta(hours=100))

        benk.sett("sensor.tpi", 1145.4)
        _poll(coord_module, coord, datetime(2026, 8, 8, 8, 0))

        kall = next(
            k
            for k in coord_module.ir.async_create_issue.call_args_list
            if k.args[2] == f"energi_delta_forkastet_{coord.entry.entry_id}"
        )
        plassholdere = kall.kwargs["translation_placeholders"]
        assert plassholdere["forrige"] == "29.07.2026 kl. 10:00"

    def test_negativt_sprang_gir_issue(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.tpi", 12.0)
        _poll(coord_module, coord, start + timedelta(minutes=1))

        assert f"energi_delta_forkastet_{coord.entry.entry_id}" in _issue_ids(coord_module.ir)

    def test_forkastet_delta_stopper_ikke_frossen_klokken(self, coord_module):
        """Et kastet sprang er ikke forbruk, så det skal ikke telle som økning."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.tpi", 1145.4)
        _poll(coord_module, coord, start + timedelta(minutes=1))
        assert coord._last_energy_increase == start


class TestFriskmelding:
    """Alt skal rydde etter seg når inputen kommer tilbake."""

    def test_alle_issues_slettes_ved_friskmelding(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.power", "unavailable")
        benk.sett("sensor.spot_price", "unavailable")
        # tpi rapporterer, men står stille: det er frossen, ikke utfall.
        resultat = _poll(coord_module, coord, start + timedelta(hours=4))
        assert _typer(resultat) == {UTFALL, FROSSEN, SPOT_UTLOPT}

        coord_module.ir.async_delete_issue.reset_mock()
        benk.sett("sensor.power", 5000)
        benk.sett("sensor.tpi", 1005.0)
        benk.sett("sensor.spot_price", 1.20)
        resultat = _poll(coord_module, coord, start + timedelta(hours=4, minutes=1))

        assert resultat["maaledata_problem"] is False
        slettet = _slettede_issue_ids(coord_module.ir)
        for prefix in ("input_utfall", "energi_frossen", "spot_utfall"):
            assert f"{prefix}_{coord.entry.entry_id}" in slettet

    def test_issue_id_er_per_entry(self, coord_module):
        """Incident 001: lagrings- og varselnøkler følger entry_id, aldri DSO-id."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk, entry_id="annen_entry")
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.power", "unavailable")
        _poll(coord_module, coord, start + timedelta(hours=1))

        assert "input_utfall_annen_entry" in _issue_ids(coord_module.ir)


class TestVarseletFolgerBerorteInput:
    """Varselet skal peke på de sensorene som er nede nå, ikke de som var det.

    Én issue dekker alle inputene som er nede av samme grunn. Da må teksten
    bygges av hele listen og skrives om når listen endrer seg. Ble den bygget
    av den første raden og stående, sa varselet at effektmåleren var borte
    lenge etter at den var tilbake, mens energimåleren som faktisk lå nede
    ikke sto nevnt noe sted. Brukeren feilsøkte da en frisk sensor.
    """

    @staticmethod
    def _begge_nede(coord_module, benk, coord, start, minutter=45):
        """Effekt- og energimåleren ute samtidig, over grace."""
        benk.sett("sensor.power", "unavailable")
        benk.sett("sensor.tpi", "unavailable")
        return _poll(coord_module, coord, start + timedelta(minutes=minutter))

    def test_begge_staar_i_varselet_mens_begge_er_nede(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        self._begge_nede(coord_module, benk, coord, start)

        plassholdere = _siste_plassholdere(coord_module.ir, f"input_utfall_{coord.entry.entry_id}")
        assert plassholdere["input"] == "effektmåleren, energimåleren"
        assert plassholdere["detaljer"] == (
            "- effektmåleren (sensor.power): 0.8\n- energimåleren (sensor.tpi): 0.8"
        )

    def test_delvis_friskmelding_skriver_om_varselet(self, coord_module):
        """Effektmåleren er tilbake, energimåleren er ikke. Da skal bare den stå."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)
        self._begge_nede(coord_module, benk, coord, start)

        benk.sett("sensor.power", 5000)
        resultat = _poll(coord_module, coord, start + timedelta(minutes=46))

        assert [p["input"] for p in resultat["input_problemer"]] == ["energi"]
        plassholdere = _siste_plassholdere(coord_module.ir, f"input_utfall_{coord.entry.entry_id}")
        assert plassholdere["input"] == "energimåleren"
        assert plassholdere["entity_id"] == "sensor.tpi"
        assert "sensor.power" not in plassholdere["detaljer"]

    def test_delvis_friskmelding_fjerner_ikke_varselet(self, coord_module):
        """Negativ prøve: det skal stå til alle er friske, ikke til den første er det."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)
        self._begge_nede(coord_module, benk, coord, start)

        coord_module.ir.async_delete_issue.reset_mock()
        benk.sett("sensor.power", 5000)
        resultat = _poll(coord_module, coord, start + timedelta(minutes=46))

        assert resultat["maaledata_problem"] is True
        slettet = _slettede_issue_ids(coord_module.ir)
        assert f"input_utfall_{coord.entry.entry_id}" not in slettet

    def test_siste_friskmelding_fjerner_varselet(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)
        self._begge_nede(coord_module, benk, coord, start)

        benk.sett("sensor.power", 5000)
        _poll(coord_module, coord, start + timedelta(minutes=46))

        coord_module.ir.async_delete_issue.reset_mock()
        benk.sett("sensor.tpi", 1005.0)
        resultat = _poll(coord_module, coord, start + timedelta(minutes=47))

        assert resultat["input_problemer"] == []
        assert f"input_utfall_{coord.entry.entry_id}" in _slettede_issue_ids(coord_module.ir)

    def test_varigheten_folger_med_over_flere_oppdateringer(self, coord_module):
        """Varselet skal ikke stå og si 0,8 timer etter to timer uten data."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.power", "unavailable")
        _poll(coord_module, coord, start + timedelta(minutes=45))
        issue_id = f"input_utfall_{coord.entry.entry_id}"
        assert _siste_plassholdere(coord_module.ir, issue_id)["timer"] == "0.8"

        _poll(coord_module, coord, start + timedelta(hours=2, minutes=5))
        assert _siste_plassholdere(coord_module.ir, issue_id)["timer"] == "2.0"

    def test_ingen_varsel_naar_ingenting_er_galt(self, coord_module):
        """Den vanlige dagen: alle sensorer leverer, ingen issue reises."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        for minutt in range(5):
            benk.sett("sensor.tpi", 1000.0 + minutt)
            resultat = _poll(coord_module, coord, start + timedelta(minutes=minutt))

        assert resultat["input_problemer"] == []
        assert resultat["maaledata_problem"] is False
        assert not [i for i in _issue_ids(coord_module.ir) if i.startswith("input_utfall_")]

    def test_enhetsvarselet_navner_begge_sensorene(self, coord_module):
        """Samme regel for enhetssorten: hver sensor med sin egen enhet."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.ENHETER = {**benk.ENHETER, "sensor.power": "kvar", "sensor.spot_price": "EUR/MWh"}
        _poll(coord_module, coord, start + timedelta(minutes=1))

        plassholdere = _siste_plassholdere(coord_module.ir, f"input_enhet_{coord.entry.entry_id}")
        assert plassholdere["detaljer"] == (
            "- effektmåleren (sensor.power): kvar\n- spotpris-sensoren (sensor.spot_price): EUR/MWh"
        )

    def test_enhetsvarselet_skrives_om_naar_den_ene_rettes(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.ENHETER = {**benk.ENHETER, "sensor.power": "kvar", "sensor.spot_price": "EUR/MWh"}
        _poll(coord_module, coord, start + timedelta(minutes=1))

        coord_module.ir.async_delete_issue.reset_mock()
        benk.ENHETER = {**benk.ENHETER, "sensor.power": "W"}
        _poll(coord_module, coord, start + timedelta(minutes=2))

        issue_id = f"input_enhet_{coord.entry.entry_id}"
        plassholdere = _siste_plassholdere(coord_module.ir, issue_id)
        assert plassholdere["input"] == "spotpris-sensoren"
        assert plassholdere["enhet"] == "EUR/MWh"
        assert issue_id not in _slettede_issue_ids(coord_module.ir)


class TestJuliReplay:
    """Replay av det ekte HAN-utfallet, time for time gjennom coordinatoren.

    Utfallsvinduet leses fra fixturenes egen `metadata.datahull`, som er stedet
    hullet er dokumentert. Juli slutter 31.07 kl. 23 og august tar over 01.08
    kl. 00, så de to hullene henger sammen til ett: 29.07 kl. 11 til 08.08 kl. 07,
    med sensorene tilbake kl. 08. August-fixturen er med utelukkende for å få med
    comebacket.

    Juli-fixturen har kwh fylt fra Elhub i etterkant og august har ingen tall i
    det hele tatt. Måleren telte videre mens sensoren var borte, så tpi-verdien
    som dukker opp ved comebacket inkluderer hullet. De ukjente august-timene
    teller som null her, framfor at testen dikter opp forbruk.
    """

    @staticmethod
    def _timer() -> tuple[list[dict], datetime, datetime]:
        juli = json.loads((FIXTURES_DIR / "bkk_juli_2026_hourly.json").read_text())
        august = json.loads((FIXTURES_DIR / "bkk_august_2026_hourly.json").read_text())
        hull_start = datetime.fromisoformat(juli["metadata"]["datahull"]["fra_og_med"]).replace(tzinfo=None)
        hull_slutt = datetime.fromisoformat(august["metadata"]["datahull"]["til_og_med"]).replace(tzinfo=None)
        return juli["hours"] + august["hours"], hull_start, hull_slutt

    @pytest.fixture
    def replay(self, coord_module):
        timer, hull_start, hull_slutt = self._timer()
        assert hull_start == datetime(2026, 7, 29, 11, 0)
        assert hull_slutt == datetime(2026, 8, 8, 7, 0)
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk, spotpris_inkl_mva=False)

        maalerstand = 133282.18
        benk.sett("sensor.tpi", maalerstand)
        benk.sett("sensor.power", 0)
        forste = datetime.fromisoformat(timer[0]["start_local"]).replace(tzinfo=None)
        coord_module.dt_util.now.return_value = forste
        coord._current_month = forste.strftime("%Y-%m")
        _poll(coord_module, coord, forste)

        logg: list[tuple[datetime, bool, set[str]]] = []
        for time in timer:
            na = datetime.fromisoformat(time["start_local"]).replace(tzinfo=None)
            nede = hull_start <= na <= hull_slutt
            maalerstand += time["kwh"] or 0.0
            if nede:
                benk.sett("sensor.power", "unavailable")
                benk.sett("sensor.tpi", "unavailable")
            else:
                benk.sett("sensor.power", time["p_max_w"])
                benk.sett("sensor.tpi", round(maalerstand, 3))
            benk.sett("sensor.spot_price", time["spot_nok_kwh_eks_mva"])
            resultat = _poll(coord_module, coord, na)
            logg.append((na, resultat["maaledata_problem"], _typer(resultat)))
        return logg

    def test_utfallet_starter_29_juli_kl_11(self, replay):
        """Sanity: fixturen markerer hullet der vi tror det er."""
        forste_nede = next(tid for tid, _, typer in replay if UTFALL in typer or FROSSEN in typer)
        assert forste_nede == datetime(2026, 7, 29, 11, 0)

    def test_vaktholdet_slaar_paa_innen_tre_timer(self, replay):
        utfall_start = datetime(2026, 7, 29, 11, 0)
        paa = next(tid for tid, problem, _ in replay if problem and tid >= utfall_start)
        assert paa - utfall_start <= timedelta(hours=3)

    def test_vaktholdet_staar_paa_gjennom_hele_utfallet(self, replay):
        vindu = [
            (tid, problem)
            for tid, problem, _ in replay
            if datetime(2026, 7, 29, 15, 0) <= tid < datetime(2026, 8, 8, 8, 0)
        ]
        assert vindu, "fant ingen timer i utfallsvinduet"
        assert all(problem for _, problem in vindu)

    def test_hullet_meldes_som_utfall_ikke_ogsaa_frossen(self, replay):
        """Én årsak, ett varsel.

        Sensoren var borte i hele hullet, og da eier utfalls-deteksjonen
        hendelsen. Frossen-teksten sier at sensoren rapporterer mens telleren
        står stille, og det ville vært usant her. Den fasen har sin egen dekning
        i TestFrossenTeller.
        """
        typer = set()
        for tid, _, t in replay:
            if datetime(2026, 7, 29, 11, 0) <= tid < datetime(2026, 8, 8, 8, 0):
                typer |= t
        assert typer == {UTFALL}

    def test_vaktholdet_slaar_av_etter_comebacket(self, replay):
        etter = [(tid, problem) for tid, problem, _ in replay if tid >= datetime(2026, 8, 8, 8, 0)]
        assert etter[0][0] == datetime(2026, 8, 8, 8, 0)
        av = next(tid for tid, problem in etter if not problem)
        assert av == datetime(2026, 8, 8, 8, 0)
        assert not any(problem for tid, problem in etter if tid > av)


class TestSlettetEntitet:
    """Deteksjon 4: entiteten finnes ikke lenger i det hele tatt.

    Før kastet coordinatoren `UpdateFailed` før vaktholdet rakk å si fra, og
    stoppet samtidig energi og energiledd som ikke trengte den sensoren. Nå
    melder vaktholdet utfallet med `finnes: false`, og alt som fortsatt har
    datagrunnlag regner videre (stromkalkulator-37d1wwi).
    """

    def test_slettet_effektsensor_melder_utfall_uten_a_felle_oppdateringen(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.power", None)
        resultat = _poll(coord_module, coord, start + timedelta(minutes=45))

        problem = next(p for p in resultat["input_problemer"] if p["input"] == "effekt")
        assert problem["type"] == UTFALL
        assert problem["finnes"] is False
        assert problem["grunn"] == "finnes_ikke"
        assert resultat["current_power_kw"] is None

    def test_unavailable_entitet_finnes_fortsatt(self):
        """Motsatt retning: en entitet som svarer unavailable er ikke slettet.

        De to krever hver sin handling av brukeren, så de skal ikke se like ut.
        """
        import stromkalkulator.coordinator as coord_modul

        benk = Sensorbenk()
        coord = _lag_coordinator(coord_modul, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_modul, coord, start)

        benk.sett("sensor.power", "unavailable")
        resultat = _poll(coord_modul, coord, start + timedelta(minutes=45))

        problem = next(p for p in resultat["input_problemer"] if p["input"] == "effekt")
        assert problem["finnes"] is True
        assert problem["grunn"] == "utilgjengelig"

    def test_energien_akkumulerer_videre_uten_effektsensor(self, coord_module):
        """Energisensoren trenger ikke effektsensoren for å telle."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.power", None)
        benk.sett("sensor.tpi", 1002.5)
        resultat = _poll(coord_module, coord, start + timedelta(minutes=45))

        assert resultat["monthly_consumption_total_kwh"] == pytest.approx(2.5)
        assert resultat["energiledd"] > 0

    def test_slettet_spotsensor_stopper_bare_de_spotavhengige_beloepene(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.spot_price", None)
        benk.sett("sensor.tpi", 1003.0)
        # Tre timer: lenger enn cachen av siste kjente pris, som er der for å
        # bære en kort glipp og ikke for å skjule en død sensor.
        resultat = _poll(coord_module, coord, start + timedelta(hours=3))

        assert resultat["spot_price_valid"] is False
        assert resultat["monthly_consumption_total_kwh"] == pytest.approx(3.0)
        assert resultat["energiledd"] > 0


class TestRuntimeEnhetsendring:
    """Deteksjon 5: sensoren svarer, men i en enhet vi ikke kan regne om.

    Det er ikke et utfall som går over av seg selv, så det meldes uten grace og
    med sin egen problemtype.
    """

    def test_enhetsendring_gir_problemtype_enhet_og_issue(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.ENHETER = {**benk.ENHETER, "sensor.spot_price": "EUR/MWh"}
        resultat = _poll(coord_module, coord, start + timedelta(minutes=1))

        problem = next(p for p in resultat["input_problemer"] if p["type"] == "enhet")
        assert problem["input"] == "spotpris"
        assert problem["raa_enhet"] == "EUR/MWh"
        assert f"input_enhet_{coord.entry.entry_id}" in _issue_ids(coord_module.ir)

    def test_gyldig_enhetsbytte_gir_ingen_varsel(self, coord_module):
        """Motsatt retning: NOK/kWh til øre/kWh er en enhet vi kan regne om.

        Falske positiver er grunnen til at forrige runde med vakthold ble
        avvist to ganger, så hver deteksjon skal ha en negativ test.
        """
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.ENHETER = {**benk.ENHETER, "sensor.spot_price": "øre/kWh"}
        benk.sett("sensor.spot_price", 120.0)
        resultat = _poll(coord_module, coord, start + timedelta(minutes=1))

        assert "enhet" not in _typer(resultat)
        assert resultat["spot_price_valid"] is True

    def test_issue_slettes_naar_enheten_rettes(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.ENHETER = {**benk.ENHETER, "sensor.spot_price": "EUR/MWh"}
        _poll(coord_module, coord, start + timedelta(minutes=1))

        benk.ENHETER = {**benk.ENHETER, "sensor.spot_price": "NOK/kWh"}
        resultat = _poll(coord_module, coord, start + timedelta(minutes=2))

        assert "enhet" not in _typer(resultat)
        assert f"input_enhet_{coord.entry.entry_id}" in _slettede_issue_ids(coord_module.ir)

    def test_leverandorpris_med_feil_enhet_melder_seg(self, coord_module):
        """Kontrakt §1 gjelder alle roller, også den som ikke varsler ved utfall.

        Leverandørprisen ble hoppet over før enhetssjekken, så en sensor som
        gikk til EUR/kWh under drift ga verken problemrad eller repair.
        Sammenligningssensoren sto stille uten at noe sted sa hvorfor.
        """
        benk = Sensorbenk()
        benk.sett("sensor.elco_price", 1.4)
        benk.ENHETER = {**benk.ENHETER, "sensor.elco_price": "NOK/kWh"}
        coord = _lag_coordinator(coord_module, benk, electricity_company_price_sensor="sensor.elco_price")
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.ENHETER = {**benk.ENHETER, "sensor.elco_price": "EUR/kWh"}
        resultat = _poll(coord_module, coord, start + timedelta(minutes=1))

        problem = next(p for p in resultat["input_problemer"] if p["type"] == "enhet")
        assert problem["input"] == "leverandorpris"
        assert problem["raa_enhet"] == "EUR/kWh"
        assert f"input_enhet_{coord.entry.entry_id}" in _issue_ids(coord_module.ir)

    def test_leverandorpris_i_utfall_melder_fortsatt_ingenting(self, coord_module):
        """Negativ prøve på den over: unntaket for utfall står som det sto.

        Enhetsgrenen skal slippe leverandørprisen gjennom, ikke hele
        vaktholdet. Blandes de to, får alle med en leverandørprissensor et
        varsel hver gang den integrasjonen starter på nytt.
        """
        benk = Sensorbenk()
        benk.sett("sensor.elco_price", 1.4)
        benk.ENHETER = {**benk.ENHETER, "sensor.elco_price": "NOK/kWh"}
        coord = _lag_coordinator(coord_module, benk, electricity_company_price_sensor="sensor.elco_price")
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.elco_price", "unavailable")
        resultat = _poll(coord_module, coord, start + timedelta(minutes=90))

        assert resultat["input_problemer"] == []
        assert resultat["maaledata_problem"] is False

    def test_enhetsfeil_erstatter_ikke_et_ekte_utfall(self, coord_module):
        """En borte sensor har ingen enhet å klage på, og skal melde utfall."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.power", None)
        resultat = _poll(coord_module, coord, start + timedelta(minutes=45))

        typer = {p["type"] for p in resultat["input_problemer"] if p["input"] == "effekt"}
        assert typer == {UTFALL}


class TestPrisenhetUbekreftet:
    """§4: en prissensor uten enhet godtas, men brukeren skal bekrefte den."""

    def _uten_enhet(self, benk):
        benk.ENHETER = {**benk.ENHETER, "sensor.spot_price": None}

    def test_varsel_reises_for_prissensor_uten_enhet(self, coord_module):
        benk = Sensorbenk()
        self._uten_enhet(benk)
        coord = _lag_coordinator(coord_module, benk)
        _poll(coord_module, coord, datetime(2026, 6, 15, 12, 0))

        assert f"prisenhet_ubekreftet_{coord.entry.entry_id}" in _issue_ids(coord_module.ir)

    def test_ingen_varsel_naar_sensoren_har_enhet(self, coord_module):
        """Den som har en Nord Pool-sensor med NOK/kWh skal ikke se noe."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        _poll(coord_module, coord, datetime(2026, 6, 15, 12, 0))

        assert f"prisenhet_ubekreftet_{coord.entry.entry_id}" not in _issue_ids(coord_module.ir)

    def test_bekreftet_rolle_gir_ingen_varsel(self, coord_module):
        benk = Sensorbenk()
        self._uten_enhet(benk)
        coord = _lag_coordinator(coord_module, benk, extra_data={"prisenhet_bekreftet": ["spotpris"]})
        _poll(coord_module, coord, datetime(2026, 6, 15, 12, 0))

        assert f"prisenhet_ubekreftet_{coord.entry.entry_id}" not in _issue_ids(coord_module.ir)

    def test_varselet_ryddes_naar_enheten_kom_mens_ha_var_nede(self, coord_module):
        """Ryddingen kan ikke stole på minnet: det er tomt etter en omstart.

        Fikk sensoren enhet mens HA sto nede, sa minnet ved oppstart at ingen
        issue var aktiv, og da ble den aldri slettet. Varselet ble stående for
        godt om noe som var i orden.
        """
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        _poll(coord_module, coord, datetime(2026, 6, 15, 12, 0))

        assert f"prisenhet_ubekreftet_{coord.entry.entry_id}" in _slettede_issue_ids(coord_module.ir)

    def test_ryddingen_skjer_en_gang_ikke_hver_poll(self, coord_module):
        """Negativ prøve: den sletter ikke i vei ved hver eneste oppdatering."""
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        for minutt in range(4):
            _poll(coord_module, coord, start + timedelta(minutes=minutt))

        slettet = [i for i in _slettede_issue_ids(coord_module.ir) if i.startswith("prisenhet_ubekreftet")]
        assert len(slettet) == 1

    def test_varselet_reises_en_gang_ikke_hver_poll(self, coord_module):
        benk = Sensorbenk()
        self._uten_enhet(benk)
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        for minutt in range(4):
            _poll(coord_module, coord, start + timedelta(minutes=minutt))

        reist = [i for i in _issue_ids(coord_module.ir) if i.startswith("prisenhet_ubekreftet")]
        assert len(reist) == 1
