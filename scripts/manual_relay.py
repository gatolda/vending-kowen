#!/usr/bin/env python3
"""
Abre/mantiene activo un relé del módulo principal manualmente.

⚠️  CH3 DAÑADO (no usar). Su función está en CH7.

Uso:
    python3 scripts/manual_relay.py <canal 1-8>

Mapeo canal → carga:
    CH1 → EV #3 llenado botellón     (GPIO 16)
    CH2 → Bomba despacho 220V        (GPIO 19)
    CH3 → ❌ DAÑADO                  (GPIO 27)
    CH4 → EV #2 salida RO / flush    (GPIO 22)
    CH5 → Lámpara UV                 (GPIO 23)
    CH6 → Generador ozono            (GPIO 24)
    CH7 → EV #1 entrada bombas RO    (GPIO  4)
    CH8 → Reserva                    (GPIO  7)

Salir y desactivar: Ctrl+C
"""

from gpiozero import OutputDevice
import time
import sys

CHANNELS = {
    1: (16, "EV #3 llenado botellón"),
    2: (19, "Bomba despacho 220V"),
    # 3: DAÑADO
    4: (22, "EV #2 salida RO / flush"),
    5: (23, "Lámpara UV"),
    6: (24, "Generador ozono"),
    7: (4,  "EV #1 entrada bombas RO"),
    8: (7,  "Reserva"),
}

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ch = int(sys.argv[1])
    if ch == 3:
        print("❌ CH3 está marcado como DAÑADO. Usá CH7 para EV #1 entrada bombas RO.")
        sys.exit(1)
    if ch not in CHANNELS:
        print(f"Canal {ch} inválido. Válidos: {list(CHANNELS.keys())}")
        sys.exit(1)

    gpio, desc = CHANNELS[ch]
    relay = OutputDevice(gpio, active_high=True, initial_value=False)

    print(f"\n=== CH{ch} — {desc} (GPIO {gpio}) ===")
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
