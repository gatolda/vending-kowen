# Fleet Watcher

Vigila Supabase y manda **alertas a Telegram**. Corre en el **VPS** (no en la Pi),
para poder detectar también cuando una máquina se cae o se queda sin internet.

## Qué alerta
- Eventos críticos nuevos (`warn` / `err`): sin presión, backstop, modo auto desactivado, STOP, etc.
- Máquina **offline** (sin heartbeat en +5 min) y su recuperación.

## Requisitos
- Python 3 (solo librería estándar, no hace falta `pip install`)
- Acceso de red a Supabase y a `api.telegram.org`

## Instalación en el VPS

```bash
# 1. Clonar el repo (o git pull si ya está)
cd ~ && git clone https://github.com/gatolda/vending-kowen.git   # o: cd ~/vending-kowen && git pull

# 2. Configurar credenciales
cd ~/vending-kowen/apps/fleet-watcher
cp .env.example .env
nano .env        # completar SUPABASE_SERVICE_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
chmod 600 .env

# 3. Probar a mano (deberías recibir "🤖 Fleet watcher iniciado" en Telegram)
python3 watcher.py
#   Ctrl+C para cortar la prueba
```

## Servicio systemd (arranque automático)

Editá el unit si tu usuario/ruta difieren, después instalalo:

```bash
# Ajustar User= y las rutas en el archivo si hace falta
sudo cp ~/vending-kowen/apps/fleet-watcher/fleet-watcher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fleet-watcher
sudo systemctl status fleet-watcher
journalctl -u fleet-watcher -f      # ver en vivo
```

## Tuning (en el `.env`)
| Variable | Default | Qué hace |
|---|---|---|
| `OFFLINE_THRESHOLD_S` | 300 | Seg sin heartbeat para declarar máquina offline |
| `POLL_INTERVAL_S` | 30 | Cada cuánto consulta Supabase |
| `ALERT_COOLDOWN_S` | 600 | No repite el mismo mensaje antes de este tiempo |
