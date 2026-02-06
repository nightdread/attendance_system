/*
 * ESP32 QR Code Display для системы учета времени
 * 
 * Требуемые библиотеки:
 * - WiFi (встроенная)
 * - HTTPClient (встроенная)
 * - ArduinoJson (установить через Library Manager)
 * - QRCode (https://github.com/ricmoo/QRCode)
 * - TFT_eSPI (для TFT дисплеев, например ILI9341)
 * 
 * Подключение TFT дисплея (ILI9341):
 * - VCC -> 5V
 * - GND -> GND
 * - CS -> GPIO 5
 * - RESET -> GPIO 4
 * - DC -> GPIO 2
 * - MOSI -> GPIO 23
 * - SCK -> GPIO 18
 * - LED -> GPIO 15 (опционально, для подсветки)
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
const char* apiKey = "";

// Инициализация дисплея
TFT_eSPI tft = TFT_eSPI();

// Переменные для отслеживания изменений токена
String lastCreatedAt = "";
unsigned long lastUpdateTime = 0;
const unsigned long UPDATE_INTERVAL = 1000;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("Инициализация ESP32 QR Code Display...");
  
  // Инициализация дисплея
  tft.init();
  tft.setRotation(1);
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  tft.setCursor(10, 10);
  tft.println("Connecting WiFi...");
  
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
    tft.println("WiFi OK!");
    delay(1000);
  } else {
    Serial.println("WiFi connection failed!");
    tft.fillScreen(TFT_BLACK);
    tft.setCursor(10, 10);
    tft.setTextColor(TFT_RED, TFT_BLACK);
    tft.println("WiFi ERROR!");
    return;
  }
  
  updateQRCode();
}

void loop() {
  unsigned long currentTime = millis();
  
  if (currentTime - lastUpdateTime >= UPDATE_INTERVAL) {
    lastUpdateTime = currentTime;
    updateQRCode();
  }
}

void updateQRCode() {
  HTTPClient http;
  
  http.begin(serverUrl);
  
  if (strlen(apiKey) > 0) {
    http.addHeader("X-API-Key", apiKey);
  }
  
  http.setTimeout(5000);
  
  int httpCode = http.GET();
  
  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    Serial.println("Response: " + payload);
    
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
    
    if (currentCreatedAt != lastCreatedAt && url.length() > 0) {
      lastCreatedAt = currentCreatedAt;
      Serial.println("Token updated: " + url);
      
      generateAndDisplayQR(url);
    }
    
  } else {
    Serial.printf("HTTP error: %d\n", httpCode);
    if (httpCode < 0) {
      displayError("Connection error");
    } else {
      displayError("HTTP " + String(httpCode));
    }
  }
  
  http.end();
}

void generateAndDisplayQR(String url) {
  QRCode qrcode;
  uint8_t qrcodeData[qrcode_getBufferSize(3)];
  
  int error = qrcode_initText(&qrcode, qrcodeData, 3, 0, url.c_str());
  
  if (error != 0) {
    Serial.println("QR code generation failed!");
    displayError("QR gen error");
    return;
  }
  
  displayQRCode(&qrcode);
}

void displayQRCode(QRCode *qrcode) {
  int size = qrcode->size;
  int displayWidth = tft.width();
  int displayHeight = tft.height();
  
  int scale = min(displayWidth, displayHeight) / (size + 4);
  if (scale < 1) scale = 1;
  
  int qrPixelSize = size * scale;
  int offsetX = (displayWidth - qrPixelSize) / 2;
  int offsetY = (displayHeight - qrPixelSize) / 2;
  
  tft.fillScreen(TFT_WHITE);
  
  for (int y = 0; y < size; y++) {
    for (int x = 0; x < size; x++) {
      if (qrcode_getModule(qrcode, x, y)) {
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
  
  Serial.println("QR code displayed");
}

void displayError(String message) {
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_RED, TFT_BLACK);
  tft.setTextSize(2);
  tft.setCursor(10, tft.height() / 2 - 20);
  tft.println("ERROR:");
  tft.setCursor(10, tft.height() / 2);
  tft.println(message);
}
