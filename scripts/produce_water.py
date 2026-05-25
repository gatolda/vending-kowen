#!/usr/bin/env python3
"""
produce_water.py — Ciclo de producción de agua (PRODUCING)
sin considerar sensores. El usuario actúa como sensor MAX.

Secuencia simplificada (CH7 controla EV #1 + Transformador):
    t=0      EV #2 cerrada (modo flush, agua a drenaje)
    t=0      CH7 ON → EV #1 abre + bombas RO arrancan simultáneamente
    t=15s    EV #2 OPEN → fin flush, agua al tanque
             ... producción en curso ...
    [user]   Apretás ENTER cuando consideres el tanque lleno
    t=stop   CH7 OFF → bombas paran + EV #1 cierra
    t=+1s    EV #2 cerrada (estado final)

Mapeo:
    CH4 (GPIO 22) → EV #2 salida RO / flush
    CH7 (GPIO  4) → EV #1 entrada + Transformador 24V (bombas RO)

Uso:
    python3 scripts/produce_water.py

Para parar: apretá ENTER (simula MAX detectado).
Para abortar de emergencia: Ctrl+C.
"""

from gpiozero import OutputDevice
import time
import sys
import threading

# Configuración hardware
EV2_GPIO = 22         # CH4 - EV #2 salida RO / flush
PUMPS_GPIO = 4        # CH7 - EV #1 entrada + Transformador 24V (bombas)
ACTIVE_HIGH = True

# Tiempos
FLUSH_TIME = 15.0     # segundos de flush al inicio (agua a drenaje)
SHUTDOWN_DELAY = 1.0  # segundos entre apagar bombas y cerrar EV #2


def listen_for_enter(stop_flag):
    """Thread que espera Enter del usuario."""
    try:
        input()
    except EOFError:
        pass
    stop_flag.set()


def main():
    # Inicializar relés (todos OFF inicialmente)
    print("[Init] Configurando relés...")
    ev2 = OutputDevice(EV2_GPIO, active_high=ACTIVE_HIGH, initial_value=False)
    pumps = OutputDevice(PUMPS_GPIO, active_high=ACTIVE_HIGH, initial_value=False)
    time.sleep(0.5)

    stop_flag = threading.Event()
    enter_thread = threading.Thread(target=listen_for_enter, args=(stop_flag,), daemon=True)

    try:
        print("\n=== Ciclo de producción de agua ===\n")

        # Fase 1: Confirmar EV #2 cerrada (flush mode)
        print("t=0.0s   EV #2 cerrada (modo flush)")
        ev2.off()
        time.sleep(0.5)

        # Fase 2: Activar bombas + EV #1 (CH7)
        print("t=0.0s   CH7 ON → EV #1 OPEN + bombas RO arrancan")
        pumps.on()

        # Fase 3: Flush
        print(f"\n  Modo flush activo. Esperando {FLUSH_TIME:.0f}s (agua al drenaje)...")
        for i in range(int(FLUSH_TIME)):
            remaining = int(FLUSH_TIME) - i
            print(f"\r  Flush: {remaining:2d}s restantes", end="", flush=True)
            time.sleep(1.0)
        print()

        # Fase 4: Apertura de EV #2 — producción al tanque
        print(f"\nt=15s    EV #2 OPEN → fin flush, agua al tanque")
        ev2.on()

        # Fase 5: Producción continua hasta que el usuario apriete Enter
        print(f"\n*** Producción en curso ***")
        print(f"*** Apretá ENTER cuando consideres el tanque lleno (vos sos el sensor MAX) ***\n")

        enter_thread.start()
        start = time.time()
        while not stop_flag.is_set():
            elapsed = int(time.time() - start)
            mins, secs = divmod(elapsed, 60)
            print(f"\r  Tiempo de producción al tanque: {mins:02d}:{secs:02d}",
                  end="", flush=True)
            time.sleep(0.5)
        print()

        # Fase 6: Detener producción (usuario detectó MAX)
        print("\n=== Tanque lleno detectado (manual). Iniciando apagado seguro ===")

        print(f"  CH7 OFF → bombas paran + EV #1 cierra")
        pumps.off()
        time.sleep(SHUTDOWN_DELAY)

        print(f"  EV #2 cerrada")
        ev2.off()

        print(f"\n=== Producción finalizada correctamente ===")

    except KeyboardInterrupt:
        print("\n\n[!] EMERGENCIA — Abortando todo.")
    finally:
        try:
            pumps.off()
            ev2.off()
            pumps.close()
            ev2.close()
            print("[Cleanup] Todos los relés desactivados.")
        except Exception:
            pass


if __name__ == "__main__":
    main()
