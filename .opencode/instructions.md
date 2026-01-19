# Git Instructions

## Commits

- Skriv commit-meldinger på norsk
- Ikke push automatisk etter commit - spør først
- Bruk kort, beskrivende tittel (maks 50 tegn)

## Commit body

Inkluder alltid en beskrivende body som forklarer:

1. **Hvorfor**: Hva var problemet eller behovet som trigget denne endringen?
2. **Hva**: Hva er gjort for å løse problemet?
3. **Kontekst**: Relevant bakgrunnsinformasjon som kan være nyttig ved senere `git log`

### Eksempel

```
Fiks feil i total_price beregning

Problemet var at total_price ble brukt før variabelen var definert,
som ga "UnboundLocalError: cannot access local variable" i Home Assistant.

Løsning: Flyttet beregningen av total_price til før den brukes i
kroner_spart_per_kwh-beregningen.
```
