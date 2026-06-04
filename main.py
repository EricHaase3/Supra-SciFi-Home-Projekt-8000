import tkinter as tk
import json
import paho.mqtt.client as mqtt

# --- KONFIGURATION ---
MQTT_BROKER = "localhost"           # Da Mosquitto auf demselben Pi läuft
MQTT_PORT = 1883
MQTT_TOPIC = "zigbee2mqtt/dht22_sensor" # Passe 'dht22_sensor' an deinen Filenamen an

# --- HINTERGRUND-LOGIK (MQTT) ---
def on_connect(client, userdata, flags, rc, properties=None):
    """Wird aufgerufen, wenn die Verbindung zum Broker steht."""
    if rc == 0:
        print("Erfolgreich mit MQTT Broker verbunden!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Verbindungsfehler. Code: {rc}")

def on_message(client, userdata, msg):
    """Wird aufgerufen, wenn der ESP32 neue Daten über Zigbee/MQTT sendet."""
    try:
        # Zigbee2MQTT sendet die Daten als JSON-String
        payload = json.loads(msg.payload.decode())
        
        # Werte auslesen (Zigbee2MQTT rechnet die Werte automatisch wieder in Floats um)
        temperatur = payload.get("temperature", "--.-")
        luftfeuchtigkeit = payload.get("humidity", "--.-")
        
        # GUI-Anzeige im Hauptthread aktualisieren
        lbl_temp.config(text=f"{temperatur} °C")
        lbl_hum.config(text=f"{luftfeuchtigkeit} %")
        
    except Exception as e:
        print(f"Fehler beim Parsen der Daten: {e}")

# --- GUI-ERSTELLUNG (Tkinter) ---
# Hauptfenster initialisieren
root = tk.Tk()
root.title("Smarthome Dashboard")

# Fenstergröße an das Hamtysan-Display anpassen (1024x600)
root.geometry("1024x600")
root.configure(bg="#1e1e24") # Dunkler, moderner Hintergrund

# Optional: Vollbildmodus aktivieren (beenden mit Alt+F4)
# root.attributes('-fullscreen', True)

# Layout-Rahmen (Cards) für ein schickes Design
frame_main = tk.Frame(root, bg="#1e1e24")
frame_main.place(relx=0.5, rely=0.5, anchor="center")

# --- TITEL ---
lbl_title = tk.Label(frame_main, text="Klimadaten Sensor 1", font=("Helvetica", 28, "bold"), fg="#ffffff", bg="#1e1e24")
lbl_title.grid(row=0, column=0, columnspan=2, pady=(0, 40))

# --- TEMPERATUR CARD ---
frame_temp = tk.Frame(frame_main, bg="#2a2a35", padx=30, pady=20, bd=2, relief="groove")
frame_temp.grid(row=1, column=0, padx=20)

lbl_temp_title = tk.Label(frame_temp, text="TEMPERATUR", font=("Helvetica", 14, "bold"), fg="#ff5964", bg="#2a2a35")
lbl_temp_title.pack()

lbl_temp = tk.Label(frame_temp, text="--.- °C", font=("Helvetica", 48, "bold"), fg="#ffffff", bg="#2a2a35")
lbl_temp.pack(pady=10)

# --- LUFTFEUCHTIGKEIT CARD ---
frame_hum = tk.Frame(frame_main, bg="#2a2a35", padx=30, pady=20, bd=2, relief="groove")
frame_hum.grid(row=1, column=1, padx=20)

lbl_hum_title = tk.Label(frame_hum, text="LUFTFEUCHTIGKEIT", font=("Helvetica", 14, "bold"), fg="#35a7ff", bg="#2a2a35")
lbl_hum_title.pack()

lbl_hum = tk.Label(frame_hum, text="--.- %", font=("Helvetica", 48, "bold"), fg="#ffffff", bg="#2a2a35")
lbl_hum.pack(pady=10)

# --- MQTT CLIENT STARTEN ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start() # Startet den MQTT-Empfang in einem eigenen Thread im Hintergrund
except Exception as e:
    print(f"MQTT Broker nicht erreichbar: {e}")
    lbl_temp.config(text="No Connection")
    lbl_hum.config(text="No Connection")

# Start der GUI-Schleife (hält das Fenster offen)
root.mainloop()