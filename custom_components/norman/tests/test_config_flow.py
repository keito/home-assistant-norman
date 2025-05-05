"""Test the Norman config flow."""

from unittest.mock import patch

import pytest

from custom_components.norman.api import NormanApiError, NormanConnectionError
from custom_components.norman.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG

VALIDATE_CONN = "custom_components.norman.api.NormanApiClient.async_validate_connection"


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "custom_components.norman.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["handler"] == DOMAIN
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}
    data_schema = result.get("data_schema")
    assert data_schema is not None
    assert isinstance(data_schema.schema[CONF_HOST], type)


async def test_flow_success(hass: HomeAssistant) -> None:
    """Test that we can configure with valid mock config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(VALIDATE_CONN, return_value=True):
        result = await hass.config_entries.flow.async_configure(  # type: ignore[call-arg]
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Norman Hub (test_host)"
    assert result.get("data") == MOCK_CONFIG
    assert result.get("result")


async def test_flow_failure(hass: HomeAssistant) -> None:
    """Test that a validation exception fails the config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(VALIDATE_CONN, side_effect=NormanConnectionError):
        result = await hass.config_entries.flow.async_configure(  # type: ignore[call-arg]
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}

    with patch(VALIDATE_CONN, side_effect=NormanApiError):
        result = await hass.config_entries.flow.async_configure(  # type: ignore[call-arg]
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result.get("errors") == {"base": "invalid_response"}

    with patch(VALIDATE_CONN, side_effect=Exception):
        result = await hass.config_entries.flow.async_configure(  # type: ignore[call-arg]
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result.get("errors") == {"base": "unknown"}
