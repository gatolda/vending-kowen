#!/usr/bin/env python3
"""
flush.py — Ciclo de flush con secuencia segura.

Trabaja alrededor del bug "CH7 no se activa solo": crea OutputDevices para
TODOS los canales sanos al inicio, después solo activa CH4 + CH7.

Secuencia:
    t=0.0s   CH4 (EV #2) → OPEN   (libera presión)
    t=1.0s   CH7 (bombas) → ON
    t=16.0s  CH7 (bombas) → OFF
    t=17.0s  CH4 (EV #2) → CLOSE

Mapeo:
    CH4 (GPIO 22) → EV #2 salida / flush
    CH7 (GPIO  4) → Bombas RO + EV #1 entrada

Uso:
    python3 scripts/flush.py

Para abortar de emergencia: Ctrl+C
"""

import signal
import sys
import time
from gpiozero import OutputDevice

# Todos los canales sanos. Crear OutputDevices para todos
# para evitar el bug donde CH7 no se activa solo.
CHANNELS = {
    1: 16,
    2: 19,
    # 3: DAÑADO
    4: 22,    # EV #2
    5: 23,
    6: 24,
    7: 4,     # Bombas + EV #1
    8: 7,
}

ACTIVE_HIGH = True
BOMBAS_TIME = 15.0
PRESSURE_RELIEF = 1.0
PRESSURE_DROP = 1.0

devices = {}


def cleanup(signum=None, frame=None):
    print("\n\n[!] Emergencia. Apagando todo.")
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

    print("=== Ciclo de flush ===\n")
    print("Iniciando en 2 segundos... (Ctrl+C para cancelar)")
    time.sleep(2)

    # Crear OutputDevices para TODOS los canales sanos
    # Esto "calienta" el backend lgpio y CH7 funciona correctamente
    print("\n[Init] Creando OutputDevices para 7 canales...")
    for ch, gpio in CHANNELS.items():
        devices[ch] = OutputDevice(gpio, active_high=ACTIVE_HIGH, initial_value=False)
        print(f"  CH{ch} (GPIO {gpio}) listo")
        time.sleep(0.1)

    # Referencias cortas a los que vamos a usar
    ev2 = devices[4]
    pumps = devices[7]

    try:
        # Fase 1: Liberar presión (abrir EV #2)
        print(f"\nt=0.0s   CH4 (EV #2) → OPEN   (libera presión)")
        ev2.on()
        time.sleep(PRESSURE_RELIEF)

        # Fase 2: Arrancar bombas
        print(f"t={PRESSURE_RELIEF:.1f}s   CH7 (bombas) → ON")
        pumps.on()

        # Fase 3: Bombas trabajando 15s
        print(f"\n  Bombas activas. Esperando {BOMBAS_TIME:.0f}s...\n")
        for i in range(int(BOMBAS_TIME)):
            remaining = int(BOMBAS_TIME) - i
            print(f"\r  Bombas: {remaining:2d}s restantes", end="", flush=True)
            time.sleep(1.0)
        print()

        # Fase 4: Apagar bombas
        print(f"\nt={PRESSURE_RELIEF + BOMBAS_TIME:.1f}s  CH7 (bombas) → OFF")
        pumps.off()
        time.sleep(PRESSURE_DROP)

        # Fase 5: Cerrar EV #2
        print(f"t={PRESSURE_RELIEF + BOMBAS_TIME + PRESSURE_DROP:.1f}s  CH4 (EV #2) → CLOSE")
        ev2.off()

        print(f"\n=== Flush completado ===")

    except KeyboardInterrupt:
        cleanup()
    finally:
        for d in devices.values():
            try:
                d.off()
                d.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
