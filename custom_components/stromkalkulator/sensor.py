"""Sensor platform for Strømkalkulator."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    AVGIFTSSONE_STANDARD,
    CONF_AVGIFTSSONE,
    CONF_DSO,
    DEFAULT_DSO,
    DEFAULT_NAME,
    DOMAIN,
    DSO_LIST,
    ENOVA_AVGIFT,
    MANUFACTURER,
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_RATE,
    get_forbruksavgift,
    get_mva_sats,
    get_norgespris_inkl_mva,
    get_norgespris_max_kwh,
)
from .coordinator import days_in_month
from .dso import FASTLEDD_UKJENT

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import NettleieCoordinator
    from .dso import DSOEntry

# Device group constants
DEVICE_NETTLEIE = "stromkalkulator"
DEVICE_STROMSTOTTE = "stromstotte"
DEVICE_NORGESPRIS = "norgespris"
DEVICE_MAANEDLIG = "maanedlig"
DEVICE_FORRIGE_MAANED = "forrige_maaned"
DEVICE_EKSPORT = "eksport"

# Coordinator-entiteter gjør ingen egen I/O ved oppdatering, så oppdateringene
# trenger ikke serialiseres. 0 er HA-konvensjonen for coordinator-baserte
# plattformer (ubegrenset parallellitet, coordinateren styrer henting).
PARALLEL_UPDATES = 0

# SensorDeviceClass.ENUM som modulkonstant. getattr med streng-fallback gjør
# importen robust der SensorDeviceClass er en redusert stub uten ENUM-medlemmet;
# i Home Assistant er ENUM uansett StrEnum-verdien "enum".
_ENUM_DEVICE_CLASS = getattr(SensorDeviceClass, "ENUM", "enum")

# Periodene TOTAL-sensorer akkumulerer over, som (coordinator-nøkkel, format).
# Nøkkelen peker på merkelappen coordinatoren nullstiller sammen med verdien.
PERIODE_MAANED = ("current_month", "%Y-%m")
PERIODE_DOGN = ("current_date", "%Y-%m-%d")


def _periodestart(merkelapp: Any, format_: str) -> datetime | None:
    """Lokal midnatt ved starten av perioden, eller None hvis merkelappen mangler.

    Månedsmerkelappen "2026-07" gir 1. juli kl. 00:00 lokal tid, døgnmerkelappen
    "2026-07-15" gir 15. juli kl. 00:00. Ugyldige verdier gir None framfor å
    kaste, slik at en sensor med rar lagret data fortsatt publiserer verdien sin.
    """
    if not isinstance(merkelapp, str):
        return None
    try:
        parsed = datetime.strptime(merkelapp, format_)
    except ValueError:
        return None
    return cast("datetime", dt_util.start_of_local_day(parsed))


def _tall(data: dict[str, Any], noekkel: str) -> float:
    """Bokført krone- eller kilowattimeverdi, med 0 for manglende eller rar verdi.

    Sensorene leser felt coordinatoren fyller ved hver oppdatering. En eldre
    lagret fil eller en teststub kan mangle et felt, og da er null det ærlige
    svaret framfor en TypeError midt i en state-skriving.
    """
    verdi = data.get(noekkel)
    return float(verdi) if isinstance(verdi, (int, float)) and not isinstance(verdi, bool) else 0.0


def _bokfort_nettleie(data: dict[str, Any]) -> float:
    """Nettleien måneden har bokført så langt: energiledd pluss fastledd.

    Begge leddene kommer fra kostnadskjernen. Energileddet er summen av dag,
    natt og de offentlige avgiftene slik de ble priset i hvert intervall, og
    fastleddet er månedsbeløpet ganget med forløpt andel av måneden. Det er
    linjen BKK kaller nettleie subtotal, og den avstemmer mot fakturaen på øret
    (docs/research/revalidering-l3b-september-2026.md).
    """
    return _tall(data, "monthly_accumulated_cost_energiledd_kr") + _tall(
        data, "monthly_accumulated_cost_kapasitetsledd_kr"
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Strømkalkulator sensors."""
    coordinator: NettleieCoordinator = entry.runtime_data

    entities: list[NettleieBaseSensor] = [
        # Nettleie - Kapasitet
        MaksForbrukSensor(coordinator, entry, 1),
        MaksForbrukSensor(coordinator, entry, 2),
        MaksForbrukSensor(coordinator, entry, 3),
        GjennomsnittForbrukSensor(coordinator, entry),
        TrinnNummerSensor(coordinator, entry),
        TrinnIntervallSensor(coordinator, entry),
        KapasitetstrinnSensor(coordinator, entry),
        MarginNesteTrinnSensor(coordinator, entry),
        # Nettleie - Energiledd
        EnergileddSensor(coordinator, entry),
        EnergileddDagSensor(coordinator, entry),
        EnergileddNattSensor(coordinator, entry),
        TariffSensor(coordinator, entry),
        # Nettleie - Avgifter
        OffentligeAvgifterSensor(coordinator, entry),
        ForbruksavgiftSensor(coordinator, entry),
        EnovaavgiftSensor(coordinator, entry),
        # Strømpriser
        TotalPriceSensor(coordinator, entry),
        ElectricityCompanyTotalSensor(coordinator, entry),
        StromprisPerKwhSensor(coordinator, entry),
        # Strømstøtte
        StromstotteSensor(coordinator, entry),
        SpotprisEtterStotteSensor(coordinator, entry),
        TotalPrisEtterStotteSensor(coordinator, entry),
        TotalPrisInklAvgifterSensor(coordinator, entry),
        StromstotteGjenstaaendeSensor(coordinator, entry),
        StromprisPerKwhEtterStotteSensor(coordinator, entry),
        # Norgespris
        TotalPrisNorgesprisSensor(coordinator, entry),
        StromprisNorgesprisSensor(coordinator, entry),
        PrisforskjellNorgesprisSensor(coordinator, entry),
        # Månedlig forbruk og kostnad
        MaanedligForbrukDagSensor(coordinator, entry),
        MaanedligForbrukNattSensor(coordinator, entry),
        MaanedligForbrukTotalSensor(coordinator, entry),
        MaanedligNettleieSensor(coordinator, entry),
        MaanedligAvgifterSensor(coordinator, entry),
        MaanedligStromstotteSensor(coordinator, entry),
        MaanedligTotalSensor(coordinator, entry),
        MaanedligNorgesprisDifferanseSensor(coordinator, entry),
        MaanedligNorgesprisKompensasjonSensor(coordinator, entry),
        DagskostnadSensor(coordinator, entry),
        AkkumulertKostnadSensor(coordinator, entry),
        EstimertMaanedskostnadSensor(coordinator, entry),
        # Forrige måned sensors
        ForrigeMaanedForbrukDagSensor(coordinator, entry),
        ForrigeMaanedForbrukNattSensor(coordinator, entry),
        ForrigeMaanedForbrukTotalSensor(coordinator, entry),
        ForrigeMaanedNettleieSensor(coordinator, entry),
        ForrigeMaanedToppforbrukSensor(coordinator, entry),
        ForrigeMaanedNorgesprisKompensasjonSensor(coordinator, entry),
        # Eksport (plusskunder med solceller)
        MaanedligEksportKwhSensor(coordinator, entry),
        MaanedligEksportInntektSensor(coordinator, entry),
        MaanedligNettokostnadSensor(coordinator, entry),
        ForrigeMaanedEksportKwhSensor(coordinator, entry),
        ForrigeMaanedEksportInntektSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class NettleieBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Strømkalkulator sensors."""

    _attr_has_entity_name = True
    _device_group: str = DEVICE_NETTLEIE
    _attr_unique_id: str
    _attr_translation_key: str
    _entry: ConfigEntry
    _dso: DSOEntry
    _last_state_written: tuple[Any, ...] | None = None
    # Settes av TOTAL-sensorer som nullstilles ved periodeskifte. Se last_reset.
    _reset_periode: ClassVar[tuple[str, str] | None] = None

    def __init__(
        self,
        coordinator: NettleieCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
        translation_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_translation_key = translation_key
        self._entry = entry

        dso_id = entry.data.get(CONF_DSO, DEFAULT_DSO)
        self._dso = DSO_LIST.get(dso_id, DSO_LIST[DEFAULT_DSO])

    def _handle_coordinator_update(self) -> None:
        """Skriv kun ny state når noe faktisk endret seg.

        Uten dette skriver hver sensor state ved hver coordinator-refresh
        (~1/min), så recorderen får en identisk rad per sensor i minuttet.
        Signaturen dekker alt som styrer entitetens HA-state: tilgjengelighet,
        verdi, attributter og last_reset. Er den uendret, hoppes skrivingen over.
        """
        signature = (
            self.available,
            self.native_value,
            self.extra_state_attributes,
            self.last_reset,
        )
        if signature == self._last_state_written:
            return
        self._last_state_written = signature
        super()._handle_coordinator_update()

    @property
    def last_reset(self) -> datetime | None:
        """Starten på perioden en TOTAL-sensor akkumulerer over.

        HA-statistikken trenger dette for sensorer som nullstilles: uten
        last_reset bokføres fallet fra periodesum til 0 som et negativt delta,
        og første time i ny periode viser hele forrige periodesum med minus
        i Energy-dashboardet. Periodestarten leses fra samme coordinator-
        oppdatering som verdien, slik at nullstillingen og den nye
        last_reset ankommer statistikk-kompilatoren atomisk.

        None for sensorer uten periodenullstilling (måleverdier og
        TOTAL_INCREASING-tellere).
        """
        if self._reset_periode is None:
            return None
        data = self.coordinator.data
        if not data:
            return None
        noekkel, format_ = self._reset_periode
        return _periodestart(data.get(noekkel), format_)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        device_names: dict[str, str] = {
            DEVICE_NETTLEIE: f"Nettleie ({self._dso['name']})",
            DEVICE_STROMSTOTTE: "Strømstøtte",
            DEVICE_NORGESPRIS: "Norgespris",
            DEVICE_EKSPORT: "Eksport (solceller)",
        }
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._device_group}")},
            name=device_names.get(self._device_group, f"Nettleie ({self._dso['name']})"),
            manufacturer=MANUFACTURER,
            model=DEFAULT_NAME,
        )

    def _spot_price_valid(self) -> bool:
        """True hvis coordinator har gyldig spotpris (ikke kaldstart/bortfall).

        Mangler nøkkelen (eldre data eller test-stub) antas spot gyldig, slik at
        gatingen ikke gjør ellers fungerende sensorer utilgjengelige.
        """
        return bool(self.coordinator.data and self.coordinator.data.get("spot_price_valid", True))

    def _norgespris_fastpris_aktiv(self) -> bool:
        """True når aktiv pris er Norgespris under taket (uavhengig av spot).

        Da kan spot-avhengige sensorer publisere fastprisen selv uten gyldig spot.
        """
        data = self.coordinator.data
        return bool(data and data.get("har_norgespris", False) and not data.get("norgespris_over_tak", False))

    def _spot_dependent(self, key: str, *, spot_free: bool = False) -> Any:
        """Coordinator-verdi, eller None hvis verdien er spot-avhengig og spot mangler.

        Ved kaldstart/bortfall (spot_price_valid=False) settes spot til 0,0. Uten
        gating ville spot-avhengige pris-sensorer publisere 0-baserte priser til
        recorderen. `spot_free=True` markerer at den aktive verdien ikke avhenger
        av spot (f.eks. Norgespris under taket) og publiseres uansett.
        """
        data = self.coordinator.data
        if not data:
            return None
        if not spot_free and not data.get("spot_price_valid", True):
            return None
        return data.get(key)

    def _fastledd_ukjent(self) -> bool:
        """Om kapasitetsleddet er ukjent fordi ingen kjenner trinnene.

        Egendefinert nettselskap uten brukeroppgitt trinntabell. Sensorer som
        bygger på et månedsbeløp blir Ukjent, og de som regner per kWh regnes
        uten fastledd og sier fra i et attributt (kontrakt §9).
        """
        return bool(self.coordinator.data and self.coordinator.data.get("fastledd_ukjent"))

    def _merk_fastledd_ukjent(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Legg på flagget som forteller at fastleddet ikke er med i tallet."""
        if self._fastledd_ukjent():
            attrs["fastledd_ukjent"] = True
        return attrs

    def _get_forbruksavgift(self) -> float:
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        return get_forbruksavgift(avgiftssone)

    def _get_mva_sats(self) -> float:
        """Get MVA rate based on avgiftssone."""
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        return get_mva_sats(avgiftssone)

    def _energiledd_eks_avgifter_attributes(self, data_key: str) -> dict[str, Any] | None:
        """Return energiledd attributes with eks-avgifter breakdown for invoice comparison."""
        if not self.coordinator.data:
            return None
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        mva_sats = get_mva_sats(avgiftssone)
        energiledd = self.coordinator.data.get(data_key, 0)
        forbruksavgift = get_forbruksavgift(avgiftssone)
        energiledd_eks_avgifter = energiledd / (1 + mva_sats) - forbruksavgift - ENOVA_AVGIFT
        return {
            "inkl_avgifter_mva": energiledd,
            "eks_avgifter_mva": round(energiledd_eks_avgifter, 4),
            "note": "Fakturaen viser pris eks. avgifter. Sammenlign med eks_avgifter_mva.",
        }


class EnergileddSensor(NettleieBaseSensor):
    """Sensor for energiledd."""

    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "energiledd", "energiledd")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("energiledd"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            attrs: dict[str, Any] = {
                "is_day_rate": self.coordinator.data.get("is_day_rate"),
                "rate_type": "dag" if self.coordinator.data.get("is_day_rate") else "natt/helg",
                "energiledd_dag": self.coordinator.data.get("energiledd_dag"),
                "energiledd_natt": self.coordinator.data.get("energiledd_natt"),
                "dso": self.coordinator.data.get("dso"),
            }
            opprinnelse = self.coordinator.data.get("tarifforigin") or {}
            attrs["tariffmodus"] = opprinnelse.get("modus")
            perioder = self.coordinator.data.get("energiledd_perioder")
            if perioder:
                attrs["sesongprising"] = True
                attrs["aktiv_periode"] = self.coordinator.data.get("aktiv_energiledd_periode")
                attrs["perioder"] = perioder
            # Brukeren har tastet en fast sats, men nettselskapet bytter pris
            # flere ganger i året og periodene styrer. Sies rett ut her framfor
            # å la satsen se ut som om den gjelder.
            if opprinnelse.get("manual_ignorert"):
                attrs["manual_ignorert"] = True
            return attrs
        return None


class KapasitetstrinnSensor(NettleieBaseSensor):
    """Sensor for kapasitetstrinn."""

    # Sats, ikke pengebeløp: ingen MONETARY, ingen ISO 4217. Se docs/domain-rules.md.
    _attr_native_unit_of_measurement: str = "kr/mnd"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "kapasitetstrinn", "kapasitetstrinn")

    @property
    def native_value(self) -> float | int | None:
        """Return the state.

        Ukjent (None) når nettselskapet fakturerer etter sikringsstørrelse og
        brukeren ikke har oppgitt den, og når et egendefinert nettselskap står
        uten trinntabell. Et tall her ville sett riktig ut og vært gjetning, og
        det er nettopp feilen incident 006 handler om.
        """
        if not self.coordinator.data:
            return None
        if self.coordinator.data.get("fastledd_mangler_sikringsvalg"):
            return None
        if self._fastledd_ukjent():
            return None
        return cast("float | int | None", self.coordinator.data.get("kapasitetsledd"))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            top_3 = self.coordinator.data.get("top_3_days", {})
            metode = self.coordinator.data.get("fastledd_metode")
            attrs: dict[str, Any] = {
                "trinn": self.coordinator.data.get("kapasitetstrinn_nummer"),
                "intervall": self.coordinator.data.get("kapasitetstrinn_intervall"),
                "gjennomsnitt_kw": self.coordinator.data.get("avg_top_3_kw"),
                "fastledd_metode": metode,
                "fastledd_grunnlag_kw": self.coordinator.data.get("fastledd_grunnlag_kw"),
                "current_power_kw": self.coordinator.data.get("current_power_kw"),
                "dso": self.coordinator.data.get("dso"),
            }
            if self.coordinator.data.get("fastledd_mangler_sikringsvalg"):
                attrs["mangler_sikringsstorrelse"] = True
            self._merk_fastledd_ukjent(attrs)
            if metode == FASTLEDD_UKJENT:
                # Nettselskapet publiserer ikke metoden sin, så beløpet er
                # regnet med NVE-modellen og kan avvike fra fakturaen.
                attrs["metode_uverifisert"] = True
            for i, (date, entry) in enumerate(top_3.items(), 1):
                attrs[f"maks_{i}_dato"] = date
                attrs[f"maks_{i}_kw"] = round(entry.kw, 2)
                attrs[f"maks_{i}_time"] = entry.hour
            return attrs
        return None


