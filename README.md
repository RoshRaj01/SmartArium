# 🐠 SmartArium — Aquarium Monitoring System

A high-performance aquarium monitoring dashboard built with Flask, C++ (ESP32), and SQLite.

---

## 🚀 Quick Start (Local)

```bash
# 1. Clone the project
git clone https://github.com/RoshRaj01/SmartArium.git
cd SmartArium

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
# Edit config.ini with your IP and preferences

# 4. Run
python app.py
```

Then open **http://localhost:5000** in your browser.

---

## 📁 Simple Architecture

```
SmartArium/
├── app.py           ← Unified Backend (Server, DB, Logic)
├── firmware.cpp     ← ESP32 C++ Hardware Code
├── config.ini       ← Master Configuration Settings
├── SmartArium.db    ← SQLite Database
├── platformio.ini   ← C++ Library Management
├── static/          ← Styles & UI Logic
└── templates/       ← HTML Layouts
```

---

## 🔌 Master Wiring Table

| Sensor | Pin Name | ESP32 Pin | Note |
| :--- | :--- | :--- | :--- |
| **DS18B20 (Temp)** | Data (Yellow) | **GPIO 4** | Internal Pull-up enabled in code. |
| | VCC (Red) | **3.3V** | |
| | GND (Black) | **GND** | |
| **MQ-135 (Ammonia)**| AO (Analog) | **GPIO 34** | Needs 5V for internal heater. |
| | VCC | **VIN (5V)** | |
| | GND | **GND** | |
| **Water Level** | S (Signal) | **GPIO 35** | |
| | VCC (+) | **3.3V** | |
| | GND (-) | **GND** | |

---

## 🌡️ Integrated Sensors

| Sensor       | Unit  | 🟢 Ideal Range | Hardware Status |
|--------------|-------|---------------|-----------------|
| Temperature  | °C    | 24–28         | Live (Online)   |
| pH Level     | pH    | 6.5–7.5       | Integrated      |
| Water Level  | %     | 80–100        | Integrated      |

---

## 📡 Hardware Integration (ESP32)

To upload the code to your ESP32 from the terminal:
```powershell
pio run --target upload
```

The C++ code in `firmware.cpp` handles WiFi connection, DS18B20 sensor reading, and secure POST requests to the SmartArium API.

---

## ☁️ Deployment

SmartArium is designed for easy deployment to **Render** or **Heroku**.
1. Push to GitHub.
2. Connect to Render.
3. Start Command: `gunicorn app:app`
