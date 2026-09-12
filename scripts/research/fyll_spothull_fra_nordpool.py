#!/usr/bin/env python3
"""Fyll spotpris-hull i en hourly-fixture med Nord Pools publiserte Final-priser.

Timer der `spot_nok_kwh_eks_mva` er null fylles fra kvarterarkivet
(`_private/Måleverdier/nordpool_nok_kvarter_no5.json`, oppdatert med
`just snapshot-kurs`), og merkes med `"spot_kilde": "nordpool_publisert"`.
Merkingen finnes fordi verify_norgespris_eksakt.py måler hvor godt
HA-recorderens lagrede priser stemmer med de publiserte: fylte timer må
holdes utenfor den sammenligningen, ellers måler den seg selv.

Timesprisen er snittet av de fire kvarterprisene, samme avregning som
verify_norgespris_eksakt.py bruker. Timer uten fire kvarter i arkivet fylles
ikke; da er arkivet ufullstendig og bør snapshottes på nytt.

Randtimen i starten av et hull fylles også. Når Nord Pool-sensoren faller ut
presis ved døgnskiftet, går den `unknown` kl. 00:00:00 og `unavailable` noen
sekunder senere. HAs statistikk-kompilator regner timesnittet bare over
numeriske states, så staten fra 23:45-kvarteret kvelden før blir båret gjennom
hele time 00. Recorderen har da en verdi for timen, men det er ikke en måling
av timen. Slike timer kjennes igjen automatisk, og regelen har to krav som
begge må være oppfylt for at en time med recorder-verdi skal overskrives:

1. Verdien ligger innenfor 0,5 øre/kWh av forrige døgns 23:45-kvarter.
2. Verdien ligger minst 0,2 øre/kWh lenger unna sin egen publiserte time enn
   den ligger fra det 23:45-kvarteret.

Begge avstandene måles mot en kurs-årgangsjustert pris, ikke mot rå publisert
pris. HA lagrer prisene slik de så ut ved publisering, og på dager der
FX-markedet var stengt på auksjonsdagen ligger hele døgnet skjevt med en
tilnærmet konstant faktor mot den publiserte Final-prisen (målt opptil 0,63 %,
som er 0,9 øre/kWh, se `maal_aargang`). Uten justeringen bommer en ekte
måling på sin egen publiserte time av en grunn som ikke har noe med hull å
gjøre, og krav 2 slår til på en gyldig måling.

Krav 1 alene holder ikke. På en natt med flat pris ligger en ekte måling i
time 00 også innenfor 0,5 øre av 23:45-kvarteret, og da ville en gyldig måling
blitt overskrevet og merket med en årsak som ikke er sann. Krav 2 skiller de
to: en båret verdi er kvelden før om igjen, så den stemmer bedre med
23:45-kvarteret enn med sin egen time. En ekte måling er omvendt. (Den gamle
ordlyden «en ekte måling stemmer med sin egen time» holdt ikke: på en
årgangsdag gjør den ikke det uten kurskorreksjon.) De to fylte randtimene i
august, 17.08 og 23.08, ligger 4,2 og 7,7 øre fra sin egen time, mens de ligger
0,00 øre fra 23:45-kvarteret begge to, årgangsjustert.

Lar kurs-årgangen seg ikke måle, blir timen stående. Det skjer når døgnet er
helt hullet, har under seks ekte timer med publisert pris, eller ikke er lagret
med én konstant kurs. Da er ikke forutsetningen for kravene etterprøvbar, og
det som mangler er ikke et argument for å fylle: en fylt time bærer et
proveniensmerke som sier at den er kjent igjen som randtime, og det merket ville
vært usant. 31.08.2026 er akkurat dette, for hele døgnet er hullet.

Er kravene i konflikt, altså verdien ligger nær 23:45-kvarteret men også nær
sin egen time, gjetter scriptet heller ikke. Timen blir stående som målt, og
saken skrives ut så den kan avgjøres for hånd med --overstyr. Samme gjelder når
arkivet mangler den publiserte timen eller 23:45-kvarteret. Hver time 00 foran
et hull skrives ut med begge avstandene og hvilken kurs-årgang som ble brukt,
uansett utfall, så avgjørelsen er synlig.

Randtimer som passerer fylles fra arkivet og merkes som de andre, med
begrunnelsen arkivert i fixturens metadata.

Andre timer der recorderen har en verdi overstyres aldri automatisk. Faller
sensoren ut midt i en time, lagrer recorderen et snitt av bare den delen av
timen den rakk å måle. Slike tilfeller overstyres eksplisitt med --overstyr og
en begrunnelse, som også arkiveres i metadata.

Kjøringen er idempotent, og proveniens som er ført én gang blir stående:

* En overstyrt time beholder recorder-verdien den hadde før overstyringen, og
  begrunnelsen, i alle senere kjøringer. Å utelate --overstyr angrer ingenting;
  timen er fylt, og metadataen sier fortsatt hvorfor.
* Gjentas --overstyr med samme begrunnelse, skjer ingenting. Gjentas den med en
  ny begrunnelse, erstattes den, og den gamle føres i `tidligere_begrunnelser`.
  Recorder-verdien i metadata er alltid den opprinnelige målingen, aldri
  arkivprisen den ble erstattet med.
* --angre er veien tilbake, og gjelder både overstyringer og randtimer:
  recorder-målingen legges tilbake i timen fra metadata, og oppføringen
  slettes. Timen behandles så som en hvilken som helst målt time i resten av
  kjøringen, så treffer randtime-regelen fortsatt, blir den fylt igjen.

Bruk:
    python3 scripts/research/fyll_spothull_fra_nordpool.py \
        --fixture tests/fixtures/bkk_august_2026_hourly.json \
        --overstyr "2026-08-23T12:00:00+02:00=sensoren falt ut midt i timen; recorder-snittet dekker bare deler av den"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parent.parent.parent
NOK_ARKIV = ROOT / "_private" / "Måleverdier" / "nordpool_nok_kvarter_no5.json"

# Hvor nær forrige døgns 23:45-kvarter en time 00 må ligge for å regnes som
# randtime. Avstanden måles mot kvarteret justert for kurs-årgangen det ble
# lagret med, så toleransen trenger ikke dekke årgangen. Klarer vi ikke å måle
# årgangen, sammenlignes det mot rå publisert pris, og da kan årgangen alene
# spise hele budsjettet: målt spenn i fixturene er opptil 0,63 % (2026-08-02,
# ratio 0,99373), som er 0,896 øre/kWh. Slike tilfeller skrives ut.
RANDTIME_TOLERANSE_NOK = 0.005
# Hvor mye lenger unna sin egen publiserte time verdien må ligge enn den ligger
# fra 23:45-kvarteret. En båret verdi er kvelden før om igjen og bommer på sin
# egen time; en ekte måling treffer den, så lenge begge sammenlignes med samme
# kurs-årgang. Marginen er satt under den trangeste saken vi har sett (31.08:
# 0,01 øre fra 23:45, 0,52 øre fra egen time), en time som selv står ufylt fordi
# kurs-årgangen på det døgnet ikke lot seg måle. Den dekker ikke
# kurs-årgangen, og skal ikke gjøre det heller: årgangen tas av justeringen i
# maal_aargang, for den er opptil 0,9 øre og ville slukt marginen.
RANDTIME_EGEN_TIME_MARGIN_NOK = 0.002
# Kurs-årgangen måles på døgnets egne ekte timer. Seks holder: et hulldøgn har
# sjelden flere igjen (17.08 har sju, 23.08 fjorten). Spennet mellom ratioene
# må være mindre enn AARGANG_MAKS_SPREDNING, ellers er ikke døgnet en konstant
# faktor og årgangen regnes som umålt.
AARGANG_MIN_TIMER = 6
AARGANG_MAKS_SPREDNING = 5e-4
RANDTIME_BEGRUNNELSE = "randtime_forrige_kvarter"
FYLT_MERKE = "nordpool_publisert"


def les_arkiv(sti: Path) -> tuple[dict[str, float], dict[str, float]]:
    """(timespriser, kvarterpriser) i NOK/kWh eks. mva, nøklet på lokal ISO.

    Timespriser tas bare med når alle fire kvarter finnes; ellers er arkivet
    ufullstendig for timen.
    """
    kvarter: dict[str, float] = {}
    bucket: dict[str, list[float]] = {}
    for dag in json.loads(sti.read_text(encoding="utf-8"))["daily"]:
        for kv in dag["kvarter"]:
            kvarter[kv["start_local"]] = kv["nok_mwh"] / 1000.0
            time_iso = kv["start_local"][:14] + "00:00" + kv["start_local"][19:]
            bucket.setdefault(time_iso, []).append(kv["nok_mwh"])
    timer = {iso: sum(q) / len(q) / 1000.0 for iso, q in bucket.items() if len(q) == 4}
    return timer, kvarter


def er_hull(time: dict[str, object]) -> bool:
    """Timen mangler recorder-måling, enten fortsatt tom eller alt fylt herfra."""
    return time["spot_nok_kwh_eks_mva"] is None or time.get("spot_kilde") == FYLT_MERKE


def forrige_kvarter_iso(ts: str) -> str:
    """Lokal ISO for kvarteret som starter 15 minutter før en timestart."""
    return (datetime.fromisoformat(ts) - timedelta(minutes=15)).isoformat()


class Aargang(NamedTuple):
    """Kurs-årgangen for ett døgn, og hva som eventuelt hindret målingen.

    `ratio` er None når årgangen ikke lot seg måle. `grunn` er den samme
    teksten uansett utfall, så en logglinje kan si hvilken årgang en avstand
    ble målt med, eller hvorfor den ikke kunne måles.
    """

    ratio: float | None
    grunn: str


def maal_aargang(
    hours: list[dict[str, object]],
    publiserte_timer: dict[str, float],
    dag: str,
    utelat: str | None = None,
) -> Aargang:
    """Kurs-årgangen HA lagret ett døgns priser med: snittet av rec/publisert.

    HA lagrer spotprisen slik den så ut ved publisering. På dager der
    FX-markedet var stengt på auksjonsdagen (søndager, enkelte helligdager og
    dagen etter) er valutakursen foreløpig og korrigeres senere til Final, så
    hele døgnet ligger skjevt mot den publiserte prisen med en tilnærmet
    konstant faktor. Uten å ta hensyn til det bommer en helt ekte måling på sin
    egen publiserte time av en grunn som ikke har noe med recorder-hull å gjøre.

    Regnestykket speiler prisårgang-blokken i
    scripts/research/verify_norgespris_eksakt.py (`analyser_maaned`): ratio per
    time, snitt over døgnet, og et krav om at spennet er lite nok til at
    faktoren er konstant. Logikken er skrevet opp på nytt her framfor å
    importeres fordi verify-scriptet eies et annet sted og drar med seg
    verify_invoice_hourly og fakturaregisteret; dette scriptet skal kunne kjøres
    på én fixture og ett arkiv. Endres den ene, skal den andre etter.
    To forskjeller, begge bevisste: verify ser bare på timer som avviker mer enn
    0,01 øre og krever 20 av dem for å kalle et døgn en årgangsdag, mens vi tar
    med alle ekte timer og nøyer oss med AARGANG_MIN_TIMER, for et hulldøgn har
    sjelden 20 timer igjen.

    Returnerer ratio None når døgnet ikke har nok ekte timer med publisert pris,
    eller når faktoren ikke er konstant. Fylte timer teller ikke: de er arkivets
    egen pris og ville målt arkivet mot seg selv.
    """
    ratioer: list[float] = []
    for h in hours:
        ts = str(h["start_local"])
        if ts[:10] != dag or ts == utelat:
            continue
        verdi = h["spot_nok_kwh_eks_mva"]
        if verdi is None or h.get("spot_kilde") == FYLT_MERKE:
            continue
        publisert = publiserte_timer.get(ts)
        if publisert is None or publisert <= 0.01:
            continue
        ratioer.append(float(verdi) / publisert)
    if len(ratioer) < AARGANG_MIN_TIMER:
        return Aargang(
            None,
            f"kurs-årgangen for {dag} er umålt: døgnet har {len(ratioer)} ekte timer "
            f"med publisert pris, og regelen krever {AARGANG_MIN_TIMER}",
        )
    spenn = max(ratioer) - min(ratioer)
    if spenn >= AARGANG_MAKS_SPREDNING:
        return Aargang(
            None,
            f"kurs-årgangen for {dag} er umålt: faktoren varierer over døgnet "
            f"(spenn {spenn:.5f}, grensen er {AARGANG_MAKS_SPREDNING:.5f}), altså "
            "er ikke hele døgnet lagret med én kurs",
        )
    snitt = sum(ratioer) / len(ratioer)
    return Aargang(snitt, f"kurs-årgang {snitt:.5f}")


def _avgjor_for_hand(ts: str) -> str:
    """Oppfordringen som følger hver time scriptet ikke vil avgjøre selv."""
    return f'Avgjør den for hånd med --overstyr "{ts}=<begrunnelse>" hvis den hører til hullet.'


def finn_randtimer(
    hours: list[dict[str, object]],
    kvarter: dict[str, float],
    publiserte_timer: dict[str, float],
) -> tuple[dict[str, float], list[str]]:
    """Time 00 rett før et hull, der recorder-verdien er forrige døgns 23:45.

    Sensoren går `unknown` presis 00:00:00 og `unavailable` få sekunder senere.
    HAs statistikk-kompilator snitter bare over numeriske states, så staten fra
    23:45-kvarteret bæres gjennom hele time 00. Verdien er da ikke en måling av
    timen, og timen hører til hullet.

    Nærheten til 23:45-kvarteret holder ikke alene: på en flat natt treffer en
    ekte måling den også. Verdien må i tillegg ligge klart lenger unna sin egen
    publiserte time enn den ligger fra 23:45-kvarteret.

    Begge avstandene måles mot kurs-årgangsjusterte priser: 23:45-kvarteret mot
    årgangen kvelden før (verdien er båret derfra), egen time mot årgangen på
    sitt eget døgn. Uten det slår krav 2 til på en ekte måling på en årgangsdag,
    der hele døgnet ligger opptil 0,9 øre skjevt mot publisert pris.

    Lar en av de to årgangene seg ikke måle, blir timen stående. Da er ikke
    forutsetningen for kravene etterprøvbar, og å fylle timen likevel ville gitt
    den et proveniensmerke vi ikke kan stå for. Linjen sier hva som ikke lot seg
    måle, og timen avgjøres for hånd med --overstyr.

    Returnerer treffene og en logglinje per time 00 foran et hull, uansett
    utfall, med begge avstandene og hvilken årgang de er målt med.
    """
    treff: dict[str, float] = {}
    meldinger: list[str] = []
    for i, h in enumerate(hours[:-1]):
        ts = str(h["start_local"])
        verdi = h["spot_nok_kwh_eks_mva"]
        if verdi is None or ts[11:13] != "00" or not er_hull(hours[i + 1]):
            continue
        if h.get("spot_kilde") == FYLT_MERKE:
            # Alt fylt i en tidligere kjøring; verdien er arkivets, ikke
            # recorderens, så regelen kan ikke prøves på nytt.
            continue
        kvarter_iso = forrige_kvarter_iso(ts)
        forrige = kvarter.get(kvarter_iso)
        if forrige is None:
            meldinger.append(
                f"{ts}: prisarkivet mangler 23:45-kvarteret kvelden før, så randtimen "
                f"kan ikke avgjøres. Lot timen stå. {_avgjor_for_hand(ts)}"
            )
            continue
        aargang_forrige = maal_aargang(hours, publiserte_timer, kvarter_iso[:10])
        if aargang_forrige.ratio is None:
            meldinger.append(
                f"{ts}: {aargang_forrige.grunn}, og verdien er båret derfra, så "
                "avstanden til 23:45-kvarteret kan ikke prøves. Lot timen stå som "
                f"målt. {_avgjor_for_hand(ts)}"
            )
            continue
        forrige_justert = forrige * aargang_forrige.ratio
        avstand_forrige = abs(float(verdi) - forrige_justert)
        if avstand_forrige > RANDTIME_TOLERANSE_NOK:
            meldinger.append(
                f"{ts}: ligger {avstand_forrige * 100:.2f} øre fra forrige døgns 23:45 "
                f"({aargang_forrige.grunn}), altså utenfor toleransen på "
                f"{RANDTIME_TOLERANSE_NOK * 100:.2f} øre. Ser ut som en ekte måling. "
                "Lot timen stå."
            )
            continue
        publisert = publiserte_timer.get(ts)
        if publisert is None:
            meldinger.append(
                f"{ts}: ligger {avstand_forrige * 100:.2f} øre fra forrige døgns 23:45, "
                "men prisarkivet mangler timen selv, så randtimen kan ikke avgjøres. "
                f"Lot timen stå. {_avgjor_for_hand(ts)}"
            )
            continue
        aargang_egen = maal_aargang(hours, publiserte_timer, ts[:10], utelat=ts)
        if aargang_egen.ratio is None:
            meldinger.append(
                f"{ts}: ligger {avstand_forrige * 100:.2f} øre fra forrige døgns 23:45 "
                f"({aargang_forrige.grunn}), men {aargang_egen.grunn}, så avstanden til "
                "sin egen publiserte time kan ikke prøves. Lot timen stå som målt. "
                f"{_avgjor_for_hand(ts)}"
            )
            continue
        publisert_justert = publisert * aargang_egen.ratio
        avstand_egen = abs(float(verdi) - publisert_justert)
        if avstand_egen < avstand_forrige + RANDTIME_EGEN_TIME_MARGIN_NOK:
            meldinger.append(
                f"{ts}: ligger {avstand_forrige * 100:.2f} øre fra forrige døgns 23:45, "
                f"men bare {avstand_egen * 100:.2f} øre fra sin egen publiserte time "
                f"({aargang_egen.grunn}). Det ser ut som en ekte måling, ikke "
                "en båret verdi. Lot timen stå; bruk --overstyr med begrunnelse hvis "
                "den likevel hører til hullet."
            )
            continue
        meldinger.append(
            f"{ts}: randtime. {avstand_forrige * 100:.2f} øre fra forrige døgns 23:45 "
            f"({aargang_forrige.grunn}), {avstand_egen * 100:.2f} øre fra sin "
            f"egen publiserte time ({aargang_egen.grunn}). Fylles fra arkivet."
        )
        treff[ts] = forrige
    return treff, meldinger


def endre_begrunnelse(arkivert: dict[str, Any], ny: str) -> tuple[dict[str, Any], bool]:
    """Oppdater begrunnelsen på en overstyring uten å miste den gamle.

    Samme begrunnelse om igjen er en bekreftelse og skal ikke endre noe. En ny
    begrunnelse erstatter den gamle, men den gamle føres i
    `tidligere_begrunnelser`, for den var grunnlaget verdien sto på inntil nå.
    Recorder-verdien røres aldri: den er målingen fra før overstyringen, og
    timen inneholder arkivprisen nå.
    """
    if ny == arkivert["begrunnelse"]:
        return arkivert, False
    historikk = [*arkivert.get("tidligere_begrunnelser", []), arkivert["begrunnelse"]]
    return {**arkivert, "begrunnelse": ny, "tidligere_begrunnelser": historikk}, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--arkiv", type=Path, default=NOK_ARKIV)
    parser.add_argument(
        "--overstyr",
        action="append",
        default=[],
        metavar="TIME=BEGRUNNELSE",
        help="Overstyr en recorder-målt time med den publiserte prisen. Krever begrunnelse.",
    )
    parser.add_argument(
        "--angre",
        action="append",
        default=[],
        metavar="TIME",
        help=(
            "Legg recorder-målingen tilbake i en fylt time (overstyring eller randtime) "
            "og slett proveniensoppføringen."
        ),
    )
    args = parser.parse_args()

    if not args.arkiv.exists():
        print(f"Finner ikke prisarkivet {args.arkiv}; kjør `just snapshot-kurs` først")
        return 1

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    hours = fixture["hours"]
    per_time = {str(h["start_local"]): h for h in hours}
    priser, kvarter = les_arkiv(args.arkiv)

    overstyringer: dict[str, str] = {}
    for spec in args.overstyr:
        time, _, begrunnelse = spec.partition("=")
        if not begrunnelse:
            print(f"--overstyr {time!r} mangler begrunnelse (TIME=BEGRUNNELSE)")
            return 1
        overstyringer[time] = begrunnelse

    fylt_fra_nordpool = fixture["metadata"].get("spothull", {}).get("fylt_fra_nordpool", {})
    tidligere_rand: dict[str, dict[str, float | str]] = fylt_fra_nordpool.get("randtimer", {})
    tidligere_overstyrte: dict[str, dict[str, Any]] = fylt_fra_nordpool.get("overstyrte_timer", {})

    # Angringene tas først, så resten av kjøringen ser timen slik recorderen
    # målte den. Blir den fylt igjen av randtime-regelen i samme kjøring, er det
    # regelen som avgjør, ikke en gammel avgjørelse som henger igjen.
    angret: list[str] = []
    for ts in args.angre:
        if ts in overstyringer:
            print(f"--angre og --overstyr gjelder samme time {ts}; velg én")
            return 1
        arkivert = tidligere_overstyrte.get(ts) or tidligere_rand.get(ts)
        if arkivert is None:
            print(f"--angre {ts} traff ingen fylt time i fixturens metadata")
            return 1
        h = per_time.get(ts)
        if h is None:
            print(f"--angre {ts} traff ingen time i fixturen")
            return 1
        h["spot_nok_kwh_eks_mva"] = arkivert["recorder_nok_kwh"]
        h.pop("spot_kilde", None)
        angret.append(ts)
        print(
            f"{ts}: angret «{arkivert['begrunnelse']}». "
            f"Recorder-målingen {arkivert['recorder_nok_kwh']} er lagt tilbake."
        )
    tidligere_overstyrte = {ts: d for ts, d in tidligere_overstyrte.items() if ts not in angret}
    tidligere_rand = {ts: d for ts, d in tidligere_rand.items() if ts not in angret}

    # Randtimene finnes før hullene fylles: etterpå ser en fylt time 00 ut som
    # en hvilken som helst arkivpris.
    nye_rand, meldinger = finn_randtimer(hours, kvarter, priser)
    for linje in meldinger:
        print(linje)

    # Proveniensen fra tidligere kjøringer følger med så lenge timen fortsatt er
    # fylt. Uten det ville en kjøring uten --overstyr tømt begrunnelsen for en
    # time som fortsatt står med arkivprisen, og fixturen ville sagt at verdien
    # er der uten å si hvorfor.
    fortsatt_merket = {ts for ts, h in per_time.items() if h.get("spot_kilde") == FYLT_MERKE}
    randtimer = {ts: data for ts, data in tidligere_rand.items() if ts in fortsatt_merket}
    overstyrte = {ts: data for ts, data in tidligere_overstyrte.items() if ts in fortsatt_merket}

    fylte: list[str] = []
    nye_overstyrte: list[str] = []
    truffet: set[str] = set()
    for h in hours:
        ts = str(h["start_local"])
        if h["spot_nok_kwh_eks_mva"] is None:
            if ts not in priser:
                print(f"Prisarkivet mangler {ts}; kan ikke fylle hullet komplett")
                return 1
            h["spot_nok_kwh_eks_mva"] = round(priser[ts], 6)
            h["spot_kilde"] = FYLT_MERKE
            fylte.append(ts)
        elif ts in nye_rand:
            # finn_randtimer krever at den publiserte timen finnes, så
            # oppslaget i priser er trygt her.
            randtimer[ts] = {
                "recorder_nok_kwh": h["spot_nok_kwh_eks_mva"],
                "forrige_kvarter_nok_kwh": round(nye_rand[ts], 6),
                "publisert_nok_kwh": round(priser[ts], 6),
                "begrunnelse": RANDTIME_BEGRUNNELSE,
            }
            h["spot_nok_kwh_eks_mva"] = round(priser[ts], 6)
            h["spot_kilde"] = FYLT_MERKE
            fylte.append(ts)
        elif ts in overstyringer:
            truffet.add(ts)
            if ts in overstyrte:
                # Allerede overstyrt. Verdien i timen er arkivprisen nå, så
                # recorder-verdien kan bare hentes fra metadata; å lese den av
                # timen ville arkivert arkivprisen som den opprinnelige målingen.
                gammel_begrunnelse = str(overstyrte[ts]["begrunnelse"])
                overstyrte[ts], byttet = endre_begrunnelse(overstyrte[ts], overstyringer[ts])
                if byttet:
                    nye_overstyrte.append(ts)
                    print(
                        f"{ts}: byttet begrunnelse fra «{gammel_begrunnelse}» til "
                        f"«{overstyringer[ts]}». Den gamle er tatt vare på i "
                        "tidligere_begrunnelser."
                    )
                continue
            if h.get("spot_kilde") == FYLT_MERKE:
                print(
                    f"--overstyr {ts}: timen er alt fylt fra arkivet som hull eller randtime, "
                    "så recorder-målingen finnes ikke lenger. Overstyring gjelder målte timer."
                )
                return 1
            if ts not in priser:
                print(f"Prisarkivet mangler {ts}; kan ikke overstyre timen")
                return 1
            overstyrte[ts] = {
                "recorder_nok_kwh": h["spot_nok_kwh_eks_mva"],
                "publisert_nok_kwh": round(priser[ts], 6),
                "begrunnelse": overstyringer[ts],
            }
            h["spot_nok_kwh_eks_mva"] = round(priser[ts], 6)
            h["spot_kilde"] = FYLT_MERKE
            nye_overstyrte.append(ts)

    ubrukte = set(overstyringer) - truffet
    if ubrukte:
        print(f"--overstyr traff ingen målt time: {sorted(ubrukte)}")
        return 1

    merkede = sum(1 for h in hours if h.get("spot_kilde") == FYLT_MERKE)
    endret = bool(fylte or nye_overstyrte or angret)
    # Datoen står stille når kjøringen ikke endret noe. Ellers ville en kjøring
    # som bare bekrefter fixturen sagt at den ble fylt i dag.
    dato = str(fylt_fra_nordpool.get("dato") or "") if not endret else ""
    if not dato:
        dato = date.today().isoformat()
    spothull = fixture["metadata"].get("spothull", {})
    spothull["fylt_fra_nordpool"] = {
        "kilde": args.arkiv.name,
        "dato": dato,
        "fylte_timer": merkede,
        "avregning": "snitt av fire publiserte Final-kvarterpriser",
        "randtimer": dict(sorted(randtimer.items())),
        "overstyrte_timer": dict(sorted(overstyrte.items())),
    }
    fixture["metadata"]["spothull"] = spothull

    args.fixture.write_text(json.dumps(fixture, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(
        f"Fylte {len(fylte)} timer (herav {len(nye_rand)} randtimer), overstyrte "
        f"{len(nye_overstyrte)} og angret {len(angret)} fra {args.arkiv.name}. "
        f"{merkede} timer er merket {FYLT_MERKE} i alt."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
