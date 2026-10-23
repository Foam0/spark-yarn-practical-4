#!/usr/bin/env bash
set -euo pipefail
if (( EUID != 0 )); then echo 'Запустите через sudo.' >&2; exit 1; fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y docker.io docker-compose-v2 git curl python3
systemctl enable --now docker
