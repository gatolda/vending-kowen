# Día 1 — Taller: Conectar Pi a la máquina Kowen

Checklist compacto. Imprimir o abrir en celular durante la sesión.

---

## PARTE A — En casa (antes del taller): preparar la Pi

Tiempo estimado: 30 min activos + 10 min de espera.

### A.1 Materiales en casa
- [ ] Raspberry Pi (la que tengas)
- [ ] MicroSD 32GB (mínimo 16GB)
- [ ] Lector microSD para tu laptop
- [ ] Cable de alimentación USB para la Pi (USB-C si es Pi 4, microUSB si es Zero)
- [ ] Laptop con WiFi de la casa para SSH

### A.2 Flashear el OS
1. Descargar **Raspberry Pi Imager** desde https://www.raspberrypi.com/software/
2. Insertar SD en el lector
3. Abrir Imager:
   - **CHOOSE DEVICE**: tu modelo de Pi
   - **CHOOSE OS** → Raspberry Pi OS (other) → **Raspberry Pi OS Lite (64-bit)** (sin escritorio, más liviano)
   - **CHOOSE STORAGE**: tu SD
4. Click **NEXT** → Aparecerá "¿Editar configuración OS?" → **EDIT SETTINGS**:
   - **Hostname:** `kowen-pi-01`
   - **Usuario:** lo que quieras (ej. `kowen`)
   - **Contraseña:** una que recuerdes
   - **WiFi:** SSID + password de tu casa (lo cambiarás en taller)
   - **Locale:** America/Santiago, teclado es-LA
   - **Services** → marcar **Enable SSH** → opción "Use password authentication"
5. Click **SAVE** → **YES** para escribir
6. Esperar ~5 min hasta que diga "Write Successful"
7. Sacar la SD

### A.3 Primer boot en casa
1. Insertar SD en la Pi
2. Conectar fuente USB → la Pi enciende (LED verde parpadea)
3. Esperar ~3 minutos al primer boot (configura todo y se conecta a tu WiFi)
4. Desde laptop: abrir terminal y ejecutar:
   ```
   ssh kowen@kowen-pi-01.local
   ```
   (reemplaza `kowen` por tu usuario)
5. Aceptar fingerprint la primera vez (escribir `yes`)
6. Ingresar contraseña → debería entrar

Si NO entra por `.local`: en el Imager te dijo la IP, o entra a tu router y busca un dispositivo llamado `kowen-pi-01`, conectas con `ssh kowen@<IP>`.

