# Endringslogg og release

Dette er den samlede instruksen for CHANGELOG, release-noter og publisering. Les og følg den før du skriver eller endrer notene, endrer versjon eller releaseflyt, eller pusher til main. [AGENTS.md](../AGENTS.md#endringslogg-og-release) viser hit for at detaljene bare skal lastes når de trengs.

## Arbeidsrekkefølge

1. Før du skriver: kjør `gh release list` og sjekk om øverste CHANGELOG-seksjon er publisert. Slupne seksjoner er historikk; opprett `## [Ikke sluppet]` ved behov. Manifestversjonen alene sier ikke hvor nye endringer hører hjemme. Se [historikkregelen](#en-sluppet-seksjon-er-historikk).
2. Skriv for HACS etter reglene under. Merk bare brukerrelevante punkter med `<!--kort-->`, og bruk `### Dette må du gjøre selv` bare for nødvendige oppgraderingshandlinger. Bruk relative lenker til filer som finnes.
3. Generer og les den faktiske korte noten med `python3 scripts/release_notes.py "Ikke sluppet" --kort`, eller bruk versjonsnummeret når seksjonen er navngitt. Kontroller ordvalg, lengde og nødvendige handlinger; grønn CI vurderer ikke om teksten er god.
4. Før commit: kjør `just test`, og begge HA-målene når endringen krever det, som beskrevet i [testguiden](testing.md#testmiljøer). Endrer du releaseflyten, kjør også `just release-plan` og les resultatet. Den skriver ingenting til GitHub.
5. Før publisering: følg [publiseringsstegene](#publisering). Push til main starter releaseporten; alle kontrollene må være grønne for samme kandidat-SHA. Gjenoppta en feilet kjøring på samme commit.

## Skriv for HACS i Home Assistant

GitHub-release-bodyen vises i HACS inne i Home Assistant. Beskriv funksjoner, synlige feilrettinger og nødvendige handlinger i korte punkter. Lengden følger endringene, uten et fast antall punkter. Første release beskriver hva brukeren får; senere releaser beskriver forskjellen fra forrige versjon. Sjekk tidligere manifestversjoner i git før du omtaler en release som den første; manglende GitHub-releaser betyr ikke at tidligere versjoner mangler.

Leseren har allerede installert integrasjonen. Installasjon, dashbordoppsett og valgfrie blueprints hører hjemme i README. Kategorien `### Dette må du gjøre selv` er bare for handlinger som kreves ved oppgradering.

Bruk `<!--kort-->` bare på de brukerrettede punktene. Testtall, CI, refaktorering, datakildepinner og annen utviklerinformasjon kan stå i full CHANGELOG eller utviklerdokumentasjonen, uten kortmerke. Release-bodyen skal ikke fylles med commit-logg, SHA-er eller byggedetaljer. Tagg, ZIP og attestasjon kontrolleres av releaseporten; [SECURITY.md](../SECURITY.md) viser hvordan de etterprøves.

Les den genererte korte noten før publisering, med handlingene først og lenke til full endringslogg sist. Hvert punkt skal forklare hva brukeren får eller merker. En kort overskrift gjør ikke et langt avsnitt kort nok til en oppdateringsdialog.

## CHANGELOG.md

Det finnes én tekst, og den ligger i repoet. `## [X.Y.Z]`-seksjonen i `CHANGELOG.md` er kilden til alt brukerne får se; workflowen henter den med `scripts/release_notes.py`. Skriv den derfor som brukertekst, ikke som utviklerlogg.

Se selv hva en gitt versjon gir:

```bash
python3 scripts/release_notes.py 1.16.0         # hele seksjonen
python3 scripts/release_notes.py 1.16.0 --kort  # det som blir release-body
```

Exit 1 hvis seksjonen mangler, er tom, har en relativ lenke til en fil som ikke finnes, eller har en tom `### Dette må du gjøre selv`. Både `ci.yml` og `release.yml` henger på den exit-koden, så en versjon uten note blir aldri publisert.

## To utskrifter av den samme teksten

Seksjonen kommer ut på to måter, og begge er utledet av den ene filen. Ingen av dem skrives for hånd ved siden av.

Den lange er hele seksjonen, med «Dette må du gjøre selv» løftet øverst og relative lenker gjort absolutte. Det er den du leser i repoet og på GitHub, og det `release_notes.py <versjon>` skriver ut.

Den korte er release-body-en, altså det HACS viser i oppdateringspanelet inne i Home Assistant. Den består av hele «Dette må du gjøre selv», punktene som er merket med `<!--kort-->`, og en lenke til hele endringsloggen. `--kort` gir den, og `release_publish.py` bruker nettopp den når releasen publiseres.

### Merkingen

Sett `<!--kort-->` til slutt i punktene en bruker faktisk merker. Når kommentaren står først, renderer GitHubs CHANGELOG-visning noen ganger resten av punktet som rå tekst:

```markdown
### Fikset

- Månedskostnaden regner nå fastleddet uavhengig av forbruket. Tidligere kunne beløpet bli for høyt. <!--kort-->
- Fjellnett vekter nå en uke som krysser månedsskiftet med mandagens måned. <!--kort-->
```

Merket er en HTML-kommentar. Den er usynlig når `CHANGELOG.md` leses som markdown på GitHub, og fjernes fra begge utskriftene.

Punktene under «Dette må du gjøre selv» blir med i sin helhet og skal ikke merkes. Et merke der telles ikke som merket punkt.

Hva som fortjener et merke, er skjønn: det brukeren ser i grensesnittet eller i tallene sine. En avrundingsrettelse eller tydeligere oppsett kan være brukerrelevant; en ny testfixtur hører hjemme i full logg. Velg etter betydning, ikke for å fylle et bestemt antall punkter.

### Vakten

En seksjon under arbeid uten et eneste merket punkt feller med exit 1, både lokalt i `pytest tests/test_release_notes.py` og i `ci.yml`. En kort note som bare er en overskrift og en lenke sier mindre enn ingenting, så den skal ikke kunne publiseres. Feilmeldingen sier hvilken versjon det gjelder og viser merket.

Seksjonen «under arbeid» er den øverste i filen. Alt under den er sluppet og er historikk, og historikk merkes ikke i ettertid. Ber du om `--kort` for en gammel versjon, får du hele seksjonen hennes og en merknad på stderr i stedet for en feil.

## Stil

- Skriv hele avsnitt og listepunkter på én linje, uten manuell linjebryting.
- Bruk vanlige ord og konkrete endringer, uten fet ledetekst, reklamespråk eller mekanisk like punkter.
- Hold punktene korte og skannbare. Ikke gjenta hva prosjektet er.
- Bruk komma eller punktum fremfor em-dash.
- Krediter brukere som rapporterer feil med `@brukernavn` og issue-referanse.

Underoverskriftene er Keep a Changelog-kategoriene (`### Fikset`, `### Lagt til`, `### Endret`, `### Verifisert`, `### Dokumentert`), pluss `### Dette må du gjøre selv`. Ikke skriv noen `# v1.3.0`-heading, tittelen settes på selve releasen.

## Dette må du gjøre selv

Krever oppgraderingen noe aktivt av brukeren, som bytte av entitets-id, bekreftelse av et enhetsbytte eller et nytt felt som må velges, skal det stå i en egen `### Dette må du gjøre selv`-kategori. Kategorien utelates når ingen handling er nødvendig. Installasjon og valgfrie innstillinger skal ikke legges her.

```markdown
## [1.17.0]

### Dette må du gjøre selv

- Bekreft enhetsbyttet under Innstillinger > System > Reparasjoner etter oppgraderingen.

### Lagt til

- Ny `binary_sensor.maaledata_problem` som varsler når en input-sensor svikter
```

Du trenger ikke skrive den først i CHANGELOG; `release_notes.py` løfter den øverst i release-body-en uansett hvor i seksjonen den står, så den ikke drukner under «Lagt til» og «Fikset». Rekkefølgen skal ikke avhenge av at noen husker den. Overskriften matches uten hensyn til store bokstaver.

Står overskriften der uten punkter under seg, feiler scriptet med exit 1 og sier hvilken versjon og hvilken kategori det gjelder. Den løftes øverst uansett, så tom ville den blitt en naken overskrift på toppen av en publisert release. Blanke linjer teller ikke som innhold. Skriv punktene, eller slett overskriften.

## Lenker

Skriv relative lenker som ellers i repoet, altså `[incident 006](docs/incidents/006-kapasitetstrinn-uten-kilde.md)`. `release_notes.py` skriver dem om til absolutte URL-er mot taggen som slippes (`.../blob/v1.17.0/docs/...`) før de havner i release-body-en. Relative lenker er døde på en releaseside, og taggen brukes framfor `main` så lenken viser innholdet slik det var ved releasen, også om et år.

- Absolutte URL-er står urørt
- Anker uten fil (`#lagt-til`) peker på `CHANGELOG.md` i repoet, på riktig tag
- Peker en relativ lenke på en fil som ikke finnes, feiler scriptet med exit 1
  framfor å publisere en død lenke. Slett eller rett stien.
- Referansestil virker også: `[regler][r1]` med `[r1]: docs/domain-rules.md`
  nederst. Det er definisjonen som skrives om, siden det er der målet står.
- Mål i vinkelparenteser, `[x](<docs/en fil.md>)`, virker og er eneste måten å
  skrive en sti med mellomrom i. En sti med parentes i navnet må skrives slik.
- Autolenker (`<https://...>`) står urørt. De må ha et skjema for å være lenker,
  så de er alltid absolutte.

Flytter du en fil det lenkes til fra en usluppen seksjon, fanges det av `pytest tests/test_release_notes.py` lokalt og av CI, ikke først i release-jobben.

## Hva workflowen legger til

`release.yml` bruker bare den korte CHANGELOG-noten som release-body. «Dette må du gjøre selv» løftes øverst, relative lenker blir absolutte, og en lenke til hele endringsloggen legges sist. Byggeinformasjon og commit-logg legges ikke til. Tagg, ZIP og attestasjon verifiseres separat.

## En sluppet seksjon er historikk

Sjekk hva som faktisk er publisert før du skriver:

```bash
gh release list
git log "$(gh release view --json tagName --jq .tagName)..HEAD"
```

Er øverste seksjon allerede sluppet, lag en ny `## [Ikke sluppet]` over. Ellers beskriver du arbeid som brukerne ikke har fått, i notatene for en versjon de har. Versjonen i `manifest.json` er allerede bumpet ved release og viser derfor ikke alene hvilken seksjon nytt arbeid hører til.

Sjekkliste før du skriver i CHANGELOG:

- [ ] Er øverste seksjon sluppet? Da lager du en ny.
- [ ] Havnet arbeidet fra forrige runde faktisk i en seksjon?
- [ ] Beskriver punktet nettoresultatet? Rettes en feil i samme uslupne vindu
      som den ble innført, skal bare sluttilstanden stå der.
- [ ] Er punktet noe en bruker merker? Da får det `<!--kort-->`.

## Publisering

1. Døp `## [Ikke sluppet]` om til `## [X.Y.Z]`, les gjennom teksten som bruker,
   og se på den korte med `python3 scripts/release_notes.py X.Y.Z --kort`
2. Bump versjonen i `manifest.json` og `pyproject.toml`, kjør `uv lock` og ta
   med oppdatert prosjektversjon i `uv.lock`
3. Commit og push til main

Resten gjør `release.yml`. Den starter CI for nettopp den commiten, venter på hele grafen, og publiserer først når artefakten er bygget, lastet opp og verifisert.

### Releaseporten

Kandidaten er repo + full SHA + manifestversjon; tagg, ZIP og attestasjon skal være bundet til den samme kandidaten.

`release.yml` er den eneste workflowen som kjører på push til main. Den kaller `ci.yml` (`workflow_call`) for sin egen commit og har `needs: ci`, så unit, kvalitet, begge HA-målene, current-E2E, HACS-validering og Hassfest må være grønne for *samme SHA* før releasejobben starter. HACS og Hassfest kjøres også nattlig fra `validate.yml` og `hassfest.yml`, siden begge kan bli røde av endringer utenfor repoet.

`ci.yml` kaller `e2e.yml` for `just test-e2e target=current`. Docker-jobben sjekker ut kandidat-SHA-en og bygger release-ZIP fra den. Den kjører de åtte livssyklusscenarioene og juni-avspillingen, rydder Compose-prosjektet også ved feil og laster bare opp redigert evidens, merket med SHA. Den avsluttende `Releaseport`-jobben krever `success` fra alle seks testjobbene; manglende, feilet, kansellert eller hoppet over resultat stopper publisering. En grønn manuell eller tidligere E2E-kjøring kan ikke erstatte kandidatens kjøring. Docker inngår ikke i pre-push eller vanlig lokal `just test`.

`upgrade` og `vakthold` er egne Docker-løp utenfor denne automatiske porten; se [testlabens avgrensninger](../tests_e2e/README.md#hva-som-sjekkes).

Det som slippes, kommer fra hovedgrenen. To vakter sier det:

- `release.yml` kjører publiseringsjobben bare når ref-en er `main` eller en
  `v*`-tagg. En `workflow_dispatch` fra en annen gren kjører CI, og stopper der.
- `release_publish.py` spør GitHub om kandidaten er hovedgrenens spiss eller en
  commit den har passert (`compare`-status `identical` eller `behind`). Er den
  ikke det, stopper flyten før noe skrives. Vakten står i scriptet og ikke bare
  i workflowen, så den gjelder også når flyten kjøres for hånd.

Prøvekjøringen mot en engangstagg trenger en ekte workflow-kjøring for å få en attestasjon, og den må kunne gå fra en gren. Derfor finnes `proveslipp`, et eget felt i dispatch-skjemaet som gir `--proveslipp`. Den veien slipper bare manifestversjon `0.0.0` gjennom, og den releasen merkes som prerelease og blir aldri `latest`. Hukes feltet av på en gren med en ekte versjon, stopper flyten.

Selve flyten ligger i `scripts/release_publish.py`, som er dekket av `tests/test_release_publish.py`. Rekkefølgen er:

1. **Les tilstanden** (`plan`). Er versjonen sluppet fra før, bevises den mot
   sin egen tagg og jobben stopper der. Peker taggen på en annen commit, blir
   det full stopp.
2. **Bygg ZIP-en** (`build`) fra git-objektene på kandidat-SHA-en, ikke fra
   arbeidstreet. Bygget er deterministisk: faste tidsstempler, rettigheter fra
   git-modus, sortert rekkefølge. Samme commit gir byte-lik fil.
3. **Attester** bygget, før noe legges ut.
4. **Verifiser og publiser** (`publish`). Attestasjonen sjekkes mot repo,
   kilde-SHA, signer-workflow og ZIP-ens sha256. Taggen opprettes eksplisitt på
   SHA-en. Draften opprettes eller gjenopptas, ZIP-en lastes opp og *leses
   tilbake* med ny sha256-utregning. `draft=false` er siste kall.

### Når noe feiler halvveis

Det finnes ingen offentlig release før siste kall, så det er ingenting å rydde. Kjør jobben om igjen på samme commit («Re-run failed jobs» beholder SHA-en, eller kjør workflowen manuelt på taggen). Hvert steg er idempotent:

- Taggen finnes og peker riktig: den står, og flyttes aldri.
- Draften finnes: den gjenbrukes, og body-en skrives ikke over. Har du redigert
  den for hånd, blir redigeringen stående.
- Draften er laget for en *annen* commit: stopp, før taggen opprettes. Body-en
  sier hvilken commit ZIP-en er bygget fra, og den setningen skal ikke kunne
  bli usann fordi en draft ble stående igjen fra et tidligere forsøk. Slett
  draften, eller slipp endringen som en ny versjon. En draft du har laget i
  nettleseren peker på en gren og ikke en commit, og den gjenbrukes som før.
- ZIP-en ligger der alt: den lastes ned og sammenlignes. Stemmer sha256-en, er
  den ferdig. Stemmer den ikke, stopper flyten framfor å bytte en fil vi ikke
  vet hva er. HACS installerer nøyaktig den filen, så det er ikke et sted for
  automatikk. Slett asset-et bevisst, eller slipp en ny versjon.

En håndskrevet draft med samme tag er ikke lenger et problem som gjør at releasen aldri kommer ut. Flyten gjenopptar den og publiserer den.

### Se hva som ville skjedd

```bash
just release-zip            # bygg ZIP-en, se sha256-en
just release-plan           # les tilstanden på GitHub, skriv ingenting
just release-verify v1.16.0 # etterprøv en release som alt er ute
```

Ingen av dem skriver til GitHub. ZIP-bygg og verifisering bruker lokale arbeidsfiler. For en ny kandidat hopper `release-plan` over attestasjonssjekken, siden byggesteget ennå ikke har attestert noe. Er versjonen allerede publisert, kontrollerer `plan` også den eksisterende attestasjonen; eldre avvik kan rapporteres som advarsler, mens `verify` behandler dem strengt. I workflowen finnes også `workflow_dispatch` med `dry_run`, som ikke publiserer tagg eller release. For en ny kandidat kjører workflowen fortsatt bygg- og attesteringssteget; `dry_run` er derfor ikke en garanti mot at en attestasjon opprettes.

### Det v1.16.0 viser

`just release-verify v1.16.0` feiler fordi taggen og attestasjonen peker på ulike commits, og ZIP-en ikke er byte-reproduserbar fra taggen. Filinnholdet er kontrollert mot taggen. Se [sikkerhetsdokumentasjonen](../SECURITY.md) for hva verifiseringen dekker.

Ikke flytt publiserte tagger eller lag en ny attestasjon som påstår at et bygg ble produsert av en annen commit. En attestasjon skal beskrive byggingen som faktisk fant sted. Dokumenter avviket der brukerne finner verifiseringsinformasjonen.

## Retting etter publisering

Rett i CHANGELOG.md først, så teksten i repoet er fasiten, og speil den til releasen. `gh release edit --notes` overskriver hele body-en, så hent den eksisterende først. Eldre releaser har en Verifisering-del og commit-fold; behold disse når en historisk note rettes. Nye noter følger den korte brukerteksten:

```bash
gh release view vX.Y.Z --json body -q .body
```
