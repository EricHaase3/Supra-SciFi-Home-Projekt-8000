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
import matplotlib.patches as mpatches
from matplotlib.widgets import Button
from database import init_db, save_measurement, get_last_values, get_history

# ─── Konfiguration ─────────────────────────────────────────────────
MQTT_BROKER     = "localhost"
MQTT_BASE_TOPIC = "zigbee2mqtt/#"
UPDATE_INTERVAL = 1000  # ms

SLOTS = [
    {"id": "Temp_Hum_Jana",   "name": "Jana"},
    {"id": "Temp_Hum_David",  "name": "David"},
    {"id": "Temp_Hum_Eric",   "name": "Eric"},
    {"id": "Temp_Hum_Dings",  "name": "Dings"},
    {"id": "Temp_Hum_Balkon", "name": "Balkon"},
    {"id": "SYSTEM_INFO",     "name": "Zentrale"},
]
SENSOR_SLOTS = [s for s in SLOTS if s["id"] != "SYSTEM_INFO"]

sensor_daten = {
    slot["id"]: {"temp": None, "hum": None, "last_seen": None, "online": False}
    for slot in SENSOR_SLOTS
}
lock = threading.Lock()

# Tab-Zustand
aktiver_tab      = "live"
historie_sensor  = SENSOR_SLOTS[0]["id"]
historie_stunden = 24

# ─── Layout-Konstanten (alle in absoluten Figure-Koordinaten 0-1) ──
#
#  ┌──────────────────────────────────────────────────────────────┐
#  │  TITELZEILE                                   y=0.955-0.995  │
#  ├──────────────────────────────────────────────────────────────┤
#  │  [ LIVE ]        [ HISTORIE ]      [ STEUERUNG ]  y=0.892   │
#  ├──────────────────────────────────────────────────────────────┤
#  │                                                              │
#  │  CONTENT-BEREICH                            y=0.010-0.882   │
#  │                                                              │
#  └──────────────────────────────────────────────────────────────┘
#
TITLE_Y     = 0.955
TITLE_H     = 0.040
TAB_Y       = 0.893   # Unterkante Tab-Buttons
TAB_H       = 0.052   # Hoehe Tab-Buttons
TAB_TOP     = TAB_Y + TAB_H  # 0.945
CONTENT_TOP = TAB_Y - 0.010  # 0.883
CONTENT_BOT = 0.010

# Tab-Button-Breiten (3 gleichmaessige Buttons)
TAB_W       = 0.322
TAB_GAP     = 0.007
TAB_X       = [0.010, 0.010 + TAB_W + TAB_GAP, 0.010 + 2*(TAB_W + TAB_GAP)]

# Farben
BG_DEEP       = "#0a0a12"
BG_CARD       = "#181825"
BG_BORDER     = "#313244"
C_TEXT        = "#cdd6f4"
C_MUTED       = "#6c7086"
C_SUBTLE      = "#a6adc8"
C_GREEN       = "#a6e3a1"
C_BLUE        = "#89b4fa"
C_RED         = "#f38ba8"
C_ORANGE      = "#fab387"
C_CYAN        = "#89dceb"
C_YELLOW      = "#f9e2af"

TAB_COLORS = {
    "live":       {"active": C_GREEN,  "inactive": "#1e1e2e"},
    "historie":   {"active": C_CYAN,   "inactive": "#1e1e2e"},
    "steuerung":  {"active": C_YELLOW, "inactive": "#1e1e2e"},
}

# ─── Hilfsfunktionen ───────────────────────────────────────────────
def lade_erinnerungen():
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
        return "sipi"

# ─── MQTT ──────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc, properties=None):
    code = rc if isinstance(rc, int) else getattr(rc, "value", 0)
    if code == 0:
        print(f"[MQTT] Verbunden mit Broker {MQTT_BROKER}")
        client.subscribe(MQTT_BASE_TOPIC)
    else:
        print(f"[MQTT] Verbindung fehlgeschlagen, Code: {rc}")

