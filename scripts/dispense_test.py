#!/usr/bin/env python3
"""
Fase Alpha — Control manual de despacho desde consola (versión gpiozero).

Sin caudalímetro: el corte de despacho es por tiempo, no por litros.

Uso:
    python3 dispense_test.py <segundos>           # ciclo completo de despacho
    python3 dispense_test.py pump <segundos>      # bomba sola por N segundos
    python3 dispense_test.py ev <segundos>        # EV sola por N segundos
    python3 dispense_test.py click pump           # pulso 1s a bomba (test clicks)
    python3 dispense_test.py click ev             # pulso 1s a EV (test clicks)
    python3 dispense_test.py interactive          # modo interactivo (REPL)

Ejemplos:
    python3 dispense_test.py 5             # despacha por 5 segundos
    python3 dispense_test.py pump 3        # bomba sola por 3s (para escuchar clicks)
    python3 dispense_test.py interactive   # modo conversacional
"""

from gpiozero import OutputDevice
import time
import sys
import signal

# ============================================
# CONFIGURACIÓN — ajustar según cableado real
# ============================================

GPIO_EV3 = 21       # Pin 40 del header — Relé canal 1 → EV #3 llenado
GPIO_PUMP = 20      # Pin 38 del header — Relé canal 2 → Bomba despacho 220V

# Módulos de relé chinos típicos son "active LOW" (se activan con GND).
# Si tu módulo es active-high, cambiar False por True.
ACTIVE_HIGH = False

# Pausa entre encender bomba y abrir EV (presurizar línea)
PRESSURIZE_DELAY = 0.5

# ============================================

# Inicializar dispositivos
# initial_value=False = empieza apagado (independiente de active_high)
ev3 = OutputDevice(GPIO_EV3, active_high=ACTIVE_HIGH, initial_value=False)
pump = OutputDevice(GPIO_PUMP, active_high=ACTIVE_HIGH, initial_value=False)

def all_off():
    ev3.off()
    pump.off()

def cleanup(signum, frame):
    print("\n[!] Interrumpido. Apagando todo.")
    all_off()
    sys.exit(0)

def dispense_cycle(seconds):
    print(f"=== Despacho de {seconds}s ===")
    print("  1. Encendiendo bomba despacho...")
    pump.on()
    time.sleep(PRESSURIZE_DELAY)
    print("  2. Abriendo EV #3 llenado...")
    ev3.on()
    print(f"  3. Dispensando por {seconds}s...")
    time.sleep(seconds)
    print("  4. Cerrando EV #3...")
    ev3.off()
    time.sleep(0.3)
    print("  5. Apagando bomba...")
    pump.off()
    print("Listo.")

def hold(device, name, seconds):
    print(f"{name} ON por {seconds}s...")
    device.on()
    time.sleep(seconds)
    device.off()
    print(f"{name} OFF")

def click(device, name):
    print(f"{name} click (1s)...")
    device.on()
    time.sleep(1)
    device.off()

def interactive():
    print("Modo interactivo. Comandos:")
    print("  pump on | pump off")
    print("  ev on   | ev off")
    print("  dispense N    (ciclo completo N seg)")
    print("  status")
    print("  exit")
    while True:
        try:
            cmd = input("> ").strip().lower().split()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not cmd:
            continue
        if cmd[0] == "exit":
            break
        elif cmd[0] == "pump" and len(cmd) > 1:
            if cmd[1] == "on": pump.on(); print("Bomba ON")
            elif cmd[1] == "off": pump.off(); print("Bomba OFF")
        elif cmd[0] == "ev" and len(cmd) > 1:
            if cmd[1] == "on": ev3.on(); print("EV ON")
            elif cmd[1] == "off": ev3.off(); print("EV OFF")
        elif cmd[0] == "dispense" and len(cmd) > 1:
            try:
                dispense_cycle(float(cmd[1]))
            except ValueError:
                print("Uso: dispense N")
        elif cmd[0] == "status":
            print(f"EV #3 (GPIO {GPIO_EV3}): {'ON' if ev3.is_active else 'OFF'}")
            print(f"Bomba (GPIO {GPIO_PUMP}): {'ON' if pump.is_active else 'OFF'}")
        else:
            print("Comando no reconocido.")
    all_off()

def main():
    signal.signal(signal.SIGINT, cleanup)

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    try:
        # Número solo → ciclo completo
        if cmd.replace('.', '', 1).isdigit():
            dispense_cycle(float(cmd))
        elif cmd == "pump" and len(sys.argv) >= 3:
            hold(pump, "Bomba", float(sys.argv[2]))
        elif cmd == "ev" and len(sys.argv) >= 3:
            hold(ev3, "EV #3", float(sys.argv[2]))
        elif cmd == "click" and len(sys.argv) >= 3:
            target = sys.argv[2].lower()
            if target == "pump":
                click(pump, "Bomba")
            elif target == "ev":
                click(ev3, "EV #3")
            else:
                print(f"Click: pump o ev, no '{target}'")
        elif cmd == "interactive":
            interactive()
        else:
            print(__doc__)
    finally:
        all_off()

if __name__ == "__main__":
    main()
