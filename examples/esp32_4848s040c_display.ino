/*
 * ESP32 QR Code Display для системы учета времени
 * Специально для ESP32-4848S040C (4.0" Capacitive Touch, 480x480)
 * 
 * Требуемые библиотеки:
 * - WiFi (встроенная)
 * - HTTPClient (встроенная)
 * - ArduinoJson (установить через Library Manager)
 * - QRCode (https://github.com/ricmoo/QRCode)
 * - TFT_eSPI (https://github.com/Bodmer/TFT_eSPI)
 * 
 * Подключение дисплея ESP32-4848S040C:
 * - VCC -> 5V
 * - GND -> GND
 * - SDA/MOSI -> GPIO 23
 * - SCL/SCK -> GPIO 18
 * - CS -> GPIO 5
 * - DC -> GPIO 2
 * - RST -> GPIO 4
 * - BL (Backlight) -> GPIO 15 (опционально, для управления подсветкой)
 * 
 * Примечание: Этот дисплей обычно использует драйвер ST7789 или ILI9341
 * Проверьте документацию вашего дисплея для точных настроек
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <qrcode.h>
#include <TFT_eSPI.h>

// Настройки WiFi
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Настройки сервера
const char* serverUrl = "http://your-server:8000/api/token";
const char* apiKey = "";  // Опционально, если настроен API_KEY на сервере

// Инициализация дисплея
TFT_eSPI tft = TFT_eSPI();

// Переменные для отслеживания изменений токена
String lastCreatedAt = "";
unsigned long lastUpdateTime = 0;
const unsigned long UPDATE_INTERVAL = 1000;  // Проверка каждую секунду

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("Инициализация ESP32-4848S040C QR Code Display...");
  Serial.println("Разрешение: 480x480 пикселей");
  
  // Инициализация дисплея
  tft.init();
  tft.setRotation(0);  // Портретная ориентация (можно изменить на 1, 2, 3)
  tft.fillScreen(TFT_BLACK);
  
  // Настройка шрифта и цветов
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  tft.setCursor(10, 10);
  tft.println("ESP32-4848S040C");
  tft.setCursor(10, 40);
  tft.println("480x480 Display");
  tft.setCursor(10, 70);
  tft.println("Connecting WiFi...");
  
  // Управление подсветкой (если подключена к GPIO 15)
  pinMode(15, OUTPUT);
  digitalWrite(15, HIGH);  // Включить подсветку
  
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
    
    tft.fillScreen(TFT_BLACK);
    tft.setCursor(10, 10);
    tft.setTextColor(TFT_GREEN, TFT_BLACK);
    tft.println("WiFi Connected!");
    tft.setCursor(10, 40);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.print("IP: ");
    tft.println(WiFi.localIP().toString());
    delay(2000);
  } else {
    Serial.println("WiFi connection failed!");
    tft.fillScreen(TFT_BLACK);
    tft.setCursor(10, 10);
    tft.setTextColor(TFT_RED, TFT_BLACK);
    tft.println("WiFi ERROR!");
    tft.setCursor(10, 40);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.println("Check SSID/Password");
    return;
  }
  
  // Первое обновление QR-кода
  updateQRCode();
}

void loop() {
  unsigned long currentTime = millis();
  
  // Проверяем токен каждую секунду
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
  // Для дисплея 480x480 можно использовать версию 3 или 4
  QRCode qrcode;
  uint8_t qrcodeData[qrcode_getBufferSize(4)];
  
  int error = qrcode_initText(&qrcode, qrcodeData, 4, 0, url.c_str());
  
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
  int displayWidth = tft.width();   // 480
  int displayHeight = tft.height(); // 480
  
  // Вычисляем масштаб для центрирования QR-кода
  // Для дисплея 480x480 и QR версии 4 (примерно 33x33 модуля)
  // можно использовать масштаб 10-12 пикселей на модуль
  int scale = min(displayWidth, displayHeight) / (size + 6);  // +6 для отступов
  if (scale < 8) scale = 8;   // Минимальный масштаб для читаемости
  if (scale > 12) scale = 12; // Максимальный масштаб для размера экрана
  
  // Центрируем QR-код
  int qrPixelSize = size * scale;
  int offsetX = (displayWidth - qrPixelSize) / 2;
  int offsetY = (displayHeight - qrPixelSize) / 2;
  
  // Очищаем экран белым фоном (для лучшей контрастности QR-кода)
  tft.fillScreen(TFT_WHITE);
  
  // Рисуем QR-код
  // Белый фон уже установлен, рисуем черные модули
  for (int y = 0; y < size; y++) {
    for (int x = 0; x < size; x++) {
      if (qrcode_getModule(qrcode, x, y)) {
        // Рисуем черный квадрат
        tft.fillRect(
          offsetX + x * scale,
          offsetY + y * scale,
          scale,
          scale,
          TFT_BLACK
        );
      }
    }
  }
  
  // Опционально: добавляем текст под QR-кодом
  tft.setTextColor(TFT_BLACK, TFT_WHITE);
  tft.setTextSize(1);
  tft.setCursor(10, displayHeight - 30);
  tft.println("Scan QR code with Telegram");
  
  Serial.println("QR code displayed");
  Serial.printf("QR size: %dx%d, Scale: %d, Offset: (%d, %d)\n", 
                size, size, scale, offsetX, offsetY);
}

void displayError(String message) {
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_RED, TFT_BLACK);
  tft.setTextSize(2);
  tft.setCursor(10, tft.height() / 2 - 20);
  tft.println("ERROR:");
  tft.setCursor(10, tft.height() / 2);
  tft.setTextSize(1);
  tft.println(message);
}
