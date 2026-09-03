# 🛰️ Supra-SciFi-Home-Projekt-8000: Central Project State & Knowledge Base

> **Hinweis für KI-Modelle & Entwickler:** Diese Datei dient als Single Source of Truth (SSOT) für das gesamte Smart-Home- & Sensor-Projekt. Bitte bei jedem neuen Session-Start einlesen.

---

## 1. Systemübersicht & Architektur

* **Zentraler Host:** Raspberry Pi 4 / 5 (Hostname: `sipi.local`, IP: `192.168.2.170`, OS: Raspberry Pi OS 64-Bit)
  * **SSH Login:** `ssh sipi@sipi.local` (Passwort: `sipi`)
  * **MQTT Broker:** Eclipse Mosquitto (Port: 1883, Topic: `zigbee2mqtt/#`)
  * **Zigbee2MQTT (Z2M):** Web-Frontend auf `http://sipi.local:8080` (Service: `zigbee2mqtt.service`)
  * **Zigbee Koordinator:** ITEAD Sonoff Zigbee 3.0 USB Dongle Plus (`/dev/serial/by-id/usb-ITead_Sonoff_Zigbee_3.0_USB_Dongle_Plus_ccefff26e5a0ef11b0ab9da361ce3355-if00-port0`, IEEE: `0x00124b0038a8e603`, Channel: 11, PAN-ID: 6754)
* **Dauerhafte Speicherung:** SQLite-Datenbank (`data/sensor_history.db`) mit indizierten Timestamps für Mehrjahresauswertungen.
* **Live-Visualisierung:** Python Matplotlib Dashboard (`main.py`) im Vollbildmodus auf dem RPi-Bildschirm (`DISPLAY=:0`).

---

## 2. Hardware & Sensor-Knoten

| Sensor-ID | Friendly Name (Z2M) | IEEE-Adresse | Controller | Messfühler | Pinout | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | `Temp_Hum_01` | `0x1051dbfffe6837b6` | ESP32-H2-Zero (RISC-V) | DHT22 (AM2302) | Data -> GPIO 0, Reset -> GPIO 9 (BOOT) | Online & gepaired |
| **02** | `Temp_Hum_02` | *Noch zu flashen* | ESP32-H2-Zero | DHT22 | Data -> GPIO 0 | Geplant |
| **03** | `Temp_Hum_03` | *Noch zu flashen* | ESP32-H2-Zero | DHT22 | Data -> GPIO 0 | Geplant |

---

## 3. Firmware-Konfiguration (Arduino IDE für ESP32-H2)

* **Board:** `ESP32H2 Dev Module`
* **Flash Mode / Size:** `QIO 80MHz` / `4MB (32Mb)`
* **Partition Scheme:** `Zigbee 4MB with spiffs`
* **Zigbee Mode:** `Zigbee ED (End Device)` (**Wichtig!**)
* **USB CDC On Boot:** `Enabled`
* **Upload Mode:** `UART0 / Hardware CDC`

---

## 4. Datenbank-Schema (`data/sensor_history.db`)

Tabelle `measurements`:
* `id` INTEGER PRIMARY KEY AUTOINCREMENT
* `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP (UTC / Lokal ISO)
* `sensor_name` TEXT (z. B. `Temp_Hum_01`)
* `temperature` REAL (°C)
* `humidity` REAL (% r.F.)
* *Indizes:* `idx_sensor_time (sensor_name, timestamp)`

---

## 5. Wichtigste CLI-Befehle auf dem Raspberry Pi

```bash
# Projekt aktualisieren & Umgebung laden
cd ~/Supra-SciFi-Home-Projekt-8000
git pull
source venv/bin/activate

# 1. Live-Diagramm im Vollbild starten
DISPLAY=:0 python3 main.py

# 2. Statistik-Zusammenfassung in der Konsole anzeigen
python3 stats.py

# 3. Z2M Log & MQTT-Verkehr prüfen
journalctl -u zigbee2mqtt -f
mosquitto_sub -t "zigbee2mqtt/#" -v
```
