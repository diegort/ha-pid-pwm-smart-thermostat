# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Home Assistant custom integration `pid_pwm_smart_thermostat` (distributed via HACS; fork of `smart_thermostat`, domain renamed so both can coexist) providing a `climate` platform that drives heaters/coolers via on/off, PWM, or PID control. UI-only (config flow + subentries); YAML platform setup was removed on purpose. Only external dependency: `simple-pid==1.0.1`.

## Commands

```bash
pip install pytest-homeassistant-custom-component simple-pid==1.0.1   # Python 3.13
pytest                                         # all tests (pytest.ini sets asyncio_mode=auto)
pytest tests/test_config_flow.py::test_ui_flow # single test
```

`pytest-homeassistant-custom-component` lags behind HA releases (latest targets 2026.2). For newer HA, `scripts/smoke_test.py <hass bin> <repo>` boots a real instance (needs `homeassistant` + `home-assistant-frontend`; HA ≥ 2026.10 needs Python ≥ 3.14.2) and drives the whole UI flow over REST/websocket.

CI (`.github/workflows/validate.yml`) runs hassfest, the HACS action and pytest. Published as a HACS **custom repository** (no home-assistant/brands entry). Manual testing: copy `custom_components/pid_pwm_smart_thermostat` into `<config>/custom_components/`; `docs/debug_config_package.yaml` + `docs/debug_lovelace_dashboard.yaml` provide fake devices; the thermostat itself is created in the UI as described in the package comments. Debug logs: `logger: logs: custom_components.pid_pwm_smart_thermostat: debug`.

Release: bump `version` in `manifest.json`. User-facing options are documented in `README.md`; keep it, `translations/en.json` and the schemas in sync.

## Architecture

All code in `custom_components/pid_pwm_smart_thermostat/`. Schemas: HA ≥ 2026.10 replaced voluptuous with `probatio` (API-compatible); modules do `import probatio as vol` with a `voluptuous` fallback for older HA — keep that pattern, don't import `voluptuous` directly. Constants (`CONF_*`, `DOMAIN`, `PLATFORMS`) live in `const.py`; `climate.py` star-imports it.

- **Setup**: `climate.async_setup_entry` assembles `entry.options` (thermostat settings) plus one list item per subentry (`subentry_type` is `heater`/`cooler`) into one dict, validates it with `DATA_SCHEMA` (controller items via `_cv_controller_target`), and passes it to `_build_thermostat`. A config entry with no subentries creates no entity (and skips validation). A new option needs both a `DATA_SCHEMA`/controller-schema entry and a form field in `config_flow.py` (+ `translations/en.json`).
- **`config_flow.py`**: the config entry holds thermostat settings in `options` (editable via `SmartThermostatOptionsFlow`; presets are a collapsed `section`, stored nested as `presets`). Heaters/coolers are **config subentries** (`ControllerSubentryFlow`, add + reconfigure): pick entity → step by domain (`switch_type` menu → `on_off`/`pwm`, `number`, `climate`). Subentry data is stored with the controller-schema keys (`pid_params` as `[kp, ki, kd]`; durations as selector dicts) and checked with `climate._cv_controller_target`. `__init__.py` registers an update listener that reloads the entry on any options/subentry change (so flows must not use `OptionsFlowWithReload`/`async_update_reload_and_abort`).
- **`SmartThermostat._async_control()`** in `climate.py` is the central loop (guarded by `_temp_lock`): computes `hvac_action` from `hvac_mode` (and, in `heat_cool`, from `heat_cool_cold/hot_tolerance`), stops controllers whose mode doesn't match, starts those that do, then calls `async_control()` on all. Triggered by sensor/controller-entity changes, mode/temperature/preset changes, and timers. `hvac_action` reflects whether controllers are actually `working` (target entity state), not just requested.
- **`controllers.py`**: decoupled from the entity through the `Thermostat` ABC. `AbstractController` has `@final` template methods (`async_start`/`async_stop`/`async_control`); subclasses implement `_async_start`, `_async_stop`, `_async_control`, `_async_ensure_not_running` (called every tick while stopped, which is why manual changes to controlled entities get reverted). Switch control uses `homeassistant.turn_on/turn_off`. `AbstractPidController` wraps `simple_pid.PID` (params inverted internally for cool mode; fixed `pid_sample_period` timer or every sensor update). `PwmSwitchPidController` output is fixed 0–100 mapped to duty within `pwm_period`.
- **Naming / state restore**: controllers are named `<heater|cooler>_<entity_id>` (logs). Each controller's `extra_state_attributes` are stored under its `get_unique_id()` (`ctrl_<object_id>`) inside the thermostat's state attributes and passed back to `controller.async_added_to_hass(hass, attrs)`. PID auto-tuning is stubbed (`NotImplementedError`).
