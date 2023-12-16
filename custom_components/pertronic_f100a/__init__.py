"""The Pertronic F100A RS485 integration."""
from __future__ import annotations

import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_API_REF,
    DOMAIN,
    MIMIC_0_99_LEDS_NUM,
    MIMIC_100_199_LEDS_NUM,
    MIMIC_200_256_LEDS_NUM,
    PANEL_NAME_LONG,
    PANEL_NAME_SHORT,
    RS485_INTERFACE_IP,
    RS485_INTERFACE_TCP_PORT,
)
from .pertronic.PertronicF100AMimic import PertronicF100AMimic

_LOGGER = logging.getLogger(__name__)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.TEXT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pertronic F100A RS485 from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in hass.data:
        _LOGGER.debug("hass.data[DOMAIN] doesn't exist, creating... ")
        hass.data[DOMAIN] = {}
    else:
        _LOGGER.debug("hass.data[DOMAIN] found")

    hass.data[DOMAIN][entry.entry_id] = storage = {}
    _LOGGER.info("Loading API module")

    await hass.async_add_executor_job(load_api, storage, entry)

    # Start the interface demon
    pertronic = hass.data[DOMAIN][entry.entry_id][CONF_API_REF]
    await hass.async_add_executor_job(pertronic.start)
    await hass.async_add_executor_job(time.sleep, 1)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading pertronic_f100a_rs485 entry {entry.entry_id}".format)
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def load_api(storage, entry: ConfigEntry):
    """A Doc String"""
    # We have to seperate this to a seperate function as the __init__ function is not async
    storage[CONF_API_REF] = PertronicF100AMimic(
        entry.data.get(RS485_INTERFACE_IP), entry.data.get(RS485_INTERFACE_TCP_PORT)
    )
