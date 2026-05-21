# Compras — Primera máquina (validación end-to-end)

Lista completa para integrar UNA máquina Kowen con todos los componentes funcionando.
Total estimado: **~$164 USD (~$155.000 CLP)** + items "one-time".

---

## 🔌 Cómputo y alimentación

| Item | Especificación | $ USD | $ CLP aprox |
|---|---|---|---|
| Raspberry Pi 3/4 | ya lo tenés ✓ | — | — |
| MicroSD 32GB clase 10 industrial | Samsung PRO Endurance | $10 | $9.000 |
| Fuente Mean Well IRM-05-5 | 5V/3A, montaje PCB | $8 | $7.500 |
| UPS HAT | UPS Lite 1S | $15 | $14.000 |
| **Subtotal cómputo** | | **$33** | **$30.500** |

## ⚡ Control (módulo relés + cableado)

| Item | Especificación | $ USD | $ CLP aprox |
|---|---|---|---|
| Módulo relé Songle SRD-05VDC | 8 canales, 30A AC | $12 | $11.000 |
| Cables Dupont 40pcs M-H | macho-hembra 20cm | $3 | $3.000 |
| Cables Dupont 40pcs M-M | macho-macho | $3 | $3.000 |
| **Bornera tornillo 5V** | regleta plástica 6-8 polos | $3 | $3.000 |
| **Bornera tornillo GND** | regleta plástica 8-10 polos | $3 | $3.000 |
| **Subtotal control** | | **$24** | **$23.000** |

## 🔧 Componentes electrónicos pequeños

| Item | Especificación | $ USD | $ CLP aprox |
|---|---|---|---|
| Kit resistencias surtidas | incluye 1kΩ, 2kΩ, 4.7kΩ, 10kΩ | $3 | $3.000 |
| Optoacopladores PC817 ×6 | para billetero/monedero/inhibits | $2 | $2.000 |
| PCB perfboard 8×12cm | doble cara | $2 | $2.000 |
| Terminales tornillo regletas | 6 pos ×5 | $5 | $5.000 |
| **Subtotal electrónica** | | **$12** | **$12.000** |

## 💧 Sensores agua (TDS + ADC)

| Item | Especificación | $ USD | $ CLP aprox |
|---|---|---|---|
| ADC ADS1115 | 16-bit I2C 4 canales | $5 | $5.000 |
| Sondas TDS analógicas ×2 | Gravity TDS sensor | $10 | $10.000 |
| **Subtotal sensores agua** | | **$15** | **$15.000** |

## 💳 RFID / NFC

| Item | Especificación | $ USD | $ CLP aprox |
|---|---|---|---|
| Lector PN532 | I2C o SPI | $10 | $10.000 |
| Tarjetas MIFARE NTAG (stock) | 10 unidades para testing | $5 | $5.000 |
| **Subtotal RFID** | | **$15** | **$15.000** |

## 📦 Mecánica e instalación

| Item | Especificación | $ USD | $ CLP aprox |
|---|---|---|---|
| Caja IP65 plástica | 200×150×80mm con prensaestopas | $10 | $9.000 |
| Conectores Dupont + crimpadora barata | si no tenés | $5 | $5.000 |
| Cables internos calibre 16AWG | 2m de cada color (rojo, negro, verde) | $5 | $5.000 |
| Cinta aisladora colores | 4 rollos | $3 | $3.000 |
| Marcador permanente fino | etiquetar cables | $2 | $2.000 |
| **Subtotal mecánica** | | **$25** | **$24.000** |

## 🔍 Sensores corriente (opcional)

| Item | Especificación | $ USD | $ CLP aprox |
|---|---|---|---|
| Sensor corriente CT SCT-013-030 ×2 | uptime bomba RO + UV (opcional) | $10 | $10.000 |
| **Subtotal opcional** | | **$10** | **$10.000** |

## 🚫 Lo que NO compras para primera máquina

- ❌ **JSN-SR04T** ($8) — máquina trae 3 flotadores reed switch
- ❌ **MOSFETs + diodos + disipadores** ($4) — bombas RO se controlan via corte AC al transformador
- ❌ **Transductor presión** ($20) — diferido a post-piloto
- ❌ **Fuente Mean Well 24V** ($15) — máquina trae transformador 24V interno
- ❌ **Pi Zero 2W extra** — usar la Pi que ya tenés

---

## 🛠️ Herramientas "one-time" (sirven para todas las máquinas)

Esto lo comprás UNA vez, sirve para las 15 máquinas:

| Item | $ USD | $ CLP | Dónde |
|---|---|---|---|
| Analizador lógico USB | $15 | $14.000 | MercadoLibre / AliExpress |
| Multímetro decente (si no tenés) | $15-30 | $14.000-28.000 | Sodimac/Easy |
| Soldador + estaño + soporte | $20 | $19.000 | Sisymsa, Anatel |
| Crimpadora Dupont (opcional) | $10 | $9.000 | MercadoLibre |
| **Total herramientas** | **$60** | **~$56.000** | |

## 🔌 Para resolver problemas del cargador

| Item | $ USD | $ CLP |
|---|---|---|
| Cable micro-USB CORTO y GRUESO | $3-5 | $3.000-5.000 |
| Cargador de tablet/iPad 2.5A (si no tenés) | $10-15 | $10.000-15.000 |

---

## 💰 Resumen total

| Concepto | $ USD | $ CLP |
|---|---|---|
| Cómputo y alimentación | $33 | $30.500 |
| Control (relés + cableado + borneras) | $24 | $23.000 |
| Componentes electrónicos | $12 | $12.000 |
| Sensores agua | $15 | $15.000 |
| RFID | $15 | $15.000 |
| Mecánica | $25 | $24.000 |
| Sensores corriente (opcional) | $10 | $10.000 |
| **Primera máquina** | **~$134** | **~$129.500** |
| Herramientas one-time | $60 | $56.000 |
| Cable USB + cargador | $15 | $14.000 |
| **TOTAL primera vez** | **~$209** | **~$199.500** |

---

## 🛒 Dónde comprar (Chile)

### MercadoLibre Chile
- Módulo relé 8ch Songle
- Cables Dupont (kits surtidos)
- Resistencias en kit
- ADS1115, PN532, sondas TDS, SCT-013
- Tarjetas MIFARE NTAG
- Analizador lógico USB

**Tiempo entrega: 1-5 días.**

### Sodimac / Easy
- MicroSD (Samsung, Kingston)
- Caja plástica
- Cinta aisladora
- Marcadores
- Cables eléctricos
- Borneras tornillo

**Tiempo entrega: mismo día (retiro tienda).**

### Sisymsa / Anatel (Santiago)
- Componentes electrónicos sueltos (resistencias, capacitores)
- Optoacopladores PC817
- Fuente Mean Well
- Soldador y estaño

**Tiempo entrega: mismo día retiro.**

### Falabella / Ripley
- Cargadores USB de calidad
- Cables USB

---

## ⏱️ Orden de prioridad de compras

Si vas a comprar gradualmente:

**Primera tanda (esta semana, para Fase Alpha en taller):**
- Cable USB corto y grueso ✅
- Borneras 5V + GND ✅
- Resistencias 1kΩ + 2kΩ (kit)
- Analizador lógico USB

**Segunda tanda (próxima semana, para validación completa):**
- ADS1115 + sondas TDS
- PN532 + tarjetas RFID
- Optoacopladores PC817

**Tercera tanda (cuando ya esté validado):**
- UPS HAT
- Caja IP65
- Resto del cableado prolijo
