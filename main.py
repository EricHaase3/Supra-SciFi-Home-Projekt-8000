import json
import threading
import paho.mqtt.client as mqtt
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
from datetime import datetime
from database import init_db, save_measurement

# ─── Konfiguration ────────────────────────────────────────────────
MQTT_BROKER     = "localhost"
MQTT_BASE_TOPIC = "zigbee2mqtt/#"  # Lauscht auf alle Ebenen
MAX_WERTE       = 60               # Anzahl sichtbarer Messpunkte im Diagramm
# ──────────────────────────────────────────────────────────────────

aktiver_sensor = "Warte auf Sensor..."
temperaturen   = deque(maxlen=MAX_WERTE)
luftfeuchten   = deque(maxlen=MAX_WERTE)
zeitstempel    = deque(maxlen=MAX_WERTE)
lock           = threading.Lock()
ani            = None

# ─── MQTT Callbacks ───────────────────────────────────────────────
def on_connect(client, userdata, flags, rc, properties=None):
    code = rc if isinstance(rc, int) else getattr(rc, "value", 0)
    if code == 0:
        print(f"[MQTT] Verbunden mit Broker {MQTT_BROKER}")
        client.subscribe(MQTT_BASE_TOPIC)
        print(f"[MQTT] Lauscht auf Topic: {MQTT_BASE_TOPIC}")
    else:
        print(f"[MQTT] Verbindung fehlgeschlagen, Code: {rc}")

def on_message(client, userdata, msg):
    global aktiver_sensor
    try:
        topic_parts = msg.topic.split("/")
        if len(topic_parts) < 2:
            return

        sensor_name = topic_parts[1]
        
        # Interne Zigbee2MQTT Status-Meldungen überspringen
        if sensor_name == "bridge":
            return

        payload = json.loads(msg.payload.decode("utf-8"))
        print(f"[MQTT Eingang] {msg.topic} -> {payload}")

        temp = payload.get("temperature") or payload.get("local_temperature") or payload.get("temp")
        hum  = payload.get("humidity") or payload.get("hum")

        if temp is None:
            return

        jetzt = datetime.now().strftime("%H:%M:%S")

        # 1. In SQLite Datenbank sichern
        save_measurement(
            sensor_name=sensor_name,
            temperature=float(temp),
            humidity=float(hum) if hum is not None else None
        )

        # 2. In Live-Grafik aufnehmen
        with lock:
            aktiver_sensor = sensor_name
            temperaturen.append(float(temp))
            luftfeuchten.append(float(hum) if hum is not None else 0.0)
            zeitstempel.append(jetzt)

        hum_str = f"{float(hum):.1f} %" if hum is not None else "Keine"
        print(f"[{jetzt}] [{sensor_name}] 💾 Gespeichert -> Temp: {float(temp):.1f} °C | Feuchte: {hum_str}")

    except json.JSONDecodeError:
        pass
    except Exception as e:
        print(f"[MQTT] Fehler beim Verarbeiten von {msg.topic}: {e}")

# ─── MQTT-Client im Hintergrund ───────────────────────────────────
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
    except ConnectionRefusedError:
        print("[MQTT] Broker nicht erreichbar – läuft Mosquitto?")

# ─── Visualisierung ───────────────────────────────────────────────
def erstelle_diagramm():
    global ani
    fig, (ax_temp, ax_hum) = plt.subplots(2, 1, figsize=(12, 7))
    fig.patch.set_facecolor("#1e1e2e")
    fig.suptitle("SciFi-Home – Live Sensordaten & Historie", color="white",
                 fontsize=15, fontweight="bold")

    for ax in (ax_temp, ax_hum):
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaaacc")
        ax.spines[:].set_color("#44445a")
        for spine in ax.spines.values():
            spine.set_linewidth(0.5)

    def aktualisieren(frame):
        with lock:
            s_name = aktiver_sensor
            temps  = list(temperaturen)
            hums   = list(luftfeuchten)
            zeiten = list(zeitstempel)

        if not temps:
            # Platzhalter während des Wartens
            ax_temp.cla()
            ax_temp.set_facecolor("#2a2a3e")
            ax_temp.set_title("Warte auf Messwerte vom Zigbee-Sensor...", color="#cdd6f4", fontsize=11)
            ax_temp.tick_params(colors="#aaaacc")
            ax_hum.cla()
            ax_hum.set_facecolor("#2a2a3e")
            ax_hum.set_title("Warte auf Feuchtigkeitsdaten...", color="#cdd6f4", fontsize=11)
            ax_hum.tick_params(colors="#aaaacc")
            return

        # Temperatur-Diagramm
        ax_temp.cla()
        ax_temp.set_facecolor("#2a2a3e")
        ax_temp.plot(zeiten, temps, color="#f38ba8", linewidth=2.2,
                     marker="o", markersize=4, label="Temperatur")
        if temps:
            ax_temp.fill_between(zeiten, temps, min(temps) - 1, alpha=0.15, color="#f38ba8")
        ax_temp.set_ylabel("°C", color="#f38ba8", fontsize=11)
        ax_temp.set_title(f"Temperatur [{s_name}]", color="#cdd6f4", fontsize=12, fontweight="bold")
        ax_temp.tick_params(colors="#aaaacc", labelsize=8)
        ax_temp.spines[:].set_color("#44445a")
        ax_temp.annotate(f"{temps[-1]:.1f} °C",
                         xy=(zeiten[-1], temps[-1]),
                         xytext=(5, 5), textcoords="offset points",
                         color="#f38ba8", fontsize=11, fontweight="bold")
        step = max(1, len(zeiten) // 6)
        ax_temp.set_xticks(range(0, len(zeiten), step))
        ax_temp.set_xticklabels(zeiten[::step], rotation=30, ha="right")

        # Luftfeuchte-Diagramm
        ax_hum.cla()
        ax_hum.set_facecolor("#2a2a3e")
        ax_hum.plot(zeiten, hums, color="#89b4fa", linewidth=2.2,
                    marker="s", markersize=4, label="Luftfeuchte")
        if hums and max(hums) > 0:
            ax_hum.fill_between(zeiten, hums, min(hums) - 1, alpha=0.15, color="#89b4fa")
        ax_hum.set_ylabel("%", color="#89b4fa", fontsize=11)
        ax_hum.set_title(f"Luftfeuchte [{s_name}]", color="#cdd6f4", fontsize=12, fontweight="bold")
        ax_hum.tick_params(colors="#aaaacc", labelsize=8)
        ax_hum.spines[:].set_color("#44445a")
        if hums and hums[-1] > 0:
            ax_hum.annotate(f"{hums[-1]:.1f} %",
                             xy=(zeiten[-1], hums[-1]),
                             xytext=(5, 5), textcoords="offset points",
                             color="#89b4fa", fontsize=11, fontweight="bold")
        step = max(1, len(zeiten) // 6)
        ax_hum.set_xticks(range(0, len(zeiten), step))
        ax_hum.set_xticklabels(zeiten[::step], rotation=30, ha="right")

        plt.tight_layout(rect=[0, 0, 1, 0.95])

    # Vollbildmodus aktivieren
    mng = plt.get_current_fig_manager()
    try:
        mng.full_screen_toggle()
    except Exception:
        try:
            mng.window.attributes("-fullscreen", True)
        except Exception:
            pass

    ani = animation.FuncAnimation(fig, aktualisieren, interval=2000, cache_frame_data=False)
    plt.show()

# ─── Start ────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    t = threading.Thread(target=mqtt_thread, daemon=True)
    t.start()
    erstelle_diagramm()