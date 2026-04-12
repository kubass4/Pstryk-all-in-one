"""Definicje sensorów dla integracji Pstryk AIO - unified-metrics."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    COORDINATOR_KEY_MAIN,
    KEY_METER_DATA_USAGE,
    KEY_METER_DATA_COST,
    KEY_PRICING_DATA_PURCHASE_TODAY,
    KEY_PRICING_DATA_PURCHASE_TOMORROW,
    KEY_PRICING_DATA_PROSUMER_TODAY,
    KEY_PRICING_DATA_PROSUMER_TOMORROW,
    KEY_LAST_UPDATE,
    SENSOR_TODAY_PURCHASE_PRICE,
    SENSOR_TOMORROW_PURCHASE_PRICE,
    SENSOR_TODAY_SALE_PRICE,
    SENSOR_TOMORROW_SALE_PRICE,
    SENSOR_CONSUMPTION_DAILY_COST,
    SENSOR_PRODUCTION_DAILY_YIELD,
    SENSOR_BILLING_BALANCE_MONTHLY_PLN,
    SENSOR_ENERGY_BALANCE_MONTHLY_KWH,
    SENSOR_BILLING_BALANCE_DAILY_PLN,
    SENSOR_ENERGY_BALANCE_DAILY_KWH,
    SENSOR_CONSUMPTION_DAILY_KWH,
    SENSOR_PRODUCTION_DAILY_KWH,
    SENSOR_CONSUMPTION_MONTHLY_KWH,
    SENSOR_PRODUCTION_MONTHLY_KWH,
    SENSOR_CONSUMPTION_MONTHLY_COST_PLN,
    SENSOR_PRODUCTION_MONTHLY_YIELD_PLN,
    FRIENDLY_NAME_PURCHASE_PRICE,
    FRIENDLY_NAME_SALE_PRICE,
    FRIENDLY_NAME_CONSUMPTION_DAILY_COST,
    FRIENDLY_NAME_PRODUCTION_DAILY_YIELD,
    FRIENDLY_NAME_BILLING_BALANCE_MONTHLY_PLN,
    FRIENDLY_NAME_ENERGY_BALANCE_MONTHLY_KWH,
    FRIENDLY_NAME_BILLING_BALANCE_DAILY_PLN,
    FRIENDLY_NAME_ENERGY_BALANCE_DAILY_KWH,
    FRIENDLY_NAME_CONSUMPTION_DAILY_KWH,
    FRIENDLY_NAME_PRODUCTION_DAILY_KWH,
    FRIENDLY_NAME_CONSUMPTION_MONTHLY_KWH,
    FRIENDLY_NAME_PRODUCTION_MONTHLY_KWH,
    FRIENDLY_NAME_CONSUMPTION_MONTHLY_COST_PLN,
    FRIENDLY_NAME_PRODUCTION_MONTHLY_YIELD_PLN,
    CONF_CHEAP_PURCHASE_PRICE_THRESHOLD,
    CONF_EXPENSIVE_PURCHASE_PRICE_THRESHOLD,
    CONF_CHEAP_SALE_PRICE_THRESHOLD,
    CONF_EXPENSIVE_SALE_PRICE_THRESHOLD,
    DEFAULT_CHEAP_PURCHASE_PRICE_THRESHOLD,
    DEFAULT_EXPENSIVE_PURCHASE_PRICE_THRESHOLD,
    DEFAULT_CHEAP_SALE_PRICE_THRESHOLD,
    DEFAULT_EXPENSIVE_SALE_PRICE_THRESHOLD,
    ATTR_PRICE_TODAY,
    ATTR_PRICE_TOMORROW,
    ATTR_PRICE_START_TIME,
    ATTR_PRICE_END_TIME,
    ATTR_PRICE_VALUE_GROSS,
    ATTR_PRICE_IS_CHEAP,
    ATTR_PRICE_IS_EXPENSIVE,
    ATTR_PRICE_UNIT,
    ATTR_DAILY_KWH_CONSUMPTION,
    ATTR_DAILY_KWH_PRODUCTION,
    ATTR_ENERGY_BALANCE_KWH,
    ATTR_MONTHLY_KWH_CONSUMPTION,
    ATTR_MONTHLY_KWH_PRODUCTION,
    ATTR_MONTHLY_PLN_COST,
    ATTR_MONTHLY_PLN_YIELD,
    ATTR_HOURLY_COST_CONSUMPTION,
    ATTR_HOURLY_YIELD_PRODUCTION,
    ATTR_AVERAGE_PRICE,
    ATTR_DAILY_BREAKDOWN_CURRENT_MONTH,
    ATTR_HOURLY_BREAKDOWN_CURRENT_DAY,
    ATTR_DATA_TIMESTAMP,
    ATTR_DATA_STATUS_MESSAGE,
    ATTR_LAST_MONTH_VALUE,
    COST_FRAME_FAE_COST,
    COST_FRAME_RAE_YIELD,
    COST_FRAME_ENERGY_BALANCE_VALUE,
    USAGE_FRAME_FAE_KWH,
    USAGE_FRAME_RAE_KWH,
    USAGE_ENERGY_BALANCE,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS_MAP = {
    SENSOR_TODAY_PURCHASE_PRICE: (
        FRIENDLY_NAME_PURCHASE_PRICE, SensorDeviceClass.MONETARY,
        None, ATTR_PRICE_UNIT, "mdi:transmission-tower-import"
    ),
    SENSOR_TOMORROW_PURCHASE_PRICE: (
        "Cena zakupu prądu (jutro)", SensorDeviceClass.MONETARY,
        None, ATTR_PRICE_UNIT, "mdi:transmission-tower-import"
    ),
    SENSOR_TODAY_SALE_PRICE: (
        FRIENDLY_NAME_SALE_PRICE, SensorDeviceClass.MONETARY,
        None, ATTR_PRICE_UNIT, "mdi:transmission-tower-export"
    ),
    SENSOR_TOMORROW_SALE_PRICE: (
        "Cena sprzedaży prądu (jutro)", SensorDeviceClass.MONETARY,
        None, ATTR_PRICE_UNIT, "mdi:transmission-tower-export"
    ),
    SENSOR_CONSUMPTION_DAILY_COST: (
        FRIENDLY_NAME_CONSUMPTION_DAILY_COST, SensorDeviceClass.MONETARY,
        SensorStateClass.TOTAL, "PLN", "mdi:cash-minus"
    ),
    SENSOR_PRODUCTION_DAILY_YIELD: (
        FRIENDLY_NAME_PRODUCTION_DAILY_YIELD, SensorDeviceClass.MONETARY,
        SensorStateClass.TOTAL, "PLN", "mdi:cash-plus"
    ),
    SENSOR_BILLING_BALANCE_MONTHLY_PLN: (
        FRIENDLY_NAME_BILLING_BALANCE_MONTHLY_PLN, SensorDeviceClass.MONETARY,
        SensorStateClass.TOTAL, "PLN", "mdi:scale-balance"
    ),
    SENSOR_ENERGY_BALANCE_MONTHLY_KWH: (
        FRIENDLY_NAME_ENERGY_BALANCE_MONTHLY_KWH, SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL, UnitOfEnergy.KILO_WATT_HOUR, "mdi:lightning-bolt-circle"
    ),
    SENSOR_BILLING_BALANCE_DAILY_PLN: (
        FRIENDLY_NAME_BILLING_BALANCE_DAILY_PLN, SensorDeviceClass.MONETARY,
        SensorStateClass.TOTAL, "PLN", "mdi:cash-clock"
    ),
    SENSOR_ENERGY_BALANCE_DAILY_KWH: (
        FRIENDLY_NAME_ENERGY_BALANCE_DAILY_KWH, SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL, UnitOfEnergy.KILO_WATT_HOUR, "mdi:lightning-bolt"
    ),
    SENSOR_CONSUMPTION_DAILY_KWH: (
        FRIENDLY_NAME_CONSUMPTION_DAILY_KWH, SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL, UnitOfEnergy.KILO_WATT_HOUR, "mdi:lightning-bolt"
    ),
    SENSOR_PRODUCTION_DAILY_KWH: (
        FRIENDLY_NAME_PRODUCTION_DAILY_KWH, SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL, UnitOfEnergy.KILO_WATT_HOUR, "mdi:solar-panel"
    ),
    SENSOR_CONSUMPTION_MONTHLY_KWH: (
        FRIENDLY_NAME_CONSUMPTION_MONTHLY_KWH, SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL, UnitOfEnergy.KILO_WATT_HOUR, "mdi:lightning-bolt-outline"
    ),
    SENSOR_PRODUCTION_MONTHLY_KWH: (
        FRIENDLY_NAME_PRODUCTION_MONTHLY_KWH, SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL, UnitOfEnergy.KILO_WATT_HOUR, "mdi:solar-panel-large"
    ),
    SENSOR_CONSUMPTION_MONTHLY_COST_PLN: (
        FRIENDLY_NAME_CONSUMPTION_MONTHLY_COST_PLN, SensorDeviceClass.MONETARY,
        SensorStateClass.TOTAL, "PLN", "mdi:cash-minus"
    ),
    SENSOR_PRODUCTION_MONTHLY_YIELD_PLN: (
        FRIENDLY_NAME_PRODUCTION_MONTHLY_YIELD_PLN, SensorDeviceClass.MONETARY,
        SensorStateClass.TOTAL, "PLN", "mdi:cash-plus"
    ),
}


def _normalize_meter_frame(frame: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizuje ramkę z unified-metrics do wspólnego formatu wewnętrznego.

    Nowe API zwraca dane zagnieżdżone w frame.metrics.meter_values i frame.metrics.cost.
    Stare API zwracało je bezpośrednio w ramce.
    Ta funkcja obsługuje oba formaty dla kompatybilności.
    """
    metrics = frame.get("metrics", {})
    meter_values = metrics.get("meter_values") or metrics.get("meterValues") or {}
    cost = metrics.get("cost") or {}

    return {
        "start": frame.get("start"),
        "end": frame.get("end"),
        "is_live": frame.get("is_live", False),
        # Zużycie (import z sieci) - kWh
        USAGE_FRAME_FAE_KWH: frame.get(
            USAGE_FRAME_FAE_KWH,
            meter_values.get("energy_active_import_register", 0) or 0,
        ),
        # Produkcja (eksport do sieci) - kWh
        USAGE_FRAME_RAE_KWH: frame.get(
            USAGE_FRAME_RAE_KWH,
            meter_values.get("energy_active_export_register", 0) or 0,
        ),
        # Bilans energetyczny - kWh
        USAGE_ENERGY_BALANCE: frame.get(
            USAGE_ENERGY_BALANCE,
            meter_values.get("energy_balance", 0) or 0,
        ),
        # Koszt zużycia - PLN
        COST_FRAME_FAE_COST: frame.get(
            COST_FRAME_FAE_COST,
            cost.get("energy_import_cost",
                cost.get("energy_active_import_register_cost", 0) or 0),
        ),
        # Wartość sprzedaży - PLN
        COST_FRAME_RAE_YIELD: frame.get(
            COST_FRAME_RAE_YIELD,
            cost.get("energy_sold_value",
                cost.get("energy_active_export_register_value", 0) or 0),
        ),
        # Bilans finansowy - PLN
        COST_FRAME_ENERGY_BALANCE_VALUE: frame.get(
            COST_FRAME_ENERGY_BALANCE_VALUE,
            cost.get("energy_balance_value", 0) or 0,
        ),
    }


