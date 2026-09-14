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

import ast
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
    BASELINE_ALLOWLIST,
    BASELINE_UTELATT,
    BEREGNING_ALLOWLIST,
    BEREGNING_UTELATT,
    DIAGNOSTICS_SCHEMA_VERSION,
    ENHET_VOKABULAR,
    INPUT_RESULTAT_ALLOWLIST,
    INPUT_RESULTAT_UTELATT,
    INTERVALL_ALLOWLIST,
    KRONER_ALLOWLIST,
    MAANEDSNAVN,
    NOKKEL_MARKOR,
    PRIS_ALLOWLIST,
    PROBLEM_ALLOWLIST,
    PROBLEM_UTELATT,
    REPAIR_SORTER,
    ROLLE_TIL_CONF,
    SATSER_ALLOWLIST,
    TEKST_MARKOR,
    VALG_ALLOWLIST,
    VALG_UTELATT,
    Aliaser,
    bygg_diagnostikk,
    enhet_visning,
    rens,
    rens_trygg,
    tekstvakt,
)
from stromkalkulator.dso import DSO_LIST, FASTLEDD_METODER, hent_fastledd_metode  # noqa: E402
from stromkalkulator.inputadapter import ENHETSTABELL, Baseline  # noqa: E402

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
# Kildeidentiteten en AMS- eller Elhub-integrasjon setter som unique_id. Den er
# målepunkt-ID-en, altså like identifiserende som adressen.
HEMMELIG_UNIQUE_ID = f"elhub_{HEMMELIG_MAALEPUNKT}"

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


@dataclass
class FakeIssue:
    """Står for HAs IssueEntry. Bare feltene diagnostikken ser etter."""

    severity: str = "warning"
    active: bool = True
    is_fixable: bool = False
    created: datetime = datetime(2026, 7, 29, 10, 58)
    dismissed_version: str | None = None
    # Feltet som bærer entity-id-en i klartekst. Skal aldri ut.
    translation_placeholders: dict = field(default_factory=dict)


def _dump(entry=None, hass=None, issues=None):
    """Bygg en dump synkront, slik resten av testpakken kjører async-kode.

    `issues` legger et issue-register bak `ir.async_get`. Uten det svarer den
    mockede HA-modulen med en MagicMock, og dumpen melder at registeret ikke
    var tilgjengelig, som er det samme den gjør i et HA der oppslaget ryker.
    """
    import asyncio

    def bygg():
        return asyncio.run(
            bygg_diagnostikk(hass or MagicMock(), entry or FakeEntry(coordinator=FakeCoordinator()))
        )

    if issues is None:
        return bygg()
    registry = MagicMock()
    registry.issues = issues
    with patch("stromkalkulator.diagnostikk.ir.async_get", MagicMock(return_value=registry)):
        return bygg()


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
        assert roller["eksport"]["konfigurert"] is False
        assert roller["eksport"]["entitet_alias"] is None

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
        assert "options_overstyrer" not in dump["config_entry"]
        assert dump["config_entry"]["valg"][konst.CONF_KAPASITET_VARSEL_TERSKEL] is None

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

    def test_forrige_maaneds_bokforte_kroner_er_med(self):
        arkiv = {
            "previous_month_energiledd_dag_kr": 123.4567,
            "previous_month_energiledd_natt_kr": 89.0123,
            "previous_month_avgifter_kr": 45.6789,
            "previous_month_stromstotte_kr": 12.3456,
        }
        coordinator = FakeCoordinator(data=arkiv)
        beregning = _dump(FakeEntry(coordinator=coordinator))["beregning"]
        assert {nokkel: beregning[nokkel] for nokkel in arkiv} == arkiv

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
            "baseline",
            "dso",
            "vakthold",
            "beregning",
            "avregning",
            "repairs",
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
        behandlet = set(VALG_ALLOWLIST) | set(ROLLE_TIL_CONF.values()) | set(VALG_UTELATT)
        assert not alle - behandlet, f"CONF-nøkler uten plass i diagnostikken: {sorted(alle - behandlet)}"
        assert not set(VALG_ALLOWLIST) & set(VALG_UTELATT)

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


def _resultat(
    rolle_entity=HEMMELIG_ENTITET,
    type_="gyldig",
    grunn=None,
    raa_enhet="kW",
    enhet_normalisert="W",
    alder=42.0,
):
    """En rad slik coordinatorens `input_resultater` bygger den."""
    return {
        "entity_id": rolle_entity,
        "type": type_,
        "grunn": grunn,
        "raa_enhet": raa_enhet,
        "enhet_normalisert": enhet_normalisert,
        "alder_sekunder": alder,
    }


def _baseline(source_identity=HEMMELIG_UNIQUE_ID, entity_id=HEMMELIG_ENTITET, forkastet=False):
    """En baseline slik coordinatoren rapporterer den."""
    return {
        "schema_version": 2,
        "source_identity": source_identity,
        "entity_id": entity_id,
        "value_kwh": 12345.678,
        "observed_at": "2026-07-29T08:58:00+00:00",
        "forkastet": forkastet,
    }


