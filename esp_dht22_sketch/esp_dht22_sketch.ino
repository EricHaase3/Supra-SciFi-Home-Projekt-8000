/*******************************************************************************
 * ESP32-H2 Zigbee & DHT22 Raumklima-Sensor (SciFi-Home)
 * 
 * Bibliothek: esp32 by Espressif Systems >= 3.3.x
 * Hardware: ESP32-H2-Zero, DHT22 an GPIO 0, Reset-Button an GPIO 9
 * 
 * WICHTIG: ZigbeeTempSensor enthält BEIDE Cluster (Temp + Feuchte) auf EP10!
 ******************************************************************************/

#ifndef ZIGBEE_MODE_ED
#error "Bitte unter Tools -> Zigbee Mode -> 'Zigbee ED (End Device)' auswaehlen!"
#endif

#include "DHT.h"
#include "Zigbee.h"

// ─── Konfiguration ────────────────────────────────────────────────
#define DHTPIN        0
#define DHTTYPE       DHT22
#define BUTTON_PIN    9

// Sende-Intervall (20 Sek. zum Testen, später 600000 = 10 Min)
const unsigned long SENDE_INTERVALL = 20000;

// ─── Zigbee-Endpunkt (EP10 enthält Temp UND Feuchte) ─────────────
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

  // 1. Sensor konfigurieren (EP10 = Temp + Feuchte Cluster)
  zbTempSensor.setManufacturerAndModel("SciFi-Home", "ESP32H2-DHT22");
  zbTempSensor.setMinMaxValue(-20.0, 60.0);
  zbTempSensor.setTolerance(0.1);
  
  // WICHTIG: Feuchtigkeits-Support auf diesem Endpunkt explizit aktivieren!
  // Parameter: min(0%), max(100%), toleranz(0.5%)
  zbTempSensor.addHumiditySensor(0.0, 100.0, 0.5);

  // 2. Endpunkt registrieren
  Zigbee.addEndpoint(&zbTempSensor);

  // 3. Zigbee starten
  Serial.println(F("[Zigbee] Starte Zigbee End Device (Temp + Feuchte auf EP10)..."));
  if (!Zigbee.begin(ZIGBEE_END_DEVICE, resetGedrueckt)) {
    Serial.println(F("[Zigbee] FEHLER: Neustart..."));
    delay(2000);
    ESP.restart();
  }

  // 4. Startwerte setzen
  delay(1500);
  float startTemp = dht.readTemperature();
  float startHum  = dht.readHumidity();
  if (!isnan(startTemp)) zbTempSensor.setTemperature(startTemp);
  if (!isnan(startHum))  zbTempSensor.setHumidity(startHum);
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
      zbTempSensor.setHumidity(hum);   // Feuchte auf DEMSELBEN Endpunkt!
      zbTempSensor.report();
      Serial.println(F("[Zigbee] Temp & Feuchte gesendet!"));
    } else {
      Serial.println(F("[Zigbee] Suche Verbindung..."));
    }
  }

  delay(100);
}
