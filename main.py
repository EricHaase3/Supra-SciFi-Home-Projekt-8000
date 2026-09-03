import json
import threading
import time
from datetime import datetime
import paho.mqtt.client as mqtt
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.patches as patches
from database import init_db, save_measurement, get_stats_summary

# ─── Konfiguration ────────────────────────────────────────────────
MQTT_BROKER     = "localhost"
MQTT_BASE_TOPIC = "zigbee2mqtt/#"
UPDATE_INTERVAL = 1000  # UI-Aktualisierung alle 1 Sekunde (ms)

# Vordefinierte Sensor-Slots (erweiterbar auf 5+ Räume)
SLOTS = [
    {"id": "Temp_Hum_01", "name": "Sensor 01 – Wohnzimmer"},
    {"id": "Temp_Hum_02", "name": "Sensor 02 – Schlafzimmer"},
    {"id": "Temp_Hum_03", "name": "Sensor 03 – Büro / Labor"},
    {"id": "Temp_Hum_04", "name": "Sensor 04 – Küche"},
    {"id": "Temp_Hum_05", "name": "Sensor 05 – Außenbereich"},
    {"id": "SYSTEM_INFO", "name": "🛰️ Supra SciFi Zentrale"}
]

# Lokaler Zwischenspeicher für die Anzeige
sensor_daten = {
    slot["id"]: {
        "temp": None,
        "hum": None,
        "last_seen": None,
        "online": False
    }
    for slot in SLOTS if slot["id"] != "SYSTEM_INFO"
}

lock = threading.Lock()

# ─── MQTT Callbacks ───────────────────────────────────────────────
def on_connect(client, userdata, flags, rc, properties=None):
    code = rc if isinstance(rc, int) else getattr(rc, "value", 0)
    if code == 0:
        print(f"[MQTT] Verbunden mit Broker {MQTT_BROKER}")
        client.subscribe(MQTT_BASE_TOPIC)
    else:
        print(f"[MQTT] Verbindung fehlgeschlagen, Code: {rc}")

def on_message(client, userdata, msg):
    try:
        topic_parts = msg.topic.split("/")
        if len(topic_parts) < 2:
            return

        sensor_name = topic_parts[1]
        if sensor_name == "bridge":
            return

        payload = json.loads(msg.payload.decode("utf-8"))

        # Temperatur extrahieren
        temp = None
        for key in ("temperature", "local_temperature", "temp"):
            if key in payload and payload[key] is not None:
                temp = float(payload[key])
                break

        # Luftfeuchtigkeit extrahieren
        hum = None
        for key in ("humidity", "hum", "relative_humidity"):
            if key in payload and payload[key] is not None:
                hum = float(payload[key])
                break

        if temp is None and hum is None:
            return

        jetzt_zeit = datetime.now().strftime("%H:%M:%S")

        # 1. In SQLite Datenbank speichern
        save_measurement(
            sensor_name=sensor_name,
            temperature=temp,
            humidity=hum
        )

        # 2. Lokalen Cache für die Kacheln aktualisieren
        with lock:
            if sensor_name not in sensor_daten:
                sensor_daten[sensor_name] = {"temp": None, "hum": None, "last_seen": None, "online": True}
            
            if temp is not None:
                sensor_daten[sensor_name]["temp"] = temp
            if hum is not None:
                sensor_daten[sensor_name]["hum"] = hum
            sensor_daten[sensor_name]["last_seen"] = jetzt_zeit
            sensor_daten[sensor_name]["online"] = True

        t_str = f"{temp:.1f} °C" if temp is not None else "--.- °C"
        h_str = f"{hum:.1f} %" if hum is not None else "--.- %"
        print(f"[{jetzt_zeit}] [{sensor_name}] 💾 Gespeichert -> Temp: {t_str} | Feuchte: {h_str}")

    except json.JSONDecodeError:
        pass
    except Exception as e:
        print(f"[MQTT] Fehler: {e}")

def mqtt_thread():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()

    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, 1883, keepalive=60)
        client.loop_forever()
    except Exception as e:
        print(f"[MQTT] Verbindungsfehler: {e}")