class MarginNesteTrinnSensor(NettleieBaseSensor):
    """Sensor for margin to next capacity tier."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement: str = "kW"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "margin_neste_trinn", "margin_neste_trinn")

    @property
    def native_value(self) -> float | None:
        """Return the state (Ukjent uten kjente trinn å ha margin til)."""
        if self.coordinator.data and not self._fastledd_ukjent():
            return cast("float | None", self.coordinator.data.get("margin_neste_trinn_kw"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "naavarende_trinn_pris": self.coordinator.data.get("kapasitetsledd"),
                "neste_trinn_pris": self.coordinator.data.get("neste_trinn_pris"),
            }
        return None


class TotalPriceSensor(NettleieBaseSensor):
    """Sensor for total electricity price (without strømstøtte)."""

    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_price", "total_price")

    @property
    def native_value(self) -> float | None:
        """Return the state (None ved manglende spotdata)."""
        return cast("float | None", self._spot_dependent("total_price_uten_stotte"))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return self._merk_fastledd_ukjent(
                {
                    "spot_price": self.coordinator.data.get("spot_price"),
                    "energiledd": self.coordinator.data.get("energiledd"),
                    "kapasitetsledd_per_kwh": self.coordinator.data.get("kapasitetsledd_per_kwh"),
                    "dso": self.coordinator.data.get("dso"),
                }
            )
        return None


class MaksForbrukSensor(NettleieBaseSensor):
    """Sensor for max power consumption on a specific day."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement: str = "kW"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _rank: int

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry, rank: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, f"maks_forbruk_{rank}", "maks_forbruk")
        self._rank = rank

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            top_3 = self.coordinator.data.get("top_3_days", {})
            if len(top_3) >= self._rank:
                entries = list(top_3.values())
                return round(cast("float", entries[self._rank - 1].kw), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            top_3 = self.coordinator.data.get("top_3_days", {})
            if len(top_3) >= self._rank:
                dates = list(top_3.keys())
                entries = list(top_3.values())
                return {
                    "dato": dates[self._rank - 1],
                    "time": entries[self._rank - 1].hour,
                }
        return None


class GjennomsnittForbrukSensor(NettleieBaseSensor):
    """Sensor for average of top 3 power consumption days."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement: str = "kW"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "gjennomsnitt_forbruk", "gjs_forbruk")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            avg = self.coordinator.data.get("avg_top_3_kw")
            if avg is not None:
                return round(cast("float", avg), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "kapasitetstrinn": self.coordinator.data.get("kapasitetsledd"),
                "dso": self.coordinator.data.get("dso"),
            }
        return None


class TrinnNummerSensor(NettleieBaseSensor):
    """Sensor for capacity tier number."""

    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default: bool = False

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "trinn_nummer", "trinn_nummer")

    @property
    def native_value(self) -> int | None:
        """Return the state (Ukjent når trinnene ikke er kjent)."""
        if self.coordinator.data and not self._fastledd_ukjent():
            return cast("int | None", self.coordinator.data.get("kapasitetstrinn_nummer"))
        return None


class TrinnIntervallSensor(NettleieBaseSensor):
    """Sensor for capacity tier interval."""

    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default: bool = False

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "trinn_intervall", "trinn_intervall")

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("str | None", self.coordinator.data.get("kapasitetstrinn_intervall"))
        return None


class OffentligeAvgifterSensor(NettleieBaseSensor):
    """Sensor for offentlige avgifter (forbruksavgift, Enova, mva)."""

    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default: bool = False
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "offentlige_avgifter", "offentlige_avgifter")

    @property
    def native_value(self) -> float:
        """Return total avgifter inkl. mva."""
        forbruksavgift = self._get_forbruksavgift()
        mva_sats = self._get_mva_sats()
        total_eks_mva = forbruksavgift + ENOVA_AVGIFT
        return round(total_eks_mva * (1 + mva_sats), 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return breakdown of fees."""
        forbruksavgift = self._get_forbruksavgift()
        mva_sats = self._get_mva_sats()
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)

        forbruksavgift_inkl_mva = round(forbruksavgift * (1 + mva_sats), 4)
        enova_inkl_mva = round(ENOVA_AVGIFT * (1 + mva_sats), 4)
        return {
            "avgiftssone": avgiftssone,
            "forbruksavgift_eks_mva": forbruksavgift,
            "forbruksavgift_inkl_mva": forbruksavgift_inkl_mva,
            "enova_avgift_eks_mva": ENOVA_AVGIFT,
            "enova_avgift_inkl_mva": enova_inkl_mva,
            "mva_sats": f"{int(mva_sats * 100)}%",
            "note": "Disse avgiftene er inkludert i energileddet fra nettselskapet",
        }


