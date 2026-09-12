"""Egendefinert nettselskap uten gjettet fastledd.

Til og med 1.16.0 hadde `custom` ti innebygde kapasitetstrinn i `dso.py`. De
var en mal, ikke priser: ingen prisliste ligger bak dem, og kapasitetsleddet er
et fast månedsbeløp, så tallet slo rett inn i månedskostnaden. Det er samme
feil som [incident 006](../docs/incidents/006-kapasitetstrinn-uten-kilde.md),
bare uten noe sted å hente de riktige tallene fra: det er bare brukeren som vet
hva selskapet hans tar.

Testene her vokter tre ting: at trinnene ikke kommer tilbake i katalogen, at
brukerens egen tabell leses akkurat slik den er skrevet, og at fastleddet er
ukjent og ikke null når tabellen mangler.

Sensorene testes i test_sensor_classes.py og test_monthly_sensors.py,
repair-varselet i test_repairs_egendefinert.py og skjemaene i
test_config_flow_options.py.
"""

from __future__ import annotations

import pytest
from stromkalkulator.const import DSO_EGENDEFINERT, resolve_avgiftssone
from stromkalkulator.dso import DSO_LIST, finn_kapasitetstrinn, parse_kapasitetstrinn

from tests.conftest import _make_entry, _make_hass, _run_update


def _lag_coordinator(coord_module, *, trinntabell=None, dso_id=DSO_EGENDEFINERT):
    """Coordinator for et anlegg, eventuelt med brukerens egen trinntabell."""
    ekstra = {"egendefinert_kapasitetstrinn": trinntabell} if trinntabell is not None else None
    entry = _make_entry(
        dso_id=dso_id,
        avgiftssone=resolve_avgiftssone(DSO_LIST[dso_id]),
        extra_data=ekstra,
    )
    return coord_module.NettleieCoordinator(_make_hass(), entry)


class TestKatalogenHarIngenTrinn:
    """Vakt mot at malen sniker seg inn igjen i dso.py."""

    def test_custom_har_tom_trinnliste(self):
        assert DSO_LIST[DSO_EGENDEFINERT]["kapasitetstrinn"] == []

    def test_custom_deler_ikke_trinn_med_noen(self):
        """En kopi fra et ekte nettselskap ville vært gjetning av samme slag."""
        for dso_id, data in DSO_LIST.items():
            if dso_id == DSO_EGENDEFINERT:
                continue
            assert (
                data["kapasitetstrinn"] != DSO_LIST[DSO_EGENDEFINERT]["kapasitetstrinn"]
                or not data["kapasitetstrinn"]
            )


class TestParserenLeserBrukerensTabell:
    """Formatet fra kontrakt §9: «2:155,5:250,10:415»."""

    def test_tre_trinn(self):
        assert parse_kapasitetstrinn("2:155,5:250,10:415") == [(2.0, 155), (5.0, 250), (10.0, 415)]

    def test_mellomrom_ignoreres(self):
        assert parse_kapasitetstrinn(" 2 : 155 , 5 : 250 ") == [(2.0, 155), (5.0, 250)]

    def test_punktum_som_desimaltegn(self):
        """155.5 kr/mnd rundes til hele kroner, som i katalogen."""
        assert parse_kapasitetstrinn("2:155.5") == [(2.0, 156)]

    def test_komma_som_desimaltegn(self):
        """Komma skiller par, men «155,5» uten kolon etter er ett tall."""
        assert parse_kapasitetstrinn("2:155,5") == [(2.0, 156)]

    def test_desimalgrense(self):
        assert parse_kapasitetstrinn("2.5:155") == [(2.5, 155)]

    def test_tomt_felt_er_lovlig(self):
        """Tomt betyr «jeg vet ikke», ikke null."""
        assert parse_kapasitetstrinn("") == []
        assert parse_kapasitetstrinn("   ") == []

    @pytest.mark.parametrize(
        "tekst",
        [
            "155",  # mangler kolon
            "2:",  # mangler pris
            ":155",  # mangler grense
            "to:155",  # ikke et tall
            "2:hundre",
            "5:250,2:155",  # synkende grenser
            "2:155,2:250",  # samme grense to ganger
            "0:155",  # grense må være over null
            "-2:155",
            "2:-155",  # negativ pris
            "2:155,,5:250",  # tomt trinn
        ],
    )
    def test_ugyldig_tabell_heves(self, tekst):
        with pytest.raises(ValueError):
            parse_kapasitetstrinn(tekst)


class TestOppslagMotBrukerensTabell:
    """Tabellen skal slå opp eksakt, uten mellomregning vi har funnet på."""

    @pytest.mark.parametrize(
        ("grunnlag", "ventet"),
        [(0.0, 155), (1.9, 155), (2.0, 250), (4.9, 250), (5.0, 415), (9.9, 415), (50.0, 415)],
    )
    def test_oppslag(self, grunnlag, ventet):
        trinn = parse_kapasitetstrinn("2:155,5:250,10:415")
        pris, _nummer, _intervall = finn_kapasitetstrinn(trinn, grunnlag)
        assert pris == ventet

    def test_oeverste_trinn_gjelder_alt_over(self):
        """Vi krever ikke at brukeren skriver «inf» for det siste trinnet."""
        trinn = parse_kapasitetstrinn("2:155,5:250,10:415")
        pris, nummer, _ = finn_kapasitetstrinn(trinn, 500.0)
        assert (pris, nummer) == (415, 3)


