# Vending Kowen — piloto Chile

Sistema de telemetría y control remoto sobre máquinas vending de agua Kowen.
Piloto inicial: 10-15 máquinas en Santiago.

## Estructura del repo

- `apps/edge-water/` — firmware Python en la Raspberry Pi (dispensado, MQTT, telemetría)
- `scripts/` — utilidades de prueba / debugging (ej. `dispense_test.py` para Fase Alpha)
- `docs/` — documentación del proyecto: BOM, tareas, esquemas de conexión, checklist taller

## Estado

Fase Alpha — validación de la cadena Pi ↔ relés ↔ actuadores 220V (bomba despacho + EV #3).

## Documentación clave

- [`docs/BOM.md`](docs/BOM.md) — listado de materiales del módulo Pi (~$168/máquina)
- [`docs/TASKS.md`](docs/TASKS.md) — roadmap del piloto en 8 fases
- [`docs/wiring_diagram.md`](docs/wiring_diagram.md) — esquema de conexiones con diagramas Mermaid
- [`docs/day_1_taller.md`](docs/day_1_taller.md) — checklist de la primera sesión en taller
- [`docs/compras_dia1.md`](docs/compras_dia1.md) — lista compacta de compras urgentes

## Workflow

```
Desarrollo en notebook
        │
   git push (origin/main)
        │
        ▼
   GitHub (privado)
        │
   git pull
        │
        ▼
   Raspberry Pi en taller / máquina
```
