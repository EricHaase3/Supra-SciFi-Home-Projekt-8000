import sqlite3
import os
import threading
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "sensor_history.db")
db_lock = threading.Lock()

def init_db():
    """Erstellt den Datenordner und die SQLite-Tabellen, falls noch nicht vorhanden."""
    os.makedirs(DB_DIR, exist_ok=True)
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    sensor_name TEXT NOT NULL,
                    temperature REAL,
                    humidity REAL
                )
            """)
            # Indizes für blitzschnelle Abfragen nach Zeit und Sensor
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON measurements(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor ON measurements(sensor_name)")
            conn.commit()

def save_measurement(sensor_name: str, temperature: float, humidity: float = None):
    """Speichert einen Messwert mit aktuellem Zeitstempel in die Datenbank."""
    if temperature is None:
        return

    jetzt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_lock:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO measurements (timestamp, sensor_name, temperature, humidity)
                    VALUES (?, ?, ?, ?)
                """, (jetzt, sensor_name, float(temperature), float(humidity) if humidity is not None else None))
                conn.commit()
        except Exception as e:
            print(f"[DB-Fehler] Konnte Messwert nicht speichern: {e}")

def get_stats_summary():
    """Gibt eine kurze Zusammenfassung der gespeicherten Sensordaten zurück."""
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    sensor_name,
                    COUNT(*) as anzahl,
                    ROUND(MIN(temperature), 1) as min_temp,
                    ROUND(AVG(temperature), 1) as avg_temp,
                    ROUND(MAX(temperature), 1) as max_temp,
                    ROUND(MIN(humidity), 1) as min_hum,
                    ROUND(AVG(humidity), 1) as avg_hum,
                    ROUND(MAX(humidity), 1) as max_hum,
                    MIN(timestamp) as erster_eintrag,
                    MAX(timestamp) as letzter_eintrag
                FROM measurements
                GROUP BY sensor_name
            """)
            return cursor.fetchall()

def get_last_values():
    """Lädt den jeweils letzten gespeicherten Messwert pro Sensor aus der Datenbank.
    Wird beim Programmstart verwendet, damit die Kacheln sofort Daten anzeigen."""
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sensor_name, temperature, humidity, timestamp
                FROM measurements
                WHERE id IN (
                    SELECT MAX(id) FROM measurements GROUP BY sensor_name
                )
            """)
            rows = cursor.fetchall()
    result = {}
    for row in rows:
        sensor_name, temp, hum, ts = row
        # Nur die Uhrzeit als Anzeigetext
        try:
            ts_kurz = ts.split(" ")[1][:8] if ts and " " in ts else ts
        except Exception:
            ts_kurz = ts
        result[sensor_name] = {
            "temp": float(temp) if temp is not None else None,
            "hum": float(hum) if hum is not None else None,
            "last_seen": ts_kurz,
            "online": False  # Werte aus DB, noch kein aktuelles Signal
        }
    return result

