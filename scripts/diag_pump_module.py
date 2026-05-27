#!/usr/bin/env python3
"""
Diagnóstico del módulo 2ch — prueba con las DOS polaridades.

Algunos módulos 2ch son active-HIGH (al revés del 8ch principal).
Este script primero prueba active-LOW (como el 8ch) y después active-HIGH.

Si en una de las dos pasadas escuchás click + LED, sabemos la polaridad.
Si en ninguna pasa nada, el problema es de cableado o GPIO.

Uso:
    python3 diag_pump_module.py
"""

from gpiozero import OutputDevice
import time

# GPIO 5 = pin físico 29 (CH9 / IN1)
# GPIO 6 = pin físico 31 (CH10 / IN2)
PINS = [(5, "IN1 / CH9"), (6, "IN2 / CH10")]

HOLD = 2.0
GAP = 1.0


def test_polarity(active_high):
    label = "active-HIGH" if active_high else "active-LOW"
    print(f"\n===== Probando {label} =====")
    for gpio, name in PINS:
        print(f"\n  GPIO {gpio} ({name}):")
        try:
            dev = OutputDevice(gpio, active_high=active_high, initial_value=False)
        except Exception as e:
            print(f"    ERROR abriendo GPIO {gpio}: {e}")
            continue

        try:
            print(f"    .on()  por {HOLD}s — ¿click? ¿LED?")
            dev.on()
            time.sleep(HOLD)
            print(f"    .off() por {GAP}s")
            dev.off()
            time.sleep(GAP)
        finally:
            dev.close()


def main():
    print("Diagnóstico módulo 2ch — vas a ver 4 pasadas en total")
    print("(2 canales × 2 polaridades). Mirá el módulo y escuchá.")
    print("\nIniciando en 2s...")
    time.sleep(2)

    test_polarity(active_high=False)  # como el 8ch
    test_polarity(active_high=True)   # opuesto

    print("\n===== Fin =====")
    print("Si UNA de las polaridades hizo click+LED, esa es la correcta.")
    print("Si NINGUNA hizo nada, problema de cableado o GPIO.")


if __name__ == "__main__":
    main()
