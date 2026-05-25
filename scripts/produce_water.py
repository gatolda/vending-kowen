#!/usr/bin/env python3
"""
produce_water.py — Ciclo completo de producción: FLUSH → PRODUCCIÓN.

Secuencia:
    Fase FLUSH (limpia la membrana, agua al drenaje):
        t=0.0s   CH4 (EV #2) → OPEN   (libera presión)
        t=1.0s   CH7 (bombas) → ON
        t=16.0s  CH4 (EV #2) → CLOSE  (fin flush)

    Fase PRODUCCIÓN (agua al tanque):
        Bombas CH7 siguen prendidas
        Apretás ENTER cuando consideres tanque lleno (sos el sensor MAX)

    Fase APAGADO seguro:
        CH7 (bombas) → OFF

Mapeo:
    CH4 (GPIO 22) → EV #2 salida / flush
    CH7 (GPIO  4) → Bombas RO + EV #1 entrada

Uso:
    python3 scripts/produce_water.py

Detener producción: ENTER (transición a apagado limpio)
Emergencia:        Ctrl+C (apaga todo inmediato)
"""

import signal
import sys
import time
import threading
from gpiozero import OutputDevice

# Canales sanos — crear todos los OutputDevices al inicio
CHANNELS = {
    1: 16,
    2: 19,
    # 3: DAÑADO
    4: 22,    # EV #2 (flush/salida RO)
    5: 23,
    6: 24,
    7: 4,     # Bombas RO + EV #1
    8: 7,
}

ACTIVE_HIGH = False   # Módulo es active-LOW
FLUSH_TIME = 15.0     # segundos de flush
PRESSURE_RELIEF = 1.0 # tiempo entre abrir EV y arrancar bombas

devices = {}


def cleanup(signum=None, frame=None):
    print("\n\n[!] EMERGENCIA — Apagando todo inmediatamente.")
    for d in devices.values():
        try:
            d.off()
            d.close()
        except Exception:
            pass
    sys.exit(0)


def listen_for_enter(stop_flag):
    try:
        input()
    except EOFError:
        pass
    stop_flag.set()


def main():
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("=== Producción de agua: FLUSH → PRODUCCIÓN ===\n")
    print("Iniciando en 2 segundos... (Ctrl+C para cancelar)")
    time.sleep(2)

    # Crear OutputDevices para todos los canales sanos
    print("\n[Init] Configurando 7 canales (todos OFF)...")
    for ch, gpio in CHANNELS.items():
        devices[ch] = OutputDevice(gpio, active_high=ACTIVE_HIGH, initial_value=False)
        time.sleep(0.05)

    ev2 = devices[4]
    pumps = devices[7]

    stop_flag = threading.Event()
    enter_thread = threading.Thread(target=listen_for_enter, args=(stop_flag,), daemon=True)

    try:
        # ═══ Fase FLUSH ═══
        print("\n━━━ Fase FLUSH ━━━\n")

        print(f"t=0.0s   CH4 (EV #2) → OPEN   (libera presión)")
        ev2.on()
        time.sleep(PRESSURE_RELIEF)

        print(f"t={PRESSURE_RELIEF:.1f}s   CH7 (bombas) → ON")
        pumps.on()

        print(f"\n  Flush en curso. Esperando {FLUSH_TIME:.0f}s...\n")
        for i in range(int(FLUSH_TIME)):
            remaining = int(FLUSH_TIME) - i
            print(f"\r  Flush: {remaining:2d}s restantes", end="", flush=True)
            time.sleep(1.0)
        print()

        # ═══ Fase PRODUCCIÓN ═══
        print(f"\n━━━ Fase PRODUCCIÓN ━━━\n")
        print(f"t={PRESSURE_RELIEF + FLUSH_TIME:.1f}s  CH4 (EV #2) → CLOSE  (fin flush)")
        ev2.off()
        print(f"         CH7 (bombas) sigue ON → agua al tanque\n")

        print("*** Producción en curso. Apretá ENTER cuando consideres tanque lleno. ***\n")
        enter_thread.start()
        start = time.time()
        while not stop_flag.is_set():
            elapsed = int(time.time() - start)
            mins, secs = divmod(elapsed, 60)
            print(f"\r  Producción: {mins:02d}:{secs:02d}", end="", flush=True)
            time.sleep(0.5)
        print()

        # ═══ Fase APAGADO ═══
        print(f"\n━━━ Apagado (tanque lleno detectado) ━━━\n")
        print(f"  CH7 (bombas) → OFF")
        pumps.off()
        time.sleep(0.5)

        print(f"  CH4 (EV #2) → confirmar OFF (ya estaba cerrada)")
        ev2.off()

        print(f"\n=== Ciclo completado ===")

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
