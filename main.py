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
from matplotlib.widgets import Button
from database import init_db, save_measurement, get_last_values, get_history

# ─── Konfiguration ──────────────────────────────────────────────────────────
MQTT_BROKER     = "localhost"
MQTT_BASE_TOPIC = "zigbee2mqtt/#"
UPDATE_INTERVAL = 30000  # 30 Sekunden – kein Ladesymbol mehr (keine Sekundenanzeige)

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

aktiver_tab      = "live"
historie_sensor  = SENSOR_SLOTS[0]["id"]
historie_stunden = 24

# ─── Layout-Konstanten ──────────────────────────────────────────────────────
#
#  ┌─────┬──────────────────────────────────────────────────────────────────┐
#  │     │  TITELZEILE                                        y=0.955-0.995 │
#  │  L  ├──────────────────────────────────────────────────────────────────┤
#  │  I  │                                                                  │
#  │  V  │                                                                  │
#  │  E  │                                                                  │
#  ├─────┤  CONTENT-BEREICH                                   y=0.005-0.950 │
#  │  H  │                                                                  │
#  │  I  │                                                                  │
#  │  S  │                                                                  │
#  ├─────┤                                                                  │
#  │  S  │                                                                  │
#  │  T  │                                                                  │
#  │  G  │                                                                  │
#  └─────┴──────────────────────────────────────────────────────────────────┘
#  0.00 0.14                                                            1.00

TITLE_Y   = 0.955
TITLE_H   = 0.040

# Linke Tab-Leiste
TAB_X     = 0.000   # Linke Kante der Tabs
TAB_W     = 0.138   # Breite der Tab-Buttons
TAB_BTM   = 0.005   # Unterkante der gesamten Tab-Leiste
TAB_TOP   = TITLE_Y # Oberkante (bündig mit Titelzeile-Unterkante)

# Trennlinie zwischen Tab-Leiste und Content
SEP_X     = TAB_W + TAB_X + 0.003   # = 0.141

# Content-Bereich
CONT_X    = SEP_X + 0.005           # = 0.146
CONT_W    = 1.000 - CONT_X - 0.005  # ≈ 0.849
CONT_Y    = TAB_BTM                  # = 0.005
CONT_H    = TITLE_Y - TAB_BTM       # = 0.950

# Farben
BG_DEEP   = "#0a0a12"
BG_CARD   = "#181825"
BG_BORDER = "#313244"
C_TEXT    = "#cdd6f4"
C_MUTED   = "#6c7086"
C_SUBTLE  = "#a6adc8"
C_GREEN   = "#a6e3a1"
C_BLUE    = "#89b4fa"
C_RED     = "#f38ba8"
C_ORANGE  = "#fab387"
C_CYAN    = "#89dceb"
C_YELLOW  = "#f9e2af"

TAB_COLORS = {
    "live":      {"active": C_GREEN,  "inactive": "#12120f"},
    "historie":  {"active": C_CYAN,   "inactive": "#0a0f12"},
    "steuerung": {"active": C_YELLOW, "inactive": "#120f00"},
}

# ─── Hilfsfunktionen ────────────────────────────────────────────────────────
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

# ─── MQTT ───────────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc, properties=None):
    code = rc if isinstance(rc, int) else getattr(rc, "value", 0)
    if code == 0:
        print(f"[MQTT] Verbunden mit {MQTT_BROKER}")
        client.subscribe(MQTT_BASE_TOPIC)
    else:
        print(f"[MQTT] Fehler Code: {rc}")

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

        jetzt = datetime.now().strftime("%H:%M")
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

        print(f"[{jetzt}] [{sensor_name}] {temp:.1f} C | {hum:.1f} %")

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

