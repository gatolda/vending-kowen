#!/usr/bin/env python3
"""
Test secuencial de los canales del módulo de relés principal.

⚠️  CH3 DAÑADO (relé soldado, no se usa más). Su función pasó a CH7.

Activa cada canal por 2 segundos en secuencia.
Útil para validar que todos los canales del módulo funcionan,
y que los GPIOs asignados no están dañados.

Uso:
    python3 test_all_channels.py              # secuencia completa (sin CH3)
    python3 test_all_channels.py 7            # solo CH7
    python3 test_all_channels.py 1 4 5        # canales específicos

Mapeo canal → carga (módulo principal):
    CH1 → EV #3 llenado botellón     (GPIO 16, pin 36)
    CH2 → Bomba despacho 220V        (GPIO 19, pin 35)
    CH3 → ❌ DAÑADO, no usar         (GPIO 27, pin 13)
    CH4 → EV #2 salida RO / flush    (GPIO 22, pin 15)
    CH5 → Lámpara UV                 (GPIO 23, pin 16)
    CH6 → Generador ozono            (GPIO 24, pin 18)
    CH7 → EV #1 entrada bombas RO    (GPIO  4, pin  7)  ← antes CH3
    CH8 → Reserva                    (GPIO  7, pin 26)
"""

from gpiozero import OutputDevice
import time
import sys
import signal

# Mapeo canal → (GPIO, descripción)
# CH3 omitido (dañado). Función movida a CH7.
CHANNELS = {
    1: (16, "EV #3 llenado botellón"),
    2: (19, "Bomba despacho 220V"),
    # 3: DAÑADO, no incluido
    4: (22, "EV #2 salida RO / flush"),
    5: (23, "Lámpara UV"),
    6: (24, "Generador ozono"),
    7: (4,  "EV #1 entrada bombas RO"),
    8: (7,  "Reserva"),
}

ACTIVE_HIGH = True
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
