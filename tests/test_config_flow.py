"""UI config flow checks. Run: pytest"""
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.pid_pwm_smart_thermostat.const import DOMAIN

ENTITY = "climate.living_room"


async def _setup_states(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.temp", "18")
    hass.states.async_set("switch.heater", "off")
    hass.states.async_set("switch.cooler", "off")
    hass.states.async_set("switch.heater2", "off")


async def _create_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Living room", "target_sensor": "sensor.temp", "min_temp": 30, "max_temp": 20,
                            "presets": {}}
    )
    assert result["errors"] == {"max_temp": "max_not_greater_than_min"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Living room", "target_sensor": "sensor.temp", "precision": "0.5", "presets": {"eco": 17}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


async def _add_subentry(hass, entry, kind, entity_id, menu_choice=None, data=None):
    result = await hass.config_entries.subentries.async_init((entry.entry_id, kind), context={"source": SOURCE_USER})
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"entity_id": entity_id})
    if menu_choice:
        assert result["type"] is FlowResultType.MENU
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"next_step_id": menu_choice})
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], data or {})
    await hass.async_block_till_done()
    return result


async def test_ui_flow(hass: HomeAssistant) -> None:
    await _setup_states(hass)
    entry = await _create_entry(hass)

    # No heaters/coolers yet: no entity
    assert hass.states.get(ENTITY) is None

    result = await _add_subentry(
        hass, entry, "heater", "switch.heater", "pwm",
        {"pwm_period": {"minutes": 10}, "kp": 50, "ki": 0.1, "kd": 0},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["pid_params"] == [50, 0.1, 0]
    state = hass.states.get(ENTITY)
    assert state.attributes["hvac_modes"] == ["off", "heat"]
    assert state.attributes["preset_modes"] == ["none", "eco"]

    result = await _add_subentry(hass, entry, "cooler", "switch.cooler", "on_off", {"cold_tolerance": 0.5})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Same entity twice is rejected
    result = await hass.config_entries.subentries.async_init((entry.entry_id, "cooler"), context={"source": SOURCE_USER})
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"entity_id": "switch.heater"})
    assert result["errors"] == {"entity_id": "already_configured"}

    assert set(hass.states.get(ENTITY).attributes["hvac_modes"]) == {"off", "heat", "cool", "heat_cool"}

    # Reconfigure the heater: switch it to on/off control on another entity
    heater_id = next(s for s, sub in entry.subentries.items() if sub.subentry_type == "heater")
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "heater"), context={"source": SOURCE_RECONFIGURE, "subentry_id": heater_id}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"entity_id": "switch.heater2"})
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"next_step_id": "on_off"})
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.subentries[heater_id].data["entity_id"] == "switch.heater2"
    assert "pid_params" not in entry.subentries[heater_id].data

    # Heat mode turns the (reconfigured) on/off heater on: 18 < target 21 - 0.3
    turn_on = async_mock_service(hass, "homeassistant", "turn_on")
    async_mock_service(hass, "homeassistant", "turn_off")
    await hass.services.async_call("climate", "set_temperature", {"entity_id": ENTITY, "temperature": 21}, blocking=True)
    await hass.services.async_call("climate", "set_hvac_mode", {"entity_id": ENTITY, "hvac_mode": "heat"}, blocking=True)
    await hass.async_block_till_done()
    assert [c.data["entity_id"] for c in turn_on] == ["switch.heater2"]

    # Options flow: disable heat_cool, entity reloads
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"target_sensor": "sensor.temp", "heat_cool_disabled": True, "presets": {}}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert "heat_cool" not in state.attributes["hvac_modes"]
    assert state.attributes.get("preset_modes") is None

