"""Drive only the test container's loopback HA API, with real config flows.

Executed with `docker compose exec ... python /harness/driver.py`. Credentials
belong to this throwaway HA user; they never appear in stdout or the trace.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import math
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiohttp

BASE = "http://127.0.0.1:8123"
AUTH = Path("/config/e2e-auth.json")
STATE = Path("/config/e2e-state.json")
TRACE = Path("/config/trace.jsonl")
INPUTS = ("energy", "energy_new", "power", "spot", "export")


def trace(name: str, **data: object) -> None:
    with TRACE.open("a") as stream:
        stream.write(json.dumps({"time": datetime.now(UTC).isoformat(), "scenario": name, **data}) + "\n")
    print(name, data, flush=True)


def near(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, abs_tol=0.002)


class Driver:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.auth = json.loads(AUTH.read_text())
        self.data = json.loads(STATE.read_text()) if STATE.exists() else {}

    def save(self) -> None:
        STATE.write_text(json.dumps(self.data))

    async def api(
        self, path: str, body: dict | None = None, *, method: str | None = None, form: dict | None = None
    ) -> object:
        headers = {"Authorization": f"Bearer {self.auth['token']}"} if self.auth.get("token") else {}
        async with self.session.request(
            method or ("POST" if body is not None or form else "GET"),
            BASE + path,
            json=body,
            data=form,
            headers=headers,
        ) as response:
            if response.status >= 400:
                # Do not include response bodies: auth errors can echo secrets.
                raise RuntimeError(f"API {path}: HTTP {response.status}")
            return await response.json()

    async def ws(self, type_: str, **payload: object) -> object:
        async with self.session.ws_connect(BASE + "/api/websocket") as ws:
            greeting = await ws.receive_json()
            if greeting["type"] != "auth_required":
                raise AssertionError("WebSocket mangler auth_required")
            await ws.send_json({"type": "auth", "access_token": self.auth["token"]})
            if (await ws.receive_json())["type"] != "auth_ok":
                raise AssertionError("WebSocket-auth feilet")
            await ws.send_json({"id": 1, "type": type_, **payload})
            result = await ws.receive_json()
            if not result.get("success"):
                raise AssertionError(f"WebSocket {type_} feilet")
            return result["result"]

    async def ready(self) -> None:
        """Vent til HA og allerede oppsatte Strømkalkulator-entiteter er klare.

        Etter en containerrestart svarer ``/api/`` før HA er ferdig startet.
        Et refresh-kall i det vinduet blir ignorert fordi entiteten ennå ikke
        finnes. Ved første oppstart finnes det ingen lagrede utganger, men ved
        alle senere scenarioer krever vi at hver lagret hovedsensor er lesbar.
        """
        deadline = time.monotonic() + 180
        sist: str | None = None
        while time.monotonic() < deadline:
            try:
                await self.api("/api/" if self.auth.get("token") else "/api/onboarding")
                if not self.auth.get("token"):
                    return
                config = await self.api("/api/config")
                if not isinstance(config, dict) or config.get("state") != "RUNNING":
                    sist = f"HA={config.get('state') if isinstance(config, dict) else config!r}"
                else:
                    mangler = []
                    for entry_id, utganger in self.data.get("utganger", {}).items():
                        entity = utganger.get("maanedlig_forbruk_total")
                        if not entity:
                            continue
                        try:
                            await self.state(entity)
                        except RuntimeError:
                            mangler.append(f"{entry_id}:{entity}")
                    if not mangler:
                        return
                    sist = f"mangler entitetene {', '.join(mangler)}"
            except (aiohttp.ClientError, RuntimeError, TimeoutError):
                sist = "API ikke klar"
            await asyncio.sleep(0.2)
        raise TimeoutError(f"HA startet ikke innen 180 sekunder ({sist})")

    async def state(self, entity: str) -> dict:
        return await self.api(f"/api/states/{entity}")

    async def wait_state(self, entity: str, predicate, *, timeout: int = 35) -> dict:
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            try:
                last = await self.state(entity)
                if predicate(last):
                    return last
            except RuntimeError:
                pass
            await asyncio.sleep(0.2)
        raise AssertionError(f"Ingen forventet state for {entity}: {last and last['state']}")

    async def service(self, domain: str, name: str, **data: object) -> None:
        await self.api(f"/api/services/{domain}/{name}", data)

    async def identify(self) -> None:
        entries = await self.ws("config/entity_registry/list")
        registry = {
            entry["unique_id"]: entry["entity_id"] for entry in entries if entry["platform"] == "template"
        }
        self.data["inputs"] = {key: registry[f"e2e_{key}"] for key in INPUTS}
        self.data["utganger"] = {}
        for navn in ("entry_id", "custom_entry_id"):
            entry_id = self.data.get(navn)
            if entry_id:
                self.data["utganger"][entry_id] = {
                    entry["unique_id"].removeprefix(f"{entry_id}_"): entry["entity_id"]
                    for entry in entries
                    if entry["platform"] == "stromkalkulator" and entry["config_entry_id"] == entry_id
                }
        if self.data.get("entry_id"):
            outputs = self.data["utganger"][self.data["entry_id"]]
            self.data["total"] = outputs["maanedlig_forbruk_total"]
            self.data["export"] = outputs["maanedlig_eksport_kwh"]
        self.save()

    def utgang(self, suffix: str, entry_id: str | None = None) -> str:
        """Entity-id-en bak et unique_id-suffiks, uavhengig av navn og språk."""
        return str(self.data["utganger"][entry_id or self.data["entry_id"]][suffix])

    async def aktiver(self, *suffixes: str, entry_id: str | None = None) -> None:
        """Slå på sensorer som er avskrudd i registeret, og last entryet på nytt.

        Flere av kronesensorene er `entity_registry_enabled_default = False`.
        Uten dette steget finnes de ikke som entiteter, og en test som leser
        dem ville målt registerets default framfor integrasjonens tall.
        """
        entry_id = entry_id or self.data["entry_id"]
        for suffix in suffixes:
            await self.ws(
                "config/entity_registry/update", entity_id=self.utgang(suffix, entry_id), disabled_by=None
            )
        await self.api(f"/api/config/config_entries/entry/{entry_id}/reload", {})
        await self.identify()
        for suffix in suffixes:
            await self.wait_state(
                self.utgang(suffix, entry_id), lambda state: state["state"] != "unavailable", timeout=60
            )

    async def set_input(self, key: str, value: float) -> None:
        await self.service("input_number", "set_value", entity_id=f"input_number.e2e_{key}", value=value)
        await self.wait_state(
            self.data["inputs"][key],
            lambda state: (
                state["state"] not in ("unknown", "unavailable")
                and math.isclose(float(state["state"]), value, abs_tol=0.000001)
            ),
        )

    async def override(self, key: str, value: str, unit: str | None = None, *, delete: bool = False) -> None:
        entity = self.data["inputs"][key]
        state = await self.state(entity)
        self.data.setdefault("overrides", {}).setdefault(key, state)
        self.save()
        if delete:
            await self.api(f"/api/states/{entity}", method="DELETE")
            return
        attrs = dict(state["attributes"])
        if unit is not None:
            attrs["unit_of_measurement"] = unit
        await self.api(f"/api/states/{entity}", {"state": value, "attributes": attrs})

    async def recover_inputs(self) -> None:
        for key, old in self.data.pop("overrides", {}).items():
            await self.api(
                f"/api/states/{self.data['inputs'][key]}",
                {"state": old["state"], "attributes": old["attributes"]},
            )
        self.save()
        await self.refresh(settle=True)

    async def refresh(self, *, settle: bool = False) -> None:
        await self.service("homeassistant", "update_entity", entity_id=self.data["total"])
        if settle:
            # HA coalesces manual updates for 10 s. A no-change assertion must
            # outlive that window, otherwise it can pass before HA has polled.
            await asyncio.sleep(11)

    async def total(self) -> float:
        state = await self.state(self.data["total"])
        return float(state["state"])

    async def expect_total(self, expected: float) -> None:
        await self.refresh()
        await self.wait_state(
            self.data["total"],
            lambda state: (
                state["state"] not in ("unknown", "unavailable") and near(float(state["state"]), expected)
            ),
        )

    async def bootstrap(self) -> None:
        answer = await self.api(
            "/api/onboarding/users",
            {
                "name": "Testlab",
                "username": self.auth["username"],
                "password": self.auth["password"],
                "client_id": BASE + "/",
                "language": "en",
            },
        )
        tokens = await self.api(
            "/auth/token",
            form={
                "grant_type": "authorization_code",
                "code": answer["auth_code"],
                "client_id": BASE + "/",
            },
        )
        self.auth["token"] = tokens["access_token"]
        # Finish onboarding with the credential-bound login token. HA's final
        # integration step rejects long-lived tokens, which have no credential.
        AUTH.write_text(json.dumps(self.auth))
        AUTH.chmod(0o600)
        status = await self.api("/api/onboarding")
        done = {row["step"] for row in status if row["done"]}
        for step, body in (
            ("core_config", {}),
            ("analytics", {}),
            ("integration", {"client_id": BASE + "/", "redirect_uri": BASE + "/"}),
        ):
            if step not in done:
                await self.api(f"/api/onboarding/{step}", body)
        # A lab may stay open for manual multi-hour outage checks. This local
        # token survives restart and avoids an expiring onboarding access token.
        self.auth["token"] = await self.ws("auth/long_lived_access_token", client_name="testlab", lifespan=1)
        AUTH.write_text(json.dumps(self.auth))
        # The frontend is now usable. Resolve templates by stable unique_id.
        for _ in range(60):
            try:
                await self.identify()
                break
            except KeyError:
                await asyncio.sleep(1)
        await self.set_input("energy", 10000)
        await self.set_input("energy_new", 50000)
        await self.set_input("power", 1000)
        await self.set_input("spot", 0.8)
        await self.set_input("export", 0)

    async def test_onboarding(self) -> None:
        flow = await self.api("/api/config/config_entries/flow", {"handler": "stromkalkulator"})
        assert flow["type"] == "form" and flow["step_id"] == "user", "DSO-steg mangler"
        flow = await self.api(
            f"/api/config/config_entries/flow/{flow['flow_id']}",
            {"tso": "bkk", "boligtype": "bolig", "har_norgespris": True},
        )
        assert flow["step_id"] == "sensors", "Sensorsteg mangler"
        self.data["config"] = {
            "tso": "bkk",
            "boligtype": "bolig",
            "har_norgespris": True,
            "power_sensor": self.data["inputs"]["power"],
            "spot_price_sensor": self.data["inputs"]["spot"],
            "energy_sensor": self.data["inputs"]["energy"],
            "export_power_sensor": self.data["inputs"]["export"],
            "spotpris_inkl_mva": False,
        }
        sensors = {
            key: value
            for key, value in self.data["config"].items()
            if key not in ("tso", "boligtype", "har_norgespris")
        }
        flow = await self.api(f"/api/config/config_entries/flow/{flow['flow_id']}", sensors)
        assert flow["type"] == "create_entry", f"Config flow feilet: {flow.get('errors')}"
        self.data["entry_id"] = flow["result"]["entry_id"]
        self.data["energy_key"] = "energy"
        self.save()
        for _ in range(60):
            try:
                await self.identify()
                break
            except KeyError:
                await asyncio.sleep(1)
        await self.expect_total(0)

    async def test_energy_increase(self) -> None:
        before = await self.total()
        key = self.data["energy_key"]
        counter = float((await self.state(self.data["inputs"][key]))["state"])
        await self.set_input(key, counter + 1.25)
        await self.expect_total(before + 1.25)

    async def checkpoint_restart(self) -> None:
        await self.refresh(settle=True)
        self.data["before_restart"] = await self.total()
        self.save()

    async def test_restart_no_double_booking(self) -> None:
        await self.identify()
        await self.expect_total(self.data["before_restart"])
        await self.refresh(settle=True)
        assert near(await self.total(), self.data["before_restart"]), "Restart dobbeltbokførte energi"
        await self.test_energy_increase()

    async def options(self) -> None:
        flow = await self.api("/api/config/config_entries/options/flow", {"handler": self.data["entry_id"]})
        # Use required defaults from the returned schema; optional omissions
        # remain omitted, which is how HA expresses removal of an optional input.
        payload = dict(self.data["config"])
        for field in flow["data_schema"]:
            if field.get("required") and "default" in field:
                payload.setdefault(field["name"], field["default"])
        result = await self.api(f"/api/config/config_entries/options/flow/{flow['flow_id']}", payload)
        assert result["type"] == "create_entry", f"Options feilet: {result.get('errors')}"
        self.save()
        # Explicit reload completes the lifecycle even if an automatic reload
        # races with the flow response; the server owns both config and storage.
        await self.api(f"/api/config/config_entries/entry/{self.data['entry_id']}/reload", {})
        await self.identify()

    async def test_meter_change(self) -> None:
        before = await self.total()
        self.data["energy_key"] = "energy_new"
        self.data["config"]["energy_sensor"] = self.data["inputs"]["energy_new"]
        await self.options()
        await self.expect_total(before)
        await self.refresh(settle=True)
        assert near(await self.total(), before), "Ny fysisk målers baseline ble bokført som forbruk"
        await self.test_energy_increase()

    async def test_remove_optional(self) -> None:
        await self.ws("config/entity_registry/update", entity_id=self.data["export"], disabled_by=None)
        await self.api(f"/api/config/config_entries/entry/{self.data['entry_id']}/reload", {})
        await self.wait_state(
            self.data["export"], lambda state: state["state"] not in ("unknown", "unavailable")
        )
        before = await self.total()
        self.data["config"].pop("export_power_sensor", None)
        await self.options()
        # Keep the source valid: an unavailable output must be caused by the
        # removed optional configuration, not by a second input failure.
        await self.override("export", "100")
        await self.refresh(settle=True)
        await self.wait_state(self.data["export"], lambda state: state["state"] == "unavailable")
        assert near(await self.total(), before)
        entries = await self.api("/api/config/config_entries/entry")
        assert any(row["entry_id"] == self.data["entry_id"] and row["state"] == "loaded" for row in entries)
        await self.recover_inputs()

    async def issues(self) -> dict[str, dict]:
        result = await self.ws("repairs/list_issues")
        return {row["issue_id"]: row for row in result["issues"] if row["domain"] == "stromkalkulator"}

    async def issue_present(self, prefix: str, entry_id: str | None = None) -> bool:
        return f"{prefix}_{entry_id or self.data['entry_id']}" in await self.issues()

    async def test_invalid_unit_recovery(self) -> None:
        await self.override("power", "1000", "bananas")
        await self.refresh(settle=True)
        assert await self.issue_present("input_enhet"), "Ugyldig enhet fikk ingen repair"
        await self.recover_inputs()
        assert not await self.issue_present("input_enhet"), "Repair overlevde frisk input"

    async def test_missing_input_recovery(self) -> None:
        before = await self.total()
        await self.override(self.data["energy_key"], "unavailable", delete=True)
        await self.refresh(settle=True)
        assert near(await self.total(), before), "Manglende energisensor ga falskt forbruk"
        await self.recover_inputs()
        await self.test_energy_increase()

    async def test_meter_jump(self) -> None:
        before = await self.total()
        key = self.data["energy_key"]
        counter = float((await self.state(self.data["inputs"][key]))["state"])
        await self.set_input(key, counter + 1000)
        await self.refresh(settle=True)
        assert near(await self.total(), before), "1000 kWh sprang ble bokført"
        # The next normal increment must work; rejecting everything forever is
        # not recovery. The rejected jump establishes the new counter baseline.
        await self.test_energy_increase()

    # --- Oppgraderingsveien fra en sluppet utgave ---

    AKKUMULATORER = (
        "maanedlig_forbruk_total",
        "maanedlig_forbruk_dag",
        "maanedlig_forbruk_natt",
        "forrige_maaned_forbruk_total",
        "forrige_maaned_forbruk_dag",
        "forrige_maaned_forbruk_natt",
        "maks_forbruk_1",
        "maks_forbruk_2",
        "maks_forbruk_3",
        "gjennomsnitt_forbruk",
        "forrige_maaned_toppforbruk",
    )
    KAPASITETSAVHENGIGE = (
        "kapasitetstrinn",
        "margin_neste_trinn",
        "trinn_nummer",
        "maanedlig_nettleie",
        "maanedlig_total",
        "akkumulert_kostnad",
        "estimated_monthly_cost",
    )
    UBEROERT_AV_FASTLEDDET = (
        "energiledd",
        "maanedlig_forbruk_total",
        "maanedlig_avgifter",
        "stromstotte",
    )

    async def test_onboarding_egendefinert(self) -> None:
        """Et andre anlegg på Egendefinert, uten kapasitetstrinn.

        Feltet for trinntabellen finnes ikke i 1.16.0 og er valgfritt i dag, så
        den samme nyttelasten går gjennom begge utgavene. Det er hele poenget:
        anlegget skal settes opp slik en bruker på 1.16.0 faktisk har det.
        """
        flow = await self.api("/api/config/config_entries/flow", {"handler": "stromkalkulator"})
        flow = await self.api(
            f"/api/config/config_entries/flow/{flow['flow_id']}",
            {"tso": "custom", "boligtype": "bolig", "har_norgespris": False},
        )
        assert flow["step_id"] == "sensors", "Sensorsteg mangler for egendefinert"
        flow = await self.api(
            f"/api/config/config_entries/flow/{flow['flow_id']}",
            {
                # Egen effektsensor: duplikatvernet nekter to anlegg på samme.
                "power_sensor": self.data["inputs"]["export"],
                "spot_price_sensor": self.data["inputs"]["spot"],
                "energy_sensor": self.data["inputs"]["energy_new"],
                "spotpris_inkl_mva": False,
            },
        )
        assert flow["step_id"] == "pricing", "Egendefinert hoppet over prissteget"
        flow = await self.api(
            f"/api/config/config_entries/flow/{flow['flow_id']}",
            {"avgiftssone": "standard", "energiledd_dag": 0.3141, "energiledd_natt": 0.2141},
        )
        assert flow["type"] == "create_entry", f"Egendefinert flow feilet: {flow.get('errors')}"
        self.data["custom_entry_id"] = flow["result"]["entry_id"]
        self.save()
        for _ in range(60):
            try:
                await self.identify()
                break
            except KeyError:
                await asyncio.sleep(1)

    async def _oppdater_alle(self) -> None:
        for entry_id in self.data["utganger"]:
            await self.service(
                "homeassistant", "update_entity", entity_id=self.utgang("maanedlig_forbruk_total", entry_id)
            )

    async def seed_akkumulatorer(self) -> None:
        """Kjør opp akkumulatorene på den gamle utgaven.

        Uten forbruk, effekttopper og kroner på begge anlegg måler
        oppgraderingstesten ingenting: null overlever alltid.
        """
        await self.aktiver(
            "akkumulert_kostnad", "maanedlig_nettleie", "maanedlig_total", "maanedlig_nettokostnad"
        )
        for effekt, kwh in ((3500.0, 2.0), (7250.0, 3.5), (1800.0, 1.5)):
            await self.set_input("power", effekt)
            await self.set_input("export", round(effekt / 2, 3))
            for key in ("energy", "energy_new"):
                teller = float((await self.state(self.data["inputs"][key]))["state"])
                await self.set_input(key, round(teller + kwh, 3))
            await self._oppdater_alle()
            await asyncio.sleep(11)
        trace("seed_akkumulatorer", total_kwh=round(await self.total(), 3))

    async def _snapshot(self) -> dict:
        bilde: dict[str, dict] = {}
        for entry_id, utganger in self.data["utganger"].items():
            rad: dict[str, object] = {}
            for suffix in (*self.AKKUMULATORER, *self.KAPASITETSAVHENGIGE, "maanedlig_nettokostnad"):
                if suffix not in utganger:
                    continue
                try:
                    state = await self.state(utganger[suffix])
                except RuntimeError:
                    # Avskrudd i registeret: den finnes i registeret, men har
                    # ingen state. Da er den heller ikke noe å sammenligne.
                    continue
                rad[suffix] = {
                    "state": state["state"],
                    "forbrukskostnad_kr": state["attributes"].get("forbrukskostnad_kr"),
                    "kapasitetsledd_kr": state["attributes"].get("kapasitetsledd_kr"),
                    "fastledd_ukjent": state["attributes"].get("fastledd_ukjent"),
                }
            bilde[entry_id] = rad
        return bilde

    async def _statistikk(self, entity: str) -> list[dict]:
        rader = await self.ws(
            "recorder/statistics_during_period",
            start_time=self.data["oppgradering_start"],
            statistic_ids=[entity],
            period="5minute",
            types=["state", "sum"],
        )
        return [punkt for punkt in rader.get(entity, []) if punkt.get("state") is not None and "sum" in punkt]

    async def checkpoint_oppgradering(self) -> None:
        await self._oppdater_alle()
        await asyncio.sleep(11)
        self.data["for_oppgradering"] = await self._snapshot()
        self.data["bkk_entry"] = self.data["entry_id"]
        self.save()
        # Vent til recorderen har kompilert minst ett punkt med det gamle
        # nivået. Skjer oppgraderingen før det, står bare det nye nivået i
        # serien, og en test på skiftet ville ikke hatt noe å sammenligne med.
        entity = self.utgang("akkumulert_kostnad", self.data["bkk_entry"])
        frist = time.monotonic() + 8 * 60
        punkter: list[dict] = []
        while time.monotonic() < frist and not punkter:
            punkter = await self._statistikk(entity)
            if not punkter:
                await asyncio.sleep(20)
        assert punkter, f"Recorderen kompilerte ingen statistikk for {entity} før oppgraderingen"
        self.data["statistikk_for"] = punkter[-1]
        self.save()
        trace(
            "checkpoint_oppgradering",
            anlegg=len(self.data["for_oppgradering"]),
            statistikkpunkter_for=len(punkter),
            siste_state_for=punkter[-1]["state"],
        )

    async def test_oppgradering_beholder_akkumulatorene(self) -> None:
        """En bruker på 1.16.0 skal ikke miste noe ved å oppgradere.

        Månedsforbruk, døgnmaks og forrige måned sammenlignes tall for tall.
        Kronesensorene er ikke med her: fastleddet er med vilje regnet om, og
        det er `test_fastleddet_er_et_periodebelop` som eier det skiftet.
        """
        await self.identify()
        await self._oppdater_alle()
        await asyncio.sleep(11)
        etter = await self._snapshot()
        for_ = self.data["for_oppgradering"]
        assert set(etter) == set(for_), "Et anlegg forsvant i oppgraderingen"
        avvik = []
        for entry_id, rad in for_.items():
            for suffix in self.AKKUMULATORER:
                if suffix not in rad:
                    continue
                gammel, ny = rad[suffix]["state"], etter[entry_id][suffix]["state"]
                if gammel in ("unknown", "unavailable") or near(float(gammel), float(ny)):
                    continue
                avvik.append(f"{suffix}: {gammel} -> {ny}")
        assert not avvik, f"Oppgraderingen mistet akkumulatorer: {avvik}"
        entries = await self.api("/api/config/config_entries/entry")
        vaare = {row["entry_id"]: row for row in entries if row["domain"] == "stromkalkulator"}
        assert set(vaare) == set(for_), "Anlegg forsvant fra config entries"
        for entry_id, row in vaare.items():
            assert row["state"] == "loaded", f"{entry_id} lastet ikke etter oppgraderingen"
        trace(
            "test_oppgradering_beholder_akkumulatorene",
            anlegg=len(for_),
            sjekkede_sensorer=sum(len(set(rad) & set(self.AKKUMULATORER)) for rad in for_.values()),
        )

    async def test_baselinen_forkastes_en_gang(self) -> None:
        """Den gamle råverdien er ikke en kilde, så den skal ikke gjenopptas.

        Det brukeren merker er at neste avlesning setter ny baseline med delta
        0. Går den gamle verdien inn som baseline igjen, blir differansen mot
        dagens tellerstand bokført som forbruk hen aldri har hatt.
        """
        before = await self.total()
        await self._oppdater_alle()
        await asyncio.sleep(11)
        assert near(await self.total(), before), "Forkastet baseline ga et sprang i månedsforbruket"
        await self.test_energy_increase()

    async def test_fastleddet_er_et_periodebelop(self) -> None:
        """Fastleddet skal være en andel av månedsbeløpet, ikke en pris per kWh.

        Den gamle koden la `kapasitetsledd / timer i måneden` inn i kWh-prisen
        og akkumulerte den mot forbruket, samtidig som et helt annet
        tidsbasert drypp gikk i `monthly_accumulated_cost_kapasitetsledd`. De
        to kunne ikke bli enige. Her er prøven at de nå er samme tall, og at
        kapasitetsleddet ikke rikker seg av at forbruket gjør det.
        """
        entry_id = self.data.get("bkk_entry") or self.data["entry_id"]
        netto = await self.state(self.utgang("maanedlig_nettokostnad", entry_id))
        akkumulert = await self.state(self.utgang("akkumulert_kostnad", entry_id))
        forbrukskostnad = float(netto["attributes"]["forbrukskostnad_kr"])
        # Toleransen er en halv øre, for `monthly_cost_kr` er avrundet til to
        # desimaler i coordinatoren mens sensorens state er hele tallet.
        assert math.isclose(forbrukskostnad, float(akkumulert["state"]), abs_tol=0.01), (
            f"monthly_cost_kr {forbrukskostnad} != akkumulert kostnad {akkumulert['state']}"
        )
        fastledd = float(akkumulert["attributes"]["kapasitetsledd_kr"])
        assert fastledd > 0, "Fastleddet påløper ikke"
        for_ = self.data["for_oppgradering"][entry_id]["maanedlig_nettokostnad"]["forbrukskostnad_kr"]
        gammel_fastledd = self.data["for_oppgradering"][entry_id]["akkumulert_kostnad"]["kapasitetsledd_kr"]
        # Forbruket dobles uten at fastleddet skal røre seg: et periodebeløp
        # kjenner ikke kilowattimene.
        key = self.data["energy_key"]
        teller = float((await self.state(self.data["inputs"][key]))["state"])
        await self.set_input(key, round(teller + 8.0, 3))
        await self._oppdater_alle()
        await asyncio.sleep(11)
        etterpaa = await self.state(self.utgang("akkumulert_kostnad", entry_id))
        nytt_fastledd = float(etterpaa["attributes"]["kapasitetsledd_kr"])
        assert math.isclose(nytt_fastledd, fastledd, abs_tol=0.5), (
            f"8 kWh forbruk flyttet fastleddet: {fastledd} -> {nytt_fastledd}"
        )
        trace(
            "test_fastleddet_er_et_periodebelop",
            gammel_monthly_cost_kr=for_,
            ny_monthly_cost_kr=forbrukskostnad,
            gammelt_kapasitetsledd_kr=gammel_fastledd,
            nytt_kapasitetsledd_kr=fastledd,
        )

    async def test_statistikken_folger_skiftet(self) -> None:
        """Skiftet i kronene skal stå i statistikken som et skifte.

        Akkumulert kostnad er `state_class: total` med månedlig `last_reset`.
        Endrer tallet seg brått ved en oppgradering, skal recorderen bokføre
        differansen. Leses det i stedet som en nullstilling, legges hele det
        nye nivået oppå det gamle, og brukeren får en sum som teller måneden
        sin to ganger.
        """
        entity = self.utgang("akkumulert_kostnad", self.data["bkk_entry"])
        # Recorderen kompilerer kortidsstatistikk hvert femte minutt på hel
        # klokke. Checkpointet ventet på punktet med det gamle nivået, så her
        # venter vi bare på det første punktet etter oppgraderingen.
        forste = self.data["statistikk_for"]["start"]
        punkter: list[dict] = []
        frist = time.monotonic() + 13 * 60
        while time.monotonic() < frist and not any(p["start"] > forste for p in punkter):
            punkter = await self._statistikk(entity)
            if not any(p["start"] > forste for p in punkter):
                await asyncio.sleep(20)
        rader = [(p["state"], p["sum"]) for p in punkter]
        assert len(rader) >= 2, f"Statistikken rakk ikke et punkt etter oppgraderingen: {punkter}"
        par = list(itertools.pairwise(rader))
        skifte = max(abs(b[0] - a[0]) for a, b in par)
        assert skifte > 1, f"Oppgraderingen flyttet ikke kronene; da måler testen ingenting: {rader}"
        for forrige, naa in par:
            assert math.isclose(naa[1] - forrige[1], naa[0] - forrige[0], abs_tol=0.02), (
                f"Summen fulgte ikke differansen: {forrige} -> {naa}"
            )
        trace(
            "test_statistikken_folger_skiftet",
            punkter=len(rader),
            forste_state=rader[0][0],
            siste_state=rader[-1][0],
            storste_skifte=round(skifte, 2),
            siste_sum=rader[-1][1],
        )

    async def merk_oppgraderingsstart(self) -> None:
        """Startpunktet statistikkspørringen leser fra.

        Tilbakedatert et kvarter fordi `statistics_during_period` bare gir
        bøtter som *starter* etter `start_time`. Bøtten vi trenger, den med
        nivået før oppgraderingen, begynte før vi rakk å spørre.
        """
        self.data["oppgradering_start"] = (datetime.now(UTC) - timedelta(minutes=15)).isoformat()
        self.save()

    # --- De tre brukersynlige endringene ---

    async def test_egendefinert_uten_fastledd(self) -> None:
        """Ukjent på det kapasitetsavhengige, tall på resten, og et varsel.

        Egendefinert hadde ti innebygde trinn til og med 1.16.0. De var en mal
        uten prisliste bak seg, så anlegget viste et plausibelt og feil beløp.
        Etter K3 står de sensorene som Ukjent, og varselet sier hvorfor.
        """
        entry_id = self.data["custom_entry_id"]
        await self.aktiver(
            "akkumulert_kostnad",
            "maanedlig_nettleie",
            "maanedlig_avgifter",
            "trinn_nummer",
            entry_id=entry_id,
        )
        await self._oppdater_alle()
        await asyncio.sleep(11)
        ukjente, tall = [], []
        for suffix in self.KAPASITETSAVHENGIGE:
            state = await self.state(self.utgang(suffix, entry_id))
            if state["state"] != "unknown":
                tall.append(f"{suffix}={state['state']}")
        assert not tall, f"Kapasitetsavhengige sensorer har tall uten trinntabell: {tall}"
        # Motstykket: den gamle utgaven viste tall her. Uten dette leddet kunne
        # testen bestått på et anlegg som aldri hadde noe å miste.
        var_tall = {
            suffix: rad["state"]
            for suffix, rad in self.data["for_oppgradering"][entry_id].items()
            if suffix in self.KAPASITETSAVHENGIGE and rad["state"] not in ("unknown", "unavailable")
        }
        assert var_tall, "Egendefinert viste ingen kapasitetstall før oppgraderingen heller"
        for suffix in self.UBEROERT_AV_FASTLEDDET:
            state = await self.state(self.utgang(suffix, entry_id))
            if state["state"] in ("unknown", "unavailable"):
                ukjente.append(suffix)
        assert not ukjente, f"Sensorer uten fastledd i seg ble også ukjente: {ukjente}"
        issues = await self.issues()
        varsel = issues.get(f"egendefinert_fastledd_{entry_id}")
        assert varsel, "Egendefinert uten trinntabell fikk ingen forklaring"
        assert varsel["translation_key"] == "egendefinert_fastledd", varsel["translation_key"]
        assert not await self.issue_present("egendefinert_fastledd"), (
            "BKK-anlegget fikk fastledd-varselet det ikke skal ha"
        )
        trace(
            "test_egendefinert_uten_fastledd",
            varsel=varsel["translation_key"],
            gjettede_tall_for=var_tall,
        )

    async def test_satsvarsel_kun_ved_avvik(self) -> None:
        """Varselet skal reises for den som avviker, og bare for den.

        Et varsel hos alle ville vært en falsk positiv hos de fleste. BKK ble
        satt opp fra katalogen og har ingenting å velge mellom; anlegget vi
        selv taster en annen sats på, har det.
        """
        bkk = self.data.get("bkk_entry") or self.data["entry_id"]
        assert not await self.issue_present("tariff_ubekreftet", bkk), "Katalogsats reiste satsvarselet"
        assert not await self.issue_present("tariff_ubekreftet", self.data["custom_entry_id"]), (
            "Egendefinert er brukerens egne tall og skal ikke få satsvarselet"
        )
        trace("test_satsvarsel_kun_ved_avvik", anlegg=len(self.data["utganger"]))

    async def vent_paa_lastet(self, entry_id: str, *, timeout: int = 120) -> None:
        """Vent til entryet er `loaded`.

        Varslene reises i `async_setup_entry`. REST-API-et svarer før entryene
        er satt opp, så en sjekk rett etter oppstart kan lese issue-registeret
        mens integrasjonen ennå ikke har kjørt, og melde at varselet uteble.
        """
        frist = time.monotonic() + timeout
        tilstand = None
        while time.monotonic() < frist:
            entries = await self.api("/api/config/config_entries/entry")
            rad = next((row for row in entries if row["entry_id"] == entry_id), None)
            tilstand = rad and rad["state"]
            if tilstand == "loaded":
                return
            await asyncio.sleep(1)
        raise AssertionError(f"{entry_id} ble ikke lastet innen {timeout} s: {tilstand}")

    async def test_satsvarsel_etter_avvik(self) -> None:
        """Motprøven, kjørt etter at lagret sats er skrudd bort fra katalogen."""
        bkk = self.data.get("bkk_entry") or self.data["entry_id"]
        await self.vent_paa_lastet(bkk)
        issues = await self.issues()
        varsel = issues.get(f"tariff_ubekreftet_{bkk}")
        assert varsel, f"Avvikende lagret sats reiste ikke satsvarselet. Reist: {sorted(issues)}"
        assert varsel["translation_key"] == "tariff_ubekreftet", varsel["translation_key"]
        plassholdere = varsel["translation_placeholders"]
        assert plassholdere["lagret_dag"] != plassholdere["katalog_dag"], (
            f"Varselet viser samme sats på begge sider: {plassholdere}"
        )
        trace("test_satsvarsel_etter_avvik", **{k: plassholdere[k] for k in ("lagret_dag", "katalog_dag")})

    # --- Vaktholdet ---

    VAKTHOLD = ("input_utfall", "energi_frossen", "spot_utfall", "input_enhet")

    async def _vakthold(self) -> dict[str, dict]:
        issues = await self.issues()
        return {
            prefix: issues[f"{prefix}_{entry_id}"]
            for entry_id in self.data["utganger"]
            for prefix in self.VAKTHOLD
            if f"{prefix}_{entry_id}" in issues
        }

    async def test_vakthold_stille_naar_alt_er_friskt(self) -> None:
        await self._oppdater_alle()
        await asyncio.sleep(11)
        aktive = await self._vakthold()
        assert not aktive, f"Vaktholdet varslet uten grunn: {sorted(aktive)}"
        trace("test_vakthold_stille_naar_alt_er_friskt", aktive=0)

    async def test_vakthold_tier_rett_etter_omstart(self) -> None:
        """En omstart er ikke et utfall.

        Vaktholdet ble avvist på nettopp dette: spotcachen er in-memory og tom
        ved første poll etter oppstart, og uten grace ville hver eneste omstart
        gitt et varsel om at spotprisen var borte.
        """
        await self._oppdater_alle()
        await asyncio.sleep(11)
        aktive = await self._vakthold()
        assert not aktive, f"Omstarten ga varsel: {sorted(aktive)}"
        trace("test_vakthold_tier_rett_etter_omstart", aktive=0)

    async def test_vakthold_tier_innenfor_grace(self) -> None:
        """En kortvarig glipp er ikke et utfall.

        Grace-en dekker HA-restart, oppdatering av en integrasjon og en
        nettverksglipp. Varsler vi her, varsler vi på alt som går over av seg
        selv, og da slutter brukeren å tro på varselet.
        """
        await self._oppdater_alle()
        await asyncio.sleep(11)
        aktive = await self._vakthold()
        assert not aktive, f"Varsel innenfor grace-vinduet: {sorted(aktive)}"
        trace("test_vakthold_tier_innenfor_grace", aktive=0)

    async def test_vakthold_spot_utlopt(self) -> None:
        """Når cachen er for gammel, tar spot_utfall over for utfallsraden.

        Én årsak, ett varsel: `spot_utlopt` sier alt utfallet sier, og i
        tillegg at kostnaden har sluttet å akkumulere. Da skal ikke spotprisen
        stå oppført i utfallsvarselet i tillegg.
        """
        await self._oppdater_alle()
        await asyncio.sleep(11)
        aktive = await self._vakthold()
        spot = aktive.get("spot_utfall")
        assert spot, f"Spotcachen gikk ut uten spotvarsel. Aktive: {sorted(aktive)}"
        assert self.data["inputs"]["spot"] in spot["translation_placeholders"]["entity_id"]
        utfall = aktive.get("input_utfall")
        assert utfall, "Effekt og energi er fortsatt nede, men utfallsvarselet forsvant"
        assert self.data["inputs"]["spot"] not in utfall["translation_placeholders"]["entity_id"], (
            "Spotprisen er meldt to ganger: både som utfall og som utløpt"
        )
        trace("test_vakthold_spot_utlopt", timer=spot["translation_placeholders"]["timer"])

    async def vent_paa_grace(self, minutter: float = 32.0) -> None:
        """La grace-vinduet løpe ut i ekte tid.

        Terskelen er 30 minutter målt på klokken. Den kan ikke jukses fram her:
        skal laben si noe om et ekte utfall, må utfallet vare like lenge som
        et ekte et. HAs egen minuttpoll holder vaktholdet i gang mens vi venter.
        """
        slutt = time.monotonic() + minutter * 60
        while time.monotonic() < slutt:
            await asyncio.sleep(60)
            trace("vent_paa_grace", gjenstaar_min=round((slutt - time.monotonic()) / 60, 1))

    async def test_vakthold_varsler_etter_grace(self) -> None:
        """Varselet skal komme, og det skal peke på alle tre sensorene som er nede.

        Spotprisen står her som utfall og ikke som utløpt: cachen er fortsatt
        fersk nok til å regne med, den er bare ikke oppdatert.
        """
        await self._oppdater_alle()
        await asyncio.sleep(11)
        aktive = await self._vakthold()
        utfall = aktive.get("input_utfall")
        assert utfall, f"Ingen utfallsvarsel etter grace. Aktive: {sorted(aktive)}"
        detaljer = utfall["translation_placeholders"]["entity_id"]
        for key in ("power", "spot", self.data["energy_key"]):
            assert self.data["inputs"][key] in detaljer, f"{key} mangler i varselet: {detaljer}"
        assert "energi_frossen" not in aktive, "Frossen teller meldt samtidig som sensoren er borte"
        trace("test_vakthold_varsler_etter_grace", sorter=sorted(aktive), entity_id=detaljer)

    async def test_vakthold_delvis_friskmelding(self) -> None:
        """Én sensor tilbake skal skrive om teksten, ikke lukke varselet."""
        gammel = self.data["inputs"]["power"]
        await self.api(
            f"/api/states/{gammel}",
            {"state": "1000", "attributes": dict(self.data["overrides"]["power"]["attributes"])},
        )
        self.data["overrides"].pop("power")
        self.save()
        await self._oppdater_alle()
        await asyncio.sleep(11)
        aktive = await self._vakthold()
        utfall = aktive.get("input_utfall")
        assert utfall, "Varselet forsvant selv om energisensoren fortsatt er nede"
        detaljer = utfall["translation_placeholders"]["entity_id"]
        assert gammel not in detaljer, f"Varselet peker på en frisk sensor: {detaljer}"
        assert self.data["inputs"][self.data["energy_key"]] in detaljer, detaljer
        trace("test_vakthold_delvis_friskmelding", entity_id=detaljer)

    async def test_vakthold_friskmelding(self) -> None:
        await self.recover_inputs()
        await self._oppdater_alle()
        await asyncio.sleep(11)
        aktive = await self._vakthold()
        assert not aktive, f"Varsel overlevde full friskmelding: {sorted(aktive)}"
        trace("test_vakthold_friskmelding", aktive=0)

    async def test_frossen_teller_varsles(self) -> None:
        """Telleren svarer, men står stille lenger enn terskelen."""
        await self._oppdater_alle()
        await asyncio.sleep(11)
        aktive = await self._vakthold()
        frossen = aktive.get("energi_frossen")
        assert frossen, f"Frossen teller ga ingen varsel. Aktive: {sorted(aktive)}"
        peker = frossen["translation_placeholders"]["entity_id"]
        assert self.data["inputs"][self.data["energy_key"]] in peker, peker
        trace("test_frossen_teller_varsles", timer=frossen["translation_placeholders"]["timer"])

    async def test_strombrudd_er_ikke_frossen_teller(self) -> None:
        """HA sto av, og da så ingen at telleren gikk. Det er ikke en frossen måler.

        Motprøven til `test_frossen_teller_varsles`: samme alder på
        `last_energy_increase`, men `last_update` sier at HA var av i gapet.
        Frossen-klokken skal bare telle tiden vi faktisk så på.
        """
        await self._oppdater_alle()
        await asyncio.sleep(11)
        aktive = await self._vakthold()
        assert "energi_frossen" not in aktive, (
            f"Strømbrudd ble meldt som frossen teller. Aktive: {sorted(aktive)}"
        )
        trace("test_strombrudd_er_ikke_frossen_teller", aktive=sorted(aktive))

    async def test_maalerbytte_varsler_ikke(self) -> None:
        """Ny fysisk kilde er en baseline, ikke et problem å varsle om."""
        before = await self.total()
        self.data["energy_key"] = "energy_new"
        self.data["config"]["energy_sensor"] = self.data["inputs"]["energy_new"]
        await self.options()
        await self.expect_total(before)
        await self.refresh(settle=True)
        assert near(await self.total(), before), "Målerbyttet bokførte den nye tellerstanden"
        aktive = await self._vakthold()
        assert not aktive, f"Målerbyttet reiste et varsel: {sorted(aktive)}"
        assert not await self.issue_present("energi_delta_forkastet"), (
            "Målerbyttet ble meldt som et forkastet sprang"
        )
        await self.test_energy_increase()
        trace("test_maalerbytte_varsler_ikke", total_kwh=round(await self.total(), 3))

    async def test_sprang_varsler_med_riktig_sensor(self) -> None:
        """Spranget skal avvises, og varselet skal navngi telleren og tallet."""
        before = await self.total()
        key = self.data["energy_key"]
        teller = float((await self.state(self.data["inputs"][key]))["state"])
        await self.set_input(key, teller + 1000)
        await self.refresh(settle=True)
        assert near(await self.total(), before), "1000 kWh sprang ble bokført"
        issues = await self.issues()
        varsel = issues.get(f"energi_delta_forkastet_{self.data['entry_id']}")
        assert varsel, "Forkastet sprang ga ingen forklaring"
        plassholdere = varsel["translation_placeholders"]
        assert plassholdere["sensor"] == self.data["inputs"][key], plassholdere["sensor"]
        assert float(plassholdere["kwh"]) > 900, plassholdere["kwh"]
        await self.test_energy_increase()
        trace("test_sprang_varsler_med_riktig_sensor", kwh=plassholdere["kwh"])

    async def outage_han(self) -> None:
        await self.override("power", "unavailable")
        await self.override(self.data["energy_key"], "unavailable")
        await self.refresh(settle=True)

    async def outage_spot(self) -> None:
        await self.override("spot", "unavailable")
        await self.refresh(settle=True)

    async def replay(self, tick: float) -> None:
        fixture = json.loads(Path("/fixture.json").read_text())
        before = await self.total()
        key = self.data["energy_key"]
        counter = float((await self.state(self.data["inputs"][key]))["state"])
        sent = 0.0
        batch = 0.0
        month = datetime.now(UTC).astimezone().strftime("%Y-%m")
        for index, row in enumerate(fixture["hours"]):
            # Flush well before the integration's 100 kWh outlier threshold.
            if batch + row["kwh"] > 25:
                await self.expect_total(before + sent)
                batch = 0.0
            power = row["p_max_w"]
            spot = row["spot_nok_kwh_eks_mva"]
            if power is None or spot is None:
                raise ValueError("Valgt fixture har kildehull; velg juni_2026 for komplett avstemming")
            await self.set_input("power", power)
            await self.set_input("spot", spot)
            sent += row["kwh"]
            batch += row["kwh"]
            await self.set_input(key, round(counter + sent, 3))
            if index % 60 == 0:
                trace("replay_progress", hours=index + 1, sent_kwh=round(sent, 3))
            await asyncio.sleep(tick)
        await self.expect_total(before + sent)
        if datetime.now(UTC).astimezone().strftime("%Y-%m") != month:
            raise AssertionError("Virkelig månedsskifte under replay; kjør på nytt uten månedsskifte")
        output = await self.state(self.data["total"])
        result = {
            "fixture": fixture["name"],
            "hours": len(fixture["hours"]),
            "source_invoice_check": fixture["reference"],
            "ha_energy_delta_kwh": round(float(output["state"]) - before, 3),
            "ha_current_month_day_kwh": output["attributes"]["dag_kwh"],
            "ha_current_month_night_kwh": output["attributes"]["natt_kwh"],
            "historical_ha_tariff_verified": False,
            "limitation": "HA bruker virkelig klokke. Historisk dag/natt er bare kildekontroll.",
        }
        assert near(result["ha_energy_delta_kwh"], sent), "HA mistet kWh under komprimert avspilling"
        Path("/config/report.json").write_text(json.dumps(result, indent=2))
        trace(
            "replay_complete", hours=len(fixture["hours"]), ha_energy_delta_kwh=result["ha_energy_delta_kwh"]
        )


SCENARIOS = (
    "bootstrap",
    "test_onboarding",
    "test_energy_increase",
    "checkpoint_restart",
    "test_restart_no_double_booking",
    "test_meter_change",
    "test_remove_optional",
    "test_invalid_unit_recovery",
    "test_missing_input_recovery",
    "test_meter_jump",
    "outage_han",
    "outage_spot",
    "recover_inputs",
    "replay",
    # Oppgraderingsveien fra en sluppet utgave
    "test_onboarding_egendefinert",
    "seed_akkumulatorer",
    "merk_oppgraderingsstart",
    "checkpoint_oppgradering",
    "test_oppgradering_beholder_akkumulatorene",
    "test_baselinen_forkastes_en_gang",
    "test_fastleddet_er_et_periodebelop",
    "test_statistikken_folger_skiftet",
    "test_egendefinert_uten_fastledd",
    "test_satsvarsel_kun_ved_avvik",
    "test_satsvarsel_etter_avvik",
    # Vaktholdet
    "test_vakthold_stille_naar_alt_er_friskt",
    "test_vakthold_tier_rett_etter_omstart",
    "test_vakthold_tier_innenfor_grace",
    "vent_paa_grace",
    "test_vakthold_varsler_etter_grace",
    "test_vakthold_spot_utlopt",
    "test_vakthold_delvis_friskmelding",
    "test_vakthold_friskmelding",
    "test_frossen_teller_varsles",
    "test_strombrudd_er_ikke_frossen_teller",
    "test_maalerbytte_varsler_ikke",
    "test_sprang_varsler_med_riktig_sensor",
)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--tick", type=float, default=0.05)
    parser.add_argument("--minutter", type=float, default=32.0, help="Ekte minutter for vent_paa_grace")
    args = parser.parse_args()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as session:
        driver = Driver(session)
        await driver.ready()
        trace(args.scenario, status="started")
        try:
            if args.scenario == "replay":
                await driver.replay(args.tick)
            elif args.scenario == "vent_paa_grace":
                await driver.vent_paa_grace(args.minutter)
            else:
                await getattr(driver, args.scenario)()
        except Exception as exc:
            trace(args.scenario, status="failed", error_type=type(exc).__name__)
            raise
        trace(args.scenario, status="passed")


if __name__ == "__main__":
    asyncio.run(main())
