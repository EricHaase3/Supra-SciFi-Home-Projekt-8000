/*******************************************************************************
 * ESP32-H2 Zigbee & DHT22 Raumklima-Sensor (SciFi-Home)
 * 
 * Bibliothek: esp32 by Espressif Systems >= 3.3.x
 * Hardware:
 *   - ESP32-H2-Zero, DHT22 an GPIO 0, Reset-Button an GPIO 9
 ******************************************************************************/

#ifndef ZIGBEE_MODE_ED
#error "Bitte unter Tools -> Zigbee Mode -> 'Zigbee ED (End Device)' auswaehlen!"
#endif

#include "DHT.h"
#include "Zigbee.h"

// ─── Pin- und Hardware-Definitionen ──────────────────────────────
#define DHTPIN        0
#define DHTTYPE       DHT22
#define BUTTON_PIN    9

// Sende-Intervall (20 Sek. zum Testen, später 600000 = 10 Min)
const unsigned long SENDE_INTERVALL = 20000;

// ─── Zigbee-Endpunkte ────────────────────────────────────────────
DHT dht(DHTPIN, DHTTYPE);
ZigbeeTempSensor zbTempSensor = ZigbeeTempSensor(10); // EP10: Temperatur
ZigbeeHumidity   zbHumSensor  = ZigbeeHumidity(11);   // EP11: Luftfeuchte

unsigned long letzteMessung = 0;

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  dht.begin();

  bool resetGedrueckt = (digitalRead(BUTTON_PIN) == LOW);
  if (resetGedrueckt) {
    Serial.println(F("[Zigbee] Factory-Reset wird durchgefuehrt..."));
  }

  // 1. Temperatur-Sensor konfigurieren (EP10)
  zbTempSensor.setManufacturerAndModel("SciFi-Home", "ESP32H2-DHT22");
  zbTempSensor.setMinMaxValue(-20.0, 60.0);
  zbTempSensor.setTolerance(0.1);

  // 2. Feuchtigkeits-Sensor konfigurieren (EP11)
  zbHumSensor.setManufacturerAndModel("SciFi-Home", "ESP32H2-DHT22");
  zbHumSensor.setMinMaxValue(0.0, 100.0);
  zbHumSensor.setTolerance(0.5);

  // 3. Endpunkte registrieren
  Zigbee.addEndpoint(&zbTempSensor);
  Zigbee.addEndpoint(&zbHumSensor);

  // 4. Zigbee starten
  Serial.println(F("[Zigbee] Starte Zigbee End Device (Temp + Feuchte)..."));
  if (!Zigbee.begin(ZIGBEE_END_DEVICE, resetGedrueckt)) {
    Serial.println(F("[Zigbee] FEHLER: Neustart..."));
    delay(2000);
    ESP.restart();
  }

  // 5. Startwerte setzen
  delay(1500);
  float startTemp = dht.readTemperature();
  float startHum  = dht.readHumidity();
  if (!isnan(startTemp)) zbTempSensor.setTemperature(startTemp);
  if (!isnan(startHum))  zbHumSensor.setHumidity(startHum);
  Serial.printf("[Sensor] Startwerte: %.2f C | %.1f %%\n", startTemp, startHum);
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

    Serial.printf("[Sensor] Temp: %.2f C | Feuchte: %.1f %%\n", temp, hum);

    if (Zigbee.connected()) {
      Serial.println(F("[Zigbee] VERBUNDEN - Sende Temp & Feuchte..."));
      zbTempSensor.setTemperature(temp);
      zbTempSensor.report();
      zbHumSensor.setHumidity(hum);
      zbHumSensor.report();
      Serial.println(F("[Zigbee] Temp & Feuchte gesendet!"));
    } else {
      Serial.println(F("[Zigbee] Suche Verbindung..."));
    }
  }

  delay(100);
}
