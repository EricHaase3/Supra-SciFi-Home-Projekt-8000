/*******************************************************************************
 * ESP32-H2 Zigbee & DHT22 Raumklima-Sensor (SciFi-Home)
 * 
 * Hardware:
 *   - ESP32-H2-Zero (RISC-V 32-Bit, Native IEEE 802.15.4 / Zigbee 3.0)
 *   - DHT22 (AM2302) Temperatur- und Feuchtigkeitssensor an GPIO 0
 *   - Integrierter BOOT-Button an GPIO 9 für Zigbee Factory-Reset (5 Sek. halten)
 ******************************************************************************/

#ifndef ZIGBEE_MODE_ED
#error "Bitte in der Arduino IDE unter 'Tools' -> 'Zigbee Mode' -> 'Zigbee ED (End Device)' auswaehlen!"
#endif

#include "DHT.h"
#include "Zigbee.h"

// ─── Pin- und Hardware-Definitionen ──────────────────────────────
#define DHTPIN        0       // DHT22 Daten-Pin an GPIO 0
#define DHTTYPE       DHT22   // DHT 22 (AM2302)
#define BUTTON_PIN    9       // BOOT-Taste für Zigbee Factory-Reset

// Sende-Intervall: Für den Live-Test z.B. 20 Sekunden (20000)
// Für den Dauerbetrieb später: 10 Minuten = 600000 ms (10 * 60 * 1000)
const unsigned long SENDE_INTERVALL = 20000; 

// ─── Globale Objekte ─────────────────────────────────────────────
DHT dht(DHTPIN, DHTTYPE);
ZigbeeTempSensor zbTempSensor = ZigbeeTempSensor(10); // Endpunkt 10

unsigned long letzteMessung = 0;

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  dht.begin();

  // Prüfen, ob die BOOT-Taste beim Start gehalten wird -> Zigbee Netzwerk löschen
  bool resetGedrueckt = (digitalRead(BUTTON_PIN) == LOW);
  if (resetGedrueckt) {
    Serial.println(F("[Zigbee] Factory-Reset angefordert! Netzwerk-Daten werden gelöscht..."));
  }

  // 1. Zigbee-Sensor konfigurieren
  zbTempSensor.setManufacturerAndModel("SciFi-Home", "ESP32H2-DHT22");
  zbTempSensor.setMinMaxValue(-20, 60); // Temperaturbereich in °C
  zbTempSensor.setTolerance(0.2);       // Mindeständerung für automatisches Reporting

  // Ersten Messwert direkt vor dem Zigbee-Start einlesen
  delay(1000);
  float startTemp = dht.readTemperature();
  if (!isnan(startTemp)) {
    zbTempSensor.setTemperature(startTemp);
    Serial.printf("[Sensor] Startwert Temperatur: %.2f °C\n", startTemp);
  }

  // 2. Endpunkt bei Zigbee registrieren
  Zigbee.addEndpoint(&zbTempSensor);

  // 3. Zigbee-Stack als End Device starten
  Serial.println(F("[Zigbee] Starte Zigbee End Device..."));
  if (!Zigbee.begin(ZIGBEE_END_DEVICE, resetGedrueckt)) {
    Serial.println(F("[Zigbee] FEHLER: Zigbee konnte nicht initialisiert werden!"));
    while (1) delay(1000);
  }

  Serial.println(F("[Zigbee] Bereit und wartet auf Messungen."));
}

void loop() {
  unsigned long jetzt = millis();

  // Zyklische Messung und Übertragung
  if (jetzt - letzteMessung >= SENDE_INTERVALL || letzteMessung == 0) {
    letzteMessung = jetzt;

    float temp = dht.readTemperature();
    float hum  = dht.readHumidity();

    if (isnan(temp) || isnan(hum)) {
      Serial.println(F("[Sensor] FEHLER: Konnte keine Daten vom DHT22 einlesen! Verkabelung prüfen."));
      return;
    }

    Serial.printf("[Sensor] Temp: %.2f °C | Feuchte: %.1f %%\n", temp, hum);

    // Temperatur im Zigbee-Cluster aktualisieren und aktiv senden
    bool verbunden = Zigbee.connected();
    if (verbunden) {
      Serial.println(F("[Zigbee] Status: VERBUNDEN (Online)"));
      zbTempSensor.setTemperature(temp);
      zbTempSensor.report();
      Serial.println(F("[Zigbee] Messwert an Koordinator gesendet!"));
    } else {
      Serial.println(F("[Zigbee] Status: Suche Verbindung zum Koordinator..."));
    }
  }

  delay(100);
}
