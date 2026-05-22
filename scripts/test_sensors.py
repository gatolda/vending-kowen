#!/usr/bin/env python3
"""
Test de sensores digitales — flotadores + presostato.

Lee continuamente el estado de los 3 sensores y los imprime cada 0.5s.
Útil para verificar cableado y entender los estados ON/OFF.

Sensores cableados:
    Flotador MAX (tanque lleno)         → GPIO 12 (pin 32)
    Flotador OUT (tanque vacío)         → GPIO 18 (pin 12)
    Presostato red (agua municipal)     → GPIO 13 (pin 33)

Cableado físico de cada sensor:
    Cable A → GPIO indicado del Pi
    Cable B → GND (cualquier pin GND del Pi: 6, 9, 14, 20, 25, 30, 34, 39)

Cómo interpretar los estados:

    Flotador MAX:
        PRESSED (pull-up activo, GPIO bajo)  → flotador arriba, tanque LLENO
        RELEASED (sin presionar, GPIO alto)  → flotador abajo, tanque NO LLENO

    Flotador OUT:
        PRESSED   → flotador arriba, hay agua
        RELEASED  → flotador abajo, VACÍO ⚠️

    Presostato red:
        PRESSED   → hay presión, agua de red OK
        RELEASED  → sin presión, sin agua de red ⚠️

(Los nombres "pressed/released" vienen de la clase Button de gpiozero, que asume
contacto a GND como "presionado")

Uso:
    python3 scripts/test_sensors.py

Salir con Ctrl+C.
"""

from gpiozero import Button
import time
import signal
import sys

# Mapeo: nombre → (GPIO, descripción)
SENSORS = {
    "MAX":         (12, "Flotador tanque LLENO"),
    "OUT":         (18, "Flotador tanque VACÍO"),
    "PRESOSTATO":  (13, "Presostato agua de red"),
}

devices = {}

def cleanup(signum=None, frame=None):
    print("\n[!] Cerrando.")
    for d in devices.values():
        try:
            d.close()
        except Exception:
            pass
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, cleanup)

    # Inicializar todos los sensores como Button (con pull-up interno por default)
    for name, (gpio, desc) in SENSORS.items():
        try:
            devices[name] = Button(gpio, pull_up=True)
            print(f"  Inicializado {name} (GPIO {gpio}) — {desc}")
        except Exception as e:
            print(f"  ERROR inicializando {name} (GPIO {gpio}): {e}")
            cleanup()

    print("\n=== Lectura continua de sensores ===")
    print("Ctrl+C para salir\n")
    print(f"{'Sensor':<12} {'Estado':<10} {'GPIO':<5}")
    print("-" * 30)

    while True:
        line = ""
        for name, dev in devices.items():
            state = "PRESSED" if dev.is_pressed else "RELEASED"
            symbol = "🔵" if dev.is_pressed else "⚪"
            line += f"{symbol} {name:<10} {state:<10}  "
        print(f"\r{line}", end="", flush=True)
        time.sleep(0.5)

if __name__ == "__main__":
    main()
