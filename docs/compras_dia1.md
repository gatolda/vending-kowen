# Compras urgentes — Día 1 taller

Lista mínima para arrancar esta semana. Total estimado: **~$20.000 CLP** (~$22 USD).

No es el BOM completo (ese viene después para las 15 máquinas). Esto es solo lo indispensable para validar la cadena Pi ↔ máquina en una sesión.

---

## 🛒 Para comprar

### Esenciales (sin esto no arrancas)

| Item | Especificación | Dónde | $ CLP aprox |
|---|---|---|---|
| [ ] **MicroSD 32GB clase 10** | Cualquier marca decente (SanDisk, Kingston) | Sodimac / Easy / cualquier tienda | $5.000-8.000 |
| [ ] **Cargador USB pared 5V 2A** | USB-C si Pi 4, microUSB si Pi Zero 2W | Tienda celular / Falabella | $5.000-8.000 |
| [ ] **Módulo relé 2 canales** | "Relay module 2 channel 5V" con opto integrado | MercadoLibre Chile | $3.000-5.000 |
| [ ] **Kit cables Dupont 40pcs M-H** | Macho-Hembra, 20cm de largo | MercadoLibre / Sisymsa | $2.000-3.000 |
| [ ] **2 resistencias** | 1kΩ y 2kΩ (1/4W) | Sisymsa / Anatel — o cualquier kit surtido | $500-2.000 |

### Insumos (probablemente ya tienes algo)

| Item | Notas |
|---|---|
| [ ] Cinta aisladora | Para etiquetar cables. $1.000 si no tienes |
| [ ] Marcador permanente fino | Para escribir en cinta. $2.000 si no tienes |
| [ ] Lector microSD (USB) | Solo si tu laptop no tiene ranura SD. $2.000 si necesitas |
| [ ] Tester multímetro | Ya lo tienes ✅ |
| [ ] Destornilladores planos y phillips | Para abrir gabinete |

**Total mínimo (sin extras que ya tengas): ~$15.500-26.000 CLP**

---

## 🚫 NO comprar todavía

Esto va en el BOM completo después, NO para Día 1:
- ❌ Módulo relé 8 canales (ya tienes uno de 2ch que sobra para hoy)
- ❌ MOSFETs IRLZ44N (no controlamos bombas DC en Día 1)
- ❌ Sondas TDS, ADS1115, JSN-SR04T, PN532 (sensores avanzados, viene en sesiones siguientes)
- ❌ UPS HAT, Mean Well IRM-05-5 (alimentación definitiva, no temporal)
- ❌ Optoacopladores PC817 (Día 1 solo tiene caudalímetro y relés, sin billetero/monedero)
- ❌ Caja IP65 (montaje definitivo)

Estos los compras todos juntos en una orden grande de AliExpress/MercadoLibre cuando ya tengas el alcance validado.

---

## 🛒 Dónde comprar (Chile)

| Tienda | Qué conviene | Tiempo |
|---|---|---|
| **MercadoLibre Chile** | Módulo relé, cables Dupont, kits resistencias | 1-3 días |
| **Sodimac / Easy** | SD card, cinta aisladora, marcadores, fuente USB básica | mismo día |
| **Sisymsa (Santiago)** | Componentes electrónicos sueltos si necesitas resistencias específicas | mismo día retiro |
| **Falabella / Ripley** | Cargador USB de calidad | mismo día |
| **Anatel** | Componentes electrónicos profesionales | mismo día |

---

## ✅ Antes de salir al taller

- [ ] SD flasheada con Raspberry Pi OS Lite (ver `day_1_taller.md` Parte A)
- [ ] Pi probada en casa, SSH funciona
- [ ] `pigpio` instalado y corriendo
- [ ] Pi apagada correctamente (`sudo shutdown now`)
- [ ] Llevar al taller: Pi + SD adentro + cargador + módulo relé + cables Dupont + resistencias + multímetro + cinta + marcador + laptop
- [ ] Celular con hotspot WiFi configurado (mismo SSID/pass que pusiste en el Imager)
