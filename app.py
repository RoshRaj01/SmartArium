from flask import Flask, render_template, jsonify, request
import sqlite3
import configparser
from datetime import datetime, timedelta
import random
import json

# ─── Load Config ─────────────────────────────────────────────────────────────
config = configparser.ConfigParser()
config.read('config.ini')

SERVER_PORT = config.getint('SERVER', 'port', fallback=5000)
SERVER_DEBUG = config.getboolean('SERVER', 'debug', fallback=True)
DB_PATH = config.get('DATABASE', 'path', fallback='aquamon.db')

# ─── Feeder Global State ───
PENDING_FEED = {"active": False, "amount": 1}
LAST_SCHEDULED_FEED = "" # Format "HH:MM" to avoid double-feeding

# ─── Database Logic ──────────────────────────────────────────────────────────
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init(self):
        with self.conn:
            self.conn.execute("CREATE TABLE IF NOT EXISTS readings (id INTEGER PRIMARY KEY, type TEXT, value REAL, timestamp DATETIME)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, sensor_type TEXT, message TEXT, severity TEXT, timestamp DATETIME, active INTEGER DEFAULT 1)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS feeder_settings (id INTEGER PRIMARY KEY, mode TEXT, quantity_grams REAL, custom_times TEXT, start_time TEXT)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS feeding_log (id INTEGER PRIMARY KEY, amount REAL, timestamp DATETIME, source TEXT)")

    def insert_reading(self, sensor_type, value):
        with self.conn:
            self.conn.execute("INSERT INTO readings (type, value, timestamp) VALUES (?, ?, ?)", (sensor_type, value, datetime.now()))

    def get_latest(self, sensor_type):
        cursor = self.conn.execute("SELECT value FROM readings WHERE type = ? ORDER BY timestamp DESC LIMIT 1", (sensor_type,))
        row = cursor.fetchone()
        return row[0] if row else 0

    def get_latest_all(self):
        types = ["oxygen", "ammonia", "tds", "temperature", "ph", "water_level"]
        return {t: self.get_latest(t) for t in types}

    def get_history(self, sensor_type, limit=50):
        cursor = self.conn.execute("SELECT value, timestamp FROM readings WHERE type = ? ORDER BY timestamp DESC LIMIT ?", (sensor_type, limit))
        return [{"value": r[0], "timestamp": r[1]} for r in cursor.fetchall()]

    def add_alert(self, sensor_type, message, severity):
        with self.conn:
            self.conn.execute("INSERT INTO alerts (sensor_type, message, severity, timestamp) VALUES (?, ?, ?, ?)", (sensor_type, message, severity, datetime.now()))

    def get_alerts(self, limit=10):
        cursor = self.conn.execute("SELECT * FROM alerts WHERE active = 1 ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]

    def dismiss_alert(self, alert_id):
        with self.conn:
            self.conn.execute("UPDATE alerts SET active = 0 WHERE id = ?", (alert_id,))

    def get_feeder_schedule(self):
        cursor = self.conn.execute("SELECT * FROM feeder_settings LIMIT 1")
        row = cursor.fetchone()
        settings = dict(row) if row else {"mode": "every_24h", "quantity_grams": 5.0, "custom_times": "[]", "start_time": "08:00"}
        
        # Get recent logs
        cursor = self.conn.execute("SELECT amount as amount_grams, timestamp, source FROM feeding_log ORDER BY timestamp DESC LIMIT 10")
        settings["log"] = [dict(r) for r in cursor.fetchall()]
        return settings

    def save_feeder_schedule(self, data):
        with self.conn:
            self.conn.execute("DELETE FROM feeder_settings")
            self.conn.execute("INSERT INTO feeder_settings (mode, quantity_grams, custom_times, start_time) VALUES (?, ?, ?, ?)", 
                              (data["mode"], data["quantity_grams"], data["custom_times"], data["start_time"]))

    def log_feeding(self, amount, source="manual"):
        with self.conn:
            self.conn.execute("INSERT INTO feeding_log (amount, timestamp, source) VALUES (?, ?, ?)", (amount, datetime.now(), source))

    def simulate_readings(self):
        types = ["oxygen", "ammonia", "tds", "temperature", "ph", "water_level"]
        for t in types:
            val = random.uniform(20, 30) if t == "temperature" else random.uniform(0, 100)
            self.insert_reading(t, val)

db = Database()

# ─── Alert Logic ─────────────────────────────────────────────────────────────
SENSOR_THRESHOLDS = {
    "temperature": (config.getfloat('THRESHOLDS', 'temp_min', fallback=24.0), config.getfloat('THRESHOLDS', 'temp_max', fallback=28.0)),
    "ph": (6.5, 8.5),
    "ammonia": (0, 20.0), # Adjusted for MQ-135 Raw Range
    "water_level": (50, 100),
    "tds": (0, 500),
    "oxygen": (5, 12)
}

def get_sensor_status(sensor_type, value):
    if sensor_type not in SENSOR_THRESHOLDS: return "green"
    lo, hi = SENSOR_THRESHOLDS[sensor_type]
    if lo <= value <= hi: return "green"
    return "red"

def is_sensor_online(sensor_type):
    cursor = db.conn.execute("SELECT timestamp FROM readings WHERE type = ? ORDER BY timestamp DESC LIMIT 1", (sensor_type,))
    row = cursor.fetchone()
    if not row: return False
    last_time = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S.%f")
    return (datetime.now() - last_time).total_seconds() < 60

def check_alerts(sensor_type, value):
    status = get_sensor_status(sensor_type, value)
    if status == "red":
        db.add_alert(sensor_type, f"ALERT: {sensor_type} is out of range!", "critical")

app = Flask(__name__)

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    sensors = {k: round(v, 2) for k, v in db.get_latest_all().items()}
    alerts = db.get_alerts(limit=5)
    statuses = {s: get_sensor_status(s, sensors[s]) for s in sensors}
    return render_template("dashboard.html", sensors=sensors, statuses=statuses, alerts=alerts)

@app.route("/sensor/<sensor_type>")
def sensor(sensor_type):
    valid = ["oxygen", "ammonia", "tds", "temperature", "ph", "water_level"]
    if sensor_type not in valid:
        return "Not found", 404
    current = db.get_latest(sensor_type)
    status = get_sensor_status(sensor_type, current)
    history = db.get_history(sensor_type, limit=50)
    suggestions = get_suggestions(sensor_type, current)
    info = SENSOR_INFO[sensor_type]
    return render_template("sensor.html",
        sensor_type=sensor_type,
        current=current,
        status=status,
        history=history,
        suggestions=suggestions,
        info=info
    )

@app.route("/feeder")
def feeder():
    schedule = db.get_feeder_schedule()
    return render_template("feeder.html", schedule=schedule)

@app.route("/notifications")
def notifications():
    alerts = db.get_alerts(limit=50)
    return render_template("notifications.html", alerts=alerts)

# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.route("/api/sensor/<sensor_type>/latest")
def api_sensor_latest(sensor_type):
    value = db.get_latest(sensor_type)
    status = get_sensor_status(sensor_type, value)
    return jsonify({"value": value, "status": status, "timestamp": datetime.now().isoformat()})

@app.route("/api/sensors/all")
def api_sensors_all():
    sensors = db.get_latest_all()
    result = {}
    for s, v in sensors.items():
        result[s] = {
            "value": round(v, 2), 
            "status": get_sensor_status(s, v),
            "online": is_sensor_online(s)
        }
    alerts = db.get_alerts(limit=5)
    alert_list = [{"id": a["id"], "message": a["message"], "severity": a["severity"], "timestamp": a["timestamp"]} for a in alerts]
    return jsonify({"sensors": result, "alerts": alert_list})

@app.route("/api/sensor/<sensor_type>/history")
def api_sensor_history(sensor_type):
    limit = int(request.args.get("limit", 50))
    history = db.get_history(sensor_type, limit=limit)
    return jsonify(history)

@app.route("/api/feeder/schedule", methods=["GET"])
def api_get_schedule():
    return jsonify(db.get_feeder_schedule())

@app.route("/api/feeder/schedule", methods=["POST"])
def api_set_schedule():
    data = request.json
    db.save_feeder_schedule(data)
    return jsonify({"success": True})

@app.route("/api/feeder/feed-now", methods=["POST"])
def api_feed_now():
    global PENDING_FEED
    data = request.json
    amount = float(data.get("amount", 1))
    PENDING_FEED["active"] = True
    PENDING_FEED["amount"] = amount
    return jsonify({"success": True, "message": f"Feeding {amount}g initiated..."})

@app.route("/api/feeder/check")
def api_feeder_check():
    global PENDING_FEED, LAST_SCHEDULED_FEED
    
    # 1. Check Scheduled Feeding
    now = datetime.now()
    now_str = now.strftime("%H:%M")
    
    if now_str != LAST_SCHEDULED_FEED:
        settings = db.get_feeder_schedule()
        mode = settings["mode"]
        start_time = settings["start_time"]
        target_times = []
        
        if mode != "custom":
            try:
                base_h, base_m = map(int, start_time.split(':'))
                if mode == "every_8h":
                    target_times = [f"{(base_h + i*8)%24:02d}:{base_m:02d}" for i in range(3)]
                elif mode == "every_12h":
                    target_times = [f"{(base_h + i*12)%24:02d}:{base_m:02d}" for i in range(2)]
                elif mode == "every_24h":
                    target_times = [start_time]
            except Exception as e:
                print(f"[FEEDER ERROR] Failed to calculate cycles: {e}")
                target_times = [start_time]
        else: 
            try: target_times = json.loads(settings["custom_times"])
            except: target_times = []

        # Check if current minute matches any target time
        if now_str in target_times:
            print(f"[FEEDER] Time Match! Current: {now_str}, Targets: {target_times}")
            PENDING_FEED["active"] = True
            PENDING_FEED["amount"] = settings["quantity_grams"]
            LAST_SCHEDULED_FEED = now_str
            db.log_feeding(settings["quantity_grams"], source="auto")
        else:
            # Just log once a minute what we are waiting for
            if random.random() < 0.05: # Only log occasionally to avoid spam
                 print(f"[FEEDER] Waiting... Current Time: {now_str}, Target Times: {target_times}")

    # 2. Return Status
    status = PENDING_FEED.copy()
    if PENDING_FEED["active"]:
        PENDING_FEED["active"] = False 
    return jsonify(status)

@app.route("/api/alerts/dismiss/<int:alert_id>", methods=["POST"])
def api_dismiss_alert(alert_id):
    db.dismiss_alert(alert_id)
    return jsonify({"success": True})

@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    """Insert a batch of simulated sensor readings"""
    db.simulate_readings()
    return jsonify({"success": True})

@app.route("/api/sensor/insert", methods=["POST"])
def api_insert():
    """Endpoint for Arduino/ESP32 to post real sensor data"""
    data = request.json
    sensor_type = data.get("sensor_type")
    value = data.get("value")
    
    if not sensor_type or value is None:
        return jsonify({"error": "Missing sensor_type or value"}), 400
        
    db.insert_reading(sensor_type, value)
    check_alerts(sensor_type, value)
    return jsonify({"success": True})

# ─── Suggestions Logic ────────────────────────────────────────────────────────

SENSOR_INFO = {
    "oxygen": {"label": "Dissolved Oxygen", "unit": "mg/L", "icon": "💧", "ideal": "6–8 mg/L"},
    "ammonia": {"label": "Ammonia", "unit": "ppm", "icon": "⚗️", "ideal": "< 0.25 ppm"},
    "tds": {"label": "Total Dissolved Solids", "unit": "ppm", "icon": "🧪", "ideal": "100–300 ppm"},
    "temperature": {"label": "Temperature", "unit": "°C", "icon": "🌡️", "ideal": "24–28 °C"},
    "ph": {"label": "pH Level", "unit": "pH", "icon": "⚖️", "ideal": "6.5–7.5"},
    "water_level": {"label": "Water Level", "unit": "%", "icon": "🫧", "ideal": "80–100%"},
}

def get_suggestions(sensor_type, value):
    tips = {
        "oxygen": {
            "green": ["Great oxygen levels! Your fish are thriving.", "Maintain current aeration. All good!"],
            "yellow": ["Consider increasing surface agitation slightly.", "Check that your air pump is running optimally."],
            "orange": ["Add an additional air stone or powerhead.", "Check for algae blooms that may be consuming oxygen overnight.", "Reduce fish load or increase filtration."],
            "red": ["URGENT: Add emergency aeration immediately.", "Perform a 30% water change now.", "Check for dead fish or decaying organic matter — remove immediately.", "Reduce feeding until levels normalize."],
        },
        "ammonia": {
            "green": ["Ammonia is safe. Your biological filter is working well.", "Keep up with regular partial water changes."],
            "yellow": ["Perform a 15–20% water change soon.", "Reduce feeding frequency for 2–3 days.", "Check that your filter media is clean and not clogged."],
            "orange": ["Do a 25–30% water change today.", "Add beneficial bacteria (e.g., Seachem Stability).", "Stop feeding for 24–48 hours.", "Test nitrite and nitrate levels too."],
            "red": ["CRITICAL: Do a 50% water change immediately.", "Do NOT feed fish until ammonia drops below 0.25 ppm.", "Use an ammonia detoxifier like Seachem Prime.", "Consider moving fish to a temporary tank if levels don't drop."],
        },
        "tds": {
            "green": ["TDS is in the ideal range for most freshwater fish.", "Maintain current water change schedule."],
            "yellow": ["Consider a partial water change to dilute dissolved solids.", "Check if any medications or additives are raising TDS."],
            "orange": ["Increase water change frequency.", "Inspect substrate for excess waste buildup.", "Check if your tap water has high TDS and consider RO water."],
            "red": ["High TDS can stress fish and inhibit gill function.", "Do a large water change (40–50%) with low-TDS water.", "Deep-clean the substrate using a gravel vacuum."],
        },
        "temperature": {
            "green": ["Temperature is ideal. Fish metabolism and immune function are optimal."],
            "yellow": ["Minor temperature drift detected. Check heater settings.", "Ensure your aquarium lid is closed to reduce evaporation-cooling."],
            "orange": ["Adjust heater by 1–2°C and monitor closely.", "Avoid placing the tank near AC vents or windows.", "Gradual changes are safer — don't adjust more than 1°C per hour."],
            "red": ["Extreme temperature can cause thermal shock.", "Add a fan to cool (if too hot) or check your heater (if too cold).", "Perform gradual water changes with temperature-adjusted water.", "Monitor fish closely for signs of distress."],
        },
        "ph": {
            "green": ["pH is perfect for most freshwater fish.", "Keep up regular water changes to maintain stability."],
            "yellow": ["pH is drifting slightly. Check CO2 levels and carbonate hardness (KH).", "Adding crushed coral or limestone can raise pH naturally."],
            "orange": ["Use a pH buffer to stabilize.", "Check KH — low KH causes pH crashes.", "Avoid large water changes with very different pH water."],
            "red": ["Dangerous pH levels can cause osmotic stress in fish.", "Use pH buffer solutions carefully — change slowly (0.1/hour max).", "Check for CO2 buildup (high plants, low aeration = pH drop).", "Test KH and GH alongside pH."],
        },
        "water_level": {
            "green": ["Water level is optimal. Evaporation is minimal."],
            "yellow": ["Top off with dechlorinated water to compensate for evaporation.", "Check for any slow leaks around seals or equipment."],
            "orange": ["Water level is significantly low. Top off immediately.", "Check if equipment is splashing water out.", "Inspect all tubing and return lines for leaks."],
            "red": ["URGENT: Water level is critical. Pumps and heaters may be exposed!", "Top off immediately to prevent heater burnout.", "Check for active leaks — inspect all seams and equipment."],
        },
    }
    status = get_sensor_status(sensor_type, value)
    return tips.get(sensor_type, {}).get(status, ["No suggestions available."])

if __name__ == "__main__":
    db.init()
    # db.simulate_readings()  # Disabled to show only real hardware data
    app.run(host="0.0.0.0", port=SERVER_PORT, debug=SERVER_DEBUG)
