#!/usr/bin/env python3
"""
Test interactivo: cada sensor controla un relé en tiempo real.

Mapeo:
    Flotador MAX (GPIO 12, pin 32)  → CH1 relé (GPIO 16, pin 36)
    Flotador OUT (GPIO 18, pin 12)  → CH2 relé (GPIO 19, pin 35)
    Presostato   (GPIO 13, pin 33)  → CH3 relé (GPIO 27, pin 13)

Cuando un sensor se cierra (contacto a GND), su relé se activa.
Cuando se abre, el relé desactiva.

Útil para validar visualmente que cada sensor funciona: accionás el
sensor con la mano y ves/oís el relé correspondiente clickear.

Uso:
    python3 scripts/test_sensores_a_reles.py

Salir con Ctrl+C.
"""

from gpiozero import Button, OutputDevice
import time
import signal
import sys

PAIRS = [
    # (nombre, gpio_sensor, gpio_relé, descripción)
    ("MAX",        12, 16, "Flotador MAX  → CH1"),
    ("OUT",        18, 19, "Flotador OUT  → CH2"),
    ("PRESOSTATO", 13, 27, "Presostato    → CH3"),
]

ACTIVE_HIGH = True

sensors = {}
relays = {}

def cleanup(signum=None, frame=None):
    print("\n[!] Cerrando. Apagando relés.")
    for r in relays.values():
        try:
            r.off()
            r.close()
        except Exception:
            pass
    for s in sensors.values():
        try:
            s.close()
        except Exception:
            pass
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, cleanup)

    print("=== Test sensor → relé ===\n")
    for name, gpio_s, gpio_r, desc in PAIRS:
        try:
            sensors[name] = Button(gpio_s, pull_up=True)
            relays[name] = OutputDevice(gpio_r, active_high=ACTIVE_HIGH, initial_value=False)
            print(f"  {desc}")
        except Exception as e:
            print(f"  ERROR {name}: {e}")
            cleanup()

    print("\nAcciona los sensores con la mano. Esperá ver clicks de los relés.\n")
    print(f"{'MAX':<11} {'OUT':<11} {'PRESOSTATO':<11}")
    print("-" * 38)

    while True:
        line = ""
        for name, _, _, _ in PAIRS:
            sensor = sensors[name]
            relay = relays[name]

            # LÓGICA INVERTIDA: relé activo cuando sensor está SUELTO (no presionado)
            # Esto refleja el estado opuesto del sensor físico para mejor lectura
            # del estado lógico del sistema (ej. MAX activo = "no lleno", etc.)
            if not sensor.is_pressed:
                if not relay.is_active:
                    relay.on()
            else:
                if relay.is_active:
                    relay.off()

            state = "🔵 ON " if relay.is_active else "⚪ OFF"
            line += f"{state:<11}"
        print(f"\r{line}", end="", flush=True)
        time.sleep(0.05)

if __name__ == "__main__":
    main()
