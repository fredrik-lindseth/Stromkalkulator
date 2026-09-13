"""Tester for at `_monthly_norgespris_compensation` respekterer Norgespris-taket.

Bakgrunn (researchrapport, scenario 3): kompensasjons-akkumulatoren ble
oppdatert for *alle* timer der `energy_kwh > 0 and spot_price_valid`, også
etter at månedsforbruket passerte taket på 5000 kWh (bolig) / 1000 kWh
(fritidsbolig). For storforbrukere overdrev verktøyet både besparelse og tap
på sammenligningssensoren, fordi timene over taket faktisk faktureres til
spot, ikke til Norgespris.

Første fiks var å slå av akkumuleringen når `norgespris_over_tak` var sann.
Den lot fortsatt hele poll-deltaet bli enten helt med eller helt utenfor, etter
hvor i minuttet grensen falt. Kostnadskjernen deler i stedet kilowattimene i én
del under og én over taket før prisen legges på (234odp5), så grensen treffer
på kilowattimen framfor på pollen.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tests.conftest import _make_entry, _make_hass, _run_update

_real_datetime = datetime


def _align_month(coordinator, when):
    """Sett coordinator-tidsstempel slik at vi unngå tilfeldig månedsskifte i tester.

    conftest setter `dt_util.now()` til 2026-06-15 ved import. Når en test
    deretter polled på april-tid utløser det _handle_month_rollover som
    nullstiller _monthly_consumption. Vi setter _current_month til testens
    måned for å unngå dette.
    """
    coordinator._current_month = when.strftime("%Y-%m")
    coordinator._current_date = when.strftime("%Y-%m-%d")
    coordinator._current_hour = when.hour


def _run_minutes(coord_module, coordinator, start, minutes):
    """Kjør N polling-sykluser, ett minutt om gangen, og returner siste resultat."""
    result = _run_update(coord_module, coordinator, now=start)
    for i in range(1, minutes + 1):
        result = _run_update(coord_module, coordinator, now=start + timedelta(minutes=i))
    return result


class TestNorgesprisCompensationUnderTak:
    """Under taket: kompensasjon akkumuleres som vanlig."""

    def test_compensation_accumulates_under_cap(self, coord_module):
        """Med forbruk godt under 5000 kWh skal hver time gi (norgespris - spot) * kWh."""
        start = _real_datetime(2026, 4, 9, 12, 0)
        hass = _make_hass(power_w=6000, spot_price=1.50)  # 6 kW, spot 1.50
        entry = _make_entry(har_norgespris=True)
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        _align_month(coordinator, start)

        # 10 polling-sykluser à 1 min = 10 min * 6 kW = 1.0 kWh forbruk totalt
        result = _run_minutes(coord_module, coordinator, start, 10)

        # Kompensasjon = (0.50 - 1.50) * 1.0 kWh = -1.0 kr (tap for Norgespris-kunde
        # når spot er billigere... vent, spot er DYRERE her, så kunden tjener på
        # Norgespris. Fortegn-konvensjon i koden: (norgespris - spot) * kWh.
        # Med norgespris=0.50, spot=1.50: bidraget er negativt = "kunden taper
        # ikke" / "spot er dyrere enn norgespris").
        expected = (0.50 - 1.50) * 1.0
        assert result["monthly_norgespris_compensation_kr"] == round(expected, 2)
        assert result["norgespris_over_tak"] is False

    def test_compensation_at_exactly_threshold(self, coord_module):
        """Forbruk akkurat under 5000 kWh: kompensasjon er full for siste time."""
        start = _real_datetime(2026, 4, 9, 12, 0)
        hass = _make_hass(power_w=6000, spot_price=2.00)
        entry = _make_entry(har_norgespris=True)
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        _align_month(coordinator, start)

        # Forhåndsfyll månedsforbruk til 4999 kWh
        coordinator._monthly_consumption = coord_module.ConsumptionData(dag=4999.0, natt=0.0)

        # Én syklus: skal være under taket fortsatt, så kompensasjonen telles.
        # (norgespris_over_tak vurderes mot monthly_total_kwh FØR ny energi
        # akkumuleres? Sjekk koden: monthly_total_kwh = self._monthly_consumption.total
        # leses ETTER at energi er akkumulert. Med 4999 + 0.1 = 4999.1 < 5000 er
        # vi fortsatt under.)
        _run_update(coord_module, coordinator, now=start)
        result = _run_update(coord_module, coordinator, now=start + timedelta(minutes=1))

        # Forbruket akkumulert i denne syklusen var ca 0.1 kWh.
        # Kompensasjon skal være positiv (norgespris 0.50 - spot 2.00 = -1.50, men
        # vi vil bekrefte at akkumuleringen kjørte.
        assert result["monthly_norgespris_compensation_kr"] != 0.0
        assert result["norgespris_over_tak"] is False


class TestNorgesprisCompensationOverTak:
    """Over taket: kompensasjon skal IKKE akkumuleres lenger."""

    def test_no_compensation_added_when_over_cap(self, coord_module):
        """Når forbruket allerede er over 5000 kWh skal nye timer ikke bidra."""
        start = _real_datetime(2026, 4, 9, 12, 0)
        hass = _make_hass(power_w=6000, spot_price=2.00)
        entry = _make_entry(har_norgespris=True)
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        _align_month(coordinator, start)

        # Sett som om kunden allerede har forbrukt 5500 kWh denne måneden.
        # Kompensasjons-akkumulator har en gammel verdi som ikke skal endres
        # av etterfølgende polling.
        coordinator._monthly_consumption = coord_module.ConsumptionData(dag=5500.0, natt=0.0)
        coordinator._monthly_norgespris_compensation = -100.0

        # Kjør 10 polling-sykluser med høyt forbruk. Ingen skal akkumulere
        # kompensasjon fordi vi er over taket.
        result = _run_minutes(coord_module, coordinator, start, 10)

        assert result["monthly_norgespris_compensation_kr"] == -100.0
        assert result["norgespris_over_tak"] is True

    def test_storforbruker_6000_kwh_compensation_stops_at_cap(self, coord_module):
        """Storforbruker (>5000 kWh) får kompensasjon kun for timer under taket.

        Reproduserer feilen fra research-rapporten: 6000-kWh-husholdning som
        passerer taket midt i måneden skal ha kompensasjon kun for de
        første 5000 kWh, ikke alle 6000.
        """
        start = _real_datetime(2026, 4, 9, 12, 0)
        # 60 kW konstant. 1 min * 60 kW = 1.0 kWh per syklus.
        hass = _make_hass(power_w=60_000, spot_price=2.00)
        entry = _make_entry(har_norgespris=True)
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        _align_month(coordinator, start)

        # Start godt under taket
        coordinator._monthly_consumption = coord_module.ConsumptionData(dag=4990.0, natt=0.0)
        coordinator._monthly_norgespris_compensation = 0.0

        # 20 polling-sykluser à 1 min à 60 kW = 20 kWh, ender på 5010 kWh.
        # Krysser taket mellom syklus 10 og 11.
        result = _run_minutes(coord_module, coordinator, start, 20)

        # Taket deler kilowattimene, det slår ikke av en bryter (234odp5).
        # Start 4990 kWh, 20 kWh forbrukt: nøyaktig 10 av dem ligger under
        # 5000-taket og får kompensasjon, de ti andre får ingen.
        # 10 kWh * (0.50 - 2.00) = -15.0 kr.
        # Den gamle koden prisen hele poll-deltaet etter månedstotalen etterpå
        # og landet på -13.5; uten noen tak-håndtering i det hele tatt: -30.
        compensation = result["monthly_norgespris_compensation_kr"]
        assert compensation == pytest.approx(-15.0, abs=0.01), (
            f"Compensation {compensation} skal dekke nøyaktig de 10 kilowattimene som lå under taket."
        )
        assert result["norgespris_over_tak"] is True
        assert result["monthly_consumption_total_kwh"] > 5000


class TestNorgesprisCompensationFritidsbolig:
    """Fritidsbolig har 1000 kWh-tak: sjekk at samme gating fungerer der."""

    def test_fritidsbolig_compensation_stops_at_1000_kwh(self, coord_module):
        """Fritidsbolig krysser 1000 kWh-taket: kompensasjon skal stoppe."""
        start = _real_datetime(2026, 4, 9, 12, 0)
        hass = _make_hass(power_w=60_000, spot_price=2.00)
        entry = _make_entry(har_norgespris=True)
        entry.data["boligtype"] = "fritidsbolig"
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        _align_month(coordinator, start)

        coordinator._monthly_consumption = coord_module.ConsumptionData(dag=995.0, natt=0.0)
        coordinator._monthly_norgespris_compensation = 0.0

        # 20 sykluser à 1 kWh = 20 kWh. Krysser 1000-taket etter ca 5 sykluser.
        result = _run_minutes(coord_module, coordinator, start, 20)

        # Start 995, 20 kWh forbrukt: 5 kWh under 1000-taket.
        # 5 kWh * (0.50 - 2.00) = -7.5 kr.
        compensation = result["monthly_norgespris_compensation_kr"]
        assert compensation == pytest.approx(-7.5, abs=0.01), (
            f"Fritidsbolig-kompensasjon {compensation} skal dekke de 5 kilowattimene under 1000-kWh-taket."
        )
        assert result["norgespris_over_tak"] is True


class TestNorgesprisCompensationBoundaryCrossing:
    """Eksakt takgrense inne i ett intervall."""

    def test_kilowattimen_som_naar_taket_er_med(self, coord_module):
        """Den kilowattimen som tar totalen til nøyaktig 5000 ligger under taket.

        Taket er en mengde kilowattimer, ikke et tidspunkt. Deltaet deles i én
        del under og én over taket før prisen legges på (234odp5), så et
        pollvindu som krysser grensen blir ikke lenger enten helt med eller helt
        utenfor etter hvor i minuttet grensen falt.
        """
        start = _real_datetime(2026, 4, 9, 12, 0)
        # 60 kW: 1 kWh per minutt.
        hass = _make_hass(power_w=60_000, spot_price=2.00)
        entry = _make_entry(har_norgespris=True)
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        _align_month(coordinator, start)

        coordinator._monthly_consumption = coord_module.ConsumptionData(dag=4999.0, natt=0.0)
        coordinator._monthly_norgespris_compensation = 0.0

        _run_update(coord_module, coordinator, now=start)
        result = _run_update(coord_module, coordinator, now=start + timedelta(minutes=1))

        # 4999 -> 5000: hele kilowattimen ligger under taket.
        # 1 kWh * (0.50 - 2.00) = -1.5 kr.
        compensation = result["monthly_norgespris_compensation_kr"]
        assert compensation == pytest.approx(-1.5, abs=0.01)
        assert result["norgespris_over_tak"] is True

    def test_kilowattimen_etter_taket_er_ikke_med(self, coord_module):
        """Står totalen på taket, gir neste kilowattime ingen kompensasjon."""
        start = _real_datetime(2026, 4, 9, 12, 0)
        hass = _make_hass(power_w=60_000, spot_price=2.00)
        entry = _make_entry(har_norgespris=True)
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        _align_month(coordinator, start)

        coordinator._monthly_consumption = coord_module.ConsumptionData(dag=5000.0, natt=0.0)
        coordinator._monthly_norgespris_compensation = 0.0

        _run_update(coord_module, coordinator, now=start)
        result = _run_update(coord_module, coordinator, now=start + timedelta(minutes=1))

        assert result["monthly_norgespris_compensation_kr"] == pytest.approx(0.0, abs=0.001)
        assert result["norgespris_over_tak"] is True
