# Smart Thermostat with auto Heat/Cool mode, PID control and PWM (Home Assistant component)

Thermostat was designed to control different kind of entities (not only switchable like in [generic_thermostat]).

### Supported domains and modes for heaters and coolers:

* `switch`, `input_boolean` - Basic on/off like [generic_thermostat] or PWM mode.
* `climate` - PID regulator.
* `number`, `input_number` -  PID regulator (additional switch is required).

### Current features:

* Support multiply heaters/coolers.
* Supports `heat_cool` mode.
* Supports all Home Assistant preset modes
* Supports invert logic of the heater/cooler.
* Protection if target sensor does not report values for period of time (`sensor_stale_duration`).
* Configured entirely from the UI (no YAML).

> **Upgrading from `smart_thermostat`:** this integration uses its own domain, `pid_pwm_smart_thermostat`, so it can
> be installed alongside the original component, and it is **UI-only**: YAML `climate:` platform configs are not
> supported. Recreate each thermostat from the UI (the options below keep the same names), then remove the old YAML.
> For debug logs use the logger name `custom_components.pid_pwm_smart_thermostat`.

## Installation (via HACS)

This is recommended way, which will handle one-click upgrade in HACS.

1. Install [hacs] if it is not installed.
2. Open HACS -> Integrations. Click 3 dots in the upper right corner.
3. Click Custom repositories.
4. Add `https://github.com/diegort/ha-pid-pwm-smart-thermostat` repository (category: Integration).
5. Find `PID PWM Smart Thermostat` and click install button.

## Installation (Manual)

NOTE: This is not recommended way, because you will need to upgrade component manually. 

1. Copy `/custom_components/pid_pwm_smart_thermostat` to your `<config_dir>/custom_components/` directory.

   * On HassIO the final location will be `/config/custom_components/pid_pwm_smart_thermostat`.
   * On Supervised the final location will be `/usr/share/hassio/homeassistant/custom_components/pid_pwm_smart_thermostat`.
   * _NOTE: You will need to create the `custom_components` folder if it does not exist._

1. Restart Home Assistant Core.

## Configuration

