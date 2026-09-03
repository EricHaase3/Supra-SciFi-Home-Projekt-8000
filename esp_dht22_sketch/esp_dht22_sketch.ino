/*******************************************************************************
 * ESP32-H2 Zigbee & DHT22 Raumklima-Sensor (SciFi-Home)
 * 
 * Bibliothek: esp32 by Espressif Systems >= 3.3.x
 * Hardware: ESP32-H2-Zero, DHT22 an GPIO 0, Reset-Button an GPIO 9
 * 
 * BATTERIE-BETRIEB: Sleepy End Device (Deep Sleep für 10 Minuten)
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

#define uS_TO_S_FACTOR 1000000ULL 
#define TIME_TO_SLEEP  600         /* 10 Minuten = 600 Sekunden */
#define REPORT_TIMEOUT 2000        /* Timeout für Bestätigung vom Koordinator in ms */

// ─── Zigbee-Endpunkt (EP10 enthält Temp UND Feuchte) ─────────────
DHT dht(DHTPIN, DHTTYPE);
ZigbeeTempSensor zbTempSensor = ZigbeeTempSensor(10);

uint8_t dataToSend = 2; // Wir senden Temp + Feuchte = 2 Attribute
bool resend = false;

// ─── Callbacks ────────────────────────────────────────────────────
void onGlobalResponse(zb_cmd_type_t command, esp_zb_zcl_status_t status, uint8_t endpoint, uint16_t cluster) {
  if ((command == ZB_CMD_REPORT_ATTRIBUTE) && (endpoint == 10)) {
    switch (status) {
      case ESP_ZB_ZCL_STATUS_SUCCESS: dataToSend--; break;
      case ESP_ZB_ZCL_STATUS_FAIL:    resend = true; break;
      default:                        break;
    }
  }
}

// ─── Messen & Schlafen (Task) ─────────────────────────────────────
static void measureAndSleep(void *arg) {
  // Kurze Pause, da der DHT22 Sensor nach dem Strom-Einschalten etwas Zeit braucht
  delay(2000);
  
  // Messwerte lesen
  float temp = dht.readTemperature();
  float hum  = dht.readHumidity();

  if (isnan(temp) || isnan(hum)) {
    Serial.println(F("[Sensor] FEHLER: DHT22 nicht erreichbar!"));
    // Gehe trotzdem schlafen, probiere es beim nächsten Aufwachen wieder
  } else {
    Serial.printf("[Sensor] Temp: %.2f C | Feuchte: %.1f %%\n", temp, hum);
    
    // Zigbee Attribute setzen
    zbTempSensor.setTemperature(temp);
    zbTempSensor.setHumidity(hum);
    
    // Senden
    zbTempSensor.report(); 
    Serial.println(F("[Zigbee] Senden gestartet..."));
    
    unsigned long startTime = millis();
    int tries = 0;
    const int maxTries = 3;
    
    // Warten auf ACK vom Koordinator (Zigbee2MQTT)
    while (dataToSend != 0 && tries < maxTries) {
      if (resend) {
        Serial.println("Fehler beim Senden! Neuer Versuch...");
        resend = false;
        dataToSend = 2;
        zbTempSensor.report();
      }
      if (millis() - startTime >= REPORT_TIMEOUT) {
        Serial.println("\nTimeout! Neuer Versuch...");
        dataToSend = 2;
        zbTempSensor.report();
        startTime = millis();
        tries++;
      }
      delay(50);
    }
    
    if (dataToSend == 0) {
      Serial.println(F("[Zigbee] Erfolgreich gesendet!"));
    } else {
      Serial.println(F("[Zigbee] Senden fehlgeschlagen, gebe auf."));
    }
  }

  // Ab in den Deep Sleep!
  Serial.println(F("[System] Gehe in Deep Sleep für 10 Minuten..."));
  esp_deep_sleep_start();
}

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  dht.begin();

  // Timer für Wakeup konfigurieren (10 Minuten)
  esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP * uS_TO_S_FACTOR);

  // Check Reset Button
  bool resetGedrueckt = (digitalRead(BUTTON_PIN) == LOW);
  if (resetGedrueckt) {
    Serial.println(F("[Zigbee] Factory-Reset wird durchgefuehrt..."));
    delay(1000);
  }

  // 1. Sensor konfigurieren
  zbTempSensor.setManufacturerAndModel("SciFi-Home", "ESP32H2-DHT22");
  zbTempSensor.setMinMaxValue(-20.0, 60.0);
  zbTempSensor.setTolerance(0.1);
  
  // Power Source: Batterie (Dummy-Werte: 100%, 3.3V, kann später durch echten ADC ersetzt werden)
  zbTempSensor.setPowerSource(ZB_POWER_SOURCE_BATTERY, 100, 33); 

  // Feuchtigkeits-Support
  zbTempSensor.addHumiditySensor(0.0, 100.0, 0.5);

  // Callback für Bestätigungen
  Zigbee.onGlobalDefaultResponse(onGlobalResponse);

  // 2. Endpunkt registrieren
  Zigbee.addEndpoint(&zbTempSensor);

  // 3. Zigbee End Device Config für Sleepy Devices (Längeres Timeout, Keep Alive)
  esp_zb_cfg_t zigbeeConfig = ZIGBEE_DEFAULT_ED_CONFIG();
  zigbeeConfig.nwk_cfg.zed_cfg.keep_alive = 10000;
  Zigbee.setTimeout(10000); // 10 Sekunden Timeout für den Begin-Vorgang

  // 4. Zigbee starten
  Serial.println(F("[Zigbee] Starte Zigbee (Sleepy End Device)..."));
  if (!Zigbee.begin(&zigbeeConfig, resetGedrueckt)) {
    Serial.println(F("[Zigbee] FEHLER: Konnte nicht starten, Neustart..."));
    delay(2000);
    ESP.restart();
  }

  Serial.println(F("[Zigbee] Warte auf Verbindung zum Netzwerk..."));
  while (!Zigbee.connected()) {
    delay(100);
  }
  Serial.println(F("[Zigbee] Verbunden!"));

  // 5. Messung und Deep Sleep in separatem Task starten
  xTaskCreate(measureAndSleep, "measure_sleep_task", 4096, NULL, 10, NULL);
}

void loop() {
  // Während der measureAndSleep Task läuft (dauert ca. 2-5 Sekunden),
  // überwachen wir hier den Reset-Button, falls der Nutzer
  // den Sensor während des kurzen Wach-Zyklus zurücksetzen will.
  
  if (digitalRead(BUTTON_PIN) == LOW) {
    delay(100);
    unsigned long startTime = millis();
    while (digitalRead(BUTTON_PIN) == LOW) {
      delay(50);
      if ((millis() - startTime) > 5000) { // 5 Sek gedrückt halten
        Serial.println("Setze Zigbee zurück...");
        Zigbee.factoryReset();
      }
    }
  }
  delay(100);
}
