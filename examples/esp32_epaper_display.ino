/*
 * ESP32 QR Code Display для системы учета времени
 * E-Paper дисплей (Waveshare 2.9" или аналогичный)
 * 
 * Требуемые библиотеки:
 * - WiFi (встроенная)
 * - HTTPClient (встроенная)
 * - ArduinoJson (установить через Library Manager)
 * - QRCode (https://github.com/ricmoo/QRCode)
 * - GxEPD2 (для e-Paper дисплеев: https://github.com/ZinggJM/GxEPD2)
 * 
 * Подключение e-Paper дисплея (Waveshare 2.9"):
 * - VCC -> 3.3V
 * - GND -> GND
 * - DIN -> GPIO 23 (MOSI)
 * - CLK -> GPIO 18 (SCK)
 * - CS -> GPIO 5
 * - DC -> GPIO 17
 * - RST -> GPIO 16
 * - BUSY -> GPIO 4
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <qrcode.h>
#include <GxEPD2_BW.h>  // Для черно-белых e-Paper дисплеев
#include <GxEPD2_3C.h>  // Для трехцветных e-Paper дисплеев (если используете)

// Выберите модель вашего дисплея (раскомментируйте нужную строку)
// Для Waveshare 2.9" черно-белый:
#include <GxEPD2_290.h>
GxEPD2_BW<GxEPD2_290, GxEPD2_290::HEIGHT> display(GxEPD2_290(/*CS=5*/ SS, /*DC=*/17, /*RST=*/16, /*BUSY=*/4));

// Для Waveshare 2.9" трехцветный (черный/белый/красный):
// #include <GxEPD2_290_T94.h>
// GxEPD2_3C<GxEPD2_290_T94, GxEPD2_290_T94::HEIGHT> display(GxEPD2_290_T94(/*CS=5*/ SS, /*DC=*/17, /*RST=*/16, /*BUSY=*/4));

// Настройки WiFi
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Настройки сервера
const char* serverUrl = "http://your-server:8000/api/token";
const char* apiKey = "";  // Опционально, если настроен API_KEY на сервере

// Переменные для отслеживания изменений токена
String lastCreatedAt = "";
unsigned long lastUpdateTime = 0;
const unsigned long UPDATE_INTERVAL = 2000;  // Проверка каждые 2 секунды (e-Paper медленный)

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("Инициализация ESP32 E-Paper QR Code Display...");
  
  // Инициализация дисплея
  display.init(115200);
  display.setRotation(1);
  display.fillScreen(GxEPD_WHITE);
  display.setTextColor(GxEPD_BLACK);
  
  // Показываем сообщение о подключении
  display.setCursor(10, 10);
  display.println("Connecting WiFi...");
  display.display();
  
  // Подключение к WiFi
  WiFi.begin(ssid, password);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("WiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    
    display.fillScreen(GxEPD_WHITE);
    display.setCursor(10, 10);
    display.println("WiFi OK!");
    display.display();
    delay(1000);
  } else {
    Serial.println("WiFi connection failed!");
    display.fillScreen(GxEPD_WHITE);
    display.setCursor(10, 10);
    display.println("WiFi ERROR!");
    display.display();
    return;
  }
  
  // Первое обновление QR-кода
  updateQRCode();
}

void loop() {
  unsigned long currentTime = millis();
  
  // Проверяем токен каждые 2 секунды (e-Paper медленный, не нужно обновлять слишком часто)
  if (currentTime - lastUpdateTime >= UPDATE_INTERVAL) {
    lastUpdateTime = currentTime;
    updateQRCode();
  }
}

void updateQRCode() {
  HTTPClient http;
  
  // Начинаем HTTP запрос
  http.begin(serverUrl);
  
  // Добавляем API key если настроен
  if (strlen(apiKey) > 0) {
    http.addHeader("X-API-Key", apiKey);
  }
  
  // Устанавливаем таймаут
  http.setTimeout(5000);
  
  // Выполняем GET запрос
  int httpCode = http.GET();
  
  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    Serial.println("Response: " + payload);
    
    // Парсим JSON
    DynamicJsonDocument doc(1024);
    DeserializationError error = deserializeJson(doc, payload);
    
    if (error) {
      Serial.print("JSON parsing failed: ");
      Serial.println(error.c_str());
      http.end();
      return;
    }
    
    String currentCreatedAt = doc["created_at"] | "";
    String url = doc["url"] | "";
    
    // Обновляем QR только если токен изменился
    if (currentCreatedAt != lastCreatedAt && url.length() > 0) {
      lastCreatedAt = currentCreatedAt;
      Serial.println("Token updated: " + url);
      
      // Генерируем и отображаем QR-код
      generateAndDisplayQR(url);
    }
    
  } else {
    Serial.printf("HTTP error: %d\n", httpCode);
    // При ошибке можно показать сообщение на экране
    if (httpCode < 0) {
      displayError("Connection error");
    } else {
      displayError("HTTP " + String(httpCode));
    }
  }
  
  http.end();
}

void generateAndDisplayQR(String url) {
  // Генерируем QR-код
  QRCode qrcode;
  uint8_t qrcodeData[qrcode_getBufferSize(3)];
  
  int error = qrcode_initText(&qrcode, qrcodeData, 3, 0, url.c_str());
  
  if (error != 0) {
    Serial.println("QR code generation failed!");
    displayError("QR gen error");
    return;
  }
  
  // Отображаем QR-код на дисплее
  displayQRCode(&qrcode);
}

void displayQRCode(QRCode *qrcode) {
  int size = qrcode->size;
  int displayWidth = display.width();
  int displayHeight = display.height();
  
  // Вычисляем масштаб для центрирования QR-кода
  int scale = min(displayWidth, displayHeight) / (size + 4);  // +4 для отступов
  if (scale < 1) scale = 1;
  
  // Центрируем QR-код
  int qrPixelSize = size * scale;
  int offsetX = (displayWidth - qrPixelSize) / 2;
  int offsetY = (displayHeight - qrPixelSize) / 2;
  
  // Очищаем экран (белый фон)
  display.fillScreen(GxEPD_WHITE);
  
  // Рисуем QR-код
  // Белый фон уже установлен, рисуем черные модули
  for (int y = 0; y < size; y++) {
    for (int x = 0; x < size; x++) {
      if (qrcode_getModule(qrcode, x, y)) {
        // Рисуем черный квадрат
        display.fillRect(
          offsetX + x * scale,
          offsetY + y * scale,
          scale,
          scale,
          GxEPD_BLACK
        );
      }
    }
  }
  
  // Обновляем дисплей (важно для e-Paper!)
  display.display();
  
  Serial.println("QR code displayed");
}

void displayError(String message) {
  display.fillScreen(GxEPD_WHITE);
  display.setCursor(10, display.height() / 2 - 20);
  display.println("ERROR:");
  display.setCursor(10, display.height() / 2);
  display.println(message);
  display.display();
}