def _normalize_pricing_frame(frame: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizuje ramkę cenową z unified-metrics.

    Nowe API zwraca ceny w frame.metrics.pricing.
    Stare API zwracało price_gross bezpośrednio w ramce.
    """
    metrics = frame.get("metrics", {})
    pricing = metrics.get("pricing", {})

    return {
        "start": frame.get("start"),
        "end": frame.get("end"),
        # Cena zakupu brutto
        "price_gross": frame.get(
            "price_gross",
            pricing.get("price_gross"),
        ),
        # Cena zakupu netto
        "price_net": frame.get(
            "price_net",
            pricing.get("price_net"),
        ),
        # Cena sprzedaży prosumenta brutto
        "price_prosumer_gross": frame.get(
            "price_prosumer_gross",
            pricing.get("price_prosumer_gross"),
        ),
        # Cena sprzedaży prosumenta netto
        "price_prosumer_net": frame.get(
            "price_prosumer_net",
            pricing.get("price_prosumer_net"),
        ),
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Konfiguruje sensory Pstryk AIO."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR_KEY_MAIN
    ]

    entities = [
        PstrykUniversalSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            sensor_key=sensor_key,
            name_suffix=name_suffix,
            device_class=device_class,
            state_class=state_class,
            unit_of_measurement=unit,
            icon=icon,
            config_entry_title=entry.title,
        )
        for sensor_key, (
            name_suffix, device_class, state_class, unit, icon
        ) in SENSOR_DESCRIPTIONS_MAP.items()
    ]

    async_add_entities(entities)
    _LOGGER.info(
        "Utworzono %d encji sensorów Pstryk AIO dla '%s'.",
        len(entities), entry.title,
    )


class PstrykUniversalSensor(CoordinatorEntity, SensorEntity):
    """Uniwersalna klasa sensora Pstryk AIO."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry_id: str,
        sensor_key: str,
        name_suffix: str,
        device_class: Optional[SensorDeviceClass],
        state_class: Optional[SensorStateClass],
        unit_of_measurement: Optional[str],
        icon: Optional[str],
        config_entry_title: str,
    ):
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._attr_unique_id = sensor_key
        self._attr_name = f"{DEFAULT_NAME} {name_suffix}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_icon = icon
        self._attr_extra_state_attributes = {}
        self._update_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Odświeżaj sensory aktualnej ceny co godzinę o pełnej godzinie
        if self._sensor_key in (SENSOR_TODAY_PURCHASE_PRICE, SENSOR_TODAY_SALE_PRICE):
            self.async_on_remove(
                async_track_time_change(
                    self.hass,
                    self._hourly_refresh_state,
                    hour=range(24), minute=0, second=0,
                )
            )

    async def _hourly_refresh_state(self, now: datetime) -> None:
        """Odświeża stan sensora o pełnej godzinie bez wywołania API."""
        if self.coordinator.last_update_success and self.coordinator.data:
            self._update_state()
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        if self._sensor_key in (SENSOR_TOMORROW_PURCHASE_PRICE, SENSOR_TOMORROW_SALE_PRICE):
            return self.coordinator.last_update_success
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_state()
        self.async_write_ha_state()

    # -------------------------------------------------------------------------
    # Pomocnicze metody parsowania
    # -------------------------------------------------------------------------

    def _get_normalized_pricing_frames(
        self, pricing_data: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Zwraca znormalizowane ramki cenowe."""
        if not pricing_data or not isinstance(pricing_data.get("frames"), list):
            return []
        return [_normalize_pricing_frame(f) for f in pricing_data["frames"]]

    def _get_normalized_meter_frames(
        self, meter_data: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Zwraca znormalizowane ramki danych licznika."""
        if not meter_data or not isinstance(meter_data.get("frames"), list):
            return []
        return [_normalize_meter_frame(f) for f in meter_data["frames"]]

    def _get_current_price_frame(
        self,
        pricing_data: Optional[Dict[str, Any]],
        price_key: str = "price_gross",
    ) -> Optional[Dict[str, Any]]:
        """Znajduje aktualną ramkę cenową na podstawie czasu UTC."""
        frames = self._get_normalized_pricing_frames(pricing_data)
        if not frames:
            return None

        now_utc = dt_util.utcnow()
        for frame in frames:
            try:
                start = dt_util.parse_datetime(frame.get("start", ""))
                end = dt_util.parse_datetime(frame.get("end", ""))
                if start and end and start <= now_utc < end:
                    return frame
            except (TypeError, ValueError):
                continue
        return None

    def _format_price_frames_for_attributes(
        self,
        pricing_data: Optional[Dict[str, Any]],
        price_key: str,
        cheap_threshold: Optional[float],
        expensive_threshold: Optional[float],
    ) -> List[Dict[str, Any]]:
        """Formatuje ramki cenowe do atrybutów sensora z konwersją czasu na lokalny."""
        frames = self._get_normalized_pricing_frames(pricing_data)
        result = []
        for frame in frames:
            try:
                start_local = None
                end_local = None

                start_utc = dt_util.parse_datetime(frame.get("start", ""))
                if start_utc:
                    start_local = dt_util.as_local(start_utc).isoformat(timespec="seconds")

                end_utc = dt_util.parse_datetime(frame.get("end", ""))
                if end_utc:
                    end_local = dt_util.as_local(end_utc).isoformat(timespec="seconds")

                price_value = frame.get(price_key)
                is_cheap = (
                    cheap_threshold is not None
                    and price_value is not None
                    and price_value <= cheap_threshold
                )
                is_expensive = (
                    expensive_threshold is not None
                    and price_value is not None
                    and price_value >= expensive_threshold
                )

                entry = {
                    "start": start_local,
                    "end": end_local,
                    "price": price_value,
                    ATTR_PRICE_IS_CHEAP: is_cheap,
                    ATTR_PRICE_IS_EXPENSIVE: is_expensive,
                }
                result.append({k: v for k, v in entry.items() if v is not None})
            except Exception as err:
                _LOGGER.warning("Błąd formatowania ramki cenowej: %s", err)
        return result

    def _calculate_average_price(
        self,
        pricing_data: Optional[Dict[str, Any]],
        price_key: str,
    ) -> Optional[float]:
        """Oblicza średnią cenę z ramek."""
        frames = self._get_normalized_pricing_frames(pricing_data)
        values = [f.get(price_key) for f in frames if f.get(price_key) is not None]
        return round(sum(values) / len(values), 4) if values else None

    def _has_meaningful_price_data(
        self,
        pricing_data: Optional[Dict[str, Any]],
        price_key: str,
    ) -> bool:
        """Sprawdza czy dane cenowe zawierają rzeczywiste wartości (nie zera/None)."""
        frames = self._get_normalized_pricing_frames(pricing_data)
        return any(
            f.get(price_key) is not None and f.get(price_key) != 0.0
            for f in frames
        )

    def _aggregate_hourly_for_day(
        self,
        meter_data: Optional[Dict[str, Any]],
        data_key: str,
        target_day: datetime,
    ) -> tuple:
        """Agreguje dane godzinowe dla danego dnia. Zwraca (suma, lista_godzin)."""
        frames = self._get_normalized_meter_frames(meter_data)
        daily_sum = 0.0
        breakdown = []
        found = False

        for frame in frames:
            try:
                start_utc = dt_util.parse_datetime(frame.get("start", ""))
                if not start_utc:
                    continue
                start_local = dt_util.as_local(start_utc)

                if (
                    start_local.year == target_day.year
                    and start_local.month == target_day.month
                    and start_local.day == target_day.day
                ):
                    value = frame.get(data_key)
                    if value is None:
                        continue
                    found = True
                    daily_sum += float(value)

                    end_local = None
                    end_utc = dt_util.parse_datetime(frame.get("end", ""))
                    if end_utc:
                        end_local = dt_util.as_local(end_utc).isoformat(timespec="seconds")

                    breakdown.append({
                        "start": start_local.isoformat(timespec="seconds"),
                        "end": end_local,
                        "value": round(float(value), 3),
                    })
            except (ValueError, TypeError) as err:
                _LOGGER.warning("Błąd agregacji godzinowej: %s", err)

        breakdown.sort(key=lambda x: x["start"])
        return (round(daily_sum, 3) if found else None), breakdown

    def _aggregate_daily_for_month(
        self,
        meter_data: Optional[Dict[str, Any]],
        data_key: str,
        target_month: datetime,
    ) -> tuple:
        """Agreguje dane dzienne dla danego miesiąca. Zwraca (suma, lista_dni)."""
        frames = self._get_normalized_meter_frames(meter_data)
        monthly_sum = 0.0
        breakdown: Dict[str, float] = {}

        for frame in frames:
            try:
                start_utc = dt_util.parse_datetime(frame.get("start", ""))
                if not start_utc:
                    continue
                start_local = dt_util.as_local(start_utc)

                if (
                    start_local.year == target_month.year
                    and start_local.month == target_month.month
                ):
                    value = frame.get(data_key)
                    if value is None:
                        continue
                    day_str = start_local.strftime("%Y-%m-%d")
                    monthly_sum += float(value)
                    breakdown[day_str] = breakdown.get(day_str, 0.0) + float(value)
            except (ValueError, TypeError) as err:
                _LOGGER.warning("Błąd agregacji dziennej: %s", err)

        formatted = [
            {"date": d, "value": round(v, 3)}
            for d, v in sorted(breakdown.items())
        ]
        return (round(monthly_sum, 3) if breakdown else None), formatted

    # -------------------------------------------------------------------------
    # Główna logika aktualizacji stanu
    # -------------------------------------------------------------------------

    def _update_state(self) -> None:
        """Aktualizuje stan sensora na podstawie danych z koordynatora."""
        data = self.coordinator.data
        if data is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {ATTR_DATA_TIMESTAMP: None}
            return

        meter_data = data.get(KEY_METER_DATA_USAGE)  # unified-metrics: usage+cost razem
        pricing_today = data.get(KEY_PRICING_DATA_PURCHASE_TODAY)
        pricing_tomorrow = data.get(KEY_PRICING_DATA_PURCHASE_TOMORROW)
        last_update = data.get(KEY_LAST_UPDATE)

        options = self.coordinator.config_entry.options
        cheap_buy = options.get(CONF_CHEAP_PURCHASE_PRICE_THRESHOLD, DEFAULT_CHEAP_PURCHASE_PRICE_THRESHOLD)
        expensive_buy = options.get(CONF_EXPENSIVE_PURCHASE_PRICE_THRESHOLD, DEFAULT_EXPENSIVE_PURCHASE_PRICE_THRESHOLD)
        cheap_sell = options.get(CONF_CHEAP_SALE_PRICE_THRESHOLD, DEFAULT_CHEAP_SALE_PRICE_THRESHOLD)
        expensive_sell = options.get(CONF_EXPENSIVE_SALE_PRICE_THRESHOLD, DEFAULT_EXPENSIVE_SALE_PRICE_THRESHOLD)

        now_local = dt_util.now()
        current_month = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_month = (current_month - timedelta(days=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        new_value: Any = None
        attributes: Dict[str, Any] = {ATTR_DATA_TIMESTAMP: last_update}

        try:
            # --- Ceny zakupu dziś ---
            if self._sensor_key == SENSOR_TODAY_PURCHASE_PRICE:
                frame = self._get_current_price_frame(pricing_today, "price_gross")
                if frame:
                    new_value = frame.get("price_gross") or frame.get("price_net")
                attributes[ATTR_PRICE_TODAY] = self._format_price_frames_for_attributes(
                    pricing_today, "price_gross", cheap_buy, expensive_buy
                )
                avg = self._calculate_average_price(pricing_today, "price_gross")
                if avg is not None:
                    attributes[f"{ATTR_AVERAGE_PRICE}_today"] = avg

            # --- Ceny zakupu jutro ---
            elif self._sensor_key == SENSOR_TOMORROW_PURCHASE_PRICE:
                if self._has_meaningful_price_data(pricing_tomorrow, "price_gross"):
                    new_value = self._calculate_average_price(pricing_tomorrow, "price_gross")
                    attributes[ATTR_PRICE_TOMORROW] = self._format_price_frames_for_attributes(
                        pricing_tomorrow, "price_gross", cheap_buy, expensive_buy
                    )
                    avg = self._calculate_average_price(pricing_tomorrow, "price_gross")
                    if avg is not None:
                        attributes[f"{ATTR_AVERAGE_PRICE}_tomorrow"] = avg
                else:
                    attributes[ATTR_DATA_STATUS_MESSAGE] = "Dane dostępne zwykle po 16:00"

            # --- Ceny sprzedaży dziś ---
            elif self._sensor_key == SENSOR_TODAY_SALE_PRICE:
                frame = self._get_current_price_frame(pricing_today, "price_prosumer_gross")
                if frame:
                    new_value = frame.get("price_prosumer_gross") or frame.get("price_prosumer_net")
                attributes[ATTR_PRICE_TODAY] = self._format_price_frames_for_attributes(
                    pricing_today, "price_prosumer_gross", cheap_sell, expensive_sell
                )
                avg = self._calculate_average_price(pricing_today, "price_prosumer_gross")
                if avg is not None:
                    attributes[f"{ATTR_AVERAGE_PRICE}_today"] = avg

            # --- Ceny sprzedaży jutro ---
            elif self._sensor_key == SENSOR_TOMORROW_SALE_PRICE:
                if self._has_meaningful_price_data(pricing_tomorrow, "price_prosumer_gross"):
                    new_value = self._calculate_average_price(
                        pricing_tomorrow, "price_prosumer_gross"
                    )
                    attributes[ATTR_PRICE_TOMORROW] = self._format_price_frames_for_attributes(
                        pricing_tomorrow, "price_prosumer_gross", cheap_sell, expensive_sell
                    )
                    avg = self._calculate_average_price(pricing_tomorrow, "price_prosumer_gross")
                    if avg is not None:
                        attributes[f"{ATTR_AVERAGE_PRICE}_tomorrow"] = avg
                else:
                    attributes[ATTR_DATA_STATUS_MESSAGE] = "Dane dostępne zwykle po 16:00"

            # --- Dzienny koszt zużycia (PLN) ---
            elif self._sensor_key == SENSOR_CONSUMPTION_DAILY_COST:
                total, breakdown = self._aggregate_hourly_for_day(
                    meter_data, COST_FRAME_FAE_COST, now_local
                )
                new_value = round(total, 2) if total is not None else 0.0
                if breakdown:
                    attributes[ATTR_HOURLY_BREAKDOWN_CURRENT_DAY] = breakdown

            # --- Dzienna wartość produkcji (PLN) ---
            elif self._sensor_key == SENSOR_PRODUCTION_DAILY_YIELD:
                total, breakdown = self._aggregate_hourly_for_day(
                    meter_data, COST_FRAME_RAE_YIELD, now_local
                )
                new_value = round(total, 2) if total is not None else 0.0
                if breakdown:
                    attributes[ATTR_HOURLY_BREAKDOWN_CURRENT_DAY] = breakdown

            # --- Dzienne zużycie (kWh) ---
            elif self._sensor_key == SENSOR_CONSUMPTION_DAILY_KWH:
                total, breakdown = self._aggregate_hourly_for_day(
                    meter_data, USAGE_FRAME_FAE_KWH, now_local
                )
                new_value = round(total, 3) if total is not None else 0.0
                if breakdown:
                    attributes[ATTR_HOURLY_BREAKDOWN_CURRENT_DAY] = breakdown

            # --- Dzienna produkcja (kWh) ---
            elif self._sensor_key == SENSOR_PRODUCTION_DAILY_KWH:
                total, breakdown = self._aggregate_hourly_for_day(
                    meter_data, USAGE_FRAME_RAE_KWH, now_local
                )
                new_value = round(total, 3) if total is not None else 0.0
                if breakdown:
                    attributes[ATTR_HOURLY_BREAKDOWN_CURRENT_DAY] = breakdown

            # --- Miesięczne saldo finansowe (PLN) ---
            elif self._sensor_key == SENSOR_BILLING_BALANCE_MONTHLY_PLN:
                total, breakdown = self._aggregate_daily_for_month(
                    meter_data, COST_FRAME_ENERGY_BALANCE_VALUE, current_month
                )
                new_value = total
                if breakdown:
                    attributes[ATTR_DAILY_BREAKDOWN_CURRENT_MONTH] = breakdown

            # --- Miesięczne saldo energetyczne (kWh) ---
            elif self._sensor_key == SENSOR_ENERGY_BALANCE_MONTHLY_KWH:
                total, breakdown = self._aggregate_daily_for_month(
                    meter_data, USAGE_ENERGY_BALANCE, current_month
                )
                new_value = total
                if breakdown:
                    attributes[ATTR_DAILY_BREAKDOWN_CURRENT_MONTH] = breakdown

            # --- Dzienne saldo finansowe (PLN) ---
            elif self._sensor_key == SENSOR_BILLING_BALANCE_DAILY_PLN:
                total, breakdown = self._aggregate_hourly_for_day(
                    meter_data, COST_FRAME_ENERGY_BALANCE_VALUE, now_local
                )
                new_value = total
                if breakdown:
                    attributes[ATTR_HOURLY_BREAKDOWN_CURRENT_DAY] = breakdown

            # --- Dzienne saldo energetyczne (kWh) ---
            elif self._sensor_key == SENSOR_ENERGY_BALANCE_DAILY_KWH:
                total, breakdown = self._aggregate_hourly_for_day(
                    meter_data, USAGE_ENERGY_BALANCE, now_local
                )
                new_value = total
                if breakdown:
                    attributes[ATTR_HOURLY_BREAKDOWN_CURRENT_DAY] = breakdown

            # --- Miesięczne zużycie (kWh) ---
            elif self._sensor_key == SENSOR_CONSUMPTION_MONTHLY_KWH:
                total, breakdown = self._aggregate_daily_for_month(
                    meter_data, USAGE_FRAME_FAE_KWH, current_month
                )
                new_value = total
                if breakdown:
                    attributes[ATTR_DAILY_BREAKDOWN_CURRENT_MONTH] = breakdown

            # --- Miesięczna produkcja (kWh) ---
            elif self._sensor_key == SENSOR_PRODUCTION_MONTHLY_KWH:
                total, breakdown = self._aggregate_daily_for_month(
                    meter_data, USAGE_FRAME_RAE_KWH, current_month
                )
                new_value = total
                if breakdown:
                    attributes[ATTR_DAILY_BREAKDOWN_CURRENT_MONTH] = breakdown
                last_month_total, _ = self._aggregate_daily_for_month(
                    meter_data, USAGE_FRAME_RAE_KWH, previous_month
                )
                if last_month_total is not None:
                    attributes[ATTR_LAST_MONTH_VALUE] = last_month_total

            # --- Miesięczny koszt zużycia (PLN) ---
            elif self._sensor_key == SENSOR_CONSUMPTION_MONTHLY_COST_PLN:
                total, breakdown = self._aggregate_daily_for_month(
                    meter_data, COST_FRAME_FAE_COST, current_month
                )
                new_value = total
                if breakdown:
                    attributes[ATTR_DAILY_BREAKDOWN_CURRENT_MONTH] = breakdown

            # --- Miesięczna wartość produkcji (PLN) ---
            elif self._sensor_key == SENSOR_PRODUCTION_MONTHLY_YIELD_PLN:
                total, breakdown = self._aggregate_daily_for_month(
                    meter_data, COST_FRAME_RAE_YIELD, current_month
                )
                new_value = total
                if breakdown:
                    attributes[ATTR_DAILY_BREAKDOWN_CURRENT_MONTH] = breakdown
                last_month_total, _ = self._aggregate_daily_for_month(
                    meter_data, COST_FRAME_RAE_YIELD, previous_month
                )
                if last_month_total is not None:
                    attributes[ATTR_LAST_MONTH_VALUE] = last_month_total

            self._attr_native_value = new_value
            self._attr_extra_state_attributes = {
                k: v for k, v in attributes.items()
                if v is not None and (not isinstance(v, list) or v)
            }

        except Exception as err:
            _LOGGER.error(
                "Błąd aktualizacji stanu sensora %s (%s): %s",
                self.name, self._sensor_key, err, exc_info=True,
            )
            self._attr_native_value = None
            self._attr_extra_state_attributes = {
                ATTR_DATA_TIMESTAMP: last_update,
                ATTR_DATA_STATUS_MESSAGE: f"Błąd: {err}",
            }

        _LOGGER.debug(
            "Sensor %s: wartość=%s, atrybuty=%d",
            self.name, self._attr_native_value,
            len(self._attr_extra_state_attributes),
        )
