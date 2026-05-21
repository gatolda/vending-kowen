# Estado actual del proyecto — Checkpoint 2026-05-21

Resumen de lo que está validado, lo que está conectado, y lo que falta. Para retomar mañana sin contexto perdido.

---

## ✅ Validado y funcionando

### Pi
- ✅ Raspberry Pi 3 con Raspberry Pi OS Lite (64-bit), Bookworm
- ✅ SSH configurado: `ssh kowen@raspberrypivendingagua.local` (o IP 192.168.1.87)
- ✅ Hostname: `raspberrypivendingagua`
- ✅ Usuario: `kowen`
- ✅ `gpiozero` + `lgpio` instalados
- ✅ `git` instalado
- ✅ Repo clonado en `~/vending-kowen/`

### Módulo principal de relés (Songle SRD-05VDC-SL-C 8 canales 30A)

**Configuración**: active-HIGH (importante en el código)

**6 canales validados con click + LED**:

| CH | Pin Pi | GPIO | Carga planeada |
|---|---|---|---|
| **CH1** ✅ | Pin 36 | GPIO 16 | EV #3 llenado botellón |
| **CH2** ✅ | Pin 35 | GPIO 19 | Bomba despacho 220V |
| **CH3** ✅ | Pin 13 | GPIO 27 | EV #1 entrada bombas RO |
| **CH4** ✅ | Pin 15 | GPIO 22 | EV #2 salida RO |
| **CH5** ✅ | Pin 16 | GPIO 23 | Lámpara UV |
| **CH6** ✅ | Pin 18 | GPIO 24 | Generador ozono |
| CH7 🟡 | Pin 7 | GPIO 4 | Transformador 24V (→ bombas RO) |
| CH8 🟡 | Pin 26 | GPIO 7 | Reserva |

**Nota**: CH7 y CH8 sin cablear todavía pero GPIOs disponibles.

### Cables al módulo

- ✅ VCC del módulo → Pi pin 2 (5V)
- ✅ GND del módulo → Pi pin 6 (GND)
- ✅ IN1-IN6 cableados a los pines indicados arriba
- 🟡 IN7 e IN8 sin cablear (reservas/futuro)

---

## 🟡 Pendiente cablear (para mañana en taller)

### Lado AC del módulo de relés (cargas físicas)

Conectar el lado de POTENCIA (NO/COM de cada canal) a la carga AC correspondiente:

| Canal | Conectar a... | Voltaje |
|---|---|---|
| CH1 NO/COM | EV #3 llenado botellón | 220V AC |
| CH2 NO/COM | Bomba despacho | 220V AC |
| CH3 NO/COM | EV #1 entrada bombas RO | 220V AC |
| CH4 NO/COM | EV #2 salida RO | 220V AC |
| CH5 NO/COM | Lámpara UV | 220V AC |
| CH6 NO/COM | Generador ozono | 220V AC |
| CH7 NO/COM | Transformador 24V (→ bombas RO) | 220V AC |

**Cableado típico por carga**:
```
Fase 220V máquina ──► COM del relé ──► NO del relé ──► un cable de la bobina/motor
                                                       otro cable ──► Neutro 220V
```

⚠️ **Antes de cablear cada carga**:
1. Desenergizar la máquina
2. Identificar y desconectar los 2 cables que iban de la placa Kowen original a esa carga
3. Etiquetar los cables originales con cinta + marcador
4. Cablear al módulo (lado NO/COM)

### Otros componentes (sesiones siguientes)

- 🟡 Botones EMPEZAR (GPIO 5) y APAGAR (GPIO 6)
- 🟡 Flotadores MAX (GPIO 12), MIN (GPIO 13), OUT (GPIO 18)
- 🟡 Caudalímetro JR-A168 (GPIO 17 + divisor 1kΩ/2kΩ)
- 🟡 ADS1115 + sondas TDS (I2C, pines 3 y 5)
- 🟡 PN532 RFID (I2C, pines 3 y 5)

---

## 🛒 Compras pendientes (para taller)

Lo mínimo para mañana:
- ✅ Pi y módulo relé (ya tenés)
- 🟡 **Cable USB corto y grueso** (para resolver undervoltage)
- 🟡 **Cargador real 5V/2.5A** (si el actual sigue débil)
- 🟡 **Bornera 5V + bornera GND** (para distribución limpia)

---

## 🧪 Scripts disponibles en `~/vending-kowen/scripts/`

| Script | Para qué |
|---|---|
| `dispense_test.py` | Ciclo de despacho (CH1 + CH2 del módulo bombas, pero ahora ajustar si se usa el módulo 8ch) |
| `test_all_channels.py` | Test secuencial CH1-CH8 del módulo principal |

### Comandos clave

```bash
# Bajar última versión del repo
cd ~/vending-kowen && git pull

# Test secuencial completo
python3 scripts/test_all_channels.py

# Test individual de un canal
python3 scripts/test_all_channels.py 3

# Click individual del módulo bombas
python3 scripts/dispense_test.py click ev
python3 scripts/dispense_test.py click pump
```

---

## 🎯 Plan para mañana

### Sesión 1 — Cablear lado AC mínimo (validar agua)

1. Desenergizar máquina
2. Identificar cables de EV #3 (llenado botellón) en la placa Kowen original
3. Desconectarlos, etiquetarlos
4. Cablear a CH1 del módulo (NO/COM)
5. Identificar cables de bomba despacho 220V
6. Desconectarlos, etiquetarlos
7. Cablear a CH2 del módulo (NO/COM)
8. Re-energizar máquina (con tanque lleno de agua)
9. Ejecutar test: `python3 scripts/test_all_channels.py 1 2`
10. Validar que **sale agua** por la boca del cliente

### Sesión 2 — Resto de cargas AC

Repetir el proceso para EV #1, EV #2, UV, ozono, transformador → CH3-CH7.

### Sesión 3 — Entradas

Botones, flotadores, caudalímetro.

### Sesión 4 — I2C

ADS1115 + PN532.

---

## ⚠️ Pines DAÑADOS — no usar

- ❌ GPIO 20 (pin 38)
- ❌ GPIO 21 (pin 40)
- ❌ GPIO 26 (pin 37)

---

## 📋 Decisiones pendientes (no urgentes)

- Decidir MQTT existente vs REST a Supabase (firmware backend)
- Consulta legal Ley 21.236 (tarjetas prepago)
- Compra del BOM completo (~$3,175 USD para piloto 15 máquinas)