class ElectricityCompanyTotalSensor(NettleieBaseSensor):
    """Sensor for total price with electricity company + nettleie."""

    _attr_entity_registry_enabled_default: bool = False
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "electricity_company_total", "electricity_company_total")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            electricity_company_total = self.coordinator.data.get("electricity_company_total")
            if electricity_company_total is not None:
                return round(cast("float", electricity_company_total), 4)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return self._merk_fastledd_ukjent(
                {
                    "electricity_company_pris": self.coordinator.data.get("electricity_company_price"),
                    "energiledd": self.coordinator.data.get("energiledd"),
                    "kapasitetsledd_per_kwh": self.coordinator.data.get("kapasitetsledd_per_kwh"),
                }
            )
        return None


class StromprisPerKwhSensor(NettleieBaseSensor):
    """Sensor for electricity price per kWh (without capacity fee)."""

    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "strompris_per_kwh", "strompris_per_kwh")

    @property
    def native_value(self) -> float | None:
        """Return the state (None ved manglende spotdata, med mindre Norgespris under tak)."""
        return cast(
            "float | None",
            self._spot_dependent("strompris_per_kwh", spot_free=self._norgespris_fastpris_aktiv()),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return self._merk_fastledd_ukjent(
                {
                    "spot_price": self.coordinator.data.get("spot_price"),
                    "energiledd": self.coordinator.data.get("energiledd"),
                }
            )
        return None


class StromstotteSensor(NettleieBaseSensor):
    """Sensor for strømstøtte per kWh."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "stromstotte", "stromstotte")

    @property
    def native_value(self) -> float | None:
        """Return the state (None ved manglende spotdata)."""
        return cast("float | None", self._spot_dependent("stromstotte"))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spotpris": self.coordinator.data.get("spot_price"),
                "terskel": self.coordinator.data.get("stromstotte_terskel", STROMSTOTTE_LEVEL),
                "dekningsgrad": f"{int(STROMSTOTTE_RATE * 100)}%",
                "tak_naadd": self.coordinator.data.get("stromstotte_tak_naadd", False),
                "boligtype": self.coordinator.data.get("boligtype", "bolig"),
            }
        return None


class SpotprisEtterStotteSensor(NettleieBaseSensor):
    """Sensor for spot price after strømstøtte."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "spotpris_etter_stotte", "spotpris_etter_stotte")

    @property
    def native_value(self) -> float | None:
        """Return the state (None ved manglende spotdata)."""
        return cast("float | None", self._spot_dependent("spotpris_etter_stotte"))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spotpris": self.coordinator.data.get("spot_price"),
                "stromstotte": self.coordinator.data.get("stromstotte"),
            }
        return None


