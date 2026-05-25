#!/usr/bin/env python3
"""
flush.py — Ciclo de flush con secuencia segura.

Secuencia:
    t=0.0s   CH4 (EV #2) → OPEN   (libera presión antes de arrancar bombas)
    t=1.0s   CH7 (bombas) → ON
    t=16.0s  CH7 (bombas) → OFF   (bombas trabajaron 15s)
    t=17.0s  CH4 (EV #2) → CLOSE  (cierra después de que bajó la presión)

Por qué este orden:
- Abrir EV antes de bombas = sin golpe de ariete al arrancar
- Apagar bombas antes de cerrar EV = sin presión atrapada al final

Mapeo:
    CH4 (GPIO 22) → EV #2 salida / flush
    CH7 (GPIO  4) → Bombas RO + EV #1 entrada

Uso:
    python3 scripts/flush.py

Para abortar de emergencia: Ctrl+C (apaga todo).
"""

import signal
import sys
import time
from gpiozero import OutputDevice

EV2_GPIO = 22       # CH4
PUMPS_GPIO = 4      # CH7

ACTIVE_HIGH = True

BOMBAS_TIME = 15.0  # segundos bombas activas
PRESSURE_RELIEF = 1.0  # tiempo entre abrir EV y arrancar bombas
PRESSURE_DROP = 1.0    # tiempo entre apagar bombas y cerrar EV

devices = []


def cleanup(signum=None, frame=None):
    print("\n\n[!] Emergencia. Apagando todo.")
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

    print("=== Ciclo de flush seguro ===\n")
    print("Iniciando en 2 segundos... (Ctrl+C para cancelar)")
    time.sleep(2)

    ev2 = OutputDevice(EV2_GPIO, active_high=ACTIVE_HIGH, initial_value=False)
    pumps = OutputDevice(PUMPS_GPIO, active_high=ACTIVE_HIGH, initial_value=False)
    devices.extend([ev2, pumps])

    try:
        # Fase 1: Liberar presión - abrir EV #2 antes de arrancar bombas
        print(f"\nt=0.0s   CH4 (EV #2) → OPEN   (libera presión)")
        ev2.on()
        time.sleep(PRESSURE_RELIEF)

        # Fase 2: Arrancar bombas
        print(f"t={PRESSURE_RELIEF:.1f}s   CH7 (bombas) → ON")
        pumps.on()

        # Fase 3: Bombas trabajando 15s
        print(f"\n  Bombas activas. Esperando {BOMBAS_TIME:.0f}s...")
        for i in range(int(BOMBAS_TIME)):
            remaining = int(BOMBAS_TIME) - i
            print(f"\r  Bombas: {remaining:2d}s restantes", end="", flush=True)
            time.sleep(1.0)
        print()

        # Fase 4: Apagar bombas
        print(f"\nt={PRESSURE_RELIEF + BOMBAS_TIME:.1f}s  CH7 (bombas) → OFF")
        pumps.off()
        time.sleep(PRESSURE_DROP)

        # Fase 5: Cerrar EV #2 (después de que presión bajó)
        print(f"t={PRESSURE_RELIEF + BOMBAS_TIME + PRESSURE_DROP:.1f}s  CH4 (EV #2) → CLOSE")
        ev2.off()

        print(f"\n=== Ciclo de flush completado ===")

    except KeyboardInterrupt:
        cleanup()
    finally:
        # Asegurar que todo queda apagado
        try:
            pumps.off()
            ev2.off()
            pumps.close()
            ev2.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
