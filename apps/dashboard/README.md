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

## Auto-start en boot (opcional)

Para que el dashboard arranque solo al encender la Pi:

```bash
sudo nano /etc/systemd/system/kowen-dashboard.service
```

Pegar:
```ini
[Unit]
Description=Kowen Dashboard
After=network-online.target

[Service]
WorkingDirectory=/home/kowen/vending-kowen/apps/dashboard
ExecStart=/usr/bin/python3 /home/kowen/vending-kowen/apps/dashboard/app.py
Restart=always
User=kowen

[Install]
WantedBy=multi-user.target
```

Habilitar:
```bash
sudo systemctl enable kowen-dashboard
sudo systemctl start kowen-dashboard
sudo systemctl status kowen-dashboard
```

## Roadmap

- [x] MVP: operaciones + estado actuadores + logs
- [ ] Lectura de sensores (MAX, OUT, presostato) en vivo
- [ ] Logs persistentes (SQLite)
- [ ] Auth básico (password)
- [ ] WebSocket para updates más eficientes
- [ ] Integración con Telegram alerts
- [ ] Sync a backend Supabase
