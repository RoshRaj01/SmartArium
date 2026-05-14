#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ESP32Servo.h>

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
const int waterLevelPin = 35; // Connected to Signal (S)
const int servoPin = 13;     // Orange Signal wire

Servo feederServo;
const char* feederUrl = "http://10.45.181.234:5000/api/feeder/check";

void performFeeding(float grams) {
  if (grams <= 0) return;
  Serial.print("FEADING: "); Serial.print(grams); Serial.println("g");
  
  feederServo.write(90); // Open
  
  // Timing: 1s for 1g, then 0.2s for each extra gram
  int duration = 1000 + (int)((grams - 1) * 200);
  if (duration < 1000) duration = 1000;
  
  delay(duration);
  feederServo.write(0); // Close
}

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
  feederServo.attach(servoPin);
  feederServo.write(0); // Start closed
}

void checkFeeder() {
  HTTPClient http;
  http.begin(feederUrl);
  int code = http.GET();
  if (code == 200) {
    String payload = http.getString();
    StaticJsonDocument<200> doc;
    deserializeJson(doc, payload);
    if (doc["active"]) {
      performFeeding(doc["amount"]);
    }
  }
  http.end();
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
  checkFeeder();
  if (WiFi.status() == WL_CONNECTED) {
    // 1. Temperature
    sensors.requestTemperatures(); 
    float temp = sensors.getTempCByIndex(0);
    if (temp != DEVICE_DISCONNECTED_C) {
      sendSensorData("temperature", temp);
    }

    delay(1000); // Give the server more time to breathe

    // 2. MQ-135 (Ammonia)
    int rawMQ = analogRead(mq135Pin);
    float ppm = (rawMQ / 4095.0) * 100.0; 
    sendSensorData("ammonia", ppm);

    delay(500);

    // 3. Water Level (Analog)
    int rawWater = analogRead(waterLevelPin);
    float levelPercent = (rawWater / 4095.0) * 100.0; 
    sendSensorData("water_level", levelPercent);
    delay(1000);
  }
  delay(5000); 
}
