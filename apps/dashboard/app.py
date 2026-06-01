#!/usr/bin/env python3
"""
Dashboard Kowen — Flask app para control y monitoreo de la máquina.

Corre en la Pi. Accesible desde cualquier dispositivo en la misma WiFi.

Uso:
    cd ~/vending-kowen/apps/dashboard
    python3 app.py

Acceso:
    http://raspberrypivendingagua.local:8000
    o http://<IP_DE_LA_PI>:8000
"""

from flask import Flask, render_template, jsonify, request
from gpiozero import OutputDevice, Button
from datetime import datetime
import threading
import time
import json
import os
import signal
import sys

import cloud_sync  # sincronización best-effort a Supabase (no bloquea el control local)


def _load_dotenv(path):
    """Carga un .env simple (KEY=VALUE por línea) en os.environ. Sin dependencias.
    Las variables ya presentes en el entorno tienen prioridad (no se pisan)."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())
    except FileNotFoundError:
        pass


# Cargar credenciales del .env (junto a este archivo) antes de usarlas
_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

app = Flask(__name__)

# Cada cuánto mandar un heartbeat de estado a la nube (seg)
HEARTBEAT_INTERVAL = 60.0

# ============================================
# CONFIGURACIÓN HARDWARE
# ============================================

# Canales — formato: (GPIO, descripción, módulo)
# Módulo "main" = módulo 8ch principal (reemplazado 2026-05-27, CH3 funciona)
# Módulo "pump" = módulo 2ch nuevo (controla contactores)
# Mapeo actualizado 2026-05-27
RELAY_CHANNELS = {
    # ── Módulo principal 8ch ──
    1:  (16, "Luz publicidad frontal", "main"),
    2:  (19, "Generador ozono", "main"),
    3:  (27, "EV entrada bombas RO", "main"),
    4:  (22, "EV llenado botellón", "main"),
    5:  (23, "EV flush salida", "main"),
    6:  (24, "Libre", "main"),
    7:  (4,  "Libre", "main"),
    8:  (7,  "Libre", "main"),
    # ── Módulo 2ch nuevo (drives contactores) ──
    # CH9  → pin físico 29 (GPIO 5) — IN1 del módulo = Bomba de llenado
    # CH10 → pin físico 31 (GPIO 6) — IN2 del módulo = Bombas RO
    9:  (5, "Bomba de llenado (contactor)", "pump"),
    10: (6, "Bombas RO (contactor)", "pump"),
}

ACTIVE_HIGH = False  # módulo es active-LOW

# Sensores digitales (flotadores + presostato)
# Button con pull_up interno: is_pressed=True cuando el pin va a GND.
# active = (is_pressed == active_when_pressed) → True significa "presente/OK" en ese nivel.
# GPIO 12 = flotador MÁXIMO, GPIO 18 = flotador MÍNIMO (re-swap tras recableado a 2 placas, verificado 2026-05-28).
# Polaridades OPUESTAS entre los dos flotadores (montaje/cableado distinto, verificado en campo):
#   MÁXIMO: agua presente (flotador arriba) = released → active_when_pressed=False
#   MÍNIMO: agua presente (flotador arriba) = pressed  → active_when_pressed=True
# Presostato: hay presión = pressed → active_when_pressed=True.
SENSORS = {
    "MAX": {
        "gpio": 12,
        "label": "Flotador máximo",
        "active_when_pressed": False,
        "text_active": "Lleno",
        "text_inactive": "No lleno",
        "alert_when_inactive": False,
    },
    "MIN": {
        "gpio": 18,
        "label": "Flotador mínimo",
        "active_when_pressed": True,
        "text_active": "Con agua",
        "text_inactive": "Vacío",
        "alert_when_inactive": True,
    },
    "PRESOSTATO": {
        "gpio": 13,
        "label": "Presión agua de red",
        "active_when_pressed": True,
        "text_active": "OK",
        "text_inactive": "Sin presión",
        "alert_when_inactive": True,
    },
}

# Tiempos de transición seguros
UV_LEAD = 0.5
PUMP_LEAD = 1.0
EV_CLOSE_FIRST = 0.3
PUMP_OFF_DELAY = 1.0
PRESSURE_RELIEF = 1.0
FLUSH_TIME = 15.0
MAX_PRODUCTION_TIME = 300.0  # 5 min safety timeout (producción manual)
AUTO_FILL_TIMEOUT = 1800.0   # 30 min backstop autollenado (corte real = sensor MÁXIMO; esto solo salta ante falla)
AUTO_REFILL_COOLDOWN = 180.0 # 3 min mínimo entre llenados auto (anti-rebote); se ignora si el nivel cae bajo el MÍNIMO
PRESSURE_LOSS_GRACE = 5.0    # seg sin presión continuos para declarar "sin presión" (ignora glitches/EMI)
PRESSURE_RECOVER_GRACE = 3.0 # seg con presión continuos para volver a declarar "con presión" (histéresis)

# ============================================
# ESTADO GLOBAL
# ============================================

relays = {}                    # ch → OutputDevice
sensors = {}                   # nombre → Button
events = []                    # log de eventos

# ── Carril PRODUCCIÓN (flush / produce / autollenado) — relés CH3, CH5, CH10 ──
current_operation = None       # nombre de la operación de producción en curso
operation_thread = None        # thread de producción
stop_event = threading.Event() # señal para abortar producción

# ── Carril DESPACHO (llenar botellón) — relés CH4, CH9 — concurrente con producción ──
dispense_active = None         # nombre del despacho en curso (o None)
dispense_thread = None         # thread de despacho
dispense_stop = threading.Event()  # señal para abortar despacho

auto_enabled = False           # modo automático (autollenado por sensores)
last_auto_fill_end = 0.0       # timestamp del último autollenado (para el cooldown anti-rebote)
pressure_ok = True             # estado debounced de presión de red (histéresis, lo mantiene sensor_monitor)
tank_full = False              # estado latcheado del flotador MÁXIMO para el display (el control usa la lectura raw)

# Relés de cada carril (para apagar solo lo propio sin pisar el otro carril)
PRODUCTION_CHANNELS = [3, 5, 10]
DISPENSE_CHANNELS = [4, 9]

START_TIME = datetime.now()


# ============================================
# INICIALIZACIÓN
# ============================================

def init_gpio():
    """Crea OutputDevices para todos los canales. Todos inician OFF."""
    for ch, (gpio, _, _) in RELAY_CHANNELS.items():
        relays[ch] = OutputDevice(gpio, active_high=ACTIVE_HIGH, initial_value=False)
    init_sensors()
    log_event("Sistema iniciado", "ok")


def init_sensors():
    """Crea Buttons para los sensores. Si alguno falla, lo deja en None (no crashea)."""
    for name, cfg in SENSORS.items():
        gpio = cfg["gpio"]
        try:
            sensors[name] = Button(gpio, pull_up=True)
        except Exception as e:
            sensors[name] = None
            log_event(f"Sensor {name} (GPIO {gpio}) no inicializó: {e}", "warn")


def sensor_active(name):
    """True si el sensor está 'activo' (agua presente / presión OK), False si no, None si no hay lectura.
    Lectura instantánea (raw). Para el presostato, el control usa el estado debounced (pressure_ok)."""
    dev = sensors.get(name)
    if dev is None:
        return None
    return dev.is_pressed == SENSORS[name]["active_when_pressed"]


def sensor_state(name):
    """Estado para MOSTRAR en el dashboard. Presostato = debounced (histéresis);
    máximo = latcheado (el flotador dispara muy breve); resto = raw.
    OJO: el control NO usa esto, usa sensor_active() (lectura real-time)."""
    if name == "PRESOSTATO":
        return pressure_ok if sensors.get(name) is not None else None
    if name == "MAX":
        return tank_full if sensors.get(name) is not None else None
    return sensor_active(name)


def log_event(message, level="info"):
    """Agrega un evento al log."""
    event = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "level": level,  # "ok" | "warn" | "err" | "info"
        "message": message,
    }
    events.append(event)
    # Mantener solo últimos 100
    if len(events) > 100:
        events.pop(0)
    print(f"[{event['timestamp']}] {level.upper()}: {message}")
    # Espejo a la nube (best-effort, no bloquea)
    cloud_sync.push_event(level, message)


def get_uptime():
    delta = datetime.now() - START_TIME
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes = remainder // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def all_relays_off():
    """Apaga TODOS los relés."""
    for r in relays.values():
        try:
            r.off()
        except Exception:
            pass


def channels_off(channels):
    """Apaga solo los relés de los canales indicados (no toca el otro carril)."""
    for ch in channels:
        try:
            relays[ch].off()
        except Exception:
            pass


# ============================================
# OPERACIONES (corren en thread separado)
# ============================================

def run_fill_bottle(seconds):
    # Carril DESPACHO — concurrente con producción. Usa dispense_stop y solo apaga CH4/CH9.
    global dispense_active, last_auto_fill_end
    dispense_active = f"Llenando botellón ({seconds}s)"
    log_event(f"Llenado iniciado ({seconds}s)", "ok")

    try:
        # Bomba de llenado via contactor (CH9 del módulo 2ch)
        relays[9].on()
        if dispense_stop.wait(PUMP_LEAD): return

        # EV llenado botellón (CH4 módulo principal)
        relays[4].on()
        if dispense_stop.wait(seconds): return

        # Cierre seguro (orden inverso)
        relays[4].off()
        if dispense_stop.wait(EV_CLOSE_FIRST): return

        relays[9].off()

        log_event(f"Llenado completado ({seconds}s)", "ok")

    except Exception as e:
        log_event(f"Error en llenado: {e}", "err")
    finally:
        channels_off(DISPENSE_CHANNELS)  # solo CH4/CH9, no toca la producción
        dispense_active = None
        # Tras despachar una recarga, resetear cooldown → la osmosis repone enseguida
        last_auto_fill_end = 0.0


def run_flush():
    global current_operation
    current_operation = "Flush en curso"
    log_event("Flush iniciado", "ok")

    try:
        # EV flush salida abre (CH5, libera presión)
        relays[5].on()
        if stop_event.wait(PRESSURE_RELIEF): return

        # EV entrada bombas RO abre (CH3)
        relays[3].on()
        if stop_event.wait(0.5): return

        # Bombas RO ON via contactor (CH10 del módulo 2ch — asumido)
        relays[10].on()
        if stop_event.wait(FLUSH_TIME): return

        # Apagar bombas
        relays[10].off()
        if stop_event.wait(PUMP_OFF_DELAY): return

        # Cerrar EV entrada RO
        relays[3].off()
        if stop_event.wait(0.3): return

        # Cerrar EV flush salida
        relays[5].off()

        log_event("Flush completado", "ok")

    except Exception as e:
        log_event(f"Error en flush: {e}", "err")
    finally:
        channels_off(PRODUCTION_CHANNELS)
        current_operation = None


def run_produce_water():
    global current_operation
    current_operation = "Producción de agua (5 min máximo)"
    log_event("Producción iniciada (timeout 5min)", "ok")

    try:
        # Fase flush: EV salida abre, EV entrada abre, bombas arrancan
        relays[5].on()  # EV flush salida abre (libera presión inicial)
        if stop_event.wait(PRESSURE_RELIEF): return

        relays[3].on()  # EV entrada bombas RO abre
        if stop_event.wait(0.5): return

        relays[10].on()  # Bombas RO ON via contactor
        log_event("Bombas RO encendidas (modo flush)", "info")
        if stop_event.wait(FLUSH_TIME): return

        # Fase producción: cerrar EV flush salida (agua va al tanque), bombas siguen
        relays[5].off()
        log_event("Fase producción activa (agua al tanque)", "info")

        # Esperar stop o timeout
        if stop_event.wait(MAX_PRODUCTION_TIME):
            log_event("Producción detenida manualmente", "warn")
        else:
            log_event(f"Producción cortada por timeout ({MAX_PRODUCTION_TIME/60:.0f} min)", "warn")

        # Apagar todo en orden seguro
        relays[10].off()  # Bombas primero
        time.sleep(0.5)
        relays[3].off()   # EV entrada cierra

    except Exception as e:
        log_event(f"Error en producción: {e}", "err")
    finally:
        channels_off(PRODUCTION_CHANNELS)
        current_operation = None


# ============================================
# MODO AUTOMÁTICO (autollenado por sensores)
# ============================================

def sensor_monitor():
    """Mantiene estados estables para el DISPLAY (no para el control):
    - Presostato: histéresis (pérdida PRESSURE_LOSS_GRACE seg / recuperación PRESSURE_RECOVER_GRACE seg)
      → pressure_ok. Evita que glitches/EMI del contactor flickeen el estado.
    - Máximo: latch → tank_full. El flotador dispara muy breve; sin latch el dashboard casi nunca
      lo muestra. Se enciende al tocar 'lleno', se apaga al arrancar un rellenado (run_auto_production)
      o si el nivel cae al MÍNIMO."""
    global pressure_ok, tank_full
    low_since = None
    high_since = None
    while True:
        time.sleep(0.5)
        # --- Presostato con histéresis ---
        raw = sensor_active("PRESOSTATO")
        if raw is not None:
            if raw:
                low_since = None
                if not pressure_ok:
                    if high_since is None:
                        high_since = time.time()
                    elif time.time() - high_since >= PRESSURE_RECOVER_GRACE:
                        pressure_ok = True
                        log_event("Presión de red restablecida", "ok")
            else:
                high_since = None
                if pressure_ok:
                    if low_since is None:
                        low_since = time.time()
                    elif time.time() - low_since >= PRESSURE_LOSS_GRACE:
                        pressure_ok = False
                        log_event("Presión de red perdida (sostenida)", "warn")
        # --- Latch del flotador máximo (para el display) ---
        if sensor_active("MAX") is True:
            tank_full = True
        elif sensor_active("MIN") is False:  # cayó al mínimo → definitivamente NO lleno
            tank_full = False


def run_auto_production():
    """Producción para autollenado: corre hasta MÁXIMO lleno, timeout, o pérdida de presión.
    Si NO llega al máximo (timeout/sin presión), desactiva el modo auto para no ciclar en seco."""
    global current_operation, auto_enabled, tank_full
    current_operation = "Autollenado (producción)"
    log_event("Autollenado: producción iniciada", "ok")
    tank_full = False  # estamos rellenando → el display deja de marcar "lleno" hasta tocar el máximo
    reached_max = False

    try:
        # Fase flush inicial
        relays[5].on()  # EV flush salida abre (libera presión)
        if stop_event.wait(PRESSURE_RELIEF): return
        relays[3].on()  # EV entrada RO abre
        if stop_event.wait(0.5): return
        relays[10].on()  # Bombas RO ON
        log_event("Autollenado: bombas RO ON (flush)", "info")
        if stop_event.wait(FLUSH_TIME): return

        # Fase producción: cerrar EV salida (agua al tanque)
        relays[5].off()
        log_event("Autollenado: producción al tanque", "info")

        # Corte REAL = sensor MÁXIMO. El backstop (30 min) solo salta ante falla.
        start = time.time()
        while time.time() - start < AUTO_FILL_TIMEOUT:
            if stop_event.wait(0.5):
                return
            if sensor_active("MAX"):
                reached_max = True
                mins = (time.time() - start) / 60
                log_event(f"Autollenado: tanque LLENO en {mins:.1f} min, parando", "ok")
                break
            # Presostato con histéresis (pressure_ok ya viene debounced del monitor)
            if not pressure_ok:
                log_event("Autollenado: sin presión de red (sostenida), abortando", "warn")
                break
        else:
            log_event(f"Autollenado: backstop {AUTO_FILL_TIMEOUT/60:.0f} min sin llegar a máximo (revisar flotador/fuga)", "warn")

        # Apagado seguro
        relays[10].off()
        time.sleep(0.5)
        relays[3].off()

    except Exception as e:
        log_event(f"Error en autollenado: {e}", "err")
    finally:
        channels_off(PRODUCTION_CHANNELS)
        current_operation = None
        if not reached_max:
            auto_enabled = False
            log_event("Modo auto DESACTIVADO (producción no completó el llenado)", "warn")


def heartbeat_loop():
    """Manda el estado actual a la nube cada HEARTBEAT_INTERVAL seg (best-effort)."""
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        try:
            cloud_sync.push_heartbeat({
                "tank_full": tank_full,
                "min_water": sensor_active("MIN"),
                "pressure_ok": pressure_ok,
                "auto_enabled": auto_enabled,
                "operation": current_operation or dispense_active,
            })
        except Exception:
            pass  # nunca dejar que el sync afecte nada


def auto_loop():
    """Loop de control del modo automático (mantener tanque lleno).
    Arranca apenas el MÁXIMO deja de marcar lleno y llena hasta el MÁXIMO.
    Cooldown anti-rebote entre llenados; se ignora si el nivel cae bajo el
    MÍNIMO (emergencia → rellena ya) o si se despachó una recarga (resetea cooldown).
    El MÍNIMO es solo alarma, no control normal."""
    global last_auto_fill_end
    last_no_pressure_log = 0.0
    while True:
        time.sleep(2)
        if not auto_enabled or current_operation is not None:
            continue

        if sensor_active("MAX") is not False:
            continue  # lleno (o sin lectura) → nada que hacer

        # No lleno → querer rellenar. Respetar cooldown salvo emergencia (bajo el mínimo).
        below_min = (sensor_active("MIN") is False)
        if not below_min and (time.time() - last_auto_fill_end < AUTO_REFILL_COOLDOWN):
            continue

        if not pressure_ok:  # estado debounced con histéresis
            now = time.time()
            if now - last_no_pressure_log > 30:
                log_event("Autollenado en espera: tanque no lleno pero sin presión de red", "warn")
                last_no_pressure_log = now
            continue

        # Condiciones OK → arrancar ciclo de producción
        if below_min:
            log_event("Autollenado: nivel bajo el MÍNIMO, rellenando (emergencia)", "warn")
        stop_event.clear()
        run_auto_production()
        last_auto_fill_end = time.time()


# ============================================
# ACCIONES (compartidas por endpoints HTTP y cola de comandos)
# Cada una devuelve (ok: bool, mensaje: str)
# ============================================

def start_dispense(seconds):
    global dispense_thread
    if dispense_active is not None:
        return False, f"Despacho en curso: {dispense_active}"
    seconds = max(1, min(60, int(float(seconds))))
    dispense_stop.clear()
    dispense_thread = threading.Thread(target=run_fill_bottle, args=(seconds,), daemon=True)
    dispense_thread.start()
    return True, f"Despacho iniciado ({seconds}s)"


def start_flush():
    global operation_thread
    if current_operation is not None:
        return False, f"Operación en curso: {current_operation}"
    stop_event.clear()
    operation_thread = threading.Thread(target=run_flush, daemon=True)
    operation_thread.start()
    return True, "Flush iniciado"


def start_produce():
    global operation_thread
    if current_operation is not None:
        return False, f"Operación en curso: {current_operation}"
    stop_event.clear()
    operation_thread = threading.Thread(target=run_produce_water, daemon=True)
    operation_thread.start()
    return True, "Producción iniciada"


def do_stop():
    global auto_enabled
    log_event("STOP solicitado", "warn")
    auto_enabled = False   # emergencia corta también el modo automático
    stop_event.set()       # corta producción
    dispense_stop.set()    # corta despacho
    all_relays_off()       # apaga TODO (ambos carriles)
    log_event("Todos los relés apagados", "ok")
    return True, "Todo apagado"


def set_auto(enabled):
    global auto_enabled
    if enabled and not auto_enabled:
        auto_enabled = True
        log_event("Modo automático ACTIVADO", "ok")
    elif not enabled and auto_enabled:
        auto_enabled = False
        log_event("Modo automático DESACTIVADO", "warn")
        stop_event.set()   # detiene producción auto en curso si la hay
    return True, f"Modo auto {'ON' if enabled else 'OFF'}"


# ============================================
# COLA DE COMANDOS (desde Supabase, escritos por el bot Telegram del VPS)
# ============================================

COMMAND_POLL_INTERVAL = 3.0


def dispatch_command(cmd, args):
    """Ejecuta un comando de la cola. Devuelve (ok, mensaje)."""
    if cmd == "fill":
        return start_dispense(args.get("seconds", 5))
    if cmd == "flush":
        return start_flush()
    if cmd == "produce":
        return start_produce()
    if cmd == "stop":
        return do_stop()
    if cmd == "auto_on":
        return set_auto(True)
    if cmd == "auto_off":
        return set_auto(False)
    return False, f"Comando desconocido: {cmd}"


def command_poller():
    """Consulta Supabase por comandos pendientes para esta máquina y los ejecuta.
    Best-effort: si no hay sync/credenciales, fetch devuelve [] y no hace nada."""
    while True:
        time.sleep(COMMAND_POLL_INTERVAL)
        try:
            cmds = cloud_sync.fetch_pending_commands()
        except Exception as e:
            print("command_poller fetch error:", e)
            continue
        for c in cmds:
            cmd = (c.get("command") or "").lower()
            args = c.get("args") or {}
            try:
                ok, msg = dispatch_command(cmd, args)
            except Exception as e:
                ok, msg = False, f"Error ejecutando: {e}"
            log_event(f"Comando remoto: {cmd} → {msg}", "info" if ok else "warn")
            cloud_sync.complete_command(c["id"], "done" if ok else "error", msg)


# ============================================
# ENDPOINTS
# ============================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify({
        "system": {
            "uptime": get_uptime(),
            "operation": current_operation,
            "dispense": dispense_active,
            "auto_enabled": auto_enabled,
        },
        "relays": {
            ch: {
                "active": r.is_active,
                "description": RELAY_CHANNELS[ch][1],
                "module": RELAY_CHANNELS[ch][2],  # "main" o "pump"
            }
            for ch, r in relays.items()
        },
        "sensors": {
            name: {
                "label": cfg["label"],
                "active": sensor_state(name),  # presostato = debounced; resto = raw
                "text_active": cfg["text_active"],
                "text_inactive": cfg["text_inactive"],
                "alert_when_inactive": cfg["alert_when_inactive"],
            }
            for name, cfg in SENSORS.items()
        },
        "events": events[-20:],
    })


@app.route("/api/operation/fill", methods=["POST"])
def op_fill():
    data = request.get_json() or {}
    ok, msg = start_dispense(data.get("seconds", 5))
    return jsonify({"status": "started", "message": msg}) if ok else (jsonify({"error": msg}), 409)


@app.route("/api/operation/flush", methods=["POST"])
def op_flush():
    ok, msg = start_flush()
    return jsonify({"status": "started", "message": msg}) if ok else (jsonify({"error": msg}), 409)


@app.route("/api/operation/produce", methods=["POST"])
def op_produce():
    ok, msg = start_produce()
    return jsonify({"status": "started", "message": msg}) if ok else (jsonify({"error": msg}), 409)


@app.route("/api/stop", methods=["POST"])
def op_stop():
    do_stop()
    return jsonify({"status": "stopped"})


@app.route("/api/auto/toggle", methods=["POST"])
def auto_toggle():
    set_auto(not auto_enabled)
    return jsonify({"auto_enabled": auto_enabled})


@app.route("/api/relay/<int:ch>/toggle", methods=["POST"])
def relay_toggle(ch):
    """Activa/desactiva un relé manualmente. Solo si no hay operación ni despacho en curso."""
    if current_operation is not None:
        return jsonify({"error": f"Operación en curso: {current_operation}"}), 409
    if dispense_active is not None:
        return jsonify({"error": f"Despacho en curso: {dispense_active}"}), 409

    if ch not in relays:
        return jsonify({"error": f"Canal {ch} no existe o está dañado"}), 404

    relay = relays[ch]
    desc = RELAY_CHANNELS[ch][1]

    # Si es del módulo 2ch (pump), confirmar acción para evitar arrancar bombas accidentales
    if relay.is_active:
        relay.off()
        log_event(f"CH{ch} ({desc}) apagado manualmente", "info")
        return jsonify({"channel": ch, "state": "off"})
    else:
        relay.on()
        log_event(f"CH{ch} ({desc}) encendido manualmente", "info")
        return jsonify({"channel": ch, "state": "on"})


# ============================================
# MAIN
# ============================================

def handle_sigterm(signum, frame):
    """systemd manda SIGTERM al parar/reiniciar el servicio. Por defecto Python no
    corre el finally con SIGTERM, así que lo convertimos en salida limpia → apaga relés."""
    log_event("SIGTERM recibido (systemd stop) — apagando relés", "warn")
    raise SystemExit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_sigterm)
    init_gpio()
    if cloud_sync.start():
        log_event(f"Sync a Supabase activo (máquina {cloud_sync.MACHINE_ID})", "ok")
        threading.Thread(target=command_poller, daemon=True).start()  # comandos remotos
    else:
        log_event("Sync a Supabase desactivado (sin credenciales)", "info")
    threading.Thread(target=sensor_monitor, daemon=True).start()
    threading.Thread(target=auto_loop, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    try:
        app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
    finally:
        all_relays_off()
        for r in relays.values():
            try:
                r.close()
            except Exception:
                pass
