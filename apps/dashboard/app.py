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
from gpiozero import OutputDevice
from datetime import datetime
import threading
import time
import json
import os

app = Flask(__name__)

# ============================================
# CONFIGURACIÓN HARDWARE
# ============================================

# Canales del módulo principal (active-LOW)
RELAY_CHANNELS = {
    1: (16, "EV #3 llenado botellón"),
    2: (19, "Bomba despacho 220V"),
    # 3: DAÑADO
    4: (22, "EV #2 salida RO"),
    5: (23, "Lámpara UV"),
    6: (24, "Generador ozono"),
    7: (4,  "EV #1 entrada bombas RO"),
    8: (7,  "Reserva"),
}

ACTIVE_HIGH = False  # módulo es active-LOW

# Tiempos de transición seguros
UV_LEAD = 0.5
PUMP_LEAD = 1.0
EV_CLOSE_FIRST = 0.3
PUMP_OFF_DELAY = 1.0
PRESSURE_RELIEF = 1.0
FLUSH_TIME = 15.0
MAX_PRODUCTION_TIME = 300.0  # 5 min safety timeout

# ============================================
# ESTADO GLOBAL
# ============================================

relays = {}                    # ch → OutputDevice
events = []                    # log de eventos
current_operation = None       # nombre de la operación en curso
operation_thread = None        # thread de la operación actual
stop_event = threading.Event() # señal para abortar

START_TIME = datetime.now()


# ============================================
# INICIALIZACIÓN
# ============================================

def init_gpio():
    """Crea OutputDevices para todos los canales. Todos inician OFF."""
    for ch, (gpio, _) in RELAY_CHANNELS.items():
        relays[ch] = OutputDevice(gpio, active_high=ACTIVE_HIGH, initial_value=False)
    log_event("Sistema iniciado", "ok")


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
        # UV ON
        relays[5].on()
        if stop_event.wait(UV_LEAD): return

        # Bomba despacho ON
        relays[2].on()
        if stop_event.wait(PUMP_LEAD): return

        # EV #3 OPEN
        relays[1].on()
        if stop_event.wait(seconds): return

        # Cierre seguro
        relays[1].off()
        if stop_event.wait(EV_CLOSE_FIRST): return

        relays[2].off()
        if stop_event.wait(PUMP_OFF_DELAY): return

        relays[5].off()

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
        # EV #2 abre (libera presión)
        relays[4].on()
        if stop_event.wait(PRESSURIZE_RELIEF := PRESSURE_RELIEF): return

        # Bombas ON
        relays[7].on()
        if stop_event.wait(FLUSH_TIME): return

        # Apagar bombas
        relays[7].off()
        if stop_event.wait(PUMP_OFF_DELAY): return

        # Cerrar EV #2
        relays[4].off()

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
        # Flush
        relays[4].on()
        if stop_event.wait(PRESSURE_RELIEF): return

        relays[7].on()
        if stop_event.wait(FLUSH_TIME): return

        # Cierra flush, entra a producción
        relays[4].off()
        log_event("Fase producción activa", "info")

        # Wait until stop_event or timeout
        if stop_event.wait(MAX_PRODUCTION_TIME):
            log_event("Producción detenida manualmente", "warn")
        else:
            log_event(f"Producción cortada por timeout ({MAX_PRODUCTION_TIME/60:.0f} min)", "warn")

        relays[7].off()

    except Exception as e:
        log_event(f"Error en producción: {e}", "err")
    finally:
        all_relays_off()
        current_operation = None


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
        },
        "relays": {
            ch: {
                "active": r.is_active,
                "description": RELAY_CHANNELS[ch][1],
            }
            for ch, r in relays.items()
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
    log_event("STOP solicitado", "warn")
    stop_event.set()
    all_relays_off()
    log_event("Todos los relés apagados", "ok")
    return jsonify({"status": "stopped"})


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    init_gpio()
    try:
        app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
    finally:
        all_relays_off()
        for r in relays.values():
            try:
                r.close()
            except Exception:
                pass