class TestInputRoller:
    """Rollene skal svare på hva som kom inn, ikke bare hva som er valgt."""

    def test_rollen_viser_tilstand_enhet_og_alder(self):
        coordinator = FakeCoordinator(data={"input_resultater": {"effekt": _resultat()}})
        rolle = _dump(FakeEntry(coordinator=coordinator))["input_roller"]["effekt"]
        assert rolle["konfigurert"] is True
        assert rolle["avlest"] is True
        assert rolle["type"] == "gyldig"
        assert rolle["grunn"] is None
        assert rolle["raa_enhet"] == "kW"
        assert rolle["enhet_normalisert"] == "W"
        assert rolle["alder_sekunder"] == 42.0

    def test_rollen_uten_avlesning_sier_det(self):
        """En optional input som ikke er satt opp har ingen tilstand å vise."""
        rolle = _dump()["input_roller"]["eksport"]
        assert rolle["konfigurert"] is False
        assert rolle["avlest"] is False
        assert rolle["type"] is None
        assert rolle["raa_enhet"] is None

    def test_ugyldig_input_viser_grunnen(self):
        coordinator = FakeCoordinator(
            data={
                "input_resultater": {
                    "spotpris": _resultat(
                        rolle_entity="sensor.nordpool_kwh_bergen",
                        type_="ugyldig",
                        grunn="feil_valuta",
                        raa_enhet="EUR/MWh",
                        enhet_normalisert=None,
                        alder=None,
                    )
                }
            }
        )
        rolle = _dump(FakeEntry(coordinator=coordinator))["input_roller"]["spotpris"]
        assert rolle["type"] == "ugyldig"
        assert rolle["grunn"] == "feil_valuta"
        assert rolle["raa_enhet"] == "EUR/MWh"
        assert rolle["alder_sekunder"] is None

    def test_utilgjengelig_input_viser_grunnen_og_alderen(self):
        """Cache-alderen er svaret på «hvor lenge har den vært borte»."""
        coordinator = FakeCoordinator(
            data={
                "input_resultater": {
                    "energi": _resultat(
                        type_="utilgjengelig",
                        grunn="finnes_ikke",
                        raa_enhet=None,
                        enhet_normalisert=None,
                        alder=7200.0,
                    )
                }
            }
        )
        rolle = _dump(FakeEntry(coordinator=coordinator))["input_roller"]["energi"]
        assert rolle["type"] == "utilgjengelig"
        assert rolle["grunn"] == "finnes_ikke"
        assert rolle["alder_sekunder"] == 7200.0

    def test_sensor_uten_enhet_skilles_fra_ukjent_enhet(self):
        """`raa_enhet` None er punkt 4 i kontrakten, ikke et hull i dumpen."""
        coordinator = FakeCoordinator(data={"input_resultater": {"spotpris": _resultat(raa_enhet=None)}})
        rolle = _dump(FakeEntry(coordinator=coordinator))["input_roller"]["spotpris"]
        assert rolle["raa_enhet"] is None

    def test_resultatets_entitet_faar_samme_alias_som_rollen(self):
        coordinator = FakeCoordinator(data={"input_resultater": {"effekt": _resultat()}})
        dump = _dump(FakeEntry(coordinator=coordinator))
        assert dump["input_roller"]["effekt"]["entitet_alias"] == "sensor.alias_1"

    def test_rolle_som_bare_coordinatoren_kjenner_faar_alias(self):
        """Entiteten kan være strøket fra entry.data, men stå i siste resultat."""
        coordinator = FakeCoordinator(
            data={"input_resultater": {"eksport": _resultat(rolle_entity=HEMMELIG_ENTITET)}}
        )
        entry = FakeEntry(coordinator=coordinator)
        entry.data.pop(konst.CONF_POWER_SENSOR)
        dump = _dump(entry)
        eksport = dump["input_roller"]["eksport"]
        assert eksport["konfigurert"] is False
        assert eksport["entitet_alias"] is not None
        assert HEMMELIG_ENTITET not in json.dumps(dump, ensure_ascii=False)


class TestEnhetsvokabular:
    """Enheten er skrevet av en fremmed integrasjon, ikke av oss."""

    def test_kjente_enheter_gjengis_med_vaart_eget_ord(self):
        assert enhet_visning("kW") == "kW"
        assert enhet_visning("kwh") == "kWh"
        assert enhet_visning(" NOK/kWh ") == "NOK/kWh"
        assert enhet_visning("ore/kWh") == "øre/kWh"
        assert enhet_visning("EUR/MWh") == "EUR/MWh"

    def test_ukjent_enhet_blir_markor(self):
        assert enhet_visning(HEMMELIG_ADRESSE) == TEKST_MARKOR
        assert enhet_visning(HEMMELIG_STI) == TEKST_MARKOR
        assert enhet_visning(object()) == TEKST_MARKOR

    def test_ingen_enhet_er_ingen_enhet(self):
        assert enhet_visning(None) is None

    def test_hele_enhetstabellen_kan_gjengis(self):
        """Godtar adapteren en enhet, skal dumpen kunne si hvilken det var."""
        mangler = set(ENHETSTABELL) - set(ENHET_VOKABULAR)
        assert not mangler, f"enheter adapteren regner på, men dumpen ikke kan vise: {sorted(mangler)}"


class TestBaseline:
    """Baselinen forklarer et månedsforbruk ingen kjenner seg igjen i."""

    def test_baseline_vises_med_aliasert_kilde(self):
        coordinator = FakeCoordinator(data={"baseline": _baseline()})
        dump = _dump(FakeEntry(coordinator=coordinator))
        baseline = dump["baseline"]
        assert baseline["value_kwh"] == 12345.678
        assert baseline["observed_at"] == "2026-07-29T08:58:00+00:00"
        assert baseline["schema_version"] == 2
        assert baseline["forkastet"] is False
        assert baseline["kilde_alias"] == "kilde_1"
        assert "source_identity" not in baseline
        assert "entity_id" not in baseline

    def test_baselinens_entitet_deler_alias_med_energirollen(self):
        coordinator = FakeCoordinator(
            data={
                "baseline": _baseline(entity_id=HEMMELIG_ENTITET),
                "input_resultater": {"energi": _resultat()},
            }
        )
        dump = _dump(FakeEntry(coordinator=coordinator))
        assert dump["baseline"]["entitet_alias"] == dump["input_roller"]["energi"]["entitet_alias"]

    def test_forkastet_baseline_uten_verdi(self):
        """Et uventet nullforbruk etter omstart skal kunne forklares her."""
        coordinator = FakeCoordinator(data={"baseline": {"forkastet": True}})
        baseline = _dump(FakeEntry(coordinator=coordinator))["baseline"]
        assert baseline["forkastet"] is True
        assert baseline["value_kwh"] is None
        assert baseline["kilde_alias"] is None

    def test_ingen_baseline_gir_none(self):
        assert _dump()["baseline"] is None

    def test_maalepunkt_id_i_kildeidentiteten_lekker_ikke(self):
        coordinator = FakeCoordinator(data={"baseline": _baseline()})
        tekst = json.dumps(_dump(FakeEntry(coordinator=coordinator)), ensure_ascii=False)
        assert HEMMELIG_MAALEPUNKT not in tekst
        assert HEMMELIG_UNIQUE_ID not in tekst


