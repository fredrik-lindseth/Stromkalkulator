"""Vakt for input- og konfigurasjonskontrakten i docs/kontrakter/input-og-konfig.md.

Avregningskontrakten har hatt en vakt siden den ble skrevet. Denne hadde ingen,
og et dokument uten vakt drifter fra koden: `nb.json` drev fra `strings.json` i
fjorten nøkler fordi ingen test leste dem sammen.

Her kjøres de normative tabellene i kontrakten: enhetstabellen (§2) som
maskinlesbar fasit K1 kan hente normaliseringen sin fra, grunn-strengene (§1),
terskelen (§8), sensortabellen for ukjent fastledd (§9) mot nøklene i
`sensor.py`, og oversettelsesnøklene (§11) mot de tre filene. I tillegg voktes
grensesnittet mot avregningskontrakten, så de to ikke rekker å si hver sin ting
om samme regel en gang til.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROT = Path(__file__).parent.parent
KONTRAKT = ROT / "docs" / "kontrakter" / "input-og-konfig.md"
AVREGNING = ROT / "docs" / "kontrakter" / "avregning.md"
KOMPONENT = ROT / "custom_components" / "stromkalkulator"


def _tekst(sti: Path) -> str:
    assert sti.exists(), f"{sti} finnes ikke"
    return sti.read_text(encoding="utf-8")


def _seksjon(tekst: str, overskrift: str) -> str:
    """Teksten fra en `## `-overskrift til den neste."""
    start = tekst.index(overskrift)
    rest = tekst[start + len(overskrift) :]
    slutt = rest.find("\n## ")
    return rest if slutt < 0 else rest[:slutt]


def _tabellrader(tekst: str) -> list[list[str]]:
    """Alle datarader i markdown-tabellene i teksten, uten hode og skillelinje."""
    rader = []
    for linje in tekst.splitlines():
        if not linje.strip().startswith("|"):
            continue
        celler = [c.strip() for c in linje.strip().strip("|").split("|")]
        if all(set(c) <= {"-", ":"} and c for c in celler):
            continue
        rader.append(celler)
    return rader


def _navn(celle: str) -> list[str]:
    """Identifikatorene i backticks i en celle."""
    return re.findall(r"`([^`]+)`", celle)


def _tall(celle: str) -> float:
    """Et norsk tall fra en tabellcelle: mellomrom som tusenskille, komma som desimaltegn."""
    return float(re.sub(r"\s", "", celle).replace(",", "."))


KONTRAKTTEKST = _tekst(KONTRAKT)


# ---------------------------------------------------------------------------
# Dokumentet


@pytest.mark.parametrize(
    "overskrift",
    [
        "## 1. Typede inputresultater",
        "## 2. Enhetstabell",
        "## 3. Krav til energisensoren",
        "## 4. Sensor uten enhet",
        "## 5. Energibaseline",
        "## 6. Tariffmodus",
        "## 7. Config v5, den ene migreringen",
        "## 9. Egendefinert fastledd",
        "## 11. Nye nøkler som må inn alle tre steder",
        "## 12. Hva kontrakten ikke avgjør",
    ],
)
def test_kontrakten_har_seksjonene(overskrift: str) -> None:
    assert overskrift in KONTRAKTTEKST


# ---------------------------------------------------------------------------
# Enhetstabellen (§2), maskinlesbar fasit


def enhetstabell() -> list[tuple[str, str, float]]:
    """(rå enhet, normalisert enhet, faktor) fra §2. K1 leser samme tabell."""
    rader = []
    rolle = ""
    for celler in _tabellrader(_seksjon(KONTRAKTTEKST, "## 2. Enhetstabell")):
        if celler[0].startswith("Rolle"):
            continue
        rolle = celler[0] or rolle
        for raa in _navn(celler[1]):
            rader.append((raa, _navn(celler[2])[0], _tall(celler[3])))
    return rader


ENHETER = enhetstabell()


def test_enhetstabellen_er_lest() -> None:
    """En tom tabell ville gjort resten av enhetstestene grønne uten å se noe."""
    assert len(ENHETER) >= 12


def test_enhetstabellen_har_ingen_dobbeltoppforing() -> None:
    """Samme enhetsstreng med to faktorer ville gjort normaliseringen tvetydig."""
    per_enhet: dict[str, set[tuple[str, float]]] = {}
    for raa, normalisert, faktor in ENHETER:
        per_enhet.setdefault(raa.lower(), set()).add((normalisert, faktor))
    for enhet, verdier in per_enhet.items():
        assert len(verdier) == 1, f"{enhet} har flere normaliseringer: {verdier}"


@pytest.mark.parametrize(("raa", "normalisert", "faktor"), ENHETER, ids=[e[0] for e in ENHETER])
def test_normaliseringen_er_dimensjonsriktig_begge_veier(raa: str, normalisert: str, faktor: float) -> None:
    """§2: en verdi normalisert og regnet tilbake er samme tall."""
    assert faktor > 0, raa
    assert normalisert in {"W", "kWh", "NOK/kWh"}
    for verdi in (0.0, 1.0, 1234.5678, 1e-4):
        assert verdi * faktor / faktor == pytest.approx(verdi, rel=1e-12, abs=1e-15)


def test_prisenhetene_henger_sammen() -> None:
    """De fire prisenhetene er hverandres tierpotenser, ikke fire løse tall."""
    faktor = {raa: f for raa, norm, f in ENHETER if norm == "NOK/kWh"}
    assert faktor["NOK/kWh"] == 1
    assert faktor["øre/kWh"] == pytest.approx(faktor["NOK/kWh"] / 100)
    assert faktor["NOK/MWh"] == pytest.approx(faktor["NOK/kWh"] / 1000)
    assert faktor["øre/MWh"] == pytest.approx(faktor["NOK/kWh"] / 100_000)


def test_energi_og_effektenhetene_henger_sammen() -> None:
    """Samme krav som for pris: tierpotenser av hverandre, ikke løse tall.

    Prisradene var bundet sammen, energi- og effektradene sto fritt, og en
    faktor 0,01 på `Wh` gikk rett gjennom vaktholdet.
    """
    kwh = {raa: f for raa, norm, f in ENHETER if norm == "kWh"}
    assert kwh["kWh"] == 1
    assert kwh["Wh"] == pytest.approx(kwh["kWh"] / 1000)
    assert kwh["MWh"] == pytest.approx(kwh["kWh"] * 1000)
    watt = {raa: f for raa, norm, f in ENHETER if norm == "W"}
    assert watt["W"] == 1
    assert watt["kW"] == pytest.approx(watt["W"] * 1000)
    assert watt["MW"] == pytest.approx(watt["W"] * 1_000_000)


def test_eur_avvises() -> None:
    """§2: EUR er ingen enhet vi kan regne om, siden vi ikke har noen kurs."""
    assert not [raa for raa, _, _ in ENHETER if "EUR" in raa.upper()]
    assert "feil_valuta" in KONTRAKTTEKST


# ---------------------------------------------------------------------------
# Grunn-strengene (§1)


def _grunner() -> dict[str, list[str]]:
    seksjon = _seksjon(KONTRAKTTEKST, "## 1. Typede inputresultater")
    ut: dict[str, list[str]] = {"Utilgjengelig": [], "Ugyldig": []}
    naavaerende = ""
    for linje in seksjon.splitlines():
        for type_ in ut:
            if linje.startswith(f"`{type_}`-grunner"):
                naavaerende = type_
        if naavaerende and linje.startswith("|"):
            celler = [c.strip() for c in linje.strip().strip("|").split("|")]
            navn = _navn(celler[0])
            if navn:
                ut[naavaerende].append(navn[0])
    return ut


GRUNNER = _grunner()


def test_grunnene_er_lest_og_entydige() -> None:
    """Diagnostikken og oversettelsene slår opp på disse, så de må være faste."""
    assert len(GRUNNER["Utilgjengelig"]) >= 4
    assert len(GRUNNER["Ugyldig"]) >= 7
    alle = GRUNNER["Utilgjengelig"] + GRUNNER["Ugyldig"]
    assert len(alle) == len(set(alle)), "samme grunn i begge tabellene"
    for grunn in alle:
        assert re.fullmatch(r"[a-zø_]+", grunn), grunn


def test_manglende_entitet_er_utilgjengelig_ikke_ugyldig() -> None:
    """En slettet sensor er en måling som ikke kommer, ikke en feilkonfigurasjon."""
    assert "finnes_ikke" in GRUNNER["Utilgjengelig"]
    assert "finnes_ikke" not in GRUNNER["Ugyldig"]


# ---------------------------------------------------------------------------
# Grensen for urimelig pris (§1), etter normalisering


def _urimelig_rad() -> str:
    """Raden for `urimelig_verdi` i grunntabellen i §1."""
    seksjon = _seksjon(KONTRAKTTEKST, "## 1. Typede inputresultater")
    return next(li for li in seksjon.splitlines() if "`urimelig_verdi`" in li and li.startswith("|"))


# Tallet og enheten det gjelder i må stå i samme setning. Leses de hver for seg,
# godtar vakten en rad som sier «over 2000 i sensorens egen enhet» så lenge
# frasen «etter normalisering» finnes et eller annet sted i dokumentet.
URIMELIG = re.compile(r"over (\d+) \*{0,2}etter\*{0,2} normalisering til `?NOK/kWh`?")


def _urimelig_grense() -> float:
    treff = URIMELIG.search(_urimelig_rad())
    assert treff, (
        "raden for `urimelig_verdi` må oppgi grensen og at den gjelder etter "
        f"normalisering til NOK/kWh, i samme setning. Raden er: {_urimelig_rad().strip()}"
    )
    return float(treff.group(1))


def test_urimelig_grense_avviser_ikke_ekte_spotpriser() -> None:
    """Funn 3: 2000 i sensorens egen enhet avviste en NOK/MWh-sensor i de dyre timene.

    2000 NOK/MWh er 2 NOK/kWh, og NO1, NO2 og NO5 har passert det. Grensen
    gjelder etter normalisering, og den skal ligge godt over ekte toppriser.
    Regnes den i sensorens egen enhet, feller `_urimelig_grense` raden.
    """
    grense = _urimelig_grense()
    faktor = {raa: f for raa, norm, f in ENHETER if norm == "NOK/kWh"}
    assert 2500 * faktor["NOK/MWh"] < grense, "en dyr time i NOK/MWh blir avvist"
    assert 700 * faktor["øre/kWh"] < grense
    assert grense >= 50, "grensen er så lav at den kan treffe ekte data"


def test_urimelig_grense_gjelder_absoluttverdien() -> None:
    """Negative spotpriser er gyldige (avregning.md B2) og skal ikke avvises.

    Kravet leses fra selve raden, ikke fra seksjonen: prosa lenger nede kan
    ikke holde liv i en rad som har mistet absoluttverdien.
    """
    assert "absoluttverdi" in _urimelig_rad()


# ---------------------------------------------------------------------------
# Terskelen for satsavvik (§8)


def _terskel() -> float:
    seksjon = _seksjon(KONTRAKTTEKST, "## 8. Når repair-varselet")
    treff = re.search(r"`(0,0[0-9]+)\s*NOK/kWh`", seksjon)
    assert treff, "fant ingen terskel i §8"
    return float(treff.group(1).replace(",", "."))


def test_terskelen_ligger_mellom_stoyen_og_minste_ekte_steg() -> None:
    """Funn 7: 0,0001 NOK/kWh slipper et ekte ett-øres-steg gjennom i flyttall."""
    terskel = _terskel()
    assert terskel > 0.00005 + 0.000006, "terskelen fanger v1-migreringens avrundingsstøy"
    assert terskel <= 0.4614 - 0.4613, "et ekte steg på 0,01 øre må passere i flyttall"
    assert abs(0.2915 - 0.2899) > terskel, "Elvias minste ekte endring må passere"


def test_varselet_reises_kun_ved_avvik() -> None:
    """Fredriks avgjørelse: ingen varsler til brukere som allerede ligger riktig."""
    seksjon = _seksjon(KONTRAKTTEKST, "## 8. Når repair-varselet")
    assert "**kun**" in seksjon


# ---------------------------------------------------------------------------
# Sensortabellen for ukjent fastledd (§9) mot sensor.py


def _sensornavn() -> list[str]:
    navn = []
    for celler in _tabellrader(_seksjon(KONTRAKTTEKST, "## 9. Egendefinert fastledd")):
        if not celler[0].startswith("`"):
            continue
        navn.extend(_navn(celler[0]))
    return navn


SENSORER = _sensornavn()
SENSORKILDE = _tekst(KOMPONENT / "sensor.py")


def test_sensortabellen_er_lest() -> None:
    assert len(SENSORER) >= 20


@pytest.mark.parametrize("navn", SENSORER, ids=SENSORER)
def test_sensorene_i_tabellen_finnes(navn: str) -> None:
    """Et navn i kontrakten som ikke finnes i sensor.py er en instruks til ingen."""
    if navn.endswith("*"):
        assert f'"{navn[:-1]}' in SENSORKILDE, f"ingen sensornøkkel starter med {navn[:-1]}"
    else:
        assert f'"{navn}"' in SENSORKILDE, f"{navn} står i §9, men finnes ikke i sensor.py"


def test_fastledd_ukjent_folger_monsteret_som_finnes() -> None:
    """§9 viser til `fastledd_mangler_sikringsvalg`, og det mønsteret må finnes."""
    assert "fastledd_mangler_sikringsvalg" in SENSORKILDE
    assert "fastledd_mangler_sikringsvalg" in _tekst(KOMPONENT / "coordinator.py")


# ---------------------------------------------------------------------------
# Oversettelsesnøkler (§11)


def _nokler_i_seksjon_11() -> list[str]:
    return _navn(_seksjon(KONTRAKTTEKST, "## 11. Nye nøkler"))


def _flate_nokler(data: object, prefiks: str = "") -> set[str]:
    if isinstance(data, dict):
        ut: set[str] = set()
        for nokkel, verdi in data.items():
            sti = f"{prefiks}.{nokkel}" if prefiks else nokkel
            ut.add(sti)
            ut |= _flate_nokler(verdi, sti)
        return ut
    return set()


def test_nokler_som_alt_finnes_star_i_alle_tre_filene() -> None:
    """§11 lover tre filer i synk. Nøklene K1 legger til fanges etter hvert som de lander."""
    filer = {
        "strings.json": _flate_nokler(json.loads(_tekst(KOMPONENT / "strings.json"))),
        "nb.json": _flate_nokler(json.loads(_tekst(KOMPONENT / "translations" / "nb.json"))),
        "en.json": _flate_nokler(json.loads(_tekst(KOMPONENT / "translations" / "en.json"))),
    }
    bladnavn = {navn: {sti.split(".")[-1] for sti in flat} for navn, flat in filer.items()}
    finnes = [n for n in _nokler_i_seksjon_11() if any(n in blad for blad in bladnavn.values())]
    assert finnes, "ingen av nøklene i §11 finnes ennå; K1 har ikke landet"
    for nokkel in finnes:
        mangler = [navn for navn, blad in bladnavn.items() if nokkel not in blad]
        assert not mangler, f"{nokkel} mangler i {mangler}"


# ---------------------------------------------------------------------------
# Grensesnittet mot avregningskontrakten


AVREGNINGSTEKST = _tekst(AVREGNING)


def test_baselinens_levetid_star_bare_ett_sted() -> None:
    """Funn 1: K0 og A0 sa hver sin ting om `TPI_STALE_HOURS`.

    Regelen eies av §5 her. Avregningskontrakten får nevne konstanten, men bare
    i et avsnitt som peker hit, aldri med sin egen regel.
    """
    assert "TPI_STALE_HOURS" in _seksjon(KONTRAKTTEKST, "## 5. Energibaseline")
    for linje in AVREGNINGSTEKST.splitlines():
        if "TPI_STALE_HOURS" not in linje:
            continue
        pytest.fail(f"avregning.md gjentar aldersgrensen: {linje.strip()}")
    assert "input-og-konfig.md#5-energibaseline" in AVREGNINGSTEKST, (
        "avregning.md C5 må peke hit for aldersgrensen"
    )


def test_vernet_kontrakten_peker_pa_finnes() -> None:
    """§5 gjør `MAX_ENERGY_DELTA_KWH` til hele vernet mot det gigantiske spranget."""
    assert "MAX_ENERGY_DELTA_KWH" in _tekst(KOMPONENT / "const.py")


def test_tpi_stale_hours_er_enten_i_bruk_eller_borte() -> None:
    """§5 pensjonerer aldersgrensen: K1 fjerner siste bruk og konstanten sammen.

    Vakten kan ikke kreve at navnet finnes, for da blir den rød i det K1 gjør
    det kontrakten ber om. Den kan heller ikke kreve at det er borte, for K1 har
    ikke landet ennå. Den krever det §5 faktisk sier: konstanten ligger aldri i
    `const.py` uten en bruker, og ingen bruker overlever konstanten.
    """
    navn = "TPI_STALE_HOURS"
    i_const = navn in _tekst(KOMPONENT / "const.py")
    brukere = sorted(
        sti.name for sti in KOMPONENT.glob("*.py") if sti.name != "const.py" and navn in _tekst(sti)
    )
    if i_const:
        assert brukere, f"{navn} står igjen i const.py uten bruker; §5 sier den skal ut"
    else:
        assert not brukere, f"{navn} er fjernet fra const.py, men brukes fortsatt i {brukere}"


def test_de_to_kontraktene_er_enige_om_store_versjonene() -> None:
    """§5 her definerer Store v2, og avregning.md D bygger v3 oppå den."""
    assert "Store-skjema v2" in KONTRAKTTEKST
    assert "| 2 | K1 |" in AVREGNINGSTEKST


def test_prisens_observasjonstid_eies_av_avregningskontrakten() -> None:
    """Funn 2: observasjonstid for pris står ett sted, og K0 peker dit."""
    assert "### A2.1" in AVREGNINGSTEKST
    assert "PRIS_SETTLE_SEKUNDER" in AVREGNINGSTEKST
    assert "avregning.md#a21-" in KONTRAKTTEKST


# ---------------------------------------------------------------------------
# Sensor uten enhet (§4 og §4.1)
#
# §4 avgjorde bare prissensoren. K1 måtte velge selv hva en effekt- eller
# energisensor uten enhet skulle bli, og valget lå i en kodekommentar. Nå står
# det i kontrakten, og her voktes det.


SEKSJON_4 = _seksjon(KONTRAKTTEKST, "## 4. Sensor uten enhet")


def test_alle_roller_uten_enhet_har_et_svar() -> None:
    """Funn 4: §4 sa bare hva en prissensor uten enhet skulle bli."""
    assert "### 4.1 Effekt- og energisensor uten enhet" in SEKSJON_4
    under = SEKSJON_4.split("### 4.1", 1)[1]
    assert "skal" in under, "regelen skal være et skal, ikke et bør"
    for rolle, enhet in (("effekt", "`W`"), ("energi", "`kWh`")):
        assert enhet in under, f"{rolle} uten enhet mangler sin antatte enhet"
    assert "avvises" in under, "det skal stå at sensoren ikke avvises"
    assert "repair" in under, "det skal stå om rollen får varsel eller ikke"


def test_antatt_enhet_er_synlig_i_diagnostikken() -> None:
    """Et stille valg skal i det minste være mulig å se at ble tatt."""
    under = SEKSJON_4.split("### 4.1", 1)[1]
    assert "`raa_enhet`" in under and "`None`" in under
    assert "raa_enhet" in _seksjon(KONTRAKTTEKST, "## 10. Hva coordinatoren eksponerer")


def test_varselet_om_prisenhet_gjelder_bare_prisrollene() -> None:
    """§4 og §4.1 skal ikke kunne leses som om effekt også får repair."""
    over = SEKSJON_4.split("### 4.1", 1)[0]
    assert "prisenhet_ubekreftet" in over
    assert "forbeholdt prisrollene" in SEKSJON_4


def test_et_varsel_for_effekt_og_energi_er_uavgjort_og_ikke_glemt() -> None:
    """Grensen går i §12, så den neste ikke tar avgjørelsen underveis."""
    assert "repair-varsel" in _seksjon(KONTRAKTTEKST, "## 12. Hva kontrakten ikke avgjør")


# ---------------------------------------------------------------------------
# Store-versjonen (§5)


SEKSJON_5 = _seksjon(KONTRAKTTEKST, "## 5. Energibaseline")


def test_skjemaversjonen_er_et_felt_i_dataene() -> None:
    """Funn 3: «Store-skjema v2» sa ikke hvilken versjon det var snakk om."""
    assert "`skjema_versjon`" in SEKSJON_5, "toppnivånøkkelen i filen skal navngis"
    assert "`schema_version`" in SEKSJON_5, "baselinens egen nøkkel skal navngis"
    assert "Store(hass, 1" in SEKSJON_5, "konstruktørens versjon skal stå eksplisitt"


def test_begrunnelsen_for_a_ikke_bumpe_star_der() -> None:
    """Uten grunnen ser valget vilkårlig ut, og den neste gjør det om.

    Begrunnelsen er en begrensning i testmiljøet, ikke et designvalg, og det
    er nettopp derfor den ikke lar seg utlede av noe annet i kontrakten.
    """
    assert "_async_migrate_func" in SEKSJON_5
    assert "MagicMock" in SEKSJON_5


def test_begrunnelsen_star_bare_ett_sted() -> None:
    """Samme feil som `TPI_STALE_HOURS`: to kontrakter med hver sin versjon.

    Avregningskontrakten får slå fast at konstruktøren blir stående, men
    begrunnelsen eies her, og den peker hit.
    """
    assert "_async_migrate_func" not in AVREGNINGSTEKST, (
        "avregning.md skal peke hit for hvorfor, ikke gjenta det"
    )
    assert "input-og-konfig.md#5-energibaseline" in AVREGNINGSTEKST


def test_koden_bumper_ikke_store_versjonen() -> None:
    """En regel koden får bryte er en anbefaling."""
    feil = [
        (sti.name, versjon)
        for sti in KOMPONENT.glob("*.py")
        for versjon in re.findall(r"Store\(\s*(?:self\.)?hass,\s*(\d+)", _tekst(sti))
        if versjon != "1"
    ]
    assert not feil, f"§5: Store-versjonen blir stående på 1, skjemaet står i dataene. {feil}"
