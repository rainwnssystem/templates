#!/bin/sh
# Usage: ./send-test-data.sh <stream-name> [count]
#   {"user_id":"<uuid>","name":"<name>","timestamp":"<iso8601>"}

set -e

STREAM="${1:?stream name required}"
COUNT="${2:-10}"
REGION="${AWS_REGION:-us-east-1}"
NAMES="Frank Alice Bob Carol Dave"

i=1
while [ "$i" -le "$COUNT" ]; do
  NAME=$(echo "$NAMES" | cut -d' ' -f$(( (i - 1) % 5 + 1 )))
  UUID=$(od -An -tx1 -N16 /dev/urandom | tr -d ' \n' | sed -E 's/(.{8})(.{4})(.{4})(.{4})(.{12})/\1-\2-\3-\4-\5/')
  DATA=$(printf '{"user_id":"%s","name":"%s","timestamp":"%s"}' "$UUID" "$NAME" "$(date -u +%Y-%m-%dT%H:%M:%S.%6NZ)")

  aws kinesis put-record \
    --region "$REGION" \
    --stream-name "$STREAM" \
    --partition-key "$UUID" \
    --data "$DATA" \
    --cli-binary-format raw-in-base64-out \
    --output text --query ShardId > /dev/null

  echo "$DATA"
  i=$((i + 1))
done

echo "sent $COUNT records to $STREAM"
