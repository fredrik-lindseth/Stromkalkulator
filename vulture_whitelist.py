# Vulture whitelist for Strømkalkulator
# These are false positives - used by Home Assistant framework

# Home Assistant requires these entry points
async_setup_entry
async_unload_entry
async_setup_entry

# Home Assistant requires these methods in sensors
native_value
extra_state_attributes
device_info

# Home Assistant config flow
async_step_user
async_step_sensors
async_step_pricing
async_step_init
async_get_options_flow

# Class attributes used by HA
_attr_unique_id
_attr_name
_attr_native_unit_of_measurement
_attr_state_class
_attr_icon
_attr_suggested_display_precision
_attr_entity_category
_device_group

# Used in Home Assistant
PLATFORMS