### A.4 Instalar dependencias mínimas en la Pi
Ya conectado por SSH, ejecutar:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y pigpio python3-pigpio python3-pip python3-venv git
sudo systemctl enable --now pigpiod
```

Verificar pigpio activo:
```bash
sudo systemctl status pigpiod
```
Debería decir `active (running)`. Salir con `q`.

### A.5 Apagar correctamente para llevar al taller
```bash
sudo shutdown now
```
Esperar a que el LED verde deje de parpadear (10s), desconectar.

✅ **Listo para llevar al taller.**

---

## PARTE B — En taller: 3 hitos

### B.1 Materiales para el taller (lista compacta)

Mínimo para Día 1:
- [ ] Pi preparada (ya hiciste Parte A)
- [ ] Fuente USB-C o microUSB 5V 2A (cualquiera, el cargador de celular sirve temporal)
- [ ] Cable USB para alimentar la Pi
- [ ] Módulo de relé de **al menos 2 canales** (~$4 USD) — para EV #3 + bomba despacho. Si ya compraste el de 8ch del BOM, mejor.
- [ ] Cables Dupont macho-hembra ×10 (set $3 USD)
- [ ] 2 resistencias: 1kΩ y 2kΩ (cualquier kit de resistencias o sueltas)
- [ ] Multímetro
- [ ] Destornilladores varios
- [ ] Cinta aisladora + marcador permanente (para etiquetar)
- [ ] Celular con hotspot WiFi para que la Pi se conecte en el taller
- [ ] Laptop con SSH (o usar Termius en el celular)

### B.2 Conexión WiFi del taller a la Pi

Antes de ir, en SSH de la casa (o en el primer boot del taller con el WiFi de tu casa todavía):
```bash
sudo raspi-config
```
- 1 System Options → S1 Wireless LAN → ingresar SSID y password del taller (tu hotspot del celular sirve)
- Finish

O más simple en taller: el primer arranque la Pi no encontrará la WiFi de casa, pero si tienes celular con hotspot llamado igual y misma password, conecta automático. Si no, conectar teclado+monitor temporal.

---

### HITO 1 — Alimentar Pi desde la máquina (30 min)

**Objetivo:** La Pi enciende dentro del gabinete Kowen, alimentada por la red 220V del gabinete.

**Pasos:**

1. **Identificar puntos AC 220V dentro del gabinete:**
   - Cerca del medidor DDS3533 hay bornes de fase (L) y neutro (N) accesibles
   - O en el conector "POWER SUPPLY CONNECT POINT" que se ve en la foto del medidor

2. **Para Día 1 (temporal, no definitivo):**
   - Usa cualquier cargador de pared 5V → conecta a un enchufe de extensión que enchufes a la red de la máquina
   - Esto valida que hay electricidad y la Pi enciende, sin meterte aún con cableado interno
   - La fuente Mean Well IRM-05-5 definitiva se instala más adelante con todo el módulo final

3. **Boot de prueba:**
   - Conectar fuente a Pi
   - Esperar 2-3 minutos
   - SSH desde laptop (con hotspot del celular activo, mismo SSID que en config Pi)
   ```
   ssh kowen@kowen-pi-01.local
   ```

✅ **Éxito Hito 1:** ves el prompt de la Pi desde tu laptop, estando físicamente en el taller.

---

### HITO 2 — Leer el caudalímetro JR-A168 (30 min)

**Objetivo:** un script Python cuenta pulsos cuando soplas o pasas agua por el caudalímetro.

**Cableado:**

```
Caudalímetro JR-A168          Raspberry Pi (header 40 pines)
─────────────────────         ───────────────────────────────
cable ROJO   (VCC)    ─────►  Pin 2  (5V)
cable NEGRO  (GND)    ─────►  Pin 6  (GND)
cable AMARILLO (señal) ──┐
                         │
                      R1=1kΩ
                         │
                         ├──► Pin 15 (GPIO 22)
                         │
                      R2=2kΩ
                         │
                         └──► Pin 6 (GND, el mismo de antes)
```

El divisor de voltaje baja la señal de 5V a ~3.3V (seguro para Pi).

**Crear el script de prueba en la Pi:**
```bash
cd ~
nano test_caudal.py
```

Pegar:
```python
import pigpio
import time

pi = pigpio.pi()
PIN = 22

pi.set_mode(PIN, pigpio.INPUT)
pi.set_pull_up_down(PIN, pigpio.PUD_UP)

count = 0
def on_pulse(gpio, level, tick):
    global count
    count += 1

cb = pi.callback(PIN, pigpio.RISING_EDGE, on_pulse)

print("Esperando pulsos. Ctrl+C para salir.")
try:
    while True:
        print(f"Pulsos: {count}")
        time.sleep(1)
except KeyboardInterrupt:
    cb.cancel()
    pi.stop()
