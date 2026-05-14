from flask import Flask, render_template, jsonify, request
import json
import random
import math
from datetime import datetime, timedelta
from services.database import db
from services.alerts import check_alerts, get_sensor_status, SENSOR_THRESHOLDS

app = Flask(__name__)

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    sensors = db.get_latest_all()
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
        result[s] = {"value": v, "status": get_sensor_status(s, v)}
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
    data = request.json
    amount = data.get("amount", 5)
    db.log_feeding(amount)
    return jsonify({"success": True, "message": f"Fed {amount}g manually"})

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
    db.simulate_readings()  # seed with initial data
    app.run(host="0.0.0.0", port=5000, debug=True)