class TotalPrisEtterStotteSensor(NettleieBaseSensor):
    """Sensor for total price after strømstøtte (spot + nettleie - støtte)."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_pris_etter_stotte", "total_pris_etter_stotte")

    @property
    def native_value(self) -> float | None:
        """Return the state (None ved manglende spotdata, med mindre Norgespris under tak)."""
        return cast(
            "float | None",
            self._spot_dependent("total_price", spot_free=self._norgespris_fastpris_aktiv()),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return self._merk_fastledd_ukjent(
                {
                    "spotpris": self.coordinator.data.get("spot_price"),
                    "stromstotte": self.coordinator.data.get("stromstotte"),
                    "spotpris_etter_stotte": self.coordinator.data.get("spotpris_etter_stotte"),
                    "energiledd": self.coordinator.data.get("energiledd"),
                    "kapasitetsledd_per_kwh": self.coordinator.data.get("kapasitetsledd_per_kwh"),
                }
            )
        return None


class TotalPrisInklAvgifterSensor(NettleieBaseSensor):
    """Sensor for total price including all taxes (for Energy Dashboard)."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_pris_inkl_avgifter", "total_pris_inkl_avgifter")

    @property
    def native_value(self) -> float | None:
        """Return the state (None ved manglende spotdata, med mindre Norgespris under tak)."""
        return cast(
            "float | None",
            self._spot_dependent("total_price_inkl_avgifter", spot_free=self._norgespris_fastpris_aktiv()),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes with breakdown."""
        if self.coordinator.data:
            return self._merk_fastledd_ukjent(
                {
                    "spotpris": self.coordinator.data.get("spot_price"),
                    "stromstotte": self.coordinator.data.get("stromstotte"),
                    "spotpris_etter_stotte": self.coordinator.data.get("spotpris_etter_stotte"),
                    "energiledd": self.coordinator.data.get("energiledd"),
                    "kapasitetsledd_per_kwh": self.coordinator.data.get("kapasitetsledd_per_kwh"),
                    "forbruksavgift_inkl_mva": self.coordinator.data.get("forbruksavgift_inkl_mva"),
                    "enova_inkl_mva": self.coordinator.data.get("enova_inkl_mva"),
                    "offentlige_avgifter": self.coordinator.data.get("offentlige_avgifter"),
                    "bruk": "Marginalkostnad per kWh for Energy Dashboard. Månedlig sum avviker fra faktura pga. kapasitetsledd-fordeling.",
                }
            )
        return None


class TotalPrisNorgesprisSensor(NettleieBaseSensor):
    """Sensor for totalpris med norgespris."""

    _device_group: str = DEVICE_NORGESPRIS
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_pris_norgespris", "total_pris_norgespris")

    @property
    def native_value(self) -> float | None:
        """Return the state (None ved manglende spotdata når man er over Norgespris-taket)."""
        data = self.coordinator.data
        spot_free = not (data and data.get("norgespris_over_tak", False))
        return cast("float | None", self._spot_dependent("total_pris_norgespris", spot_free=spot_free))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return self._merk_fastledd_ukjent(
                {
                    "norgespris": self.coordinator.data.get("norgespris"),
                    "energiledd": self.coordinator.data.get("energiledd"),
                    "kapasitetsledd_per_kwh": self.coordinator.data.get("kapasitetsledd_per_kwh"),
                    "norgespris_over_tak": self.coordinator.data.get("norgespris_over_tak", False),
                    "boligtype": self.coordinator.data.get("boligtype", "bolig"),
                }
            )
        return None


class StromprisNorgesprisSensor(NettleieBaseSensor):
    """Sensor for ren strømpris under Norgespris-ordningen, uten nettleie."""

    _device_group: str = DEVICE_NORGESPRIS
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "strompris_norgespris", "strompris_norgespris")

    @property
    def native_value(self) -> float | None:
        """Return the state (None ved manglende spotdata når man er over Norgespris-taket)."""
        data = self.coordinator.data
        spot_free = not (data and data.get("norgespris_over_tak", False))
        return cast("float | None", self._spot_dependent("strompris_norgespris", spot_free=spot_free))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            boligtype = self.coordinator.data.get("boligtype", "bolig")
            return self._merk_fastledd_ukjent(
                {
                    "fast_pris": self.coordinator.data.get("norgespris"),
                    "spot_pris": self.coordinator.data.get("spot_price"),
                    "forbruk_denne_maaneden_kwh": self.coordinator.data.get("monthly_consumption_total_kwh"),
                    "maks_kwh_med_fast_pris": get_norgespris_max_kwh(boligtype),
                    "over_maaneds_grense": self.coordinator.data.get("norgespris_over_tak", False),
                    "boligtype": boligtype,
                }
            )
        return None


class PrisforskjellNorgesprisSensor(NettleieBaseSensor):
    """Sensor for prisforskjell mellom norgespris og vanlig pris."""

    _device_group: str = DEVICE_NORGESPRIS
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "prisforskjell_norgespris", "prisforskjell_norgespris")

    @property
    def native_value(self) -> float | None:
        """Return the state (None ved manglende spotdata; sammenligningen krever spot)."""
        return cast("float | None", self._spot_dependent("kroner_spart_per_kwh"))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            norgespris = self.coordinator.data.get("norgespris")
            spotpris_etter_stotte = self.coordinator.data.get("spotpris_etter_stotte")
            # "Din pris" er det kunden faktisk betaler: Norgespris for
            # Norgespris-kunder, ellers spotpris etter strømstøtte.
            har_norgespris = self.coordinator.data.get("har_norgespris", False)
            din_pris_etter_stotte = norgespris if har_norgespris else spotpris_etter_stotte
            # Differansen måles mot ordningen du IKKE har. For en Norgespris-kunde
            # er begge de to feltene over Norgespris-satsen, så uten dette så
            # attributtene ut som 0,50 mot 0,50 med en differanse på 0,51.
            alternativ_etter_stotte = spotpris_etter_stotte if har_norgespris else norgespris
            return {
                "din_pris_etter_stotte": din_pris_etter_stotte,
                "alternativ_etter_stotte": alternativ_etter_stotte,
                "norgespris_etter_stotte": norgespris,
                "differens_per_kwh": self.coordinator.data.get("kroner_spart_per_kwh"),
                "note": f"Norgespris er fast {get_norgespris_inkl_mva(self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)) * 100:.0f} øre/kWh",
            }
        return None


# =============================================================================
# Fakturasammenligning - Separate sensorer for hver fakturalinje
# =============================================================================


class EnergileddDagSensor(NettleieBaseSensor):
    """Sensor for energiledd dag-sats (eks. avgifter, for fakturasammenligning)."""

    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default: bool = False
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "energiledd_dag", "energiledd_dag")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("energiledd_dag"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        return self._energiledd_eks_avgifter_attributes("energiledd_dag")


class EnergileddNattSensor(NettleieBaseSensor):
    """Sensor for energiledd natt/helg-sats (eks. avgifter, for fakturasammenligning)."""

    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default: bool = False
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "energiledd_natt", "energiledd_natt")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("energiledd_natt"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        return self._energiledd_eks_avgifter_attributes("energiledd_natt")


class ForbruksavgiftSensor(NettleieBaseSensor):
    """Sensor for forbruksavgift (elavgift) per kWh."""

    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default: bool = False
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forbruksavgift", "forbruksavgift")

    @property
    def native_value(self) -> float:
        """Return forbruksavgift inkl. mva."""
        forbruksavgift = self._get_forbruksavgift()
        mva_sats = self._get_mva_sats()
        return round(forbruksavgift * (1 + mva_sats), 4)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return breakdown."""
        forbruksavgift = self._get_forbruksavgift()
        mva_sats = self._get_mva_sats()
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        return {
            "eks_mva": forbruksavgift,
            "inkl_mva": round(forbruksavgift * (1 + mva_sats), 4),
            "mva_sats": f"{int(mva_sats * 100)}%",
            "avgiftssone": avgiftssone,
            "ore_per_kwh_eks_mva": round(forbruksavgift * 100, 2),
            "note": "Fakturaen viser forbruksavgift eks. mva",
        }


class EnovaavgiftSensor(NettleieBaseSensor):
    """Sensor for Enova-avgift per kWh."""

    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default: bool = False
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "enovaavgift", "enovaavgift")

    @property
    def native_value(self) -> float:
        """Return Enova-avgift inkl. mva."""
        mva_sats = self._get_mva_sats()
        return round(ENOVA_AVGIFT * (1 + mva_sats), 4)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return breakdown."""
        mva_sats = self._get_mva_sats()
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        return {
            "eks_mva": ENOVA_AVGIFT,
            "inkl_mva": round(ENOVA_AVGIFT * (1 + mva_sats), 4),
            "mva_sats": f"{int(mva_sats * 100)}%",
            "avgiftssone": avgiftssone,
            "ore_per_kwh_eks_mva": round(ENOVA_AVGIFT * 100, 2),
            "note": "Fakturaen viser Enova-avgift eks. mva (1,0 øre/kWh)",
        }


class StromstotteGjenstaaendeSensor(NettleieBaseSensor):
    """Sensor for remaining kWh before strømstøtte cap."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "stromstotte_gjenstaaende", "stromstotte_gjenstaaende")

    @property
    def native_value(self) -> float | None:
        """Return remaining kWh before cap is reached."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("stromstotte_gjenstaaende_kwh"))
        return None


class StromprisPerKwhEtterStotteSensor(NettleieBaseSensor):
    """Sensor for electricity price per kWh after subsidy (without capacity fee)."""

    _attr_entity_registry_enabled_default: bool = False
    _device_group: str = DEVICE_STROMSTOTTE
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, "strompris_per_kwh_etter_stotte", "strompris_per_kwh_etter_stotte"
        )

    @property
    def native_value(self) -> float | None:
        """Return the state (None ved manglende spotdata, med mindre Norgespris under tak)."""
        return cast(
            "float | None",
            self._spot_dependent(
                "strompris_per_kwh_etter_stotte", spot_free=self._norgespris_fastpris_aktiv()
            ),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spotpris": self.coordinator.data.get("spot_price"),
                "stromstotte": self.coordinator.data.get("stromstotte"),
                "energiledd": self.coordinator.data.get("energiledd"),
            }
        return None


class TariffSensor(NettleieBaseSensor):
    """Sensor for current tariff period (dag/natt) - for use with utility_meter."""

    _attr_device_class: SensorDeviceClass = _ENUM_DEVICE_CLASS
    _attr_options: ClassVar[list[str]] = ["dag", "natt"]

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "tariff", "tariff")

    @property
    def native_value(self) -> str | None:
        """Return current tariff: 'dag' or 'natt'."""
        if self.coordinator.data:
            is_day = self.coordinator.data.get("is_day_rate")
            return "dag" if is_day else "natt"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return attributes with schedule info."""
        if self.coordinator.data:
            return {
                "is_day_rate": self.coordinator.data.get("is_day_rate"),
                "dag_periode": "Hverdager 06:00-22:00 (ikke helligdager)",
                "natt_periode": "22:00-06:00, helger og helligdager",
                "bruk": "Bruk denne sensoren til å styre utility_meter tariff-bytte",
            }
        return None


