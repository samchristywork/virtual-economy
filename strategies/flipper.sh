#!/bin/bash

USER=$1

if [[ -z "$USER" ]]; then
  echo "Usage: $0 <username>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

LINE=$(./get-listings.sh | grep -v "\"$USER\"$" | sort -t',' -k4 -n | head -1)
if [[ -z "$LINE" ]]; then
  echo "[$USER] No listings available."
  exit 0
fi

ID=$(echo "$LINE" | cut -f1 -d',')
ASSET=$(echo "$LINE" | cut -f2 -d',' | tr -d '"')
QTY=$(echo "$LINE" | cut -f3 -d',')
PRICE=$(echo "$LINE" | cut -f4 -d',')

BALANCE=$(curl -s localhost:8000/users | jq -r ".[] | select(.name == \"$USER\") | .balance")
MAX_QTY=$(echo "$BALANCE $PRICE" | awk '{print int($1/$2)}')

if [[ $MAX_QTY -le 0 ]]; then
  echo "[$USER] Can't afford cheapest listing (\$$PRICE/share)."
  exit 0
fi

if [[ $MAX_QTY -lt $QTY ]]; then BUY_QTY=$MAX_QTY; else BUY_QTY=$QTY; fi

./buy.sh $ID $USER $BUY_QTY

SELL_PRICE=$(echo "$PRICE" | awk '{printf "%.2f", $1 * 1.25}')
./sell.sh "$USER" "$ASSET" "$BUY_QTY" "$SELL_PRICE"
