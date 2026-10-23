#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if (( EUID != 0 )); then echo 'Запустите через sudo на edge.' >&2; exit 1; fi
if (( $# != 3 )); then echo "Использование: $0 INTERNAL_IP PUBLIC_IP endpoints.json" >&2; exit 1; fi
./scripts/publish-web.sh "$@"
if ! command -v cloudflared >/dev/null; then
  case "$(uname -m)" in x86_64) arch=amd64;; aarch64) arch=arm64;; *) exit 1;; esac
  temp="$(mktemp)"
  curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$arch" -o "$temp"
  install -m 755 "$temp" /usr/local/bin/cloudflared
  rm "$temp"
fi
root="$(pwd)"
endpoints="$(realpath "$3")"
# Пути и параметры должны быть простыми: их передаём в systemd без shell.
for value in "$root" "$endpoints" "$1" "$2"; do
  if [[ ! "$value" =~ ^[a-zA-Z0-9_./:-]+$ ]]; then echo 'Недопустимый аргумент' >&2; exit 1; fi
done
cat > /etc/systemd/system/hadoop-web-tunnels.service <<UNIT
[Unit]
Description=Hadoop laboratory HTTPS interfaces
After=network-online.target nginx.service
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$root
ExecStart=/usr/bin/python3 $root/scripts/tunnel-supervisor.py --internal-host $1 --public-host $2 --endpoints $endpoints
Restart=always
RestartSec=15
KillMode=control-group
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable hadoop-web-tunnels
systemctl restart hadoop-web-tunnels
echo 'Запуск туннелей идёт в фоне. Адреса: /var/lib/hadoop-web/public-urls.json'
echo 'Статус: journalctl -u hadoop-web-tunnels -f'
