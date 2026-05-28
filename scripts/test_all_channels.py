#!/usr/bin/env python3
"""
Test secuencial de los canales del módulo de relés principal (8ch).

Módulo 8ch reemplazado 2026-05-27 → CH3 ahora funciona.

Activa cada canal por 2 segundos en secuencia.
Útil para validar que todos los canales del módulo funcionan,
y para identificar qué válvula/carga está en cada canal.

Uso:
    python3 test_all_channels.py              # secuencia completa
    python3 test_all_channels.py 5            # solo CH5
    python3 test_all_channels.py 3 4 5        # canales específicos

Mapeo canal → carga (módulo principal), actualizado 2026-05-27:
    CH1 → Luz publicidad frontal     (GPIO 16, pin 36)
    CH2 → Generador ozono            (GPIO 19, pin 35)
    CH3 → EV entrada bombas RO       (GPIO 27, pin 13)
    CH4 → EV llenado botellón        (GPIO 22, pin 15)
    CH5 → EV flush salida            (GPIO 23, pin 16)
    CH6 → Libre                      (GPIO 24, pin 18)
    CH7 → Libre                      (GPIO  4, pin  7)
    CH8 → Libre                      (GPIO  7, pin 26)
"""

from gpiozero import OutputDevice
import time
import sys
import signal

# Mapeo canal → (GPIO, descripción) — alineado con app.py
CHANNELS = {
    1: (16, "Luz publicidad frontal"),
    2: (19, "Generador ozono"),
    3: (27, "EV entrada bombas RO"),
    4: (22, "EV llenado botellón"),
    5: (23, "EV flush salida"),
    6: (24, "Libre"),
    7: (4,  "Libre"),
    8: (7,  "Libre"),
}

ACTIVE_HIGH = False   # Módulo es active-LOW (descubierto 2026-05-25)
HOLD_TIME = 2.0
GAP_TIME = 0.5

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
    if ch not in CHANNELS:
        print(f"\n--- CH{ch}: SIN ASIGNAR (dañado o reserva)")
        return
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
        return list(CHANNELS.keys())
    try:
        channels = [int(x) for x in args]
    except ValueError:
        print(f"Error: argumentos deben ser números de canal (1-8)")
        print(__doc__)
        sys.exit(1)
    return channels

def main():
    signal.signal(signal.SIGINT, cleanup)
    channels = parse_channels(sys.argv[1:])

    print(f"=== Test de {len(channels)} canal(es): {channels} ===")
    print(f"Cada canal activo por {HOLD_TIME}s, pausa de {GAP_TIME}s entre canales.")
    print(f"\nIniciando en 2 segundos... (Ctrl+C para cancelar)")
    time.sleep(2)

    try:
        for ch in channels:
            test_channel(ch)
        print("\n=== Test completado. ===")
    finally:
        for dev in devices.values():
            try:
                dev.off()
                dev.close()
            except Exception:
                pass

if __name__ == "__main__":
    main()
