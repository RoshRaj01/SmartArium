"""
alerts.py — Threshold checking and status classification.
"""

SENSOR_THRESHOLDS = {
    "oxygen": {
        "green":  (6.0, 10.0),
        "yellow": (5.0, 11.0),
        "orange": (4.0, 12.0),
        # below 4 or above 12 → red
    },
    "ammonia": {
        "green":  (0.0, 0.25),
        "yellow": (0.0, 0.5),
        "orange": (0.0, 1.0),
    },
    "tds": {
        "green":  (100, 300),
        "yellow": (50, 500),
        "orange": (30, 700),
    },
    "temperature": {
        "green":  (24.0, 28.0),
        "yellow": (22.0, 30.0),
        "orange": (20.0, 32.0),
    },
    "ph": {
        "green":  (6.5, 7.5),
        "yellow": (6.0, 8.0),
        "orange": (5.5, 8.5),
    },
    "water_level": {
        "green":  (80, 100),
        "yellow": (65, 100),
        "orange": (50, 100),
    },
}

SENSOR_LABELS = {
    "oxygen": "Dissolved Oxygen",
    "ammonia": "Ammonia",
    "tds": "TDS",
    "temperature": "Temperature",
    "ph": "pH",
    "water_level": "Water Level",
}

SENSOR_UNITS = {
    "oxygen": "mg/L",
    "ammonia": "ppm",
    "tds": "ppm",
    "temperature": "°C",
    "ph": "pH",
    "water_level": "%",
}

def get_sensor_status(sensor_type, value):
    """Returns 'green', 'yellow', 'orange', or 'red'."""
    t = SENSOR_THRESHOLDS.get(sensor_type)
    if not t:
        return "green"
    for level in ("green", "yellow", "orange"):
        lo, hi = t[level]
        if lo <= value <= hi:
            return level
    return "red"

def check_alerts(sensor_type, value):
    """Check thresholds and write alerts to DB if needed."""
    from services.database import db
    status = get_sensor_status(sensor_type, value)
    label = SENSOR_LABELS.get(sensor_type, sensor_type)
    unit = SENSOR_UNITS.get(sensor_type, "")

    if status == "red":
        msg = f"🚨 CRITICAL: {label} is at {value}{unit} — immediate action required!"
        db.add_alert(sensor_type, msg, "critical")
    elif status == "orange":
        msg = f"⚠️ WARNING: {label} is at {value}{unit} — needs attention."
        db.add_alert(sensor_type, msg, "warning")
    elif status == "yellow":
        msg = f"💛 NOTICE: {label} is at {value}{unit} — monitor closely."
        db.add_alert(sensor_type, msg, "notice")
    else:
        # clear existing alerts for this sensor
        from services.database import db as _db
        _db.dismiss_alert_by_sensor(sensor_type)
