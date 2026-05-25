#!/usr/bin/env python3
"""
Abre/mantiene activo un relé del módulo principal manualmente.
Útil para tareas de mantenimiento: lavado de filtros, pruebas individuales, etc.

El relé queda activo hasta que presiones Ctrl+C.

Uso:
    python3 scripts/manual_relay.py <canal>

Canales del módulo principal:
    1 → EV #3 llenado botellón     (GPIO 16)
    2 → Bomba despacho 220V        (GPIO 19)
    3 → EV #1 entrada bombas RO    (GPIO 27)  ← lavado pre-filtros
    4 → EV #2 salida RO / flush    (GPIO 22)
    5 → Lámpara UV                 (GPIO 23)
    6 → Generador ozono            (GPIO 24)
    7 → Transformador 24V (RO)     (GPIO  4)
    8 → Reserva                    (GPIO  7)

Ejemplos:
    python3 scripts/manual_relay.py 3      # abre EV #1 para lavar filtros
    python3 scripts/manual_relay.py 5      # prende UV solo

Salir y desactivar: Ctrl+C
"""

from gpiozero import OutputDevice
import time
import signal
import sys

CHANNELS = {
    1: (16, "EV #3 llenado botellón"),
    2: (19, "Bomba despacho 220V"),
    3: (27, "EV #1 entrada bombas RO"),
    4: (22, "EV #2 salida RO / flush"),
    5: (23, "Lámpara UV"),
    6: (24, "Generador ozono"),
    7: (4,  "Transformador 24V (bombas RO)"),
    8: (7,  "Reserva"),
}

ACTIVE_HIGH = True

device = None

def cleanup(signum=None, frame=None):
    print("\n[!] Cerrando relé.")
    if device:
        device.off()
        device.close()
    sys.exit(0)

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    try:
        ch = int(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' no es un número válido")
        sys.exit(1)

    if ch not in CHANNELS:
        print(f"Error: canal {ch} no existe. Válidos: 1-8")
        sys.exit(1)

    gpio, desc = CHANNELS[ch]

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    global device
    device = OutputDevice(gpio, active_high=ACTIVE_HIGH, initial_value=False)

    print(f"=== Activando CH{ch} ===")
    print(f"  Carga: {desc}")
    print(f"  GPIO:  {gpio}")
    print(f"  Estado: ACTIVO (relé ON)")
    print()
    print("⚠️  Ctrl+C para desactivar y salir.")
    print()

    device.on()

    try:
        start = time.time()
        while True:
            elapsed = int(time.time() - start)
            mins, secs = divmod(elapsed, 60)
            print(f"\r  Tiempo activo: {mins:02d}:{secs:02d}", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()
