# 🐠 AquaMon — Aquarium Monitoring System

A full-stack aquarium monitoring dashboard built with Flask, HTML/CSS/JS, and SQLite (free to run, free to deploy).

---

## 🚀 Quick Start (Local)

```bash
# 1. Clone / unzip the project
cd aquamon

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py
```

Then open **http://localhost:5000** in your browser.

---

## 📁 Project Structure

```
aquamon/
├── app.py                  ← Flask app + routes + suggestion logic
├── requirements.txt
├── aquamon.db              ← Auto-created SQLite database
│
├── services/
│   ├── database.py         ← All DB reads/writes (swap for Supabase here)
│   └── alerts.py           ← Threshold logic & alert generation
│
├── templates/
│   ├── sidebar.html        ← Shared sidebar (included in all pages)
│   ├── dashboard.html      ← Home dashboard with 6 sensor cards
│   ├── sensor.html         ← Per-sensor detail page with chart
│   ├── feeder.html         ← Feeder control & schedule
│   └── notifications.html  ← All active alerts
│
└── static/
    ├── css/main.css        ← Full dark-ocean theme stylesheet
    └── js/
        ├── main.js         ← Shared JS (clock, alerts, live refresh)
        ├── sensor.js       ← Chart.js chart + live value update
        └── feeder.js       ← Schedule UI + feed-now logic
```

---

## 🌡️ Sensor Thresholds

| Sensor       | Unit  | 🟢 Good      | 🟡 Okay      | 🟠 Bad       | 🔴 Critical   |
|--------------|-------|-------------|-------------|-------------|--------------|
| Dissolved O₂ | mg/L  | 6–10        | 5–11        | 4–12        | < 4 or > 12  |
| Ammonia      | ppm   | 0–0.25      | 0–0.5       | 0–1.0       | > 1.0        |
| TDS          | ppm   | 100–300     | 50–500      | 30–700      | < 30 or > 700|
| Temperature  | °C    | 24–28       | 22–30       | 20–32       | < 20 or > 32 |
| pH           | pH    | 6.5–7.5     | 6.0–8.0     | 5.5–8.5     | < 5.5 or > 8.5|
| Water Level  | %     | 80–100      | 65–100      | 50–100      | < 50         |

---

## 📡 Adding Real Sensor Data

To push data from an ESP32 / Arduino, send a POST request to your deployed app:

```python
# Python example (MicroPython on ESP32)
import urequests, ujson

data = {"sensor_type": "ph", "value": 7.2}
urequests.post("https://your-app.onrender.com/api/sensor/insert", json=data)
```

Add this route to `app.py`:
```python
@app.route("/api/sensor/insert", methods=["POST"])
def api_insert():
    d = request.json
    db.insert_reading(d["sensor_type"], d["value"])
    check_alerts(d["sensor_type"], d["value"])
    return jsonify({"ok": True})
```

---

## ☁️ Free Deployment (Render.com)

1. Push your project to a **GitHub repo**
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Add `gunicorn` to `requirements.txt`
6. Deploy! Your app will be live at `https://your-app.onrender.com`

> **Note:** Render's free tier spins down after 15 min of inactivity. Use [UptimeRobot](https://uptimerobot.com) (free) to ping it every 10 min and keep it awake.

---

## ☁️ Upgrading to Supabase (Free Cloud DB)

Replace the SQLite calls in `services/database.py` with the Supabase Python client:

```bash
pip install supabase
```

```python
from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Insert reading
supabase.table("sensor_data").insert({
    "sensor_type": sensor_type,
    "value": value,
    "timestamp": datetime.now().isoformat()
}).execute()

# Get latest
result = supabase.table("sensor_data")\
    .select("value")\
    .eq("sensor_type", sensor_type)\
    .order("id", desc=True)\
    .limit(1)\
    .execute()
```

Set your Supabase credentials as environment variables on Render:
- `SUPABASE_URL`
- `SUPABASE_KEY`

---

## 🔮 Future Features

- [ ] Connect ESP32 / Arduino sensors via WiFi
- [ ] Email/SMS alerts (Twilio free tier)
- [ ] WebSocket real-time updates (Flask-SocketIO)
- [ ] Mobile PWA support
- [ ] Multiple tank support
- [ ] Fish species profiles with ideal parameter ranges
