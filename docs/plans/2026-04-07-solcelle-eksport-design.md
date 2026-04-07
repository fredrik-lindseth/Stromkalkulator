# Design: Solcelle-eksport / salg av strom tilbake til nett

**Dato:** 2026-04-07
**Bakgrunn:** Plusskunder med solceller vil se inntekt fra eksport, sammenligne med/uten Norgespris, og se nettokostnad.

## Regler for stromeksport i Norge

- Plusskunder mottar spotpris fra stromleverandor for eksportert strom
- Ingen nettleie pa eksportert kraft
- Ingen forbruksavgift eller Enova-avgift pa eksport
- Ingen stromstotte pa eksport
- Norgespris gjelder ikke eksport — alltid spotpris uavhengig av avtale
- Sammenligning: "Jeg valgte bort Norgespris for a selge til spot. Lønner det seg?"

## Ny konfigurasjon

Nytt valgfritt felt: `CONF_EXPORT_POWER_SENSOR` ("export_power_sensor")

- Valgfri sensor som maler eksport-effekt i watt (W)
- Konfigureres i config flow (sensors-step) og options flow
- Nar sensoren ikke er konfigurert: alle eksport-sensorer returnerer None

## Nye akkumulatorer i coordinator

### `_monthly_export_kwh`

Akkumulerer eksportert energi per oppdatering:
```
export_energy_kwh = export_power_kw * elapsed_hours
_monthly_export_kwh += export_energy_kwh
```

Samme riemann-sum-logikk som forbruk. Clamper elapsed_hours til 0-6 min.
Nullstilles ved manedsskifte, arkiveres til `_previous_month_export_kwh`.

### `_monthly_export_revenue`

Akkumulerer inntekt fra eksport:
```
_monthly_export_revenue += spot_price * export_energy_kwh
```

Spotpris brukes direkte — ingen avgifter, ingen stotte.
Nullstilles ved manedsskifte, arkiveres til `_previous_month_export_revenue`.

## Nye datanokler i coordinator-returverdien

```python
"monthly_export_kwh": round(self._monthly_export_kwh, 3),
"monthly_export_revenue_kr": round(self._monthly_export_revenue, 2),
"previous_month_export_kwh": round(self._previous_month_export_kwh, 3),
"previous_month_export_revenue_kr": round(self._previous_month_export_revenue, 2),
"eksport_konfigurert": self.export_power_sensor is not None,
```

## Nye sensorer

Alle i ny device-gruppe `DEVICE_EKSPORT = "eksport"`.
Alle disabled by default (`_attr_entity_registry_enabled_default = False`).

### 1. MaanedligEksportKwhSensor

- Manedlig eksportert energi (kWh)
- `SensorDeviceClass.ENERGY`, `SensorStateClass.TOTAL_INCREASING`
- Datanokkel: `monthly_export_kwh`

### 2. MaanedligEksportInntektSensor

- Manedlig inntekt fra salg (kr)
- `SensorDeviceClass.MONETARY`, `SensorStateClass.TOTAL`
- Datanokkel: `monthly_export_revenue_kr`
- Attributter: snitt-spotpris for eksport (`revenue / kwh`)

### 3. MaanedligNettokostnadSensor

- Netto manedskostnad = forbrukskostnad - eksportinntekt
- `SensorDeviceClass.MONETARY`, `SensorStateClass.TOTAL`
- Gjenbruker `daily_cost_kr`-akkumulering (manedlig) og `monthly_export_revenue_kr`
- NB: Bruker eksisterende manedlig total (dagskostnad-sum gjennom maneden) minus eksportinntekt.
  For enkelhet: vi summerer `daily_cost` over hele maneden via en ny akkumulator `_monthly_cost`.

### 4. ForrigeMaanedEksportKwhSensor

- Forrige maneds eksportert energi
- Datanokkel: `previous_month_export_kwh`

### 5. ForrigeMaanedEksportInntektSensor

- Forrige maneds eksportinntekt
- Datanokkel: `previous_month_export_revenue_kr`

## Sammenligning med Norgespris (eksisterende sensor dekker dette)

Sammenligningen "med vs uten Norgespris" handler kun om forbrukssiden:
- Med Norgespris: forbruk koster 50 ore/kWh, eksport gir spot
- Uten Norgespris: forbruk koster spot-stromstotte, eksport gir spot

Differansen er kun pa forbruk. Eksisterende `MaanedligNorgesprisDifferanseSensor` dekker allerede
denne sammenligningen. Nettokostnad-sensoren gir det totale bildet.

## Storage / persistens

Nye felter i `_save_stored_data` / `_load_stored_data`:
- `monthly_export_kwh`
- `monthly_export_revenue`
- `previous_month_export_kwh`
- `previous_month_export_revenue`
- `monthly_cost`

## Berørte filer

- `const.py` — `CONF_EXPORT_POWER_SENSOR`, `DEVICE_EKSPORT`
- `coordinator.py` — akkumulatorer, eksport-beregning, storage, manedsskifte
- `sensor.py` — 5 nye sensor-klasser
- `config_flow.py` — valgfri eksport-sensor i sensors-step og options
- `strings.json`, `translations/nb.json`, `translations/en.json` — nye labels
- `tests/test_eksport.py` — tester for eksport-funksjonalitet
