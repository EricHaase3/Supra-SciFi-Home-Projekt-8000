import json
import os
import subprocess
import threading
import socket
from datetime import datetime
import paho.mqtt.client as mqtt
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.gridspec as gridspec
from matplotlib.widgets import Button
from database import init_db, save_measurement, get_last_values, get_history

# ─── Konfiguration ────────────────────────────────────────────────
MQTT_BROKER     = "localhost"
MQTT_BASE_TOPIC = "zigbee2mqtt/#"
UPDATE_INTERVAL = 1000  # UI-Aktualisierung alle 1 Sekunde (ms)

# Vordefinierte Sensor-Slots (für das 7 Zoll Display optimiert)
SLOTS = [
    {"id": "Temp_Hum_Jana",  "name": "Jana"},
    {"id": "Temp_Hum_David", "name": "David"},
    {"id": "Temp_Hum_Eric",  "name": "Eric"},
    {"id": "Temp_Hum_Dings", "name": "Dings"},
    {"id": "Temp_Hum_Balkon","name": "Balkon"},
    {"id": "SYSTEM_INFO",    "name": "Zentrale"},
]
SENSOR_SLOTS = [s for s in SLOTS if s["id"] != "SYSTEM_INFO"]

# Lokaler Zwischenspeicher für die Anzeige
sensor_daten = {
    slot["id"]: {"temp": None, "hum": None, "last_seen": None, "online": False}
    for slot in SENSOR_SLOTS
}

lock = threading.Lock()

# Tab-Zustand
aktiver_tab     = "live"           # "live" | "historie" | "steuerung"
historie_sensor = SENSOR_SLOTS[0]["id"]  # Welcher Sensor wird im Historien-Tab angezeigt?
historie_stunden = 24              # Zeitraum in Stunden

# Farben
FARBE_AKTIV   = "#89b4fa"  # Blau für aktiven Tab-Button
FARBE_INAKTIV = "#313244"  # Dunkelgrau für inaktive Tab-Buttons
FARBE_TEXT    = "#cdd6f4"

# ─── Hilfsfunktionen ──────────────────────────────────────────────
def lade_erinnerungen():
    """Lädt reminders.json aus dem Projektordner."""
    pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reminders.json")
    try:
        with open(pfad, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"erinnerungen": [], "notizen": []}

def get_hostname():
    try:
        return socket.gethostname()
    except Exception:
        return "unbekannt"

# ─── MQTT Callbacks ───────────────────────────────────────────────
def on_connect(client, userdata, flags, rc, properties=None):
    code = rc if isinstance(rc, int) else getattr(rc, "value", 0)
    if code == 0:
        print(f"[MQTT] Verbunden mit Broker {MQTT_BROKER}")
        client.subscribe(MQTT_BASE_TOPIC)
    else:
        print(f"[MQTT] Verbindung fehlgeschlagen, Code: {rc}")

def on_message(client, userdata, msg):
    try:
        topic_parts = msg.topic.split("/")
        if len(topic_parts) < 2:
            return
        sensor_name = topic_parts[1]
        if sensor_name == "bridge":
            return

        payload = json.loads(msg.payload.decode("utf-8"))

        temp = None
        for key in ("temperature", "local_temperature", "temp"):
            if key in payload and payload[key] is not None:
                temp = float(payload[key])
                break

        hum = None
        for key in ("humidity", "hum", "relative_humidity", "temperature_ep11", "temperature_2"):
            if key in payload and payload[key] is not None:
                hum = float(payload[key])
                break

        if temp is None and hum is None:
            return

        jetzt_zeit = datetime.now().strftime("%H:%M:%S")
        save_measurement(sensor_name=sensor_name, temperature=temp, humidity=hum)

        with lock:
            if sensor_name not in sensor_daten:
                sensor_daten[sensor_name] = {"temp": None, "hum": None, "last_seen": None, "online": True}
            if temp is not None:
                sensor_daten[sensor_name]["temp"] = temp
            if hum is not None:
                sensor_daten[sensor_name]["hum"] = hum
            sensor_daten[sensor_name]["last_seen"] = jetzt_zeit
            sensor_daten[sensor_name]["online"] = True

        t_str = f"{temp:.1f} °C" if temp is not None else "--.- °C"
        h_str = f"{hum:.1f} %"  if hum  is not None else "--.- %"
        print(f"[{jetzt_zeit}] [{sensor_name}] 💾 Gespeichert -> Temp: {t_str} | Feuchte: {h_str}")

    except json.JSONDecodeError:
        pass
    except Exception as e:
        print(f"[MQTT] Fehler: {e}")

