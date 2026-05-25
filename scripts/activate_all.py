#!/usr/bin/env python3
"""
Activa los 8 canales del módulo de relés SIMULTÁNEAMENTE
y los deja activos hasta Ctrl+C.

Útil para medir voltaje bajo carga máxima.

Uso:
    python3 scripts/activate_all.py
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
    relays = {}

    print("=== Activando los 8 canales simultáneamente ===\n")

    for ch, (gpio, desc) in CHANNELS.items():
        relays[ch] = OutputDevice(gpio, active_high=True, initial_value=False)
        relays[ch].on()
        print(f"  CH{ch} ON (GPIO {gpio}) — {desc}")

    print("\n⚠️  Los 8 relés deberían estar activos. Medí voltaje VCC↔GND del módulo.")
    print("    Ctrl+C para desactivar todos.\n")

    try:
        start = time.time()
        while True:
            elapsed = int(time.time() - start)
            mins, secs = divmod(elapsed, 60)
            print(f"\r  Tiempo activo: {mins:02d}:{secs:02d}", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[!] Desactivando todos los relés.")
    finally:
        for r in relays.values():
            try:
                r.off()
                r.close()
            except Exception:
                pass
        print("Todos OFF.")

if __name__ == "__main__":
    main()
