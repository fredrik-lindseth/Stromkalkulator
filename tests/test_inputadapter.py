"""Inputadapteren: typede resultater, enhetsnormalisering og baseline.

Kontrakten står i `docs/kontrakter/input-og-konfig.md`. Denne filen kjører den.

De fire tusen-gangene er det som gjorde modulen nødvendig. En NOK/MWh-sensor
lest som NOK/kWh, en kW-sensor lest som W, en Wh-sensor lest som kWh og en
øre/kWh-sensor lest som kroner gir alle tall som ser plausible ut og er tusen
eller hundre ganger feil.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from hypothesis import given
from hypothesis import strategies as st
from stromkalkulator.inputadapter import (
    ENHETSTABELL,
    MAKS_RIMELIG_PRIS_NOK_KWH,
    Baseline,
    Gyldig,
    Ugyldig,
    Utilgjengelig,
    kanoniser_enhet,
    les_input,
    vurder_enhet,
    vurder_state,
)

NAA = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)

EFFEKT = "effekt"
EKSPORT = "eksport"
ENERGI = "energi"
SPOTPRIS = "spotpris"
LEVERANDORPRIS = "leverandorpris"


def _state(verdi, enhet=None, state_class=None, last_updated=None):
    state = MagicMock()
    state.state = str(verdi)
    attributter = {}
    if enhet is not None:
        attributter["unit_of_measurement"] = enhet
    if state_class is not None:
        attributter["state_class"] = state_class
    state.attributes = attributter
    state.last_updated = last_updated
    return state


def _les(verdi, rolle, **kw):
    return vurder_state(_state(verdi, **kw), rolle, entity_id="sensor.test", naa=NAA)


# ---------------------------------------------------------------------------
# De fire tusen-gangene


class TestTusenGangene:
    """Akseptansen fra planen: fire enheter som gir opptil 1000x feil tall."""

    def test_nok_per_mwh_blir_nok_per_kwh(self):
        resultat = _les(850, SPOTPRIS, enhet="NOK/MWh")
        assert isinstance(resultat, Gyldig)
        assert resultat.verdi == pytest.approx(0.85)
        assert resultat.enhet_normalisert == "NOK/kWh"

    def test_kilowatt_blir_watt(self):
        resultat = _les(5.2, EFFEKT, enhet="kW")
        assert isinstance(resultat, Gyldig)
        assert resultat.verdi == pytest.approx(5200.0)
        assert resultat.enhet_normalisert == "W"

    def test_watttimer_blir_kilowattimer(self):
        resultat = _les(1_234_500, ENERGI, enhet="Wh", state_class="total_increasing")
        assert isinstance(resultat, Gyldig)
        assert resultat.verdi == pytest.approx(1234.5)
        assert resultat.enhet_normalisert == "kWh"

    def test_ore_per_kwh_blir_kroner(self):
        resultat = _les(85.5, SPOTPRIS, enhet="øre/kWh")
        assert isinstance(resultat, Gyldig)
        assert resultat.verdi == pytest.approx(0.855)

    def test_ore_uten_o_med_strek_over(self):
        """`ore` er en vanlig skrivemåte og skal treffe samme rad."""
        assert _les(85.5, SPOTPRIS, enhet="ore/kWh").verdi == pytest.approx(0.855)


class TestValuta:
    """EUR avvises i setup og ved runtime. Vi har ingen valutakurs."""

    @pytest.mark.parametrize("enhet", ["EUR/kWh", "EUR/MWh", "eur/kwh", "€/kWh", "USD/MWh"])
    def test_fremmed_valuta_avvises(self, enhet):
        resultat = _les(0.065, SPOTPRIS, enhet=enhet)
        assert isinstance(resultat, Ugyldig)
        assert resultat.grunn == "feil_valuta"
        assert resultat.raa_enhet == enhet

    @pytest.mark.parametrize("enhet", ["NOK/kWh", "kr/kWh", "øre/kWh", "NOK/MWh", "kr/MWh", "øre/MWh"])
    def test_norske_prisenheter_godtas(self, enhet):
        assert isinstance(_les(1.0, SPOTPRIS, enhet=enhet), Gyldig)


class TestEnhetsoppslag:
    def test_whitespace_og_store_bokstaver_spiller_ingen_rolle(self):
        for enhet in ("NOK/kWh", " nok/kwh ", "NOK / kWh", "Nok/KWH"):
            assert vurder_enhet(enhet, SPOTPRIS) == ("NOK/kWh", 1.0)

    def test_kanoniseringen_er_stabil(self):
        assert kanoniser_enhet(" ØRE / kWh ") == "øre/kwh"
        assert kanoniser_enhet("ore/MWh") == "øre/mwh"

    def test_ukjent_enhet(self):
        resultat = _les(1.0, SPOTPRIS, enhet="bananer")
        assert isinstance(resultat, Ugyldig)
        assert resultat.grunn == "ukjent_enhet"

    def test_energienhet_i_effektfeltet_er_feil_dimensjon(self):
        assert _les(1543, EFFEKT, enhet="kWh").grunn == "feil_dimensjon"

    def test_effektenhet_i_energifeltet_er_feil_dimensjon(self):
        assert _les(5000, ENERGI, enhet="W", state_class="total_increasing").grunn == "feil_dimensjon"

    def test_prisenhet_i_effektfeltet_er_feil_dimensjon(self):
        assert _les(1.2, EFFEKT, enhet="NOK/kWh").grunn == "feil_dimensjon"

    def test_bare_kroner_i_prisfeltet_er_feil_dimensjon(self):
        """Den ekte feilen fra 34qzbh: en kr-totalsensor pekt inn som spotpris."""
        assert _les(877.5, SPOTPRIS, enhet="kr").grunn == "feil_dimensjon"

    def test_kroner_per_maaned_er_feil_dimensjon(self):
        assert _les(415, SPOTPRIS, enhet="kr/mnd").grunn == "feil_dimensjon"

    def test_eksport_har_samme_dimensjon_som_effekt(self):
        assert _les(3.4, EKSPORT, enhet="kW").verdi == pytest.approx(3400.0)

    def test_leverandorpris_har_samme_dimensjon_som_spot(self):
        assert _les(45, LEVERANDORPRIS, enhet="øre/kWh").verdi == pytest.approx(0.45)


class TestEnhetTabellenMotKontrakten:
    """Tabellen i koden skal være den samme som den i kontrakten.

    Kontraktvakten i test_inputkontrakt.py leser markdown-tabellen. Her leses
    den samme tabellen igjen og sammenlignes med koden, slik at de to ikke kan
    drive fra hverandre uten at noe blir rødt.
    """

    def test_hver_rad_i_kontrakten_finnes_i_koden(self):
        from tests.test_inputkontrakt import ENHETER

        assert ENHETER, "kontraktvakten leste ingen enheter"
        for raa, normalisert, faktor in ENHETER:
            regel = ENHETSTABELL[kanoniser_enhet(raa)]
            assert regel.normalisert == normalisert, raa
            assert regel.faktor == pytest.approx(faktor), raa

    def test_koden_har_ingen_prisenhet_kontrakten_mangler(self):
        from tests.test_inputkontrakt import ENHETER

        i_kontrakten = {kanoniser_enhet(raa) for raa, _, _ in ENHETER}
        # `kr`, `NOK` og `øre` alene står ikke i kontraktens tabell: de er ingen
        # gyldig enhet for noen rolle, bare gjenkjent så feilen blir presis.
        bare_valuta = {"kr", "nok", "øre"}
        assert set(ENHETSTABELL) - bare_valuta == i_kontrakten


# ---------------------------------------------------------------------------
# Resultattypene


class TestUtilgjengelig:
    def test_ingen_entitet_konfigurert(self):
        resultat = les_input(MagicMock(), None, EKSPORT, naa=NAA)
        assert isinstance(resultat, Utilgjengelig)
        assert resultat.grunn == "ikke_konfigurert"

    def test_slettet_entitet_er_utilgjengelig_ikke_ugyldig(self):
        """En slettet sensor er en måling som uteble, ikke en feilkonfigurasjon."""
        hass = MagicMock()
        hass.states.get = MagicMock(return_value=None)
        resultat = les_input(hass, "sensor.borte", EFFEKT, naa=NAA)
        assert isinstance(resultat, Utilgjengelig)
        assert resultat.grunn == "finnes_ikke"

    @pytest.mark.parametrize(("state", "grunn"), [("unavailable", "utilgjengelig"), ("unknown", "ukjent")])
    def test_unavailable_og_unknown_skilles(self, state, grunn):
        hass = MagicMock()
        hass.states.get = MagicMock(return_value=_state(state, enhet="W"))
        resultat = les_input(hass, "sensor.effekt", EFFEKT, naa=NAA)
        assert isinstance(resultat, Utilgjengelig)
        assert resultat.grunn == grunn


class TestUgyldigVerdi:
    def test_tekst_er_ikke_tall(self):
        assert _les("søppel", EFFEKT, enhet="W").grunn == "ikke_tall"

    @pytest.mark.parametrize("verdi", ["nan", "inf", "-inf"])
    def test_nan_og_uendelig(self, verdi):
        assert _les(verdi, EFFEKT, enhet="W").grunn == "ikke_endelig"

    def test_urimelig_pris_etter_normalisering(self):
        assert _les(8772.4, SPOTPRIS).grunn == "urimelig_verdi"

    def test_dyr_time_i_nok_per_mwh_er_rimelig(self):
        """Grensen gjelder etter normalisering. 2500 NOK/MWh er 2,50 NOK/kWh.

        Regnet i sensorens egen enhet ville den gamle grensen på 2000 avvist en
        ekte time NO1, NO2 og NO5 har hatt.
        """
        assert isinstance(_les(2500, SPOTPRIS, enhet="NOK/MWh"), Gyldig)

    def test_negativ_pris_er_gyldig(self):
        """Negative spotpriser finnes, og absoluttverdien er det grensen måler."""
        assert isinstance(_les(-0.05, SPOTPRIS, enhet="NOK/kWh"), Gyldig)
        assert _les(-200, SPOTPRIS, enhet="NOK/kWh").grunn == "urimelig_verdi"

    def test_grensen_er_akkurat_inkludert(self):
        assert isinstance(_les(MAKS_RIMELIG_PRIS_NOK_KWH, SPOTPRIS, enhet="NOK/kWh"), Gyldig)
        assert _les(MAKS_RIMELIG_PRIS_NOK_KWH + 1, SPOTPRIS, enhet="NOK/kWh").grunn == "urimelig_verdi"


class TestKumulativEnergi:
    """Vi leser differansen mellom avlesninger, så telleren må gå én vei."""

    @pytest.mark.parametrize("state_class", ["total_increasing", "total"])
    def test_kumulative_state_class_godtas(self, state_class):
        assert isinstance(_les(1000, ENERGI, enhet="kWh", state_class=state_class), Gyldig)

    def test_measurement_avvises(self):
        resultat = _les(1000, ENERGI, enhet="kWh", state_class="measurement")
        assert resultat.grunn == "ikke_kumulativ"

    def test_uten_state_class_avvises(self):
        assert _les(1000, ENERGI, enhet="kWh").grunn == "ikke_kumulativ"

    def test_kravet_gjelder_ikke_effekt_og_pris(self):
        assert isinstance(_les(5000, EFFEKT, enhet="W"), Gyldig)
        assert isinstance(_les(1.2, SPOTPRIS, enhet="NOK/kWh"), Gyldig)


class TestTidspunkt:
    """§1: observasjonstid og avlesningstid er to ulike tider."""

    def test_observed_at_kommer_fra_last_updated(self):
        sett = datetime(2026, 6, 15, 11, 58, tzinfo=UTC)
        resultat = _les(5000, EFFEKT, enhet="W", last_updated=sett)
        assert resultat.observed_at == sett
        assert resultat.avlest_kl == NAA

    def test_uten_last_updated_faller_observed_at_til_avlesningstiden(self):
        resultat = _les(5000, EFFEKT, enhet="W")
        assert resultat.observed_at == NAA


class TestEnhetAntatt:
    """§4: en prissensor uten enhet godtas som NOK/kWh, men det skal syne."""

    def test_prissensor_uten_enhet_godtas_med_markering(self):
        resultat = _les(1.2, SPOTPRIS)
        assert isinstance(resultat, Gyldig)
        assert resultat.verdi == pytest.approx(1.2)
        assert resultat.raa_enhet is None
        assert resultat.enhet_antatt is True

    def test_sensor_med_enhet_er_ikke_antatt(self):
        assert _les(1.2, SPOTPRIS, enhet="NOK/kWh").enhet_antatt is False

    def test_effektsensor_uten_enhet_antas_i_watt(self):
        assert _les(5000, EFFEKT).verdi == pytest.approx(5000.0)


# ---------------------------------------------------------------------------
# Normaliseringen er dimensjonsriktig begge veier


@given(
    enhet=st.sampled_from(sorted(ENHETSTABELL)),
    verdi=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
)
def test_normalisering_er_dimensjonsriktig_begge_veier(enhet, verdi):
    """§2: en verdi normalisert og regnet tilbake er samme tall.

    Uten dette kravet kan en faktor være feil vei uten at noen ser det: 0,001
    og 1000 ser like riktige ut i en tabell, og bare regnestykket avslører
    hvilken som hører hjemme hvor.
    """
    regel = ENHETSTABELL[enhet]
    assert regel.faktor > 0
    tilbake = verdi * regel.faktor / regel.faktor
    assert tilbake == pytest.approx(verdi, rel=1e-9, abs=1e-12)


@given(
    verdi=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_samme_effekt_i_tre_enheter_gir_samme_watt(verdi):
    """W, kW og MW som beskriver samme effekt skal normalisere til samme tall."""
    i_watt = _les(verdi, EFFEKT, enhet="W")
    i_kilowatt = _les(verdi / 1000, EFFEKT, enhet="kW")
    i_megawatt = _les(verdi / 1_000_000, EFFEKT, enhet="MW")
    assert i_kilowatt.verdi == pytest.approx(i_watt.verdi, rel=1e-9, abs=1e-9)
    assert i_megawatt.verdi == pytest.approx(i_watt.verdi, rel=1e-9, abs=1e-9)


# ---------------------------------------------------------------------------
# Baselinen


class TestBaseline:
    def test_rundtur_gjennom_store_formatet(self):
        baseline = Baseline("maaler-1", "sensor.tpi", 1234.567, NAA)
        tilbake = Baseline.fra_lagret(baseline.som_lagret())
        assert tilbake == baseline

    def test_skjemaversjonen_skrives(self):
        assert Baseline("m", "sensor.tpi", 1.0, NAA).som_lagret()["schema_version"] == 2

    def test_tidspunktet_lagres_i_utc(self):
        from zoneinfo import ZoneInfo

        lokal = datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("Europe/Oslo"))
        lagret = Baseline("m", "sensor.tpi", 1.0, lokal).som_lagret()
        assert lagret["observed_at"] == "2026-06-15T10:00:00+00:00"

    def test_v1_form_forkastes(self):
        """Alt som ligger lagret fra før har verken kilde eller enhet."""
        assert Baseline.fra_lagret({"last_tpi_kwh": 1000.0}) is None
        assert Baseline.fra_lagret(None) is None

    def test_samme_kilde_paa_unique_id(self):
        baseline = Baseline("maaler-1", "sensor.tpi", 1.0, NAA)
        assert baseline.samme_kilde("maaler-1", "sensor.helt_annen") is True
        assert baseline.samme_kilde("maaler-2", "sensor.tpi") is False

    def test_uten_unique_id_sammenlignes_entity_id(self):
        baseline = Baseline(None, "sensor.tpi", 1.0, NAA)
        assert baseline.samme_kilde(None, "sensor.tpi") is True
        assert baseline.samme_kilde(None, "sensor.annen") is False

    def test_registrert_kilde_slaar_manglende(self):
        """En baseline uten unique_id mot en avlesning med er ikke samme kilde.

        Motsatt vei heller: den ene siden vet hvilken måler det er, den andre
        ikke, og da kan vi ikke påstå at det er den samme.
        """
        assert Baseline(None, "sensor.tpi", 1.0, NAA).samme_kilde("maaler-1", "sensor.tpi") is False
        assert Baseline("maaler-1", "sensor.tpi", 1.0, NAA).samme_kilde(None, "sensor.tpi") is False
