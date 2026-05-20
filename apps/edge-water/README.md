# edge-water

Firmware para el dispensador de agua a granel. Corre en una Raspberry Pi 4/5
controlando válvula, bomba y caudalímetro YF-S201, y se comunica con el backend
por MQTT.

## Diseño

- **`hardware/`** — protocolos (`Valve`, `Pump`, `FlowMeter`, `StatusLed`) e
  implementaciones `Real` (gpiozero/pigpio) y `Mock` (in-memory para PC/tests).
- **`bus/`** — abstracción pub/sub. `InMemoryBus` para simulador/tests, `MqttBus`
  (aiomqtt) para producción. Wildcards estilo MQTT (`+`, `#`).
- **`messages.py`** — contratos pydantic de comandos (`DispenseCommand`,
  `AbortCommand`) y eventos (`DispenseStarted/Progress/Completed/Failed`,
  `Heartbeat`, `LeakDetected`, `Telemetry`).
- **`dispenser.py`** — máquina de estados del dispensado. Garantiza:
  - Confirmación por **pulsos del caudalímetro**, no por tiempo.
  - **Idempotencia** sobre `order_id` (reentregas del backend no dispensan dos
    veces).
  - Cierre de válvula y bomba **siempre** en `finally`, también en fallo.
  - Modos de fallo: `timeout`, `no_flow`, `aborted`, `busy`, `hardware`,
    `overflow`.
- **`app.py`** — wiring + tareas de fondo: heartbeat periódico y `LeakWatcher`
  (detecta pulsos en estado idle).
- **`cli.py`** — comandos `run` (producción) y `simulate` (interactivo).

## Setup en PC (desarrollo / simulador)

```powershell
cd apps/edge-water
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### Correr los tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

22 tests cubren happy path, atasco, abort, idempotencia, busy, sobreflujo
parcial, cierre seguro de hardware y end-to-end por el bus.

### Simulador interactivo

```powershell
.\.venv\Scripts\edge-water.exe simulate
```

Menú con acciones para dispensar, abortar e inyectar fallas (atasco, fuga,
caudal lento, atasco a mitad de orden). Imprime los eventos que el backend
recibiría en tiempo real.

## Setup en la Raspberry Pi (producción)

1. Instalar pigpio y habilitar el daemon:

   ```bash
   sudo apt install pigpio python3-pigpio
   sudo systemctl enable --now pigpiod
   ```

2. Clonar el repo y crear el venv:

   ```bash
   cd /opt/edge-water
   python3 -m venv .venv
   .venv/bin/pip install -e ".[hardware]"
   ```

3. Copiar `.env.example` a `.env` y editar:
   - `MACHINE_ID` único por máquina
   - `HARDWARE_MODE=real`
   - `BUS_MODE=mqtt` y datos del broker
   - `PULSES_PER_LITER` recalibrado midiendo agua real
   - `RELAY_ACTIVE_LOW` según tu placa de relés

4. Calibración del caudalímetro: dispensar 1 L a un recipiente graduado y
   anotar pulsos reales. Ajustar `PULSES_PER_LITER`. Repetir 3 veces y promediar.

5. Servicio systemd (`/etc/systemd/system/edge-water.service`):

   ```ini
   [Unit]
   Description=Edge water dispenser firmware
   After=network-online.target pigpiod.service
   Requires=pigpiod.service

   [Service]
   WorkingDirectory=/opt/edge-water
   EnvironmentFile=/opt/edge-water/.env
   ExecStart=/opt/edge-water/.venv/bin/edge-water run
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl enable --now edge-water
   journalctl -u edge-water -f
   ```

## Topics MQTT

```
machines/{machine_id}/cmd/dispense          backend → edge
machines/{machine_id}/cmd/abort             backend → edge
machines/{machine_id}/event/dispense_started     edge → backend
machines/{machine_id}/event/dispense_progress    edge → backend
machines/{machine_id}/event/dispense_completed   edge → backend
machines/{machine_id}/event/dispense_failed      edge → backend
machines/{machine_id}/event/heartbeat            edge → backend
machines/{machine_id}/event/leak_detected        edge → backend
machines/{machine_id}/event/telemetry            edge → backend
```

Payloads JSON serializados de los modelos pydantic en `messages.py`. QoS 1.

## Pinout por defecto (BCM)

| Componente   | GPIO | Notas                                       |
|--------------|------|---------------------------------------------|
| Caudalímetro | 17   | YF-S201 (señal). Pull-up interno habilitado |
| Válvula      | 23   | Vía relé (active-low por defecto)           |
| Bomba        | 24   | Vía relé (active-low por defecto)           |
| LED estado   | 18   | ON/OFF simple por ahora                     |

Todos configurables vía `.env`.

## Próximos pasos

- LED RGB WS2812 (parpadeo coloreado por estado).
- Sensor de nivel del estanque (HC-SR04) en `Telemetry`.
- OTA via Balena o Docker + Watchtower.
- Métricas: tasa de éxito, tiempo medio de dispensado, drift de calibración.
