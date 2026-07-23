#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <image_path> [endpoint_name]" >&2
  exit 1
fi

IMAGE_PATH="$1"
ENDPOINT_NAME="${2:-${SAGEMAKER_ENDPOINT_NAME:?endpoint name required (arg2 or SAGEMAKER_ENDPOINT_NAME env)}}"
REGION="${AWS_REGION:-ap-northeast-2}"

if [ ! -f "$IMAGE_PATH" ]; then
  echo "File not found: $IMAGE_PATH" >&2
  exit 1
fi

PAYLOAD_FILE=$(mktemp)
RESPONSE_FILE=$(mktemp)
trap 'rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE"' EXIT


# ──────────────────────────────────────────────────────────────
# Option 1) base64 + JSON
#   Content-Type: application/json
#   Body: {"image": "<base64>"}
# ──────────────────────────────────────────────────────────────

B64=$(base64 -w 0 "$IMAGE_PATH")
printf '{"image":"%s"}' "$B64" > "$PAYLOAD_FILE"
CONTENT_TYPE="application/json"


# ──────────────────────────────────────────────────────────────
# Option 2) base64 string only (no JSON wrap)
#   Content-Type: text/plain
#   Body: "<base64>"
# ──────────────────────────────────────────────────────────────

# base64 -w 0 "$IMAGE_PATH" > "$PAYLOAD_FILE"
# CONTENT_TYPE="text/plain"


# ──────────────────────────────────────────────────────────────
# Option 3) raw bytes (no base64)
#   Content-Type: image/png  (or image/jpeg)
#   Body: raw image bytes  (33% smaller than base64)
# ──────────────────────────────────────────────────────────────

# cp "$IMAGE_PATH" "$PAYLOAD_FILE"
# CONTENT_TYPE="image/png"


# fileb:// + raw image bytes | text | json
aws sagemaker-runtime invoke-endpoint \
  --region "$REGION" \
  --endpoint-name "$ENDPOINT_NAME" \
  --content-type "$CONTENT_TYPE" \
  --body "fileb://$PAYLOAD_FILE" \
  "$RESPONSE_FILE" >/dev/null

cat "$RESPONSE_FILE"
echo
