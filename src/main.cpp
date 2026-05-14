#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ─── Settings ────────────────────────────────────────────────────────────────
const char* ssid = "iQOO Neo 10R";
const char* password = "netillaman";
const char* serverUrl = "http://10.45.181.234:5000/api/sensor/insert";

// DS18B20 Temperature Sensor
const int oneWireBus = 4; // Data wire is plugged into pin 4 on the ESP32
OneWire oneWire(oneWireBus);
DallasTemperature sensors(&oneWire);

// MQ-135 Gas Sensor (Ammonia/Air Quality)
const int mq135Pin = 34; // Connected to AO (Analog Output)

void setup() {
  Serial.begin(115200);
  
  // WiFi Connection
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");
  
  // Enable internal pull-up for the sensor data pin
  pinMode(oneWireBus, INPUT_PULLUP);
  
  sensors.begin();
}

void sendSensorData(String type, float value) {
  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  StaticJsonDocument<200> doc;
  doc["sensor_type"] = type;
  doc["value"] = value;
  String requestBody;
  serializeJson(doc, requestBody);
  
  Serial.print("Sending " + type + ": ");
  Serial.println(value);
  
  int httpResponseCode = http.POST(requestBody);
  if (httpResponseCode > 0) {
    Serial.print("Server Response: ");
    Serial.println(httpResponseCode);
  } else {
    Serial.print("Error: ");
    Serial.println(httpResponseCode);
  }
  http.end();
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    // 1. Temperature
    sensors.requestTemperatures(); 
    float temp = sensors.getTempCByIndex(0);
    if (temp != DEVICE_DISCONNECTED_C) {
      sendSensorData("temperature", temp);
    }

    delay(500); // Give the server a moment to breathe

    // 2. MQ-135 (Ammonia)
    int rawValue = analogRead(mq135Pin);
    float ppm = (rawValue / 4095.0) * 100.0; // Simple mapping
    sendSensorData("ammonia", ppm);
  }
  delay(5000); 
}
