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

app = Flask(__name__)

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

# ============================================
# ESTADO GLOBAL
# ============================================

relays = {}                    # ch → OutputDevice
sensors = {}                   # nombre → Button
events = []                    # log de eventos
current_operation = None       # nombre de la operación en curso
operation_thread = None        # thread de la operación actual
stop_event = threading.Event() # señal para abortar
auto_enabled = False           # modo automático (autollenado por sensores)

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
    """True si el sensor está 'activo' (agua presente / presión OK), False si no, None si no hay lectura."""
    dev = sensors.get(name)
    if dev is None:
        return None
    return dev.is_pressed == SENSORS[name]["active_when_pressed"]


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


# ============================================
# OPERACIONES (corren en thread separado)
# ============================================

def run_fill_bottle(seconds):
    global current_operation
    current_operation = f"Llenando botellón ({seconds}s)"
    log_event(f"Llenado iniciado ({seconds}s)", "ok")

    try:
        # Bomba de llenado via contactor (CH9 del módulo 2ch — asumido)
        relays[9].on()
        if stop_event.wait(PUMP_LEAD): return

        # EV llenado botellón (CH4 módulo principal)
        relays[4].on()
        if stop_event.wait(seconds): return

        # Cierre seguro (orden inverso)
        relays[4].off()
        if stop_event.wait(EV_CLOSE_FIRST): return

        relays[9].off()

        log_event(f"Llenado completado ({seconds}s)", "ok")

    except Exception as e:
        log_event(f"Error en llenado: {e}", "err")
    finally:
        all_relays_off()
        current_operation = None


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
        all_relays_off()
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
        all_relays_off()
        current_operation = None


# ============================================
# MODO AUTOMÁTICO (autollenado por sensores)
# ============================================

def run_auto_production():
    """Producción para autollenado: corre hasta MÁXIMO lleno, timeout, o pérdida de presión.
    Si NO llega al máximo (timeout/sin presión), desactiva el modo auto para no ciclar en seco."""
    global current_operation, auto_enabled
    current_operation = "Autollenado (producción)"
    log_event("Autollenado: producción iniciada", "ok")
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
            if sensor_active("PRESOSTATO") is False:
                log_event("Autollenado: SIN PRESIÓN de red, abortando", "warn")
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
        all_relays_off()
        current_operation = None
        if not reached_max:
            auto_enabled = False
            log_event("Modo auto DESACTIVADO (producción no completó el llenado)", "warn")


def auto_loop():
    """Loop de control del modo automático (mantener tanque lleno).
    Corre siempre en background; sólo actúa cuando auto_enabled está activo
    y no hay otra operación en curso. Produce apenas el MÁXIMO deja de marcar lleno."""
    last_no_pressure_log = 0.0
    while True:
        time.sleep(2)
        if not auto_enabled or current_operation is not None:
            continue

        max_full = sensor_active("MAX")
        if max_full is not False:
            continue  # ya está lleno (o sin lectura) → nada que hacer

        # Tanque por debajo del máximo → querer rellenar
        if sensor_active("PRESOSTATO") is False:
            now = time.time()
            if now - last_no_pressure_log > 30:
                log_event("Autollenado en espera: tanque no lleno pero sin presión de red", "warn")
                last_no_pressure_log = now
            continue

        # Condiciones OK → arrancar ciclo de producción
        stop_event.clear()
        run_auto_production()


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
                "active": (sensors[name].is_pressed == cfg["active_when_pressed"]
                           if sensors.get(name) else None),
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
    global operation_thread

    if current_operation is not None:
        return jsonify({"error": f"Operación en curso: {current_operation}"}), 409

    data = request.get_json() or {}
    seconds = float(data.get("seconds", 5))
    seconds = max(1, min(60, seconds))

    stop_event.clear()
    operation_thread = threading.Thread(target=run_fill_bottle, args=(seconds,), daemon=True)
    operation_thread.start()
    return jsonify({"status": "started", "operation": f"fill_{seconds}s"})


@app.route("/api/operation/flush", methods=["POST"])
def op_flush():
    global operation_thread

    if current_operation is not None:
        return jsonify({"error": f"Operación en curso: {current_operation}"}), 409

    stop_event.clear()
    operation_thread = threading.Thread(target=run_flush, daemon=True)
    operation_thread.start()
    return jsonify({"status": "started", "operation": "flush"})


@app.route("/api/operation/produce", methods=["POST"])
def op_produce():
    global operation_thread

    if current_operation is not None:
        return jsonify({"error": f"Operación en curso: {current_operation}"}), 409

    stop_event.clear()
    operation_thread = threading.Thread(target=run_produce_water, daemon=True)
    operation_thread.start()
    return jsonify({"status": "started", "operation": "produce"})


@app.route("/api/stop", methods=["POST"])
def op_stop():
    global auto_enabled
    log_event("STOP solicitado", "warn")
    auto_enabled = False  # emergencia corta también el modo automático
    stop_event.set()
    all_relays_off()
    log_event("Todos los relés apagados", "ok")
    return jsonify({"status": "stopped"})


@app.route("/api/auto/toggle", methods=["POST"])
def auto_toggle():
    global auto_enabled
    auto_enabled = not auto_enabled
    if auto_enabled:
        log_event("Modo automático ACTIVADO", "ok")
    else:
        log_event("Modo automático DESACTIVADO", "warn")
        stop_event.set()  # detiene producción auto en curso si la hay
    return jsonify({"auto_enabled": auto_enabled})


@app.route("/api/relay/<int:ch>/toggle", methods=["POST"])
def relay_toggle(ch):
    """Activa/desactiva un relé manualmente. Solo si no hay operación en curso."""
    if current_operation is not None:
        return jsonify({"error": f"Operación en curso: {current_operation}"}), 409

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

if __name__ == "__main__":
    init_gpio()
    threading.Thread(target=auto_loop, daemon=True).start()
    try:
        app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
    finally:
        all_relays_off()
        for r in relays.values():
            try:
                r.close()
            except Exception:
                pass
