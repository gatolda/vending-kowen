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

    # Crear el relé y activarlo
    relay = OutputDevice(gpio, active_high=True, initial_value=False)

    print(f"=== CH{ch} — {desc} (GPIO {gpio}) ===")
    relay.on()
    print(f"  Relé ACTIVO. Ctrl+C para desactivar y salir.\n")

    try:
        start = time.time()
        while True:
            elapsed = int(time.time() - start)
            mins, secs = divmod(elapsed, 60)
            print(f"\r  Tiempo activo: {mins:02d}:{secs:02d}", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[!] Desactivando relé.")
    finally:
        relay.off()
        relay.close()
        print("Cerrado.")

if __name__ == "__main__":
    main()
