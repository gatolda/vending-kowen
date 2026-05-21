# BOM - Listado de Materiales

Versión: 2026-05-14 (rev 2 — componentes identificados por modelo)
Piloto: 15 máquinas Kowen
Total estimado hardware: **~$3,400 USD**

## Componentes identificados de la máquina Kowen (referencia)

Hardware preexistente que NO compramos (ya está instalado en cada máquina):

| Componente | Modelo | Specs | Cantidad por máquina |
|---|---|---|---|
| Caudalímetro | JINGRUI JR-A168 | Hall 3 cables, 1-30 L/min, ≤1.75 MPa, K~330 p/L | 1 |
| Electroválvulas | SAN YE 2W-160-15 | AC 220V, 16mm orificio, 1/2" | 3 (entrada / RO-flush / despacho) |
| Bombas diafragma | B.N.Q.S. DP-125-200W | 24VDC 2.5A, 2.8 L/min, 82 PSI working | 3 (2 RO + 1 despacho) |
| Lámpara UV | — | 220V AC | 1 |
| Generador ozono | — | 220V AC, dentro del tanque | 1 |
| Manómetro | analógico mecánico | 0-1 MPa, solo visual | 1 |
| Tanque acumulador | acero inox | 200L, externo arriba | 1 |


## Por máquina (~$160 USD)

| # | Componente | Modelo / Especificación | Cant | USD c/u | USD total | Notas |
|---|---|---|---|---|---|---|
| 1 | Raspberry Pi | Pi 4 (R&D) / Pi Zero 2W (producción) | 1 | $35 / $15 | $35 | Pi 4 para los primeros prototipos por debug. Migrar a Zero 2W cuando esté estable |
| 2 | MicroSD | Samsung PRO Endurance 32GB | 1 | $10 | $10 | Industrial grade, soporta escrituras de log |
| 3 | UPS HAT | UPS Lite 1S | 1 | $15 | $15 | Tolerancia a cortes de luz |
| 4 | Fuente AC/DC | Mean Well IRM-05-5 (5V 3A) | 1 | $8 | $8 | Confiable industrial |
| 5 | Módulo relés 8ch | Songle SRD-05VDC-SL-C **30A** | 1 | $12 | $12 | Para las **5 cargas AC**: 3 EV + UV + ozono. Reservas para futuro. NO comprar los baratos 10A |
| ~~5b~~ | ~~MOSFET potencia DC~~ | ~~IRLZ44N~~ | 0 | — | $0 | **NO requerido**: bombas RO se controlan cortando AC al transformador (Relé 7 del módulo Songle) |
| ~~5c~~ | ~~Diodos flyback~~ | ~~1N5408~~ | 0 | — | $0 | **NO requerido** (sin MOSFETs) |
| ~~5d~~ | ~~Disipadores TO-220~~ | — | 0 | — | $0 | **NO requerido** (sin MOSFETs) |
| 6 | Optoacopladores | PC817 | 6 | $0.30 | $2 | Aislar billetero/monedero/caudalímetro/inhibits |
| 7 | ADC I2C | ADS1115 16-bit 4 canales | 1 | $5 | $5 | Para sondas TDS y eventualmente presión |
| 8 | Sondas TDS | TDS sensor analógico (Gravity) | 2 | $5 | $10 | Pre y post RO membrane |
| 9 | ~~Sensor nivel ultrasónico~~ | ~~JSN-SR04T~~ | 0 | — | $0 | **NO requerido**: máquina ya trae 2 flotadores reed switch (MIN + MAX) instalados |
| 10 | Presostato | Low-pressure switch 1/4" 0.3 bar | 1 | $10 | $10 | Protección bomba en seco |
| 11 | Sensor corriente | SCT-013-030 (CT clamp 30A) | 2 | $5 | $10 | Uptime bomba booster + UV |
| 12 | Lector RFID/NFC | PN532 (SPI/I2C/UART) | 1 | $10 | $10 | Reemplaza lector original. Soporta NFC móvil |
| 13 | Caja IP65 | Plástica 200×150×80mm con prensaestopas | 1 | $10 | $10 | Montaje interno al gabinete |
| 14 | PCB perfboard | 8×12cm doble cara | 1 | $2 | $2 | Para acondicionamiento de señales |
| 15 | Conectores Dupont | M-M, M-F, F-F + crimpadora | varios | — | $5 | Cableado interno |
| 16 | Tubo PVC 50mm | Corte 40cm + tapa con orificio | 1 | $3 | $3 | Guía para sensor ultrasónico en tanque |
| 17 | Resistencias kit | 1kΩ, 4.7kΩ, 10kΩ, 15kΩ | kit | — | $3 | Pull-up/down y divisores de voltaje |
| 18 | Terminales tornillo | Regletas 6 pos × 5 | 5 | $1 | $5 | Conexión AC a relés |
| 18b | **Bornera de distribución 5V** | Regleta tornillo plástica 6-8 polos | 1 | $3 | $3 | Distribuir 5V a sensores y módulos |
| 18c | **Bornera de distribución GND** | Regleta tornillo plástica 8-10 polos | 1 | $3 | $3 | Tierra común para todo |
| 18d | Bornera 24VDC (opcional) | Regleta tornillo 4 polos | 1 | $2 | $2 | Distribuir 24V interno a MOSFETs |
| | **Subtotal por máquina** | | | | **~$164** | Sin MOSFETs (bombas RO via relé al transformador). Con borneras 5V+GND. |

