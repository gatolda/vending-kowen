#!/usr/bin/env python3
"""
Abre/mantiene activo un relé del módulo principal manualmente.

Uso:
    python3 scripts/manual_relay.py <canal 1-8>

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

    ch = int(sys.argv[1])
    if ch not in CHANNELS:
        print(f"Canal {ch} inválido. Válidos: 1-8")
        sys.exit(1)

    gpio, desc = CHANNELS[ch]

    print(f"\n[DEBUG] Iniciando con GPIO={gpio}, CH={ch}, desc='{desc}'")
    print(f"[DEBUG] Creando OutputDevice...")
    relay = OutputDevice(gpio, active_high=True, initial_value=False)
    print(f"[DEBUG] Creado. value={relay.value}  is_active={relay.is_active}")

    print(f"\n=== CH{ch} — {desc} (GPIO {gpio}) ===")
    print(f"[DEBUG] Llamando relay.on()...")
    relay.on()
    print(f"[DEBUG] Después de .on(): value={relay.value}  is_active={relay.is_active}")
    print(f"  → Si is_active=True pero NO clickea: problema hardware (cable IN suelto)")
    print(f"  → Si is_active=False: bug software (no llegó a .on())")

    print(f"\n  Relé ACTIVO. Ctrl+C para desactivar y salir.\n")

    try:
        start = time.time()
        while True:
            elapsed = int(time.time() - start)
            mins, secs = divmod(elapsed, 60)
            # mostrar también el estado en cada tick (debug)
            print(f"\r  Tiempo: {mins:02d}:{secs:02d}  value={relay.value}  active={relay.is_active}",
                  end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[!] Desactivando relé.")
    finally:
        relay.off()
        relay.close()
        print("Cerrado.")

if __name__ == "__main__":
    main()
