#!/bin/bash

USER=$1

if [[ -z "$USER" ]]; then
  echo "Usage: $0 <username>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

ALL_LISTINGS=$(./get-listings.sh)

BALANCE=$(curl -s localhost:8000/users | jq -r ".[] | select(.name == \"$USER\") | .balance")

for ASSET in FOOD OIL WATER; do
  ASSET_LISTINGS=$(echo "$ALL_LISTINGS" | awk -F',' -v a="\"$ASSET\"" '$2 == a')

  if [[ -z "$ASSET_LISTINGS" ]]; then
    continue
  fi

  AVG_PRICE=$(echo "$ASSET_LISTINGS" | awk -F',' '{sum+=$4; n++} END {printf "%.4f", sum/n}')

  # Buy listings priced below the average (cheapest first)
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
  done < <(echo "$ASSET_LISTINGS" | grep -v "\"$USER\"$" | awk -F',' -v avg="$AVG_PRICE" '$4 < avg' | sort -t',' -k4 -n)

  # List all holdings of this asset at 5% above average to capture the spread
  HOLD_QTY=$(./get-holdings.sh | grep "^\"$USER\"" | awk -F',' -v a="\"$ASSET\"" '$2 == a' | cut -f3 -d',')

  if [[ -z "$HOLD_QTY" || "$HOLD_QTY" -le 0 ]]; then
    continue
  fi

  SELL_PRICE=$(echo "$AVG_PRICE" | awk '{printf "%.2f", $1 * 1.05}')
  echo "[$USER] Listing $HOLD_QTY $ASSET at \$$SELL_PRICE (avg \$$AVG_PRICE)"
  ./sell.sh "$USER" "$ASSET" "$HOLD_QTY" "$SELL_PRICE"
done