def on_message(client, userdata, msg):
    try:
        parts = msg.topic.split("/")
        if len(parts) < 2:
            return
        sensor_name = parts[1]
        if sensor_name == "bridge":
            return

        payload = json.loads(msg.payload.decode("utf-8"))

        temp = None
        for key in ("temperature", "local_temperature", "temp"):
            if key in payload and payload[key] is not None:
                temp = float(payload[key]); break

        hum = None
        for key in ("humidity", "hum", "relative_humidity", "temperature_ep11", "temperature_2"):
            if key in payload and payload[key] is not None:
                hum = float(payload[key]); break

        if temp is None and hum is None:
            return

        jetzt = datetime.now().strftime("%H:%M:%S")
        save_measurement(sensor_name=sensor_name, temperature=temp, humidity=hum)

        with lock:
            if sensor_name not in sensor_daten:
                sensor_daten[sensor_name] = {"temp": None, "hum": None, "last_seen": None, "online": True}
            if temp is not None:
                sensor_daten[sensor_name]["temp"] = temp
            if hum is not None:
                sensor_daten[sensor_name]["hum"] = hum
            sensor_daten[sensor_name]["last_seen"] = jetzt
            sensor_daten[sensor_name]["online"] = True

        t_str = f"{temp:.1f} C" if temp is not None else "--.- C"
        h_str = f"{hum:.1f} %" if hum is not None else "--.- %"
        print(f"[{jetzt}] [{sensor_name}] Gespeichert -> Temp: {t_str} | Feuchte: {h_str}")

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

