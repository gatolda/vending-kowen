# Dashboard Kowen

App web Flask para control y monitoreo de la máquina vending desde cualquier
dispositivo en la misma red WiFi.

## Instalación en la Pi

```bash
# Una vez:
sudo apt install -y python3-flask

# Después siempre que actualicemos:
cd ~/vending-kowen
git pull
```

## Correr la app

```bash
cd ~/vending-kowen/apps/dashboard
python3 app.py
```

Va a imprimir algo como:
```
 * Running on http://0.0.0.0:8000
```

## Acceso

Desde cualquier dispositivo en la misma WiFi:

- **Hostname**: http://raspberrypivendingagua.local:8000
- **Por IP**: http://192.168.1.87:8000 (ajustar a tu IP)

## Funcionalidades

### Operaciones (botones)
- **💧 Llenar botellón**: ciclo de despacho con tiempo configurable (1-60s)
- **🔄 Flush sistema**: ciclo de flush de la membrana RO (~17s)
- **⚗️ Producir agua**: flush + producción para llenar tanque (timeout 5min)

### Vista en vivo
- Estado de cada actuador (CH1-CH8) con LED virtual
- Operación en curso con banner
- Uptime del sistema
- Log de los últimos 20 eventos

### Stop emergencia
- Botón rojo siempre visible al fondo
- Apaga TODOS los relés inmediatamente
- Mata cualquier operación en curso

## Endpoints API

```
GET  /                       → dashboard HTML
GET  /api/status             → estado actual JSON
POST /api/operation/fill     → inicia llenado (body: {"seconds": 5})
POST /api/operation/flush    → inicia flush
POST /api/operation/produce  → inicia producción
POST /api/stop               → emergencia
```

## Auto-start en boot (systemd)

El archivo del servicio ya está versionado en el repo: `kowen-dashboard.service`.
Para instalarlo (una sola vez):

```bash
# Copiar el unit file al directorio de systemd
sudo cp ~/vending-kowen/apps/dashboard/kowen-dashboard.service /etc/systemd/system/

# Recargar systemd, habilitar (arranque en boot) y arrancar ahora
sudo systemctl daemon-reload
sudo systemctl enable --now kowen-dashboard

# Verificar
sudo systemctl status kowen-dashboard
```

Operación diaria:
```bash
sudo systemctl restart kowen-dashboard   # reinicio limpio (apaga relés ordenadamente vía SIGTERM)
sudo systemctl stop kowen-dashboard      # parar
sudo systemctl start kowen-dashboard     # arrancar
journalctl -u kowen-dashboard -f         # ver logs en vivo
```

Tras actualizar el código (`git pull`), aplicar con:
```bash
sudo systemctl restart kowen-dashboard
```

> Nota: ya no hace falta correr `python3 app.py` a mano ni usar `pkill`.
> El servicio captura SIGTERM y apaga todos los relés antes de salir.
> El dashboard arranca solo tras un corte de luz o reinicio de la Pi.

## Roadmap

- [x] MVP: operaciones + estado actuadores + logs
- [ ] Lectura de sensores (MAX, OUT, presostato) en vivo
- [ ] Logs persistentes (SQLite)
- [ ] Auth básico (password)
- [ ] WebSocket para updates más eficientes
- [ ] Integración con Telegram alerts
- [ ] Sync a backend Supabase
