/*
 * ESP32 QR Code Display для системы учета времени
 * OLED дисплей (SSD1306 128x64 или 128x32)
 * 
 * Требуемые библиотеки:
 * - WiFi (встроенная)
 * - HTTPClient (встроенная)
 * - ArduinoJson (установить через Library Manager)
 * - QRCode (https://github.com/ricmoo/QRCode)
 * - Adafruit_SSD1306 (https://github.com/adafruit/Adafruit_SSD1306)
 * - Adafruit_GFX (https://github.com/adafruit/Adafruit-GFX-Library)
 * 
 * Подключение OLED дисплея (SSD1306 I2C):
 * - VCC -> 3.3V
 * - GND -> GND
 * - SDA -> GPIO 21
 * - SCL -> GPIO 22
 * 
 * Для SPI версии:
 * - MOSI -> GPIO 23
 * - CLK -> GPIO 18
 * - CS -> GPIO 5
 * - DC -> GPIO 2
 * - RST -> GPIO 4
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <qrcode.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// Настройки OLED дисплея
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1  // Reset pin (или -1 если используется Arduino reset)
#define SCREEN_ADDRESS 0x3C  // I2C адрес (обычно 0x3C или 0x3D)

// Инициализация дисплея (I2C)
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Для SPI версии используйте:
// #define OLED_MOSI   23
// #define OLED_CLK    18
// #define OLED_DC     2
// #define OLED_CS     5
// #define OLED_RST    4
// Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, OLED_MOSI, OLED_CLK, OLED_DC, OLED_RST, OLED_CS);

// Настройки WiFi
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Настройки сервера
const char* serverUrl = "http://your-server:8000/api/token";
const char* apiKey = "";  // Опционально, если настроен API_KEY на сервере

// Переменные для отслеживания изменений токена
String lastCreatedAt = "";
unsigned long lastUpdateTime = 0;
const unsigned long UPDATE_INTERVAL = 1000;  // Проверка каждую секунду

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("Инициализация ESP32 OLED QR Code Display...");
  
  // Инициализация I2C для OLED
  Wire.begin();
  
  // Инициализация дисплея
  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println(F("SSD1306 allocation failed"));
    for (;;);  // Зависаем, если дисплей не найден
  }
  
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
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
    
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("WiFi OK!");
    display.display();
    delay(1000);
  } else {
    Serial.println("WiFi connection failed!");
    display.clearDisplay();
    display.setCursor(0, 0);
    display.setTextColor(SSD1306_WHITE);
    display.println("WiFi ERROR!");
    display.display();
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
  // Для OLED дисплеев используем версию 2 (меньше размер, но подходит для коротких URL)
  QRCode qrcode;
  uint8_t qrcodeData[qrcode_getBufferSize(2)];
  
  int error = qrcode_initText(&qrcode, qrcodeData, 2, 0, url.c_str());
  
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
  // Для OLED дисплеев обычно нужен масштаб 2-3 пикселя на модуль QR-кода
  int scale = min(displayWidth, displayHeight) / (size + 2);  // +2 для отступов
  if (scale < 1) scale = 1;
  if (scale > 4) scale = 4;  // Ограничиваем максимальный масштаб
  
  // Центрируем QR-код
  int qrPixelSize = size * scale;
  int offsetX = (displayWidth - qrPixelSize) / 2;
  int offsetY = (displayHeight - qrPixelSize) / 2;
  
  // Очищаем экран
  display.clearDisplay();
  
  // Рисуем QR-код
  // OLED дисплеи обычно черные пиксели на черном фоне, поэтому рисуем белые пиксели
  for (int y = 0; y < size; y++) {
    for (int x = 0; x < size; x++) {
      if (qrcode_getModule(qrcode, x, y)) {
        // Рисуем белый квадрат (для OLED черный фон, белые пиксели)
        display.fillRect(
          offsetX + x * scale,
          offsetY + y * scale,
          scale,
          scale,
          SSD1306_WHITE
        );
      }
    }
  }
  
  // Обновляем дисплей
  display.display();
  
  Serial.println("QR code displayed");
}

void displayError(String message) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, display.height() / 2 - 10);
  display.println("ERROR:");
  display.setCursor(0, display.height() / 2);
  display.println(message);
  display.display();
}
