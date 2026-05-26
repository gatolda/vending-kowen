#!/usr/bin/env python3
"""
fill_bottle.py — Ciclo de llenado de botellón (DISPENSING).

Sin caudalímetro: el corte de despacho es por tiempo configurable.
Sin sensor de pago: arranca apenas se ejecuta el script.

Secuencia (siguiendo docs/logica_operacion.md):
    t=0.0s   CH5 (UV) → ON                 (esterilización en línea)
    t=0.5s   CH2 (Bomba despacho) → ON     (presurizar línea)
    t=1.0s   CH1 (EV #3) → OPEN            (apertura al cliente)
             ... despacho por N segundos ...
    t=N+1.0s CH1 (EV #3) → CLOSE           (cerrar primero)
    t=N+1.3s CH2 (Bomba despacho) → OFF    (luego apagar bomba)
    t=N+2.3s CH5 (UV) → OFF                (margen para esterilizar último flujo)

Mapeo:
    CH1 (GPIO 16) → EV #3 llenado botellón
    CH2 (GPIO 19) → Bomba despacho 220V
    CH5 (GPIO 23) → Lámpara UV

Uso:
    python3 scripts/fill_bottle.py            # despacho por 5 segundos (default)
    python3 scripts/fill_bottle.py 10         # despacho por 10 segundos
    python3 scripts/fill_bottle.py 30         # despacho por 30 segundos

Emergencia: Ctrl+C apaga todo inmediato.

Pre-requisitos del operador (vos):
- Verificar que el tanque tenga agua (mirar nivel)
- Botellón posicionado bajo la boca de despacho
- Si Ctrl+C → desconectar 220V por seguridad
"""

import signal
import sys
import time
from gpiozero import OutputDevice

# Canales sanos — crear todos al inicio
CHANNELS = {
    1: 16,    # EV #3 llenado botellón
    2: 19,    # Bomba despacho 220V
    # 3: DAÑADO
    4: 22,    # EV #2 (no usado aquí, pero inicializado)
    5: 23,    # UV
    6: 24,    # Ozono (no usado aquí)
    7: 4,     # EV #1 (no usado aquí)
    8: 7,     # Reserva
}

ACTIVE_HIGH = False     # Módulo es active-LOW

# Tiempos de transición seguros
UV_LEAD = 0.5           # UV se prende antes que bomba
PUMP_LEAD = 1.0         # bomba se prende antes que EV
EV_CLOSE_FIRST = 0.3    # EV cierra antes que bomba
PUMP_OFF_DELAY = 1.0    # margen UV después de bomba apagada

# Default si no se pasa argumento
DEFAULT_DISPENSE_TIME = 5.0
MAX_DISPENSE_TIME = 60.0   # safety: máximo absoluto

devices = {}


def cleanup(signum=None, frame=None):
    print("\n\n[!] EMERGENCIA — Apagando todo inmediato.")
    for d in devices.values():
        try:
            d.off()
            d.close()
        except Exception:
            pass
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Parse tiempo de despacho
    dispense_time = DEFAULT_DISPENSE_TIME
    if len(sys.argv) > 1:
        try:
            dispense_time = float(sys.argv[1])
        except ValueError:
            print(f"Error: '{sys.argv[1]}' no es un número válido")
            sys.exit(1)

    if dispense_time > MAX_DISPENSE_TIME:
        print(f"⚠️  Tiempo {dispense_time}s excede máximo {MAX_DISPENSE_TIME}s. Capeando a {MAX_DISPENSE_TIME}s")
        dispense_time = MAX_DISPENSE_TIME

    print(f"=== Llenado de botellón ({dispense_time:.1f}s de despacho) ===")
    print("Iniciando en 2 segundos... (Ctrl+C para cancelar)")
    time.sleep(2)

    # Crear OutputDevices para todos los canales sanos
    print("\n[Init] Configurando relés (todos OFF)...")
    for ch, gpio in CHANNELS.items():
        devices[ch] = OutputDevice(gpio, active_high=ACTIVE_HIGH, initial_value=False)
        time.sleep(0.05)

    ev3 = devices[1]
    pump = devices[2]
    uv = devices[5]

    try:
        # ═══ Fase 1: UV ON ═══
        print(f"\nt=0.0s   CH5 (UV) → ON          (esterilización en línea)")
        uv.on()
        time.sleep(UV_LEAD)

        # ═══ Fase 2: Bomba ON ═══
        print(f"t={UV_LEAD:.1f}s   CH2 (Bomba) → ON       (presurizar)")
        pump.on()
        time.sleep(PUMP_LEAD)

        # ═══ Fase 3: EV #3 OPEN — despacho ═══
        print(f"t={UV_LEAD + PUMP_LEAD:.1f}s   CH1 (EV #3) → OPEN     (agua al cliente)")
        ev3.on()

        # Cuenta regresiva de despacho
        print(f"\n  Despachando {dispense_time:.1f}s...\n")
        start = time.time()
        while True:
            elapsed = time.time() - start
            if elapsed >= dispense_time:
                break
            remaining = dispense_time - elapsed
            print(f"\r  Despacho: {remaining:5.1f}s restantes", end="", flush=True)
            time.sleep(0.1)
        print()

        # ═══ Fase 4: Cierre seguro (orden inverso) ═══
        print(f"\nt={UV_LEAD + PUMP_LEAD + dispense_time:.1f}s   CH1 (EV #3) → CLOSE    (cerrar salida)")
        ev3.off()
        time.sleep(EV_CLOSE_FIRST)

        print(f"t={UV_LEAD + PUMP_LEAD + dispense_time + EV_CLOSE_FIRST:.1f}s   CH2 (Bomba) → OFF      (parar bomba)")
        pump.off()
        time.sleep(PUMP_OFF_DELAY)

        print(f"t={UV_LEAD + PUMP_LEAD + dispense_time + EV_CLOSE_FIRST + PUMP_OFF_DELAY:.1f}s   CH5 (UV) → OFF")
        uv.off()

        print(f"\n=== Llenado completado ===")

    except KeyboardInterrupt:
        cleanup()
    finally:
        # Asegurar TODO apagado
        for d in devices.values():
            try:
                d.off()
                d.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
