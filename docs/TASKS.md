# Tareas - Roadmap del piloto Kowen

Versión: 2026-05-14
Estado base: firmware `edge-water` ya funcional (dispensado + MQTT + tests). Falta toda la capa de pagos, control total del RO, RFID, y backend/dashboard.

---

## Fase 0 — Cerrar Reverse Engineering en taller

Trabajo de campo, requiere acceso físico a una máquina Kowen.

### Componentes ya identificados por modelo (no necesitan RE)
- Caudalímetro: JINGRUI JR-A168 (Hall 3 cables, ~330 p/L nominal)
- Electroválvulas: SAN YE 2W-160-15 (AC 220V)
- Bombas: B.N.Q.S. DP-125-200W (24VDC 2.5A) — 2 RO + 1 despacho

### Tareas RE pendientes
- [ ] Mapear las **7 cargas eléctricas (5 AC + 2 DC)**: qué cable de la placa Kowen controla cada actuador. AC: EV#1, EV#2, EV#3, UV, ozono. DC: ro_pumps (2 bombas juntas en 1 driver), dispense_pump.
- [x] ~~Confirmar número exacto de electroválvulas~~ — **CONFIRMADO 3 EV** (entrada bombas RO + salida RO + llenado botellón)
- [x] ~~Verificar fuente 24VDC interna~~ — **CONFIRMADO existe**, no se compra Mean Well
- [x] ~~Verificar línea de drenaje de las membranas RO~~ — **CONFIRMADA siempre abierta**. Concentrate flush via EV #2 queda viable sin riesgo de deadheading de bombas.
- [ ] Caracterizar billetero ICT: confirmar DIP switches en modo Pulse, configurar 1 pulso = $1.000 CLP, medir voltaje lógico de salida
- [ ] Reprogramar monedero: aceptar solo $100 ($100=1p) y $500 ($500=5p), bloquear el resto
- [ ] RE del PCB de displays 7-seg: identificar si es shift register / direct multiplex / driver dedicado (probablemente con analizador lógico)
- [ ] Verificar estado del lector RFID original (probable reemplazo con PN532 igual)
- [ ] **Decidir si agregamos transductor de presión electrónico** ($20 USD), o nos quedamos solo con el manómetro mecánico existente
- [ ] Documentar wiring completo en `docs/wiring.md` con foto + tabla de conectores

---

## Fase 1 — Compras

- [ ] Comprar BOM completo para 15 máquinas (~$3,100 USD, rev 2) — ver `BOM.md`
- [ ] Comprar analizador lógico USB ($15) — crítico para RE displays
- [ ] Comprar stock inicial 100 tarjetas RFID MIFARE/NTAG ($50)
- [ ] Comprar filtros de repuesto para 1 ciclo completo del piloto ($570)
- [ ] Tener Pi 4 de banco montado y listo para desarrollo en taller

---

## Fase 2 — Extender firmware `edge-water`

Lo que ya existe (no tocar a menos que sea necesario):
- Driver de válvula + bomba + caudalímetro YF-S201
- Máquina de estados de dispensado con idempotencia
- Bus MQTT con tópicos definidos
- Heartbeat, LeakWatcher, Telemetry events
- Tests (22), simulador interactivo, CLI

Lo que falta agregar:

### Drivers de hardware nuevos
- [ ] `hardware/coin_acceptor.py` — lectura pulse del monedero vía optoacoplador a GPIO
- [ ] `hardware/bill_acceptor.py` — lectura pulse del billetero ICT vía optoacoplador
- [ ] `hardware/rfid_reader.py` — PN532 vía SPI o I2C (sugerido `nfcpy` o `adafruit-circuitpython-pn532`)
- [ ] `hardware/tds_sensor.py` — sondas TDS analógicas vía ADS1115 (sugerido `adafruit-circuitpython-ads1x15`)
- [ ] `hardware/level_sensor.py` — JSN-SR04T ultrasónico, lectura por trigger/echo GPIO
- [ ] `hardware/pressure_sensor.py` — transductor 0-1.2 MPa con salida 0.5-4.5V via ADS1115 (si se agrega)
- [ ] `hardware/current_sensor.py` — SCT-013 vía ADS1115 (otro canal)
- [ ] `hardware/display.py` — driver de 7-seg (depende del resultado de RE)
- [ ] `hardware/ac_relay_bank.py` — control de las 5 cargas AC (3 EV + UV + ozono) via módulo Songle
- [ ] `hardware/dc_pump_driver.py` — control de las 3 bombas 24VDC via MOSFETs IRLZ44N (PWM opcional para soft-start)
- [ ] Refactor `hardware/pump.py` y `hardware/valve.py` para soportar múltiples instancias nombradas (`ro_pump_1`, `ro_pump_2`, `dispense_pump`, `solenoid_inlet`, `solenoid_ro`, `solenoid_dispense`)

