"""Vakt for diagnostikk-skjemaet: versjon, personvern og JSON-renhet.

Dumpen limes inn i en offentlig GitHub-issue av en bruker som vil ha hjelp.
Tre ting må derfor holde: versjonen må være den som faktisk kjører, ingen
brukervalgte navn kan følge med, og `json.dumps` må gå uten hjelpehook.

Filen har også to drift-vakter. Den ene krever at hver nøkkel i
`coordinator.data` enten er med i allowlisten eller uttrykkelig utelatt, den
andre det samme for hver `CONF_*` i const.py. Uten dem ville en ny nøkkel
stille falt ut av dumpen, slik `nb.json` drev fra `strings.json` i fjorten
nøkler uten at noen merket det.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# diagnostikk.py importerer async_get_integration og HAs versjonskonstant på
# modulnivå, slik produksjonskode skal. conftest mocker `homeassistant` som en
# flat MagicMock uten undermoduler, og MagicMock nekter dunder-attributter, så
# begge må på plass før importen under.
sys.modules.setdefault("homeassistant.loader", MagicMock())
sys.modules["homeassistant.const"].__version__ = "2025.8.1"

from stromkalkulator import const as konst  # noqa: E402
from stromkalkulator.diagnostics import async_get_config_entry_diagnostics  # noqa: E402
from stromkalkulator.diagnostikk import (  # noqa: E402
    BEREGNING_ALLOWLIST,
    BEREGNING_UTELATT,
    DIAGNOSTICS_SCHEMA_VERSION,
    MAANEDSNAVN,
    NOKKEL_MARKOR,
    PROBLEM_ALLOWLIST,
    PROBLEM_UTELATT,
    ROLLE_TIL_CONF,
    TEKST_MARKOR,
    VALG_ALLOWLIST,
    Aliaser,
    bygg_diagnostikk,
    rens,
    rens_trygg,
)

from tests.conftest import _make_entry, _make_hass, _run_update  # noqa: E402

ROT = Path(__file__).parent.parent
MANIFEST = json.loads(
    (ROT / "custom_components" / "stromkalkulator" / "manifest.json").read_text(encoding="utf-8")
)

# Verdier vi planter og krever at aldri står i dumpen.
HEMMELIG_ENTITET = "sensor.fredrik_lindseth_nesttunveien_hovedmaaler"
HEMMELIG_TITTEL = "Strømkalkulator Nesttunveien 42"
HEMMELIG_ENTRY_ID = "01JABCDEF0123456789ENTRYID"
HEMMELIG_STI = "/config/custom_components/stromkalkulator"
HEMMELIG_MAALEPUNKT = "707057500012345678"
HEMMELIG_ADRESSE = "Nesttunveien 42, 5221 Nesttun"
# Entity-id der delen før punktumet ikke er et HA-domene, men et navn. Ikke
# nåbar via EntitySelector, men .storage kan redigeres for hånd.
HEMMELIG_PSEUDODOMENE = "fredrik_nesttunveien_42.effekt"

MANGLER = object()


@dataclass
class FakeDagsmaks:
    """Står for coordinatorens DailyMaxEntry: en dataklasse i data-dicten."""

    kw: float
    hour: int | None = None


class FakeCoordinator:
    """Minimal coordinator. Ikke MagicMock: dumpen skal testes på ekte verdier."""

    def __init__(self, data=None, **overstyr):
        self.data = {} if data is None else data
        self._dso_id = "bkk"
        self.dso = {"name": "BKK"}
        self.energiledd_dag_eks_mva = 0.28770
        self.energiledd_natt_eks_mva = 0.10500
        self.energiledd_dag = 0.46125
        self.energiledd_natt = 0.23275
        self.kapasitetstrinn = [(2, 155), (5, 250), (float("inf"), 6900)]
        self.fastledd_metode = "MND_MAX"
        self._weekly_max_power = {}
        self.energi_frossen_terskel_timer = 3.0
        self._last_energy_increase = datetime(2026, 7, 29, 10, 58)
        self._input_sist_gyldig = {"energi": datetime(2026, 7, 29, 10, 58)}
        self._vakthold_issues = {"utfall", "frossen"}
        for navn, verdi in overstyr.items():
            setattr(self, navn, verdi)


class FakeEntry:
    """Config entry uten MagicMock, så «ulastet» faktisk mangler runtime_data."""

    def __init__(self, *, data=None, options=None, coordinator=MANGLER, **overstyr):
        self.entry_id = HEMMELIG_ENTRY_ID
        self.title = HEMMELIG_TITTEL
        self.version = 4
        self.minor_version = 1
        self.source = "user"
        self.state = "loaded"
        self.data = {
            konst.CONF_DSO: "bkk",
            konst.CONF_AVGIFTSSONE: "standard",
            konst.CONF_HAR_NORGESPRIS: False,
            konst.CONF_BOLIGTYPE: "bolig",
            konst.CONF_POWER_SENSOR: HEMMELIG_ENTITET,
            konst.CONF_SPOT_PRICE_SENSOR: "sensor.nordpool_kwh_bergen",
        }
        if data is not None:
            self.data.update(data)
        self.options = options or {}
        if coordinator is not MANGLER:
            self.runtime_data = coordinator
        for navn, verdi in overstyr.items():
            setattr(self, navn, verdi)


def _dump(entry=None, hass=None):
    """Bygg en dump synkront, slik resten av testpakken kjører async-kode."""
    import asyncio

    return asyncio.run(
        bygg_diagnostikk(hass or MagicMock(), entry or FakeEntry(coordinator=FakeCoordinator()))
    )


class TestVersjon:
    """Versjonen i dumpen må være den som kjører, ikke den entryet har."""

    def test_version_er_fra_manifest_ikke_config_entry(self):
        dump = _dump(FakeEntry(version=4, coordinator=FakeCoordinator()))
        assert dump["integration"]["version"] == MANIFEST["version"]
        assert dump["integration"]["manifest_version_paa_disk"] == MANIFEST["version"]
        # Skjemaversjonen på entryet står for seg selv, og blandes ikke inn.
        assert dump["config_entry"]["version"] == 4
        assert dump["integration"]["version"] != dump["config_entry"]["version"]

    def test_loader_vinner_over_filen_paa_disk(self):
        """Loaderen har manifestet slik det ble lastet, altså koden som kjører."""
        integration = MagicMock()
        integration.version = "1.15.0"
        with patch(
            "stromkalkulator.diagnostikk.async_get_integration",
            AsyncMock(return_value=integration),
        ):
            dump = _dump()
        assert dump["integration"]["version"] == "1.15.0"
        assert dump["integration"]["version_kilde"] == "loader"
        assert dump["integration"]["manifest_version_paa_disk"] == MANIFEST["version"]
        # HACS har byttet filene uten omstart: da er dette selve svaret.
        assert dump["integration"]["versjon_avvik"] is True

    def test_ingen_avvik_naar_loader_og_disk_er_enige(self):
        integration = MagicMock()
        integration.version = MANIFEST["version"]
        with patch(
            "stromkalkulator.diagnostikk.async_get_integration",
            AsyncMock(return_value=integration),
        ):
            dump = _dump()
        assert dump["integration"]["versjon_avvik"] is False

    def test_faller_tilbake_til_manifestfilen_naar_loaderen_ryker(self):
        with patch(
            "stromkalkulator.diagnostikk.async_get_integration",
            AsyncMock(side_effect=RuntimeError("ingen integrasjon")),
        ):
            dump = _dump()
        assert dump["integration"]["version"] == MANIFEST["version"]
        assert dump["integration"]["version_kilde"] == "manifest_fil"

    def test_ha_versjon_og_domene_er_med(self):
        dump = _dump()
        assert dump["integration"]["ha_version"] == "2025.8.1"
        assert dump["integration"]["domain"] == konst.DOMAIN

    def test_skjemaversjon_er_med(self):
        assert _dump()["diagnostics_schema_version"] == DIAGNOSTICS_SCHEMA_VERSION


class TestPersonvern:
    """Plantede verdier som ville røpet hvem og hvor brukeren er."""

    def test_ingen_plantede_verdier_i_json(self):
        coordinator = FakeCoordinator(
            data={
                "input_problemer": [
                    {
                        "type": "utfall",
                        "input": "effekt",
                        "entity_id": HEMMELIG_ENTITET,
                        "siden": "2026-07-29T10:58:00",
                        "minutter": 90,
                        "timer": 1.5,
                    }
                ],
                "maalepunkt_id": HEMMELIG_MAALEPUNKT,
                "config_dir": HEMMELIG_STI,
            }
        )
        entry = FakeEntry(
            data={
                "installasjonssti": HEMMELIG_STI,
                "maalepunkt": HEMMELIG_MAALEPUNKT,
                konst.CONF_ENERGY_SENSOR: HEMMELIG_PSEUDODOMENE,
            },
            options={"kallenavn": "Huset til Fredrik"},
            coordinator=coordinator,
        )
        tekst = json.dumps(_dump(entry), ensure_ascii=False)
        for hemmelig in (
            HEMMELIG_ENTITET,
            HEMMELIG_TITTEL,
            HEMMELIG_ENTRY_ID,
            HEMMELIG_STI,
            HEMMELIG_MAALEPUNKT,
            "Huset til Fredrik",
            "nordpool_kwh_bergen",
            HEMMELIG_PSEUDODOMENE,
            "fredrik_nesttunveien_42",
        ):
            assert hemmelig not in tekst, f"{hemmelig} lekket ut i diagnostikken"

    def test_entry_og_tittel_er_aliasert(self):
        dump = _dump()
        assert dump["config_entry"]["alias"] == "entry_1"
        assert dump["config_entry"]["tittel_alias"] == "tittel_1"

    def test_rollene_beholder_relasjonen_sin(self):
        """Samme entitet i to roller skal ha samme alias, ulike ulikt."""
        entry = FakeEntry(
            data={
                konst.CONF_POWER_SENSOR: "sensor.maaler",
                konst.CONF_ENERGY_SENSOR: "sensor.maaler",
                konst.CONF_SPOT_PRICE_SENSOR: "sensor.spot",
            },
            coordinator=FakeCoordinator(),
        )
        roller = _dump(entry)["input_roller"]
        assert roller["effekt"]["entitet_alias"] == roller["energi"]["entitet_alias"]
        assert roller["effekt"]["entitet_alias"] != roller["spotpris"]["entitet_alias"]
        assert roller["effekt"]["entitet_alias"].startswith("sensor.")
        assert roller["eksport"] == {"konfigurert": False, "entitet_alias": None}

    def test_vaktholdsproblem_peker_paa_samme_alias_som_rollen(self):
        coordinator = FakeCoordinator(
            data={
                "input_problemer": [
                    {"type": "utfall", "input": "effekt", "entity_id": HEMMELIG_ENTITET, "minutter": 90}
                ]
            }
        )
        dump = _dump(FakeEntry(coordinator=coordinator))
        problem = dump["vakthold"]["input_problemer"][0]
        assert problem["entitet_alias"] == dump["input_roller"]["effekt"]["entitet_alias"]
        assert "entity_id" not in problem
        assert problem["minutter"] == 90

    def test_aliasene_er_tellere_uten_innhold(self):
        """Aliaset er rekkefølgen i dumpen, ikke noe utledet av navnet.

        To dumper gir derfor de samme aliasene, men et alias kan ikke knytte
        dem sammen: `sensor.alias_1` betyr «den første entiteten denne dumpen
        nevnte», og to vilt ulike entity-id-er får samme alias.
        """
        a = Aliaser()
        b = Aliaser()
        assert a.alias("sensor.x", "entitet") == "sensor.alias_1"
        assert b.alias("sensor.y", "entitet") == "sensor.alias_1"
        assert a.alias(None, "entitet") is None

    def test_ukjent_domene_i_entity_id_forsvinner(self):
        """Er delen før punktumet ikke et HA-domene, er det et navn."""
        aliaser = Aliaser()
        assert aliaser.alias(HEMMELIG_PSEUDODOMENE, "entitet") == "entitet_1"
        assert aliaser.alias("input_number.tak", "entitet") == "input_number.alias_2"

    def test_dumpen_sier_selv_hva_som_er_utelatt(self):
        assert any("aliasert" in linje for linje in _dump()["utelatt_med_vilje"])


class TestLekkasjeprober:
    """De fire veiene dommeren fikk plantet data ut gjennom (2j5drs9-c2).

    Ingen av dem går gjennom noe brukeren kan sette i UI-et, men dumpen limes
    inn i en offentlig issue, og da er angrepsflaten alt som havner i JSON-en.
    Alle fire planter i felt koden stoler på.
    """

    def test_ekstra_felt_paa_en_problemrad_folger_ikke_med(self):
        """Rad 1: problemradene var en denylist og slapp gjennom alt nytt."""
        coordinator = FakeCoordinator(
            data={
                "input_problemer": [
                    {
                        "type": "utfall",
                        "input": "effekt",
                        "entity_id": HEMMELIG_ENTITET,
                        "siden": "2026-07-29T10:58:00",
                        "minutter": 90,
                        "timer": 1.5,
                        # Feltene et framtidig vakthold kunne funnet på å legge på.
                        "attributes": {"meter_id": HEMMELIG_MAALEPUNKT},
                        "melding": f"{HEMMELIG_ENTITET} svarer ikke",
                        "friendly_name": HEMMELIG_ADRESSE,
                    }
                ]
            }
        )
        dump = _dump(FakeEntry(coordinator=coordinator))
        problem = dump["vakthold"]["input_problemer"][0]
        assert set(problem) == set(PROBLEM_ALLOWLIST) | {"entitet_alias"}
        tekst = json.dumps(dump, ensure_ascii=False)
        for plantet in (HEMMELIG_MAALEPUNKT, HEMMELIG_ENTITET, HEMMELIG_ADRESSE):
            assert plantet not in tekst

    def test_navn_i_domenedelen_av_en_entity_id_folger_ikke_med(self):
        """Rad 2: aliaset beholdt alt før første punktum."""
        entry = FakeEntry(
            data={konst.CONF_POWER_SENSOR: HEMMELIG_PSEUDODOMENE},
            coordinator=FakeCoordinator(),
        )
        dump = _dump(entry)
        assert dump["input_roller"]["effekt"]["entitet_alias"] == "entitet_1"
        assert "fredrik_nesttunveien_42" not in json.dumps(dump, ensure_ascii=False)

    def test_verdier_under_allowlistede_nokler_folger_ikke_med(self):
        """Rad 3: nøkkelen var allowlistet, verdien gikk rått ut."""
        entry = FakeEntry(
            data={
                konst.CONF_SIKRINGSTRINN: HEMMELIG_STI,
                konst.CONF_DSO: HEMMELIG_ADRESSE,
                konst.CONF_AVGIFTSSONE: HEMMELIG_MAALEPUNKT,
            },
            coordinator=FakeCoordinator(),
        )
        dump = _dump(entry)
        valg = dump["config_entry"]["valg"]
        assert valg[konst.CONF_SIKRINGSTRINN] == TEKST_MARKOR
        assert valg[konst.CONF_DSO] == TEKST_MARKOR
        assert valg[konst.CONF_AVGIFTSSONE] == TEKST_MARKOR
        tekst = json.dumps(dump, ensure_ascii=False)
        for plantet in (HEMMELIG_STI, HEMMELIG_ADRESSE, HEMMELIG_MAALEPUNKT):
            assert plantet not in tekst

    def test_konstantstrenger_fra_coordinatoren_folger_ikke_med(self):
        """Rad 4: dso.name og de avledede merkelappene var rene strenger."""
        coordinator = FakeCoordinator(
            data={
                "previous_month_name": HEMMELIG_ADRESSE,
                "kapasitetstrinn_intervall": HEMMELIG_STI,
                "current_month": HEMMELIG_MAALEPUNKT,
                "top_3_days": {HEMMELIG_ADRESSE: FakeDagsmaks(kw=7.2, hour=18)},
            },
            dso={"name": HEMMELIG_ADRESSE},
        )
        dump = _dump(FakeEntry(coordinator=coordinator))
        assert dump["dso"]["name"] == TEKST_MARKOR
        beregning = dump["beregning"]
        assert beregning["previous_month_name"] == TEKST_MARKOR
        assert beregning["kapasitetstrinn_intervall"] == TEKST_MARKOR
        assert beregning["current_month"] == TEKST_MARKOR
        # Også nøkler: en dict fra coordinatoren kan bære navnet i nøkkelen.
        assert list(beregning["top_3_days"]) == [NOKKEL_MARKOR]
        for plantet in (HEMMELIG_ADRESSE, HEMMELIG_STI, HEMMELIG_MAALEPUNKT):
            assert plantet not in json.dumps(dump, ensure_ascii=False)

    def test_kjente_verdier_slipper_fortsatt_gjennom(self):
        """Vakten er verdiløs hvis den også spiser det dumpen er til for."""
        for kjent in (
            "bkk",
            "BKK",
            "standard",
            "MND_MAX",
            "0-2 kW",
            ">100 kW",
            "juni 2026",
            "2026-06",
            "2026-06-15",
            "2026-06-15T12:00:00",
            "2026-06-15T12:00:00+02:00",
            "05-01 til 09-30",
            "1.16.0",
            "",
        ):
            assert rens_trygg(kjent) == kjent, f"{kjent!r} ble sensurert"


class TestJsonRenhet:
    """json.dumps må gå uten default-hook, også med dataklasser og inf."""

    def test_dumps_uten_default_hook(self):
        coordinator = FakeCoordinator(
            data={
                "top_3_days": {"2026-07-14": FakeDagsmaks(kw=7.2, hour=18)},
                "margin_neste_trinn_kw": float("inf"),
                "current_month": "2026-07",
            }
        )
        dump = _dump(FakeEntry(coordinator=coordinator))
        tekst = json.dumps(dump, allow_nan=False)
        assert json.loads(tekst)["beregning"]["top_3_days"]["2026-07-14"] == {"kw": 7.2, "hour": 18}
        assert dump["beregning"]["margin_neste_trinn_kw"] is None

    def test_rens_takler_ukjente_typer(self):
        assert rens(object()) == "<utelatt: object>"
        assert rens(datetime(2026, 7, 29, 10, 58)) == "2026-07-29T10:58:00"
        assert rens({"a", "b"}) == ["a", "b"]
        assert rens(float("nan")) is None
        assert rens(True) is True

    def test_dumps_gaar_ogsaa_paa_ekte_coordinatordata(self, coord_module):
        hass = _make_hass()
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator.data = _run_update(coord_module, coordinator)
        dump = _dump(FakeEntry(coordinator=coordinator))
        json.dumps(dump, allow_nan=False)


class TestUlastetEntry:
    """Den som ber om en dump har ofte et oppsett som nettopp feilet."""

    def test_ulastet_entry_gir_snapshot(self):
        dump = _dump(FakeEntry())
        assert dump["lastet"] is False
        assert dump["dso"] is None
        assert dump["vakthold"] is None
        assert dump["beregning"] is None
        # Det som ikke krever coordinatoren er fortsatt der.
        assert dump["integration"]["version"] == MANIFEST["version"]
        assert dump["config_entry"]["valg"][konst.CONF_DSO] == "bkk"
        assert dump["input_roller"]["effekt"]["konfigurert"] is True
        json.dumps(dump, allow_nan=False)

    def test_lastet_entry_er_merket_lastet(self):
        assert _dump()["lastet"] is True


class TestInnhold:
    """Det dumpen faktisk skal svare på."""

    def test_valg_og_options_overstyring(self):
        entry = FakeEntry(
            data={konst.CONF_SIKRINGSTRINN: 63},
            options={konst.CONF_KAPASITET_VARSEL_TERSKEL: 0.9, "kallenavn": "x"},
            coordinator=FakeCoordinator(),
        )
        dump = _dump(entry)
        assert dump["config_entry"]["valg"][konst.CONF_SIKRINGSTRINN] == 63
        assert dump["config_entry"]["options_overstyrer"] == [konst.CONF_KAPASITET_VARSEL_TERSKEL]

    def test_dso_seksjon(self):
        dso = _dump()["dso"]
        assert dso["id"] == "bkk"
        assert dso["name"] == "BKK"
        assert dso["energiledd_dag_inkl_mva"] == 0.46125
        assert dso["kapasitetstrinn_count"] == 3
        assert dso["fastledd_metode"] == "MND_MAX"

    def test_vakthold_seksjon(self):
        vakthold = _dump()["vakthold"]
        assert vakthold["grace_minutter"] == konst.INPUT_UTFALL_GRACE_MINUTTER
        assert vakthold["frossen_terskel_timer"] == 3.0
        assert vakthold["sist_energi_okning"] == "2026-07-29T10:58:00"
        assert vakthold["input_sist_gyldig"] == {"energi": "2026-07-29T10:58:00"}
        assert vakthold["aktive_issues"] == ["frossen", "utfall"]

    def test_beregning_tar_med_allowlisten(self):
        coordinator = FakeCoordinator(data={"total_price": 1.5, "spot_price": 1.2})
        beregning = _dump(FakeEntry(coordinator=coordinator))["beregning"]
        assert beregning["total_price"] == 1.5
        assert set(beregning) == set(BEREGNING_ALLOWLIST)

    def test_diagnostics_py_er_et_tynt_kall(self):
        import asyncio

        entry = FakeEntry(coordinator=FakeCoordinator())
        hass = MagicMock()
        fra_plattformen = asyncio.run(async_get_config_entry_diagnostics(hass, entry))
        assert fra_plattformen.keys() == _dump(entry, hass).keys()


class TestSkjemaVakt:
    """Et skjema uten vakt driver fra virkeligheten."""

    def test_toppnivaanokler_er_som_dokumentert(self):
        assert set(_dump()) == {
            "diagnostics_schema_version",
            "integration",
            "config_entry",
            "input_roller",
            "lastet",
            "dso",
            "vakthold",
            "beregning",
            "utelatt_med_vilje",
        }

    def test_hver_coordinator_nokkel_er_behandlet(self, coord_module):
        """Ny nøkkel i coordinator.data må enten tas med eller utelates bevisst."""
        hass = _make_hass()
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())
        data = _run_update(coord_module, coordinator)

        behandlet = set(BEREGNING_ALLOWLIST) | set(BEREGNING_UTELATT)
        mangler = set(data) - behandlet
        finnes_ikke = behandlet - set(data)
        assert not mangler, f"nye nøkler i coordinator.data: {sorted(mangler)}"
        assert not finnes_ikke, f"allowlisten peker på nøkler som ikke finnes: {sorted(finnes_ikke)}"

    def test_hver_conf_nokkel_er_behandlet(self):
        """Et nytt konfigvalg må enten vises eller utelates bevisst."""
        # Disse er entity-id-er og håndteres av ROLLE_TIL_CONF med aliasering.
        alle = {
            verdi
            for navn, verdi in vars(konst).items()
            if navn.startswith("CONF_") and isinstance(verdi, str)
        }
        assert alle, "fant ingen CONF-nøkler i const.py, da vakter denne testen ingenting"
        behandlet = set(VALG_ALLOWLIST) | set(ROLLE_TIL_CONF.values())
        assert not alle - behandlet, f"CONF-nøkler uten plass i diagnostikken: {sorted(alle - behandlet)}"

    def test_hvert_felt_paa_en_ekte_problemrad_er_behandlet(self, coord_module):
        """Rad-allowlisten må følge `_vakthold_problem`, ikke bare påstå det.

        Bygges raden av coordinatoren selv, feller denne testen både et nytt
        felt ingen tok stilling til og en allowlist som peker på felt som ikke
        finnes lenger.
        """
        rad = coord_module.NettleieCoordinator._vakthold_problem(
            konst.VAKTHOLD_UTFALL,
            konst.INPUT_ROLLE_EFFEKT,
            HEMMELIG_ENTITET,
            datetime(2026, 7, 29, 9, 28),
            datetime(2026, 7, 29, 10, 58),
        )
        behandlet = set(PROBLEM_ALLOWLIST) | set(PROBLEM_UTELATT)
        assert not set(rad) - behandlet, f"nye felt på problemraden: {sorted(set(rad) - behandlet)}"
        assert not behandlet - set(rad), (
            f"allowlisten peker på felt som ikke finnes: {sorted(behandlet - set(rad))}"
        )

    def test_maanedsnavnene_er_de_coordinatoren_lager(self, coord_module):
        """Vokter kopien av månedsnavnene som tekstvakten slipper gjennom."""
        coordinator = coord_module.NettleieCoordinator(_make_hass(), _make_entry())
        for nummer, navn in enumerate(MAANEDSNAVN, start=1):
            laget = coordinator._format_month_name(datetime(2026, nummer, 15))
            assert laget == f"{navn} 2026"

    def test_ekte_coordinatordata_utloser_ingen_markor(self, coord_module):
        """Tekstvakten skal ikke sensurere dumpens eget innhold.

        Legger noen en ny merkelapp i coordinator.data som vokabularet ikke
        kjenner, blir feltet en markør i hver eneste dump. Da skal det felles
        her, ikke oppdages av en bruker som lurer på hvor tallet ble av.
        """
        hass = _make_hass()
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())
        coordinator.data = _run_update(coord_module, coordinator)
        tekst = json.dumps(_dump(FakeEntry(coordinator=coordinator)), ensure_ascii=False)
        assert TEKST_MARKOR not in tekst, "tekstvakten sensurerte en ekte verdi"
        assert NOKKEL_MARKOR not in tekst, "tekstvakten sensurerte en ekte nøkkel"

    def test_allowlisten_har_ingen_duplikater(self):
        assert len(BEREGNING_ALLOWLIST) == len(set(BEREGNING_ALLOWLIST))
        assert len(VALG_ALLOWLIST) == len(set(VALG_ALLOWLIST))
        assert len(PROBLEM_ALLOWLIST) == len(set(PROBLEM_ALLOWLIST))
        assert not set(BEREGNING_ALLOWLIST) & set(BEREGNING_UTELATT)
        assert not set(PROBLEM_ALLOWLIST) & set(PROBLEM_UTELATT)


@pytest.mark.parametrize("rolle", sorted(ROLLE_TIL_CONF))
def test_alle_fem_roller_er_med(rolle):
    assert rolle in _dump()["input_roller"]
