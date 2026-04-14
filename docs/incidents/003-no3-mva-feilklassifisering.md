# Incident 003: NO3 feilklassifisert som mva-fritak

**Dato:** april 2026
**Status:** Under utredning

## Symptomer

Under rutinemessig verifisering av DSO-priser mot offisielle kilder ble det oppdaget at koden behandler alle NO3-nettselskap som mva-frie. De fleste NO3-selskap er i Trøndelag og Møre og Romsdal, som betaler 25% mva.

## Rotårsak

### Feil: NO3 → mva-fritak er feil

`const.py` mapper prisområde NO3 til avgiftssone `nord_norge` (mva-fritak):

```python
def get_default_avgiftssone(prisomrade: str) -> str:
    if prisomrade in ("NO3", "NO4"):
        return AVGIFTSSONE_NORD_NORGE
    return AVGIFTSSONE_STANDARD
```

Merverdiavgiftsloven § 6-6 er klar:

> "Omsetning av elektrisk kraft og energi levert fra alternative energikilder til husholdningsbruk i fylkene Finnmark, Troms og Nordland, er fritatt for merverdiavgift."

Mva-fritak er **fylkesbasert**, ikke prisområde-basert. NO3 dekker:

| Område i NO3 | Fylke | Mva-fritak? |
|---|---|---|
| Helgeland (sørligste del) | Nordland | Ja |
| Nord-Trøndelag | Trøndelag | **Nei** |
| Sør-Trøndelag | Trøndelag | **Nei** |
| Nordmøre | Møre og Romsdal | **Nei** |
| Romsdal | Møre og Romsdal | **Nei** |
| Nord-Østerdal | Innlandet | **Nei** |

Kun en liten del av NO3 (Helgeland/Bindal) har mva-fritak. De aller fleste NO3-kunder betaler 25% mva.

NO4 er derimot korrekt: dekker Nordland (utenom Helgeland), Troms og Finnmark, som alle har mva-fritak.

### Konsekvenser

Avgiftssone brukes til:
- **Strømstøtte-terskel**: 96,25 øre inkl. mva for `standard`, 77 øre for `nord_norge`
- **Norgespris**: 50 øre inkl. mva for `standard`, 40 øre for `nord_norge`

NO3-kunder i Trøndelag/Møre og Romsdal som betaler mva, får feil strømstøtte og Norgespris.

### Feilaktig "fix" av Elinett

Under prisverifiseringen ble Elinett feilaktig antatt å være i Helgeland (Nordland). Elinett betjener Aukra, Hustadvika, Gjemnes og Molde i Møre og Romsdal (kilde: Statnett Områdeplan Midt 2025). Prisene ble midlertidig endret fra 38,46/28,46 (inkl. mva, korrekt) til 36,43/26,43 (eks. mva, feil). Revertert umiddelbart etter oppdagelse.

## Berørte DSO-er

### NO3-selskap som FEIL får mva-fritak (skal ha standard/25% mva)

| DSO | Plassering | Fylke |
|---|---|---|
| tensio_tn | Nord-Trøndelag | Trøndelag |
| tensio_ts | Sør-Trøndelag | Trøndelag |
| elinett | Molde-området | Møre og Romsdal |
| mellom | Romsdal/Nordmøre | Møre og Romsdal |
| nettselskapet | Namdal | Trøndelag |
| fjellnett | Oppdal | Trøndelag |
| klive | Kristiansund | Møre og Romsdal |
| nordvest_nett | Sunnmøre | Møre og Romsdal |
| romsdalsnett | Romsdal | Møre og Romsdal |
| s_nett | Surnadal | Møre og Romsdal |
| straumen_nett | Inderøy | Trøndelag |
| vevig | Nordmøre/Sunndal | Møre og Romsdal |
| viermie | Røros | Trøndelag |
| netera | Namsos | Trøndelag |

### NO3-selskap som KORREKT skal ha mva-fritak

| DSO | Plassering | Fylke |
|---|---|---|
| bindal_kraftnett | Bindal | Nordland |

