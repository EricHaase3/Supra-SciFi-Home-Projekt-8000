#!/bin/bash
# Skript zum Einrichten des automatischen Starts auf dem Raspberry Pi

AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/dashboard.desktop"
PROJECT_DIR="/home/sipi/Supra-SciFi-Home-Projekt-8000"

echo "Richte Autostart für das Smarthome-Dashboard ein..."

# Ausführungsrechte für das Startskript setzen
chmod +x "$PROJECT_DIR/start_dashboard.sh"

# Zielordner anlegen falls noch nicht vorhanden
mkdir -p "$AUTOSTART_DIR"

# .desktop-Eintrag für die grafische Oberfläche erstellen
cat << EOF > "$DESKTOP_FILE"
[Desktop Entry]
Type=Application
Name=Smarthome Dashboard
Exec=/bin/bash $PROJECT_DIR/start_dashboard.sh
Terminal=false
EOF

echo "✓ Autostart-Eintrag erfolgreich erstellt: $DESKTOP_FILE"
echo "Das Dashboard startet nun bei jedem Boot automatisch auf dem angeschlossenen Display!"
