/*******************************************************************************
 * ESP32-H2 Zigbee & DHT22 Raumklima-Sensor (SciFi-Home)
 * 
 * Hardware:
 *   - ESP32-H2-Zero (RISC-V 32-Bit, Native IEEE 802.15.4 / Zigbee 3.0)
 *   - DHT22 (AM2302) Temperatur- und Feuchtigkeitssensor an GPIO 0
 *   - Integrierter BOOT-Button an GPIO 9 für Zigbee Factory-Reset
 * 
 * HINWEIS LUFTFEUCHTE:
 *   Die ZigbeeHumidity-Klasse ist erst ab ESP32-Bibliothek Version 3.x verfügbar.
 *   Mit der aktuellen Version wird nur Temperatur per Zigbee übertragen.
 *   Update: Boardverwalter -> "esp32 by Espressif Systems" auf 3.x oder höher.
 ******************************************************************************/

#ifndef ZIGBEE_MODE_ED
#error "Bitte unter Tools -> Zigbee Mode -> 'Zigbee ED (End Device)' auswaehlen!"
#endif

#include "DHT.h"
#include "Zigbee.h"

// ─── Pin- und Hardware-Definitionen ──────────────────────────────
#define DHTPIN        0       // DHT22 Daten-Pin an GPIO 0
#define DHTTYPE       DHT22
#define BUTTON_PIN    9       // BOOT-Taste für Zigbee Factory-Reset

// Sende-Intervall in ms (20 Sek. zum Testen, später 600000 = 10 Min)
const unsigned long SENDE_INTERVALL = 20000;

// ─── Globale Objekte ─────────────────────────────────────────────
DHT dht(DHTPIN, DHTTYPE);
ZigbeeTempSensor zbTempSensor = ZigbeeTempSensor(10);

unsigned long letzteMessung = 0;

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  dht.begin();

  bool resetGedrueckt = (digitalRead(BUTTON_PIN) == LOW);
  if (resetGedrueckt) {
    Serial.println(F("[Zigbee] Factory-Reset wird durchgefuehrt..."));
  }

  // 1. Temperatur-Sensor konfigurieren
  zbTempSensor.setManufacturerAndModel("SciFi-Home", "ESP32H2-DHT22");
  zbTempSensor.setMinMaxValue(-20.0, 60.0);
  zbTempSensor.setTolerance(0.1);

  // 2. Endpunkt registrieren
  Zigbee.addEndpoint(&zbTempSensor);

  // 3. Zigbee starten
  Serial.println(F("[Zigbee] Starte Zigbee End Device (Temperatur)..."));
  if (!Zigbee.begin(ZIGBEE_END_DEVICE, resetGedrueckt)) {
    Serial.println(F("[Zigbee] FEHLER: Neustart..."));
    delay(2000);
    ESP.restart();
  }

  // 4. Startwert setzen
  delay(1500);
  float startTemp = dht.readTemperature();
  if (!isnan(startTemp)) {
    zbTempSensor.setTemperature(startTemp);
    Serial.printf("[Sensor] Startwert: %.2f C\n", startTemp);
  }

  Serial.println(F("[Zigbee] Bereit!"));
}

void loop() {
  unsigned long jetzt = millis();

  if (jetzt - letzteMessung >= SENDE_INTERVALL || letzteMessung == 0) {
    letzteMessung = jetzt;

    float temp = dht.readTemperature();
    float hum  = dht.readHumidity();

    if (isnan(temp) || isnan(hum)) {
      Serial.println(F("[Sensor] FEHLER: DHT22 nicht erreichbar!"));
      return;
    }

    // Ausgabe: Luftfeuchte wird lokal gemessen, aber noch nicht per Zigbee gesendet
    Serial.printf("[Sensor] Temp: %.2f C | Feuchte: %.1f %%\n", temp, hum);

    if (Zigbee.connected()) {
      Serial.println(F("[Zigbee] VERBUNDEN - Sende Temperatur..."));
      zbTempSensor.setTemperature(temp);
      zbTempSensor.report();
      Serial.println(F("[Zigbee] Temperatur gesendet!"));
    } else {
      Serial.println(F("[Zigbee] Suche Verbindung..."));
    }
  }

  delay(100);
}
