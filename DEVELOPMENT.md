# Utvikling

## Testdata for toppforbruk

For å teste kapasitetstrinn-beregninger kan du opprette en lagringsfil manuelt på HA-serveren.

### Opprett testdata via SSH

```bash
cat > /config/.storage/nettleie_bkk << 'EOF'
{
  "version": 1,
  "data": {
    "daily_max_power": {
      "2026-01-17": 5.2,
      "2026-01-18": 3.8,
      "2026-01-19": 4.5
    },
    "current_month": 1
  }
}
EOF
```

**Merk:** Endre `nettleie_bkk` til din TSO-id (f.eks. `nettleie_tensio`, `nettleie_elvia`).

### Felter

| Felt | Beskrivelse |
|------|-------------|
| `daily_max_power` | Dict med dato (YYYY-MM-DD) → maks kW |
| `current_month` | Måned (1-12) - data nullstilles ved ny måned |

### Eksempel: Test ulike kapasitetstrinn

**Trinn 1 (0-2 kW):**
```json
"daily_max_power": {
  "2026-01-17": 1.5,
  "2026-01-18": 1.8,
  "2026-01-19": 1.2
}
```

**Trinn 3 (5-10 kW):**
```json
"daily_max_power": {
  "2026-01-17": 7.5,
  "2026-01-18": 8.2,
  "2026-01-19": 6.8
}
```

### Etter endring

Restart Home Assistant for å laste inn de nye verdiene.