class TestRepairs:
    """Et varsel brukeren har klikket bort forklarer ofte hele saken."""

    def test_issues_for_dette_anlegget(self):
        issues = {
            (konst.DOMAIN, f"input_utfall_{HEMMELIG_ENTRY_ID}"): FakeIssue(
                translation_placeholders={"entity_id": HEMMELIG_ENTITET}
            ),
        }
        repairs = _dump(issues=issues)["repairs"]
        assert repairs["tilgjengelig"] is True
        assert repairs["issues"] == [
            {
                "sort": "input_utfall",
                "gjelder": "dette_anlegget",
                "aktiv": True,
                "fiksbar": False,
                "alvorlighet": "warning",
                "opprettet": "2026-07-29T10:58:00",
                "avvist_i_versjon": None,
            }
        ]

    def test_domenevide_og_fremmede_issues(self):
        issues = {
            (konst.DOMAIN, "satser_utdatert"): FakeIssue(),
            (konst.DOMAIN, "input_utfall_01JXXXXXXXXXXXXXXXXXXXXXXX"): FakeIssue(),
            ("mobile_app", "noe_annet"): FakeIssue(),
        }
        repairs = _dump(issues=issues)["repairs"]
        gjelder = {rad["sort"]: rad["gjelder"] for rad in repairs["issues"]}
        assert gjelder == {
            "satser_utdatert": "hele_integrasjonen",
            "input_utfall": "annet_anlegg",
        }

    def test_avvist_issue_er_med_og_merket(self):
        issues = {
            (konst.DOMAIN, "norgespris_utlopt"): FakeIssue(
                active=False, dismissed_version="2025.8.1", severity="error", is_fixable=True
            )
        }
        rad = _dump(issues=issues)["repairs"]["issues"][0]
        assert rad["aktiv"] is False
        assert rad["avvist_i_versjon"] == "2025.8.1"
        assert rad["alvorlighet"] == "error"
        assert rad["fiksbar"] is True

    def test_ukjent_sort_blir_markor(self):
        """En issue-id fra en gammel versjon er like gjerne et navn."""
        issues = {(konst.DOMAIN, f"{HEMMELIG_ADRESSE}_{HEMMELIG_ENTRY_ID}"): FakeIssue()}
        dump = _dump(issues=issues)
        assert dump["repairs"]["issues"][0]["sort"] == TEKST_MARKOR
        assert HEMMELIG_ADRESSE not in json.dumps(dump, ensure_ascii=False)

    def test_registeret_kan_mangle(self):
        """En dump skal ikke ryke fordi issue-registeret ikke svarer."""
        repairs = _dump()["repairs"]
        assert repairs == {"tilgjengelig": False, "issues": []}

    def test_repairs_ogsaa_naar_entryet_ikke_er_lastet(self):
        issues = {(konst.DOMAIN, "satser_utdatert"): FakeIssue()}
        dump = _dump(FakeEntry(), issues=issues)
        assert dump["lastet"] is False
        assert dump["repairs"]["issues"][0]["sort"] == "satser_utdatert"

    def test_alle_issue_sorter_koden_lager_er_kjent(self, coord_module):
        """Vokter kopien av vaktholdets issue-prefikser mot coordinatoren."""
        fra_coordinator = set(coord_module._VAKTHOLD_ISSUE_PREFIX.values())
        assert fra_coordinator <= REPAIR_SORTER, (
            f"vakthold-issues dumpen ikke kjenner: {sorted(fra_coordinator - REPAIR_SORTER)}"
        )
        assert konst.TARIFF_ISSUE_PREFIX.rstrip("_") in REPAIR_SORTER
        assert konst.EGENDEFINERT_ISSUE_PREFIX.rstrip("_") in REPAIR_SORTER


class TestTarifforigin:
    """Satsene som ble brukt, ikke de som ligger lagret."""

    def test_tarifforigin_slipper_gjennom_uten_markor(self):
        origin = {
            "modus": konst.TARIFFMODUS_CATALOG,
            "dso": "bkk",
            "sesongperioder_styrer": True,
            "manual_ignorert": False,
            "energiledd_dag_eks_mva": 0.2877,
            "energiledd_natt_eks_mva": 0.105,
            "energiledd_dag_inkl_mva": 0.46125,
            "energiledd_natt_inkl_mva": 0.23275,
        }
        coordinator = FakeCoordinator(data={"tarifforigin": origin})
        assert _dump(FakeEntry(coordinator=coordinator))["beregning"]["tarifforigin"] == origin

    @pytest.mark.parametrize("modus", sorted(konst.TARIFFMODUS_ALLE))
    def test_hver_tariffmodus_vises(self, modus):
        coordinator = FakeCoordinator(data={"tarifforigin": {"modus": modus, "dso": "bkk"}})
        beregning = _dump(FakeEntry(coordinator=coordinator))["beregning"]
        assert beregning["tarifforigin"]["modus"] == modus

    def test_plantet_modus_blir_markor(self):
        coordinator = FakeCoordinator(data={"tarifforigin": {"modus": HEMMELIG_ADRESSE}})
        dump = _dump(FakeEntry(coordinator=coordinator))
        assert dump["beregning"]["tarifforigin"]["modus"] == TEKST_MARKOR
        assert HEMMELIG_ADRESSE not in json.dumps(dump, ensure_ascii=False)


class TestLekkasjeproberD2:
    """Egne forsøk på å lekke gjennom de nye feltene.

    Alle tre planter i felt koden stoler på: en adresse i entitetsnavnet en
    rolle rapporterer, en målepunkt-ID i sensorens attributter og en sti i en
    option. Ingen av dem er nåbare i UI-et, men dumpen limes inn offentlig.
    """

    def test_adresse_i_entitetsnavnet_paa_et_inputresultat(self):
        coordinator = FakeCoordinator(
            data={
                "input_resultater": {
                    "effekt": _resultat(rolle_entity=f"sensor.{HEMMELIG_ADRESSE}"),
                    "energi": _resultat(rolle_entity=HEMMELIG_PSEUDODOMENE),
                }
            }
        )
        dump = _dump(FakeEntry(coordinator=coordinator))
        tekst = json.dumps(dump, ensure_ascii=False)
        for plantet in (HEMMELIG_ADRESSE, HEMMELIG_PSEUDODOMENE, "fredrik_nesttunveien_42"):
            assert plantet not in tekst, f"{plantet} lekket ut gjennom input_resultater"

    def test_maalepunkt_id_i_enhet_og_attributter(self):
        """Enheten og kildeidentiteten kommer begge fra en fremmed integrasjon."""
        coordinator = FakeCoordinator(
            data={
                "input_resultater": {
                    "energi": _resultat(raa_enhet=f"kWh ({HEMMELIG_MAALEPUNKT})"),
                },
                "baseline": _baseline(source_identity=HEMMELIG_MAALEPUNKT),
                "input_problemer": [
                    {
                        "type": "enhet",
                        "input": "energi",
                        "entity_id": HEMMELIG_ENTITET,
                        "raa_enhet": HEMMELIG_MAALEPUNKT,
                        "grunn": "ukjent_enhet",
                        "finnes": True,
                    }
                ],
            }
        )
        dump = _dump(FakeEntry(coordinator=coordinator))
        assert dump["input_roller"]["energi"]["raa_enhet"] == TEKST_MARKOR
        assert dump["vakthold"]["input_problemer"][0]["raa_enhet"] == TEKST_MARKOR
        assert HEMMELIG_MAALEPUNKT not in json.dumps(dump, ensure_ascii=False)

    def test_sti_i_en_option_og_i_et_repair_varsel(self):
        issues = {
            (konst.DOMAIN, f"input_enhet_{HEMMELIG_ENTRY_ID}"): FakeIssue(
                translation_placeholders={
                    "entity_id": HEMMELIG_ENTITET,
                    "sti": HEMMELIG_STI,
                },
                severity=HEMMELIG_ADRESSE,
            )
        }
        entry = FakeEntry(
            options={konst.CONF_SIKRINGSTRINN: HEMMELIG_STI, "loggsti": HEMMELIG_STI},
            data={konst.CONF_ENERGI_FROSSEN_TIMER: HEMMELIG_STI},
            coordinator=FakeCoordinator(),
        )
        dump = _dump(entry, issues=issues)
        assert dump["repairs"]["issues"][0]["alvorlighet"] == TEKST_MARKOR
        tekst = json.dumps(dump, ensure_ascii=False)
        for plantet in (HEMMELIG_STI, HEMMELIG_ADRESSE, HEMMELIG_ENTITET):
            assert plantet not in tekst, f"{plantet} lekket ut"