# ─── Dashboard ─────────────────────────────────────────────────────
def erstelle_dashboard():
    global aktiver_tab, historie_sensor, historie_stunden

    fig = plt.figure(figsize=(16, 9), facecolor=BG_DEEP)

    # Vollbild
    mng = plt.get_current_fig_manager()
    try:
        mng.full_screen_toggle()
    except Exception:
        try:
            mng.window.attributes("-fullscreen", True)
        except Exception:
            pass

    # ── Titelzeile (feste Axes) ─────────────────────────────────────
    ax_title = fig.add_axes([0.0, TITLE_Y, 1.0, TITLE_H])
    ax_title.set_facecolor(BG_DEEP)
    ax_title.set_xticks([]); ax_title.set_yticks([])
    for sp in ax_title.spines.values():
        sp.set_visible(False)
    uhr_text = ax_title.text(
        0.5, 0.5, "",
        color=C_TEXT, fontsize=12, fontweight="bold",
        ha="center", va="center", transform=ax_title.transAxes
    )

    # ── Tab-Buttons ─────────────────────────────────────────────────
    tab_keys   = ["live", "historie", "steuerung"]
    tab_labels = ["  LIVE  ", "  HISTORIE  ", "  STEUERUNG  "]
    tab_btns   = []

    for i, (key, label) in enumerate(zip(tab_keys, tab_labels)):
        bax = fig.add_axes([TAB_X[i], TAB_Y, TAB_W, TAB_H])
        color_inactive = TAB_COLORS[key]["inactive"]
        btn = Button(bax, label, color=color_inactive, hovercolor=BG_BORDER)
        btn.label.set_fontsize(10)
        btn.label.set_fontweight("normal")
        btn.label.set_color(C_MUTED)
        tab_btns.append(btn)

    # Trennlinie unter Tab-Buttons
    ax_sep = fig.add_axes([0.0, TAB_Y - 0.002, 1.0, 0.003])
    ax_sep.set_facecolor(BG_BORDER)
    ax_sep.set_xticks([]); ax_sep.set_yticks([])
    for sp in ax_sep.spines.values():
        sp.set_visible(False)

    # ── Content-Verwaltung ─────────────────────────────────────────
    content_axes   = []  # Alle axes des aktuellen Tabs
    content_btns   = []  # Alle Button-Objekte des aktuellen Tabs (Referenz halten!)

    def clear_content():
        for a in content_axes:
            try:
                a.remove()
            except Exception:
                pass
        content_axes.clear()
        content_btns.clear()

    def update_tab_btns():
        for i, (key, btn) in enumerate(zip(tab_keys, tab_btns)):
            if key == aktiver_tab:
                col = TAB_COLORS[key]["active"]
                btn.ax.set_facecolor(col)
                btn.label.set_color(BG_DEEP)
                btn.label.set_fontweight("bold")
                btn.label.set_fontsize(11)
            else:
                btn.ax.set_facecolor(TAB_COLORS[key]["inactive"])
                btn.label.set_color(C_MUTED)
                btn.label.set_fontweight("normal")
                btn.label.set_fontsize(10)

    def switch_tab(key):
        global aktiver_tab
        aktiver_tab = key
        update_tab_btns()
        clear_content()
        if key == "live":
            build_live()
        elif key == "historie":
            build_historie()
        elif key == "steuerung":
            build_steuerung()
        fig.canvas.draw_idle()

    tab_btns[0].on_clicked(lambda e: switch_tab("live"))
    tab_btns[1].on_clicked(lambda e: switch_tab("historie"))
    tab_btns[2].on_clicked(lambda e: switch_tab("steuerung"))

    # ══════════════════════════════════════════════════════════════
    # TAB 1: LIVE – 2x3 Kachelraster
    # ══════════════════════════════════════════════════════════════
    def build_live():
        # Content-Bereich aufteilen: 2 Zeilen x 3 Spalten
        # x: 0.010 bis 0.990 → 3 Spalten mit kleinen Luecken
        col_w = (0.980 - 2*0.008) / 3   # ~0.321
        row_h = (CONTENT_TOP - CONTENT_BOT - 0.008) / 2  # ~0.432
        positions = []
        for row in range(2):
            for col in range(3):
                x = 0.010 + col * (col_w + 0.008)
                y = CONTENT_TOP - (row + 1) * row_h - row * 0.008
                positions.append([x, y, col_w, row_h])

        for pos in positions:
            ax = fig.add_axes(pos)
            ax.set_facecolor(BG_CARD)
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_color(BG_BORDER)
                sp.set_linewidth(1.5)
            content_axes.append(ax)

    def update_live():
        if aktiver_tab != "live" or len(content_axes) != 6:
            return
        with lock:
            snap = {k: dict(v) for k, v in sensor_daten.items()}

        for idx, slot in enumerate(SLOTS):
            ax = content_axes[idx]
            ax.cla()
            ax.set_facecolor(BG_CARD)
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_color(BG_BORDER)
                sp.set_linewidth(1.5)

            sid   = slot["id"]
            sname = slot["name"]

            # Kachel 6: Systeminfo
            if sid == "SYSTEM_INFO":
                ax.spines[:].set_color(C_BLUE)
                ax.spines[:].set_linewidth(2.0)
                ax.text(0.5, 0.86, "ZENTRALSTATION", color=C_BLUE,
                        fontsize=10, fontweight="bold", ha="center", va="center")
                for y_pos, txt in zip([0.65, 0.48, 0.31],
                                      [f"Host: {get_hostname()}.local",
                                       "Zigbee 3.0 / MQTT",
                                       "DB: SQLite (Dauerlogger)"]):
                    ax.text(0.5, y_pos, txt, color=C_SUBTLE, fontsize=8, ha="center", va="center")
                ax.text(0.5, 0.11, "SYSTEM BEREIT  [OK]", color=C_GREEN,
                        fontsize=9, fontweight="bold", ha="center", va="center")
                continue

            d = snap.get(sid, {})
            temp, hum, last = d.get("temp"), d.get("hum"), d.get("last_seen")
            online = (temp is not None or hum is not None)

            if online:
                ax.spines[:].set_color("#45475a")
                status_text  = "[+] ONLINE"
                status_color = C_GREEN
            else:
                status_text  = "[ ] BEREIT"
                status_color = C_MUTED

            ax.text(0.06, 0.90, sname, color=C_TEXT,
                    fontsize=11, fontweight="bold", ha="left", va="center")
            ax.text(0.94, 0.90, status_text, color=status_color,
                    fontsize=7, fontweight="bold", ha="right", va="center")
            ax.axhline(0.80, 0.04, 0.96, color=BG_BORDER, linewidth=1.2)

            # Temperatur
            if temp is not None:
                t_str   = f"{temp:.1f}"
                t_color = C_RED if temp >= 24 else (C_BLUE if temp <= 19 else C_ORANGE)
            else:
                t_str, t_color = "--.-", "#585b70"

            # Luftfeuchte
            if hum is not None and hum > 0:
                h_str, h_color = f"{hum:.1f}", C_BLUE
            else:
                h_str, h_color = "--.-", "#585b70"

            ax.text(0.27, 0.52, t_str,   color=t_color, fontsize=24, fontweight="bold", ha="center", va="center")
            ax.text(0.27, 0.28, "Temp (C)", color=C_MUTED, fontsize=8,  ha="center", va="center")
            ax.axvline(0.50, 0.21, 0.73, color=BG_BORDER, linewidth=1.2)
            ax.text(0.73, 0.52, h_str,   color=h_color, fontsize=24, fontweight="bold", ha="center", va="center")
            ax.text(0.73, 0.28, "Feuchte (%)", color=C_MUTED, fontsize=8,  ha="center", va="center")

            last_txt = f"Signal: {last}" if last else "Warte auf Funksignal ..."
            ax.text(0.5, 0.09, last_txt, color=C_MUTED, fontsize=7, ha="center", va="center")

    # ══════════════════════════════════════════════════════════════
    # TAB 2: HISTORIE
    # Layout (absolute figure coords):
    #
    #  0.883 ─────────────────────────────────────────────── (Content-Top)
    #  0.828 │ [Jana] [David] [Eric] [Dings] [Balkon]  [24h][7T][30T] │
    #  0.820 ─ (Trennlinie) ──────────────────────────────────────────
    #  0.455 │  Temperatur-Plot                                        │
    #  0.445 ─ (Luecke) ────────────────────────────────────────────
    #  0.065 │  Luftfeuchte-Plot                                       │
    #  0.010 ─────────────────────────────────────────────── (Content-Bot)
    # ══════════════════════════════════════════════════════════════
    HIST_BTN_Y  = 0.828   # Unterkante Sensor/Zeit-Buttons
    HIST_BTN_H  = 0.047   # Hoehe Sensor/Zeit-Buttons
    HIST_SEP_Y  = HIST_BTN_Y - 0.010   # = 0.818
    HIST_T_TOP  = HIST_SEP_Y - 0.008   # = 0.810 oben Temp-Plot
    HIST_T_BOT  = 0.455                # unterkante Temp-Plot
    HIST_H_TOP  = 0.440                # oben Feuchte-Plot
    HIST_H_BOT  = CONTENT_BOT + 0.055  # = 0.065
    HIST_LEFT   = 0.065
    HIST_RIGHT  = 0.985

    def build_historie():
        global historie_sensor, historie_stunden

        # ── Sensor-Auswahl-Buttons (5) ───────────────────────────
        # Jeder Button: Breite 0.120, Abstand 0.008, Start x=0.010
        s_btn_w = 0.122
        s_btn_gap = 0.008
        for i, slot in enumerate(SENSOR_SLOTS):
            bx = s_btn_w + s_btn_gap
            ax_b = fig.add_axes([0.010 + i*bx, HIST_BTN_Y, s_btn_w, HIST_BTN_H])
            is_active = slot["id"] == historie_sensor
            fc = C_CYAN if is_active else "#2a2a3e"
            tc = BG_DEEP if is_active else C_SUBTLE
            btn = Button(ax_b, slot["name"], color=fc, hovercolor="#45475a")
            btn.label.set_fontsize(9)
            btn.label.set_fontweight("bold" if is_active else "normal")
            btn.label.set_color(tc)
            content_axes.append(ax_b)
            content_btns.append(btn)

            def make_select(sid):
                def handler(e):
                    global historie_sensor
                    historie_sensor = sid
                    clear_content()
                    build_historie()
                    fig.canvas.draw_idle()
                return handler
            btn.on_clicked(make_select(slot["id"]))

        # ── Zeitraum-Buttons (3) ─────────────────────────────────
        # Rechts ausgerichtet, x=0.685 bis 0.985
        zeit_opts  = [("24 h", 24), ("7 Tage", 168), ("30 Tage", 720)]
        z_btn_w    = 0.093
        z_btn_gap  = 0.008
        z_start_x  = HIST_RIGHT - len(zeit_opts)*(z_btn_w + z_btn_gap) + z_btn_gap
        for i, (label, std) in enumerate(zeit_opts):
            ax_z = fig.add_axes([z_start_x + i*(z_btn_w + z_btn_gap),
                                 HIST_BTN_Y, z_btn_w, HIST_BTN_H])
            is_active = std == historie_stunden
            fc = C_YELLOW if is_active else "#2a2a3e"
            tc = BG_DEEP if is_active else C_SUBTLE
            btnz = Button(ax_z, label, color=fc, hovercolor="#45475a")
            btnz.label.set_fontsize(8)
            btnz.label.set_fontweight("bold" if is_active else "normal")
            btnz.label.set_color(tc)
            content_axes.append(ax_z)
            content_btns.append(btnz)

            def make_zeit(s):
                def handler(e):
                    global historie_stunden
                    historie_stunden = s
                    clear_content()
                    build_historie()
                    fig.canvas.draw_idle()
                return handler
            btnz.on_clicked(make_zeit(std))

        # ── Trennlinie ───────────────────────────────────────────
        ax_sep2 = fig.add_axes([0.010, HIST_SEP_Y, 0.980, 0.003])
        ax_sep2.set_facecolor(BG_BORDER)
        ax_sep2.set_xticks([]); ax_sep2.set_yticks([])
        for sp in ax_sep2.spines.values():
            sp.set_visible(False)
        content_axes.append(ax_sep2)

        # ── Diagramm-Axes ────────────────────────────────────────
        ax_temp = fig.add_axes([
            HIST_LEFT, HIST_T_BOT,
            HIST_RIGHT - HIST_LEFT, HIST_T_TOP - HIST_T_BOT
        ])
        ax_hum = fig.add_axes([
            HIST_LEFT, HIST_H_BOT,
            HIST_RIGHT - HIST_LEFT, HIST_H_TOP - HIST_H_BOT
        ])

        for ax in (ax_temp, ax_hum):
            ax.set_facecolor(BG_CARD)
            ax.tick_params(colors=C_SUBTLE, labelsize=7)
            for sp in ax.spines.values():
                sp.set_color(BG_BORDER)
                sp.set_linewidth(0.8)
            ax.yaxis.label.set_color(C_SUBTLE)
            ax.grid(True, color=BG_BORDER, linewidth=0.5, linestyle="--", alpha=0.6)

        content_axes.extend([ax_temp, ax_hum])

        # ── Daten laden ──────────────────────────────────────────
        ts_list, temp_list, hum_list = get_history(historie_sensor, historie_stunden)
        sensor_label  = next((s["name"] for s in SENSOR_SLOTS if s["id"] == historie_sensor), "?")
        if historie_stunden < 48:
            zeit_label = f"{historie_stunden} Stunden"
        else:
            zeit_label = f"{historie_stunden // 24} Tage"

        if not ts_list:
            for ax, lbl in ((ax_temp, "Temperatur"), (ax_hum, "Luftfeuchte")):
                ax.text(0.5, 0.5,
                        f"Keine Daten fuer \"{sensor_label}\" in den letzten {zeit_label}.",
                        color=C_MUTED, fontsize=9, ha="center", va="center",
                        transform=ax.transAxes)
            ax_temp.set_title(f"Temperatur   |   Sensor: {sensor_label}   |   Zeitraum: {zeit_label}",
                              color=C_TEXT, fontsize=9, pad=6)
            ax_hum.set_title(f"Luftfeuchte  |   Sensor: {sensor_label}   |   Zeitraum: {zeit_label}",
                             color=C_TEXT, fontsize=9, pad=6)
        else:
            # X-Achsen-Labels
            n = len(ts_list)
            step = max(1, n // 8)
            x_ticks  = list(range(0, n, step))
            if historie_stunden <= 24:
                x_labels = [ts_list[i][11:16] for i in x_ticks]   # HH:MM
            elif historie_stunden <= 168:
                x_labels = [ts_list[i][5:10] + "\n" + ts_list[i][11:16] for i in x_ticks]
            else:
                x_labels = [ts_list[i][5:10] for i in x_ticks]   # MM-DD

            x = list(range(n))

            # Temperatur-Plot
            vt = [(i, v) for i, v in enumerate(temp_list) if v is not None]
            if vt:
                xi, yi = zip(*vt)
                ax_temp.plot(xi, yi, color=C_RED, linewidth=1.6, marker="o",
                             markersize=2.5, label="Temperatur")
                ax_temp.fill_between(xi, yi, min(yi) - 0.3, alpha=0.10, color=C_RED)
                ax_temp.annotate(f"{yi[-1]:.1f} C", xy=(xi[-1], yi[-1]),
                                 xytext=(5, 5), textcoords="offset points",
                                 color=C_RED, fontsize=8, fontweight="bold")
            ax_temp.set_ylabel("Grad C", color=C_RED, fontsize=8)
            ax_temp.set_title(
                f"Temperatur   |   Sensor: {sensor_label}   |   Zeitraum: {zeit_label}   "
                f"|   {n} Messpunkte",
                color=C_TEXT, fontsize=9, pad=6)
            ax_temp.set_xticks(x_ticks)
            ax_temp.set_xticklabels(x_labels, rotation=25, ha="right", fontsize=6.5)

            # Feuchte-Plot
            vh = [(i, v) for i, v in enumerate(hum_list) if v is not None]
            if vh:
                xi, yi = zip(*vh)
                ax_hum.plot(xi, yi, color=C_BLUE, linewidth=1.6, marker="s",
                            markersize=2.5, label="Luftfeuchte")
                ax_hum.fill_between(xi, yi, min(yi) - 0.3, alpha=0.10, color=C_BLUE)
                ax_hum.annotate(f"{yi[-1]:.1f} %", xy=(xi[-1], yi[-1]),
                                xytext=(5, 5), textcoords="offset points",
                                color=C_BLUE, fontsize=8, fontweight="bold")
            ax_hum.set_ylabel("% rH", color=C_BLUE, fontsize=8)
            ax_hum.set_title(
                f"Luftfeuchte  |   Sensor: {sensor_label}   |   Zeitraum: {zeit_label}",
                color=C_TEXT, fontsize=9, pad=6)
            ax_hum.set_xticks(x_ticks)
            ax_hum.set_xticklabels(x_labels, rotation=25, ha="right", fontsize=6.5)

    # ══════════════════════════════════════════════════════════════
    # TAB 3: STEUERUNG
    # ══════════════════════════════════════════════════════════════
    def build_steuerung():
        # Zwei Spalten: links Systeminfo, rechts Erinnerungen
        mid  = 0.500
        gap  = 0.010
        h    = CONTENT_TOP - CONTENT_BOT
        y0   = CONTENT_BOT

        ax_info = fig.add_axes([0.010,       y0, mid - gap - 0.010, h])
        ax_memo = fig.add_axes([mid + gap, y0, 1.0 - mid - gap - 0.010, h])
        content_axes.extend([ax_info, ax_memo])

        for ax in (ax_info, ax_memo):
            ax.set_facecolor(BG_CARD)
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_color(BG_BORDER); sp.set_linewidth(1.5)

        # ── Linke Seite: Systeminfo ──────────────────────────────
        ax_info.text(0.5, 0.93, "ZENTRALSTATION", color=C_BLUE,
                     fontsize=13, fontweight="bold", ha="center", va="center")
        ax_info.axhline(0.86, 0.05, 0.95, color=BG_BORDER, linewidth=1.2)

        infos = [
            ("Host",       f"{get_hostname()}.local  (Raspberry Pi)"),
            ("IP",         "192.168.2.160"),
            ("Protokoll",  "Zigbee 3.0  via  Zigbee2MQTT"),
            ("Datenbank",  "SQLite  (data/sensor_history.db)"),
            ("MQTT-Broker","Mosquitto  @  localhost:1883"),
        ]
        for i, (key, val) in enumerate(infos):
            y_pos = 0.75 - i * 0.10
            ax_info.text(0.07, y_pos, f"{key}:", color=C_MUTED,
                         fontsize=9, ha="left", va="center")
            ax_info.text(0.38, y_pos, val, color=C_SUBTLE,
                         fontsize=9, ha="left", va="center")

        ax_info.axhline(0.27, 0.05, 0.95, color=BG_BORDER, linewidth=1.2)
        ax_info.text(0.5, 0.21, "SYSTEMSTEUERUNG", color=C_MUTED,
                     fontsize=8, ha="center", va="center")

        # Shutdown-Button
        bx_sd = fig.add_axes([0.030, 0.060, 0.190, 0.110])
        btn_sd = Button(bx_sd, "[X]  Herunterfahren", color="#3d1515", hovercolor=C_RED)
        btn_sd.label.set_fontsize(9)
        btn_sd.label.set_color(C_RED)
        content_axes.append(bx_sd); content_btns.append(btn_sd)

        # Neustart-Button
        bx_rs = fig.add_axes([0.245, 0.060, 0.190, 0.110])
        btn_rs = Button(bx_rs, "[>]  Neustart", color="#15301a", hovercolor=C_GREEN)
        btn_rs.label.set_fontsize(9)
        btn_rs.label.set_color(C_GREEN)
        content_axes.append(bx_rs); content_btns.append(btn_rs)

        def do_shutdown(e):
            print("[System] Fahre Raspberry Pi herunter...")
            subprocess.Popen(["sudo", "shutdown", "-h", "now"])

        def do_restart(e):
            print("[System] Starte Dashboard neu...")
            python = __import__("sys").executable
            os.execv(python, [python] + __import__("sys").argv)

        btn_sd.on_clicked(do_shutdown)
        btn_rs.on_clicked(do_restart)

        # ── Rechte Seite: Erinnerungen ───────────────────────────
        data  = lade_erinnerungen()
        erinnerungen = data.get("erinnerungen", [])
        notizen      = data.get("notizen", [])

        ax_memo.text(0.5, 0.93, "ERINNERUNGEN & NOTIZEN", color=C_ORANGE,
                     fontsize=13, fontweight="bold", ha="center", va="center")
        ax_memo.axhline(0.86, 0.05, 0.95, color=BG_BORDER, linewidth=1.2)

        yy = 0.79
        ax_memo.text(0.06, yy, "Wochentag", color=C_MUTED, fontsize=8,
                     fontweight="bold", ha="left", va="center")
        ax_memo.text(0.48, yy, "Aufgabe", color=C_MUTED, fontsize=8,
                     fontweight="bold", ha="left", va="center")
        yy -= 0.07

        for erin in erinnerungen:
            if yy < 0.42:
                break
            ax_memo.text(0.06, yy, erin.get("wochentag", ""),
                         color=C_TEXT, fontsize=9, ha="left", va="center")
            ax_memo.text(0.48, yy, erin.get("text", ""),
                         color=C_SUBTLE, fontsize=9, ha="left", va="center")
            yy -= 0.09

        if notizen:
            ax_memo.axhline(yy - 0.02, 0.05, 0.95, color=BG_BORDER, linewidth=1.0)
            yy -= 0.10
            ax_memo.text(0.5, yy, "Hinweise", color=C_MUTED, fontsize=8,
                         fontweight="bold", ha="center", va="center")
            yy -= 0.09
            for notiz in notizen:
                if yy < 0.04:
                    break
                ax_memo.text(0.06, yy, f"> {notiz}", color=C_SUBTLE, fontsize=9,
                             ha="left", va="center")
                yy -= 0.09

    # ── Animations-Loop ─────────────────────────────────────────────
    def animate(frame):
        jetzt = datetime.now().strftime("%d.%m.%Y   |   %H:%M:%S")
        uhr_text.set_text(f">> SUPRA SCI-FI HOME 8000   |   {jetzt}")
        if aktiver_tab == "live":
            update_live()

    # Startzustand
    build_live()
    update_tab_btns()

    fig.canvas.mpl_connect("close_event", lambda e: __import__("sys").exit(0))
    ani = animation.FuncAnimation(fig, animate, interval=UPDATE_INTERVAL, cache_frame_data=False)
    plt.show()

# ─── Start ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()

    vorwerte = get_last_values()
    for sid, werte in vorwerte.items():
        if sid in sensor_daten:
            sensor_daten[sid].update(werte)
        else:
            sensor_daten[sid] = werte
    if vorwerte:
        print(f"[DB] {len(vorwerte)} Sensor(en) mit letzten Werten vorgeladen.")

    t = threading.Thread(target=mqtt_thread, daemon=True)
    t.start()

    try:
        erstelle_dashboard()
    except KeyboardInterrupt:
        print("\n[System] Beendet.")
        __import__("sys").exit(0)