# ─── Dashboard ──────────────────────────────────────────────────────────────
def erstelle_dashboard():
    global aktiver_tab, historie_sensor, historie_stunden

    fig = plt.figure(figsize=(16, 9), facecolor=BG_DEEP)

    mng = plt.get_current_fig_manager()
    try:
        mng.full_screen_toggle()
    except Exception:
        try:
            mng.window.attributes("-fullscreen", True)
        except Exception:
            pass

    # ── Titelzeile ─────────────────────────────────────────────────────────
    ax_title = fig.add_axes([0.0, TITLE_Y, 1.0, TITLE_H])
    ax_title.set_facecolor("#11111b")
    ax_title.set_xticks([]); ax_title.set_yticks([])
    for sp in ax_title.spines.values():
        sp.set_visible(False)
    uhr_text = ax_title.text(
        0.5, 0.5, "",
        color=C_TEXT, fontsize=12, fontweight="bold",
        ha="center", va="center", transform=ax_title.transAxes
    )

    # Trennlinie unter Titelzeile
    ax_title_sep = fig.add_axes([0.0, TITLE_Y - 0.003, 1.0, 0.003])
    ax_title_sep.set_facecolor(BG_BORDER)
    ax_title_sep.set_xticks([]); ax_title_sep.set_yticks([])
    for sp in ax_title_sep.spines.values():
        sp.set_visible(False)

    # ── Vertikale Tab-Leiste (links) ────────────────────────────────────────
    tab_keys   = ["live", "historie", "steuerung"]
    tab_labels = ["L\nI\nV\nE", "H\nI\nS\nT\nO\nR\nI\nE", "S\nT\nE\nU\nE\nR\nU\nN\nG"]
    tab_labels_h = ["LIVE", "HISTORIE", "STEUERUNG"]  # horizontale Version fuer Button-Label

    # Tab-Leisten-Hintergrund
    ax_tabbar = fig.add_axes([TAB_X, CONT_Y, TAB_W, CONT_H])
    ax_tabbar.set_facecolor("#11111b")
    ax_tabbar.set_xticks([]); ax_tabbar.set_yticks([])
    for sp in ax_tabbar.spines.values():
        sp.set_visible(False)

    # Trennlinie zwischen Tab-Leiste und Content
    ax_sep = fig.add_axes([SEP_X, CONT_Y, 0.003, CONT_H])
    ax_sep.set_facecolor(BG_BORDER)
    ax_sep.set_xticks([]); ax_sep.set_yticks([])
    for sp in ax_sep.spines.values():
        sp.set_visible(False)

    # Tab-Buttons gleichmaessig ueber die Hoehe aufteilen
    n_tabs   = len(tab_keys)
    tab_h    = CONT_H / n_tabs          # Hoehe pro Tab ≈ 0.317
    tab_gap  = 0.004                    # kleiner Abstand zwischen Tabs
    tab_btns = []

    for i, (key, label) in enumerate(zip(tab_keys, tab_labels_h)):
        y_pos = CONT_Y + (n_tabs - 1 - i) * tab_h + tab_gap / 2
        h_pos = tab_h - tab_gap
        bax = fig.add_axes([TAB_X + 0.004, y_pos, TAB_W - 0.008, h_pos])
        btn = Button(bax, label, color=TAB_COLORS[key]["inactive"], hovercolor=BG_BORDER)
        # Beschriftung vertikal / zentriert
        btn.label.set_fontsize(10)
        btn.label.set_fontweight("normal")
        btn.label.set_color(C_MUTED)
        btn.label.set_rotation(90)   # Text hochkant
        tab_btns.append(btn)

    # ── Content-Verwaltung ─────────────────────────────────────────────────
    content_axes = []
    content_btns = []

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
                btn.ax.set_facecolor(TAB_COLORS[key]["active"])
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
        {"live": build_live, "historie": build_historie, "steuerung": build_steuerung}[key]()
        fig.canvas.draw_idle()

    tab_btns[0].on_clicked(lambda e: switch_tab("live"))
    tab_btns[1].on_clicked(lambda e: switch_tab("historie"))
    tab_btns[2].on_clicked(lambda e: switch_tab("steuerung"))

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1: LIVE – 2x3 Kachelraster
    # ══════════════════════════════════════════════════════════════════════
    def build_live():
        cols, rows = 3, 2
        gap  = 0.008
        w    = (CONT_W - (cols - 1) * gap) / cols
        h    = (CONT_H - (rows - 1) * gap) / rows
        for row in range(rows):
            for col in range(cols):
                x = CONT_X + col * (w + gap)
                y = CONT_Y + (rows - 1 - row) * (h + gap)
                ax = fig.add_axes([x, y, w, h])
                ax.set_facecolor(BG_CARD)
                ax.set_xticks([]); ax.set_yticks([])
                for sp in ax.spines.values():
                    sp.set_color(BG_BORDER); sp.set_linewidth(1.5)
                content_axes.append(ax)

    def update_live():
        if aktiver_tab != "live" or len(content_axes) != 6:
            return
        with lock:
            snap = {k: dict(v) for k, v in sensor_daten.items()}

        for idx, slot in enumerate(SLOTS):
            ax  = content_axes[idx]
            ax.cla()
            ax.set_facecolor(BG_CARD)
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_color(BG_BORDER); sp.set_linewidth(1.5)

            sid, sname = slot["id"], slot["name"]

            if sid == "SYSTEM_INFO":
                ax.spines[:].set_color(C_BLUE); ax.spines[:].set_linewidth(2.0)
                ax.text(0.5, 0.86, "ZENTRALSTATION", color=C_BLUE,
                        fontsize=10, fontweight="bold", ha="center", va="center")
                for yp, txt in zip([0.65, 0.48, 0.31],
                                   [f"Host: {get_hostname()}.local",
                                    "Zigbee 3.0 / MQTT",
                                    "DB: SQLite (Dauerlogger)"]):
                    ax.text(0.5, yp, txt, color=C_SUBTLE, fontsize=8, ha="center", va="center")
                ax.text(0.5, 0.11, "SYSTEM BEREIT  [OK]", color=C_GREEN,
                        fontsize=9, fontweight="bold", ha="center", va="center")
                continue

            d    = snap.get(sid, {})
            temp = d.get("temp")
            hum  = d.get("hum")
            last = d.get("last_seen")
            online = (temp is not None or hum is not None)

            if online:
                ax.spines[:].set_color("#45475a")
                status_text, status_color = "[+] ONLINE", C_GREEN
            else:
                status_text, status_color = "[ ] BEREIT", C_MUTED

            ax.text(0.06, 0.90, sname, color=C_TEXT,
                    fontsize=11, fontweight="bold", ha="left", va="center")
            ax.text(0.94, 0.90, status_text, color=status_color,
                    fontsize=7, fontweight="bold", ha="right", va="center")
            ax.axhline(0.80, 0.04, 0.96, color=BG_BORDER, linewidth=1.2)

            t_str   = f"{temp:.1f}" if temp is not None else "--.-"
            t_color = (C_RED if temp is not None and temp >= 24 else
                       (C_BLUE if temp is not None and temp <= 19 else C_ORANGE)
                       if temp is not None else "#585b70")

            h_str   = f"{hum:.1f}" if (hum is not None and hum > 0) else "--.-"
            h_color = C_BLUE if (hum is not None and hum > 0) else "#585b70"

            ax.text(0.27, 0.52, t_str, color=t_color,
                    fontsize=24, fontweight="bold", ha="center", va="center")
            ax.text(0.27, 0.28, "Temp (C)", color=C_MUTED,
                    fontsize=8, ha="center", va="center")
            ax.axvline(0.50, 0.21, 0.73, color=BG_BORDER, linewidth=1.2)
            ax.text(0.73, 0.52, h_str, color=h_color,
                    fontsize=24, fontweight="bold", ha="center", va="center")
            ax.text(0.73, 0.28, "Feuchte (%)", color=C_MUTED,
                    fontsize=8, ha="center", va="center")

            last_txt = f"Signal: {last}" if last else "Warte auf Funksignal ..."
            ax.text(0.5, 0.09, last_txt, color=C_MUTED, fontsize=7, ha="center", va="center")

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2: HISTORIE
    #
    # Innerhalb des Content-Bereichs (CONT_X bis CONT_X+CONT_W, CONT_Y bis CONT_Y+CONT_H):
    #
    #  obere 8%  : Sensor-Auswahl-Buttons (links) + Zeitraum-Buttons (rechts)
    #  Linie     : Trennlinie
    #  mittlere 42%: Temperatur-Diagramm (flach)
    #  kleiner Spalt
    #  untere 42%  : Luftfeuchte-Diagramm (flach)
    # ══════════════════════════════════════════════════════════════════════
    def build_historie():
        global historie_sensor, historie_stunden

        # Berechnung der absoluten Y-Positionen
        btn_h    = 0.046
        btn_y    = CONT_Y + CONT_H - btn_h - 0.005          # ≈ 0.899
        sep_y    = btn_y - 0.008                              # ≈ 0.891
        plot_top = sep_y - 0.005                              # ≈ 0.886
        plot_mid = CONT_Y + (plot_top - CONT_Y) / 2 + 0.010  # Mitte + kleiner Versatz
        gap      = 0.018
        diag_h   = (plot_top - CONT_Y - gap) / 2             # Hoehe je Diagramm ≈ 0.43

        temp_bot = plot_mid + gap / 2
        temp_top = temp_bot + diag_h
        hum_top  = plot_mid - gap / 2
        hum_bot  = CONT_Y + 0.010

        plt_left  = CONT_X + 0.030
        plt_right = CONT_X + CONT_W - 0.008
        plt_w     = plt_right - plt_left

        # ── Sensor-Buttons ───────────────────────────────────────────────
        s_w = 0.110
        s_g = 0.007
        for i, slot in enumerate(SENSOR_SLOTS):
            ax_b = fig.add_axes([CONT_X + i*(s_w + s_g), btn_y, s_w, btn_h])
            is_a = slot["id"] == historie_sensor
            btn  = Button(ax_b, slot["name"],
                          color=(C_CYAN if is_a else "#1a1a2e"),
                          hovercolor="#2a2a4e")
            btn.label.set_fontsize(9)
            btn.label.set_fontweight("bold" if is_a else "normal")
            btn.label.set_color(BG_DEEP if is_a else C_SUBTLE)
            content_axes.append(ax_b)
            content_btns.append(btn)

            def make_sel(sid):
                def h(e):
                    global historie_sensor
                    historie_sensor = sid
                    clear_content(); build_historie()
                    fig.canvas.draw_idle()
                return h
            btn.on_clicked(make_sel(slot["id"]))

        # ── Zeitraum-Buttons ─────────────────────────────────────────────
        z_opts = [("24 h", 24), ("7 Tage", 168), ("30 Tage", 720)]
        z_w    = 0.085
        z_g    = 0.007
        z_x0   = CONT_X + CONT_W - len(z_opts)*(z_w + z_g) + z_g
        for i, (label, std) in enumerate(z_opts):
            ax_z = fig.add_axes([z_x0 + i*(z_w + z_g), btn_y, z_w, btn_h])
            is_a = std == historie_stunden
            btnz = Button(ax_z, label,
                          color=(C_YELLOW if is_a else "#1e1a00"),
                          hovercolor="#2e2a00")
            btnz.label.set_fontsize(8)
            btnz.label.set_fontweight("bold" if is_a else "normal")
            btnz.label.set_color(BG_DEEP if is_a else C_SUBTLE)
            content_axes.append(ax_z)
            content_btns.append(btnz)

            def make_z(s):
                def h(e):
                    global historie_stunden
                    historie_stunden = s
                    clear_content(); build_historie()
                    fig.canvas.draw_idle()
                return h
            btnz.on_clicked(make_z(std))

        # ── Trennlinie ───────────────────────────────────────────────────
        ax_line = fig.add_axes([CONT_X, sep_y, CONT_W, 0.002])
        ax_line.set_facecolor(BG_BORDER)
        ax_line.set_xticks([]); ax_line.set_yticks([])
        for sp in ax_line.spines.values():
            sp.set_visible(False)
        content_axes.append(ax_line)

        # ── Diagramm-Axes ────────────────────────────────────────────────
        ax_temp = fig.add_axes([plt_left, temp_bot, plt_w, temp_top - temp_bot])
        ax_hum  = fig.add_axes([plt_left, hum_bot,  plt_w, hum_top  - hum_bot ])

        for ax in (ax_temp, ax_hum):
            ax.set_facecolor(BG_CARD)
            ax.tick_params(colors=C_SUBTLE, labelsize=7)
            for sp in ax.spines.values():
                sp.set_color(BG_BORDER); sp.set_linewidth(0.8)
            ax.grid(True, color=BG_BORDER, linewidth=0.5, linestyle="--", alpha=0.5)
        content_axes.extend([ax_temp, ax_hum])

        # ── Daten laden ──────────────────────────────────────────────────
        ts_list, temp_list, hum_list = get_history(historie_sensor, historie_stunden)
        s_label = next((s["name"] for s in SENSOR_SLOTS if s["id"] == historie_sensor), "?")
        z_label = (f"{historie_stunden} h" if historie_stunden < 48
                   else f"{historie_stunden // 24} Tage")
        n = len(ts_list)

        # X-Achsen-Labels
        step     = max(1, n // 8)
        x_ticks  = list(range(0, n, step))
        if historie_stunden <= 24:
            x_labels = [ts_list[i][11:16] for i in x_ticks]
        elif historie_stunden <= 168:
            x_labels = [ts_list[i][5:10] + "\n" + ts_list[i][11:16] for i in x_ticks]
        else:
            x_labels = [ts_list[i][5:10] for i in x_ticks]

        def info_text(ax, typ, farbe):
            """Schreibt Sensor, Zeitraum und Messpunkte als separate Texte ins Diagramm."""
            # Typ-Label (gross, links)
            ax.text(0.0, 1.035, typ, color=farbe,
                    fontsize=10, fontweight="bold",
                    ha="left", va="bottom", transform=ax.transAxes)
            # Sensor & Zeitraum (mittig)
            ax.text(0.38, 1.035, f"Sensor:  {s_label}",
                    color=C_TEXT, fontsize=8.5, ha="left", va="bottom",
                    transform=ax.transAxes)
            ax.text(0.58, 1.035, f"Zeitraum:  {z_label}",
                    color=C_TEXT, fontsize=8.5, ha="left", va="bottom",
                    transform=ax.transAxes)
            # Messpunkte (rechts)
            ax.text(1.0, 1.035, f"{n} Messpunkte",
                    color=C_MUTED, fontsize=8, ha="right", va="bottom",
                    transform=ax.transAxes)

        if not ts_list:
            for ax, lbl, col in ((ax_temp, "Temperatur", C_RED),
                                  (ax_hum,  "Luftfeuchte", C_BLUE)):
                info_text(ax, lbl, col)
                ax.text(0.5, 0.5, f"Keine Daten fuer Sensor \"{s_label}\".",
                        color=C_MUTED, fontsize=9, ha="center", va="center",
                        transform=ax.transAxes)
        else:
            # Temperatur-Plot
            info_text(ax_temp, "Temperatur", C_RED)
            ax_temp.set_ylabel("Grad C", color=C_RED, fontsize=8, labelpad=4)
            vt = [(i, v) for i, v in enumerate(temp_list) if v is not None]
            if vt:
                xi, yi = zip(*vt)
                ax_temp.plot(xi, yi, color=C_RED, linewidth=1.5,
                             marker="o", markersize=2.5)
                ax_temp.fill_between(xi, yi, min(yi) - 0.3,
                                     alpha=0.10, color=C_RED)
                ax_temp.annotate(f"  {yi[-1]:.1f} C", xy=(xi[-1], yi[-1]),
                                 xytext=(4, 0), textcoords="offset points",
                                 color=C_RED, fontsize=8, fontweight="bold")
            ax_temp.set_xticks(x_ticks)
            ax_temp.set_xticklabels(x_labels, rotation=20, ha="right", fontsize=6.5)

            # Luftfeuchte-Plot
            info_text(ax_hum, "Luftfeuchte", C_BLUE)
            ax_hum.set_ylabel("% rH", color=C_BLUE, fontsize=8, labelpad=4)
            vh = [(i, v) for i, v in enumerate(hum_list) if v is not None]
            if vh:
                xi, yi = zip(*vh)
                ax_hum.plot(xi, yi, color=C_BLUE, linewidth=1.5,
                            marker="s", markersize=2.5)
                ax_hum.fill_between(xi, yi, min(yi) - 0.3,
                                    alpha=0.10, color=C_BLUE)
                ax_hum.annotate(f"  {yi[-1]:.1f} %", xy=(xi[-1], yi[-1]),
                                xytext=(4, 0), textcoords="offset points",
                                color=C_BLUE, fontsize=8, fontweight="bold")
            ax_hum.set_xticks(x_ticks)
            ax_hum.set_xticklabels(x_labels, rotation=20, ha="right", fontsize=6.5)

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3: STEUERUNG
    # ══════════════════════════════════════════════════════════════════════
    def build_steuerung():
        mid = CONT_X + CONT_W / 2
        gap = 0.010

        ax_info = fig.add_axes([CONT_X,       CONT_Y, mid - CONT_X - gap, CONT_H])
        ax_memo = fig.add_axes([mid + gap, CONT_Y, CONT_X + CONT_W - mid - gap, CONT_H])
        content_axes.extend([ax_info, ax_memo])

        for ax in (ax_info, ax_memo):
            ax.set_facecolor(BG_CARD)
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_color(BG_BORDER); sp.set_linewidth(1.5)

        # ── Systeminfo ───────────────────────────────────────────────────
        ax_info.text(0.5, 0.93, "ZENTRALSTATION", color=C_BLUE,
                     fontsize=13, fontweight="bold", ha="center", va="center")
        ax_info.axhline(0.86, 0.05, 0.95, color=BG_BORDER, linewidth=1.2)

        for i, (key, val) in enumerate([
            ("Host",      f"{get_hostname()}.local  (Raspberry Pi)"),
            ("IP",        "192.168.2.160"),
            ("Protokoll", "Zigbee 3.0  via  Zigbee2MQTT"),
            ("Datenbank", "SQLite  (data/sensor_history.db)"),
            ("Broker",    "Mosquitto  @  localhost:1883"),
        ]):
            yp = 0.75 - i * 0.10
            ax_info.text(0.06, yp, f"{key}:", color=C_MUTED,
                         fontsize=9, ha="left", va="center")
            ax_info.text(0.37, yp, val, color=C_SUBTLE,
                         fontsize=9, ha="left", va="center")

        ax_info.axhline(0.27, 0.05, 0.95, color=BG_BORDER, linewidth=1.2)
        ax_info.text(0.5, 0.21, "SYSTEMSTEUERUNG", color=C_MUTED,
                     fontsize=8, ha="center", va="center")

        # Buttons berechnen (in absoluten Figure-Coords, innerhalb der linken Hälfte)
        lft_x = CONT_X + 0.015
        btn_y_abs = CONT_Y + 0.045
        btn_h_abs = 0.090

        bx_sd = fig.add_axes([lft_x,        btn_y_abs, 0.165, btn_h_abs])
        bx_rs = fig.add_axes([lft_x + 0.180, btn_y_abs, 0.165, btn_h_abs])

        btn_sd = Button(bx_sd, "[X]  Herunterfahren", color="#3d1515", hovercolor=C_RED)
        btn_rs = Button(bx_rs, "[>]  Neustart",       color="#15301a", hovercolor=C_GREEN)
        for btn, col in ((btn_sd, C_RED), (btn_rs, C_GREEN)):
            btn.label.set_fontsize(9)
            btn.label.set_color(col)
        content_axes.extend([bx_sd, bx_rs])
        content_btns.extend([btn_sd, btn_rs])

        btn_sd.on_clicked(lambda e: (
            print("[System] Fahre herunter..."),
            subprocess.Popen(["sudo", "shutdown", "-h", "now"])
        ))
        btn_rs.on_clicked(lambda e: (
            print("[System] Neustart Dashboard..."),
            os.execv(__import__("sys").executable,
                     [__import__("sys").executable] + __import__("sys").argv)
        ))

        # ── Erinnerungen ─────────────────────────────────────────────────
        data = lade_erinnerungen()
        ax_memo.text(0.5, 0.93, "ERINNERUNGEN & NOTIZEN", color=C_ORANGE,
                     fontsize=13, fontweight="bold", ha="center", va="center")
        ax_memo.axhline(0.86, 0.05, 0.95, color=BG_BORDER, linewidth=1.2)

        yy = 0.79
        ax_memo.text(0.06, yy, "Wochentag", color=C_MUTED, fontsize=8,
                     fontweight="bold", ha="left", va="center")
        ax_memo.text(0.48, yy, "Aufgabe", color=C_MUTED, fontsize=8,
                     fontweight="bold", ha="left", va="center")
        yy -= 0.07

        for er in data.get("erinnerungen", []):
            if yy < 0.42:
                break
            ax_memo.text(0.06, yy, er.get("wochentag", ""),
                         color=C_TEXT, fontsize=9, ha="left", va="center")
            ax_memo.text(0.48, yy, er.get("text", ""),
                         color=C_SUBTLE, fontsize=9, ha="left", va="center")
            yy -= 0.09

        notizen = data.get("notizen", [])
        if notizen:
            ax_memo.axhline(yy - 0.02, 0.05, 0.95, color=BG_BORDER, linewidth=1.0)
            yy -= 0.10
            ax_memo.text(0.5, yy, "Hinweise", color=C_MUTED, fontsize=8,
                         fontweight="bold", ha="center", va="center")
            yy -= 0.09
            for notiz in notizen:
                if yy < 0.04:
                    break
                ax_memo.text(0.06, yy, f"> {notiz}", color=C_SUBTLE,
                             fontsize=9, ha="left", va="center")
                yy -= 0.09

    # ── Animations-Loop ────────────────────────────────────────────────────
    def animate(frame):
        # Nur Stunde:Minute – loest das Ladesymbol-Problem
        jetzt = datetime.now().strftime("%d.%m.%Y   |   %H:%M")
        uhr_text.set_text(f"SUPRA SCI-FI HOME 8000   |   {jetzt}")
        if aktiver_tab == "live":
            update_live()

    # Startzustand
    build_live()
    update_tab_btns()

    fig.canvas.mpl_connect("close_event", lambda e: __import__("sys").exit(0))
    ani = animation.FuncAnimation(
        fig, animate,
        interval=UPDATE_INTERVAL,   # 30 Sekunden
        cache_frame_data=False
    )
    plt.show()

# ─── Start ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()

    vorwerte = get_last_values()
    for sid, werte in vorwerte.items():
        if sid in sensor_daten:
            sensor_daten[sid].update(werte)
        else:
            sensor_daten[sid] = werte
    if vorwerte:
        print(f"[DB] {len(vorwerte)} Sensor(en) vorgeladen.")

    t = threading.Thread(target=mqtt_thread, daemon=True)
    t.start()

    try:
        erstelle_dashboard()
    except KeyboardInterrupt:
        print("\n[System] Beendet.")
        __import__("sys").exit(0)