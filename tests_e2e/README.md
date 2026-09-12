# tests_e2e

Tom med vilje. Her skal Docker-laget bo: en fersk offisiell HA-container med
integrasjonen montert read-only, drevet gjennom serverens eget API. Det er et
annet lag enn de to andre:

- `tests/` regner uten Home Assistant i det hele tatt (HA er stubbet).
- `tests_ha/` kjører ekte HA i prosess, raskt, via
  pytest-homeassistant-custom-component.
- `tests_e2e/` skal kjøre en hel HA-server og verifisere livssyklus, ikke tall.

Innholdet hører til dcat-issue `stromkalkulator-6b54ywj` (T11b), som ligger
etter release 1.17.0. Kravene til harnesset står i kommentaren `6b54ywj-c2`:
låst image-tag, egen midlertidig config, Europe/Oslo, eget compose-prosjektnavn,
ingen produksjonsconfig og ingen supervisor-token.

`just test-e2e` finnes allerede, men feiler med en melding om at laget ikke er
bygget. Den skal ikke gjøres grønn ved å kjøre null tester.
