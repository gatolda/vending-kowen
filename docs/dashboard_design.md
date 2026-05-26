# Dashboard Kowen — Diseño funcional

App web local para control y monitoreo de la máquina, accesible desde cualquier
dispositivo en la misma red WiFi.

## Objetivos

1. **Visualizar** estado de sensores y actuadores en tiempo real
2. **Operar** la máquina con botones (llenar, flush, producir)
3. **Detener** emergencia con un click siempre visible
4. **Auditar** acciones recientes con log de eventos

## Stack técnico

| Capa | Tecnología | Razón |
|---|---|---|
| Backend | Python + Flask | Liviano, ya tenemos Python en la Pi |
| Real-time | Flask-SocketIO | Updates push sin polling pesado |
| Frontend | HTML + Tailwind CSS (via CDN) + Alpine.js | Sin build step, simple |
| Hardware | gpiozero (ya en uso) | Reutilizamos el código |
| Servicio | systemd | Auto-start en boot |

## Acceso

- URL: `http://raspberrypivendingagua.local:8000`
- O directamente: `http://192.168.1.87:8000`
- Sin auth en MVP (es red privada). En siguiente fase: password básico.

## Estructura visual (mobile-first)

```
┌──────────────────────────────┐
│ 🚰 Kowen Vending             │  ← Header sticky
│ ─────────────────────────────│
│ Sistema 🟢 | Uptime 4h 23m   │
├──────────────────────────────┤
│                              │
│ 📊 ESTADO TANQUE             │
│ ╔══════════════════════════╗ │
│ ║ MAX: 🟢  OUT: ⚪         ║ │
│ ║ Red municipal: 🟢        ║ │
│ ║ Bombas RO: ⚪            ║ │
│ ╚══════════════════════════╝ │
│                              │
│ 🎬 OPERACIONES               │
│ ┌──────────────────────────┐ │
│ │ 💧 Llenar botellón       │ │
│ │  Tiempo: [ 5 ] segundos  │ │
│ │ ┌──────────────────────┐ │ │
│ │ │  INICIAR LLENADO     │ │ │
│ │ └──────────────────────┘ │ │
│ └──────────────────────────┘ │
│                              │
│ ┌──────────────────────────┐ │
│ │ 🔄 Flush sistema         │ │
│ │ ┌──────────────────────┐ │ │
│ │ │  INICIAR FLUSH       │ │ │
│ │ └──────────────────────┘ │ │
│ └──────────────────────────┘ │
│                              │
│ ┌──────────────────────────┐ │
│ │ ⚗️ Producir agua          │ │
│ │ ┌──────────────────────┐ │ │
│ │ │  INICIAR PRODUCCIÓN  │ │ │
│ │ └──────────────────────┘ │ │
│ └──────────────────────────┘ │
│                              │
│ 🔧 ACTUADORES (lectura)      │
│ ┌──────────────────────────┐ │
│ │ CH1 EV #3 llenado    ⚪  │ │
│ │ CH2 Bomba despacho   ⚪  │ │
│ │ CH4 EV #2 salida     ⚪  │ │
│ │ CH5 UV               ⚪  │ │
│ │ CH6 Ozono            ⚪  │ │
│ │ CH7 EV #1 entrada    ⚪  │ │
│ │ CH8 Reserva          ⚪  │ │
│ └──────────────────────────┘ │
│                              │
│ 📋 EVENTOS RECIENTES         │
│ ┌──────────────────────────┐ │
│ │ 14:23 ✓ Llenado completo │ │
│ │ 14:18 ✓ Flush completo   │ │
│ │ 14:15 ⚠ Bombas iniciadas │ │
│ └──────────────────────────┘ │
│                              │
└──────────────────────────────┘
┌──────────────────────────────┐
│       🛑 STOP TODO           │  ← Sticky bottom
└──────────────────────────────┘
```

## Paleta de colores

| Estado | Color | Símbolo |
|---|---|---|
| OK / Activo | Verde #10b981 | 🟢 |
| Inactivo / Idle | Gris #6b7280 | ⚪ |
| Atención / Operando | Amarillo #f59e0b | 🟡 |
| Alarma / Emergencia | Rojo #ef4444 | 🔴 |
| Daño / NA | Gris oscuro | ❌ |

## Comportamiento

### Operaciones (botones)
- Click → confirmación inline (si es destructivo)
- Inicia el script correspondiente como subprocess
- Cambia botón a "⏳ Ejecutando..." con barra de progreso si aplica
- Al terminar: vuelve a estado normal + log de evento
- Si falla: log con ✗ + alerta visual

### Sensores (lectura)
- Update via WebSocket cada 500ms o por evento
- Cambio de estado → animación suave (color flash)
- Mostrar timestamp del último cambio

### Actuadores (estado)
- Update via WebSocket cada 500ms
- Solo lectura por ahora (no permite control manual desde aquí)
- En sesión futura: botón individual para activar (con confirmación)

### Stop emergencia
- **Siempre visible** (sticky bottom)
- Color rojo intenso
- Click → mata cualquier script corriendo
- Apaga TODOS los relés
- Sin confirmación (es seguridad, debe ser inmediato)

### Log de eventos
- Últimos 50 eventos
- Persistente entre sesiones (archivo JSON o SQLite)
- Cada evento: timestamp, tipo, mensaje
- Color según severidad

## Endpoints del backend

```
GET  /                       → index.html
GET  /api/status             → JSON con estado actual
                                {
                                  "sensors": {...},
                                  "relays": {...},
                                  "uptime": "...",
                                  "running_script": null,
                                  "events": [...]
                                }

POST /api/operation/fill     → inicia fill_bottle.py {seconds: 5}
POST /api/operation/flush    → inicia flush.py
POST /api/operation/produce  → inicia produce_water.py
POST /api/stop               → mata script + todos los relés OFF

WS   /ws                     → real-time updates
                                {sensors, relays, event}
```

## Plan de implementación (3-4 sesiones)

### Sesión 1 — MVP backend
- Flask server básico
- Endpoints sin frontend bonito
- Test desde curl/Postman

### Sesión 2 — Frontend MVP
- HTML estático con Tailwind
- Botones para las 3 operaciones
- Estado de relés via polling

### Sesión 3 — Real-time + logs
- WebSocket para updates
- Log persistente
- Mejoras visuales

### Sesión 4 — Refinamiento
- Manejo de errores robusto
- Servicio systemd
- Documentación de uso

## Pendiente para fases futuras

- Autenticación (usuario/password)
- Acceso remoto (Tailscale o reverse SSH)
- Logs en Supabase
- Telegram bot integrado
- Dashboard admin con histórico
- Multi-tenant (para varios operadores)
