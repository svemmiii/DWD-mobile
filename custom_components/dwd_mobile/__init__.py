"""DWD Mobile integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import DwdMobileCoordinator

PLATFORMS: list[Platform] = [Platform.WEATHER, Platform.SENSOR]

type DwdMobileConfigEntry = ConfigEntry[DwdMobileCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DwdMobileConfigEntry) -> bool:
    """Set up DWD Mobile from a config entry."""
    coordinator = DwdMobileCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DwdMobileConfigEntry) -> bool:
    """Unload a DWD Mobile config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
