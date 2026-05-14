#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ─── Settings ────────────────────────────────────────────────────────────────
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* serverUrl = "http://192.168.1.100:5000/api/sensor/insert";

// DS18B20 Temperature Sensor
const int oneWireBus = 4; // Data wire is plugged into pin 4 on the ESP32
OneWire oneWire(oneWireBus);
DallasTemperature sensors(&oneWire);

void setup() {
  Serial.begin(115200);
  
  // WiFi Connection
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");
  
  sensors.begin();
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    sensors.requestTemperatures(); 
    float temperatureC = sensors.getTempCByIndex(0);
    
    if (temperatureC != DEVICE_DISCONNECTED_C) {
      Serial.print("Temperature: ");
      Serial.println(temperatureC);
      
      // Send data to Flask
      HTTPClient http;
      http.begin(serverUrl);
      http.addHeader("Content-Type", "application/json");
      
      StaticJsonDocument<200> doc;
      doc["sensor_type"] = "temperature";
      doc["value"] = temperatureC;
      
      String requestBody;
      serializeJson(doc, requestBody);
      
      int httpResponseCode = http.POST(requestBody);
      
      if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.println(httpResponseCode);
        Serial.println(response);
      } else {
        Serial.print("Error on sending POST: ");
        Serial.println(httpResponseCode);
      }
      http.end();
    }
  }
  
  delay(10000); // Wait 10 seconds before next reading
}