Cada uno con `Mock` para tests + `Real` para producción, siguiendo el patrón ya establecido en `hardware/`.

### Lógica de negocio
- [ ] Máquina de estados de venta extendida:
  - IDLE → (pago detectado vía moneda/billete/tarjeta) → READY_TO_DISPENSE
  - READY_TO_DISPENSE → (cliente presiona EMPEZAR) → DISPENSING
  - DISPENSING → (litros pagados entregados) → COMPLETED
  - Cualquier estado → (timeout / fallo) → ABORTED + alerta Telegram
- [ ] Pago unificado: suma de pulsos billetero + monedero + saldo de tarjeta antes de habilitar EMPEZAR
- [ ] Orden de débito al despachar (suscripción → litros prepagados → saldo CLP)
- [ ] Loop background de llenado de tanque 200L: cuando nivel < umbral, activar EV #1 (entrada) + ambas bombas RO simultáneamente, hasta nivel > 90%
- [ ] Auto-flush programado cada N litros (config en .env) — usar EV #2 RO
- [ ] Loop background de esterilización por ozono: activar generador de ozono X minutos cada Y horas (no por venta, por tiempo)
- [ ] Cache local SQLite de saldos de tarjetas (para mostrar saldo en display)
- [ ] Lógica offline: rechazar tarjeta si no se puede verificar saldo con backend en X segundos

### Eventos nuevos en `messages.py`
- [ ] `PaymentCoinReceived(amount_clp, total_balance_clp)`
- [ ] `PaymentBillReceived(amount_clp, total_balance_clp)`
- [ ] `CardRead(uid, balance_clp, balance_liters)`
- [ ] `CardRejected(uid, reason)` — sin saldo, offline, etc.
- [ ] `SaleStarted(payment_method, amount_clp_or_liters)`
- [ ] `SaleCompleted(liters_dispensed, payment_method)`
- [ ] `TankLevelReport(percent, liters)`
- [ ] `TdsReading(in_ppm, out_ppm, rejection_percent)`
- [ ] `FilterFlushExecuted(reason)`
- [ ] `LowWaterPressure(triggered)`

### Decisión técnica a resolver
- [ ] **MQTT actual vs REST a Supabase:** el firmware usa MQTT con broker propio. Supabase no tiene MQTT nativo. Opciones: (a) mantener MQTT con broker propio + Edge Function que ingiere y lo publica a Supabase, (b) cambiar a REST directo a Supabase, (c) usar Supabase Realtime con polling. Decidir antes de redactar `architecture.md`.

---

## Fase 3 — Backend Supabase

- [ ] Crear proyecto Supabase
- [ ] Aplicar esquema DB inicial (~15 tablas): `machines`, `events`, `sales`, `alerts`, `users`, `operators`, `customers`, `rfid_cards`, `card_transactions`, `card_subscriptions`, `products`, `filter_lifecycle`
- [ ] Configurar Auth + Row Level Security:
  - Admin ve todo
  - Operador ve solo sus máquinas, sus operaciones, sus comisiones
  - Cliente final (futuro) ve solo su tarjeta
- [ ] Service tokens únicos por máquina con permisos limitados a su `machine_id`
- [ ] Edge Function: bot Telegram (alertas críticas, comandos)
- [ ] Edge Function: ingestion de eventos (si vamos por REST) o MQTT bridge
- [ ] Edge Function: cálculo de comisión al registrar `card_transactions`
- [ ] Triggers Postgres para derivar `sales` desde `events`
- [ ] Pre-poblar catálogo semilla de productos (5 productos)

---

## Fase 4 — Dashboard Next.js + Tailwind

