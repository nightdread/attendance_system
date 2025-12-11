# Интеграция с микроконтроллером

Этот документ описывает, как подключить микроконтроллер (ESP32, Arduino и т.д.) для отображения QR-кода с токеном системы учета времени.

## API Endpoint

Для получения текущего токена используйте endpoint:

```
GET /api/token
```

### Параметры запроса

- **Заголовки (опционально):**
  - `X-API-Key: ваш_api_key` - если в системе настроен `API_KEY` в переменных окружения

### Ответ

```json
{
  "token": "abc123xyz",
  "url": "https://t.me/your_bot?start=abc123xyz",
  "bot_username": "your_bot",
  "created_at": "2025-12-11T10:30:45.123456"
}
```

Поле `created_at` содержит ISO timestamp создания токена. Используйте его для отслеживания изменений токена.

### Пример запроса

```bash
curl http://your-server:8000/api/token
```

С API key (если настроен):
```bash
curl -H "X-API-Key: your_api_key" http://your-server:8000/api/token
```

## Примеры кода

### ESP32 с дисплеем (TFT/e-Paper)

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <qrcode.h>  // Библиотека: https://github.com/ricmoo/QRCode

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* serverUrl = "http://your-server:8000/api/token";
const char* apiKey = "YOUR_API_KEY";  // Опционально

void setup() {
  Serial.begin(115200);
  
  // Подключение к WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("WiFi connected");
  
  // Инициализация дисплея
  // display.init();
  
  updateQRCode();
}

String lastCreatedAt = "";

void loop() {
  // Проверяем каждую секунду для быстрого обновления после сканирования
  updateQRCode();
  delay(1000);
}

void updateQRCode() {
  HTTPClient http;
  http.begin(serverUrl);
  
  // Добавляем API key если настроен
  if (strlen(apiKey) > 0) {
    http.addHeader("X-API-Key", apiKey);
  }
  
  int httpCode = http.GET();
  
  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    
    // Парсим JSON
    DynamicJsonDocument doc(1024);
    deserializeJson(doc, payload);
    
    String currentCreatedAt = doc["created_at"] | "";
    
    // Обновляем QR только если токен изменился
    if (currentCreatedAt != lastCreatedAt) {
      lastCreatedAt = currentCreatedAt;
      String url = doc["url"];
      
      Serial.println("Token updated: " + url);
      
      // Генерируем QR-код
      QRCode qrcode;
      uint8_t qrcodeData[qrcode_getBufferSize(3)];
      qrcode_initText(&qrcode, qrcodeData, 3, 0, url.c_str());
      
      // Отображаем QR-код на дисплее
      displayQRCode(&qrcode);
    }
    
  } else {
    Serial.printf("HTTP error: %d\n", httpCode);
  }
  
  http.end();
}

void displayQRCode(QRCode *qrcode) {
  // Пример для TFT дисплея
  int size = qrcode->size;
  int scale = min(display.width(), display.height()) / size;
  int offsetX = (display.width() - size * scale) / 2;
  int offsetY = (display.height() - size * scale) / 2;
  
  display.fillScreen(TFT_BLACK);
  
  for (int y = 0; y < size; y++) {
    for (int x = 0; x < size; x++) {
      if (qrcode_getModule(qrcode, x, y)) {
        display.fillRect(offsetX + x * scale, offsetY + y * scale, scale, scale, TFT_WHITE);
      }
    }
  }
}
```

### Arduino с WiFi модулем

```cpp
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>
#include <qrcode.h>

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* serverUrl = "http://your-server:8000/api/token";

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("WiFi connected");
  updateQRCode();
}

String lastCreatedAt = "";

void loop() {
  updateQRCode();
  delay(1000);  // Проверяем каждую секунду
}

