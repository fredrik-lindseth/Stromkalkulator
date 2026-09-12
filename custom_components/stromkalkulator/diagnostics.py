"""Diagnostics-plattformen for Strømkalkulator.

Selve skjemaet ligger i `diagnostikk.py`, så det kan testes uten HAs
diagnostics-plattform. Denne filen er bare inngangen HA kaller.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .diagnostikk import bygg_diagnostikk

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Returner diagnostikk for et config entry."""
    return await bygg_diagnostikk(hass, entry)