class TestCoordinatorUtenTabell:
    """Uten tabell er fastleddet ukjent, ikke null."""

    def test_flagget_settes(self, coord_module):
        coord = _lag_coordinator(coord_module)
        data = _run_update(coord_module, coord)
        assert data["fastledd_ukjent"] is True
        assert data["kapasitetsledd"] == 0
        assert data["kapasitetstrinn_nummer"] is None

    def test_ingen_trinnvarsel_uten_trinn(self, coord_module):
        """Uten kjente trinn finnes det ingen margin å varsle om."""
        coord = _lag_coordinator(coord_module)
        coord._daily_max_power = {"2026-06-01": coord_module.DailyMaxEntry(kw=9.9, hour=8)}
        data = _run_update(coord_module, coord)
        assert data["kapasitet_varsel"] is False
        assert data["margin_neste_trinn_kw"] == 0.0

    def test_energiledd_og_forbruk_regnes_som_før(self, coord_module):
        """Alt som ikke avhenger av fastleddet skal være uberørt."""
        coord = _lag_coordinator(coord_module)
        data = _run_update(coord_module, coord)
        assert data["energiledd"] > 0
        assert data["spot_price"] > 0
        assert data["offentlige_avgifter"] > 0

    def test_ulesbar_tabell_teller_som_ingen(self, coord_module):
        """Et håndredigert entry skal gi ukjent, ikke halve trinn."""
        coord = _lag_coordinator(coord_module, trinntabell="dette er ikke en tabell")
        data = _run_update(coord_module, coord)
        assert data["fastledd_ukjent"] is True


class TestCoordinatorMedTabell:
    """Med tabell regnes fastleddet som for et hvilket som helst nettselskap."""

    def test_trinnet_slaas_opp(self, coord_module):
        coord = _lag_coordinator(coord_module, trinntabell="2:155,5:250,10:415")
        coord._daily_max_power = {
            "2026-06-01": coord_module.DailyMaxEntry(kw=6.0, hour=8),
            "2026-06-02": coord_module.DailyMaxEntry(kw=6.0, hour=8),
            "2026-06-03": coord_module.DailyMaxEntry(kw=6.0, hour=8),
        }
        data = _run_update(coord_module, coord)
        assert data["fastledd_ukjent"] is False
        assert data["kapasitetsledd"] == 415
        assert data["kapasitetstrinn_nummer"] == 3
        assert data["kapasitetstrinn_intervall"] == "5-10 kW"

    def test_uten_forbruk_gir_laveste_trinn(self, coord_module):
        coord = _lag_coordinator(coord_module, trinntabell="2:155,5:250,10:415")
        data = _run_update(coord_module, coord)
        assert data["kapasitetsledd"] == 155

    def test_margin_til_neste_trinn(self, coord_module):
        coord = _lag_coordinator(coord_module, trinntabell="2:155,5:250,10:415")
        coord._daily_max_power = {
            "2026-06-01": coord_module.DailyMaxEntry(kw=4.0, hour=8),
            "2026-06-02": coord_module.DailyMaxEntry(kw=4.0, hour=8),
            "2026-06-03": coord_module.DailyMaxEntry(kw=4.0, hour=8),
        }
        data = _run_update(coord_module, coord)
        assert data["margin_neste_trinn_kw"] == 1.0
        assert data["neste_trinn_pris"] == 415


class TestKjenteNettselskapErUberoert:
    """Falske positiver varsler hos alle. Flagget gjelder bare Egendefinert."""

    @pytest.mark.parametrize("dso_id", ["bkk", "elvia", "alut", "fjellnett"])
    def test_flagget_er_av(self, coord_module, dso_id):
        ekstra = {"sikringstrinn": "inntil_3x125a"} if dso_id == "alut" else None
        entry = _make_entry(
            dso_id=dso_id,
            avgiftssone=resolve_avgiftssone(DSO_LIST[dso_id]),
            extra_data=ekstra,
        )
        coord = coord_module.NettleieCoordinator(_make_hass(), entry)
        data = _run_update(coord_module, coord)
        assert data["fastledd_ukjent"] is False

    def test_trinntabell_paa_kjent_dso_overstyrer_ikke_katalogen(self, coord_module):
        """Feltet finnes ikke i skjemaet for kjente nettselskap, men et entry

        kan bære det etter et bytte. Katalogen er verifisert, og et minne fra
        Egendefinert-tiden skal ikke slå den ut.
        """
        coord = _lag_coordinator(coord_module, trinntabell="2:1,5:2", dso_id="bkk")
        data = _run_update(coord_module, coord)
        assert data["kapasitetsledd"] == DSO_LIST["bkk"]["kapasitetstrinn"][0][1]
