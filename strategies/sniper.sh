#!/bin/bash

USER=$1
MAX_PRICE=10

if [[ -z "$USER" ]]; then
  echo "Usage: $0 <username>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

BALANCE=$(curl -s localhost:8000/users | jq -r ".[] | select(.name == \"$USER\") | .balance")

while read LINE; do
  ID=$(echo "$LINE" | cut -f1)
  QTY=$(echo "$LINE" | cut -f3)
  PRICE=$(echo "$LINE" | cut -f4)

  MAX_QTY=$(echo "$BALANCE $PRICE" | awk '{print int($1/$2)}')
  if [[ $MAX_QTY -le 0 ]]; then
    echo "[$USER] Out of money."
    break
  fi

  if [[ $MAX_QTY -lt $QTY ]]; then BUY_QTY=$MAX_QTY; else BUY_QTY=$QTY; fi
  BUY_RESULT=$(./buy.sh "$ID" "$USER" "$BUY_QTY")
  echo "$BUY_RESULT"
  if echo "$BUY_RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "[$USER] Buy failed, skipping."
    continue
  fi
  BALANCE=$(echo "$BALANCE $PRICE $BUY_QTY" | awk '{b = $1 - $2*$3; printf "%.2f", (b < 0 ? 0 : b)}')
done < <(./get-listings.sh | awk -F'\t' -v max="$MAX_PRICE" -v u="$USER" '$5 != u && $4 < max')
