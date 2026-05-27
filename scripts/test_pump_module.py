#!/usr/bin/env python3
"""
Test del módulo 2ch nuevo (drives contactores para bombas).

Hace varios ciclos ON/OFF en cada canal para verificar:
  - El módulo arranca con relés OFF (sin click espurio al inicializar)
  - Cada canal responde al GPIO correspondiente
  - El LED del módulo y el click del relé son consistentes

⚠️  IMPORTANTE: los contactores NO deben estar todavía conectados a las salidas
    del módulo. Este test es para validar el módulo solo (relé + LED).

Mapeo:
    CH9  → GPIO 5  (pin físico 29) → IN1 → Bomba despacho (contactor)
    CH10 → GPIO 6  (pin físico 31) → IN2 → Bombas RO (contactor)

Uso:
    python3 test_pump_module.py            # ambos canales, 3 ciclos
    python3 test_pump_module.py 9          # solo CH9
    python3 test_pump_module.py 10         # solo CH10
    python3 test_pump_module.py 9 10 5     # ambos canales, 5 ciclos
"""

from gpiozero import OutputDevice
import time
import sys
import signal

CHANNELS = {
    9:  (5, "Bomba despacho (contactor) — IN1"),
    10: (6, "Bombas RO (contactor) — IN2"),
}

ACTIVE_HIGH = False   # módulo es active-LOW
HOLD_TIME = 1.5       # tiempo ON
GAP_TIME = 1.0        # tiempo OFF entre ciclos
DEFAULT_CYCLES = 3

devices = {}


def cleanup(signum=None, frame=None):
    print("\n[!] Interrumpido. Apagando todos los relés del módulo 2ch.")
    for dev in devices.values():
        try:
            dev.off()
            dev.close()
        except Exception:
            pass
    sys.exit(0)


def test_channel(ch, cycles):
    if ch not in CHANNELS:
        print(f"\n[!] CH{ch} no existe en el módulo 2ch (válidos: 9, 10).")
        return

    gpio, desc = CHANNELS[ch]
    print(f"\n=== CH{ch} (GPIO {gpio}) → {desc} ===")

    try:
        dev = OutputDevice(gpio, active_high=ACTIVE_HIGH, initial_value=False)
    except Exception as e:
        print(f"    ERROR al abrir GPIO {gpio}: {e}")
        return
    devices[ch] = dev

    for i in range(1, cycles + 1):
        print(f"    Ciclo {i}/{cycles}: ON ({HOLD_TIME}s) — escuchá click + LED")
        dev.on()
        time.sleep(HOLD_TIME)
        print(f"    Ciclo {i}/{cycles}: OFF ({GAP_TIME}s)")
        dev.off()
        time.sleep(GAP_TIME)


def parse_args(args):
    if not args:
        return list(CHANNELS.keys()), DEFAULT_CYCLES

    channels = []
    cycles = DEFAULT_CYCLES
    for a in args:
        try:
            n = int(a)
        except ValueError:
            print(f"Error: argumentos deben ser enteros")
            print(__doc__)
            sys.exit(1)
        if n in CHANNELS:
            channels.append(n)
        elif n > 0:
            cycles = n
        else:
            print(f"Error: valor inválido {n}")
            sys.exit(1)

    if not channels:
        channels = list(CHANNELS.keys())
    return channels, cycles


def main():
    signal.signal(signal.SIGINT, cleanup)
    channels, cycles = parse_args(sys.argv[1:])

    print(f"=== Test módulo 2ch ===")
    print(f"Canales: {channels} | Ciclos por canal: {cycles}")
    print(f"ON {HOLD_TIME}s, OFF {GAP_TIME}s\n")
    print(f"Iniciando en 2s... (Ctrl+C para abortar)")
    time.sleep(2)

    try:
        for ch in channels:
            test_channel(ch, cycles)
        print("\n=== Test completado ===")
        print("Si escuchaste click + viste LED en cada ciclo, el módulo 2ch funciona ok.")
    finally:
        for dev in devices.values():
            try:
                dev.off()
                dev.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
