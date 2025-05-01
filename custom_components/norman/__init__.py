"""Integration for Norman window coverings."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import NormanApiClient, NormanConnectionError
from .const import DOMAIN, PLATFORMS
from .coordinator import NormanCoordinator

_LOGGER = logging.getLogger(__name__)

type NormanConfigEntry = ConfigEntry[NormanApiClient]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Norman from a config entry."""

    # Create API instance
    api = NormanApiClient(entry.data[CONF_HOST])

    # Validate the API connection
    try:
        await api.async_validate_connection()
    except NormanConnectionError as err:
        await api.async_close()
        raise ConfigEntryNotReady(f"Failed to connect to Norman hub: {err}") from err

    # Create coordinator for data updates
    coordinator = NormanCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator for platforms to access
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Start listening to hub notifications for real-time updates in background task
    # This will be automatically cancelled when the entry is unloaded
    entry.async_create_background_task(
        hass, coordinator.listen_notifications(), "Notification Listener"
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Add an entry cleanup function when unloading
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.async_close()

        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
