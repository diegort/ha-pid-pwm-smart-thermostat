"""Smoke test of the UI flow against a real HA instance (use when pytest-homeassistant-custom-component
lags behind HA). Needs homeassistant + home-assistant-frontend installed.

Usage: python scripts/smoke_test.py <path to hass executable> <repo root>
"""
import asyncio, json, os, shutil, subprocess, sys, tempfile, time
import aiohttp

HASS, REPO = sys.argv[1], sys.argv[2]
BASE = "http://127.0.0.1:18123"
CID = BASE + "/"

CONFIG = """
homeassistant: {name: smoke, unit_system: metric, time_zone: UTC, latitude: 0, longitude: 0, elevation: 0}
http: {server_port: 18123, server_host: 127.0.0.1}
api:
config:
onboarding:
input_boolean: {heater: {}, heater2: {}, cooler: {}, yaml_heater: {}}
input_number: {temp: {min: 0, max: 40, step: 0.1, initial: 18}}
logger: {default: warning, logs: {custom_components.pid_pwm_smart_thermostat: info}}
climate:
  - platform: pid_pwm_smart_thermostat
    name: yaml_thermostat
    target_sensor: input_number.temp
    heater: input_boolean.yaml_heater
"""


async def main():
    cfg = tempfile.mkdtemp(prefix="pid_pwm_smoke_")
    os.makedirs(f"{cfg}/custom_components")
    shutil.copytree(f"{REPO}/custom_components/pid_pwm_smart_thermostat",
                    f"{cfg}/custom_components/pid_pwm_smart_thermostat")
    open(f"{cfg}/configuration.yaml", "w").write(CONFIG)
    log = open(f"{cfg}/hass.out", "w")
    proc = subprocess.Popen([HASS, "-c", cfg, "--skip-pip"], stdout=log, stderr=subprocess.STDOUT)
    try:
        async with aiohttp.ClientSession() as s:
            for _ in range(180):
                try:
                    async with s.get(BASE + "/api/onboarding") as r:
                        if r.status == 200: break
                except aiohttp.ClientError: pass
                await asyncio.sleep(1)
            else:
                raise SystemExit("HA did not start")
            async with s.post(BASE + "/api/onboarding/users", json={
                "client_id": CID, "name": "t", "username": "t", "password": "t", "language": "en"}) as r:
                code = (await r.json())["auth_code"]
            async with s.post(BASE + "/auth/token", data={
                "grant_type": "authorization_code", "code": code, "client_id": CID}) as r:
                token = (await r.json())["access_token"]
            h = {"Authorization": f"Bearer {token}"}

            async def post(path, body):
                async with s.post(BASE + path, json=body, headers=h) as r:
                    data = await r.json()
                    assert r.status == 200, (path, r.status, data)
                    return data

            async def state(eid):
                async with s.get(f"{BASE}/api/states/{eid}", headers=h) as r:
                    return await r.json() if r.status == 200 else None

            async def wait_state(eid, pred, what):
                for _ in range(50):
                    st = await state(eid)
                    if pred(st): return st
                    await asyncio.sleep(0.2)
                raise AssertionError(f"{what}: {st}")

            # YAML is not supported: a leftover YAML platform config must not create an entity
            await asyncio.sleep(1)
            assert await state("climate.yaml_thermostat") is None
            print("OK yaml platform config ignored")

            # Thermostat entry; form must serialize (incl. the presets section)
            F = "/api/config/config_entries/flow"
            r = await post(F, {"handler": "pid_pwm_smart_thermostat"})
            names = [f["name"] for f in r["data_schema"]]
            assert "presets" in names and "target_sensor" in names, names
            r = await post(f"{F}/{r['flow_id']}", {"name": "Living", "target_sensor": "input_number.temp",
                                                    "min_temp": 30, "max_temp": 20, "presets": {}})
            assert r["errors"] == {"max_temp": "max_not_greater_than_min"}, r
            r = await post(f"{F}/{r['flow_id']}", {"name": "Living", "target_sensor": "input_number.temp",
                                                    "precision": "0.5", "presets": {"eco": 17}})
            assert r["type"] == "create_entry", r
            entry_id = r["result"]["entry_id"]
            await asyncio.sleep(1)
            assert await state("climate.living") is None, "empty thermostat must not create an entity"
            print("OK entry created, no entity while empty")

            SF = "/api/config/config_entries/subentries/flow"
            async def add(kind, entity, menu, data, subentry_id=None):
                body = {"handler": [entry_id, kind]}
                if subentry_id: body["subentry_id"] = subentry_id
                r = await post(SF, body)
                r = await post(f"{SF}/{r['flow_id']}", {"entity_id": entity})
                if r["type"] == "form" and r.get("errors"): return r
                if menu:
                    assert r["type"] == "menu", r
                    r = await post(f"{SF}/{r['flow_id']}", {"next_step_id": menu})
                assert r["data_schema"], r
                return await post(f"{SF}/{r['flow_id']}", data)

            r = await add("heater", "input_boolean.heater", "pwm",
                          {"pwm_period": {"hours": 0, "minutes": 10, "seconds": 0}, "kp": 50, "ki": 0.1, "kd": 0})
            assert r["type"] == "create_entry", r
            st = await wait_state("climate.living", lambda x: x and "heat" in x["attributes"]["hvac_modes"], "heater")
            assert st["attributes"]["preset_modes"] == ["none", "eco"], st
            print("OK pwm heater subentry -> entity", st["attributes"]["hvac_modes"])

            r = await add("cooler", "input_boolean.cooler", "on_off", {"cold_tolerance": 0.5})
            assert r["type"] == "create_entry", r
            r = await add("cooler", "input_boolean.heater", None, {})
            assert r["errors"] == {"entity_id": "already_configured"}, r
            await wait_state("climate.living", lambda x: x and "heat_cool" in x["attributes"]["hvac_modes"], "cooler")
            print("OK on/off cooler subentry, duplicate entity rejected")

            async with s.ws_connect(BASE + "/api/websocket") as ws:
                await ws.receive_json()
                await ws.send_json({"type": "auth", "access_token": token}); await ws.receive_json()
                await ws.send_json({"id": 1, "type": "config_entries/subentries/list", "entry_id": entry_id})
                subs = (await ws.receive_json())["result"]
            heater_sub = next(x["subentry_id"] for x in subs if x["subentry_type"] == "heater")
            r = await add("heater", "input_boolean.heater2", "on_off", {}, subentry_id=heater_sub)
            assert r["type"] == "abort" and r["reason"] == "reconfigure_successful", r
            print("OK heater reconfigured")

            # Control: heat mode, target 21 > 18 -> on/off heater turns on
            await asyncio.sleep(1)
            await post("/api/services/climate/set_temperature", {"entity_id": "climate.living", "temperature": 21})
            await post("/api/services/climate/set_hvac_mode", {"entity_id": "climate.living", "hvac_mode": "heat"})
            await wait_state("input_boolean.heater2", lambda x: x["state"] == "on", "heater2 on")
            await wait_state("climate.living", lambda x: x["attributes"]["hvac_action"] == "heating", "heating")
            print("OK heat mode turned on input_boolean.heater2 and hvac_action=heating")

            # Options flow
            OF = "/api/config/config_entries/options/flow"
            r = await post(OF, {"handler": entry_id})
            assert [f for f in r["data_schema"] if f["name"] == "presets"], r
            r = await post(f"{OF}/{r['flow_id']}", {"target_sensor": "input_number.temp",
                                                     "heat_cool_disabled": True, "presets": {}})
            assert r["type"] == "create_entry", r
            st = await wait_state("climate.living", lambda x: x and "heat_cool" not in x["attributes"]["hvac_modes"],
                                  "options applied")
            assert "preset_modes" not in st["attributes"], st
            print("OK options flow applied")
    finally:
        proc.terminate(); proc.wait(30); log.close()
        print("HA config/log dir:", cfg)
        out = open(f"{cfg}/hass.out").read()
        bad = [l for l in out.splitlines() if ("pid_pwm_smart_thermostat" in l or "yaml_thermostat" in l) and ("ERROR" in l or "WARNING" in l or "Traceback" in l)]
        print("--- integration warnings/errors in HA log:"); print("\n".join(bad) or "(none)")
        errs = [l for l in out.splitlines() if " ERROR " in l]
        print("--- all HA ERROR lines:"); print("\n".join(errs[:20]) or "(none)")

asyncio.run(main())
