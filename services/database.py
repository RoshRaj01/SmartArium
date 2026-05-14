"""
database.py — Local SQLite database.
To switch to Supabase (free cloud tier), replace the SQL calls with
the supabase-py client. Schema is identical.
"""
import sqlite3
import random
import math
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "aquamon.db")

class Database:
    def _conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        conn = self._conn()
        c = conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_type TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feeder_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL DEFAULT 'every_8h',
                custom_times TEXT,
                quantity_grams REAL NOT NULL DEFAULT 5.0,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feeding_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount_grams REAL NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT DEFAULT 'scheduled'
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_type TEXT,
                message TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'warning',
                dismissed INTEGER NOT NULL DEFAULT 0,
                timestamp TEXT NOT NULL
            );
        """)
        conn.commit()
        conn.close()

    # ── Sensor Data ────────────────────────────────────────────────────────────

    def insert_reading(self, sensor_type, value):
        conn = self._conn()
        conn.execute(
            "INSERT INTO sensor_data (sensor_type, value, timestamp) VALUES (?,?,?)",
            (sensor_type, value, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def get_latest(self, sensor_type):
        conn = self._conn()
        row = conn.execute(
            "SELECT value FROM sensor_data WHERE sensor_type=? ORDER BY id DESC LIMIT 1",
            (sensor_type,)
        ).fetchone()
        conn.close()
        return round(row["value"], 2) if row else _default_value(sensor_type)

    def get_latest_all(self):
        sensors = ["oxygen", "ammonia", "tds", "temperature", "ph", "water_level"]
        return {s: self.get_latest(s) for s in sensors}

    def get_history(self, sensor_type, limit=50):
        conn = self._conn()
        rows = conn.execute(
            "SELECT value, timestamp FROM sensor_data WHERE sensor_type=? ORDER BY id DESC LIMIT ?",
            (sensor_type, limit)
        ).fetchall()
        conn.close()
        result = [{"value": round(r["value"], 2), "timestamp": r["timestamp"]} for r in rows]
        result.reverse()
        return result

    def simulate_readings(self):
        """Seed the database with 48 hours of simulated history (every 30 min)."""
        conn = self._conn()
        count = conn.execute("SELECT COUNT(*) as c FROM sensor_data").fetchone()["c"]
        conn.close()
        if count > 10:
            # already seeded — just add one fresh reading
            for s in ["oxygen", "ammonia", "tds", "temperature", "ph", "water_level"]:
                self.insert_reading(s, _simulate_value(s))
            return

        now = datetime.now()
        conn = self._conn()
        for i in range(96):  # 48 hours × 2
            ts = (now - timedelta(minutes=30 * (96 - i))).isoformat()
            for s in ["oxygen", "ammonia", "tds", "temperature", "ph", "water_level"]:
                val = _simulate_value(s, drift=i)
                conn.execute(
                    "INSERT INTO sensor_data (sensor_type, value, timestamp) VALUES (?,?,?)",
                    (s, val, ts)
                )
        conn.commit()
        conn.close()
        # generate initial alerts
        for s in ["oxygen", "ammonia", "tds", "temperature", "ph", "water_level"]:
            v = self.get_latest(s)
            from services.alerts import check_alerts
            check_alerts(s, v)

    # ── Feeder ────────────────────────────────────────────────────────────────

    def get_feeder_schedule(self):
        conn = self._conn()
        row = conn.execute("SELECT * FROM feeder_schedule ORDER BY id DESC LIMIT 1").fetchone()
        log = conn.execute(
            "SELECT amount_grams, timestamp, source FROM feeding_log ORDER BY id DESC LIMIT 10"
        ).fetchall()
        conn.close()
        schedule = dict(row) if row else {
            "mode": "every_8h", "custom_times": None,
            "quantity_grams": 5.0, "updated_at": datetime.now().isoformat()
        }
        schedule["log"] = [dict(l) for l in log]
        return schedule

    def save_feeder_schedule(self, data):
        conn = self._conn()
        conn.execute(
            "INSERT INTO feeder_schedule (mode, custom_times, quantity_grams, updated_at) VALUES (?,?,?,?)",
            (
                data.get("mode", "every_8h"),
                data.get("custom_times"),
                data.get("quantity_grams", 5.0),
                datetime.now().isoformat()
            )
        )
        conn.commit()
        conn.close()

    def log_feeding(self, amount, source="manual"):
        conn = self._conn()
        conn.execute(
            "INSERT INTO feeding_log (amount_grams, timestamp, source) VALUES (?,?,?)",
            (amount, datetime.now().isoformat(), source)
        )
        conn.commit()
        conn.close()

    # ── Alerts ────────────────────────────────────────────────────────────────

    def add_alert(self, sensor_type, message, severity):
        conn = self._conn()
        # avoid duplicate active alerts for same sensor
        conn.execute(
            "DELETE FROM alerts WHERE sensor_type=? AND dismissed=0",
            (sensor_type,)
        )
        conn.execute(
            "INSERT INTO alerts (sensor_type, message, severity, timestamp) VALUES (?,?,?,?)",
            (sensor_type, message, severity, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def get_alerts(self, limit=20):
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM alerts WHERE dismissed=0 ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def dismiss_alert(self, alert_id):
        conn = self._conn()
        conn.execute("UPDATE alerts SET dismissed=1 WHERE id=?", (alert_id,))
        conn.commit()
        conn.close()

    def dismiss_alert_by_sensor(self, sensor_type):
        conn = self._conn()
        conn.execute("UPDATE alerts SET dismissed=1 WHERE sensor_type=? AND dismissed=0", (sensor_type,))
        conn.commit()
        conn.close()


def _default_value(sensor_type):
    defaults = {
        "oxygen": 7.0, "ammonia": 0.1, "tds": 200,
        "temperature": 26.0, "ph": 7.0, "water_level": 90.0
    }
    return defaults.get(sensor_type, 0.0)

def _simulate_value(sensor_type, drift=0):
    """Generate a realistic sensor reading with slight drift over time."""
    base = {
        "oxygen": (7.0, 0.5),
        "ammonia": (0.15, 0.08),
        "tds": (210, 20),
        "temperature": (26.0, 1.0),
        "ph": (7.1, 0.3),
        "water_level": (88.0, 5.0),
    }
    b, noise = base[sensor_type]
    # simulate a slow drift + random noise
    drift_factor = math.sin(drift / 20) * noise * 0.5
    value = b + drift_factor + random.uniform(-noise, noise)
    # clamp
    clamps = {
        "oxygen": (2.0, 12.0), "ammonia": (0.0, 4.0), "tds": (50, 800),
        "temperature": (18.0, 35.0), "ph": (5.0, 9.5), "water_level": (30.0, 100.0)
    }
    lo, hi = clamps[sensor_type]
    return round(max(lo, min(hi, value)), 2)


db = Database()
