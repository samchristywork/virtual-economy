#!/bin/bash

USER=$1
TARGET="FOOD"

if [[ -z "$USER" ]]; then
  echo "Usage: $0 <username>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

BALANCE=$(curl -s localhost:8000/users | jq -r ".[] | select(.name == \"$USER\") | .balance")

while read LINE; do
  ID=$(echo "$LINE" | cut -f1 -d',')
  QTY=$(echo "$LINE" | cut -f3 -d',')
  PRICE=$(echo "$LINE" | cut -f4 -d',')

  MAX_QTY=$(echo "$BALANCE $PRICE" | awk '{print int($1/$2)}')
  if [[ $MAX_QTY -le 0 ]]; then
    echo "[$USER] Out of money."
    break
  fi

  if [[ $MAX_QTY -lt $QTY ]]; then BUY_QTY=$MAX_QTY; else BUY_QTY=$QTY; fi
  ./buy.sh "$ID" "$USER" "$BUY_QTY"
  BALANCE=$(echo "$BALANCE $PRICE $BUY_QTY" | awk '{printf "%.2f", $1 - $2*$3}')
done < <(./get-listings.sh | awk -F',' -v t="\"$TARGET\"" '$2 == t' | grep -v "\"$USER\"$")