Bindal er i Nordland og har mva-fritak, men prisene i koden er beregnet MED 25% mva (dobbel mva-feil i kommentarene + faktiske verdier). Trenger korrigering.

### Energiledd-verdier: Faktisk status

De fleste NO3 DSO-er har energiledd-verdier hentet direkte fra nettsider som oppgir priser "inkl. mva". Siden disse selskapene faktisk ER i mva-sonen, er de lagrede verdiene korrekte som de er. Problemet er avgiftssone-klassifiseringen, ikke energileddet.

Unntak der energileddet er feil:
- **bindal_kraftnett**: Har 43,04/36,79 (inkl. mva via dobbel mva-beregning), men Bindal har mva-fritak. Bør være eks. mva. I tillegg er dette 2025-priser.

## Foreslått løsning

### Steg 1: Endre NO3-default til standard

```python
def get_default_avgiftssone(prisomrade: str) -> str:
    if prisomrade == "NO4":  # Kun NO4 default til nord_norge
        return AVGIFTSSONE_NORD_NORGE
    return AVGIFTSSONE_STANDARD
```

### Steg 2: Per-DSO avgiftssone-override

Legg til `avgiftssone`-felt i `DSOEntry` for unntak:

```python
class DSOEntry(TypedDict):
    # ...eksisterende felter...
    avgiftssone: NotRequired[str]  # Overstyrer default fra prisomrade
```

Bruk for:
- `bindal_kraftnett`: `"avgiftssone": "nord_norge"` (Nordland i NO3)
- Eventuelle andre grensetilfeller

### Steg 3: Fiks Bindal Kraftnett

Rett energiledd til eks. mva-verdier og oppdater til 2026-priser når tilgjengelig.

### Steg 4: Oppdater config flow

La brukeren velge avgiftssone ved oppsett, med default basert på DSO. Vis tydelig at det handler om fylke, ikke prisområde.

### Steg 5: Oppdater AVGIFTSSONE_OPTIONS

Fra: "Nord-Norge - NO3, NO4"
Til: "Nord-Norge - Nordland, Troms, Finnmark (mva-fritak)"

## Lærdom

### 1. Prisområde er ikke avgiftssone

NO1-NO5 er markedsområder for kraftbørsen, definert av Statnett basert på nettkapasitet. Mva-fritak er definert i skattelovgivningen basert på fylkesgrenser. NO4 overlapper tilfeldigvis med mva-fritak-fylkene, men NO3 gjør det ikke.

### 2. Én DSO kan ha en uventet geografisk plassering

Elinett ble antatt å være i Helgeland (Nordland) basert på en feil kommentar i koden. Statnetts Områdeplan Midt bekrefter at Elinett er i Møre og Romsdal. Alltid verifiser geografi mot offisielle kilder.

### 3. "Nord-Norge" er tvetydig

Begrepet "Nord-Norge" betyr ulike ting i ulike kontekster:
- Geografisk: Nordland, Troms, Finnmark
- Skattemessig (mva-fritak): Nordland, Troms, Finnmark (§ 6-6)
- Kraftmarked: NO4 (+ deler av Nordland i NO3)
- Forbruksavgift: Egen sats for NO3+NO4 (fra 2026: lik sats overalt)

Koden blandet sammen kraftmarked-definisjonen med skattedefinisjonen.

## Kilder

- [Merverdiavgiftsloven § 6-6](https://lovdata.no/dokument/NL/lov/2009-06-19-58/KAPITTEL_6)
- [Skatteetaten MVA-håndboken § 6-6](https://www.skatteetaten.no/rettskilder/type/handboker/merverdiavgiftshandboken/gjeldende/M-6/M-6-6/)
- [Statnett Områdeplan Midt 2025](https://www.statnett.no/globalassets/for-aktorer-i-kraftsystemet/planer-og-analyser/omradeplaner/midt/omradeplan-midt-2025.pdf) (bekrefter Elinett i Midt/Møre og Romsdal)
