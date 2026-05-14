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

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    sensors.requestTemperatures(); 
    float temperatureC = sensors.getTempCByIndex(0);
    
    if (temperatureC != DEVICE_DISCONNECTED_C) {
      Serial.println("-------------------------");
      Serial.print("Current Temperature: ");
      Serial.print(temperatureC);
      Serial.println(" °C");
      
      // Send data to Flask
      HTTPClient http;
      http.begin(serverUrl);
      http.addHeader("Content-Type", "application/json");
      
      StaticJsonDocument<200> doc;
      doc["sensor_type"] = "temperature";
      doc["value"] = temperatureC;
      
      String requestBody;
      serializeJson(doc, requestBody);
      
      Serial.println("Sending data to server...");
      int httpResponseCode = http.POST(requestBody);
      
      if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.print("Server Response Code: ");
        Serial.println(httpResponseCode);
        Serial.print("Server Message: ");
        Serial.println(response);
      } else {
        Serial.print("!! ERROR sending POST: ");
        Serial.println(httpResponseCode);
        Serial.println("Check if your Laptop and ESP32 are on the same WiFi!");
      }
      http.end();
      Serial.println("-------------------------");
    } else {
      Serial.println("!! SENSOR ERROR: DS18B20 not found!");
      Serial.println("Check your wiring and the 4.7k resistor.");
      Serial.println("-------------------------");
    }
  }
  
  delay(10000); // Wait 10 seconds before next reading
}