## Adicionales fijos (una vez)

| Item | Cantidad | USD | Notas |
|---|---|---|---|
| Analizador lógico USB | 1 | $15 | Saleae clone, para RE de displays 7-seg y billetero |
| Tarjetas MIFARE NTAG | 100 | $50 | Stock inicial Socio Kowen ($0.50 c/u) |
| Pi 4 para banco de pruebas | 1 | $50 | Setup permanente de desarrollo |
| Herramientas extras | varios | $30 | Crimpadora, terminales, soldadura especializada |
| **Subtotal único** | | **$145** | |

## Filtros de respuesto (inicio piloto)

| Item | Por máquina | × 15 | USD total | Notas |
|---|---|---|---|---|
| Filtro sedimento PP | 1 | 15 | $30 | |
| Filtro GAC carbono | 1 | 15 | $30 | |
| Filtro CTO carbono | 1 | 15 | $30 | |
| Membrana RO | 1 (repuesto) | 15 | $300-450 | $20-30 c/u industrial |
| Lámpara UV repuesto | 1 | 15 | $150 | $10 c/u |
| **Subtotal filtros** | | | **~$570** | |

## Total piloto 15 máquinas (versión final 2026-05-14)

| Concepto | USD |
|---|---|
| Hardware módulos Pi (15 × $164) | $2,460 |
| Adicionales fijos | $145 |
| Filtros repuesto | $570 |
| **TOTAL** | **~$3,175 USD** |

Confirmado en taller 2026-05-14:
- Máquina ya trae fuente 24VDC interna (no se compra Mean Well)
- 2 bombas RO se controlan juntas con 1 MOSFET (no 2)
- **Bomba de despacho es 220V AC** (corregido), va por relé del módulo Songle, no por MOSFET
- Sin transductor de presión electrónico (diferido a post-piloto)
- Sin EV de flush dedicada (concentrate flush via software con EV #2)
- Línea de drenaje siempre abierta verificada → concentrate flush seguro

**Excluido (asumido ya existente):** las 15 máquinas Kowen físicas y la infraestructura eléctrica/agua de cada sitio de instalación.

## Costos software/cloud (operativos)

| Servicio | Tier | USD/mes |
|---|---|---|
| Supabase | Free hasta 100MB DB | $0 inicial, $25/mes al crecer |
| Vercel | Free hasta tráfico medio | $0 |
| Dominio + DNS | — | ~$15/año |
| Telegram bot | — | $0 |
| 4G LTE (opcional, no incluido en BOM) | Plan IoT chileno | $5-10/mes/máquina |

## Fuentes de compra recomendadas

- **AliExpress / 1688:** Pi accesorios, optoacopladores, sensores TDS, ADS1115, PN532, JSN-SR04T, módulos relés. Tiempo: 30-45 días, mejor precio.
- **MercadoLibre Chile:** Raspberry Pi oficial, fuentes Mean Well, terminales y conectores. Stock local, sin demora.
- **Sodimac / Easy:** Tubería PVC, cajas IP65, terminales tornillo.
- **Anatel / Sisymsa (Chile):** Componentes electrónicos especializados si AliExpress se demora.
