import json
import threading
import paho.mqtt.client as mqtt
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
from datetime import datetime

# ─── Konfiguration ────────────────────────────────────────────────
MQTT_BROKER   = "localhost"
MQTT_PORT     = 1883
MQTT_TOPIC    = "zigbee2mqtt/dht22_sensor"  # Namen in Zigbee2MQTT vergeben
MAX_WERTE     = 60  # Anzahl sichtbarer Messpunkte im Diagramm
# ──────────────────────────────────────────────────────────────────

temperaturen  = deque(maxlen=MAX_WERTE)
luftfeuchten  = deque(maxlen=MAX_WERTE)
zeitstempel   = deque(maxlen=MAX_WERTE)
lock          = threading.Lock()
ani           = None  # Referenz halten, um Garbage Collection zu verhindern

# ─── MQTT Callbacks ───────────────────────────────────────────────
def on_connect(client, userdata, flags, rc, properties=None):
    # Unterstützt paho-mqtt Version 1.x und 2.x
    code = rc if isinstance(rc, int) else getattr(rc, "value", 0)
    if code == 0:
        print(f"[MQTT] Verbunden mit Broker {MQTT_BROKER}")
        client.subscribe(MQTT_TOPIC)
        print(f"[MQTT] Topic abonniert: {MQTT_TOPIC}")
    else:
        print(f"[MQTT] Verbindung fehlgeschlagen, Code: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))

        # Zigbee2MQTT liefert Temperatur und ggf. Feuchte
        temp = payload.get("temperature")
        hum  = payload.get("humidity", 0)

        if temp is None:
            return

        jetzt = datetime.now().strftime("%H:%M:%S")

        with lock:
            temperaturen.append(float(temp))
            luftfeuchten.append(float(hum) if hum is not None else 0.0)
            zeitstempel.append(jetzt)

        print(f"[{jetzt}] Temp: {float(temp):.1f} °C | Feuchte: {float(hum):.1f} %")

    except json.JSONDecodeError:
        print(f"[MQTT] Ungültiges JSON: {msg.payload}")
    except Exception as e:
        print(f"[MQTT] Fehler beim Verarbeiten: {e}")

# ─── MQTT-Client in eigenem Thread ────────────────────────────────
def mqtt_thread():
    try:
        # Paho-MQTT 2.0+ Callback API
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        # Fallback für ältere Versionen
        client = mqtt.Client()

    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except ConnectionRefusedError:
        print("[MQTT] Broker nicht erreichbar – läuft Mosquitto?")

# ─── Visualisierung ───────────────────────────────────────────────
def erstelle_diagramm():
    global ani
    fig, (ax_temp, ax_hum) = plt.subplots(2, 1, figsize=(12, 7))
    fig.patch.set_facecolor("#1e1e2e")
    fig.suptitle("SciFi-Home – DHT22 Live-Daten (Zigbee)", color="white",
                 fontsize=14, fontweight="bold")

    for ax in (ax_temp, ax_hum):
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaaacc")
        ax.spines[:].set_color("#44445a")
        for spine in ax.spines.values():
            spine.set_linewidth(0.5)

    def aktualisieren(frame):
        with lock:
            temps  = list(temperaturen)
            hums   = list(luftfeuchten)
            zeiten = list(zeitstempel)

        if not temps:
            return

        # Temperatur-Plot
        ax_temp.cla()
        ax_temp.set_facecolor("#2a2a3e")
        ax_temp.plot(zeiten, temps, color="#f38ba8", linewidth=1.8,
                     marker="o", markersize=3, label="Temperatur")
        if temps:
            ax_temp.fill_between(zeiten, temps,
                                 min(temps) - 1, alpha=0.15, color="#f38ba8")
        ax_temp.set_ylabel("°C", color="#f38ba8")
        ax_temp.set_title("Temperatur", color="#cdd6f4", fontsize=11)
        ax_temp.tick_params(colors="#aaaacc", labelsize=8)
        ax_temp.spines[:].set_color("#44445a")
        ax_temp.annotate(f"{temps[-1]:.1f} °C",
                         xy=(zeiten[-1], temps[-1]),
                         xytext=(5, 5), textcoords="offset points",
                         color="#f38ba8", fontsize=9)
        step = max(1, len(zeiten) // 6)
        ax_temp.set_xticks(range(0, len(zeiten), step))
        ax_temp.set_xticklabels(zeiten[::step], rotation=30, ha="right")

        # Luftfeuchte-Plot
        ax_hum.cla()
        ax_hum.set_facecolor("#2a2a3e")
        ax_hum.plot(zeiten, hums, color="#89b4fa", linewidth=1.8,
                    marker="s", markersize=3, label="Luftfeuchte")
        if hums:
            ax_hum.fill_between(zeiten, hums,
                                min(hums) - 1, alpha=0.15, color="#89b4fa")
        ax_hum.set_ylabel("%", color="#89b4fa")
        ax_hum.set_title("Luftfeuchte", color="#cdd6f4", fontsize=11)
        ax_hum.tick_params(colors="#aaaacc", labelsize=8)
        ax_hum.spines[:].set_color("#44445a")
        ax_hum.annotate(f"{hums[-1]:.1f} %",
                         xy=(zeiten[-1], hums[-1]),
                         xytext=(5, 5), textcoords="offset points",
                         color="#89b4fa", fontsize=9)
        step = max(1, len(zeiten) // 6)
        ax_hum.set_xticks(range(0, len(zeiten), step))
        ax_hum.set_xticklabels(zeiten[::step], rotation=30, ha="right")

        plt.tight_layout(rect=[0, 0, 1, 0.95])

    ani = animation.FuncAnimation(fig, aktualisieren,
                                  interval=2000, cache_frame_data=False)
    plt.show()

# ─── Start ────────────────────────────────────────────────────────
if __name__ == "__main__":
    t = threading.Thread(target=mqtt_thread, daemon=True)
    t.start()
    erstelle_diagramm()