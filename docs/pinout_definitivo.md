# Pinout definitivo de la Raspberry Pi 3 — Piloto Kowen

Asignación completa de pines GPIO confirmada en testing (2026-05-20).

## Estado de pines

- ✅ **CONFIRMADO funcional**: testeado y validado en hardware
- 🟡 **PLANEADO**: asignado para componente, pendiente cableado físico
- ❌ **DAÑADO**: identificado dañado en testing, NO usar

---

## Pinout completo (40-pin header)

```
                              SD card slot side
                                     │
                                     ▼
        ┌─────────────────────────────────────────────┐
        │                                             │
   3.3V │  1 ●● 2   5V          ← VCC módulo relé    │
GPIO 2  │  3 ●● 4   5V                                │
GPIO 3  │  5 ●● 6   GND         ← GND módulo relé    │
GPIO 4  │  7 ●● 8   GPIO 14                          │
   GND  │  9 ●● 10  GPIO 15                          │
GPIO 17 │ 11 ●● 12  GPIO 18                          │
GPIO 27 │ 13 ●● 14  GND                              │
GPIO 22 │ 15 ●● 16  GPIO 23                          │
   3.3V │ 17 ●● 18  GPIO 24                          │
GPIO 10 │ 19 ●● 20  GND                              │
GPIO  9 │ 21 ●● 22  GPIO 25                          │
GPIO 11 │ 23 ●● 24  GPIO 8                           │
   GND  │ 25 ●● 26  GPIO 7                           │
ID_SD   │ 27 ●● 28  ID_SC                            │
GPIO  5 │ 29 ●● 30  GND     ← Botón EMPEZAR + GND   │
GPIO  6 │ 31 ●● 32  GPIO 12 ← Botón APAGAR + Niv MAX│
GPIO 13 │ 33 ●● 34  GND     ← Nivel MIN + GND       │
GPIO 19 │ 35 ●● 36  GPIO 16 ← EV #3 (CH1) + Bomba(CH2)│
GPIO 26 │ 37 ●● 38  GPIO 20 ❌ DAÑADO    ❌ DAÑADO   │
   GND  │ 39 ●● 40  GPIO 21                ❌ DAÑADO│
        │                                             │
        └─────────────────────────────────────────────┘
                            USB / Ethernet side
```

---

## Tabla de conexiones por componente

### Alimentación

| Componente | Pin físico Pi | Notas |
|---|---|---|
| 5V para módulo relé y módulos auxiliares | Pin 2 (5V) | También pin 4 disponible |
| GND común | Pin 6 (GND) | También pin 9, 14, 20, 25, 30, 34, 39 |

### Salidas — Módulo de relé 8 canales (Songle SRD-05VDC-SL-C)

⚠️ Active-HIGH para este módulo en particular

| Carga AC controlada | Canal módulo | Pi GPIO | Pin físico | Estado |
|---|---|---|---|---|
| EV #3 (llenado botellón) | IN1 / CH1 | GPIO 19 | Pin 35 | ✅ Validado |
| Bomba despacho 220V | IN2 / CH2 | GPIO 16 | Pin 36 | ✅ Validado |
| EV #1 (entrada bombas RO) | IN3 / CH3 | GPIO 27 | Pin 13 | 🟡 Planeado |
| EV #2 (salida RO / flush) | IN4 / CH4 | GPIO 22 | Pin 15 | 🟡 Planeado |
| Lámpara UV | IN5 / CH5 | GPIO 23 | Pin 16 | 🟡 Planeado |
| Generador ozono | IN6 / CH6 | GPIO 24 | Pin 18 | 🟡 Planeado |
| (Reserva) | IN7 / CH7 | — | — | — |
| (Reserva) | IN8 / CH8 | — | — | — |

### Salidas — MOSFET para bombas RO 24VDC (controladas en paralelo)

| Carga | Pi GPIO | Pin físico | Notas |
|---|---|---|---|
| 2× Bombas RO (en paralelo, 1 driver) | GPIO 25 | Pin 22 | Via MOSFET IRLZ44N + diodo flyback |

