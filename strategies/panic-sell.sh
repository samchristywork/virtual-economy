#!/bin/bash

SELLER=$1

if [[ -z "$SELLER" ]]; then
  echo "Usage: $0 <seller>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

./get-holdings.sh | awk -F'\t' -v u="$SELLER" '$1 == u' | while read LINE; do
  ASSET=$(echo "$LINE" | cut -f2)
  QTY=$(echo "$LINE" | cut -f3)
  ./sell.sh "$SELLER" "$ASSET" "$QTY" 1
done
