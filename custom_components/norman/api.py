"""API client for Norman window coverings."""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
import logging
import time
from typing import Any

import aiohttp
from aiohttp import ClientResponse, ClientTimeout
from aiohttp.client_exceptions import ClientError

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

# API endpoints
ENDPOINT_REGISTRATION = "/NM/v1/registration"
ENDPOINT_GET_ALL_PERIPHERAL = "/NM/v1/GetAllPeripheral"
ENDPOINT_STATUS = "/NM/v1/status"
ENDPOINT_CONTROL = "/NM/v1/control"


class NormanApiError(HomeAssistantError):
    """Exception to indicate an API error occurred."""


class NormanConnectionError(HomeAssistantError):
    """Exception to indicate a connection error occurred."""


class NormanApiClient:
    """API client for Norman Hub."""

    def __init__(self, host: str) -> None:
        """Initialize the API client.

        Args:
            host: IP address or hostname of the Norman hub

        """
        self.host = host
        self.base_url = f"http://{host}:10123"
        self._session = aiohttp.ClientSession()
        self._thing_name: str | None = None
        self._notif_response: ClientResponse | None = None

    async def async_validate_connection(self) -> bool:
        """Test if we can connect to the Norman hub.

        Returns:
            True if connection is successful

        Raises:
            NormanConnectionError: If connection fails

        """
        try:
            await self._async_registration()
        except ClientError as err:
            _LOGGER.error("Failed to connect to Norman hub at %s", self.host)
            raise NormanConnectionError from err
        else:
            return True

    async def _async_registration(self) -> dict[str, Any]:
        """Send registration request to get ThingName.

        Returns:
            Registration response data

        Raises:
            NormanApiError: If API returns an error

        """
        timestamp = int(time.time())
        payload = {"Timestamp": timestamp}

        try:
            response = await self._session.post(
                f"{self.base_url}{ENDPOINT_REGISTRATION}",
                json=payload,
                timeout=ClientTimeout(total=10),
            )
            response.raise_for_status()
            data = await response.json()

            if data.get("Error", 0) != 0:
                raise NormanApiError(
                    f"Registration failed with error code: {data.get('Error')}"
                )

            self._thing_name = data.get("ThingName")
        except ClientError as err:
            raise NormanConnectionError(
                f"Failed to connect to Norman hub: {err}"
            ) from err
        except (json.JSONDecodeError, KeyError) as err:
            raise NormanApiError(f"Invalid response from Norman hub: {err}") from err
        else:
            return data

    async def async_get_devices(self) -> dict[str, Any]:
        """Get list of all devices from the Norman hub.

        Returns:
            Dictionary with device information

        Raises:
            NormanApiError: If API returns an error
            NormanConnectionError: If connection fails

        """
        # First ensure we have a ThingName
        if not self._thing_name:
            await self._async_registration()

        timestamp = int(time.time())
        task_id = int(time.time() * 1000) % 10000  # Random task ID
        payload: dict[str, Any] = {
            "ThingName": self._thing_name,
            "TaskID": task_id,
            "Timestamp": timestamp,
        }

        try:
            response = await self._session.post(
                f"{self.base_url}{ENDPOINT_GET_ALL_PERIPHERAL}",
                json=payload,
                timeout=ClientTimeout(total=10),
            )
            response.raise_for_status()
            data = await response.json()

            status = data.get("status", {})
            if status.get("code", 0) != 0:
                error_msg = status.get("error", "Unknown error")
                raise NormanApiError(f"GetAllPeripheral failed: {error_msg}")
        except ClientError as err:
            raise NormanConnectionError(
                f"Failed to connect to Norman hub: {err}"
            ) from err
        except (json.JSONDecodeError, KeyError) as err:
            raise NormanApiError(f"Invalid response from Norman hub: {err}") from err
        else:
            return data

    async def async_get_status(self) -> dict[str, Any]:
        """Get current status of all devices.

        Returns:
            Dictionary with device status information

        Raises:
            NormanApiError: If API returns an error
            NormanConnectionError: If connection fails

        """
        timestamp = int(time.time())
        payload = {"Timestamp": timestamp}

        try:
            response = await self._session.post(
                f"{self.base_url}{ENDPOINT_STATUS}",
                json=payload,
                timeout=ClientTimeout(total=10),
            )
            response.raise_for_status()
            data = await response.json()

            if data.get("Error", 0) != 0:
                raise NormanApiError(
                    f"Status request failed with error code: {data.get('Error')}"
                )
        except ClientError as err:
            raise NormanConnectionError(
                f"Failed to connect to Norman hub: {err}"
            ) from err
        except (json.JSONDecodeError, KeyError) as err:
            raise NormanApiError(f"Invalid response from Norman hub: {err}") from err
        else:
            return data

    async def async_set_position(
        self, device_id: int, bottom_rail_position: int, middle_rail_position: int
    ) -> None:
        """Set cover position.

        Args:
            device_id: ID of the Norman device
            bottom_rail_position: Bottom rail position (0=closed, 100=open)
            middle_rail_position: Middle rail position (0=closed, 100=open)

        Raises:
            NormanApiError: If API returns an error
            NormanConnectionError: If connection fails

        """
        timestamp = int(time.time())
        task_id = int(time.time() * 1000) % 10000  # Random task ID
        payload = {
            "PeripheralUID": device_id,
            "Timestamp": timestamp,
            "TaskID": task_id,
            "BottomRailPosition": bottom_rail_position,
            "MiddleRailPosition": middle_rail_position,
        }

        try:
            response = await self._session.post(
                f"{self.base_url}{ENDPOINT_CONTROL}",
                json=payload,
                timeout=ClientTimeout(total=10),
            )
            response.raise_for_status()
            data = await response.json()

            if data.get("Error", 0) != 0:
                raise NormanApiError(
                    f"Control request failed with error code: {data.get('Error')}"
                )

        except ClientError as err:
            raise NormanConnectionError(
                f"Failed to connect to Norman hub: {err}"
            ) from err
        except (json.JSONDecodeError, KeyError) as err:
            raise NormanApiError(f"Invalid response from Norman hub: {err}") from err

    async def async_close(self) -> None:
        """Close the API client session."""
        if self._notif_response:
            self._notif_response.close()
            self._notif_response = None
        if self._session:
            await self._session.close()

    async def async_listen_notifications(self) -> AsyncIterator[dict[str, Any]]:
        """Listen for peripheral state change notifications via long-poll."""
        url = f"{self.base_url}/NM/v1/notification"
        # Disable timeouts for long-poll
        timeout = ClientTimeout(total=None)
        try:
            async with self._session.post(url, timeout=timeout) as response:
                response.raise_for_status()
                self._notif_response = response
                buffer: str = ""
                depth = 0
                while True:
                    chunk = await response.content.read(1024)
                    if not chunk:
                        # No more data, stream closed
                        break
                    text = chunk.decode(errors="ignore")
                    for char in text:
                        if char == "{":
                            depth += 1
                            buffer += char
                        elif char == "}":
                            buffer += char
                            depth -= 1
                            if depth == 0:
                                try:
                                    obj = json.loads(buffer)
                                except json.JSONDecodeError:
                                    _LOGGER.debug(
                                        "Failed to parse notification JSON: %s", buffer
                                    )
                                else:
                                    # Skip initial acknowledgements without PeripheralList
                                    if "PeripheralList" in obj:
                                        yield obj
                                buffer = ""
                        elif depth > 0:
                            buffer += char
        except ClientError as err:
            raise NormanConnectionError(
                f"Notification listener connection error: {err}"
            ) from err
        finally:
            self._notif_response = None
