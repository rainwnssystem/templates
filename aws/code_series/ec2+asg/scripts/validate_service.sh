#!/bin/bash
set -e

for i in $(seq 1 15); do
  if curl -fsS http://localhost:8080/healthz > /dev/null; then
    exit 0
  fi
  echo "Health check (${i} tried)"
  sleep 2
done

echo "[ValidateService] Health check failed"
systemctl status product --no-pager || true
journalctl -u product -n 30 --no-pager || true
exit 1