class TestFlereOppsett:
    """Samme dump må virke på tvers av avtale-, mva- og tariffvalg."""

    @pytest.mark.parametrize("har_norgespris", [True, False])
    @pytest.mark.parametrize("spotpris_inkl_mva", [True, False])
    @pytest.mark.parametrize("avgiftssone", ["standard", "tiltakssone"])
    def test_ekte_coordinator_gir_ren_dump(
        self, coord_module, har_norgespris, spotpris_inkl_mva, avgiftssone
    ):
        hass = _make_hass()
        entry = _make_entry(
            har_norgespris=har_norgespris,
            spotpris_inkl_mva=spotpris_inkl_mva,
            avgiftssone=avgiftssone,
            energy_sensor="sensor.energy",
            export_power_sensor="sensor.export_power",
            electricity_company_price_sensor="sensor.elco_price",
        )
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator.data = _run_update(coord_module, coordinator)
        dump = _dump(FakeEntry(coordinator=coordinator))
        tekst = json.dumps(dump, allow_nan=False, ensure_ascii=False)
        assert TEKST_MARKOR not in tekst, "tekstvakten sensurerte en ekte verdi"
        assert NOKKEL_MARKOR not in tekst, "tekstvakten sensurerte en ekte nøkkel"
        assert dump["beregning"]["har_norgespris"] == har_norgespris
        assert dump["input_roller"]["effekt"]["type"] == "gyldig"

    def test_dumpen_er_lik_etter_reload(self, coord_module):
        """To dumper av samme oppsett skal kunne sammenlignes felt for felt."""
        hass = _make_hass()
        entry = _make_entry(energy_sensor="sensor.energy")
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator.data = _run_update(coord_module, coordinator)
        fake = FakeEntry(coordinator=coordinator)
        assert json.dumps(_dump(fake), allow_nan=False) == json.dumps(_dump(fake), allow_nan=False)

    def test_en_syntetisk_feilrapport_forklarer_grunnlaget(self, coord_module):
        """GO-kriteriet: dumpen svarer på hvorfor tallene stoppet.

        Uten rå identifikatorer, og uten at leseren må be om noe mer.
        """
        hass = _make_hass()
        entry = _make_entry(energy_sensor="sensor.energy")
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator.data = _run_update(coord_module, coordinator)
        coordinator.data["input_resultater"]["energi"] = _resultat(
            type_="utilgjengelig", grunn="finnes_ikke", raa_enhet=None, alder=9000.0
        )
        coordinator.data["baseline"] = _baseline()
        issues = {(konst.DOMAIN, f"input_utfall_{HEMMELIG_ENTRY_ID}"): FakeIssue()}
        dump = _dump(FakeEntry(coordinator=coordinator), issues=issues)

        assert dump["input_roller"]["energi"]["grunn"] == "finnes_ikke"
        assert dump["input_roller"]["energi"]["alder_sekunder"] == 9000.0
        assert dump["baseline"]["value_kwh"] == 12345.678
        assert dump["repairs"]["issues"][0]["sort"] == "input_utfall"
        assert dump["beregning"]["tarifforigin"]["modus"] in konst.TARIFFMODUS_ALLE
        assert dump["integration"]["version"] == MANIFEST["version"]

        tekst = json.dumps(dump, allow_nan=False, ensure_ascii=False)
        for raa in (HEMMELIG_ENTITET, HEMMELIG_ENTRY_ID, HEMMELIG_MAALEPUNKT, "sensor.energy"):
            assert raa not in tekst, f"{raa} sto rått i feilrapporten"


class TestSkjemaVaktD2:
    """Driftvakter for feltene D2 la til."""

    def test_hvert_felt_i_input_resultater_er_behandlet(self, coord_module):
        hass = _make_hass()
        entry = _make_entry(energy_sensor="sensor.energy")
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        data = _run_update(coord_module, coordinator)
        rad = data["input_resultater"]["effekt"]
        behandlet = set(INPUT_RESULTAT_ALLOWLIST) | set(INPUT_RESULTAT_UTELATT)
        assert not set(rad) - behandlet, f"nye felt i input_resultater: {sorted(set(rad) - behandlet)}"
        assert not behandlet - set(rad), (
            f"allowlisten peker på felt som ikke finnes: {sorted(behandlet - set(rad))}"
        )

    def test_hvert_felt_i_baselinen_er_behandlet(self):
        lagret = Baseline(
            source_identity=HEMMELIG_UNIQUE_ID,
            entity_id=HEMMELIG_ENTITET,
            value_kwh=1.0,
            observed_at=datetime(2026, 7, 29, 10, 58),
        ).som_lagret()
        felt = set(lagret) | {"forkastet"}
        behandlet = set(BASELINE_ALLOWLIST) | set(BASELINE_UTELATT)
        assert felt == behandlet, f"baseline-felt uten beslutning: {sorted(felt ^ behandlet)}"

    def test_allowlistene_er_uten_duplikater(self):
        assert not set(BASELINE_ALLOWLIST) & set(BASELINE_UTELATT)
        assert not set(INPUT_RESULTAT_ALLOWLIST) & set(INPUT_RESULTAT_UTELATT)

    def test_rollene_har_de_samme_feltene(self):
        roller = _dump()["input_roller"]
        felt = {frozenset(rad) for rad in roller.values()}
        assert len(felt) == 1, "rollene har ulike felt, og da kan de ikke sammenlignes"


# ---------------------------------------------------------------------------
# Fingeravtrykket av feltsettet
# ---------------------------------------------------------------------------

# Dicter der nøklene er data og ikke skjema: en dato, et trinn, en rolle vi
# tilfeldigvis har sist gyldig tid for. Feltet selv teller med, innholdet
# gjør det ikke, så en annen fixture eller en annen målemåned ikke endrer
# fingeravtrykket.
VERDIDICTER: frozenset[str] = frozenset(
    {
        "vakthold.input_sist_gyldig",
        "beregning.top_3_days",
        "beregning.previous_month_top_3",
        "beregning.tarifforigin",
        "beregning.energiledd_perioder[]",
    }
)


def _feltsett(dump):
    """Hvert navngitte felt i dumpen, som en sti: «vakthold.input_problemer[].type».

    Bare navn. Verdier, rekkefølge, kommentarer og vokabularer er ikke med, så
    en ny DSO, en ny repair-sort eller en omskrevet docstring rører ikke
    fingeravtrykket. Et nytt eller fjernet felt gjør det.
    """
    felt: set[str] = set()

    def gaa(verdi, sti):
        if isinstance(verdi, dict):
            if sti in VERDIDICTER:
                return
            for nokkel, under in verdi.items():
                barn = f"{sti}.{nokkel}" if sti else str(nokkel)
                felt.add(barn)
                gaa(under, barn)
        elif isinstance(verdi, list):
            for under in verdi:
                gaa(under, f"{sti}[]")

    gaa(dump, "")
    return felt


def _fingeravtrykk(felt):
    return hashlib.sha256("\n".join(sorted(felt)).encode()).hexdigest()[:16]


