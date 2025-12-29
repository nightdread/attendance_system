"""
Валидация входных данных для системы учета рабочего времени
"""
import re
from typing import Optional, Tuple


class ValidationError(Exception):
    """Исключение для ошибок валидации"""
    pass


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Валидация имени пользователя
    
    Правила:
    - Длина от 3 до 50 символов
    - Только буквы (латиница, кириллица), цифры, подчеркивания и дефисы
    - Не может начинаться с цифры или дефиса
    
    Returns:
        (is_valid, error_message)
    """
    if not username:
        return False, "Имя пользователя не может быть пустым"
    
    username = username.strip()
    
    if len(username) < 3:
        return False, "Имя пользователя должно содержать минимум 3 символа"
    
    if len(username) > 50:
        return False, "Имя пользователя не может быть длиннее 50 символов"
    
    # Разрешаем буквы (латиница, кириллица), цифры, подчеркивания, дефисы
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ_][a-zA-Zа-яА-ЯёЁ0-9_-]*$', username):
        return False, "Имя пользователя может содержать только буквы, цифры, подчеркивания и дефисы, и должно начинаться с буквы или подчеркивания"
    
    return True, None


def validate_password(password: str, min_length: int = 8, require_complexity: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Валидация пароля
    
    Правила:
    - Минимальная длина (по умолчанию 8 символов)
    - Максимальная длина 128 символов
    - При require_complexity=True: должен содержать буквы и цифры
    
    Args:
        password: Пароль для проверки
        min_length: Минимальная длина пароля
        require_complexity: Требовать ли сложность (буквы + цифры)
    
    Returns:
        (is_valid, error_message)
    """
    if not password:
        return False, "Пароль не может быть пустым"
    
    if len(password) < min_length:
        return False, f"Пароль должен содержать минимум {min_length} символов"
    
    if len(password) > 128:
        return False, "Пароль не может быть длиннее 128 символов"
    
    if require_complexity:
        has_letters = bool(re.search(r'[a-zA-Zа-яА-ЯёЁ]', password))
        has_digits = bool(re.search(r'\d', password))
        
        if not has_letters:
            return False, "Пароль должен содержать хотя бы одну букву"
        
        if not has_digits:
            return False, "Пароль должен содержать хотя бы одну цифру"
    
    return True, None


def validate_fio(fio: str, min_length: int = 3, max_length: int = 200) -> Tuple[bool, Optional[str]]:
    """
    Валидация ФИО
    
    Правила:
    - Минимальная длина (по умолчанию 3 символа)
    - Максимальная длина (по умолчанию 200 символов)
    - Должно содержать только буквы, пробелы, дефисы и апострофы
    
    Args:
        fio: ФИО для проверки
        min_length: Минимальная длина
        max_length: Максимальная длина
    
    Returns:
        (is_valid, error_message)
    """
    if not fio:
        return False, "ФИО не может быть пустым"
    
    fio = fio.strip()
    
    if len(fio) < min_length:
        return False, f"ФИО должно содержать минимум {min_length} символа"
    
    if len(fio) > max_length:
        return False, f"ФИО не может быть длиннее {max_length} символов"
    
    # Разрешаем буквы (латиница, кириллица), пробелы, дефисы, апострофы
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s\'-]+$', fio):
        return False, "ФИО может содержать только буквы, пробелы, дефисы и апострофы"
    
    # Проверяем, что есть хотя бы одна буква
    if not re.search(r'[a-zA-Zа-яА-ЯёЁ]', fio):
        return False, "ФИО должно содержать хотя бы одну букву"
    
    return True, None


def validate_token(token: str, min_length: int = 8, max_length: int = 64) -> Tuple[bool, Optional[str]]:
    """
    Валидация токена
    
    Правила:
    - Длина от min_length до max_length символов
    - Только буквы, цифры, дефисы и подчеркивания
    
    Args:
        token: Токен для проверки
        min_length: Минимальная длина
        max_length: Максимальная длина
    
    Returns:
        (is_valid, error_message)
    """
    if not token:
        return False, "Токен не может быть пустым"
    
    token = token.strip()
    
    if len(token) < min_length:
        return False, f"Токен должен содержать минимум {min_length} символов"
    
    if len(token) > max_length:
        return False, f"Токен не может быть длиннее {max_length} символов"
    
    # Разрешаем только буквы, цифры, дефисы и подчеркивания
    if not re.match(r'^[a-zA-Z0-9_-]+$', token):
        return False, "Токен может содержать только буквы, цифры, дефисы и подчеркивания"
    
    return True, None


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Валидация email адреса
    
    Returns:
        (is_valid, error_message)
    """
    if not email:
        return False, "Email не может быть пустым"
    
    email = email.strip().lower()
    
    # Базовый паттерн для email
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return False, "Некорректный формат email адреса"
    
    if len(email) > 254:  # RFC 5321
        return False, "Email адрес слишком длинный"
    
    return True, None


def validate_department(department: str, max_length: int = 100) -> Tuple[bool, Optional[str]]:
    """
    Валидация названия отдела
    
    Returns:
        (is_valid, error_message)
    """
    if not department:
        return True, None  # Отдел может быть пустым
    
    department = department.strip()
    
    if len(department) > max_length:
        return False, f"Название отдела не может быть длиннее {max_length} символов"
    
    return True, None


def validate_position(position: str, max_length: int = 100) -> Tuple[bool, Optional[str]]:
    """
    Валидация должности
    
    Returns:
        (is_valid, error_message)
    """
    if not position:
        return True, None  # Должность может быть пустой
    
    position = position.strip()
    
    if len(position) > max_length:
        return False, f"Название должности не может быть длиннее {max_length} символов"
    
    return True, None


def validate_role(role: str, allowed_roles: list[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Валидация роли пользователя
    
    Args:
        role: Роль для проверки
        allowed_roles: Список разрешенных ролей. Если None, используется стандартный набор
    
    Returns:
        (is_valid, error_message)
    """
    if not role:
        return False, "Роль не может быть пустой"
    
    if allowed_roles is None:
        allowed_roles = ["user", "admin", "manager", "hr", "terminal"]
    
    if role not in allowed_roles:
        return False, f"Недопустимая роль. Разрешенные роли: {', '.join(allowed_roles)}"
    
    return True, None


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Очистка строки от потенциально опасных символов
    
    Args:
        value: Строка для очистки
        max_length: Максимальная длина (обрезает если превышена)
    
    Returns:
        Очищенная строка
    """
    if not value:
        return ""
    
    # Удаляем управляющие символы (кроме пробелов, табуляции, переноса строки)
    sanitized = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', value)
    
    # Обрезаем до максимальной длины
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized.strip()

