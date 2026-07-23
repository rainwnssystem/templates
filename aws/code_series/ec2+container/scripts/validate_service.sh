#!/bin/bash
set -e

for i in $(seq 1 15); do
  if curl -fsS http://localhost:8080/health > /dev/null; then
    exit 0
  fi
  echo "Health check (${i} tried)"
  sleep 2
done

echo "[ValidateService] Health check failed"
docker logs product || true
exit 1