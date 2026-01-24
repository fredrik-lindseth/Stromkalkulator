# Fakturasammenligning - Referansedata fra BKK

Dette er anonymiserte fakturaer fra BKK (Bergen) brukt for å validere integrasjonens beregninger.

## Fakturaer

- [Oktober 2025](BKK_Faktura_oktober_2025.md)
- [November 2025](BKK_Faktura_november_2025.md)
- [Desember 2025](BKK_Faktura_desember_2025.md)

## Sammendrag

### Oktober 2025
| Linje                | Forbruk      | Pris           | Sum           |
|----------------------|--------------|----------------|---------------|
| Energiledd dag       | 707.09 kWh   | 35.963 øre/kWh | 254.29 kr     |
| Energiledd natt/helg | 536.117 kWh  | 23.738 øre/kWh | 127.26 kr     |
| Midlert. strømstønad | 115.661 kWh  | -6.188 øre/kWh | -7.16 kr      |
| Kapasitet 5-10 kW    | 31 dager     | 415 kr/mnd     | 415.00 kr     |
| Forbruksavgift       | 1243.207 kWh | 15.662 øre/kWh | 194.72 kr     |
| Enovaavgift          | 1243.207 kWh | 1.25 øre/kWh   | 15.54 kr      |
| **Sum**              |              |                | **999.65 kr** |

### November 2025 (Faktura november_2025)
| Linje                | Forbruk      | Pris            | Sum           |
|----------------------|--------------|-----------------|---------------|
| Energiledd dag       | 709.157 kWh  | 35.963 øre/kWh  | 255.03 kr     |
| Energiledd natt/helg | 765.349 kWh  | 23.738 øre/kWh  | 181.68 kr     |
| Midlert. strømstønad | 933.128 kWh  | -43.381 øre/kWh | -404.80 kr    |
| Kapasitet 5-10 kW    | 30 dager     | 415 kr/mnd      | 415.00 kr     |
| Forbruksavgift       | 1474.506 kWh | 15.662 øre/kWh  | 230.94 kr     |
| Enovaavgift          | 1474.506 kWh | 1.25 øre/kWh    | 18.43 kr      |
| **Sum**              |              |                 | **696.28 kr** |

### Desember 2025 (Faktura desember_2025)
| Linje                | Forbruk      | Pris            | Sum            |
|----------------------|--------------|-----------------|----------------|
| Energiledd dag       | 667.422 kWh  | 35.963 øre/kWh  | 240.03 kr      |
| Energiledd natt/helg | 887.299 kWh  | 23.738 øre/kWh  | 210.63 kr      |
| Midlert. strømstønad | 1107.173 kWh | -11.054 øre/kWh | -122.39 kr     |
| Kapasitet 5-10 kW    | 31 dager     | 415 kr/mnd      | 415.00 kr      |
| Forbruksavgift       | 1554.721 kWh | 15.662 øre/kWh  | 243.50 kr      |
| Enovaavgift          | 1554.721 kWh | 1.25 øre/kWh    | 19.43 kr       |
| **Sum**              |              |                 | **1006.20 kr** |

## Viktige observasjoner

### Priser fra fakturaen (2025)
- **Energiledd dag**: 35.963 øre/kWh (eks. avgifter)
- **Energiledd natt/helg**: 23.738 øre/kWh (eks. avgifter)
- **Forbruksavgift**: 15.662 øre/kWh (2025 vintersats for Sør-Norge)
- **Enovaavgift**: 1.25 øre/kWh (2025-sats)
- **Kapasitet 5-10 kW**: 415 kr/mnd

### Strømstøtte
Strømstønaden beregnes for timer hvor spotpris er over terskel:
- **Terskel 2025**: 70 øre/kWh (91.25 øre inkl. mva)
- **Dekningsgrad**: 90%
- kWh i kolonnen viser forbruk i timer OVER terskelen

## Home Assistant oppsett for akkumulering

For å sammenligne med fakturaen trenger du å akkumulere kWh per kategori per måned.

### Utility Meter eksempel (configuration.yaml)

```yaml
utility_meter:
  # Energiledd dag (kWh forbrukt på dagtid)
  energiledd_dag_maaned:
    source: sensor.strom_forbruk_kwh  # Din kWh-sensor
    cycle: monthly
    tariffs:
      - dag
      - natt

  # Strømstøtte-berettiget forbruk
  stromstotte_kwh_maaned:
    source: sensor.strom_forbruk_kwh
    cycle: monthly
```

### Template sensor for å beregne kostnad

```yaml
template:
  - sensor:
      - name: "Energiledd dag kostnad måned"
        unit_of_measurement: "kr"
        state: >
          {{ (states('sensor.energiledd_dag_maaned_dag') | float(0)) 
             * (states('sensor.stromkalkulator_energiledd_dag') | float(0)) }}
```

### Automatisering for tariff-bytte

```yaml
automation:
  - alias: "Sett energiledd tariff"
    trigger:
      - platform: state
        entity_id: sensor.stromkalkulator_energiledd
    action:
      - service: utility_meter.select_tariff
        target:
          entity_id: utility_meter.energiledd_dag_maaned
        data:
          tariff: >
            {% if state_attr('sensor.stromkalkulator_energiledd', 'is_day_rate') %}
              dag
            {% else %}
              natt
            {% endif %}
```

## Sensorer fra integrasjonen

Etter oppdatering har du disse sensorene for fakturasammenligning:

| Sensor                                     | Beskrivelse               | Enhet   |
|--------------------------------------------|---------------------------|---------|
| `sensor.stromkalkulator_energiledd_dag`    | Energiledd dag-sats       | NOK/kWh |
| `sensor.stromkalkulator_energiledd_natt`   | Energiledd natt-sats      | NOK/kWh |
| `sensor.stromkalkulator_forbruksavgift`    | Forbruksavgift            | NOK/kWh |
| `sensor.stromkalkulator_enovaavgift`       | Enovaavgift               | NOK/kWh |
| `sensor.stromkalkulator_kapasitetstrinn`   | Kapasitetsledd            | kr/mnd  |
| `sensor.stromkalkulator_stromstotte`       | Strømstøtte per kWh       | NOK/kWh |
| `sensor.stromkalkulator_stromstotte_aktiv` | Ja/Nei om støtte er aktiv | -       |

### Attributter for fakturasammenligning

Hver sensor har attributter som viser pris eks. mva for enklere sammenligning med fakturaen:
- `eks_mva` / `eks_avgifter_mva`: Pris uten mva/avgifter
- `inkl_mva`: Pris med mva
- `ore_per_kwh_eks_mva`: Pris i øre (som på fakturaen)
