"""Base entity for DWD Mobile."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, VERSION
from .coordinator import DwdMobileCoordinator


class DwdMobileEntity(CoordinatorEntity[DwdMobileCoordinator]):
    """Common base for DWD Mobile entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DwdMobileCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=NAME,
            manufacturer="Deutscher Wetterdienst (DWD) / Community Integration",
            model="Mobile DWD weather source",
            sw_version=VERSION,
            configuration_url="https://github.com/svemmiii/DWD-mobile",
        )

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        return data.device_attributes if data is not None else {}
