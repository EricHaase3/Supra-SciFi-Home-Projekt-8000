#ifndef ZIGBEE_MODE_ED
#define ZIGBEE_MODE_ED
#endif

#include "Zigbee.h"
#include <DHT.h>

// ─── Pin & Sensor Konfiguration ──────────────────────────────────
#define DHTPIN        0        // GPIO 0 für DHT22 Datenleitung
#define DHTTYPE       DHT22    // DHT 22 (AM2302)
#define BOOT_BUTTON   9        // BOOT-Taste am ESP32-H2-Zero

#define TEMP_SENSOR_ENDPOINT_NUMBER 10

// Sende-Intervall in Millisekunden (alle 20 Sekunden)
const unsigned long SENDE_INTERVALL = 20000; 
unsigned long letzteMessung = 0;

DHT dht(DHTPIN, DHTTYPE);

// Zigbee Endpunkt für Temperatursensor
ZigbeeTempSensor zbTempSensor = ZigbeeTempSensor(TEMP_SENSOR_ENDPOINT_NUMBER);

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println("\n==========================================");
  Serial.println("   ESP32-H2 Zigbee DHT22 Sensor Start    ");
  Serial.println("==========================================");
  Serial.printf("[Config] DHT22 verbunden an GPIO %d\n", DHTPIN);

  pinMode(BOOT_BUTTON, INPUT_PULLUP);
  dht.begin();

  // 1. Zigbee-Sensor konfigurieren (Bereiche & Bezeichnungen)
  zbTempSensor.setManufacturerAndModel("SciFi-Home", "ESP32H2-DHT22");
  zbTempSensor.setMinMaxValue(-20, 60); // Temperaturbereich in °C
  zbTempSensor.setTolerance(0.5);       // Mindeständerung für automatisches Reporting

  // 2. Endpunkt bei Zigbee registrieren
  Zigbee.addEndpoint(&zbTempSensor);

  // 3. Prüfen, ob BOOT-Taste gedrückt ist (Factory Reset erzwingen)
  bool resetGedrueckt = (digitalRead(BOOT_BUTTON) == LOW);
  if (resetGedrueckt) {
    Serial.println("[Zigbee] BOOT-Taste gedrückt -> NVRAM Reset & neuer Pairing-Modus!");
  }

  // 4. Zigbee starten
  Serial.println("[Zigbee] Starte Zigbee Stack...");
  if (!Zigbee.begin(ZIGBEE_END_DEVICE, resetGedrueckt)) {
    Serial.println("[Zigbee] FEHLER beim Initialisieren von Zigbee!");
    while (1) {
      delay(1000);
    }
  }

  // 5. Netzwerksuche (Pairing) aktiv starten
  Serial.println("[Zigbee] Starte Netzwerksuche nach Koordinator...");
  Zigbee.searchNetwork();
}

void loop() {
  unsigned long jetzt = millis();

  // Alle X Sekunden Status & Sensor auslesen
  if (jetzt - letzteMessung >= SENDE_INTERVALL || letzteMessung == 0) {
    letzteMessung = jetzt;

    // Verbindungsstatus prüfen
    bool verbunden = Zigbee.connected();
    Serial.printf("\n[Zigbee] Status: %s\n", verbunden ? "VERBUNDEN (Online)" : "SUCHE NETZWERK...");

    if (!verbunden) {
      // Falls noch nicht verbunden, Suche wiederholen
      Zigbee.searchNetwork();
    }

    float temp = dht.readTemperature();
    float hum  = dht.readHumidity();

    if (isnan(temp)) {
      Serial.println("[DHT22] Fehler: Konnte Temperatur nicht lesen!");
    } else {
      Serial.printf("[Sensor] Temp: %.2f °C | Feuchte: %.1f %%\n", temp, isnan(hum) ? 0.0 : hum);

      if (verbunden) {
        zbTempSensor.setTemperature(temp);
        zbTempSensor.report();
        Serial.println("[Zigbee] Messwert erfolgreich gesendet!");
      }
    }
  }

  delay(200);
}
