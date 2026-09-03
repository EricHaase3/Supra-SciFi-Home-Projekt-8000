# Projekt-Status: Supra-SciFi-Home-Projekt-8000

## 1. Projekt-Übersicht
Dieses Projekt realisiert ein Smart-Home-Umweltüberwachungssystem, basierend auf dem Zigbee-Standard. 
Es verbindet moderne Mikrocontroller-Technologie (ESP32-H2) mit einem Raspberry Pi als zentrale Datensenke und Visualisierungs-Hub (Dashboard für ein 7-Zoll-Display).

**Ziel des Systems:** 
Das System sammelt Temperatur- und Luftfeuchtigkeitsdaten von mehreren autarken, batteriebetriebenen Sensorknoten im Haus ("David", "Jana", "Eric", "Dings", "Balkon") und visualisiert diese nahezu in Echtzeit auf einem zentralen Dashboard. Die Daten werden außerdem dauerhaft archiviert, um langfristige klimatische Veränderungen (Jahresrückblicke) analysieren zu können.

---

## 2. Aktueller Stand (03. September 2026)

### 2.1. Hardware & Sensoren (ESP32-H2-Zero + DHT22)
* **Code-Status:** Der Code für die ESP32-Sensoren (`esp_dht22_sketch.ino`) ist fertiggestellt und auf **Sleepy End Device (Deep Sleep)** optimiert.
* **Funktion:** Der Sensor liest die Daten vom DHT22, funkt sie via Zigbee (Endpoint 10, Temp & Feuchte Cluster kombiniert) an Zigbee2MQTT und schläft danach für 10 Minuten (`esp_deep_sleep_start`).
* **Bibliotheken:** Nutzt die native `Zigbee.h` aus dem esp32-Board-Support-Package v3.3.x von Espressif.

### 2.2. Zentrale (Raspberry Pi)
* **Infrastruktur:** Mosquitto (MQTT-Broker) und Zigbee2MQTT (Z2M) mit Sonoff Dongle Plus laufen stabil als Systemdienste.
* **Datenbank:** Die SQLite-Datenbank (`database.py`) speichert zuverlässig und asynchron alle eintreffenden Messdaten mit Zeitstempel. Beim Neustart des Dashboards werden die zuletzt bekannten Werte automatisch aus der Datenbank geladen (`get_last_values`).
* **Visualisierung:** Das Python-Skript (`main.py`) läuft mit Matplotlib und erzeugt ein responsives Dashboard. Das Layout und die Schriftgrößen wurden speziell für ein 7-Zoll Touch-Display optimiert, damit alle Werte (Temp & Feuchte) lesbar bleiben.

---

## 3. Zukünftige Pläne & Weiterentwicklung

### 3.1. Hardware-Modifikationen für Langzeit-Batteriebetrieb
Der Code ist bereits auf Batteriebetrieb optimiert (Deep Sleep). Für echte Langzeitlaufzeiten (Monate/Jahre) stehen folgende physische Umbauten der restlichen Sensoren an:
* **Entfernung der Power-LEDs:** Die LEDs auf den ESP32-H2-Zero Boards müssen abgelötet/entfernt werden, da sie sonst konstant ~2-5 mA verbrauchen.
* **Akkus & LDOs:** Auswahl der finalen Akkus (Ideal: LiFePO4 direkt an 3.3V, um Wandlerverluste zu vermeiden).
* **Optional:** Den `VCC`-Pin des DHT22 nicht dauerhaft an 3.3V hängen, sondern über einen GPIO-Pin nur für die Mess-Sekunde mit Strom versorgen.

### 3.2. "Jahresrückblick" & Datenanalyse
* **`stats.py`:** Ausbau des bisherigen Statistik-Skripts. Geplant ist eine Auswertung (z.B. als PDF oder als generierte Graphen), die Temperaturverläufe über Wochen und Monate darstellt.
* **Datenbereinigung:** Bei monatelangem Sammeln im 10-Minuten-Takt entstehen große Datenmengen (ca. 50.000 Einträge pro Sensor pro Jahr). Ggf. muss später eine Logik integriert werden, die alte Daten verdichtet (z.B. nur noch Tages-Durchschnitte nach 3 Monaten).

### 3.3. Weitere Sensoren
* Fertigstellung der Hardware für "Jana", "Eric", "Dings" und "Balkon" und Anlernen in Zigbee2MQTT unter Verwendung des aktuellen Deep-Sleep-Codes.
