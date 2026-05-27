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

# Canales — formato: (GPIO, descripción, módulo)
# Módulo "main" = módulo 8ch principal
# Módulo "pump" = módulo 2ch nuevo (controla contactores)
# Mapeo actualizado 2026-05-27
RELAY_CHANNELS = {
    # ── Módulo principal 8ch ──
    1:  (16, "Luz publicidad frontal", "main"),
    2:  (19, "Generador ozono", "main"),
    # 3: DAÑADO
    4:  (22, "EV #2 salida RO", "main"),
    5:  (23, "Libre (UV pendiente)", "main"),
    6:  (24, "EV #3 llenado botellón", "main"),
    7:  (4,  "EV #1 entrada RO", "main"),
    8:  (7,  "Reserva", "main"),
    # ── Módulo 2ch nuevo (drives contactores) ──
    9:  (9,  "Bomba despacho (contactor)", "pump"),
    10: (10, "Bombas RO (contactor)", "pump"),
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
    for ch, (gpio, _, _) in RELAY_CHANNELS.items():
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
        # NOTA: UV pendiente de asignación
        # Bomba despacho via contactor (CH9 del módulo 2ch)
        relays[9].on()
        if stop_event.wait(PUMP_LEAD): return

        # EV #3 llenado (CH6 módulo principal)
        relays[6].on()
        if stop_event.wait(seconds): return

        # Cierre seguro (orden inverso)
        relays[6].off()
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
        # EV #2 abre (libera presión)
        relays[4].on()
        if stop_event.wait(PRESSURE_RELIEF): return

        # EV #1 entrada abre (CH7)
        relays[7].on()
        if stop_event.wait(0.5): return

        # Bombas RO ON via contactor (CH10 del módulo 2ch)
        relays[10].on()
        if stop_event.wait(FLUSH_TIME): return

        # Apagar bombas
        relays[10].off()
        if stop_event.wait(PUMP_OFF_DELAY): return

        # Cerrar EV #1
        relays[7].off()
        if stop_event.wait(0.3): return

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
        # Fase flush: EV #2 abre, EV #1 abre, bombas arrancan
        relays[4].on()  # EV #2 abre (libera presión inicial)
        if stop_event.wait(PRESSURE_RELIEF): return

        relays[7].on()  # EV #1 entrada abre
        if stop_event.wait(0.5): return

        relays[10].on()  # Bombas RO ON via contactor
        log_event("Bombas RO encendidas (modo flush)", "info")
        if stop_event.wait(FLUSH_TIME): return

        # Fase producción: cerrar EV #2 (agua va al tanque), bombas siguen
        relays[4].off()
        log_event("Fase producción activa (agua al tanque)", "info")

        # Esperar stop o timeout
        if stop_event.wait(MAX_PRODUCTION_TIME):
            log_event("Producción detenida manualmente", "warn")
        else:
            log_event(f"Producción cortada por timeout ({MAX_PRODUCTION_TIME/60:.0f} min)", "warn")

        # Apagar todo en orden seguro
        relays[10].off()  # Bombas primero
        time.sleep(0.5)
        relays[7].off()   # EV #1 cierra

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
                "module": RELAY_CHANNELS[ch][2],  # "main" o "pump"
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
    try:
        app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
    finally:
        all_relays_off()
        for r in relays.values():
            try:
                r.close()
            except Exception:
                pass
