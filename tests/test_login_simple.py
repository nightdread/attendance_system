#!/usr/bin/env python3
"""
Простой тест логина с правильным экранированием
"""
import requests
from urllib.parse import urljoin

BASE_URL = "https://attendance.141922.ru"
USERNAME = "admin"
PASSWORD = "PYC$$pehxZ2OG&6Hb"

session = requests.Session()
session.verify = False

# Отключаем предупреждения SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("1. Получение страницы логина...")
response = session.get(urljoin(BASE_URL, "/login"))
print(f"   Статус: {response.status_code}")

# Извлекаем CSRF токен
import re
csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)
if csrf_match:
    csrf_token = csrf_match.group(1)
    print(f"   CSRF токен: {csrf_token[:30]}...")
else:
    print("   ⚠ CSRF токен не найден")
    csrf_token = None

print("\n2. Сброс сессии через /logout...")
response = session.get(urljoin(BASE_URL, "/logout"), allow_redirects=True)
print(f"   Статус: {response.status_code}, URL: {response.url}")

print("\n3. Повторное получение CSRF токена...")
response = session.get(urljoin(BASE_URL, "/login"))
csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)
if csrf_match:
    csrf_token = csrf_match.group(1)
    print(f"   Новый CSRF токен: {csrf_token[:30]}...")
else:
    print("   ⚠ CSRF токен не найден")
    csrf_token = None

print("\n4. Попытка логина...")
login_data = {
    "username": USERNAME,
    "password": PASSWORD,
    "next_url": "/admin"
}
if csrf_token:
    login_data["csrf_token"] = csrf_token

response = session.post(
    urljoin(BASE_URL, "/login"),
    data=login_data,
    allow_redirects=False,
    headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": urljoin(BASE_URL, "/login")
    }
)

print(f"   Статус: {response.status_code}")
print(f"   Заголовки Location: {response.headers.get('Location', 'N/A')}")

if response.status_code == 302:
    print("   ✓ Успешный редирект - логин прошел!")
    redirect_url = response.headers.get('Location', '')
    print(f"   Редирект на: {redirect_url}")
    
    # Проверяем токен через API
    print("\n5. Проверка токена через API...")
    api_response = session.get(urljoin(BASE_URL, "/api/active_token"), allow_redirects=False)
    print(f"   API статус: {api_response.status_code}")
    if api_response.status_code == 200:
        data = api_response.json()
        print(f"   ✓ Токен получен успешно!")
        print(f"   Токен для отметки: {data.get('token', 'N/A')[:20]}...")
        success = True
    else:
        print(f"   ✗ API ошибка: {api_response.text[:200]}")
        success = False
else:
    print("   ✗ Логин не прошел")
    if "Invalid credentials" in response.text:
        print("   Ошибка: Invalid credentials")
    elif "error" in response.text.lower():
        error_match = re.search(r'<div[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</div>', response.text, re.IGNORECASE)
        if error_match:
            print(f"   Ошибка: {error_match.group(1).strip()}")
    print(f"   Ответ (первые 500 символов): {response.text[:500]}")
    success = False

print(f"\n{'='*60}")
print(f"Результат: {'✓ УСПЕШНО' if success else '✗ ОШИБКА'}")
print(f"{'='*60}")