### Entradas — Botones del panel frontal (con pull-up interno)

| Botón | Pi GPIO | Pin físico | Otro cable |
|---|---|---|---|
| EMPEZAR (verde) | GPIO 5 | Pin 29 | Pin 30 (GND) |
| APAGAR (rojo) | GPIO 6 | Pin 31 | Pin 34 (GND) |

### Entradas — Sensores de nivel del tanque (flotadores reed switch)

| Sensor | Pi GPIO | Pin físico | Otro cable |
|---|---|---|---|
| Nivel MIN (fondo del tanque) | GPIO 13 | Pin 33 | Pin 34 (GND) |
| Nivel MAX (tope del tanque) | GPIO 12 | Pin 32 | Pin 34 (GND) |

### Entradas — Caudalímetro JINGRUI JR-A168

| Cable caudalímetro | Conexión | Pin físico |
|---|---|---|
| Rojo (VCC, 5V) | Pin 2 (5V Pi) | Pin 2 |
| Negro (GND) | Pin 6 (GND Pi) | Pin 6 |
| Amarillo (señal pulso) | Divisor 1kΩ+2kΩ → GPIO 17 | Pin 11 |

### Entradas — Sondas TDS via ADC ADS1115 (I2C)

| Componente | Pi GPIO | Pin físico | Notas |
|---|---|---|---|
| ADS1115 SDA | GPIO 2 (SDA) | Pin 3 | Bus I2C |
| ADS1115 SCL | GPIO 3 (SCL) | Pin 5 | Bus I2C |
| ADS1115 VCC | 3.3V | Pin 1 | — |
| ADS1115 GND | GND | Pin 9 | — |
| Sonda TDS pre-RO | ADS1115 canal A0 | — | Analógico |
| Sonda TDS post-RO | ADS1115 canal A1 | — | Analógico |

### Entradas — Lector RFID PN532 (NFC para tarjeta Socio Kowen)

| Componente PN532 | Pi GPIO | Pin físico | Notas |
|---|---|---|---|
| VCC | 3.3V | Pin 1 o 17 | — |
| GND | GND | Pin 14 o 20 | — |
| SDA (I2C) | GPIO 2 (SDA) | Pin 3 | Compartido con ADS1115 |
| SCL (I2C) | GPIO 3 (SCL) | Pin 5 | Compartido con ADS1115 |
| IRQ (opcional) | GPIO 4 | Pin 7 | Si se quiere interrupt |

### Pines ❌ DAÑADOS — NO usar

| GPIO | Pin físico | Notas |
|---|---|---|
| GPIO 21 | Pin 40 | Identificado dañado durante testing inicial |
| GPIO 20 | Pin 38 | Identificado dañado durante testing |
| GPIO 26 | Pin 37 | Identificado dañado durante testing |

---

## Resumen total de pines usados

| Categoría | Cantidad |
|---|---|
| Salidas (relés AC + MOSFET DC) | 7 GPIOs |
| Entradas digitales (botones + flotadores + caudalímetro) | 5 GPIOs |
| Bus I2C (ADS1115 + PN532) | 2 GPIOs (SDA/SCL compartidos) |
| **Total GPIOs en uso** | **14** |
| GPIOs disponibles para futuras expansiones | ~12 |
| GPIOs dañados (no usables) | 3 |

---

## Fase Alpha (validación en taller) — solo lo mínimo

Para el primer test en el taller, solo conectamos:

1. ✅ **Alimentación Pi** (cargador USB temporal)
2. ✅ **VCC + GND módulo relé** (pin 2 + pin 6)
3. ✅ **CH1 (EV #3) → GPIO 19 (pin 35)**
4. ✅ **CH2 (Bomba despacho) → GPIO 16 (pin 36)**
5. ✅ **Salidas de relé NO/COM → EV #3 + Bomba** (lado AC 220V)

El resto se va agregando en sesiones posteriores siguiendo este mismo mapa.