def _fullt_avregningsgrunnlag():
    intervall = dict.fromkeys(INTERVALL_ALLOWLIST)
    intervall.update(
        pris=dict.fromkeys(PRIS_ALLOWLIST),
        satser=dict.fromkeys(SATSER_ALLOWLIST),
        kroner=dict.fromkeys(KRONER_ALLOWLIST),
    )
    return {"oppdatert": None, "siste_energistand_kwh": None, "intervaller": [intervall]}


def _full_dump():
    """En dump der hver seksjon er fylt, så alle feltene faktisk er med.

    En tom baseline eller et tomt issue-register skjuler halve skjemaet, og et
    fingeravtrykk av et halvt skjema vokter bare den halvdelen.
    """
    problemrad = dict.fromkeys(PROBLEM_ALLOWLIST)
    problemrad["entity_id"] = HEMMELIG_ENTITET
    coordinator = FakeCoordinator(
        data={
            "input_resultater": {rolle: _resultat() for rolle in ROLLE_TIL_CONF},
            "baseline": _baseline(),
            "input_problemer": [problemrad],
            "avregning_grunnlag": _fullt_avregningsgrunnlag(),
        }
    )
    issues = {(konst.DOMAIN, "satser_utdatert"): FakeIssue()}
    return _dump(FakeEntry(coordinator=coordinator), issues=issues)


# Feltsettet slik det så ut da hver skjemaversjon ble sluppet. Utvides eller
# krympes feltsettet, skal versjonen bumpes og en ny linje legges til her;
# linjene over er historikk og skal ikke røres.
SKJEMA_FINGERAVTRYKK: dict[int, str] = {
    3: "57667d2cbd0c23aa",
    # 4: kostnadskjernen (L3b) la splitten av energileddet og strømstøtten i
    # kroner under "beregning".
    4: "5e19c921aa05721a",
    # 5: avregningsgrunnlag og normaliserte inputverdier; options_overstyrer fjernet.
    5: "319de8578855d72e",
    # 6: forrige måneds bokførte energiledd, avgifter og strømstøtte.
    6: "72f4afa9f1bff34b",
}


class TestAvregningsgrunnlag:
    @pytest.mark.parametrize("mangler_pris", [False, True])
    @pytest.mark.parametrize("har_norgespris", [False, True])
    def test_json_fra_replay_gir_samme_intervallsum_i_l2_fasiten(
        self, coord_module, mangler_pris, har_norgespris
    ):
        from tests.replay.fasit import OSLO, Fasit, Satser
        from tests.replay.harness import Replay, logg_fra_timesenergi, pollplan

        start = datetime(2026, 6, 15, 10, tzinfo=OSLO)
        timer = [(start + timedelta(hours=i), 2.0 + i) for i in range(5)]
        priser = {t: [0.4, 0.8, 1.2, 1.6] for t, _ in timer}
        replay = Replay(
            coord_module,
            logg_fra_timesenergi(timer, priser, maler_sekunder=60),
            entry_kwargs={"har_norgespris": har_norgespris},
        )
        replay.start(start)
        if mangler_pris:
            replay.pris_hull(*[start + timedelta(hours=3, minutes=15 * i) for i in range(4)])
        try:
            replay.kjor(pollplan(start, start + timedelta(hours=4, minutes=10)))
            replay.coord.data = replay.data
            entry = FakeEntry(coordinator=replay.coord)
            dump = json.loads(json.dumps(_dump(entry), allow_nan=False))
            avregning = dump["avregning"]
            assert TEKST_MARKOR not in json.dumps(avregning)
            assert len(avregning["intervaller"]) == 2
            assert len(replay.coord._bok.intervaller()) > 2
            assert avregning["intervaller"][0]["apen"] is False
            assert avregning["intervaller"][1]["apen"] is True
            assert avregning["intervaller"][0]["kvalitet"] == ("uten_pris" if mangler_pris else "komplett")
            assert avregning["intervaller"][1]["kvalitet"] == "delvis_pris"
            assert avregning["kwh_uten_pris"] > 0 if mangler_pris else avregning["kwh_uten_pris"] == 0
            assert avregning["kwh_delvis_pris"] > 0
            assert avregning["siste_energistand_kwh"] == dump["input_roller"]["energi"]["verdi"]
            for rad in avregning["intervaller"]:
                sats = rad["satser"]
                nett = sats["energiledd_inkl_mva"] - sats["avgifter_inkl_mva"]
                f = Fasit(
                    Satser(
                        energiledd_dag_inkl_mva=nett,
                        energiledd_natt_inkl_mva=nett,
                        forbruksavgift_inkl_mva=sats["avgifter_inkl_mva"],
                        enova_inkl_mva=0,
                        mva_faktor=1 + sats["mva_sats"],
                        har_norgespris=sats["har_norgespris"],
                        norgespris_inkl_mva=sats["norgespris_inkl_mva"],
                        norgespris_maks_kwh=max(0, sats["norgespris_max_kwh"] - rad["kwh_for"]),
                        stromstotte_terskel_inkl_mva=sats["stromstotte_terskel"],
                        stromstotte_maks_kwh=max(0, sats["stromstotte_max_kwh"] - rad["kwh_for"]),
                    )
                )
                tid = datetime.fromisoformat(rad["start_utc"])
                f.bokfor_intervall(tid, rad["kwh"])
                pris = rad["pris"]
                if pris:
                    for i in range(pris["pris_prover"]):
                        f.prisprove(tid + timedelta(minutes=15 * i, seconds=61), pris["nok_per_kwh_eks_mva"])
                fasit = f.avregning()
                assert fasit.kwh_total == pytest.approx(rad["kroner"]["kwh"])
                assert fasit.kwh_uten_pris == pytest.approx(rad["kroner"]["kwh_uten_pris"])
                assert fasit.energiledd_dag_kr == pytest.approx(rad["kroner"]["energiledd_dag_kr"])
                assert fasit.energiledd_natt_kr == pytest.approx(rad["kroner"]["energiledd_natt_kr"])
                assert fasit.forbruksavgift_kr == pytest.approx(rad["kroner"]["avgifter_kr"])
                kompensasjon = (
                    rad["kroner"]["norgespris_kompensasjon_kr"]
                    if sats["har_norgespris"]
                    else -rad["kroner"]["stromstotte_kr"]
                )
                assert fasit.stotte_kr == pytest.approx(kompensasjon)

            # En ny poll får ikke endre grunnlaget for data som allerede er publisert.
            replay.poll(start + timedelta(hours=4, minutes=15))
            assert _dump(entry)["avregning"] == avregning
        finally:
            replay.lukk()

    def test_nye_nostede_felt_og_kildeidentitet_lekker_ikke(self):
        grunnlag = _fullt_avregningsgrunnlag()
        grunnlag["historikk"] = HEMMELIG_TITTEL
        rad = grunnlag["intervaller"][0]
        rad["entity_id"] = HEMMELIG_ENTITET
        rad["regelkilde"] = HEMMELIG_ENTITET
        rad["kvalitet"] = HEMMELIG_TITTEL
        for navn in ("satser", "pris", "kroner"):
            rad[navn]["adresse"] = HEMMELIG_TITTEL
        rad["pris"]["kilde"] = HEMMELIG_UNIQUE_ID
        coord = FakeCoordinator(
            data={
                "avregning_grunnlag": grunnlag,
                "avregning_kilde": HEMMELIG_UNIQUE_ID,
                "baseline": _baseline(),
            }
        )
        dump = _dump(FakeEntry(coordinator=coord))
        assert dump["avregning"]["kilde_alias"] == dump["baseline"]["kilde_alias"]
        tekst = json.dumps(dump)
        for hemmelig in (HEMMELIG_TITTEL, HEMMELIG_ENTITET, HEMMELIG_UNIQUE_ID):
            assert hemmelig not in tekst
        assert "historikk" not in dump["avregning"]

    def test_ulastet_entry_har_ikke_avregningsgrunnlag(self):
        assert _dump(FakeEntry())["avregning"] is None

    def test_ugyldig_input_har_ingen_tallverdi(self, coord_module):
        from stromkalkulator.inputadapter import Ugyldig

        coordinator = coord_module.NettleieCoordinator(_make_hass(), _make_entry())
        coordinator._input_resultater["effekt"] = Ugyldig("ukjent_enhet", "sensor.power", "adresse")
        rad = coordinator._input_resultater_rapport(datetime(2026, 6, 15))["effekt"]
        assert rad["verdi"] is None
        assert rad["observed_at"] is None
        assert rad["avlest_kl"] is None


