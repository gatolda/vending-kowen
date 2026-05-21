#!/usr/bin/env python3
"""
Test secuencial de los 8 canales del módulo de relés principal.

Activa cada canal por 2 segundos en secuencia (CH1 → CH8).
Útil para validar que todos los canales del módulo funcionan,
y que los GPIOs asignados no están dañados.

Uso:
    python3 test_all_channels.py              # secuencia completa CH1..CH8
    python3 test_all_channels.py 3            # solo CH3
    python3 test_all_channels.py 1 3 5        # CH1, CH3 y CH5

Mapeo canal → carga (módulo principal):
    CH1 → EV #3 llenado botellón     (GPIO 19, pin 35)
    CH2 → EV #1 entrada bombas RO    (GPIO 27, pin 13)
    CH3 → EV #2 salida RO            (GPIO 22, pin 15)
    CH4 → Lámpara UV                 (GPIO 23, pin 16)
    CH5 → Generador ozono            (GPIO 24, pin 18)
    CH6 → reserva                    (GPIO  4, pin  7)
    CH7 → reserva                    (GPIO  7, pin 26)
    CH8 → reserva                    (GPIO  8, pin 24)

Módulo bombas (separado) — no incluido en este test:
    bomba despacho 220V              (GPIO 16, pin 36)
    transformador 24V (bombas RO)    (GPIO 25, pin 22)
    → para testar el módulo de bombas usar dispense_test.py
"""

from gpiozero import OutputDevice
import time
import sys
import signal

# Mapeo canal → (GPIO, descripción)
CHANNELS = {
    1: (19, "EV #3 llenado botellón"),
    2: (27, "EV #1 entrada bombas RO"),
    3: (22, "EV #2 salida RO"),
    4: (23, "Lámpara UV"),
    5: (24, "Generador ozono"),
    6: (4,  "Reserva 1"),
    7: (7,  "Reserva 2"),
    8: (8,  "Reserva 3"),
}

ACTIVE_HIGH = True
HOLD_TIME = 2.0     # segundos cada canal queda encendido
GAP_TIME = 0.5      # pausa entre canales

devices = {}

def cleanup(signum=None, frame=None):
    print("\n[!] Interrumpido. Apagando todos los relés.")
    for dev in devices.values():
        try:
            dev.off()
            dev.close()
        except Exception:
            pass
    sys.exit(0)

def test_channel(ch):
    gpio, desc = CHANNELS[ch]
    print(f"\n--- CH{ch} (GPIO {gpio}) → {desc} ---")
    print(f"    ON {HOLD_TIME}s. Esperá click + LED CH{ch}...")

    try:
        dev = OutputDevice(gpio, active_high=ACTIVE_HIGH, initial_value=False)
    except Exception as e:
        print(f"    ERROR al abrir GPIO {gpio}: {e}")
        return
    devices[ch] = dev

    dev.on()
    time.sleep(HOLD_TIME)
    print(f"    OFF")
    dev.off()
    time.sleep(GAP_TIME)

def parse_channels(args):
    if not args:
        return list(range(1, 9))
    try:
        channels = [int(x) for x in args]
    except ValueError:
        print(f"Error: argumentos deben ser números de canal (1-8)")
        print(__doc__)
        sys.exit(1)
    for ch in channels:
        if ch not in CHANNELS:
            print(f"Error: CH{ch} no existe (válido: 1-8)")
            sys.exit(1)
    return channels

def main():
    signal.signal(signal.SIGINT, cleanup)
    channels = parse_channels(sys.argv[1:])

    print(f"=== Test de {len(channels)} canal(es): {channels} ===")
    print(f"Cada canal activo por {HOLD_TIME}s, pausa de {GAP_TIME}s entre canales.")
    print(f"Total estimado: {len(channels) * (HOLD_TIME + GAP_TIME):.1f}s")
    print(f"\nIniciando en 2 segundos... (Ctrl+C para cancelar)")
    time.sleep(2)

    try:
        for ch in channels:
            test_channel(ch)
        print("\n=== Test completado. Todos los relés probados. ===")
    finally:
        # Asegurar que todo queda apagado
        for dev in devices.values():
            try:
                dev.off()
                dev.close()
            except Exception:
                pass

if __name__ == "__main__":
    main()
