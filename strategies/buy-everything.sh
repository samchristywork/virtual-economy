#!/bin/bash

BUYER=$1

if [[ -z "$BUYER" ]]; then
  echo "Usage: $0 <buyer>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

./get-listings.sh | grep -v "\"$BUYER\"$" | shuf | while read LINE; do
  ID=$(echo "$LINE" | cut -f1 -d',')
  QTY=$(echo "$LINE" | cut -f3 -d',')
  ./buy.sh "$ID" "$BUYER" "$QTY"
done