# =============================================================================
# MÅNEDLIG FORBRUK OG KOSTNAD - Device: "Månedlig forbruk"
# =============================================================================


class MaanedligBaseSensor(NettleieBaseSensor):
    """Base class for monthly consumption/cost sensors."""

    _device_group: str = DEVICE_MAANEDLIG

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for Månedlig device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._device_group}")},
            name="Månedlig forbruk",
            manufacturer=MANUFACTURER,
            model=DEFAULT_NAME,
        )


class MaanedligForbrukDagSensor(MaanedligBaseSensor):
    """Sensor for monthly day tariff consumption."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_forbruk_dag", "maanedlig_forbruk_dag")

    @property
    def native_value(self) -> float | None:
        """Return monthly day consumption."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_consumption_dag_kwh"))
        return None


class MaanedligForbrukNattSensor(MaanedligBaseSensor):
    """Sensor for monthly night tariff consumption."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_forbruk_natt", "maanedlig_forbruk_natt")

    @property
    def native_value(self) -> float | None:
        """Return monthly night consumption."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_consumption_natt_kwh"))
        return None


class MaanedligForbrukTotalSensor(MaanedligBaseSensor):
    """Sensor for total monthly consumption."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_forbruk_total", "maanedlig_forbruk_total")

    @property
    def native_value(self) -> float | None:
        """Return total monthly consumption."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_consumption_total_kwh"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return consumption breakdown."""
        if self.coordinator.data:
            dag = self.coordinator.data.get("monthly_consumption_dag_kwh", 0)
            natt = self.coordinator.data.get("monthly_consumption_natt_kwh", 0)
            total = self.coordinator.data.get("monthly_consumption_total_kwh", 0)
            return {
                "dag_kwh": dag,
                "natt_kwh": natt,
                "dag_pct": round(dag / total * 100, 1) if total > 0 else 0.0,
                "natt_pct": round(natt / total * 100, 1) if total > 0 else 0.0,
            }
        return None


class MaanedligNettleieSensor(MaanedligBaseSensor):
    """Sensor for monthly grid rent cost (energiledd + kapasitetsledd)."""

    _attr_entity_registry_enabled_default: bool = False
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _reset_periode: ClassVar[tuple[str, str]] = PERIODE_MAANED
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_nettleie", "maanedlig_nettleie")

    @property
    def native_value(self) -> float | None:
        """Nettleien bokføringen har ført så langt (Ukjent uten kjent fastledd)."""
        if self.coordinator.data and not self._fastledd_ukjent():
            return round(_bokfort_nettleie(self.coordinator.data), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Splitten bokføringen står med.

        `energiledd_dag_kr` og `energiledd_natt_kr` er nettleiens energidel uten
        de offentlige avgiftene, som står for seg i `avgifter_kr`. Det er samme
        splitt som fakturaen bruker. De tre summerer til energileddet i verdien,
        med ett unntak: måneden en lagret fil fra før splitten leses inn bærer
        den gamle summen som åpningsbalanse som ikke kan deles i ettertid.
        """
        data = self.coordinator.data
        if not data:
            return None
        return self._merk_fastledd_ukjent(
            {
                "energiledd_dag_kr": round(_tall(data, "monthly_energiledd_dag_kr"), 2),
                "energiledd_natt_kr": round(_tall(data, "monthly_energiledd_natt_kr"), 2),
                "avgifter_kr": round(_tall(data, "monthly_avgifter_kr"), 2),
                "kapasitetsledd_kr": None
                if self._fastledd_ukjent()
                else round(_tall(data, "monthly_accumulated_cost_kapasitetsledd_kr"), 2),
            }
        )


