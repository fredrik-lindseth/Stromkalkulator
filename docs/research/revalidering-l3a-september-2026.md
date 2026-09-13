# Revalidering av fakturafasiten etter L3a (september 2026)

Målt mot `559f799` («coordinator: la energileddet bokføres uten et mellomtall
ingen leser»), med `ce1ca99` som før-tilstand. Dette er en verifiseringsrunde:
ingenting i grunnlaget er rettet, og ingen produksjonskode er rørt.

## Hva som ble revalidert, og hvorfor akkurat nå

Endringsserien L3a flyttet tre ting i hvordan avregningsgrunnlaget regnes:
energi bokføres på måletidens tariff i stedet for pollens, en time uten
prisprøve arver ikke lenger naboens pris, og Norgespris-linjen regnes mot
timeprisen framfor prisen ved poll. Alle tre kan flytte kroner mellom
komponenter uten at totalen sier fra, og det er nøyaktig det
`stromkalkulator-443xvtv` ber om å få målt.

Merk rekkefølgen i loggen: `dae8102` («wip: coordinator bokfører gjennom
avregningsboken») ligger *før* `fea9c9e` og bærer mesteparten av
coordinator-endringen. Bruker du `fea9c9e` som før-tilstand, måler du et
tomt diff. Riktig før-tilstand er `ce1ca99`.

## Rå grunnlag er urørt

```
git diff --stat ce1ca99 559f799 -- tests/fixtures/ scripts/research/ \
    tests/replay/fasit.py tests/test_faktura_bkk.py
```

Kommandoen gir tom utskrift. Faktura-, Elhub- og Final-prisgrunnlaget,
fasit-implementasjonen og verifiseringsskriptene er alle uendret gjennom
serien. Følgen er at attesten mot faktura er bit-identisk før og etter:

```
python3 scripts/research/verify_invoice_hourly.py \
    --hourly tests/fixtures/bkk_<måned>_2026_hourly.json --faktura <måned>_2026
python3 scripts/research/verify_norgespris_eksakt.py
```

kjørt i begge utsjekkene gir samme utskrift, linje for linje. Alle sju
2026-månedene står «Alt innenfor toleranse», og august står «DELVIS» på
volumlinjene som før.

`verify_norgespris_eksakt.py` trenger `_private/Måleverdier/`. Den er
gitignored og finnes bare i hovedutsjekken, så i et worktree må den lenkes
inn (`ln -s <hovedutsjekk>/_private _private`) før skriptet sier annet enn
«Ingen måneder med full prisdekning».

## Komponentene som faktisk flyttet seg

Attesten over sier ingenting om coordinatoren, for den regnes uten den.
Derfor ble mai, juni og juli 2026 spilt gjennom den ekte coordinatoren i
begge utsjekkene, matet fra Elhubs intervallenergi og Nord Pools Final-priser
med 10 sekunders målerkadens, og lest av rett før månedsskiftet og på
`previous_month_*` etter rulleringen.

Tallene er kilowattimer og kroner, «før» er `ce1ca99` og «etter» `559f799`.

| Måned     | Komponent         | Før      | Etter    | Differanse | Faktura  |
| --------- | ----------------- | -------: | -------: | ---------: | -------: |
| mai 2026  | forbruk dag       | 518,133  | 518,142  | +0,009     | 518,142  |
| mai 2026  | forbruk natt      | 661,170  | 661,161  | -0,009     | 661,161  |
| mai 2026  | forbruk total     | 1179,288 | 1179,288 | 0          | 1179,303 |
| mai 2026  | energiledd akk.   | 392,9551 | 392,9573 | +0,0022    |          |
| mai 2026  | Norgespris        | -1032,48 | -1032,56 | -0,08      | -1032,56 |
| mai 2026  | kapasitetsledd    | 250      | 250      | 0          | 250      |
| mai 2026  | `monthly_cost_kr` | 1377,27  | 1377,27  | 0          |          |
| juni 2026 | forbruk dag       | 590,385  | 590,646  | +0,261     | 590,646  |
| juni 2026 | forbruk natt      | 443,243  | 442,982  | -0,261     | 442,982  |
| juni 2026 | forbruk total     | 1033,617 | 1033,617 | 0          | 1033,628 |
| juni 2026 | energiledd akk.   | 375,5328 | 375,5924 | +0,0596    |          |
| juni 2026 | Norgespris        | -363,55  | -363,53  | +0,02      | -363,54  |
| juni 2026 | kapasitetsledd    | 250      | 250      | 0          | 250      |
| juni 2026 | `monthly_cost_kr` | 1249,21  | 1249,21  | 0          |          |
| juli 2026 | forbruk dag       | 514,202  | 514,414  | +0,212     | 514,414  |
| juli 2026 | forbruk natt      | 424,561  | 424,349  | -0,212     | 424,349  |
| juli 2026 | forbruk total     | 938,741  | 938,741  | 0          | 938,763  |
| juli 2026 | energiledd akk.   | 336,0400 | 336,0885 | +0,0485    |          |
| juli 2026 | Norgespris        | -807,56  | -807,50  | +0,06      | -807,50  |
| juli 2026 | kapasitetsledd    | 250      | 250      | 0          | 250      |
| juli 2026 | `monthly_cost_kr` | 1119,60  | 1119,60  | 0          |          |

