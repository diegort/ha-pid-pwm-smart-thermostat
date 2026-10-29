"""Constants for the Smart Thermostat component."""
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    PRECISION_TENTHS,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    Platform,
)

DOMAIN = "pid_pwm_smart_thermostat"
PLATFORMS = [Platform.CLIMATE]

# Config subentry types; also the DATA_SCHEMA keys of the heater/cooler lists
SUBENTRY_HEATER = "heater"
SUBENTRY_COOLER = "cooler"

# Defaults
DEFAULT_NAME = "PID PWM Smart Thermostat"
DEFAULT_SWITCH_TOLERANCE = 0.3
DEFAULT_HEAT_COOL_TOLERANCE = 0.3
# DEFAULT_PID_KP = 1.0
# DEFAULT_PID_KI = 1.0
# DEFAULT_PID_KD = 1.0

# Configuration
CONF_HEATER = "heater"
CONF_COOLER = "cooler"
CONF_INVERTED = "inverted"
CONF_SENSOR = "target_sensor"
CONF_STALE_DURATION = "sensor_stale_duration"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_TARGET_TEMP = "target_temp"
CONF_MIN_DUR = "min_cycle_duration"
CONF_COLD_TOLERANCE = "cold_tolerance"
CONF_HOT_TOLERANCE = "hot_tolerance"
CONF_HEAT_COOL_COLD_TOLERANCE = "heat_cool_cold_tolerance"
CONF_HEAT_COOL_HOT_TOLERANCE = "heat_cool_hot_tolerance"
CONF_KEEP_ALIVE = "keep_alive"
CONF_INITIAL_HVAC_MODE = "initial_hvac_mode"
CONF_PRESETS = "presets"
CONF_HEAT_COOL_DISABLED = "heat_cool_disabled"
CONF_PRECISION = "precision"
CONF_PID_PARAMS = "pid_params"
CONF_PID_SAMPLE_PERIOD = "pid_sample_period"
CONF_PID_MIN = "min"
CONF_PID_MAX = "max"
CONF_PID_SWITCH_ENTITY_ID = "switch_entity_id"
CONF_PID_SWITCH_INVERTED = "switch_inverted"
CONF_PWM_SWITCH_PERIOD = "pwm_period"
