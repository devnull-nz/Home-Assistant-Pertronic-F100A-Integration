"""Support for Binary inputs from a command centre server."""
from __future__ import annotations

import logging

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_API_REF,
    DOMAIN,
    MIMIC_0_99_LEDS_NUM,
    MIMIC_100_199_LEDS_NUM,
    MIMIC_200_256_LEDS_NUM,
)
from .pertronic.PertronicF100AMimic import PertronicF100AMimic

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up entry."""
    _LOGGER.info("Loading f100a lcd text entities")
    sensors: list[PertronicLCDText] = []
    pertronic: PertronicF100AMimic = hass.data[DOMAIN][entry.entry_id][CONF_API_REF]

    sensors.append(PertronicLCDText(1, pertronic, entry))
    sensors.append(PertronicLCDText(2, pertronic, entry))

    async_add_entities(sensors)


class PertronicLCDText(TextEntity):
    # Implement one of these methods.

    def __init__(self, lcd_line, pertronic: PertronicF100AMimic, entry: ConfigEntry):
        self._lcd_line = lcd_line
        self._pertronic = pertronic

        self._attr_name = "{} LCD {}".format("F100A", lcd_line)
        self._attr_unique_id = "{}_{}_LCD_{}".format(
            "F100A", entry.entry_id, self._lcd_line
        )

        self._mode = "text"
        self._native_max = 100
        self._native_min = 0
        self._pattern = None
        self._native_value = "NO_DATA"
        pertronic.register_lcd_callback(self.proccess_callback)

    def set_value(self, value: str) -> None:
        """Set the text value."""
        return False

    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        return False

    @property
    def native_value(self):
        return self._native_value

    def proccess_callback(self, text_0, text_1):
        if self._lcd_line == 1:
            self._native_value = text_0
        else:
            self._native_value = text_1

    async def async_base_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.proccess_callback(
            self._pertronic.get_lcd_text(1), self._pertronic.get_lcd_text(2)
        )
