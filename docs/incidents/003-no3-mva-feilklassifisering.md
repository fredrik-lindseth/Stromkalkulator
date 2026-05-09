# Incident 003: NO3 feilklassifisert som mva-fritak

**Dato:** april 2026
**Status:** under utredning

## Symptomer

Under verifisering av DSO-priser ble det oppdaget at koden behandler alle NO3-nettselskap som mva-frie. De fleste NO3-selskap er i Trøndelag og Møre og Romsdal, som betaler 25% mva.

## Rotårsak

`const.py` mapper prisområde NO3 til avgiftssone `nord_norge` (mva-fritak):

```python
def get_default_avgiftssone(prisomrade: str) -> str:
    if prisomrade in ("NO3", "NO4"):
        return AVGIFTSSONE_NORD_NORGE
    return AVGIFTSSONE_STANDARD
```

Merverdiavgiftsloven § 6-6 er fylkesbasert, ikke prisområde-basert: fritak gjelder kun husholdningsbruk i Finnmark, Troms og Nordland. NO3 dekker:

| Område                    | Fylke           | Mva-fritak? |
| ------------------------- | --------------- | ----------- |
| Helgeland (sørligste del) | Nordland        | Ja          |
| Nord-Trøndelag            | Trøndelag       | Nei         |
| Sør-Trøndelag             | Trøndelag       | Nei         |
| Nordmøre                  | Møre og Romsdal | Nei         |
| Romsdal                   | Møre og Romsdal | Nei         |
| Nord-Østerdal             | Innlandet       | Nei         |

Kun en liten del av NO3 (Helgeland/Bindal) har mva-fritak. NO4 derimot er korrekt: dekker Nordland (utenom Helgeland), Troms og Finnmark.

## Konsekvenser

Avgiftssone styrer:

- Strømstøtte-terskel: 96,25 øre inkl. mva for `standard`, 77 øre for `nord_norge`
- Norgespris: 50 øre inkl. mva for `standard`, 40 øre for `nord_norge`

NO3-kunder i Trøndelag/Møre og Romsdal får feil strømstøtte og Norgespris.

### Sidekommentar: Elinett

Elinett ble feilaktig antatt å være i Helgeland (Nordland) under verifiseringen. Statnetts Områdeplan Midt 2025 bekrefter Elinett betjener Aukra, Hustadvika, Gjemnes og Molde i Møre og Romsdal. Prisene ble midlertidig endret til eks. mva-verdier og umiddelbart revertert.

## Berørte DSO-er

NO3 som FEIL får mva-fritak (skal være standard/25%):

| DSO            | Plassering       | Fylke           |
| -------------- | ---------------- | --------------- |
| tensio_tn      | Nord-Trøndelag   | Trøndelag       |
| tensio_ts      | Sør-Trøndelag    | Trøndelag       |
| elinett        | Molde-området    | Møre og Romsdal |
| mellom         | Romsdal/Nordmøre | Møre og Romsdal |
| nettselskapet  | Namdal           | Trøndelag       |
| fjellnett      | Oppdal           | Trøndelag       |
| klive          | Kristiansund    | Møre og Romsdal |
| nordvest_nett  | Sunnmøre         | Møre og Romsdal |
| romsdalsnett   | Romsdal          | Møre og Romsdal |
| s_nett         | Surnadal         | Møre og Romsdal |
| straumen_nett  | Inderøy          | Trøndelag       |
| vevig          | Nordmøre/Sunndal | Møre og Romsdal |
| viermie        | Røros            | Trøndelag       |
| netera         | Namsos           | Trøndelag       |

NO3 som KORREKT skal ha mva-fritak:

| DSO              | Plassering | Fylke    |
| ---------------- | ---------- | -------- |
| bindal_kraftnett | Bindal     | Nordland |

`bindal_kraftnett` har 43,04/36,79 (lagret som inkl. mva via dobbel mva-beregning), men Bindal har mva-fritak. Bør være eks. mva. 2025-priser, må også oppdateres.

### Energiledd-status

De fleste NO3 DSO-er har energiledd hentet fra nettsider som oppgir priser inkl. mva. Selskapene ER i mva-sonen, så lagrede verdier er korrekte. Problemet er avgiftssone-klassifiseringen, ikke energileddet.

## Foreslått løsning

1. Endre NO3-default til standard:

```python
def get_default_avgiftssone(prisomrade: str) -> str:
    if prisomrade == "NO4":
        return AVGIFTSSONE_NORD_NORGE
    return AVGIFTSSONE_STANDARD
```

2. Per-DSO `avgiftssone`-felt i `DSOEntry` for unntak (Bindal: `"avgiftssone": "nord_norge"`).
3. Fiks Bindal Kraftnett: rett energiledd til eks. mva, oppdater til 2026-priser.
4. Config flow: la brukeren velge avgiftssone, default basert på DSO. Vis at det handler om fylke, ikke prisområde.
5. Oppdater AVGIFTSSONE_OPTIONS-tekst fra "Nord-Norge - NO3, NO4" til "Nord-Norge - Nordland, Troms, Finnmark (mva-fritak)".

## Lærdom

1. **Prisområde er ikke avgiftssone.** NO1-NO5 er Statnetts markedsområder basert på nettkapasitet. Mva-fritak er fylkesbasert i skattelovgivningen. NO4 overlapper tilfeldig med fritaksfylkene, NO3 gjør det ikke.
2. **Verifiser geografi mot offisielle kilder.** Elinett ble antatt å være i Helgeland basert på en feil kommentar i koden.
3. **"Nord-Norge" er tvetydig.** Geografisk: Nordland/Troms/Finnmark. Mva-fritak: samme. Kraftmarked: NO4 + deler av Nordland i NO3. Forbruksavgift: lik sats overalt fra 2026.

## Kilder

- [Merverdiavgiftsloven § 6-6](https://lovdata.no/dokument/NL/lov/2009-06-19-58/KAPITTEL_6)
- [Skatteetaten MVA-håndboken § 6-6](https://www.skatteetaten.no/rettskilder/type/handboker/merverdiavgiftshandboken/gjeldende/M-6/M-6-6/)
- [Statnett Områdeplan Midt 2025](https://www.statnett.no/globalassets/for-aktorer-i-kraftsystemet/planer-og-analyser/omradeplaner/midt/omradeplan-midt-2025.pdf)