class TestSkjemaFingeravtrykk:
    """Vakten som feller en skjemautvidelse uten bump.

    K3 la et felt i `VALG_ALLOWLIST` og et i `BEREGNING_ALLOWLIST` uten at noe
    ble rødt, fordi versjonstesten bare pinnet tallet mot seg selv. Den pinner
    nå tallet mot feltene.
    """

    def test_feltsettet_er_pinnet_mot_skjemaversjonen(self):
        felt = _feltsett(_full_dump())
        fasit = SKJEMA_FINGERAVTRYKK.get(DIAGNOSTICS_SCHEMA_VERSION)
        assert fasit is not None, (
            f"skjemaversjon {DIAGNOSTICS_SCHEMA_VERSION} har ingen linje i SKJEMA_FINGERAVTRYKK"
        )
        assert _fingeravtrykk(felt) == fasit, (
            "feltsettet i dumpen er ikke det som er pinnet for skjemaversjon "
            f"{DIAGNOSTICS_SCHEMA_VERSION}. Er felt lagt til eller fjernet, bump "
            "DIAGNOSTICS_SCHEMA_VERSION og legg inn fingeravtrykket "
            f"{_fingeravtrykk(felt)} på en ny linje i SKJEMA_FINGERAVTRYKK.\n"
            f"feltene nå ({len(felt)}):\n" + "\n".join(sorted(felt))
        )

    def test_historikken_stopper_paa_naavaerende_versjon(self):
        assert max(SKJEMA_FINGERAVTRYKK) == DIAGNOSTICS_SCHEMA_VERSION
        assert len(set(SKJEMA_FINGERAVTRYKK.values())) == len(SKJEMA_FINGERAVTRYKK), (
            "to skjemaversjoner med samme feltsett: da var bumpen unødvendig"
        )

    def test_fingeravtrykket_taaler_en_ny_dso_og_en_ny_repair_sort(self):
        """Vokabularer er ikke felt, og skal ikke kreve en versjonsbump."""
        for_ = _fingeravtrykk(_feltsett(_full_dump()))
        issues = {
            (konst.DOMAIN, "satser_utdatert"): FakeIssue(),
            (konst.DOMAIN, f"dso_delt_{HEMMELIG_ENTRY_ID}"): FakeIssue(),
        }
        problemrad = dict.fromkeys(PROBLEM_ALLOWLIST)
        problemrad["entity_id"] = HEMMELIG_ENTITET
        coordinator = FakeCoordinator(
            data={
                "input_resultater": {rolle: _resultat() for rolle in ROLLE_TIL_CONF},
                "baseline": _baseline(),
                "input_problemer": [problemrad],
                "avregning_grunnlag": _fullt_avregningsgrunnlag(),
            },
            dso={"name": "BKK"},
        )
        etter = _fingeravtrykk(_feltsett(_dump(FakeEntry(coordinator=coordinator), issues=issues)))
        assert for_ == etter

    def test_et_nytt_felt_i_en_seksjon_endrer_fingeravtrykket(self):
        """Selve mutasjonen dommeren kjørte: et felt til i dso-seksjonen."""
        felt = _feltsett(_full_dump())
        assert _fingeravtrykk(felt | {"dso.et_felt_ingen_har_lagt_til"}) != _fingeravtrykk(felt)


# ---------------------------------------------------------------------------
# Repair-sortene, lest ut av koden som lager dem
# ---------------------------------------------------------------------------

KOMPONENT = ROT / "custom_components" / "stromkalkulator"

# De to indirekte veiene til en issue-id: vaktholdets løkke over
# `_VAKTHOLD_ISSUE_PREFIX` (dekket av test_alle_issue_sorter_koden_lager_er_kjent)
# og `_reis_med_aarsdemping`, som får id-en inn som parameter fra kallere vi
# leser konstanten til. Dukker det opp en tredje, skal denne testen si fra.
KJENTE_INDIREKTE = {"prefix", "issue_id"}


