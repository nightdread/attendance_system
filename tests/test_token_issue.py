#!/usr/bin/env python3
"""
Скрипт для проверки выдачи токена для отметки приходящих сотрудников
"""
import requests
import json
from urllib.parse import urljoin
import urllib3

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://attendance.141922.ru"

def test_token_endpoints():
    """Тестирует различные способы получения токена"""
    print("=" * 70)
    print("ПРОВЕРКА ВЫДАЧИ ТОКЕНА ДЛЯ ОТМЕТКИ СОТРУДНИКОВ")
    print("=" * 70)
    
    results = {}
    
    # Тест 1: /api/token без аутентификации (публичный доступ)
    print("\n1. Тест: /api/token (публичный доступ, без аутентификации)")
    print("-" * 70)
    try:
        response = requests.get(
            urljoin(BASE_URL, "/api/token"),
            verify=False,
            timeout=10
        )
        print(f"   Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Токен получен успешно!")
            print(f"   Токен: {data.get('token', 'N/A')}")
            print(f"   URL: {data.get('url', 'N/A')}")
            print(f"   Bot username: {data.get('bot_username', 'N/A')}")
            print(f"   Created at: {data.get('created_at', 'N/A')}")
            results['public_token'] = True
            results['public_token_data'] = data
        elif response.status_code == 401:
            print(f"   ⚠️  Требуется API ключ (это нормально, если API_KEY настроен)")
            results['public_token'] = False
            results['public_token_reason'] = "Requires API key"
        else:
            print(f"   ❌ Ошибка: {response.status_code}")
            print(f"   Ответ: {response.text[:200]}")
            results['public_token'] = False
            results['public_token_error'] = response.text[:200]
    except Exception as e:
        print(f"   ❌ Исключение: {e}")
        results['public_token'] = False
        results['public_token_error'] = str(e)
    
    # Тест 2: /api/token с API ключом
    print("\n2. Тест: /api/token (с API ключом)")
    print("-" * 70)
    try:
        # Получаем API ключ из .env
        import os
        env_file = os.path.join(os.path.dirname(__file__), '.env')
        api_key = None
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('API_KEY='):
                        api_key = line.split('=', 1)[1].strip()
                        break
        
        if api_key:
            response = requests.get(
                urljoin(BASE_URL, "/api/token"),
                headers={"X-API-Key": api_key},
                verify=False,
                timeout=10
            )
            print(f"   Статус: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Токен получен успешно!")
                print(f"   Токен: {data.get('token', 'N/A')}")
                print(f"   URL: {data.get('url', 'N/A')}")
                print(f"   Bot username: {data.get('bot_username', 'N/A')}")
                results['api_token'] = True
                results['api_token_data'] = data
            else:
                print(f"   ❌ Ошибка: {response.status_code}")
                print(f"   Ответ: {response.text[:200]}")
                results['api_token'] = False
        else:
            print(f"   ⚠️  API ключ не найден в .env файле")
            results['api_token'] = None
    except Exception as e:
        print(f"   ❌ Исключение: {e}")
        results['api_token'] = False
        results['api_token_error'] = str(e)
    
    # Тест 3: /api/active_token с API ключом
    print("\n3. Тест: /api/active_token (с API ключом)")
    print("-" * 70)
    try:
        if api_key:
            response = requests.get(
                urljoin(BASE_URL, "/api/active_token"),
                headers={"X-API-Key": api_key},
                verify=False,
                timeout=10
            )
            print(f"   Статус: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Токен получен успешно!")
                print(f"   Токен: {data.get('token', 'N/A')}")
                print(f"   URL: {data.get('url', 'N/A')}")
                print(f"   Bot URL: {data.get('bot_url', 'N/A')}")
                results['active_token'] = True
                results['active_token_data'] = data
            else:
                print(f"   ❌ Ошибка: {response.status_code}")
                print(f"   Ответ: {response.text[:200]}")
                results['active_token'] = False
        else:
            print(f"   ⚠️  API ключ не найден")
            results['active_token'] = None
    except Exception as e:
        print(f"   ❌ Исключение: {e}")
        results['active_token'] = False
        results['active_token_error'] = str(e)
    
    # Тест 4: Проверка формата токена
    print("\n4. Проверка формата токена")
    print("-" * 70)
    token_data = results.get('public_token_data') or results.get('api_token_data') or results.get('active_token_data')
    if token_data:
        token = token_data.get('token', '')
        url = token_data.get('url', '')
        
        print(f"   Длина токена: {len(token)} символов")
        print(f"   Формат токена: {'✅ Корректный' if len(token) >= 8 else '❌ Слишком короткий'}")
        print(f"   URL содержит токен: {'✅ Да' if token in url else '❌ Нет'}")
        print(f"   URL формат: {'✅ Корректный' if url.startswith('https://t.me/') else '❌ Неверный формат'}")
        
        results['token_format'] = {
            'length': len(token),
            'valid_length': len(token) >= 8,
            'token_in_url': token in url,
            'url_format_valid': url.startswith('https://t.me/')
        }
    else:
        print(f"   ⚠️  Нет данных токена для проверки")
        results['token_format'] = None
    
    # Итоги
    print("\n" + "=" * 70)
    print("ИТОГИ ПРОВЕРКИ")
    print("=" * 70)
    
    if results.get('public_token'):
        print("✅ Публичный доступ к токену: РАБОТАЕТ")
    elif results.get('public_token') is False and results.get('public_token_reason') == "Requires API key":
        print("⚠️  Публичный доступ: Требуется API ключ (это нормально)")
    else:
        print("❌ Публичный доступ к токену: НЕ РАБОТАЕТ")
    
    if results.get('api_token'):
        print("✅ Получение токена через API ключ: РАБОТАЕТ")
    elif results.get('api_token') is None:
        print("⚠️  Получение токена через API ключ: API ключ не настроен")
    else:
        print("❌ Получение токена через API ключ: НЕ РАБОТАЕТ")
    
    if results.get('active_token'):
        print("✅ Эндпоинт /api/active_token: РАБОТАЕТ")
    elif results.get('active_token') is None:
        print("⚠️  Эндпоинт /api/active_token: API ключ не настроен")
    else:
        print("❌ Эндпоинт /api/active_token: НЕ РАБОТАЕТ")
    
    if results.get('token_format'):
        fmt = results['token_format']
        if fmt.get('valid_length') and fmt.get('token_in_url') and fmt.get('url_format_valid'):
            print("✅ Формат токена: КОРРЕКТНЫЙ")
        else:
            print("❌ Формат токена: ЕСТЬ ПРОБЛЕМЫ")
            if not fmt.get('valid_length'):
                print("   - Токен слишком короткий")
            if not fmt.get('token_in_url'):
                print("   - Токен не найден в URL")
            if not fmt.get('url_format_valid'):
                print("   - Неверный формат URL")
    
    print("\n" + "=" * 70)
    
    # Общий результат
    success_count = sum([
        results.get('public_token') or (results.get('public_token') is False and results.get('public_token_reason') == "Requires API key"),
        results.get('api_token') or results.get('active_token'),
        results.get('token_format') and all([
            results['token_format'].get('valid_length'),
            results['token_format'].get('token_in_url'),
            results['token_format'].get('url_format_valid')
        ])
    ])
    
    if success_count >= 2:
        print("✅ ОБЩИЙ РЕЗУЛЬТАТ: Токен выдается корректно")
        return True
    else:
        print("❌ ОБЩИЙ РЕЗУЛЬТАТ: Есть проблемы с выдачей токена")
        return False

if __name__ == "__main__":
    import sys
    success = test_token_endpoints()
    sys.exit(0 if success else 1)
