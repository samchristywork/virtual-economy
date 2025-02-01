#!/bin/bash

USER=$1

if [[ -z "$USER" ]]; then
  echo "Usage: $0 <username>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

ALL_LISTINGS=$(./get-listings.sh)

./get-holdings.sh | awk -F'\t' -v u="$USER" '$1 == u' | while read LINE; do
  ASSET=$(echo "$LINE" | cut -f2)
  HOLD_QTY=$(echo "$LINE" | cut -f3)

  MIN_PRICE=$(echo "$ALL_LISTINGS" | awk -F'\t' -v a="$ASSET" -v u="$USER" '$2 == a && $5 != u {print $4}' | sort -n | head -1)

  if [[ -z "$MIN_PRICE" ]]; then
    continue
  fi

  VALID=$(echo "$MIN_PRICE" | awk '{print ($1 > 0.01)}')
  if [[ $VALID -ne 1 ]]; then
    continue
  fi

  SELL_PRICE=$(echo "$MIN_PRICE" | awk '{printf "%.2f", $1 - 0.01}')
  ./sell.sh "$USER" "$ASSET" "$HOLD_QTY" "$SELL_PRICE"
done
