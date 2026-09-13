"""Drive only the test container's loopback HA API, with real config flows.

Executed with `docker compose exec ... python /harness/driver.py`. Credentials
belong to this throwaway HA user; they never appear in stdout or the trace.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from datetime import UTC, datetime
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
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                await self.api("/api/" if self.auth.get("token") else "/api/onboarding")
                return
            except (aiohttp.ClientError, RuntimeError, TimeoutError):
                await asyncio.sleep(1)
        raise TimeoutError("HA startet ikke innen 180 sekunder")

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
        if self.data.get("entry_id"):
            outputs = {
                entry["unique_id"]: entry["entity_id"]
                for entry in entries
                if entry["platform"] == "stromkalkulator"
                and entry["config_entry_id"] == self.data["entry_id"]
            }
            self.data["total"] = outputs[f"{self.data['entry_id']}_maanedlig_forbruk_total"]
            self.data["export"] = outputs[f"{self.data['entry_id']}_maanedlig_eksport_kwh"]
        self.save()

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

    async def issue_present(self, prefix: str) -> bool:
        result = await self.ws("repairs/list_issues")
        return any(
            row["domain"] == "stromkalkulator" and row["issue_id"] == f"{prefix}_{self.data['entry_id']}"
            for row in result["issues"]
        )

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
)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--tick", type=float, default=0.05)
    args = parser.parse_args()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as session:
        driver = Driver(session)
        await driver.ready()
        trace(args.scenario, status="started")
        try:
            if args.scenario == "replay":
                await driver.replay(args.tick)
            else:
                await getattr(driver, args.scenario)()
        except Exception as exc:
            trace(args.scenario, status="failed", error_type=type(exc).__name__)
            raise
        trace(args.scenario, status="passed")


if __name__ == "__main__":
    asyncio.run(main())
