"""
Модуль для работы с производственным календарем России.
Поддерживает проверку выходных дней, праздников и сокращенных рабочих дней.
"""

import os
import json
import requests
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ProductionCalendar:
    """Класс для работы с производственным календарем"""
    
    def __init__(self, api_url: Optional[str] = None, calendar_file: Optional[str] = None):
        """
        Инициализация календаря
        
        Args:
            api_url: URL API для получения календаря (например, isdayoff.ru)
            calendar_file: Путь к локальному JSON файлу с календарем
        """
        self.api_url = api_url
        self.calendar_file = calendar_file
        self.cache: Dict[str, bool] = {}  # Кэш для проверенных дат
        
        # Загружаем локальный календарь если указан
        self.local_calendar: Dict[str, Dict] = {}
        if calendar_file:
            self._load_local_calendar()
    
    def _load_local_calendar(self):
        """Загрузить локальный календарь из JSON файла"""
        if not self.calendar_file:
            return
        
        calendar_path = Path(self.calendar_file)
        if not calendar_path.exists():
            logger.warning(f"Calendar file not found: {calendar_path}")
            return
        
        try:
            with open(calendar_path, 'r', encoding='utf-8') as f:
                self.local_calendar = json.load(f)
            logger.info(f"Loaded local calendar from {calendar_path}")
        except Exception as e:
            logger.error(f"Error loading calendar file: {e}")
    
    def _check_weekend(self, check_date: date) -> bool:
        """Проверить, является ли дата выходным днем (суббота или воскресенье)"""
        weekday = check_date.weekday()
        return weekday >= 5  # 5 = суббота, 6 = воскресенье
    
    def _check_local_calendar(self, check_date: date) -> Optional[bool]:
        """
        Проверить дату в локальном календаре
        
        Returns:
            True если рабочий день
            False если выходной/праздник
            None если дата не найдена в календаре
        """
        if not self.local_calendar:
            return None
        
        date_str = check_date.strftime("%Y-%m-%d")
        year = str(check_date.year)
        
        # Проверяем год в календаре
        if year not in self.local_calendar:
            return None
        
        year_data = self.local_calendar[year]
        
        # Проверяем конкретную дату
        if date_str in year_data.get("holidays", []):
            return False  # Праздник
        
        if date_str in year_data.get("workdays", []):
            return True  # Рабочий день (перенос)
        
        # Проверяем сокращенные дни
        if date_str in year_data.get("short_days", []):
            return True  # Сокращенный рабочий день (все равно рабочий)
        
        return None
    
    def _check_api(self, check_date: date) -> Optional[bool]:
        """
        Проверить дату через API
        
        Returns:
            True если рабочий день
            False если выходной/праздник
            None если API недоступен
        """
        if not self.api_url:
            return None
        
        date_str = check_date.strftime("%Y%m%d")
        
        try:
            # Формат API isdayoff.ru: https://isdayoff.ru/api/getdata?year=2025&month=1&day=25
            # Или: https://isdayoff.ru/20250125
            if "isdayoff.ru" in self.api_url:
                url = f"https://isdayoff.ru/{date_str}"
            else:
                # Универсальный формат: {api_url}?date=YYYY-MM-DD
                url = f"{self.api_url}?date={check_date.strftime('%Y-%m-%d')}"
            
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            # isdayoff.ru возвращает: 0 = рабочий день, 1 = выходной, 2 = сокращенный
            result = response.text.strip()
            if result == "0":
                return True  # Рабочий день
            elif result == "1":
                return False  # Выходной
            elif result == "2":
                return True  # Сокращенный рабочий день (все равно рабочий)
            else:
                logger.warning(f"Unexpected API response: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error checking API calendar: {e}")
            return None
    
    def is_working_day(self, check_date: date) -> bool:
        """
        Проверить, является ли дата рабочим днем
        
        Args:
            check_date: Дата для проверки
            
        Returns:
            True если рабочий день, False если выходной/праздник
        """
        date_str = check_date.strftime("%Y-%m-%d")
        
        # Проверяем кэш
        if date_str in self.cache:
            return self.cache[date_str]
        
        # Сначала проверяем локальный календарь
        local_result = self._check_local_calendar(check_date)
        if local_result is not None:
            self.cache[date_str] = local_result
            return local_result
        
        # Затем проверяем API
        api_result = self._check_api(check_date)
        if api_result is not None:
            self.cache[date_str] = api_result
            return api_result
        
        # Если ни локальный календарь, ни API не доступны, используем стандартную логику
        # (суббота/воскресенье = выходной)
        is_weekend = self._check_weekend(check_date)
        result = not is_weekend
        self.cache[date_str] = result
        
        logger.warning(
            f"Calendar not available for {date_str}, using default logic "
            f"(weekend check: {is_weekend})"
        )
        
        return result
    
    def is_holiday(self, check_date: date) -> bool:
        """
        Проверить, является ли дата праздником или выходным
        
        Returns:
            True если праздник/выходной, False если рабочий день
        """
        return not self.is_working_day(check_date)
    
    def get_working_days_in_range(self, start_date: date, end_date: date) -> int:
        """
        Подсчитать количество рабочих дней в диапазоне
        
        Args:
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Количество рабочих дней
        """
        count = 0
        current = start_date
        while current <= end_date:
            if self.is_working_day(current):
                count += 1
            current += timedelta(days=1)
        
        return count


# Глобальный экземпляр календаря (инициализируется при первом использовании)
_calendar_instance: Optional[ProductionCalendar] = None


def get_calendar() -> ProductionCalendar:
    """Получить глобальный экземпляр календаря"""
    global _calendar_instance
    
    if _calendar_instance is None:
        from config.config import PRODUCTION_CALENDAR_API_URL, PRODUCTION_CALENDAR_FILE
        
        _calendar_instance = ProductionCalendar(
            api_url=PRODUCTION_CALENDAR_API_URL,
            calendar_file=PRODUCTION_CALENDAR_FILE
        )
    
    return _calendar_instance


def is_working_day(check_date: date) -> bool:
    """Удобная функция для проверки рабочего дня"""
    return get_calendar().is_working_day(check_date)


def is_holiday(check_date: date) -> bool:
    """Удобная функция для проверки праздника/выходного"""
    return get_calendar().is_holiday(check_date)