void updateQRCode() {
  WiFiClient client;
  HTTPClient http;
  
  http.begin(client, serverUrl);
  int httpCode = http.GET();
  
  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    
    DynamicJsonDocument doc(1024);
    deserializeJson(doc, payload);
    
    String currentCreatedAt = doc["created_at"] | "";
    
    // Обновляем QR только если токен изменился
    if (currentCreatedAt != lastCreatedAt) {
      lastCreatedAt = currentCreatedAt;
      String url = doc["url"];
      Serial.println("QR URL updated: " + url);
      
      // Генерация и отображение QR-кода
      // ... ваш код для отображения
    }
    
  } else {
    Serial.printf("HTTP error: %d\n", httpCode);
  }
  
  http.end();
}
```

### Python (Raspberry Pi с дисплеем)

```python
import requests
import qrcode
from PIL import Image
import time

SERVER_URL = "http://your-server:8000/api/token"
API_KEY = "your_api_key"  # Опционально

def get_token():
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    
    response = requests.get(SERVER_URL, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data["url"]
    return None

def generate_qr_code(url):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    return img

def main():
    while True:
        url = get_token()
        if url:
            print(f"Current token URL: {url}")
            qr_img = generate_qr_code(url)
            # Отображение на дисплее или сохранение
            qr_img.save("qrcode.png")
            # display.show(qr_img)  # Для e-ink дисплея
        
        time.sleep(5)  # Обновление каждые 5 секунд

if __name__ == "__main__":
    main()
```

## Библиотеки для генерации QR-кода

### Arduino/ESP32
- **QRCode**: https://github.com/ricmoo/QRCode
- Установка через Arduino Library Manager: поиск "QRCode"

### Python
- **qrcode**: `pip install qrcode[pil]`
- **Pillow**: для работы с изображениями

## Рекомендации

1. **Частота обновления**: 
   - **Рекомендуется**: проверять токен каждые **1-2 секунды** для быстрого обновления после сканирования
   - **Минимум**: каждые 5 секунд (но это даст задержку до 5 секунд после сканирования)
   - **Важно**: токен остается **одним и тем же**, пока его не отсканируют. После сканирования создается новый токен
   
2. **Оптимизация с `created_at`**: Используйте поле `created_at` из ответа API для отслеживания изменений. Обновляйте QR-код только если `created_at` изменился, это позволит проверять токен чаще без лишней перерисовки дисплея.

2. **Обработка ошибок**: Всегда обрабатывайте случаи, когда сервер недоступен или возвращает ошибку. В таких случаях можно показывать предыдущий QR-код или сообщение об ошибке.

3. **Кэширование**: Сохраняйте последний полученный токен и обновляйте QR-код только при изменении токена.

4. **Безопасность**: Если используете API key, храните его в безопасном месте (EEPROM, зашифрованном хранилище).

5. **Размер QR-кода**: Для дисплеев с низким разрешением используйте версию QR-кода 1-3 (меньше данных, но проще отсканировать).

## Пример с кэшированием токена (оптимизированный)

```cpp
String lastToken = "";
String lastCreatedAt = "";

void updateQRCode() {
  HTTPClient http;
  http.begin(serverUrl);
  int httpCode = http.GET();
  
  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    DynamicJsonDocument doc(1024);
    deserializeJson(doc, payload);
    
    String currentToken = doc["token"];
    String currentCreatedAt = doc["created_at"] | "";
    
    // Обновляем QR только если токен изменился (проверяем по created_at или token)
    if (currentCreatedAt != lastCreatedAt || currentToken != lastToken) {
      lastToken = currentToken;
      lastCreatedAt = currentCreatedAt;
      String url = doc["url"];
      generateAndDisplayQR(url);
      Serial.println("QR updated: " + currentToken);
    }
  }
  
  http.end();
}

void loop() {
  // Проверяем каждую секунду для быстрого обновления
  updateQRCode();
  delay(1000);
}
```

**Преимущества этого подхода:**
- Проверка каждую секунду позволяет получить новый токен в течение 1 секунды после сканирования
- Перерисовка QR-кода происходит только при изменении токена (экономия ресурсов)
- Использование `created_at` более надежно, чем сравнение токенов

## Поддержка

При возникновении проблем проверьте:
1. Доступность сервера: `curl http://your-server:8000/api/health`
2. Правильность API key (если используется)
3. Логи сервера для диагностики ошибок

