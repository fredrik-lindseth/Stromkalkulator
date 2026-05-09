"""Button-platform for Strømkalkulator.

Genererer en ferdig fakturaverifiserings-rapport som persistent_notification
i Home Assistant. Brukeren kan kopiere innholdet rett inn i et issue uten å
fylle ut tabeller manuelt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.components.button import ButtonEntity
from homeassistant.components.persistent_notification import async_create
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AVGIFTSSONE_STANDARD,
    CONF_AVGIFTSSONE,
    CONF_DSO,
    CONF_HAR_NORGESPRIS,
    CONF_SPOTPRIS_INKL_MVA,
    DEFAULT_DSO,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
)
from .dso import DSO_LIST


def _read_manifest_version() -> str:
    """Les versjon fra manifest.json (kun ved import for å unngå blocking I/O)."""
    try:
        manifest_path = Path(__file__).parent / "manifest.json"
        return str(json.loads(manifest_path.read_text()).get("version", "ukjent"))
    except (OSError, ValueError):
        return "ukjent"


_MANIFEST_VERSION: str = _read_manifest_version()

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import NettleieCoordinator
    from .dso import DSOEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button platform."""
    coordinator: NettleieCoordinator = entry.runtime_data
    async_add_entities([FakturaRapportButton(coordinator, entry)])


class FakturaRapportButton(CoordinatorEntity, ButtonEntity):  # type: ignore[misc]
    """Knapp som genererer fakturaverifiserings-rapport."""

    _attr_has_entity_name = True
    _attr_translation_key = "lag_fakturarapport"
    _attr_icon = "mdi:clipboard-text-outline"

    def __init__(
        self, coordinator: NettleieCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_lag_fakturarapport"
        dso_id = entry.data.get(CONF_DSO, DEFAULT_DSO)
        self._dso: DSOEntry = DSO_LIST.get(dso_id, DSO_LIST[DEFAULT_DSO])

    @property
    def device_info(self) -> DeviceInfo:
        from homeassistant.helpers.device_registry import DeviceInfo

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_forrige_maaned")},
            name="Forrige måned",
            manufacturer=MANUFACTURER,
            model=DEFAULT_NAME,
        )

    async def async_press(self) -> None:
        """Generer rapport og legg den i en persistent_notification."""
        markdown = self._build_report()
        async_create(
            self.hass,
            markdown,
            title="Fakturaverifiserings-rapport",
            notification_id=f"stromkalkulator_fakturarapport_{self._entry.entry_id}",
        )

    def _build_report(self) -> str:
        data: dict[str, Any] = self.coordinator.data or {}
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        har_norgespris = self._entry.data.get(CONF_HAR_NORGESPRIS, False)
        spotpris_inkl_mva = self._entry.data.get(CONF_SPOTPRIS_INKL_MVA, False)

        prev_name = data.get("previous_month_name") or "(forrige måned ikke tilgjengelig)"
        forbruk_dag = data.get("previous_month_consumption_dag_kwh", 0.0)
        forbruk_natt = data.get("previous_month_consumption_natt_kwh", 0.0)
        forbruk_total = data.get("previous_month_consumption_total_kwh", 0.0)
        kapasitetsledd = data.get("previous_month_kapasitetsledd", 0)
        kapasitetstrinn = data.get("previous_month_kapasitetstrinn") or "(ikke tilgjengelig)"
        avg_top_3 = data.get("previous_month_avg_top_3_kw", 0.0)
        norgespris_diff = data.get("previous_month_norgespris_diff_kr", 0.0)
        norgespris_komp = data.get("previous_month_norgespris_compensation_kr", 0.0)

        energiledd_dag = data.get("previous_month_energiledd_dag", 0.0)
        energiledd_natt = data.get("previous_month_energiledd_natt", 0.0)

        avtale = "Norgespris" if har_norgespris else "Spotpris + strømstøtte"
        spot_handling = "inkl. mva" if spotpris_inkl_mva else "eks. mva"

        return f"""**Fakturaverifisering for {prev_name}**

Kopier alt under linja og lim inn i et nytt issue:

---

## Oppsett

- **Nettselskap:** {self._dso['name']}
- **Prisområde:** {self._dso['prisomrade']}
- **Avgiftssone:** {avgiftssone}
- **Avtale:** {avtale}
- **Periode:** {prev_name}
- **Integrasjons-versjon:** {_MANIFEST_VERSION}
- **Spotpris-håndtering:** {spot_handling}

## Forbruk

| Kategori | kWh |
| --- | --- |
| Dag | {forbruk_dag:.3f} |
| Natt/helg | {forbruk_natt:.3f} |
| **Totalt** | **{forbruk_total:.3f}** |

## Integrasjonens beregninger

| Linje | Verdi |
| --- | --- |
| Energiledd dag (NOK/kWh inkl. alt) | {energiledd_dag:.4f} |
| Energiledd natt/helg (NOK/kWh inkl. alt) | {energiledd_natt:.4f} |
| Kapasitetstrinn | {kapasitetstrinn} |
| Kapasitetsledd (kr/mnd) | {kapasitetsledd} |
| Snitt topp 3 effekt (kW) | {avg_top_3:.2f} |
| Norgespris-besparelse (kr) | {norgespris_diff:.2f} |
| Norgespris-kompensasjon (kr) | {norgespris_komp:.2f} |

## Faktura (fyll inn)

| Linje | Pris på faktura | Beløp på faktura (kr) |
| --- | --- | --- |
| Energiledd dag | | |
| Energiledd natt/helg | | |
| Forbruksavgift | | |
| Enovaavgift | | |
| Kapasitet | | |
| Strømstøtte (hvis spot-kunde) | | |
| Norgespris-kompensasjon (hvis Norgespris) | | |
| **Sum nettleie** | | |

## Konklusjon

- [ ] Alle linjer matcher (avrundingsavvik på øre-nivå er normalt)
- [ ] Avvik som bør undersøkes:

## Kreditt

Hvordan vil du krediteres? (fornavn / alias / handle / anonymt)

---

Personvern: ikke ta med navn, adresse, kundenummer, fakturanummer eller KID."""
