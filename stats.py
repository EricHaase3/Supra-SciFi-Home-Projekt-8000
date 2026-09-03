import sqlite3
import os
from database import DB_PATH, get_stats_summary

def zeige_statistik():
    if not os.path.exists(DB_PATH):
        print(f"\n[Info] Noch keine Datenbank unter '{DB_PATH}' vorhanden.")
        return

    stats = get_stats_summary()
    if not stats:
        print("\n[Info] Datenbank ist initialisiert, aber es sind noch keine Messwerte vorhanden.")
        return

    print("\n" + "=" * 70)
    print("        📊 SUPRA-SCIFI-HOME – SENSORDATEN STATISTIK")
    print("=" * 70)

    for row in stats:
        sensor, count, min_t, avg_t, max_t, min_h, avg_h, max_h, start, ende = row
        print(f"\n📍 Sensor: {sensor}")
        print(f"   ├─ Messpunkte gesamt: {count}")
        print(f"   ├─ Zeitraum:          {start} bis {ende}")
        print(f"   ├─ Temperatur (°C):   Min: {min_t}°C | Schnitt: {avg_t}°C | Max: {max_t}°C")
        if min_h is not None:
            print(f"   └─ Feuchtigkeit (%):  Min: {min_h}% | Schnitt: {avg_h}% | Max: {max_h}%")
        else:
            print(f"   └─ Feuchtigkeit (%):  Keine Daten")

    print("\n" + "=" * 70 + "\n")

if __name__ == "__main__":
    zeige_statistik()