```

Guardar (Ctrl+O, Enter, Ctrl+X).

**Ejecutar:**
```bash
python3 test_caudal.py
```

**Probar:**
- Soplar fuerte por el caudalímetro → contador debería subir
- Si no sube, verificar conexiones con multímetro (entre amarillo y GND debería ver pulsos al soplar)

✅ **Éxito Hito 2:** el contador sube al hacer pasar aire o agua.

---

### HITO 3 — Activar EV #3 + bomba despacho 220V desde la Pi (60 min)

**Objetivo:** la Pi enciende y apaga simultáneamente la bomba de despacho (220V AC) Y la electroválvula de llenado del botellón (EV #3, 220V AC). Las dos juntas son las que entregan agua al cliente.

⚠️ **PRECAUCIÓN:** estás trabajando con 220V AC. Desenergizar la máquina antes de cablear. Volver a energizar solo para el test.

**Necesitas un módulo de al menos 2 canales** (o 2 módulos de 1ch). Si llevas el de 8ch del BOM, mejor.

**Cableado:**

```
Lado lógico (Pi → módulo relé):
─────────────────────────────────
Pi Pin 2  (5V)   ──► VCC del módulo
Pi Pin 6  (GND)  ──► GND del módulo
Pi Pin 40 (GPIO 21) ──► IN1 del módulo  (controla EV #3)
Pi Pin 38 (GPIO 20) ──► IN2 del módulo  (controla bomba despacho)
                       (OJO: GPIO 20 es pin 38, no confundir con pin 20)


Lado de potencia (relés → actuadores):
─────────────────────────────────────────
Primero: DESCONECTAR los cables que iban de la placa Kowen a:
  - EV #3 (2 cables) → etiquetar "VENÍA DE PLACA KOWEN - EV3"
  - Bomba de despacho 220V (2 cables) → etiquetar "VENÍA DE PLACA KOWEN - BOMBA"

Luego cablear cada relé como interruptor en serie:

Relé 1 (canal IN1) — EV #3:
  220V FASE     ──► COM relé 1
  NO relé 1     ──► bobina EV #3 (un cable)
  otro cable EV #3 ──► 220V NEUTRO

Relé 2 (canal IN2) — Bomba despacho:
  220V FASE     ──► COM relé 2
  NO relé 2     ──► motor bomba (un cable)
  otro cable bomba ──► 220V NEUTRO
```

**Script de prueba:**
```bash
nano test_despacho.py
```

```python
import pigpio
import time

pi = pigpio.pi()
PIN_EV3 = 21       # GPIO 21 = pin 40
PIN_BOMBA = 20     # GPIO 20 = pin 38

pi.set_mode(PIN_EV3, pigpio.OUTPUT)
pi.set_mode(PIN_BOMBA, pigpio.OUTPUT)

# OJO: muchos módulos relé son "active LOW" (se activan con 0, no con 1).
# Si los relés NO clickean al ejecutar, cambia los valores: ON=0, OFF=1.
ON, OFF = 1, 0

print("Secuencia de despacho de prueba (5 segundos):")
print("  Paso 1: encender bomba")
pi.write(PIN_BOMBA, ON)
time.sleep(0.5)  # esperar a que la bomba presurice

print("  Paso 2: abrir EV #3 (debería empezar a salir agua)")
pi.write(PIN_EV3, ON)
time.sleep(5)

print("  Paso 3: cerrar EV #3")
pi.write(PIN_EV3, OFF)
time.sleep(0.5)

print("  Paso 4: apagar bomba")
pi.write(PIN_BOMBA, OFF)

print("Listo.")
pi.stop()
```

**Por qué la secuencia bomba-primero, EV-segundo:**
- Encender la bomba antes presuriza la línea
- Abrir la EV con bomba ya corriendo da flujo inmediato
- Cerrar la EV antes de apagar la bomba evita golpe de ariete (la bomba no queda empujando contra una válvula cerrada de golpe)

**Ejecutar (máquina ENERGIZADA, tanque con agua):**
```bash
python3 test_despacho.py
```

**Qué debe pasar:**
1. Click del relé 2 (bomba arranca, oirás su zumbido si es de motor)
2. Click del relé 1 (solenoide EV #3 se abre)
3. Sale agua por la boca de despacho del cliente durante 5 segundos
4. Click del relé 1 (EV cierra)
5. Click del relé 2 (bomba se apaga)

✅ **Éxito Hito 3:** sale agua al cliente durante los 5 segundos.

Si **NO sale agua** pero oyes los clicks: la bomba arrancó pero algo del lado hidráulico está raro (tanque vacío, válvula manual cerrada en algún lado, manguera obstruida). Igual cuenta como hito eléctrico OK, sólo hay que solucionar lo hidráulico.

---

## Al cierre del Día 1

Documenta el resultado:

- [ ] Hito 1 OK / falló (razón)
- [ ] Hito 2 OK / falló (razón). Si OK: ¿cuántos pulsos contó aprox por litro?
- [ ] Hito 3 OK / falló (razón). ¿Los relés fueron active-high o active-low? ¿Salió agua o solo clicks?

Si los 3 hitos OK: **felicitaciones, ya tienes la base. Las siguientes sesiones agregan capas (billetero, monedero, RFID, más actuadores) sobre esta misma cadena validada.**

Si alguno falló: anotamos el síntoma y debuggeamos en la próxima conversación.

---

## Apagado seguro

Antes de irte del taller:
```bash
sudo shutdown now
```

Esperar 10 segundos (LED verde deja de parpadear), luego desconectar fuente.

**Si vas a dejar la máquina sin Pi conectada**: reconectar los cables originales de la placa Kowen a la EV #3 que desconectaste en el Hito 3 (los etiquetados con cinta).
