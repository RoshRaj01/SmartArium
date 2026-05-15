#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

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
const int turbidityPin = 32;  // Turbidity sensor (Analog)
const int tdsPin = 33;        // TDS Meter V1.0 (Analog)
const int servoPin = 13;     // Orange Signal wire

Servo feederServo;
const char* feederUrl = "http://10.45.181.234:5000/api/feeder/check";

// OLED Display Settings
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Global variables to store latest values for display
float lastTemp = 0;
float lastAmmonia = 0;
float lastWater = 0;
float lastTurbidity = 0;
float lastTDS = 0;
bool isFeeding = false;
int lastResponseCode = 0;

void updateDisplay() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  
  // Header
  display.setCursor(0, 0);
  display.println("--- SMARTARIUM ---");
  display.println("");
  
  if (isFeeding) {
    display.setTextSize(2);
    display.setCursor(10, 25);
    display.println("FEEDING...");
    display.setTextSize(1);
  } else {
    // Temperature
    display.print("Temp:    ");
    display.print(lastTemp, 2);
    display.println(" C");
    
    // Ammonia
    display.print("Ammonia: ");
    display.print(lastAmmonia, 2);
    display.println(" ppm");
    
    // Water Level
    display.print("Water:   ");
    display.print(lastWater, 2);
    display.println(" %");

    // Turbidity
    display.print("Turb:    ");
    display.print(lastTurbidity, 1);
    display.println(" NTU");

    // TDS
    display.print("TDS:     ");
    display.print(lastTDS, 0);
    display.println(" ppm");
  }
  
  // WiFi & Server Status
  display.setCursor(0, 56);
  if (WiFi.status() == WL_CONNECTED) {
    display.print("WIFI:OK");
  } else {
    display.print("WIFI:LOST");
  }
  
  display.setCursor(64, 56);
  display.print("SRV:");
  display.print(lastResponseCode);
  
  display.display();
}

void performFeeding(float grams) {
  if (grams <= 0) return;
  Serial.print("FEADING: "); Serial.print(grams); Serial.println("g");
  
  isFeeding = true;
  updateDisplay();
  
  feederServo.write(90); // Open
  
  // Timing: 1s for 1g, then 0.2s for each extra gram
  int duration = 1000 + (int)((grams - 1) * 200);
  if (duration < 1000) duration = 1000;
  
  delay(duration);
  feederServo.write(0); // Close
  
  isFeeding = false;
  updateDisplay();
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

  // OLED Initialization
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { 
    Serial.println(F("SSD1306 allocation failed"));
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(20, 20);
    display.println("SMARTARIUM");
    display.setCursor(20, 35);
    display.println("Starting...");
    display.display();
    delay(2000);
  }
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
  lastResponseCode = httpResponseCode;
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
      lastTemp = temp;
      updateDisplay(); // Update immediately
      sendSensorData("temperature", temp);
    }

    delay(500);

    // 2. MQ-135 (Ammonia)
    int rawMQ = analogRead(mq135Pin);
    float ppm = (rawMQ / 4095.0) * 100.0; 
    lastAmmonia = ppm;
    updateDisplay(); // Update immediately
    sendSensorData("ammonia", ppm);

    delay(500);

    // 3. Water Level (Analog)
    int rawWater = analogRead(waterLevelPin);
    float levelPercent = (rawWater / 4095.0) * 100.0; 
    lastWater = levelPercent;
    updateDisplay(); 
    sendSensorData("water_level", levelPercent);

    delay(500);

    // 4. Turbidity (Analog)
    int rawTurb = analogRead(turbidityPin);
    // Simple conversion: 3.3V (4095) is clean (~0 NTU), 0V is dirty
    // For many sensors: NTU = -1120.4*V^2 + 5742.3*V - 4353.8
    // Simplified for now: mapping 0-4095 to 3000-0 NTU
    float turbidity = (1.0 - (rawTurb / 4095.0)) * 3000.0;
    if (turbidity < 0) turbidity = 0;
    lastTurbidity = turbidity;
    updateDisplay();
    sendSensorData("turbidity", turbidity);
    
    delay(500);

    // 5. TDS Meter (Analog)
    int rawTDS = analogRead(tdsPin);
    float voltageTDS = rawTDS * (3.3 / 4095.0);
    // Temperature compensation
    float compCoeff = 1.0 + 0.02 * (lastTemp - 25.0);
    float compVolts = voltageTDS / compCoeff;
    // Standard Gravity TDS formula
    float tdsValue = (133.42 * pow(compVolts, 3) - 255.86 * pow(compVolts, 2) + 857.39 * compVolts) * 0.5;
    if (tdsValue < 0) tdsValue = 0;
    lastTDS = tdsValue;
    updateDisplay();
    sendSensorData("tds", tdsValue);

    delay(1000);
  }
  updateDisplay();
  delay(2000); 
}
