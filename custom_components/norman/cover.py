"""Support for Norman window coverings."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, cached_property
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import NormanApiError, NormanConnectionError
from .const import COVER_TYPE_SMARTDRAPE, DOMAIN
from .coordinator import NormanCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Norman cover devices."""
    coordinator: NormanCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[NormanCoverBase] = []
    for device_id, device_data in coordinator.data.items():
        cover_type = device_data.type

        if cover_type == COVER_TYPE_SMARTDRAPE:
            entities.append(NormanBlind(coordinator, device_id, entry))
        else:
            # TODO: Support other kinds of blinds
            raise HomeAssistantError(
                f"Unsupported cover type {cover_type} for device {device_id}"
            )

    async_add_entities(entities)


class NormanCoverBase(CoordinatorEntity[NormanCoordinator], CoverEntity):
    """Base class for Norman covers."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.STOP
    )

    def __init__(
        self,
        coordinator: NormanCoordinator,
        device_id: int,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator)
        self._device_id = device_id

        device_data = self.coordinator.data[device_id]

        self._attr_unique_id = str(device_id)
        self._attr_name = device_data.name or f"Norman Cover {device_id}"

        # Create device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=self._attr_name,
            manufacturer="Norman",
            model=f"Window Covering {device_data.module_type}",
            suggested_area=device_data.room_name,
            sw_version=device_data.firmware_version,
        )

    @cached_property
    def device_class(self) -> CoverDeviceClass | None:
        """Return the device class."""
        return CoverDeviceClass.BLIND

    @property
    def available(self) -> bool:  # type: ignore[override]
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        # TODO: handle case where individual devices can go offline
        return self._device_id in self.coordinator.data

    @property
    def is_closed(self) -> bool | None:  # type: ignore[override]
        """Return if the cover is closed.

        Returns:
            True if the cover is closed, False otherwise, None if unknown

        """
        position = self.current_cover_position
        if position is None:
            return None
        return position == 0

    @property
    def current_cover_position(self) -> int | None:  # type: ignore[override]
        """Return current position of the cover.

        Norman API returns 0 as closed and 100 as open, which aligns with HA's convention.

        Returns:
            Position from 0 (closed) to 100 (open), None if unknown

        """
        if not self.coordinator.data or self._device_id not in self.coordinator.data:
            return None

        device_data = self.coordinator.data[self._device_id]
        return device_data.bottom_rail_position

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        # Close bottom rail to 0, preserve middle rail
        await self._async_set_position(bottom=0, middle=None, action="close cover")

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        # Open bottom rail to 100, preserve middle rail
        await self._async_set_position(bottom=100, middle=None, action="open cover")

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        # Move bottom rail (cover) to position, preserve middle rail
        await self._async_set_position(
            bottom=position, middle=None, action="set position", value=position
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover by maintaining its current position."""
        current = self.current_cover_position
        if current is None:
            return
        await self._async_set_position(bottom=current, middle=None, action="stop cover")

    async def _async_set_position(
        self,
        bottom: int | None,
        middle: int | None,
        action: str,
        value: int | None = None,
    ) -> None:
        """Set bottom and middle rail positions, preserving the other if None, with error handling."""
        # Fetch current data for defaults
        data = self.coordinator.data.get(self._device_id)
        # Determine bottom rail position
        if bottom is None:
            if data and data.bottom_rail_position is not None:
                bottom_val = data.bottom_rail_position
            else:
                bottom_val = 100
        else:
            bottom_val = bottom

        # Determine middle rail position
        if middle is None:
            if data and data.middle_rail_position is not None:
                middle_val = data.middle_rail_position
            else:
                middle_val = 100
        else:
            middle_val = middle

        try:
            await self.coordinator.api.async_set_position(
                self._device_id, bottom_val, middle_val
            )
            await self.coordinator.async_request_refresh()
        except (NormanApiError, NormanConnectionError) as err:
            raise HomeAssistantError(
                f"Failed to {action} (value: {value}) for {self._attr_name}: {err}"
            ) from err


class NormanBlind(NormanCoverBase):
    """Representation of a Norman blind with tilt capabilities."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.STOP
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    @property
    def current_cover_tilt_position(self) -> int | None:  # type: ignore[override]
        """Return current tilt position of the cover.

        Norman API uses middle_rail_position for tilt (0-100).

        """
        if not self.coordinator.data or self._device_id not in self.coordinator.data:
            return None

        device_data = self.coordinator.data[self._device_id]
        return device_data.middle_rail_position

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        await self._async_set_position(bottom=None, middle=100, action="open tilt")

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        await self._async_set_position(bottom=None, middle=0, action="close tilt")

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        tilt_position = kwargs[ATTR_TILT_POSITION]
        await self._async_set_position(
            bottom=None,
            middle=tilt_position,
            action="set tilt position",
            value=tilt_position,
        )
