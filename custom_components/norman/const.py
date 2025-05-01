"""Constants for the Norman integration."""

from homeassistant.const import Platform

DOMAIN = "norman"

# Platforms
PLATFORMS = [Platform.COVER]

# Config entry keys
CONF_HOST = "host"

# Default values
RECONNECT_INTERVAL = 15  # seconds

# Cover types
COVER_TYPE_SMARTDRAPE = "smartdrape"  # Has position and tilt capabilities
