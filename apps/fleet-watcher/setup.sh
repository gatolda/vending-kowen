#!/bin/bash
# Configura el .env del fleet-watcher de forma segura (secretos ocultos).
# Mismo patrón que scripts/setup_cloud.sh: input silencioso → validación →
# backup → replace → restart. Encuentra su propio directorio, así funciona
# en el VPS sin importar dónde esté clonado el repo.
#
# Uso (en el VPS, SIN sudo):
#     bash ~/proyectos/vending-kowen/apps/fleet-watcher/setup.sh
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    echo "❌ No corras esto con sudo (el .env va en tu HOME). Corré: bash $0"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
EXAMPLE_FILE="$SCRIPT_DIR/.env.example"
SERVICE="fleet-watcher.service"

# Si el .env no existe o está vacío, crearlo desde el ejemplo (trae URL + tuning)
if [[ ! -s "$ENV_FILE" ]]; then
    cp "$EXAMPLE_FILE" "$ENV_FILE" 2>/dev/null || touch "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

BACKUP="/tmp/.env.watcher.bak.$$"
trap 'rm -f "$BACKUP"' EXIT
cp "$ENV_FILE" "$BACKUP"

# Reemplaza (o agrega) una variable en el .env
set_var() {
    local name="$1" value="$2"
    sed -i "/^${name}=/d" "$ENV_FILE"
    printf '%s=%s\n' "$name" "$value" >> "$ENV_FILE"
}

echo "=== Configuración fleet-watcher (Supabase + Telegram) ==="
echo

# --- SUPABASE_SERVICE_KEY (oculto) ---
echo "Pegá la SUPABASE_SERVICE_KEY (sb_secret_...) y Enter:"
echo "(no vas a ver lo que tipeás — es a propósito)"
read -rs SB_KEY
echo
if [[ "${#SB_KEY}" -lt 20 ]]; then
    echo "❌ La key parece inválida (largo: ${#SB_KEY})."
    unset SB_KEY
    exit 1
fi
set_var "SUPABASE_SERVICE_KEY" "$SB_KEY"
unset SB_KEY

# --- TELEGRAM_BOT_TOKEN (oculto) ---
echo "Pegá el TELEGRAM_BOT_TOKEN (de @BotFather) y Enter:"
echo "(tampoco se muestra)"
read -rs TG_TOKEN
echo
if [[ "$TG_TOKEN" != *:* ]]; then
    echo "❌ El token no parece válido (debería contener ':')."
    unset TG_TOKEN
    exit 1
fi
set_var "TELEGRAM_BOT_TOKEN" "$TG_TOKEN"
unset TG_TOKEN

# --- TELEGRAM_CHAT_ID (no secreto, visible) ---
read -rp "TELEGRAM_CHAT_ID (número): " TG_CHAT
if [[ ! "$TG_CHAT" =~ ^-?[0-9]+$ ]]; then
    echo "❌ El chat_id debe ser numérico."
    exit 1
fi
set_var "TELEGRAM_CHAT_ID" "$TG_CHAT"

chmod 600 "$ENV_FILE"
echo
echo "✅ .env del watcher configurado en $ENV_FILE"

# Reiniciar el servicio si ya está instalado; si no, sugerir prueba a mano
if systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE}"; then
    sudo systemctl restart "$SERVICE" && echo "✅ ${SERVICE} reiniciado"
    echo "   Ver logs:  journalctl -u ${SERVICE} -f"
else
    echo "ℹ️  El servicio ${SERVICE} todavía no está instalado."
    echo "   Probá a mano:  python3 $SCRIPT_DIR/watcher.py"
fi
