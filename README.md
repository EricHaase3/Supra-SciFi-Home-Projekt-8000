# Supra-SciFi-Home-Projekt-8000

## Raspberry Pi
- **Login:** `sipi` | **PW:** `sipi`
- **IP:** `192.168.2.170` (bzw. `sipi.local`)
- **Zigbee2MQTT Web-Frontend:** [`http://192.168.2.170:8080`](http://192.168.2.170:8080) *(oder `http://sipi.local:8080`)*
- **SQLite-Datenbank:** `data/sensor_history.db` *(speichert alle Messwerte automatisch)*

### In Windows CMD / SSH:
```bash
ssh sipi@sipi.local                             # Verbinden mit dem RPi
cd ~/Supra-SciFi-Home-Projekt-8000              # Navigieren in Projektordner
git pull                                        # Aktuellen Code pullen
source venv/bin/activate                        # Venv aktivieren

# Live-Visualisierung + permanenter SQLite-Logger:
DISPLAY=:0 python3 main.py

# Statistik aller Sensoren in der Konsole anzeigen:
python3 stats.py
```

### Wichtige RPi Systemdienste
- **Mosquitto MQTT:** `sudo systemctl status mosquitto`
- **Zigbee2MQTT:** `sudo systemctl status zigbee2mqtt`
- **Logs einsehen:** `journalctl -u zigbee2mqtt -f`

---

## ESP32-H2-Zero (Zigbee Sensor Node)

### Arduino IDE Einstellungen
- **Board:** `ESP32H2 Dev Module` *(Wichtig: RISC-V H2)*
- **Zigbee Mode:** `Zigbee ED (End Device)` *(Menü Werkzeuge / Tools)*
- **Partition Scheme:** `Zigbee 4MB with spiffs` *(Wichtig für NVRAM)*
- **USB CDC On Boot:** `Enabled` *(Für Serial Monitor Ausgabe)*
- **Flash Size:** `4MB (32Mb)`

### Benötigte Bibliotheken
- **Board-Paket:** `esp32` by *Espressif Systems* ($\ge$ Version `3.0.0`)
- **Bibliotheksverwalter:**
  - `DHT sensor library` by *Adafruit*
  - `Adafruit Unified Sensor` *(Abhängigkeit)*

### Pinbelegung (DHT22 an ESP32-H2-Zero)
| DHT22 Pin | Funktion | ESP32-H2-Zero Pin |
| :--- | :--- | :--- |
| **Pin 1 (VCC)** | 3.3V | **3V3** (oder 5V/VBUS) |
| **Pin 2 (DATA)** | Daten | **GPIO 0** *(Pull-Up 4.7k-10k bei Einzelsensor)* |
| **Pin 3 (NC)** | Nicht belegt | – |
| **Pin 4 (GND)** | Masse | **GND** |

- **Pairing / Reset:** Integrierte `BOOT`-Taste (**GPIO 9**) beim Start gedrückt halten.

---

## Roadmap & Status
- [x] Raspberry Pi Basis-Setup (Mosquitto + Zigbee2MQTT + Sonoff Dongle Plus)
- [x] ESP32-H2-Zero Firmware (DHT22 + Zigbee End Device)
- [x] Zigbee2MQTT Pairing erfolgreich
- [x] SQLite-Datenbankanbindung (`database.py` & `stats.py`)
- [x] Deep Sleep für extremen Batteriebetrieb implementiert (Sleepy End Device)

### Hardware To-Dos (Vor dem finalen Verbauen)
- [ ] **Power-LEDs entfernen:** Von allen ESP32-H2-Zero Boards die Power-LED abkratzen/auslöten, da sie den Akku entlädt (~2-5 mA permanent).
- [ ] **Akkus wählen:** LiFePO4 Akku (3.2V) an den `3V3` Pin klemmen ODER Li-Ion (3.7V) an den `5V` Pin klemmen.
- [ ] **DHT22 verkabeln:** Sensoren an den neuen Boards (Jana, Eric, Dings, Balkon) exakt wie das erste Board verlöten (GPIO 0).
- [ ] Alle weiteren Sensoren flashen und in Zigbee2MQTT anlernen.

### Ausblick (Was kommt als nächstes?)
- **Jahresrückblick & Datenanalyse:** Ausbau von `stats.py` zu einem Script, das langfristige Auswertungen und Graphen aus der SQLite-Datenbank generiert (z.B. für Temperaturverläufe über Wochen/Monate).
- **Batterie-Überwachung:** Den internen ADC (Analog-Digital-Wandler) des ESP32 auslesen und den echten Batteriestand (anstelle von fixen 100%) übertragen.
- **Vision: Interaktives 10-Zoll Hausflur-Terminal:**
  - Migration auf ein größeres 10-Zoll Touchdisplay als zentrales UI.
  - Eine Benutzeroberfläche mit **3 Reitern (Tabs)**:
    1. **Live:** Aktuelle Temperatur- und Feuchtigkeitswerte.
    2. **Historie:** Diagramme und Graphen der letzten Tage, Wochen und Monate.
    3. **Info & Steuerung:** Erinnerungen (z.B. Müllkalender) und System-Buttons (wie z.B. ein Button zum sicheren Herunterfahren des Raspberry Pi ohne Konsolenbefehl).