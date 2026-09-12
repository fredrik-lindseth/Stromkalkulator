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

    def get(self, entity_id: str):
        verdi = self.verdier.get(entity_id, "__mangler__")
        if verdi == "__mangler__" or verdi is None:
            return None
        return _make_state(verdi)


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

    def test_issue_reises_kun_ved_overgang(self, coord_module):
        benk = Sensorbenk()
        coord = _lag_coordinator(coord_module, benk)
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.power", "unavailable")
        for minutter in (40, 50, 60, 70):
            _poll(coord_module, coord, start + timedelta(minutes=minutter))

        utfall_issues = [i for i in _issue_ids(coord_module.ir) if i.startswith("input_utfall_")]
        assert len(utfall_issues) == 1

    def test_leverandorpris_varsler_ikke(self, coord_module):
        """Leverandørprisen mater en sammenligningssensor og skal ikke alarmere."""
        benk = Sensorbenk()
        benk.sett("sensor.elco_price", 1.4)
        coord = _lag_coordinator(
            coord_module, benk, electricity_company_price_sensor="sensor.elco_price"
        )
        start = datetime(2026, 6, 15, 12, 0)
        _poll(coord_module, coord, start)

        benk.sett("sensor.elco_price", "unavailable")
        resultat = _poll(coord_module, coord, start + timedelta(minutes=45))

        assert resultat["maaledata_problem"] is False
        assert resultat["leverandorpris_gyldig"] is False

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
        hull_start = datetime.fromisoformat(
            juli["metadata"]["datahull"]["fra_og_med"]
        ).replace(tzinfo=None)
        hull_slutt = datetime.fromisoformat(
            august["metadata"]["datahull"]["til_og_med"]
        ).replace(tzinfo=None)
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
        forste_nede = next(
            tid for tid, _, typer in replay if UTFALL in typer or FROSSEN in typer
        )
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
        etter = [
            (tid, problem)
            for tid, problem, _ in replay
            if tid >= datetime(2026, 8, 8, 8, 0)
        ]
        assert etter[0][0] == datetime(2026, 8, 8, 8, 0)
        av = next(tid for tid, problem in etter if not problem)
        assert av == datetime(2026, 8, 8, 8, 0)
        assert not any(problem for tid, problem in etter if tid > av)
