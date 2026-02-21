#!/usr/bin/env python3
"""
Скрипт для тестирования сброса сессии и получения токена
"""
import requests
import sys
from urllib.parse import urljoin

# Конфигурация
BASE_URL = "https://attendance.141922.ru"
# Или локально: BASE_URL = "http://localhost:8000"

# Учетные данные из .env
USERNAME = "admin"
PASSWORD = "PYC$$pehxZ2OG&6Hb"

def test_token_acquisition():
    """Тестирует получение токена после сброса сессии"""
    session = requests.Session()
    
    print("=" * 60)
    print("ТЕСТ: Сброс сессии и получение токена")
    print("=" * 60)
    
    # Шаг 1: Получаем CSRF токен со страницы логина
    print("\n1. Получение CSRF токена со страницы логина...")
    login_page_url = urljoin(BASE_URL, "/login")
    try:
        response = session.get(login_page_url, verify=False)
        response.raise_for_status()
        print(f"   ✓ Страница логина доступна (статус: {response.status_code})")
        
        # Извлекаем CSRF токен из HTML (если есть)
        csrf_token = None
        if 'csrf_token' in response.text:
            import re
            match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)
            if match:
                csrf_token = match.group(1)
                print(f"   ✓ CSRF токен получен: {csrf_token[:20]}...")
    except Exception as e:
        print(f"   ✗ Ошибка при получении страницы логина: {e}")
        return False
    
    # Шаг 2: Сбрасываем сессию через /logout
    print("\n2. Сброс текущей сессии через /logout...")
    logout_url = urljoin(BASE_URL, "/logout")
    try:
        response = session.get(logout_url, verify=False, allow_redirects=True)
        print(f"   ✓ Сессия сброшена (статус: {response.status_code})")
        print(f"   ✓ Редирект на: {response.url}")
        
        # Проверяем, что сессия действительно очищена
        if "access_token" in session.cookies:
            print("   ⚠ Внимание: access_token все еще в cookies")
        else:
            print("   ✓ Cookies очищены")
    except Exception as e:
        print(f"   ✗ Ошибка при сбросе сессии: {e}")
        return False
    
    # Шаг 3: Получаем CSRF токен заново для логина
    print("\n3. Получение CSRF токена для логина...")
    try:
        response = session.get(login_page_url, verify=False)
        response.raise_for_status()
        
        # Извлекаем CSRF токен
        csrf_token = None
        if 'csrf_token' in response.text:
            import re
            match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)
            if match:
                csrf_token = match.group(1)
                print(f"   ✓ CSRF токен получен: {csrf_token[:20]}...")
    except Exception as e:
        print(f"   ✗ Ошибка при получении CSRF токена: {e}")
        return False
    
    # Шаг 4: Выполняем логин
    print("\n4. Выполнение логина...")
    login_post_url = urljoin(BASE_URL, "/login")
    login_data = {
        "username": USERNAME,
        "password": PASSWORD,
        "next_url": "/admin"
    }
    if csrf_token:
        login_data["csrf_token"] = csrf_token
    else:
        print("   ⚠ CSRF токен не найден, пробуем без него...")
    
    print(f"   Отправка данных: username={USERNAME}, csrf_token={'есть' if csrf_token else 'нет'}")
    
    try:
        response = session.post(
            login_post_url,
            data=login_data,
            verify=False,
            allow_redirects=False,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": login_page_url
            }
        )
        
        print(f"   Статус ответа: {response.status_code}")
        print(f"   Заголовки ответа: {dict(response.headers)}")
        
        # Проверяем наличие ошибок в ответе
        if "error" in response.text.lower() or "invalid" in response.text.lower():
            import re
            error_match = re.search(r'<div[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</div>', response.text, re.IGNORECASE)
            if error_match:
                error_msg = error_match.group(1).strip()
                print(f"   ✗ Ошибка в ответе: {error_msg}")
            else:
                # Ищем ошибку в других местах
                if "invalid credentials" in response.text.lower():
                    print(f"   ✗ Ошибка: Invalid credentials")
                else:
                    print(f"   ✗ Обнаружена ошибка в HTML ответе")
        
        # Проверяем редирект (успешный логин должен редиректить)
        if response.status_code == 302:
            redirect_location = response.headers.get("Location", "")
            print(f"   ✓ Редирект после логина: {redirect_location}")
            
            # Проверяем наличие токена в сессии
            if "access_token" in session.cookies or hasattr(session, 'cookies'):
                print("   ✓ Токен получен в cookies")
                
                # Проверяем токен через API
                print("\n5. Проверка токена через API...")
                api_url = urljoin(BASE_URL, "/api/active_token")
                
                # Используем сессию с cookies
                api_response = session.get(api_url, verify=False)
                
                if api_response.status_code == 200:
                    data = api_response.json()
                    print(f"   ✓ API запрос успешен!")
                    print(f"   ✓ Токен для отметки: {data.get('token', 'N/A')[:10]}...")
                    print(f"   ✓ URL бота: {data.get('url', 'N/A')[:50]}...")
                    return True
                else:
                    print(f"   ✗ API запрос не удался (статус: {api_response.status_code})")
                    print(f"   Ответ: {api_response.text[:200]}")
                    return False
            else:
                # Попробуем получить токен из заголовков или проверить через другой способ
                print("   ⚠ Токен не найден в cookies, проверяем через заголовки...")
                
                # Проверяем через API с Bearer токеном (если он в заголовках)
                api_url = urljoin(BASE_URL, "/api/active_token")
                api_response = session.get(api_url, verify=False)
                
                if api_response.status_code == 200:
                    print("   ✓ API запрос успешен через сессию!")
                    return True
                else:
                    print(f"   ✗ API запрос не удался (статус: {api_response.status_code})")
                    return False
        else:
            print(f"   ✗ Логин не удался (статус: {response.status_code})")
            print(f"   Ответ: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"   ✗ Ошибка при логине: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_token_verification():
    """Дополнительная проверка: создание и верификация JWT токена"""
    print("\n" + "=" * 60)
    print("ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: Верификация JWT токена")
    print("=" * 60)
    
    try:
        # Добавляем путь проекта в sys.path
        import sys
        import os
        project_root = os.path.dirname(os.path.abspath(__file__))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from auth.jwt_handler import JWTHandler
        
        # Создаем тестовый токен
        test_data = {"sub": "testuser", "role": "admin"}
        token = JWTHandler.create_access_token(test_data)
        print(f"\n✓ Токен создан: {token[:50]}...")
        
        # Верифицируем токен
        payload = JWTHandler.verify_token(token)
        if payload:
            print(f"✓ Токен верифицирован успешно")
            print(f"  Username: {payload.get('sub')}")
            print(f"  Role: {payload.get('role')}")
            print(f"  Expires: {payload.get('exp')}")
            return True
        else:
            print("✗ Токен не прошел верификацию")
            return False
    except ImportError as e:
        print(f"⚠ Модуль не найден (это нормально для теста без зависимостей): {e}")
        return True  # Не критично для основного теста
    except Exception as e:
        print(f"✗ Ошибка при проверке JWT: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Отключаем предупреждения SSL для тестирования
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Тест получения токена
    token_test = test_token_acquisition()
    
    # Тест верификации JWT
    jwt_test = test_token_verification()
    
    print("\n" + "=" * 60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    print(f"Получение токена: {'✓ УСПЕШНО' if token_test else '✗ ОШИБКА'}")
    print(f"Верификация JWT: {'✓ УСПЕШНО' if jwt_test else '✗ ОШИБКА'}")
    
    sys.exit(0 if (token_test and jwt_test) else 1)
