#!/usr/bin/env python3
"""
test_ch7_long.py — Mantener CH7 activo por 30 segundos.

Diagnóstico: queremos saber si CH7 puede sostenerse encendido por más de
2 segundos cuando es la ÚNICA carga activa.

Si CH7 se apaga sola → problema de voltaje / hardware
Si CH7 se mantiene 30s → el problema es el script anterior (concurrencia)
"""

import signal
import sys
import time
from gpiozero import OutputDevice

PUMPS_GPIO = 4  # CH7

def cleanup(signum=None, frame=None):
    print("\n[!] Cleanup.")
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, cleanup)

    print("=== Test CH7 sostenido 30s ===")
    print("Iniciando en 2 segundos...")
    time.sleep(2)

    relay = OutputDevice(PUMPS_GPIO, active_high=True, initial_value=False)
    print(f"\nCreado. value={relay.value} is_active={relay.is_active}")

    print("\nActivando CH7...")
    relay.on()
    print(f"Después de .on(): value={relay.value} is_active={relay.is_active}")

    print("\nManteniendo 30 segundos. Observá si la bomba sigue trabajando.\n")

    try:
        for i in range(30):
            remaining = 30 - i
            print(f"\r  {remaining:2d}s | value={relay.value} active={relay.is_active}",
                  end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n\nDesactivando.")
        relay.off()
        relay.close()
        print("Done.")

if __name__ == "__main__":
    main()