class MaanedligAvgifterSensor(MaanedligBaseSensor):
    """Sensor for monthly public fees (forbruksavgift + Enova)."""

    _attr_entity_registry_enabled_default: bool = False
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _reset_periode: ClassVar[tuple[str, str]] = PERIODE_MAANED
    _attr_suggested_display_precision: int = 0
    _avgiftssone: str

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_avgifter", "maanedlig_avgifter")
        self._avgiftssone = entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)

    @property
    def native_value(self) -> float | None:
        """Avgiftene bokføringen har ført så langt i måneden."""
        if self.coordinator.data:
            return round(_tall(self.coordinator.data, "monthly_avgifter_kr"), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Fordelingen mellom forbruksavgift og Enova.

        Bokføringen fører de to under ett, siden de følger samme kilowattimer.
        Splitten her er derfor det bokførte beløpet fordelt etter forholdet
        mellom de to satsene. Endres forbruksavgiften midt i en måned (den gjør
        det ved nyttår og 1. april), er splitten et anslag mens totalen er
        eksakt.
        """
        data = self.coordinator.data
        if not data:
            return None
        avgifter_kr = _tall(data, "monthly_avgifter_kr")
        forbruksavgift_sats = _tall(data, "forbruksavgift_inkl_mva")
        enova_sats = _tall(data, "enova_inkl_mva")
        sum_satser = forbruksavgift_sats + enova_sats
        forbruksavgift_kr = round(avgifter_kr * forbruksavgift_sats / sum_satser, 2) if sum_satser else 0.0
        return {
            "forbruksavgift_kr": forbruksavgift_kr,
            "enovaavgift_kr": round(avgifter_kr - forbruksavgift_kr, 2),
            "avgiftssone": self._avgiftssone,
        }


class MaanedligStromstotteSensor(MaanedligBaseSensor):
    """Strømstøtten måneden har bokført, time for time slik den faktureres."""

    _attr_entity_registry_enabled_default: bool = False
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _reset_periode: ClassVar[tuple[str, str]] = PERIODE_MAANED
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_stromstotte", "maanedlig_stromstotte")

    @property
    def native_value(self) -> float | None:
        """Støtten bokføringen har ført så langt i måneden."""
        if self.coordinator.data:
            return round(_tall(self.coordinator.data, "monthly_stromstotte_kr"), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return subsidy info."""
        if self.coordinator.data:
            return {
                "merknad": "Bokført time for time med timens egen spotpris, og stanset ved månedstaket.",
                "stromstotte_per_kwh": self.coordinator.data.get("stromstotte"),
                "har_norgespris": self.coordinator.data.get("har_norgespris"),
            }
        return None


class MaanedligTotalSensor(MaanedligBaseSensor):
    """Sensor for total monthly cost (nettleie + avgifter - strømstøtte)."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _reset_periode: ClassVar[tuple[str, str]] = PERIODE_MAANED
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_total", "maanedlig_total")

    @property
    def native_value(self) -> float | None:
        """Bokført nettleie minus bokført strømstøtte.

        Energileddet i bokføringen inkluderer allerede forbruksavgift og
        Enova-avgift. Avgifter legges IKKE til separat, det ville dobbelttelle
        dem.

        Ukjent når fastleddet er ukjent: en månedstotal uten kapasitetsledd er
        systematisk for lav, og et tall som ser ut som en total skal ikke mangle
        en av de to store postene.
        """
        if self.coordinator.data and not self._fastledd_ukjent():
            return round(
                _bokfort_nettleie(self.coordinator.data)
                - _tall(self.coordinator.data, "monthly_stromstotte_kr"),
                2,
            )
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return cost breakdown."""
        data = self.coordinator.data
        if not data:
            return None
        dag_kwh = _tall(data, "monthly_consumption_dag_kwh")
        natt_kwh = _tall(data, "monthly_consumption_natt_kwh")
        total_kwh = dag_kwh + natt_kwh
        nettleie = _bokfort_nettleie(data)
        stotte = _tall(data, "monthly_stromstotte_kr")
        total_kostnad = nettleie - stotte

        return self._merk_fastledd_ukjent(
            {
                "nettleie_kr": round(nettleie, 2),
                "stromstotte_kr": round(stotte, 2),
                "forbruk_dag_kwh": round(dag_kwh, 1),
                "forbruk_natt_kwh": round(natt_kwh, 1),
                "forbruk_total_kwh": round(total_kwh, 1),
                "vektet_snittpris_kr_per_kwh": round(total_kostnad / total_kwh, 4) if total_kwh > 0 else None,
            }
        )


class MaanedligNorgesprisDifferanseSensor(MaanedligBaseSensor):
    """Sensor for accumulated monthly Norgespris savings/loss."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _reset_periode: ClassVar[tuple[str, str]] = PERIODE_MAANED
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "maanedlig_norgespris_diff", "maanedlig_norgespris_diff")

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_norgespris_diff_kr"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.coordinator.data:
            har_norgespris = self.coordinator.data.get("har_norgespris", False)
            return {
                "sammenligner_med": "spotpris" if har_norgespris else "Norgespris",
                "positiv_betyr": "du sparer med nåværende avtale",
            }
        return None


class MaanedligNorgesprisKompensasjonSensor(MaanedligBaseSensor):
    """Sensor for accumulated monthly Norgespris compensation (norgespris - spot) * kWh."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _reset_periode: ClassVar[tuple[str, str]] = PERIODE_MAANED
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator, entry, "maanedlig_norgespris_kompensasjon", "maanedlig_norgespris_kompensasjon"
        )

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_norgespris_compensation_kr"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.coordinator.data:
            return {
                "formel": "(norgespris - spotpris) * kWh, akkumulert per time",
                "negativ_betyr": "spot dyrere enn norgespris",
            }
        return None


