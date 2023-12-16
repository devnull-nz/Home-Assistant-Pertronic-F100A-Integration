"""Support for Binary inputs from a command centre server."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    _LOGGER.info("Loading binary sensors")
    sensors: list[PetronicBinarySensor] = []
    pertronic: PertronicF100AMimic = hass.data[DOMAIN][entry.entry_id][CONF_API_REF]

    sensors.append(PetronicSpecialBinarySensor("Normal", "normal", pertronic, entry))
    sensors.append(PetronicSpecialBinarySensor("Fire", "fire", pertronic, entry))
    sensors.append(PetronicSpecialBinarySensor("Defect", "defect", pertronic, entry))
    sensors.append(PetronicSpecialBinarySensor("Evacute", "evacuate", pertronic, entry))
    sensors.append(
        PetronicSpecialBinarySensor(
            "Slience Alarms", "silence_alarms", pertronic, entry
        )
    )
    sensors.append(
        PetronicSpecialBinarySensor(
            "Device Isloated", "device_isolated", pertronic, entry
        )
    )
    sensors.append(
        PetronicSpecialBinarySensor("PSU Defect", "psu_defect", pertronic, entry)
    )
    sensors.append(
        PetronicSpecialBinarySensor("Sprinkler", "sprinkler", pertronic, entry)
    )
    sensors.append(
        PetronicSpecialBinarySensor(
            "Door Holder Isolated", "door_holder_isolate", pertronic, entry
        )
    )
    sensors.append(
        PetronicSpecialBinarySensor("AUX Isolated", "aux_isolate", pertronic, entry)
    )
    sensors.append(
        PetronicSpecialBinarySensor("Walk Test", "walk_test", pertronic, entry)
    )

    if (
        entry.data.get(MIMIC_0_99_LEDS_NUM) > 0
        or entry.data.get(MIMIC_100_199_LEDS_NUM) > 0
        or entry.data.get(MIMIC_200_256_LEDS_NUM) > 0
    ):
        _LOGGER.info("Using LEDS")

        for led in range(257):
            if led == 0:  # LED 0 does not exist
                continue

            if led <= 99:
                led_nums = entry.data.get(MIMIC_0_99_LEDS_NUM)
                if led_nums < 1:
                    continue
                if not (led <= 0 + led_nums):
                    continue

            elif led <= 199:
                led_nums = entry.data.get(MIMIC_100_199_LEDS_NUM)
                if led_nums < 1:
                    continue
                if not (led <= 100 + led_nums):
                    continue

            elif led <= 256:
                led_nums = entry.data.get(MIMIC_200_256_LEDS_NUM)
                if led_nums < 1:
                    continue
                if not (led <= 200 + led_nums):
                    continue

            # If we've reached here, than the LED is able to be imported
            _LOGGER.debug("Using LED {}".format(led))

            sensor = PetronicBinarySensor(led, pertronic, entry)
            sensors.append(sensor)

        # print(inputs)

        async_add_entities(sensors)


class PetronicBinarySensor(BinarySensorEntity):
    """GCC REST binary sensor."""

    def __init__(self, led_id, pertronic: PertronicF100AMimic, entry: ConfigEntry):
        self._pertronic = pertronic
        self._led_id = led_id

        self._is_on = None

        self._attr_name = "{} LED {}".format("F100A", led_id)
        self._attr_unique_id = "{}_{}_LED_{}".format(
            "F100A", entry.entry_id, self._led_id
        )

        pertronic.register_led_callback(led_id, self.proccess_callback)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    def proccess_callback(self, led_state):
        """Callback processor"""
        self._is_on = led_state
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()

    async def async_base_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.proccess_callback(self._pertronic.get_led_state(self._led_id))

    async def async_get_last_state(self):
        """Returns item state"""
        return self._is_on


class PetronicSpecialBinarySensor(BinarySensorEntity):
    """GCC REST binary sensor."""

    def __init__(
        self, led_name, led_type, pertronic: PertronicF100AMimic, entry: ConfigEntry
    ):
        self._pertronic = pertronic
        self._led_id = led_type

        self._is_on = None

        self._attr_name = "{} {}".format("F100A", led_name)
        self._attr_unique_id = "{}_{}_LED_{}".format(
            "F100A", entry.entry_id, self._led_id
        )

        pertronic.register_special_led_callback(led_type, self.proccess_callback)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    def proccess_callback(self, led_state):
        """Callback processor"""
        self._is_on = led_state
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()

    async def async_base_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.proccess_callback(self._pertronic.get_special_led_state(self._led_id))

    async def async_get_last_state(self):
        """Returns item state"""
        return self._is_on
