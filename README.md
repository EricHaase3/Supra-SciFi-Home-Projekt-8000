# Supra-SciFi-Home-Projekt-8000

## Raspberry Pi
- **Login:** `sipi` | **PW:** `sipi`
- **IP:** `192.168.2.170` (bzw. `sipi.local`)
- **Zigbee2MQTT Web-Frontend:** [`http://192.168.2.170:8080`](http://192.168.2.170:8080) *(oder `http://sipi.local:8080`)*

### Wichtige RPi Systemdienste
- **Mosquitto MQTT:** `sudo systemctl status mosquitto`
- **Zigbee2MQTT:** `sudo systemctl status zigbee2mqtt`
- **Logs einsehen:** `journalctl -u zigbee2mqtt -f`

### In Windows CMD / SSH:
```bash
ssh sipi@sipi.local                             # Verbinden mit dem RPi
cd ~/Supra-SciFi-Home-Projekt-8000              # Navigieren in Projektordner
git pull                                        # Aktuellen Code pullen
source venv/bin/activate                        # Venv aktivieren
python3 main.py                                 # Programm ausführen
```

---

## ESP32-H2-Zero (Zigbee Sensor Node)

### Arduino IDE Einstellungen
- **Board:** `ESP32H2 Dev Module` *(Wichtig: RISC-V H2, nicht Standard-ESP32!)*
- **Zigbee Mode:** `Zigbee ED (End Device)` *(Menü Werkzeuge / Tools)*
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

## Offene Punkte & Roadmap
- [x] Raspberry Pi Basis-Setup (Mosquitto + Zigbee2MQTT + Sonoff Dongle Plus)
- [ ] ESP32-H2-Zero flashen und in Zigbee2MQTT pairen
- [ ] Daten von mehreren ESPs in `main.py` visualisieren
- [ ] Datenbank zur persistenten Datenspeicherung (z. B. SQLite / InfluxDB)
- [ ] Zigbee OTA Firmware-Updates über RPi/Konsole evaluieren