#!/bin/bash

USER=$1

if [[ -z "$USER" ]]; then
  echo "Usage: $0 <username>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

LINE=$(./get-listings.sh | awk -F'\t' -v u="$USER" '$5 != u' | sort -t$'\t' -k4 -n | head -1)
if [[ -z "$LINE" ]]; then
  echo "[$USER] No listings available."
  exit 0
fi

ID=$(echo "$LINE" | cut -f1)
ASSET=$(echo "$LINE" | cut -f2)
QTY=$(echo "$LINE" | cut -f3)
PRICE=$(echo "$LINE" | cut -f4)

BALANCE=$(curl -s localhost:8000/users | jq -r ".[] | select(.name == \"$USER\") | .balance")
MAX_QTY=$(echo "$BALANCE $PRICE" | awk '{print int($1/$2)}')

if [[ $MAX_QTY -le 0 ]]; then
  echo "[$USER] Can't afford cheapest listing (\$$PRICE/share)."
  exit 0
fi

if [[ $MAX_QTY -lt $QTY ]]; then BUY_QTY=$MAX_QTY; else BUY_QTY=$QTY; fi

BUY_RESULT=$(./buy.sh "$ID" "$USER" "$BUY_QTY")
echo "$BUY_RESULT"
if echo "$BUY_RESULT" | jq -e '.error' > /dev/null 2>&1; then
  echo "[$USER] Buy failed, skipping sell."
  exit 0
fi

SELL_PRICE=$(echo "$PRICE" | awk '{printf "%.2f", $1 * 1.25}')
./sell.sh "$USER" "$ASSET" "$BUY_QTY" "$SELL_PRICE"