### Setup
- [ ] Bootstrapping del proyecto Next.js 14 + Tailwind + Supabase client
- [ ] Configurar PWA manifest + service worker básico
- [ ] Layout responsive (mobile-first para operadores)

### Páginas operador (PWA en celular)
- [ ] Login (Supabase Auth)
- [ ] Home: estado de mis máquinas + accesos rápidos
- [ ] Vender producto: leer tarjeta → seleccionar producto → cobrar → acreditar
- [ ] Buscar tarjeta/cliente
- [ ] Mi negocio: ventas, comisiones

### Páginas admin (escritorio + tablet)
- [ ] Dashboard global: KPIs + mapa de máquinas
- [ ] Máquina detalle: estado vivo, sales, filtros, comandos remotos
- [ ] Clientes CRUD
- [ ] Productos CRUD (incluyendo promociones temporales)
- [ ] Operadores: invitar, asignar máquinas, % comisión
- [ ] Reportes: ventas, retención, anti-fraude
- [ ] Configuración del sistema

---

## Fase 5 — Mecánica e instalación

- [ ] Diseño del montaje del módulo Pi dentro del gabinete Kowen
- [ ] Adaptador para sensor JSN-SR04T en tapa del tanque 200L + tubo guía PVC
- [ ] Puntos de instalación de sondas TDS (T en línea pre-RO y post-RO)
- [ ] Cableado limpio con terminales y etiquetado
- [ ] Documentación fotográfica del primer prototipo armado
- [ ] Plan de restauración estética (vinilos nuevos, limpieza profunda) — paralelo

---

## Fase 6 — Validación

- [ ] Calibración del caudalímetro (K-factor real, contra recipiente medido)
- [ ] Calibración de sondas TDS (con solución de referencia 1413 µS/cm)
- [ ] Pruebas de carga: 50 ventas seguidas sin error
- [ ] Pruebas de fallo: corte de red, corte de agua, Pi reboot mid-sale
- [ ] Pruebas de alertas: forzar "pago sin dispensa" y verificar Telegram
- [ ] Test de tarjeta offline: cortar red, intentar comprar con tarjeta
- [ ] Test de auto-flush: simular N litros producidos, verificar flush

---

## Fase 7 — Despliegue piloto

- [ ] Generar imagen base de SD para producción (con Pi-gen o Packer)
- [ ] Script de provisioning automático (`provision.sh <machine_id> <location>`)
- [ ] Implementar OTA: comando vía Supabase Realtime → `git pull` + `systemctl restart`
- [ ] Instalar máquina #1 en sitio real (piloto cero)
- [ ] Monitoreo intensivo 30 días sin tocar
- [ ] Instalación progresiva #2 a #15 (1-2 por semana)

---

## Fase 8 — Pendientes operacionales/legales

- [ ] Consulta a abogado/contador sobre Ley 21.236 (medios de pago electrónicos)
- [ ] Restauración estética de las 15 máquinas (vinilos, limpieza)
- [ ] Definir contratos con dueños de locales (operadores)
- [ ] Modelo de comisiones final + onboarding de operadores
- [ ] Material de marketing (volantes, banner, demo de tarjeta)
- [ ] Plan de mantenimiento periódico (cambio de filtros, calibraciones)
- [ ] Tabla de costos operativos por máquina/año

---

## Estimaciones de plazo (referenciales, sin compromiso)

| Fase | Duración estimada |
|---|---|
| Fase 0 — RE | 1-2 semanas (depende de disponibilidad taller) |
| Fase 1 — Compras | 4-6 semanas (AliExpress mayoritariamente) |
| Fase 2 — Firmware | 4-6 semanas (paralelo con compras) |
| Fase 3 — Backend | 2-3 semanas |
| Fase 4 — Dashboard | 4-6 semanas |
| Fase 5 — Mecánica | 1-2 semanas (paralelo) |
| Fase 6 — Validación | 2 semanas |
| Fase 7 — Despliegue | 2-4 semanas para llegar a 15 máquinas |
| Fase 8 — Operacional | continuo |

**Línea crítica:** compras (Fase 1) bloquea Fase 2-6 parcialmente. Empezar Fase 1 lo antes posible. Backend (Fase 3) y firmware (Fase 2) pueden avanzar en paralelo desde el primer día.

**Total piloto desde hoy:** ~4-6 meses para tener 15 máquinas operando si todo va bien.
