# Pinout — Listado componente → pin

Referencia rápida para cableado de la Raspberry Pi 3 al hardware del piloto Kowen.

## Alimentación

- **5V para módulo relé / sensores 5V** → Pin 2
- **GND común** → Pin 6

## Salidas — Cargas AC (vía módulo relé Songle 8ch)

- **EV #3 (llenado botellón)** → Pin 35 (GPIO 19) ✅ validado
- **Bomba despacho 220V** → Pin 36 (GPIO 16) ✅ validado
- **EV #1 (entrada bombas RO)** → Pin 13 (GPIO 27)
- **EV #2 (salida RO / flush)** → Pin 15 (GPIO 22)
- **Lámpara UV** → Pin 16 (GPIO 23)
- **Generador ozono** → Pin 18 (GPIO 24)
- **Transformador 24V (→ bombas RO)** → Pin 22 (GPIO 25)

*Las bombas RO se controlan indirectamente cortando AC al transformador 24V (Relé 7). Sin MOSFET ni circuito DC adicional.*

## Entradas — Botones del panel

- **Botón EMPEZAR (verde)** → Pin 29 (GPIO 5)
- **Botón APAGAR (rojo)** → Pin 31 (GPIO 6)

## Entradas — Sensores de nivel del tanque (flotadores reed switch)

- **Sensor nivel MAX** → Pin 32 (GPIO 12) — tanque lleno, parar bombas RO
- **Sensor nivel MIN** → Pin 33 (GPIO 13) — necesita rellenar, activar bombas RO
- **Sensor nivel OUT (vacío)** → Pin 12 (GPIO 18) — tanque vacío, ALERTA + bloquear venta

## Entradas — Caudalímetro JINGRUI JR-A168

- **Cable rojo (VCC 5V)** → Pin 2
- **Cable negro (GND)** → Pin 6
- **Cable amarillo (señal pulso)** → Pin 11 (GPIO 17), vía divisor 1kΩ + 2kΩ

## Bus I2C — ADS1115 (TDS) + PN532 (RFID)

- **SDA** → Pin 3 (GPIO 2)
- **SCL** → Pin 5 (GPIO 3)
- **VCC ADS1115 y PN532** → Pin 1 o 17 (3.3V)
- **GND** → Pin 14 o 20

## ❌ Pines DAÑADOS — NO USAR

- ❌ Pin 37 (GPIO 26)
- ❌ Pin 38 (GPIO 20)
- ❌ Pin 40 (GPIO 21)

---

## Fase Alpha (test mínimo en taller)

Solo estos 4 cables al inicio:

1. **5V** → Pin 2 → VCC módulo relé
2. **GND** → Pin 6 → GND módulo relé
3. **EV #3** → Pin 35 → IN1 módulo relé (CH1)
4. **Bomba despacho** → Pin 36 → IN2 módulo relé (CH2)

Después de validar Fase Alpha en taller, ir sumando el resto en sesiones siguientes.