# ─── Sci-Fi Multi-Kachel Dashboard ────────────────────────────────
def erstelle_dashboard():
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    fig.patch.set_facecolor("#0f0f17")  # Deep Space Dark
    
    # Fensterleiste / Vollbild
    mng = plt.get_current_fig_manager()
    try:
        mng.full_screen_toggle()
    except Exception:
        try:
            mng.window.attributes("-fullscreen", True)
        except Exception:
            pass

    flat_axes = axes.flatten()

    def zeichne_kacheln(frame):
        with lock:
            aktuelle_daten = {k: dict(v) for k, v in sensor_daten.items()}

        uhrzeit_jetzt = datetime.now().strftime("%d.%m.%Y  •  %H:%M:%S")
        fig.suptitle(f"🛰️  SUPRA SCI-FI HOME 8000  •  KLIMA-LEITSTAND\n{uhrzeit_jetzt}",
                     color="#cdd6f4", fontsize=15, fontweight="bold", y=0.97)

        for idx, slot in enumerate(SLOTS):
            ax = flat_axes[idx]
            ax.cla()
            ax.set_facecolor("#181825")
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_color("#313244")
                spine.set_linewidth(1.5)

            slot_id = slot["id"]
            slot_name = slot["name"]

            # Kachel 6: Systeminfo / Zentrale
            if slot_id == "SYSTEM_INFO":
                ax.spines[:].set_color("#89b4fa")
                ax.text(0.5, 0.85, "🛰️ ZENTRALSTATION", color="#89b4fa",
                        fontsize=13, fontweight="bold", ha="center", va="center")
                ax.text(0.5, 0.65, "Host: sipi.local (RPi)", color="#a6adc8",
                        fontsize=11, ha="center", va="center")
                ax.text(0.5, 0.48, "Protokoll: Zigbee 3.0 / MQTT", color="#a6adc8",
                        fontsize=11, ha="center", va="center")
                ax.text(0.5, 0.32, "Datenbank: SQLite (Dauerlogger)", color="#a6adc8",
                        fontsize=11, ha="center", va="center")
                ax.text(0.5, 0.15, "Status: SYSTEM BEREIT ●", color="#a6e3a1",
                        fontsize=12, fontweight="bold", ha="center", va="center")
                continue

            daten = aktuelle_daten.get(slot_id, {"temp": None, "hum": None, "last_seen": None, "online": False})
            temp = daten.get("temp")
            hum = daten.get("hum")
            last = daten.get("last_seen")
            ist_online = (temp is not None or hum is not None)

            # Rahmenfarbe & Status-Badge
            if ist_online:
                ax.spines[:].set_color("#45475a")
                status_text = "● ONLINE"
                status_color = "#a6e3a1"  # Sci-Fi Grün
            else:
                status_text = "○ BEREIT"
                status_color = "#6c7086"  # Grau

            # Titelzeile der Kachel
            ax.text(0.08, 0.88, slot_name, color="#cdd6f4",
                    fontsize=12, fontweight="bold", ha="left", va="center")
            ax.text(0.92, 0.88, status_text, color=status_color,
                    fontsize=10, fontweight="bold", ha="right", va="center")

            # Trennlinie
            ax.axhline(0.78, 0.05, 0.95, color="#313244", linewidth=1.0)

            # Große Zahlenwerte für Temperatur
            if temp is not None:
                temp_str = f"{temp:.1f}"
                temp_unit = "°C"
                t_color = "#f38ba8" if temp >= 24 else ("#89b4fa" if temp <= 19 else "#fab387")
            else:
                temp_str = "--.-"
                temp_unit = "°C"
                t_color = "#585b70"

            # Große Zahlenwerte für Luftfeuchte
            if hum is not None and hum > 0:
                hum_str = f"{hum:.1f}"
                hum_unit = "%"
                h_color = "#89b4fa"
            else:
                hum_str = "--.-"
                hum_unit = "%"
                h_color = "#585b70"

            # Anzeige Temperatur-Block (Links)
            ax.text(0.28, 0.52, temp_str, color=t_color,
                    fontsize=26, fontweight="bold", ha="center", va="center")
            ax.text(0.28, 0.30, f"Temperatur ({temp_unit})", color="#a6adc8",
                    fontsize=9, ha="center", va="center")

            # Vertikale Trennlinie
            ax.axvline(0.50, 0.22, 0.72, color="#313244", linewidth=1.0)

            # Anzeige Feuchte-Block (Rechts)
            ax.text(0.72, 0.52, hum_str, color=h_color,
                    fontsize=26, fontweight="bold", ha="center", va="center")
            ax.text(0.72, 0.30, f"Luftfeuchte ({hum_unit})", color="#a6adc8",
                    fontsize=9, ha="center", va="center")

            # Fußzeile mit Zeitstempel
            last_text = f"Letztes Signal: {last}" if last else "Wartet auf Funkkontakt..."
            ax.text(0.5, 0.10, last_text, color="#6c7086",
                    fontsize=8, ha="center", va="center")

        plt.subplots_adjust(left=0.04, right=0.96, top=0.88, bottom=0.05, wspace=0.15, hspace=0.18)

    ani = animation.FuncAnimation(fig, zeichne_kacheln, interval=UPDATE_INTERVAL, cache_frame_data=False)
    plt.show()

# ─── Start ────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    t = threading.Thread(target=mqtt_thread, daemon=True)
    t.start()
    erstelle_dashboard()