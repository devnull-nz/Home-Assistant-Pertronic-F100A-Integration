"""Config flow for Pertronic F100A RS485 integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from .pertronic.PertronicF100AMimic import PertronicF100AMimic

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

def create_host_data_schema(
    panel_name="Pertronic F100a",
    panel_name_short="F100A",
    ip_addr="192.168.1.1",
    port=20108,
    led_0_99=99,
    led_100_199=99,
    led_200_256=56,
):
    """Returns the schema for the UI configuration interface"""
    return vol.Schema(
        {
            vol.Required("panel_name", description={"suggested_value": panel_name}): str,
            vol.Required("panel_name_short", description={"suggested_value": panel_name_short}): str,
            vol.Required("ip_addr", description={"suggested_value": ip_addr}): str,
            vol.Required("port", default=port): int,
            vol.Required("led_0_99", default=led_0_99): int,
            vol.Required("led_100_199", default=led_100_199): int,
            vol.Required("led_200_256", default=led_200_256): int,
        }
    )

def validate_input_with_pertronic(data: dict[str, Any]) -> bool:

    if data["led_0_99"] < 0 or data["led_0_99"] > 99:
        raise InvalidLedLength
    
    if data["led_100_199"] < 0 or data["led_100_199"] > 99:
        raise InvalidLedLength

    if data["led_200_256"] < 0 or data["led_200_256"] > 56:
        raise InvalidLedLength


    mimic = PertronicF100AMimic(data["ip_addr"], data["port"])

    if mimic.test_connection() is not True:
        raise CannotConnect
    return True

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from create_host_data_schema with values provided by the user.
    """

    await hass.async_add_executor_job(validate_input_with_pertronic, data)

    return {
        "panel_name": data["panel_name"],
        "panel_name_short": data["panel_name_short"],
        "ip_addr": data["ip_addr"],
        "port": data["port"],
        "led_0_99": data["led_0_99"],
        "led_100_199": data["led_100_199"],
        "led_200_256": data["led_200_256"],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pertronic F16 Mimic."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=create_host_data_schema()
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except InvalidLedLength:
            errors["base"] = "invalid_led_length"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["panel_name"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=create_host_data_schema(
                user_input["panel_name"], user_input["panel_name_short"], user_input["ip_addr"], user_input["port"], user_input["led_0_99"], user_input["led_100_199"], user_input["led_200_256"]
            ), errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

class InvalidLedLength(HomeAssistantError):
    """Error to indicate there is invalid auth."""
