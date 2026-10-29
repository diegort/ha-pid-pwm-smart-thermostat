"""Config flow for the PID PWM Smart Thermostat.

The config entry holds the thermostat settings (editable via the options flow). Each heater/cooler is a
config subentry (data keys: see `climate.DATA_SCHEMA` controller items).
"""
from __future__ import annotations

from typing import Any

try:
    import probatio as vol  # HA >= 2026.10 validates with probatio
except ImportError:  # older HA
    import voluptuous as vol

from homeassistant.components.climate import HVACMode
from homeassistant.components.climate.const import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_SLEEP,
)
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback, split_entity_id
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector

from .climate import (
    CLIMATE_DOMAIN,
    DATA_SCHEMA,
    INPUT_BOOLEAN_DOMAIN,
    INPUT_NUMBER_DOMAIN,
    NUMBER_DOMAIN,
    SUPPORTED_TARGET_DOMAINS,
    SWITCH_DOMAIN,
    _cv_controller_target,
)
from .const import (
    CONF_COLD_TOLERANCE,
    CONF_ENTITY_ID,
    CONF_HEAT_COOL_COLD_TOLERANCE,
    CONF_HEAT_COOL_DISABLED,
    CONF_HEAT_COOL_HOT_TOLERANCE,
    CONF_HOT_TOLERANCE,
    CONF_INITIAL_HVAC_MODE,
    CONF_INVERTED,
    CONF_KEEP_ALIVE,
    CONF_MAX_TEMP,
    CONF_MIN_DUR,
    CONF_MIN_TEMP,
    CONF_NAME,
    CONF_PID_MAX,
    CONF_PID_MIN,
    CONF_PID_PARAMS,
    CONF_PID_SAMPLE_PERIOD,
    CONF_PID_SWITCH_ENTITY_ID,
    CONF_PID_SWITCH_INVERTED,
    CONF_PRECISION,
    CONF_PRESETS,
    CONF_PWM_SWITCH_PERIOD,
    CONF_SENSOR,
    CONF_STALE_DURATION,
    CONF_TARGET_TEMP,
    DEFAULT_HEAT_COOL_TOLERANCE,
    DEFAULT_NAME,
    DEFAULT_SWITCH_TOLERANCE,
    DOMAIN,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SUBENTRY_COOLER,
    SUBENTRY_HEATER,
)

# PID params are a single `[kp, ki, kd]` list in the stored data, but three fields in the form
CONF_KP = "kp"
CONF_KI = "ki"
CONF_KD = "kd"

STEP_ON_OFF = "on_off"
STEP_PWM = "pwm"
STEP_NUMBER = "number"
STEP_CLIMATE = "climate"

_TEMP = selector.NumberSelector(selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step="any"))
_POSITIVE = selector.NumberSelector(
    selector.NumberSelectorConfig(min=0, mode=selector.NumberSelectorMode.BOX, step="any")
)
_DURATION = selector.DurationSelector()
_BOOL = selector.BooleanSelector()

THERMOSTAT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", INPUT_NUMBER_DOMAIN, NUMBER_DOMAIN])
        ),
        vol.Optional(CONF_MIN_TEMP): _TEMP,
        vol.Optional(CONF_MAX_TEMP): _TEMP,
        vol.Optional(CONF_TARGET_TEMP): _TEMP,
        vol.Optional(CONF_PRECISION): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[str(p) for p in (PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE)],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_INITIAL_HVAC_MODE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL],
                translation_key=CONF_INITIAL_HVAC_MODE,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_STALE_DURATION): _DURATION,
        vol.Optional(CONF_HEAT_COOL_DISABLED, default=False): _BOOL,
        vol.Optional(CONF_HEAT_COOL_COLD_TOLERANCE, default=DEFAULT_HEAT_COOL_TOLERANCE): _POSITIVE,
        vol.Optional(CONF_HEAT_COOL_HOT_TOLERANCE, default=DEFAULT_HEAT_COOL_TOLERANCE): _POSITIVE,
        vol.Required(CONF_PRESETS): section(
            vol.Schema(
                {
                    vol.Optional(preset): _TEMP
                    for preset in (PRESET_AWAY, PRESET_ECO, PRESET_COMFORT, PRESET_HOME, PRESET_SLEEP, PRESET_BOOST)
                }
            ),
            {"collapsed": True},
        ),
    }
)


def _validate_thermostat(user_input: dict[str, Any]) -> dict[str, str]:
    """Return form errors for the thermostat settings."""
    minimum = user_input.get(CONF_MIN_TEMP)
    maximum = user_input.get(CONF_MAX_TEMP)
    if None not in (minimum, maximum) and minimum >= maximum:
        return {CONF_MAX_TEMP: "max_not_greater_than_min"}
    try:
        DATA_SCHEMA({**user_input, CONF_NAME: "validate"})
    except vol.Invalid:
        return {"base": "invalid_config"}
    return {}


class SmartThermostatConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a thermostat; heaters/coolers are added afterwards as subentries."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            options = dict(user_input)
            name = options.pop(CONF_NAME)
            if not (errors := _validate_thermostat(options)):
                return self.async_create_entry(title=name, data={}, options=options)

        schema = vol.Schema({vol.Required(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector()}).extend(
            THERMOSTAT_SCHEMA.schema
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SmartThermostatOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_HEATER: ControllerSubentryFlow, SUBENTRY_COOLER: ControllerSubentryFlow}


class SmartThermostatOptionsFlow(OptionsFlow):
    """Edit the thermostat settings."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            if not (errors := _validate_thermostat(user_input)):
                return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                THERMOSTAT_SCHEMA, user_input or self.config_entry.options
            ),
            errors=errors,
        )


def _pid_schema() -> dict:
    return {
        vol.Required(CONF_KP): _POSITIVE,
        vol.Required(CONF_KI): _POSITIVE,
        vol.Required(CONF_KD): _POSITIVE,
        vol.Optional(CONF_PID_SAMPLE_PERIOD): _DURATION,
    }


def _min_max_schema() -> dict:
    return {vol.Optional(CONF_PID_MIN): _TEMP, vol.Optional(CONF_PID_MAX): _TEMP}


def _common_schema() -> dict:
    return {vol.Optional(CONF_INVERTED, default=False): _BOOL, vol.Optional(CONF_KEEP_ALIVE): _DURATION}


CONTROLLER_SCHEMAS = {
    STEP_ON_OFF: vol.Schema(
        {
            vol.Optional(CONF_COLD_TOLERANCE, default=DEFAULT_SWITCH_TOLERANCE): _POSITIVE,
            vol.Optional(CONF_HOT_TOLERANCE, default=DEFAULT_SWITCH_TOLERANCE): _POSITIVE,
            vol.Optional(CONF_MIN_DUR): _DURATION,
            **_common_schema(),
        }
    ),
    STEP_PWM: vol.Schema(
        {
            vol.Required(CONF_PWM_SWITCH_PERIOD): _DURATION,
            **_pid_schema(),
            **_common_schema(),
        }
    ),
    STEP_NUMBER: vol.Schema(
        {
            vol.Required(CONF_PID_SWITCH_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=[SWITCH_DOMAIN, INPUT_BOOLEAN_DOMAIN])
            ),
            vol.Optional(CONF_PID_SWITCH_INVERTED, default=False): _BOOL,
            **_pid_schema(),
            **_min_max_schema(),
            **_common_schema(),
        }
    ),
    STEP_CLIMATE: vol.Schema({**_pid_schema(), **_min_max_schema(), **_common_schema()}),
}


class ControllerSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure a heater/cooler: pick the entity, then the step for its controller type."""

    def __init__(self) -> None:
        self._entity_id: str | None = None
        self._previous: dict[str, Any] = {}

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        self._previous = dict(self._get_reconfigure_subentry().data)
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        errors = {}
        if user_input is not None:
            entity_id = user_input[CONF_ENTITY_ID]
            if self._entity_used_elsewhere(entity_id):
                errors[CONF_ENTITY_ID] = "already_configured"
            else:
                self._entity_id = entity_id
                domain = split_entity_id(entity_id)[0]
                if domain in (SWITCH_DOMAIN, INPUT_BOOLEAN_DOMAIN):
                    return await self.async_step_switch_type()
                if domain in (NUMBER_DOMAIN, INPUT_NUMBER_DOMAIN):
                    return await self.async_step_number()
                if domain == CLIMATE_DOMAIN:
                    return await self.async_step_climate()

        schema = vol.Schema(
            {
                vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=SUPPORTED_TARGET_DOMAINS)
                )
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or self._previous),
            errors=errors,
        )

    async def async_step_switch_type(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return self.async_show_menu(step_id="switch_type", menu_options=[STEP_ON_OFF, STEP_PWM])

    async def async_step_on_off(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return self._controller_step(STEP_ON_OFF, user_input)

    async def async_step_pwm(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return self._controller_step(STEP_PWM, user_input)

    async def async_step_number(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return self._controller_step(STEP_NUMBER, user_input)

    async def async_step_climate(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return self._controller_step(STEP_CLIMATE, user_input)

    def _entity_used_elsewhere(self, entity_id: str) -> bool:
        current = self._reconfigure_subentry_id if self.source == SOURCE_RECONFIGURE else None
        return any(
            subentry.data.get(CONF_ENTITY_ID) == entity_id
            for subentry_id, subentry in self._get_entry().subentries.items()
            if subentry_id != current
        )

    @callback
    def _controller_step(self, step_id: str, user_input: dict[str, Any] | None) -> SubentryFlowResult:
        errors = {}
        if user_input is not None:
            data = {CONF_ENTITY_ID: self._entity_id, **user_input}
            if CONF_KP in data:
                data[CONF_PID_PARAMS] = [data.pop(CONF_KP), data.pop(CONF_KI), data.pop(CONF_KD)]
            try:
                _cv_controller_target(dict(data))
            except vol.Invalid:
                errors["base"] = "invalid_config"
            else:
                title = self._entity_title()
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_and_abort(
                        self._get_entry(), self._get_reconfigure_subentry(), title=title, data=data
                    )
                return self.async_create_entry(title=title, data=data)

        suggested = user_input
        if suggested is None:
            suggested = dict(self._previous)
            if pid := suggested.pop(CONF_PID_PARAMS, None):
                suggested.update(zip((CONF_KP, CONF_KI, CONF_KD), pid))
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(CONTROLLER_SCHEMAS[step_id], suggested),
            description_placeholders={"entity_id": self._entity_id},
            errors=errors,
        )

    def _entity_title(self) -> str:
        state = self.hass.states.get(self._entity_id)
        return state.name if state else self._entity_id
