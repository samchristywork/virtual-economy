#!/bin/bash

USER=$1

if [[ -z "$USER" ]]; then
  echo "Usage: $0 <username>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

ALL_LISTINGS=$(./get-listings.sh)

./get-holdings.sh | grep "^\"$USER\"" | while read LINE; do
  ASSET=$(echo "$LINE" | cut -f2 -d',' | tr -d '"')
  HOLD_QTY=$(echo "$LINE" | cut -f3 -d',')

  MIN_PRICE=$(echo "$ALL_LISTINGS" | awk -F',' -v a="\"$ASSET\"" '$2 == a' | \
    grep -v "\"$USER\"$" | cut -f4 -d',' | sort -n | head -1)

  if [[ -z "$MIN_PRICE" ]]; then
    continue
  fi

  SELL_PRICE=$(echo "$MIN_PRICE" | awk '{printf "%.2f", $1 - 0.01}')
  VALID=$(echo "$SELL_PRICE" | awk '{print ($1 > 0)}')

  if [[ $VALID -ne 1 ]]; then
    continue
  fi

  ./sell.sh "$USER" "$ASSET" "$HOLD_QTY" "$SELL_PRICE"
done