def _modulkonstanter():
    """Navn -> verdi for hver strengkonstant på modulnivå i komponenten."""
    konstanter: dict[str, str] = {}
    for fil in sorted(KOMPONENT.glob("*.py")):
        for node in ast.parse(fil.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                mal, verdi = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                mal, verdi = node.target, node.value
            else:
                continue
            if isinstance(mal, ast.Name) and isinstance(verdi, ast.Constant) and isinstance(verdi.value, str):
                konstanter[mal.id] = verdi.value
    return konstanter


def _les_issue_id(uttrykk, konstanter):
    """Hva et uttrykk blir til: («full» | «prefiks» | «ukjent», tekst)."""
    if isinstance(uttrykk, ast.Constant) and isinstance(uttrykk.value, str):
        return "full", uttrykk.value
    if isinstance(uttrykk, ast.Name):
        if uttrykk.id in konstanter:
            return "full", konstanter[uttrykk.id]
        return "ukjent", uttrykk.id
    if isinstance(uttrykk, ast.JoinedStr):
        tekst = ""
        for bit in uttrykk.values:
            if isinstance(bit, ast.Constant):
                tekst += str(bit.value)
                continue
            indre = bit.value
            if isinstance(indre, ast.Name) and indre.id in konstanter:
                tekst += konstanter[indre.id]
                continue
            if not tekst:
                return "ukjent", ast.unparse(indre)
            return "prefiks", tekst
        return "full", tekst
    return "ukjent", ast.unparse(uttrykk)


def _issue_ider_fra_kilden():
    """Issue-id-ene koden kan lage, lest ut av kildekoden.

    Tre steder teller: tredjeargumentet til `async_create_issue`, hver
    tilordning til en variabel som heter `issue_id`, og modulkonstantene som
    heter `*_ISSUE_ID` eller `*_ISSUE_PREFIX` og finnes nettopp for dette.
    """
    konstanter = _modulkonstanter()
    fulle: set[str] = set()
    prefikser: set[str] = set()
    ukjente: set[str] = set()

    for navn, verdi in konstanter.items():
        if navn.endswith("_ISSUE_ID"):
            fulle.add(verdi)
        elif navn.endswith("_ISSUE_PREFIX"):
            prefikser.add(verdi)

    for fil in sorted(KOMPONENT.glob("*.py")):
        if fil.name == "diagnostikk.py":
            continue
        kandidater = []
        for node in ast.walk(ast.parse(fil.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "async_create_issue":
                if len(node.args) >= 3:
                    kandidater.append(node.args[2])
                kandidater += [kw.value for kw in node.keywords if kw.arg == "issue_id"]
            elif isinstance(node, ast.Assign) and any(
                isinstance(mal, ast.Name) and mal.id == "issue_id" for mal in node.targets
            ):
                kandidater.append(node.value)
        for uttrykk in kandidater:
            slag, tekst = _les_issue_id(uttrykk, konstanter)
            {"full": fulle, "prefiks": prefikser, "ukjent": ukjente}[slag].add(tekst)

    return fulle, prefikser, ukjente


class TestRepairSorterMotKilden:
    """REPAIR_SORTER var en håndkopi, og en håndkopi driver.

    K3s `egendefinert_fastledd` manglet i den, og varselet sto som «<tekst
    utelatt>» i hver dump uten at noe ble rødt. Nå leses sortene ut av koden
    som lager dem.
    """

    def test_hver_issue_id_koden_lager_er_kjent(self):
        fulle, prefikser, _ = _issue_ider_fra_kilden()
        assert fulle, "fant ingen issue-id-er i kildekoden, da vakter denne testen ingenting"
        for tekst in sorted(fulle):
            assert tekst in REPAIR_SORTER, f"issue-id-en «{tekst}» mangler i REPAIR_SORTER"
        for tekst in sorted(prefikser):
            sort = tekst.rstrip("_")
            assert sort in REPAIR_SORTER or any(s.startswith(tekst) for s in REPAIR_SORTER), (
                f"issue-prefikset «{tekst}» mangler i REPAIR_SORTER"
            )

    def test_de_indirekte_veiene_er_de_vi_vet_om(self):
        """En ny indirekte id-bygging skal kreve en beslutning, ikke gli forbi."""
        _, _, ukjente = _issue_ider_fra_kilden()
        assert ukjente == KJENTE_INDIREKTE, (
            f"issue-id-er denne vakten ikke klarer å lese: {sorted(ukjente - KJENTE_INDIREKTE)}"
        )

    def test_egendefinert_fastledd_vises_med_sort(self):
        """Selve driften dommeren målte: sorten sto som markør i dumpen."""
        issues = {(konst.DOMAIN, f"egendefinert_fastledd_{HEMMELIG_ENTRY_ID}"): FakeIssue()}
        dump = _dump(FakeEntry(coordinator=FakeCoordinator()), issues=issues)
        assert dump["repairs"]["issues"][0]["sort"] == "egendefinert_fastledd"
        assert dump["repairs"]["issues"][0]["gjelder"] == "dette_anlegget"


# ---------------------------------------------------------------------------
# Ett nettselskap per fastledd-metode
# ---------------------------------------------------------------------------

# (nettselskap, sikringstrinn, trinnbeskrivelsen coordinatoren skal lage).
# Motvakten kjørte bare bkk, og så ingen av de fire andre metodene: for et
# sikringsbasert nettselskap sto både valget og trinnbeskrivelsen som
# «<tekst utelatt>», altså nettopp det en fastleddsak trenger.
FASTLEDD_PROVER: dict[str, tuple[str, str | None, str | None]] = {
    "TRE_DØGNMAX_MND": ("bkk", None, None),
    "MND_MAX": ("sor_aurdal_energi", None, None),
    "OV_TREFASE": ("alut", "inntil_3x125a", "Inntil 3 x 125 A"),
    "FEM_VEKTET_ÅR": ("fjellnett", None, None),
    "UKJENT": ("tinfos", None, None),
}


def _ekte_dump(coord_module, dso_id, sikringstrinn=None, trinntabell=None):
    """Dump av en ekte coordinator for et gitt nettselskap."""
    ekstra: dict[str, str] = {}
    if sikringstrinn is not None:
        ekstra[konst.CONF_SIKRINGSTRINN] = sikringstrinn
    if trinntabell is not None:
        ekstra[konst.CONF_EGENDEFINERT_KAPASITETSTRINN] = trinntabell
    entry = _make_entry(dso_id=dso_id, energy_sensor="sensor.energy", extra_data=ekstra)
    coordinator = coord_module.NettleieCoordinator(_make_hass(), entry)
    coordinator.data = _run_update(coord_module, coordinator)
    fake = FakeEntry(
        data={konst.CONF_DSO: dso_id, **ekstra},
        coordinator=coordinator,
    )
    return _dump(fake)


class TestHverFastleddMetode:
    """Dumpen må være like lesbar hos et sikrings-nettselskap som hos BKK."""

    def test_provene_dekker_hver_metode(self):
        assert set(FASTLEDD_PROVER) == set(FASTLEDD_METODER)

    @pytest.mark.parametrize("metode", sorted(FASTLEDD_PROVER))
    def test_nettselskapet_har_metoden_provet_paastar(self, metode):
        dso_id = FASTLEDD_PROVER[metode][0]
        assert hent_fastledd_metode(DSO_LIST[dso_id]) == metode

    @pytest.mark.parametrize("metode", sorted(FASTLEDD_PROVER))
    def test_dumpen_er_ren_for_hver_metode(self, coord_module, metode):
        dso_id, sikringstrinn, beskrivelse = FASTLEDD_PROVER[metode]
        dump = _ekte_dump(coord_module, dso_id, sikringstrinn)
        tekst = json.dumps(dump, allow_nan=False, ensure_ascii=False)
        assert TEKST_MARKOR not in tekst, "tekstvakten sensurerte en ekte verdi"
        assert NOKKEL_MARKOR not in tekst, "tekstvakten sensurerte en ekte nøkkel"
        assert dump["dso"]["fastledd_metode"] == metode
        if sikringstrinn is not None:
            assert dump["config_entry"]["valg"][konst.CONF_SIKRINGSTRINN] == sikringstrinn
            assert dump["beregning"]["kapasitetstrinn_intervall"] == beskrivelse

    def test_netera_er_det_andre_sikringsselskapet(self, coord_module):
        """To nettselskap deler metoden, men ingen trinn-id-er."""
        dump = _ekte_dump(coord_module, "netera", "230v_0_10")
        assert dump["config_entry"]["valg"][konst.CONF_SIKRINGSTRINN] == "230v_0_10"
        assert dump["beregning"]["kapasitetstrinn_intervall"] == "0-10 A (230 V)"
        assert TEKST_MARKOR not in json.dumps(dump, ensure_ascii=False)

    def test_sikringstrinn_uten_valg_sier_hvorfor(self, coord_module):
        dump = _ekte_dump(coord_module, "alut")
        assert dump["beregning"]["kapasitetstrinn_intervall"] == "sikringsstørrelse ikke valgt"
        assert dump["beregning"]["fastledd_mangler_sikringsvalg"] is True
        assert TEKST_MARKOR not in json.dumps(dump, ensure_ascii=False)

    def test_en_plantet_trinn_id_slipper_ikke_gjennom(self):
        """Vokabularet er katalogen vår, ikke hva som helst i konfigfeltet."""
        entry = FakeEntry(
            data={konst.CONF_SIKRINGSTRINN: HEMMELIG_ADRESSE},
            coordinator=FakeCoordinator(),
        )
        dump = _dump(entry)
        assert dump["config_entry"]["valg"][konst.CONF_SIKRINGSTRINN] == TEKST_MARKOR
        assert HEMMELIG_ADRESSE not in json.dumps(dump, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Trinntabellen for Egendefinert
# ---------------------------------------------------------------------------


class TestTrinntabell:
    """Egendefinert-brukeren er nettopp den vi trenger tabellen fra.

    Kommentaren i VALG_ALLOWLIST sa at trinntabellen forklarte fastleddet.
    Det gjorde den ikke: fritekstfeltet ble en markør i hver dump. Tallene
    parseren leste står nå under dso, og de bærer ingen strenger.
    """

    def test_brukerens_trinn_staar_som_tall(self, coord_module):
        dump = _ekte_dump(coord_module, "custom", trinntabell="2:155,5:250")
        assert dump["dso"]["kapasitetstrinn"] == [[2.0, 155], [5.0, 250]]
        assert dump["dso"]["kapasitetstrinn_count"] == 2
        assert TEKST_MARKOR not in json.dumps(dump, ensure_ascii=False)

    def test_raateksten_er_ikke_med(self, coord_module):
        dump = _ekte_dump(coord_module, "custom", trinntabell="2:155,5:250")
        assert konst.CONF_EGENDEFINERT_KAPASITETSTRINN not in dump["config_entry"]["valg"]
        assert "2:155,5:250" not in json.dumps(dump, ensure_ascii=False)

    def test_uten_tabell_sier_dumpen_at_fastleddet_er_ukjent(self, coord_module):
        dump = _ekte_dump(coord_module, "custom")
        assert dump["dso"]["kapasitetstrinn"] == []
        assert dump["beregning"]["fastledd_ukjent"] is True
        assert dump["beregning"]["kapasitetstrinn_intervall"] == "fastledd ukjent"
        assert TEKST_MARKOR not in json.dumps(dump, ensure_ascii=False)

    def test_katalogtrinnene_staar_ogsaa(self, coord_module):
        """Tabellen som ble regnet med, ikke bare antallet rader."""
        dump = _ekte_dump(coord_module, "bkk")
        assert dump["dso"]["kapasitetstrinn"][0] == [2.0, 155]
        # Øverste trinn har ingen øvre grense, og JSON har ingen uendelig.
        assert dump["dso"]["kapasitetstrinn"][-1][0] is None

    def test_en_plantet_streng_i_trinntabellen_sensureres(self):
        coordinator = FakeCoordinator(kapasitetstrinn=[(2, HEMMELIG_ADRESSE)])
        dump = _dump(FakeEntry(coordinator=coordinator))
        assert dump["dso"]["kapasitetstrinn"] == [[2, TEKST_MARKOR]]
        assert HEMMELIG_ADRESSE not in json.dumps(dump, ensure_ascii=False)


class TestVersjonsformatet:
    """«Tre tall, så hva som helst» slapp en adresse gjennom.

    Ingen brukerstyrt vei dit i dag, men formatet er det eneste som skiller en
    versjonsstreng fra en fritekst, og det skal ikke hvile på at ingen finner
    veien.
    """

    @pytest.mark.parametrize(
        "versjon",
        ["1.17.0", "2025.8.1", "2026.1.0b3", "2026.2.0.dev202601010223", "1.0.0-rc.1", "1.0.0+build.7"],
    )
    def test_ekte_versjoner_slipper_gjennom(self, versjon):
        assert tekstvakt(versjon)

    @pytest.mark.parametrize("juks", ["1.0.0nesttunveien42", "1.0.0nesttunveien-42", "1.0.0.Nesttunveien"])
    def test_en_adresse_bak_tre_tall_slipper_ikke(self, juks):
        assert not tekstvakt(juks)


class TestLekkasjeproberTrinn:
    """Egne forsøk på å lekke gjennom feltene denne runden la til.

    De nye veiene inn er trinntabellen, sikringstrinn-valget og trinnlisten i
    dso-seksjonen. Alle tre er tall eller katalogord hos oss, og alle tre tar
    imot det coordinatoren gir dem.
    """

    def test_trinntabellen_som_fritekst_lekker_ikke(self):
        entry = FakeEntry(
            data={
                konst.CONF_EGENDEFINERT_KAPASITETSTRINN: f"2:155,{HEMMELIG_ADRESSE}",
                konst.CONF_SIKRINGSTRINN: HEMMELIG_MAALEPUNKT,
            },
            coordinator=FakeCoordinator(),
        )
        tekst = json.dumps(_dump(entry), ensure_ascii=False)
        for plantet in (HEMMELIG_ADRESSE, HEMMELIG_MAALEPUNKT, "Nesttunveien"):
            assert plantet not in tekst, f"{plantet} lekket ut gjennom et trinnfelt"

    def test_en_plantet_noekkel_i_trinnlisten_sensureres(self):
        coordinator = FakeCoordinator(kapasitetstrinn=[(2, {HEMMELIG_ADRESSE: HEMMELIG_MAALEPUNKT})])
        dump = _dump(FakeEntry(coordinator=coordinator))
        assert dump["dso"]["kapasitetstrinn"] == [[2, {NOKKEL_MARKOR: TEKST_MARKOR}]]
        tekst = json.dumps(dump, ensure_ascii=False)
        assert HEMMELIG_ADRESSE not in tekst
        assert HEMMELIG_MAALEPUNKT not in tekst

    def test_et_plantet_sikringstrinn_i_en_option_lekker_ikke(self):
        entry = FakeEntry(
            options={konst.CONF_SIKRINGSTRINN: HEMMELIG_STI},
            data={konst.CONF_SIKRINGSTRINN: f"inntil_3x125a {HEMMELIG_STI}"},
            coordinator=FakeCoordinator(),
        )
        tekst = json.dumps(_dump(entry), ensure_ascii=False)
        assert HEMMELIG_STI not in tekst
