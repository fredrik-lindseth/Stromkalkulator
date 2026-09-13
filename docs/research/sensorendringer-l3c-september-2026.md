# Hva L3c flyttet i månedssensorene (september 2026)

L3a la avregningen på intervaller, L3b la kronene i `kostnad.py`, og L3c fikk
sensorene til å lese dem. Sensorene regnet selv fram til nå: de ganget månedens
kilowattimer med satsen som sto i data-dicten akkurat da. Notatet her måler hva
byttet gjorde med tallene brukerne ser.

Ingen entitets-ID, enhet, `device_class` eller `state_class` er rørt. Det er
etterprøvd ved å dumpe hele entitetsregisteret for alle 55 entiteter, mot både
HA 2025.1 (minimum) og HA 2026.9 (current), før og etter, og diffe. Begge
diffene er tomme.

## Målingen

Coordinatoren er kjørt gjennom juni 2026 med fem minutters poll, 5 kW konstant
effekt og 1,20 kr/kWh spot, altså BKK-tariffen og trinn 3 (415 kr). For hver
sensor er den gamle formelen regnet på nøyaktig den samme data-dicten som den
nye leser, så alt annet enn formelen står stille.

### Midt i måneden (15. juni, 1799,6 kWh bokført)

| Sensor                | Før     | Etter  | Differanse |
| --------------------- | ------- | ------ | ---------- |
| Månedlig nettleie     | 1035,05 | 827,50 |    -207,55 |
| Månedlig nettleie tot | 650,48  | 442,84 |    -207,64 |
| Månedlig avgifter     | 182,84  | 182,88 |      +0,04 |
| Månedlig strømstøtte  | 384,57  | 384,66 |      +0,09 |

### Ved månedsslutt (30. juni, 3599,2 kWh bokført)

| Sensor                | Før     | Etter   | Differanse |
| --------------------- | ------- | ------- | ---------- |
| Månedlig nettleie     | 1655,10 | 1655,00 |      -0,10 |
| Månedlig nettleie tot | 885,96  | 885,68  |      -0,28 |
| Månedlig avgifter     | 365,68  | 365,77  |      +0,09 |
| Månedlig strømstøtte  | 769,14  | 769,32  |      +0,18 |

## De to store tallene er fastleddet, og bare midt i måneden

`Månedlig nettleie` viste før hele månedens kapasitetsledd fra første poll den
1. i måneden. Nå viser den det bokførte fastleddet, altså månedsbeløpet ganget
med forløpt andel av måneden, som er det samme tallet `Akkumulert strømkostnad`
og `Dagens kostnad` alltid har brukt. De 207,55 kronene 15. juni er nøyaktig
415 minus 207,45, altså halve månedsbeløpet som ikke var forløpt ennå.

`Månedlig nettleie total` følger etter, siden den er nettleie minus støtte.

Ved månedsslutt er differansen 10 øre, som er fastleddet for de siste fem
minuttene. Tallet du sammenligner med fakturaen er altså uendret. Det som er
endret, er at sensoren ikke lenger overdriver tidlig i måneden: 1. juni viste
den 415 kroner nettleie før noe var brukt.

Dette er retning, ikke bare forflytning. En månedssensor med `state_class`
`TOTAL` som starter på et helt månedsbeløp og deretter bare vokser, er ikke en
akkumulator. Nå er den det, og de fire kostnadssensorene forteller samme
historie.

## Småtallene er slakk i siste intervall, ikke en formelendring

Avgifter og strømstøtte flyttet seg 4 til 18 øre. Det er forbruket i det åpne
intervallet som ikke er bokført ennå: den gamle formelen brukte akkumulatoren
for kilowattimer, som oppdateres ved hver poll, mens bokføringen lukker
intervallet først. Differansen er under 0,05 % og skifter fortegn med hvor i
intervallet pollen faller.

Med konstant spotpris, som i denne målingen, er de to formlene nesten like for
strømstøtten. Med ekte priser er de det ikke: den gamle ganget hele månedens
kilowattimer med støttesatsen i den ene timen vi tilfeldigvis spurte i, mens
bokføringen summerer time for time med timens egen spotpris og stanser ved
månedstaket. Det er hele grunnen til at sensoren het «estimat» før. Det gjør
den ikke lenger.

## Attributtene som byttet betydning

`Månedlig nettleie` hadde `energiledd_dag_kr` og `energiledd_natt_kr` regnet
med en sats som har forbruksavgift og Enova oppi. De viser nå nettleiens
energidel uten avgiftene, og avgiftene står i det nye attributtet
`avgifter_kr`. Det er fakturaens egen splitt, og de fire attributtene summerer
til sensorverdien. For mai 2026 gir det 186,34 / 86,77 / 119,85 / 250, som er
BKK-fakturaens fire linjer på øret.

`Månedlig avgifter` har fortsatt `forbruksavgift_kr` og `enovaavgift_kr`.
Bokføringen fører de to under ett, så splitten er det bokførte beløpet fordelt
etter forholdet mellom satsene. Endres forbruksavgiften midt i måneden, er
splitten et anslag mens totalen er eksakt. Før var begge deler et anslag.

## Det ene stedet som fortsatt regner selv

`Forrige måned nettleie` ganger arkiverte satser med arkiverte kilowattimer.
Coordinatoren arkiverer ikke forrige måneds bokførte kroner, bare
kilowattimene, satsene som gjaldt siste dag i måneden og kapasitetstrinnet, så
det finnes ikke noe å lese. Tallet stemmer når satsene sto stille gjennom
måneden, og bommer når de ikke gjorde det, altså ved nyttår og for
sesong-nettselskap 1. april og 1. november. Sensoren sier det selv i
attributtet `kilde`, og arkiveringen er ført som `stromkalkulator-1fnzdn8`.

## Slik gjøres målingen om igjen

Legg dette som `tests/test_zz_l3c_maal.py`, kjør `just test-unit -s
tests/test_zz_l3c_maal.py`, og slett filen etterpå. Den er en måling, ikke en
port.

```python
from datetime import datetime, timedelta

from tests.conftest import _make_entry, _make_hass, _run_update


def test_maal(coord_module):
    c = coord_module.NettleieCoordinator(_make_hass(power_w=5000, spot_price=1.20), _make_entry())
    t = datetime(2026, 6, 1, 0, 0)
    for i in range(30 * 24 * 12 - 1):  # fem minutters poll, hele juni
        data = _run_update(coord_module, c, t + timedelta(minutes=5 * i))

    dag_kwh = data["monthly_consumption_dag_kwh"]
    natt_kwh = data["monthly_consumption_natt_kwh"]
    total_kwh = data["monthly_consumption_total_kwh"]
    gammel_nettleie = round(
        dag_kwh * data["energiledd_dag"] + natt_kwh * data["energiledd_natt"] + data["kapasitetsledd"], 2
    )
    gammel_stotte = round(total_kwh * data["stromstotte"], 2)
    gammel_avgifter = round(total_kwh * (data["forbruksavgift_inkl_mva"] + data["enova_inkl_mva"]), 2)
    ny_nettleie = round(
        data["monthly_accumulated_cost_energiledd_kr"] + data["monthly_accumulated_cost_kapasitetsledd_kr"],
        2,
    )
    print(gammel_nettleie, ny_nettleie, gammel_stotte, data["monthly_stromstotte_kr"])
    print(gammel_avgifter, data["monthly_avgifter_kr"])
```

Pollintervallet må være under `MAX_ELAPSED_HOURS` (6 minutter), ellers forkaster
Riemann-stien hvert eneste vindu og du måler på null kilowattimer.