class DagskostnadSensor(MaanedligBaseSensor):
    """Sensor for today's accumulated cost."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _reset_periode: ClassVar[tuple[str, str]] = PERIODE_DOGN
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "daily_cost", "dagskostnad")

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("daily_cost_kr"))
        return None


class AkkumulertKostnadSensor(MaanedligBaseSensor):
    """Akkumulert kostnad for Energy Dashboard (stat_cost).

    Akkumulerer strompris, energiledd og kapasitetsledd separat.
    Kapasitetsledd fordeles lineaert over maneden (tidsbasert),
    slik at manedstotalen matcher fakturaen uavhengig av forbruk.
    """

    _attr_entity_registry_enabled_default: bool = False
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _reset_periode: ClassVar[tuple[str, str]] = PERIODE_MAANED
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "akkumulert_kostnad", "akkumulert_kostnad")

    @property
    def native_value(self) -> float | None:
        """Return accumulated monthly cost (Ukjent uten kjent fastledd)."""
        if self.coordinator.data and not self._fastledd_ukjent():
            return cast("float | None", self.coordinator.data.get("monthly_accumulated_cost_kr"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return cost breakdown."""
        if self.coordinator.data:
            return self._merk_fastledd_ukjent(
                {
                    "strompris_kr": self.coordinator.data.get("monthly_accumulated_cost_strom_kr"),
                    "energiledd_kr": self.coordinator.data.get("monthly_accumulated_cost_energiledd_kr"),
                    "kapasitetsledd_kr": self.coordinator.data.get(
                        "monthly_accumulated_cost_kapasitetsledd_kr"
                    ),
                    "total_kwh": self.coordinator.data.get("monthly_consumption_total_kwh"),
                    "bruk": "Velg som 'Use an entity tracking total costs' i Energy Dashboard",
                }
            )
        return None


class EstimertMaanedskostnadSensor(MaanedligBaseSensor):
    """Sensor for estimated total monthly cost."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "estimated_monthly_cost", "estimert_maanedskostnad")

    @property
    def native_value(self) -> float | None:
        """Estimert total for måneden (Ukjent uten kjent fastledd).

        Den variable delen er det bokføringen har ført så langt, skalert fra
        dagene som er gått til hele måneden. Fastleddet legges på som helt
        månedsbeløp, for det faktureres uansett hvor langt måneden er kommet.
        """
        data = self.coordinator.data
        if not data or self._fastledd_ukjent():
            return None

        now = dt_util.now()
        day_of_month: int = now.day
        dim: int = days_in_month(now)

        # Energileddet i bokføringen inkluderer allerede forbruksavgift + enova.
        variabel_kr = _tall(data, "monthly_accumulated_cost_energiledd_kr") - _tall(
            data, "monthly_stromstotte_kr"
        )
        estimert_variabel = (variabel_kr / day_of_month) * dim
        return round(estimert_variabel + _tall(data, "kapasitetsledd"), 0)


# =============================================================================
# FORRIGE MÅNED - Device: "Forrige måned"
# =============================================================================


class ForrigeMaanedBaseSensor(NettleieBaseSensor):
    """Base class for previous month sensors.

    Snapshotet av en avsluttet måned står stille til neste månedsskifte, og
    byttes da ut i sin helhet. For statistikk-kompilatoren er det en
    nullstilling: uten last_reset bokføres forskjellen mellom to måneders
    snapshot som et delta, og en måned som var lavere enn forrige gir et
    negativt delta i Energy-dashboardet. `last_reset` er derfor starten på
    *inneværende* måned, som er øyeblikket snapshotet ble byttet (4qba).
    """

    _device_group: str = DEVICE_FORRIGE_MAANED
    _reset_periode: ClassVar[tuple[str, str] | None] = PERIODE_MAANED

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for Forrige måned device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._device_group}")},
            name="Forrige måned",
            manufacturer=MANUFACTURER,
            model=DEFAULT_NAME,
        )


class ForrigeMaanedForbrukDagSensor(ForrigeMaanedBaseSensor):
    """Sensor for previous month day tariff consumption."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forrige_maaned_forbruk_dag", "forrige_maaned_forbruk_dag")

    @property
    def native_value(self) -> float | None:
        """Return previous month day consumption."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("previous_month_consumption_dag_kwh"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the month name."""
        if self.coordinator.data:
            return {"maaned": self.coordinator.data.get("previous_month_name")}
        return None


class ForrigeMaanedForbrukNattSensor(ForrigeMaanedBaseSensor):
    """Sensor for previous month night tariff consumption."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forrige_maaned_forbruk_natt", "forrige_maaned_forbruk_natt")

    @property
    def native_value(self) -> float | None:
        """Return previous month night consumption."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("previous_month_consumption_natt_kwh"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the month name."""
        if self.coordinator.data:
            return {"maaned": self.coordinator.data.get("previous_month_name")}
        return None


class ForrigeMaanedForbrukTotalSensor(ForrigeMaanedBaseSensor):
    """Sensor for previous month total consumption."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forrige_maaned_forbruk_total", "forrige_maaned_forbruk_total")

    @property
    def native_value(self) -> float | None:
        """Return previous month total consumption."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("previous_month_consumption_total_kwh"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return consumption breakdown."""
        if self.coordinator.data:
            return {
                "maaned": self.coordinator.data.get("previous_month_name"),
                "dag_kwh": self.coordinator.data.get("previous_month_consumption_dag_kwh"),
                "natt_kwh": self.coordinator.data.get("previous_month_consumption_natt_kwh"),
            }
        return None