Dette er lærepengen issuet advarer om, målt: **totalforbruket, kapasitetsleddet
og `monthly_cost_kr` står stille i alle tre månedene, mens dag/natt-splitten
flyttet inntil 0,261 kWh over tariffgrensen.** Hadde vi bare sett på totalen,
hadde serien sett ut som et null-diff.

Retningen er den vi vil ha. Etter `559f799` treffer coordinatorens dag/natt
Elhub-fasiten eksakt i alle tre månedene, mot inntil 0,26 kWh bom før. Både
mai og juli traff Norgespris-linjen på øret etterpå; juni ligger 1 øre fra
fakturaen, som er der fasiten selv ligger, altså avrundingsstøy og ikke et
avvik i coordinatoren.

Totalforbruket ligger 0,011 til 0,022 kWh under Elhub i begge utsjekkene.
Det er siste måling i måneden, som faller etter siste poll i pollplanen, og
ikke et fortegn på noe som helst. Den står uendret gjennom serien.

### Én komponent som med vilje ikke fulgte med

`monthly_cost_kr` og `daily_cost` flyttet seg ikke, selv om dag/natt-splitten
gjorde det. Det er ikke en glipp: `coordinator.py` sier rett ut at
Norgespris-linjen er bokført mot intervallets timepris mens dags- og
månedskostnaden står igjen på pollens pris til kostnadskjernen tar dem. Med
andre ord er kroneverdiene i den familien fortsatt førbilde, ikke etterbilde,
og de skal måles på nytt når kostnadskjernen lander.

### To endringer som ikke gav utslag her

Regelen om at en time uten prisprøve ikke skal arve naboens pris slår ikke ut
på mai, juni og juli, fordi Final-pris-fixturene har full prisdekning for alle
timene. `kwh_uten_pris` og `kwh_delvis_pris` er null i fasiten for alle tre.
Regelen biter først i måneder med prishull, og de månedene er akkurat de som
ikke lar seg avstemme mot faktura ennå.

Randtime-regelen i `scripts/research/fyll_spothull_fra_nordpool.py`, som ble
kurs-årgangsbevisst i `bc2b04d` og `20e94fc`, er allerede bakt inn i
august-fixturen (`9399077`). `verify_norgespris_eksakt.py` bekrefter 50 timer
holdt utenfor prisfideliteten for august, ikke 51. Ingen av
referansemånedene med faktura-avstemming er påvirket.

## Testporten

```
UV_PROJECT_ENVIRONMENT=.venv-unit uv run --frozen --python 3.13 --group unit \
    pytest tests/ -q
```

I en ren utsjekk av `559f799`: 3359 passert, 34 hoppet over. Ingen feil.

## August 2026 er fortsatt ikke avstembar

176 av 744 timer mangler HAN-måling etter leserutfallet 29. juli til 8. august,
og Elhub-CSV-en for august er ikke lastet ned. Én time, 31.08 kl. 00, står
bevisst ufylt i påvente av en beslutning. Måneden er derfor merket DELVIS i
`verify_invoice_hourly.py` og står i `UFULLSTENDIGE` i replay-testene, og den
er ikke revalidert her utover at utskriften er uendret fra før serien.
Nedlastingen spores i `stromkalkulator-r568ale`.

## Kommandoen som produserte før/etter-tabellen

Sammenligningen er kjørt med et engangsharnesse, ikke et skript i repoet.
Skal den gjøres om igjen, lag to detached worktrees på de to commitene, lenk
inn `_private`, legg filen under inn som `tests/test_revalider_maaneder.py` i
begge og kjør `pytest tests/test_revalider_maaneder.py -q -s`. Fjern filen
etterpå; den hører ikke hjemme i suiten, for den er en måling og ikke en port.

