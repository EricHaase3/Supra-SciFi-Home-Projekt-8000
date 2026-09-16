#!/bin/bash
# Warte kurz, bis Desktop, Display und MQTT-Broker bereit sind
sleep 5

cd /home/sipi/Supra-SciFi-Home-Projekt-8000

# Virtuelle Umgebung aktivieren (falls vorhanden)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Python-Dashboard starten
python3 main.py