class ForrigeMaanedNettleieSensor(ForrigeMaanedBaseSensor):
    """Sensor for previous month grid rent cost."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forrige_maaned_nettleie", "forrige_maaned_nettleie")

    @property
    def native_value(self) -> float | None:
        """Forrige måneds bokførte nettleie, inkludert fullført fastledd."""
        data = self.coordinator.data
        if not data:
            return None
        # Et gammelt Store-arkiv har kWh og satser, men ikke de bokførte
        # komponentene. `previous_month_cost` kan ikke brukes som erstatning:
        # det inneholder også strøm. Ukjent er bedre enn å vise bare
        # kapasitetsleddet eller å gjette med sats * kWh.
        if data.get("previous_month_name") and not data.get("previous_month_bokforte_kroner", False):
            return None
        return round(
            _tall(data, "previous_month_energiledd_dag_kr")
            + _tall(data, "previous_month_energiledd_natt_kr")
            + _tall(data, "previous_month_avgifter_kr")
            + _tall(data, "previous_month_kapasitetsledd")
            - _tall(data, "previous_month_stromstotte_kr"),
            2,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return cost breakdown."""
        data = self.coordinator.data
        if not data:
            return None
        if data.get("previous_month_name") and not data.get("previous_month_bokforte_kroner", False):
            return {"maaned": data.get("previous_month_name"), "bokforte_kroner": False}
        return {
            "maaned": data.get("previous_month_name"),
            "energiledd_dag_kr": round(_tall(data, "previous_month_energiledd_dag_kr"), 2),
            "energiledd_natt_kr": round(_tall(data, "previous_month_energiledd_natt_kr"), 2),
            "avgifter_kr": round(_tall(data, "previous_month_avgifter_kr"), 2),
            "stromstotte_kr": round(_tall(data, "previous_month_stromstotte_kr"), 2),
            "kapasitetsledd_kr": data.get("previous_month_kapasitetsledd", 0),
            "kapasitetstrinn": data.get("previous_month_kapasitetstrinn", ""),
            "snitt_topp_3_kw": data.get("previous_month_avg_top_3_kw", 0.0),
            "norgespris_differanse_kr": data.get("previous_month_norgespris_diff_kr", 0.0),
            "bokforte_kroner": True,
        }


class ForrigeMaanedToppforbrukSensor(ForrigeMaanedBaseSensor):
    """Sensor for previous month top 3 power consumption average."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement: str = "kW"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 2
    # En MEASUREMENT-sensor akkumulerer ingenting, så last_reset hører ikke
    # hjemme her selv om de andre i gruppen har den.
    _reset_periode: ClassVar[tuple[str, str] | None] = None

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forrige_maaned_toppforbruk", "forrige_maaned_toppforbruk")

    @property
    def native_value(self) -> float | None:
        """Return previous month average top 3 power."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("previous_month_avg_top_3_kw"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return top 3 days breakdown."""
        if self.coordinator.data:
            top_3 = self.coordinator.data.get("previous_month_top_3", {})
            attrs: dict[str, Any] = {"maaned": self.coordinator.data.get("previous_month_name")}
            sorted_entries = sorted(top_3.items(), key=lambda x: x[1].kw, reverse=True)
            for i, (date, entry) in enumerate(sorted_entries, 1):
                attrs[f"topp_{i}_dato"] = date
                attrs[f"topp_{i}_kw"] = round(entry.kw, 2)
                attrs[f"topp_{i}_time"] = entry.hour
            return attrs
        return None


class ForrigeMaanedNorgesprisKompensasjonSensor(ForrigeMaanedBaseSensor):
    """Sensor for previous month Norgespris compensation."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            entry,
            "forrige_maaned_norgespris_kompensasjon",
            "forrige_maaned_norgespris_kompensasjon",
        )

    @property
    def native_value(self) -> float | None:
        """Return previous month Norgespris compensation."""
        if self.coordinator.data:
            return cast(
                "float | None", self.coordinator.data.get("previous_month_norgespris_compensation_kr")
            )
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the month name."""
        if self.coordinator.data:
            return {
                "maaned": self.coordinator.data.get("previous_month_name"),
                "formel": "(norgespris - spotpris) * kWh, akkumulert per time",
            }
        return None


# =============================================================================
# EKSPORT (PLUSSKUNDER MED SOLCELLER) - Device: "Eksport"
# =============================================================================


class EksportBaseSensor(NettleieBaseSensor):
    """Base class for export sensors."""

    _device_group: str = DEVICE_EKSPORT
    _attr_entity_registry_enabled_default: bool = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for Eksport device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._device_group}")},
            name="Eksport (solceller)",
            manufacturer=MANUFACTURER,
            model=DEFAULT_NAME,
        )

    @property
    def available(self) -> bool:
        """Only available when export sensor is configured."""
        if not self.coordinator.data:
            return False
        return bool(self.coordinator.data.get("eksport_konfigurert", False))


class MaanedligEksportKwhSensor(EksportBaseSensor):
    """Sensor for monthly exported energy."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_eksport_kwh", "maanedlig_eksport_kwh")

    @property
    def native_value(self) -> float | None:
        """Return monthly exported kWh."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_export_kwh"))
        return None


class MaanedligEksportInntektSensor(EksportBaseSensor):
    """Sensor for monthly export revenue."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _reset_periode: ClassVar[tuple[str, str]] = PERIODE_MAANED
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_eksport_inntekt", "maanedlig_eksport_inntekt")

    @property
    def native_value(self) -> float | None:
        """Return monthly export revenue."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_export_revenue_kr"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return export details."""
        if self.coordinator.data:
            kwh = self.coordinator.data.get("monthly_export_kwh", 0)
            revenue = self.coordinator.data.get("monthly_export_revenue_kr", 0)
            return {
                "eksport_kwh": kwh,
                "snitt_spotpris": round(revenue / kwh, 4) if kwh > 0 else None,
                "note": "Eksport betales til spotpris, ingen nettleie, avgifter eller stromstotte",
            }
        return None


class MaanedligNettokostnadSensor(EksportBaseSensor):
    """Sensor for net monthly cost (consumption - export revenue)."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _reset_periode: ClassVar[tuple[str, str]] = PERIODE_MAANED
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_nettokostnad", "maanedlig_nettokostnad")

    @property
    def native_value(self) -> float | None:
        """Return net cost (consumption cost minus export revenue)."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_net_cost_kr"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return cost breakdown."""
        if self.coordinator.data:
            return {
                "forbrukskostnad_kr": self.coordinator.data.get("monthly_cost_kr"),
                "eksportinntekt_kr": self.coordinator.data.get("monthly_export_revenue_kr"),
            }
        return None


class ForrigeMaanedEksportKwhSensor(EksportBaseSensor):
    """Sensor for previous month exported energy."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_suggested_display_precision: int = 1
    # Snapshot av en avsluttet måned, byttes ved månedsskiftet. Se
    # ForrigeMaanedBaseSensor for hvorfor last_reset er inneværende månedsstart.
    _reset_periode: ClassVar[tuple[str, str]] = PERIODE_MAANED

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forrige_maaned_eksport_kwh", "forrige_maaned_eksport_kwh")

    @property
    def native_value(self) -> float | None:
        """Return previous month exported kWh."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("previous_month_export_kwh"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the month name."""
        if self.coordinator.data:
            return {"maaned": self.coordinator.data.get("previous_month_name")}
        return None


class ForrigeMaanedEksportInntektSensor(EksportBaseSensor):
    """Sensor for previous month export revenue."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_suggested_display_precision: int = 0
    # Samme som eksport-kWh-en over: snapshot, ikke akkumulator.
    _reset_periode: ClassVar[tuple[str, str]] = PERIODE_MAANED

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, "forrige_maaned_eksport_inntekt", "forrige_maaned_eksport_inntekt"
        )

    @property
    def native_value(self) -> float | None:
        """Return previous month export revenue."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("previous_month_export_revenue_kr"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the month name and net cost."""
        if self.coordinator.data:
            return {
                "maaned": self.coordinator.data.get("previous_month_name"),
                "nettokostnad_kr": self.coordinator.data.get("previous_month_net_cost_kr"),
            }
        return None