```python
"""Engangsmåling: full måned gjennom coordinatoren, komponent for komponent."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROT))
from tests.replay.fasit import Fasit  # noqa: E402
from tests.replay.harness import Replay, logg_fra_timesenergi, pollplan  # noqa: E402

FIX = ROT / "tests" / "fixtures"
MND = ["mai_2026", "juni_2026", "juli_2026"]


def _j(navn):
    return json.loads((FIX / navn).read_text(encoding="utf-8"))


def timer(navn):
    return [(datetime.fromisoformat(h["start_local"]), h["kwh"]) for h in _j(f"elhub_{navn}.json")["hours"]]


def priser(navn):
    ut = {}
    for h in _j(f"final_pris_{navn}.json")["hours"]:
        ut[datetime.fromisoformat(h["start_local"])] = h["kvarter"] or [h["nok_per_kwh_eks_mva"]] * 4
    return ut


def fasit_for(navn):
    f = Fasit()
    p = priser(navn)
    for start, kwh in timer(navn):
        f.bokfor_intervall(start, kwh)
        for i, verdi in enumerate(p[start]):
            f.prisprove(start + timedelta(minutes=15 * i, seconds=450), verdi)
    return f


@pytest.mark.parametrize("navn", MND)
def test_dump(coord_module, navn):
    t = timer(navn)
    logg = logg_fra_timesenergi(t, priser(navn), maler_sekunder=10)
    r = Replay(coord_module, logg)
    start = t[0][0]
    slutt = t[-1][0] + timedelta(hours=1)
    r.start(start)
    r.kjor(pollplan(start, slutt))
    try:
        d = dict(r.data)
        r.rull_maned(slutt + timedelta(minutes=5))
        prev = dict(r.data)
        f = fasit_for(navn).avregning()
        print(
            "DUMP "
            + json.dumps(
                {
                    "maaned": navn,
                    "dag_kwh": prev["previous_month_consumption_dag_kwh"],
                    "natt_kwh": prev["previous_month_consumption_natt_kwh"],
                    "total_kwh": d["monthly_consumption_total_kwh"],
                    "energiledd_akk_kr": d["monthly_accumulated_cost_energiledd_kr"],
                    "kapasitetsledd_kr": prev["previous_month_kapasitetsledd"],
                    "snitt_topp3_kw": prev["previous_month_avg_top_3_kw"],
                    "norgespris_kr": prev["previous_month_norgespris_compensation_kr"],
                    "monthly_cost_kr": d["monthly_cost_kr"],
                    "akkumulert_kr": d["monthly_accumulated_cost_kr"],
                    "fasit_dag_kwh": round(f.kwh_dag, 3),
                    "fasit_natt_kwh": round(f.kwh_natt, 3),
                    "fasit_stotte_kr": round(f.stotte_kr, 2),
                    "fasit_kwh_uten_pris": round(f.kwh_uten_pris, 3),
                },
                sort_keys=True,
            )
        )
    finally:
        r.lukk()
```

Pollplanen må stoppe på månedsgrensen. Ruller du forbi den, nullstiller
coordinatoren `monthly_*` for den nye måneden, og alt du leser av er nuller.

## Dette må kjøres på nytt etter kostnadskjernen

Kostnadskjernen (L3b) bygger om `kostnad.py` og kommer til å endre kronetallene.
Denne runden er derfor gyldig bare for `559f799`. Når L3b lander, må hele
attesten kjøres om igjen for alle ti verifiserte måneder:

- **oktober, november og desember 2025** gjennom `tests/test_faktura_bkk.py`
  (spotpris og strømstøtte, 2025-satser).
- **februar til august 2026** gjennom `verify_invoice_hourly.py` per måned.
- **mai, juni og juli 2026** i tillegg gjennom replay-fasiten i
  `tests/test_replay_hendelser.py` og gjennom engangsharnesset over, siden det
  er de eneste med både Elhub-intervallenergi og Final-pris.
- **`monthly_cost_kr`, `monthly_net_cost_kr`, `daily_cost` og hele
  `monthly_accumulated_cost_*`-familien** er de som faktisk vil flytte seg.
  Forbruk i kWh, dag/natt-splitten og kapasitetsleddet skal derimot stå stille;
  gjør de ikke det, har L3b rørt noe den ikke skulle.
- **August 2026** kan ikke avstemmes mot faktura før Elhub-CSV-en er lastet ned
  (`stromkalkulator-r568ale`) og beslutningen om 31.08 kl. 00 er tatt.
