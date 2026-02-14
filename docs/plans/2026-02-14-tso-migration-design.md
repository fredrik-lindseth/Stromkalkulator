# Automatisk TSO-migrering ved fusjon av nettselskaper

## Bakgrunn

Nettselskaper i Norge fusjonerer jevnlig. Brukere som har konfigurert integrasjonen med et selskap som fusjoneres, må migreres automatisk til det nye selskapet uten tap av data eller manuell rekonfigurering.

## Kjente fusjoner

- Skiakernett → Vevig
- Norgesnett → Glitre Nett

## Design

### Datastruktur (tso.py)

```python
@dataclass(frozen=True)
class TSOFusjon:
    gammel: str
    ny: str

TSO_MIGRATIONS: Final[list[TSOFusjon]] = [
    TSOFusjon(gammel="skiakernett", ny="vevig"),
    TSOFusjon(gammel="norgesnett", ny="glitre"),
]
```

Gamle TSO-oppføringer fjernes fra `TSO_LIST` — de finnes kun i `TSO_MIGRATIONS`.

### Migreringsfunksjon (__init__.py)

Kjører i `async_setup_entry`, før coordinator opprettes:

1. Les `entry.data["tso"]`
2. Sjekk om nøkkelen finnes som `gammel` i `TSO_MIGRATIONS`
3. Hvis ja:
   - Oppdater config entry med ny TSO-nøkkel via `async_update_entry`
   - Flytt `.storage`-fil fra `stromkalkulator_{gammel}` til `stromkalkulator_{ny}`
   - Opprett en HA repair issue
   - Logg info-melding
4. Hvis nei: fortsett normalt

### Repair issue

Bruker `homeassistant.helpers.issue_registry.async_create_issue`.

Tekst: "{gammelt navn} er nå en del av {nytt navn}. Integrasjonen er automatisk oppdatert, og forbruksdata og historikk er bevart."

### Storage-migrering

Persistent storage bruker nøkkel `f"{DOMAIN}_{tso_id}"`. Ved migrering flyttes/renames filen slik at månedsdata (forbruk, topp-3) bevares.

### Dataflyt

```
Oppstart → async_setup_entry
  → Les entry.data["tso"]
  → Finnes i TSO_MIGRATIONS?
    → Nei: fortsett normalt
    → Ja:
      → Oppdater entry.data["tso"] til ny nøkkel
      → Flytt .storage-fil
      → Opprett repair issue
      → Logg info
  → Opprett coordinator (med ny TSO)
  → Sett opp sensorer
```

## Beslutninger

- **Tilnærming B** (dict-sjekk ved oppstart) valgt over HA VERSION-mekanisme — fusjoner er data-migreringer, ikke schema-endringer
- **Dataclass** `TSOFusjon` for selvdokumenterende kode
- **Bevar historikk** ved å flytte storage-fil
- **Repair issue** for brukersynlighet
