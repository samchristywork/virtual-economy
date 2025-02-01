#!/bin/bash

BUYER=$1

if [[ -z "$BUYER" ]]; then
  echo "Usage: $0 <buyer>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

./get-listings.sh | awk -F'\t' -v u="$BUYER" '$5 != u' | shuf | while read LINE; do
  ID=$(echo "$LINE" | cut -f1)
  QTY=$(echo "$LINE" | cut -f3)
  ./buy.sh "$ID" "$BUYER" "$QTY"
done
