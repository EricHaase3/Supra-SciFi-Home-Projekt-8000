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

// Sende-Intervall: 20 Sekunden zum Testen (später 10 Minuten: 600000 ms)
const unsigned long SENDE_INTERVALL = 20000; 

// ─── Globale Objekte: Temperatur (EP 10) & Feuchte (EP 11) ───────
DHT dht(DHTPIN, DHTTYPE);
ZigbeeTempSensor zbTempSensor = ZigbeeTempSensor(10); // EP10: Temperatur
ZigbeeTempSensor zbHumSensor  = ZigbeeTempSensor(11); // EP11: Luftfeuchte (Wert als Temperaturäquivalent)

unsigned long letzteMessung = 0;

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  dht.begin();

  // Prüfen, ob die BOOT-Taste beim Start gehalten wird -> Zigbee Factory-Reset
  bool resetGedrueckt = (digitalRead(BUTTON_PIN) == LOW);
  if (resetGedrueckt) {
    Serial.println(F("[Zigbee] Factory-Reset angefordert! Netzwerk-Daten werden gelöscht..."));
  }

  // 1. Temperatur-Cluster konfigurieren (Endpunkt 10)
  zbTempSensor.setManufacturerAndModel("SciFi-Home", "ESP32H2-DHT22");
  zbTempSensor.setMinMaxValue(-20.0, 60.0);
  zbTempSensor.setTolerance(0.1);

  // 2. Feuchtigkeits-Endpunkt konfigurieren (EP11, Wert als Temperatur-Cluster)
  zbHumSensor.setManufacturerAndModel("SciFi-Home", "ESP32H2-DHT22");
  zbHumSensor.setMinMaxValue(0.0, 100.0);
  zbHumSensor.setTolerance(0.5);

  // Endpunkte registrieren
  Zigbee.addEndpoint(&zbTempSensor);
  Zigbee.addEndpoint(&zbHumSensor);

  // 3. Zigbee-Stack starten
  Serial.println(F("[Zigbee] Starte Zigbee End Device mit Temp & Feuchte..."));
  if (!Zigbee.begin(ZIGBEE_END_DEVICE, resetGedrueckt)) {
    Serial.println(F("[Zigbee] FEHLER: Zigbee konnte nicht initialisiert werden!"));
    while (1) delay(1000);
  }

  // 4. Initiale Sensorwerte setzen
  delay(1500);
  float startTemp = dht.readTemperature();
  float startHum  = dht.readHumidity();
  if (!isnan(startTemp)) zbTempSensor.setTemperature(startTemp);
  if (!isnan(startHum))  zbHumSensor.setHumidity(startHum);

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
      Serial.println(F("[Sensor] FEHLER: Konnte keine Daten vom DHT22 einlesen!"));
      return;
    }

    Serial.printf("[Sensor] Temp: %.2f °C | Feuchte: %.1f %%\n", temp, hum);

    // Temperatur & Luftfeuchtigkeit an Z2M melden
    bool verbunden = Zigbee.connected();
    if (verbunden) {
      Serial.println(F("[Zigbee] Status: VERBUNDEN (Online)"));
      zbTempSensor.setTemperature(temp);
      zbTempSensor.report();
      // Luftfeuchte auf EP11 als Temperaturwert senden (Workaround)
      zbHumSensor.setTemperature(hum);
      zbHumSensor.report();
      Serial.println(F("[Zigbee] Messwerte (Temp & Feuchte) erfolgreich gemeldet!"));
    } else {
      Serial.println(F("[Zigbee] Status: Suche Verbindung zum Koordinator..."));
    }
  }

  delay(100);
}
