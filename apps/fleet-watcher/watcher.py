#!/usr/bin/env python3
"""
Fleet watcher — vigila Supabase y manda alertas a Telegram.

Corre en el VPS (NO en la Pi), justamente para poder detectar cuando una
máquina se cae o se queda sin internet (eso una Pi caída no lo puede avisar
de sí misma).

Detecta y alerta:
  - Eventos críticos nuevos (level 'warn' o 'err') en la tabla `events`
  - Máquina OFFLINE: si no llega un heartbeat en OFFLINE_THRESHOLD_S
  - Máquina ONLINE de nuevo (recuperación)

Solo usa librería estándar (no requiere pip install).

Config por entorno (.env junto a este archivo):
  SUPABASE_URL            https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY    secret key (lee con bypass de RLS)
  TELEGRAM_BOT_TOKEN      token del bot (@BotFather)
  TELEGRAM_CHAT_ID        a quién mandar las alertas
  OFFLINE_THRESHOLD_S     seg sin heartbeat = offline (default 300)
  POLL_INTERVAL_S         cada cuánto chequea (default 30)
  ALERT_COOLDOWN_S        no repetir el mismo mensaje antes de esto (default 600)
"""

import os
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta


def _load_dotenv(path):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass


_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
OFFLINE_THRESHOLD = float(os.environ.get("OFFLINE_THRESHOLD_S", "300"))
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL_S", "30"))
ALERT_COOLDOWN = float(os.environ.get("ALERT_COOLDOWN_S", "600"))

# Íconos por nivel de evento
LEVEL_ICON = {"err": "🔴", "warn": "🟡", "ok": "🟢", "info": "ℹ️"}


def _sb_get(path):
    """GET a la API REST de Supabase. Devuelve lista de dicts."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    req = urllib.request.Request(url)
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def send_telegram(text):
    """Manda un mensaje al chat configurado. No lanza (loguea y sigue)."""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": text}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print("Telegram error:", e)
        return False


def main():
    if not (SUPABASE_URL and SUPABASE_KEY):
        raise SystemExit("Faltan SUPABASE_URL / SUPABASE_SERVICE_KEY en el .env")
    if not (TG_TOKEN and TG_CHAT):
        raise SystemExit("Faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID en el .env")

    # Arrancar desde el último evento actual: no queremos re-alertar el historial
    try:
        latest = _sb_get("events?select=id&order=id.desc&limit=1")
        last_id = latest[0]["id"] if latest else 0
    except Exception as e:
        print("No pude leer events al inicio:", e)
        last_id = 0

    offline = {}      # machine_id -> True si ya avisamos que está offline
    last_alert = {}   # clave -> timestamp del último envío (anti-spam)

    def should_send(key):
        now = time.time()
        if last_alert.get(key, 0) + ALERT_COOLDOWN > now:
            return False
        last_alert[key] = now
        return True

    print(f"Fleet watcher iniciado. Poll cada {POLL_INTERVAL:.0f}s, offline a los {OFFLINE_THRESHOLD:.0f}s.")
    send_telegram("🤖 Fleet watcher iniciado — vigilando máquinas.")

    while True:
        # ── 1) Eventos críticos nuevos ──
        try:
            rows = _sb_get(
                f"events?select=id,machine_id,level,message,ts"
                f"&id=gt.{last_id}&level=in.(warn,err)&order=id.asc"
            )
            for ev in rows:
                last_id = max(last_id, ev["id"])
                key = f"{ev['machine_id']}:{ev['message']}"
                if not should_send(key):
                    continue  # mismo mensaje hace poco → no spamear
                icon = LEVEL_ICON.get(ev["level"], "•")
                send_telegram(f"{icon} [{ev['machine_id']}] {ev['message']}")
        except Exception as e:
            print("Error chequeando eventos:", e)

        # ── 2) Máquinas offline / recuperadas ──
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(seconds=OFFLINE_THRESHOLD)).isoformat()
            cutoff_q = urllib.parse.quote(cutoff, safe="")
            machines = _sb_get("machines?select=id,nombre")
            for m in machines:
                mid = m["id"]
                recent = _sb_get(
                    f"heartbeats?select=id&machine_id=eq.{mid}&ts=gte.{cutoff_q}&limit=1"
                )
                is_online = len(recent) > 0
                if not is_online and not offline.get(mid):
                    offline[mid] = True
                    send_telegram(f"🔴 [{mid}] {m.get('nombre','')} OFFLINE — sin datos hace +{OFFLINE_THRESHOLD/60:.0f} min")
                elif is_online and offline.get(mid):
                    offline[mid] = False
                    send_telegram(f"🟢 [{mid}] {m.get('nombre','')} volvió ONLINE")
        except Exception as e:
            print("Error chequeando heartbeats:", e)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
