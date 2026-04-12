"""Integracja Pstryk AIO."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import PstrykApiClientApiKey, PstrykApiError, PstrykAuthError
from .const import (
    DOMAIN,
    PLATFORMS,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    COORDINATOR_KEY_MAIN,
    KEY_METER_DATA_USAGE,
    KEY_METER_DATA_COST,
    KEY_PRICING_DATA_PURCHASE_TODAY,
    KEY_PRICING_DATA_PURCHASE_TOMORROW,
    KEY_PRICING_DATA_PROSUMER_TODAY,
    KEY_PRICING_DATA_PROSUMER_TOMORROW,
    KEY_LAST_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Konfiguruje Pstryk AIO z wpisu konfiguracyjnego."""
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.debug("Rozpoczynanie konfiguracji wpisu dla %s.", entry.title)

    api_key = entry.data[CONF_API_KEY]
    session = async_get_clientsession(hass)
    api_client = PstrykApiClientApiKey(api_key=api_key, session=session)

    async def async_update_data():
        """Pobiera najnowsze dane z API Pstryk (unified-metrics)."""
        _LOGGER.debug("Rozpoczynanie aktualizacji danych dla Pstryk AIO.")

        try:
            now_in_ha_tz = dt_util.now()
            current_local_date = now_in_ha_tz.date()
            tomorrow_local_date = current_local_date + timedelta(days=1)
            now_utc = dt_util.utcnow()

            # Okna czasowe
            start_of_current_month_local = now_in_ha_tz.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            start_of_previous_month_local = (
                start_of_current_month_local - timedelta(days=1)
            ).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            meter_history_start_utc = dt_util.as_utc(start_of_previous_month_local)
            meter_history_end_utc = now_utc

            today_start_utc = dt_util.as_utc(
                now_in_ha_tz.replace(hour=0, minute=0, second=0, microsecond=0)
            )
            today_end_utc = today_start_utc + timedelta(days=1)
            tomorrow_start_utc = today_end_utc
            tomorrow_end_utc = today_end_utc + timedelta(days=1)

            # --- Dane licznika (zużycie + koszty) przez unified-metrics ---
            meter_data_response = await api_client.get_unified_meter(
                resolution="hour",
                window_start=meter_history_start_utc,
                window_end=meter_history_end_utc,
            )
            if meter_data_response is None:
                _LOGGER.warning(
                    "Nie udało się pobrać danych licznika z unified-metrics."
                )

            # Dla kompatybilności z sensor.py który spodziewa się dwóch oddzielnych
            # kluczy (usage i cost), przekazujemy ten sam obiekt pod oboma kluczami.
            # sensor.py pobiera z nich różne pola.
            meter_data_usage_response = meter_data_response
            meter_data_cost_response = meter_data_response

            # --- Pomocnicze funkcje walidacji danych cenowych ---
            def _has_meaningful_price_data(response_data: Optional[dict]) -> bool:
                if not response_data or not isinstance(
                    response_data.get("frames"), list
                ):
                    return False
                for frame in response_data["frames"]:
                    if (
                        frame.get("price_gross") is not None
                        and frame.get("price_gross") != 0.0
                    ):
                        return True
                return False

            def _are_frames_for_expected_date(
                response_data: Optional[dict], expected_date: datetime.date
            ) -> bool:
                if (
                    not response_data
                    or not isinstance(response_data.get("frames"), list)
                    or not response_data["frames"]
                ):
                    return False
                first_frame = response_data["frames"][0]
                start_utc_str = first_frame.get("start")
                if not start_utc_str:
                    return False
                try:
                    start_utc_dt = dt_util.parse_datetime(start_utc_str)
                    if not start_utc_dt:
                        return False
                    return dt_util.as_local(start_utc_dt).date() == expected_date
                except Exception as err:
                    _LOGGER.error(
                        "Błąd podczas sprawdzania daty ramek: %s", err
                    )
                    return False

            # --- Ceny zakupu i sprzedaży (unified-metrics, jedno wywołanie) ---
            # DZIŚ
            refresh_today = (
                coordinator._date_prices_today_fetched != current_local_date
                or coordinator._cached_pricing_today is None
            )

            if refresh_today:
                _LOGGER.debug(
                    "Pobieranie cen na dziś (%s) przez unified-metrics.",
                    current_local_date,
                )
                pricing_today_response = await api_client.get_unified_pricing(
                    window_start=today_start_utc,
                    window_end=today_end_utc,
                )
                if pricing_today_response and pricing_today_response.get("frames"):
                    coordinator._cached_pricing_today = pricing_today_response
                    coordinator._date_prices_today_fetched = current_local_date
                    _LOGGER.info(
                        "Pobrano i zbuforowano ceny na dziś (%s).",
                        current_local_date,
                    )
                else:
                    _LOGGER.warning(
                        "Brak danych cenowych na dziś (%s). Używam cache.",
                        current_local_date,
                    )
                    pricing_today_response = coordinator._cached_pricing_today or {}
            else:
                _LOGGER.debug(
                    "Używanie zbuforowanych cen na dziś (%s).", current_local_date
                )
                pricing_today_response = coordinator._cached_pricing_today or {}

            # Reset cache jutra przy zmianie dnia
            if coordinator._date_prices_tomorrow_valid_for != tomorrow_local_date:
                _LOGGER.info(
                    "Nowy dzień dla danych 'jutro': %s. Resetowanie cache.",
                    tomorrow_local_date,
                )
                coordinator._cached_pricing_tomorrow = {}
                coordinator._date_prices_tomorrow_valid_for = tomorrow_local_date

            # JUTRO
            if coordinator._cached_pricing_tomorrow and coordinator._cached_pricing_tomorrow.get("frames"):
                _LOGGER.debug(
                    "Używanie zbuforowanych cen na jutro (%s).", tomorrow_local_date
                )
                pricing_tomorrow_response = coordinator._cached_pricing_tomorrow
            else:
                _LOGGER.info(
                    "Pobieranie cen na jutro (%s) przez unified-metrics.",
                    tomorrow_local_date,
                )
                pricing_tomorrow_raw = await api_client.get_unified_pricing(
                    window_start=tomorrow_start_utc,
                    window_end=tomorrow_end_utc,
                )
                if _has_meaningful_price_data(
                    pricing_tomorrow_raw
                ) and _are_frames_for_expected_date(
                    pricing_tomorrow_raw, tomorrow_local_date
                ):
                    coordinator._cached_pricing_tomorrow = pricing_tomorrow_raw
                    pricing_tomorrow_response = pricing_tomorrow_raw
                    _LOGGER.info(
                        "Pobrano i zbuforowano ceny na jutro (%s).",
                        tomorrow_local_date,
                    )
                else:
                    _LOGGER.debug(
                        "Ceny na jutro (%s) jeszcze niedostępne.",
                        tomorrow_local_date,
                    )
                    coordinator._cached_pricing_tomorrow = {}
                    pricing_tomorrow_response = {}

            # unified-metrics zwraca buy_price i sell_price w tych samych ramkach,
            # więc przekazujemy ten sam obiekt pod kluczami zakupu i sprzedaży.
            data_payload = {
                KEY_METER_DATA_USAGE: meter_data_usage_response,
                KEY_METER_DATA_COST: meter_data_cost_response,
                KEY_PRICING_DATA_PURCHASE_TODAY: pricing_today_response,
                KEY_PRICING_DATA_PURCHASE_TOMORROW: pricing_tomorrow_response,
                KEY_PRICING_DATA_PROSUMER_TODAY: pricing_today_response,
                KEY_PRICING_DATA_PROSUMER_TOMORROW: pricing_tomorrow_response,
                KEY_LAST_UPDATE: dt_util.utcnow().isoformat(),
            }

            _LOGGER.info(
                "Dane Pstryk AIO zaktualizowane. "
                "Licznik: %s, Ceny dziś: %s, Ceny jutro: %s",
                "OK" if meter_data_response else "BRAK",
                "OK" if pricing_today_response.get("frames") else "BRAK",
                "OK" if pricing_tomorrow_response.get("frames") else "BRAK",
            )
            return data_payload

        except PstrykAuthError as err:
            _LOGGER.error("Błąd autoryzacji podczas aktualizacji: %s", err)
            raise UpdateFailed(f"Błąd autoryzacji: {err}") from err
        except PstrykApiError as err:
            _LOGGER.error("Błąd API podczas aktualizacji: %s", err)
            raise UpdateFailed(f"Błąd API: {err}") from err
        except Exception as err:
            _LOGGER.exception("Nieoczekiwany błąd podczas aktualizacji: %s", err)
            raise UpdateFailed(f"Nieoczekiwany błąd: {err}") from err

    update_interval_minutes = entry.options.get(
        "update_interval", DEFAULT_UPDATE_INTERVAL_MINUTES
    )
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN} ({entry.title})",
        update_method=async_update_data,
        update_interval=timedelta(minutes=update_interval_minutes),
    )

    # Cache dla cen — unified-metrics zwraca buy+sell razem
    coordinator._cached_pricing_today = None
    coordinator._cached_pricing_tomorrow = {}
    coordinator._date_prices_today_fetched = None
    coordinator._date_prices_tomorrow_valid_for = None

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        _LOGGER.warning("Pierwsze odświeżenie danych nie powiodło się.")

    hass.data[DOMAIN][entry.entry_id] = {
        "api_client": api_client,
        COORDINATOR_KEY_MAIN: coordinator,
    }

    entry.async_on_unload(
        entry.add_update_listener(async_update_options_listener)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "Pomyślnie skonfigurowano Pstryk AIO dla %s.", entry.title
    )
    return True


async def async_update_options_listener(
    hass: HomeAssistant, entry: ConfigEntry
):
    """Obsługuje aktualizacje opcji konfiguracyjnych."""
    _LOGGER.debug(
        "Opcje dla %s zaktualizowane, przeładowanie integracji.", entry.entry_id
    )
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Zwalnia zasoby przy usuwaniu integracji."""
    _LOGGER.info("Usuwanie wpisu Pstryk AIO dla %s.", entry.title)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id)
            _LOGGER.info(
                "Pomyślnie usunięto integrację Pstryk AIO dla %s.", entry.title
            )
    else:
        _LOGGER.error(
            "Nie udało się odładować platform dla %s.", entry.title
        )

    return unload_ok
