#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if (( EUID != 0 )); then echo 'Запустите через sudo на edge-узле.' >&2; exit 1; fi
if (( $# != 3 )); then echo "Использование: $0 INTERNAL_IP PUBLIC_IP endpoints.json" >&2; exit 1; fi
internal="$1"; public="$2"; endpoints="$3"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y nginx python3 curl
generated="$(mktemp -d)"
trap 'rm -rf "$generated"' EXIT
python3 scripts/render-nginx.py --internal-host "$internal" --public-host "$public" --endpoints "$endpoints" --output-dir "$generated"
install -d /var/www/hadoop-lab
install -m 644 "$generated/index.html" /var/www/hadoop-lab/index.html
if test -f /etc/nginx/sites-available/hadoop-lab; then
  cp -p /etc/nginx/sites-available/hadoop-lab "/etc/nginx/sites-available/hadoop-lab.backup.$(date +%Y%m%d%H%M%S)"
fi
install -m 644 "$generated/hadoop-lab.conf" /etc/nginx/sites-available/hadoop-lab
ln -sfn /etc/nginx/sites-available/hadoop-lab /etc/nginx/sites-enabled/hadoop-lab
# Стандартная страница nginx конфликтует с общей страницей стенда на порту 80.
if test -L /etc/nginx/sites-enabled/default; then unlink /etc/nginx/sites-enabled/default; fi
nginx -t
systemctl enable --now nginx
systemctl reload nginx
echo "Интерфейсы опубликованы: http://$public/"