def mqtt_thread():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, 1883, keepalive=60)
        client.loop_forever()
    except Exception as e:
        print(f"[MQTT] Verbindungsfehler: {e}")

# ─── Dashboard ────────────────────────────────────────────────────
def erstelle_dashboard():
    global aktiver_tab, historie_sensor, historie_stunden

    fig = plt.figure(figsize=(16, 9), facecolor="#0f0f17")

    # Vollbild
    mng = plt.get_current_fig_manager()
    try:
        mng.full_screen_toggle()
    except Exception:
        try:
            mng.window.attributes("-fullscreen", True)
        except Exception:
            pass

    # ── Layout: Titelzeile, Tab-Buttons, Content-Bereich ──────────
    gs_main = gridspec.GridSpec(
        3, 1,
        figure=fig,
        height_ratios=[0.06, 0.09, 0.85],
        hspace=0.0,
        left=0.01, right=0.99, top=0.99, bottom=0.01
    )

    ax_title   = fig.add_subplot(gs_main[0])   # Titelzeile
    ax_tabs    = fig.add_subplot(gs_main[1])   # Tab-Button-Leiste
    ax_content = fig.add_subplot(gs_main[2])   # Platzhalter – wird in draw_* ersetzt

    for ax in (ax_title, ax_tabs, ax_content):
        ax.set_facecolor("#0f0f17")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    # ── Titeltext ─────────────────────────────────────────────────
    uhrzeit_text = ax_title.text(
        0.5, 0.5, "",
        color=FARBE_TEXT, fontsize=11, fontweight="bold",
        ha="center", va="center", transform=ax_title.transAxes
    )

    # ── Tab-Buttons ───────────────────────────────────────────────
    btn_positionen = [
        (0.01,  0.05, 0.29, 0.90, "[ LIVE ]"),
        (0.355, 0.05, 0.29, 0.90, "[ HISTORIE ]"),
        (0.70,  0.05, 0.29, 0.90, "[ STEUERUNG ]"),
    ]

    tab_keys    = ["live", "historie", "steuerung"]
    tab_buttons = []

    content_axes = []  # Hält alle aktuell gezeichneten Content-Subaxes

    def clear_content():
        """Entfernt alle Content-Subaxes."""
        for a in content_axes:
            try:
                a.remove()
            except Exception:
                pass
        content_axes.clear()
        ax_content.set_visible(False)

    def update_tab_colors():
        for i, btn in enumerate(tab_buttons):
            if tab_keys[i] == aktiver_tab:
                btn.ax.set_facecolor(FARBE_AKTIV)
                btn.label.set_color("#1e1e2e")
                btn.label.set_fontweight("bold")
            else:
                btn.ax.set_facecolor(FARBE_INAKTIV)
                btn.label.set_color(FARBE_TEXT)
                btn.label.set_fontweight("normal")

    def switch_tab(key):
        global aktiver_tab
        aktiver_tab = key
        update_tab_colors()
        clear_content()
        if key == "live":
            draw_live()
        elif key == "historie":
            draw_historie()
        elif key == "steuerung":
            draw_steuerung()
        fig.canvas.draw_idle()

    for (x, y, w, h, label) in btn_positionen:
        btn_ax = fig.add_axes([x, 0.905 - h * 0.09, w, h * 0.09])
        btn = Button(btn_ax, label, color=FARBE_INAKTIV, hovercolor="#45475a")
        btn.label.set_color(FARBE_TEXT)
        btn.label.set_fontsize(9)
        tab_buttons.append(btn)

    tab_buttons[0].on_clicked(lambda e: switch_tab("live"))
    tab_buttons[1].on_clicked(lambda e: switch_tab("historie"))
    tab_buttons[2].on_clicked(lambda e: switch_tab("steuerung"))

    # ── Tab 1: LIVE ───────────────────────────────────────────────
    def draw_live():
        """Zeichnet das 2×3 Kachelraster auf dem Content-Bereich."""
        gs_live = gridspec.GridSpecFromSubplotSpec(
            2, 3, subplot_spec=gs_main[2],
            hspace=0.12, wspace=0.10
        )
        for i in range(6):
            row, col = divmod(i, 3)
            ax = fig.add_subplot(gs_live[row, col])
            content_axes.append(ax)

    def update_live(frame):
        if aktiver_tab != "live":
            return
        if not content_axes or len(content_axes) != 6:
            return

        with lock:
            aktuelle_daten = {k: dict(v) for k, v in sensor_daten.items()}

        for idx, slot in enumerate(SLOTS):
            ax = content_axes[idx]
            ax.cla()
            ax.set_facecolor("#181825")
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_color("#313244")
                spine.set_linewidth(1.5)

            slot_id   = slot["id"]
            slot_name = slot["name"]

            # Kachel 6: Systeminfo
            if slot_id == "SYSTEM_INFO":
                ax.spines[:].set_color("#89b4fa")
                ax.text(0.5, 0.85, ">> ZENTRALSTATION", color="#89b4fa",
                        fontsize=11, fontweight="bold", ha="center", va="center")
                ax.text(0.5, 0.64, f"Host: {get_hostname()}.local (RPi)", color="#a6adc8",
                        fontsize=9, ha="center", va="center")
                ax.text(0.5, 0.47, "Protokoll: Zigbee 3.0 / MQTT", color="#a6adc8",
                        fontsize=9, ha="center", va="center")
                ax.text(0.5, 0.30, "DB: SQLite (Dauerlogger)", color="#a6adc8",
                        fontsize=9, ha="center", va="center")
                ax.text(0.5, 0.12, "Status: SYSTEM BEREIT ●", color="#a6e3a1",
                        fontsize=10, fontweight="bold", ha="center", va="center")
                continue

            daten = aktuelle_daten.get(slot_id, {"temp": None, "hum": None, "last_seen": None, "online": False})
            temp  = daten.get("temp")
            hum   = daten.get("hum")
            last  = daten.get("last_seen")
            ist_online = (temp is not None or hum is not None)

            if ist_online:
                ax.spines[:].set_color("#45475a")
                status_text  = "● ONLINE"
                status_color = "#a6e3a1"
            else:
                status_text  = "○ BEREIT"
                status_color = "#6c7086"

            # Kachel-Header
            ax.text(0.05, 0.90, slot_name, color="#cdd6f4",
                    fontsize=11, fontweight="bold", ha="left", va="center")
            ax.text(0.95, 0.90, status_text, color=status_color,
                    fontsize=8, fontweight="bold", ha="right", va="center")
            ax.axhline(0.80, 0.03, 0.97, color="#313244", linewidth=1.2)

            # Temperatur (kleinere Schrift)
            if temp is not None:
                temp_str = f"{temp:.1f}"
                t_color  = "#f38ba8" if temp >= 24 else ("#89b4fa" if temp <= 19 else "#fab387")
            else:
                temp_str = "--.-"
                t_color  = "#585b70"

            # Luftfeuchte (kleinere Schrift)
            if hum is not None and hum > 0:
                hum_str = f"{hum:.1f}"
                h_color = "#89b4fa"
            else:
                hum_str = "--.-"
                h_color = "#585b70"

            # Werte – Schriftgröße von 32 auf 22 reduziert
            ax.text(0.28, 0.53, temp_str, color=t_color,
                    fontsize=22, fontweight="bold", ha="center", va="center")
            ax.text(0.28, 0.28, "Temp (°C)", color="#a6adc8",
                    fontsize=8, ha="center", va="center")

            ax.axvline(0.50, 0.20, 0.75, color="#313244", linewidth=1.2)

            ax.text(0.72, 0.53, hum_str, color=h_color,
                    fontsize=22, fontweight="bold", ha="center", va="center")
            ax.text(0.72, 0.28, "Feuchte (%)", color="#a6adc8",
                    fontsize=8, ha="center", va="center")

            last_text = f"Signal: {last}" if last else "Warte auf Funksignal..."
            ax.text(0.5, 0.10, last_text, color="#6c7086",
                    fontsize=7, ha="center", va="center")

    # ── Tab 2: HISTORIE ───────────────────────────────────────────
    def draw_historie():
        """Zeichnet den Historien-Tab: Sensor-Buttons + Liniendiagramm."""
        global historie_sensor, historie_stunden

        # Sensor-Auswahl-Buttons (obere Reihe)
        gs_hist = gridspec.GridSpecFromSubplotSpec(
            3, 1, subplot_spec=gs_main[2],
            height_ratios=[0.12, 0.44, 0.44],
            hspace=0.15
        )

        # Sensor-Buttons-Leiste
        ax_sens_bar = fig.add_subplot(gs_hist[0])
        ax_sens_bar.set_facecolor("#0f0f17")
        ax_sens_bar.set_xticks([])
        ax_sens_bar.set_yticks([])
        for spine in ax_sens_bar.spines.values():
            spine.set_visible(False)
        content_axes.append(ax_sens_bar)

        # Zeitraum-Buttons
        ax_time_bar_outer = fig.add_axes([0.74, 0.855, 0.25, 0.055])
        ax_time_bar_outer.set_visible(False)
        content_axes.append(ax_time_bar_outer)

        sensor_btns = []
        for i, slot in enumerate(SENSOR_SLOTS):
            bx = fig.add_axes([0.01 + i * 0.165, 0.855, 0.14, 0.055])
            is_active = slot["id"] == historie_sensor
            fc = FARBE_AKTIV if is_active else FARBE_INAKTIV
            btn = Button(bx, slot["name"], color=fc, hovercolor="#45475a")
            btn.label.set_fontsize(8)
            btn.label.set_color("#1e1e2e" if is_active else FARBE_TEXT)
            content_axes.append(bx)
            sensor_btns.append((btn, slot["id"]))

        def select_sensor(sid):
            global historie_sensor
            historie_sensor = sid
            clear_content()
            draw_historie()
            fig.canvas.draw_idle()

        for btn, sid in sensor_btns:
            btn.on_clicked(lambda e, s=sid: select_sensor(s))

        # Zeitraum-Buttons (24h / 7T / 30T)
        zeitraum_opts = [("24h", 24), ("7 Tage", 168), ("30 Tage", 720)]
        zeit_btns = []
        for i, (label, stunden) in enumerate(zeitraum_opts):
            bx = fig.add_axes([0.74 + i * 0.085, 0.855, 0.075, 0.055])
            is_active = stunden == historie_stunden
            fc = "#a6e3a1" if is_active else FARBE_INAKTIV
            btn = Button(bx, label, color=fc, hovercolor="#45475a")
            btn.label.set_fontsize(7)
            btn.label.set_color("#1e1e2e" if is_active else FARBE_TEXT)
            content_axes.append(bx)
            zeit_btns.append((btn, stunden))

        def select_zeitraum(std):
            global historie_stunden
            historie_stunden = std
            clear_content()
            draw_historie()
            fig.canvas.draw_idle()

        for btn, std in zeit_btns:
            btn.on_clicked(lambda e, s=std: select_zeitraum(s))

        # Diagramm-Axes: Temperatur oben, Feuchte unten
        ax_temp = fig.add_subplot(gs_hist[1])
        ax_hum  = fig.add_subplot(gs_hist[2])
        content_axes.extend([ax_temp, ax_hum])

        for ax in (ax_temp, ax_hum):
            ax.set_facecolor("#181825")
            ax.tick_params(colors="#aaaacc", labelsize=7)
            for spine in ax.spines.values():
                spine.set_color("#313244")
                spine.set_linewidth(1.0)

        # Daten laden
        ts_list, temp_list, hum_list = get_history(historie_sensor, historie_stunden)

        # Sensor-Anzeigename ermitteln
        sensor_label = next((s["name"] for s in SENSOR_SLOTS if s["id"] == historie_sensor), historie_sensor)
        stunden_label = f"{historie_stunden}h" if historie_stunden < 168 else (f"{historie_stunden // 24} Tage")

        if not ts_list:
            for ax, lbl in ((ax_temp, "Temperatur"), (ax_hum, "Luftfeuchte")):
                ax.text(0.5, 0.5, f"Keine Daten für \"{sensor_label}\" in den letzten {stunden_label}.",
                        color="#6c7086", fontsize=9, ha="center", va="center", transform=ax.transAxes)
        else:
            # X-Labels: nur Uhrzeit (oder Datum wenn > 24h)
            if len(ts_list) > 12:
                step = max(1, len(ts_list) // 8)
                x_ticks = list(range(0, len(ts_list), step))
                if historie_stunden <= 24:
                    x_labels = [ts_list[i][11:16] for i in x_ticks]  # HH:MM
                else:
                    x_labels = [ts_list[i][:10] + "\n" + ts_list[i][11:16] for i in x_ticks]
            else:
                x_ticks  = list(range(len(ts_list)))
                x_labels = [ts_list[i][11:16] for i in x_ticks]

            x = list(range(len(ts_list)))

            # Temperatur-Plot
            valid_t = [(i, v) for i, v in enumerate(temp_list) if v is not None]
            if valid_t:
                xi, yi = zip(*valid_t)
                ax_temp.plot(xi, yi, color="#f38ba8", linewidth=1.5, marker="o", markersize=2)
                ax_temp.fill_between(xi, yi, min(yi) - 0.5, alpha=0.12, color="#f38ba8")
                ax_temp.annotate(f"{yi[-1]:.1f} °C", xy=(xi[-1], yi[-1]),
                                 xytext=(4, 4), textcoords="offset points",
                                 color="#f38ba8", fontsize=8)
            ax_temp.set_ylabel("°C", color="#f38ba8", fontsize=8)
            ax_temp.set_title(f"Temperatur – {sensor_label} (letzte {stunden_label})",
                              color="#cdd6f4", fontsize=9, pad=4)
            ax_temp.set_xticks(x_ticks)
            ax_temp.set_xticklabels(x_labels, rotation=20, ha="right", fontsize=6)

            # Feuchte-Plot
            valid_h = [(i, v) for i, v in enumerate(hum_list) if v is not None]
            if valid_h:
                xi, yi = zip(*valid_h)
                ax_hum.plot(xi, yi, color="#89b4fa", linewidth=1.5, marker="s", markersize=2)
                ax_hum.fill_between(xi, yi, min(yi) - 0.5, alpha=0.12, color="#89b4fa")
                ax_hum.annotate(f"{yi[-1]:.1f} %", xy=(xi[-1], yi[-1]),
                                xytext=(4, 4), textcoords="offset points",
                                color="#89b4fa", fontsize=8)
            ax_hum.set_ylabel("%", color="#89b4fa", fontsize=8)
            ax_hum.set_title(f"Luftfeuchte – {sensor_label} (letzte {stunden_label})",
                             color="#cdd6f4", fontsize=9, pad=4)
            ax_hum.set_xticks(x_ticks)
            ax_hum.set_xticklabels(x_labels, rotation=20, ha="right", fontsize=6)

    # ── Tab 3: STEUERUNG ──────────────────────────────────────────
    def draw_steuerung():
        """Zeichnet den Steuerungs-Tab: Systeminfo + Erinnerungen + Buttons."""
        gs_ctrl = gridspec.GridSpecFromSubplotSpec(
            1, 2, subplot_spec=gs_main[2],
            wspace=0.06
        )

        ax_info = fig.add_subplot(gs_ctrl[0])
        ax_memo = fig.add_subplot(gs_ctrl[1])
        content_axes.extend([ax_info, ax_memo])

        for ax in (ax_info, ax_memo):
            ax.set_facecolor("#181825")
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_color("#313244")
                spine.set_linewidth(1.5)

        # ── Linke Seite: Systeminfo + Steuer-Buttons ──
        ax_info.text(0.5, 0.93, ">> ZENTRALSTATION", color="#89b4fa",
                     fontsize=12, fontweight="bold", ha="center", va="center")
        ax_info.axhline(0.86, 0.05, 0.95, color="#313244", linewidth=1.2)

        infos = [
            ("Host",       f"{get_hostname()}.local"),
            ("IP",         "192.168.2.160"),
            ("Protokoll",  "Zigbee 3.0 / MQTT"),
            ("Datenbank",  "SQLite (data/sensor_history.db)"),
            ("Broker",     "Mosquitto @ localhost:1883"),
        ]
        for i, (key, val) in enumerate(infos):
            y = 0.77 - i * 0.10
            ax_info.text(0.07, y, f"{key}:", color="#6c7086", fontsize=8, ha="left", va="center")
            ax_info.text(0.40, y, val, color="#a6adc8", fontsize=8, ha="left", va="center")

        ax_info.axhline(0.27, 0.05, 0.95, color="#313244", linewidth=1.2)
        ax_info.text(0.5, 0.22, "SYSTEMSTEUERUNG", color="#6c7086",
                     fontsize=7, ha="center", va="center")

        # Shutdown-Button
        bx_shutdown = fig.add_axes([0.08, 0.07, 0.17, 0.10])
        btn_shutdown = Button(bx_shutdown, "[X]  Herunterfahren", color="#45475a", hovercolor="#f38ba8")
        btn_shutdown.label.set_fontsize(8)
        btn_shutdown.label.set_color(FARBE_TEXT)
        content_axes.append(bx_shutdown)

        # Neustart-Button
        bx_restart = fig.add_axes([0.27, 0.07, 0.17, 0.10])
        btn_restart = Button(bx_restart, "[>]  Neustart", color="#45475a", hovercolor="#a6e3a1")
        btn_restart.label.set_fontsize(8)
        btn_restart.label.set_color(FARBE_TEXT)
        content_axes.append(bx_restart)

        def do_shutdown(e):
            print("[System] Fahre Raspberry Pi herunter...")
            subprocess.Popen(["sudo", "shutdown", "-h", "now"])

        def do_restart(e):
            print("[System] Starte Dashboard neu...")
            python = __import__("sys").executable
            os.execv(python, [python] + __import__("sys").argv)

        btn_shutdown.on_clicked(do_shutdown)
        btn_restart.on_clicked(do_restart)

        # ── Rechte Seite: Erinnerungen & Notizen ──
        erinnerungen_data = lade_erinnerungen()
        erinnerungen = erinnerungen_data.get("erinnerungen", [])
        notizen      = erinnerungen_data.get("notizen", [])

        ax_memo.text(0.5, 0.93, "-- ERINNERUNGEN & NOTIZEN --", color="#fab387",
                     fontsize=12, fontweight="bold", ha="center", va="center")
        ax_memo.axhline(0.86, 0.05, 0.95, color="#313244", linewidth=1.2)

        y = 0.80
        ax_memo.text(0.07, y, "Wochentag", color="#6c7086", fontsize=8,
                     fontweight="bold", ha="left", va="center")
        ax_memo.text(0.45, y, "Aufgabe", color="#6c7086", fontsize=8,
                     fontweight="bold", ha="left", va="center")
        y -= 0.07

        for erinnerung in erinnerungen:
            if y < 0.45:
                break
            ax_memo.text(0.07, y, erinnerung.get("wochentag", ""),
                         color="#cdd6f4", fontsize=9, ha="left", va="center")
            ax_memo.text(0.45, y, erinnerung.get("text", ""),
                         color="#a6adc8", fontsize=9, ha="left", va="center")
            y -= 0.09

        if notizen:
            ax_memo.axhline(y - 0.03, 0.05, 0.95, color="#313244", linewidth=1.0)
            y -= 0.10
            ax_memo.text(0.5, y, "-- Hinweise --", color="#6c7086", fontsize=8,
                         fontweight="bold", ha="center", va="center")
            y -= 0.09
            for notiz in notizen:
                if y < 0.05:
                    break
                ax_memo.text(0.07, y, f"• {notiz}", color="#a6adc8", fontsize=8,
                             ha="left", va="center")
                y -= 0.09

    # ── Animations-Callback ───────────────────────────────────────
    def animate(frame):
        jetzt = datetime.now().strftime("%d.%m.%Y  •  %H:%M:%S")
        uhrzeit_text.set_text(f">> SUPRA SCI-FI HOME 8000  |  {jetzt}")

        if aktiver_tab == "live":
            update_live(frame)
        # Historie und Steuerung aktualisieren sich nur bei Tab-Wechsel

    # Startzustand: Live-Tab
    draw_live()
    update_tab_colors()

    fig.canvas.mpl_connect("close_event", lambda event: __import__("sys").exit(0))
    ani = animation.FuncAnimation(fig, animate, interval=UPDATE_INTERVAL, cache_frame_data=False)
    plt.show()

# ─── Start ────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()

    # Letzte bekannte Werte aus der Datenbank vorausfüllen
    vorwerte = get_last_values()
    for sensor_id, werte in vorwerte.items():
        if sensor_id in sensor_daten:
            sensor_daten[sensor_id].update(werte)
        else:
            sensor_daten[sensor_id] = werte
    if vorwerte:
        print(f"[DB] {len(vorwerte)} Sensor(en) mit letzten Werten aus der Datenbank vorgeladen.")

    t = threading.Thread(target=mqtt_thread, daemon=True)
    t.start()

    try:
        erstelle_dashboard()
    except KeyboardInterrupt:
        print("\n[System] Programm durch Benutzer (Ctrl+C) beendet.")
        __import__("sys").exit(0)