1. Go to **Settings -> Devices & services -> Add integration** and pick **PID PWM Smart Thermostat**.
2. Fill in the thermostat settings (see [Thermostat options](#thermostat-options)).
   They can be changed later with **Configure**.
3. On the integration page, use **Add heater** / **Add cooler** for each controlled entity. The next step depends on
   the entity domain (see [Controllers](#controllers)): switches ask for on/off or PWM mode, numbers and climates
   for PID parameters. Each heater/cooler can be reconfigured or deleted from its own menu.
   The climate entity is created once the first heater or cooler is added.

## Glossary

* `target_temp` - Climate target temperature, can be changed in UI. Initial can be set via the `target_temp` option.
* `cur_temp` - Current sensor temperature. Will be reported by `target_sensor` entity.
* `CONFIG.xxx` - Reference to a thermostat option.
* `CONFIG.CONTROLLER.xxx` - Reference to a heater/cooler option.

## Thermostat options

* Name _(Required)_ - Climate entity name. Can be changed later by renaming the integration entry.
* `target_sensor` _(Required)_ - Target temperature sensor (`sensor`, `input_number` or `number`).
* `sensor_stale_duration` _(Optional)_ - Thermostat will stop all controllers if no data received from sensor during this period.
* `min_temp` _(Optional, default=7)_ - Set minimum set point available.
* `max_temp` _(Optional, default=35)_ - Set maximum set point available.
* `target_temp` _(Optional)_ - Initial target temperature.
* `precision` _(Optional)_ - Precision for this device. Supported values are 0.1, 0.5 and 1.0. Default: 0.1 for Celsius and 1.0 for Fahrenheit.
* `initial_hvac_mode` _(Optional)_ - Initial HVAC mode.
* `heat_cool_disabled` _(Optional, default=false)_ - Disable `heat_cool` mode.
* `heat_cool_cold_tolerance` _(Optional, default=0.3)_ - Cold tolerance for turning on heater controllers. Used only in `heat_cool` mode.
* `heat_cool_hot_tolerance` _(Optional, default=0.3)_ - Hot tolerance for turning on cooler controllers. Used only in `heat_cool` mode.
* Preset temperatures _(Optional)_ - `away`, `eco`, `comfort`, `home`, `sleep`, `boost`. Only the presets you fill in
  are offered; if none are set, the preset mode feature is not available.

## Common behavior

Initial HVAC mode can be set via the `initial_hvac_mode` option.

Thermostat behavior will depend on active HVAC mode. HVAC mode can be set in UI. 

_**NOTE: Smart thermostat will always take full control of the heaters/coolers. 
So it will turn them on/off back if you change their states manually**_

### HVAC_MODE = `heat`
_NOTE: available if at least one `CONFIG.heater` was defined._

* All **heater** controllers will be turned on. Specific behavior of each **heater** will depend on the controller type.
* All **cooler** controllers will be turned off.

### HVAC_MODE = `cool`

_NOTE: available if at least one `CONFIG.cooler` was defined._

* All **cooler** controllers will be turned on. Specific behavior of each **cooler** will depend on the controller type.
* All **heater** controllers will be turned off.

### HVAC_MODE = `heat_cool` 

_NOTE: available if at least one `CONFIG.heater` and at least one `CONFIG.cooler` were defined._

* If `cur_temp >= target_temp + CONFIG.heat_cool_hot_tolerance` 
  * All **cooler** controllers will be turned on.
  * All **heater** controllers will be turned off.
  * Specific behavior of each heater/cooler will depend on the controller type.


* If `cur_temp <= target_temp - CONFIG.heat_cool_cold_tolerance` 
  * All **heater** controllers will be turned on.
  * All **cooler** controllers will be turned off.
  * Specific behavior of each heater/cooler will depend on the controller type.

_NOTE: turning on controller **DOES NOT MEAN** turning on `CONFIG.CONTROLLER.entity_id` inside controller. 
Controller behavior depends on the **specific controller logic** and described below for each controller._


## Controllers

A specific controller is created for each heater/cooler based on its entity domain. 

### Switch controller (ON/OFF)

Domains: `switch`,`input_boolean` 

#### Options

* `entity_id` _(Required)_ - Target entity ID.
* `inverted` _(Optional, default=false)_ - Need to invert `entity_id` logic.
* `keep_alive` _(Optional)_ - Send keep-alive interval. Use with heaters, coolers,  A/C units that shut off if they don’t receive a signal from their remote for a while. 
* `min_cycle_duration` _(Optional, default=null)_ - Minimal cycle duration. Used to protect from on/off cycling.
* `cold_tolerance` _(Optional, default=0.3)_ - Cold tolerance.
* `hot_tolerance` _(Optional, default=0.3)_ - Hot tolerance.

#### Behavior

* Turn on `entity_id` if `cur_temp <= target_temp - cold_tolerance` (heater) or `cur_temp >= target_temp + self._hot_tolerance` (cooler)
* No `entity_id` changes will be performed if config `min_cycle_duration` was set and enough time was not passed since last switch.
* Behavior on/off will be inverted if `inverted` option was set to `true`

### PWM Switch PID controller

Domains: `switch`,`input_boolean`.

See [General PID explanation](docs/PID.md) how to tune PID parameters.

* Internal PID limits are integers, defined as constants `PWM_SWITCH_MIN_VALUE` and `PWM_SWITCH_MAX_VALUE` (0, 100).
  So, you must use this limits when tuning the PID params. 

#### Options

* `entity_id` _(Required)_ - Target entity ID.
* `inverted` _(Optional, default=false)_ - Need to invert `entity_id` logic.
* `keep_alive` _(Optional)_ - Send keep-alive interval. Use with heaters, coolers,  A/C units that shut off if they don’t receive a signal from their remote for a while. 
* `Kp`, `Ki`, `Kd` _(Required)_ - PID params (_Always positive, will be inverted internally for cool mode_).
* `pid_sample_period` _(Optional)_ - PID constant sample time period.
* `pwm_period`  _(Required)_ - PWM period. Switch will be turned on and turned off according internal PID output once in this period.  

#### Behavior

* PID output will be calculated internally based on the provided PID params.
* `pwm_period` will be separated to two parts: `ON` and `OFF`. Each part duration will depend on PID output. 
* PWM on/off need will be checked every `pwm_period/100` time **but not often than each 1 second**. (`PWM_SWITCH_MAX_VALUE` internal const variable)
* Behavior on/off will be inverted if `inverted` option was set to `true`.
* It is keep on/off state duration before Home Assistant restart. Last change time is saved in thermostat state attributes.

NOTE: Select **PWM with PID** when adding a `switch`/`input_boolean` heater or cooler.

### Climate controller (PID mode supported)

Domains: `climate`

See [General PID explanation](docs/PID.md) how to tune PID parameters.

#### Options

* `entity_id` _(Required)_ - Target entity ID.
* `inverted` _(Optional, default=false)_ - Need to invert `entity_id` logic.
* `keep_alive` _(Optional)_ - Send keep-alive interval. Use with heaters, coolers,  A/C units that shut off if they don’t receive a signal from their remote for a while. 
* `Kp`, `Ki`, `Kd` _(Required)_ - PID params (_Always positive, will be inverted internally for cool mode_).
* `pid_sample_period` _(Optional)_ - PID constant sample time period.
* `min` _(Optional)_ - Minimum temperature which can be set. Attribute `min_temp` from `entity_id` will be used if not specified.
* `max` _(Optional)_ - Maximum temperature which can be set. Attribute `max_temp` from `entity_id` will be used if not specified.

#### Behavior

* Climate `entity_id` will be turned on when controller is active.
* Climate `entity_id` will be turned off when controller is not active.
* Climate `entity_id` temperature will be adjusted every `pid_sample_period` it is provided, or on every `CONFIG.target_sensor` update if `pid_sample_period` is not provided.
* PID params will be inverted if `inverted` was set to `true`

### Number + Switch controller (PID mode supported)

Domains: `number`,`input_number`

See [General PID explanation](docs/PID.md) how to tune PID parameters.

#### Options

* `entity_id` _(Required)_ - Target entity ID.
* `inverted` _(Optional, default=false)_ - Need to invert `entity_id` logic.
* `keep_alive` _(Optional)_ - Send keep-alive interval. Use with heaters, coolers,  A/C units that shut off if they don’t receive a signal from their remote for a while. 
* `Kp`, `Ki`, `Kd` _(Required)_ - PID params (_Always positive, will be inverted internally for cool mode_).
* `pid_sample_period` _(Optional)_ - PID constant sample time period.
* `min` _(Optional)_ - Minimum temperature which can be set. Attribute `min` from `entity_id` will be used if not specified.
* `max` _(Optional)_ - Maximum temperature which can be set. Attribute `max` from `entity_id` will be used if not specified.
* `switch_entity_id` _(Required)_ - Switch entity which belongs to `switch`,`input_boolean` domains.
* `switch_inverted` _(Optional, default=false)_ - Is `switch_entity_id` inverted?

#### Behavior

* Switch `switch_entity_id` will be turned on when controller is active.
* Switch `switch_entity_id` will be turned off when controller is not active.
* Number `entity_id` temperature will be adjusted every `pid_sample_period` it is provided, or on every `CONFIG.target_sensor` update if `pid_sample_period` is not provided.
* PID params will be inverted if `inverted` was set to `true`
* `switch_entity_id` behavior will be inverted if `switch_inverted` was set to `true`



## Reporting an Issue

1. Setup your logger to print debug messages for this component using:
```yaml
logger:
  default: info
  logs:
    custom_components.pid_pwm_smart_thermostat: debug
```
1. Restart HA
1. Verify you're still having the issue
1. File an issue in this GitHub Repository containing your HA log (Developer section > Info > Load Full Home Assistant Log)
   * You can paste your log file at pastebin https://pastebin.com/ and submit a link.
   * Please include details about your setup (Pi, NUC, etc, docker?, HassOS?)
   * The log file can also be found at `/<config_dir>/home-assistant.log`
   

[generic_thermostat]: https://www.home-assistant.io/integrations/generic_thermostat/
[hacs]: https://hacs.xyz
[General PID explanation]: (docs/PID.md)
