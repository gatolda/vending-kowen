#!/usr/bin/env python3
"""
flush.py — Test de flush: enciende bombas RO + abre EV #2.

Activa simultáneamente y mantiene activos hasta Ctrl+C:
    CH7 (GPIO 4)  → Bombas RO + EV #1 entrada
    CH4 (GPIO 22) → EV #2 salida / flush

Útil para hacer un lavado manual del sistema o probar el flujo de agua.

Uso:
    python3 scripts/flush.py

Detener: Ctrl+C (apaga todo de forma segura)
"""

import signal
import sys
import time
from gpiozero import OutputDevice

# Pines (igual mapping que test_all_channels.py)
PUMPS_GPIO = 4    # CH7 - Bombas RO + EV #1 entrada
EV2_GPIO = 22     # CH4 - EV #2 salida / flush

ACTIVE_HIGH = True

devices = []


def cleanup(signum=None, frame=None):
    print("\n\n[!] Deteniendo flush. Apagando todo.")
    for d in devices:
        try:
            d.off()
            d.close()
        except Exception:
            pass
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("=== Flush ===")
    print("Iniciando en 2 segundos... (Ctrl+C para cancelar)")
    time.sleep(2)

    pumps = OutputDevice(PUMPS_GPIO, active_high=ACTIVE_HIGH, initial_value=False)
    ev2 = OutputDevice(EV2_GPIO, active_high=ACTIVE_HIGH, initial_value=False)
    devices.extend([pumps, ev2])

    print("\nCH7 (bombas + EV #1) → ON")
    pumps.on()
    time.sleep(0.5)

    print("CH4 (EV #2 flush)     → ON")
    ev2.on()

    print("\n*** Flush en curso ***")
    print("*** Ctrl+C para detener ***\n")

    try:
        start = time.time()
        while True:
            elapsed = int(time.time() - start)
            mins, secs = divmod(elapsed, 60)
            print(f"\r  Tiempo: {mins:02d}:{secs:02d}", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
