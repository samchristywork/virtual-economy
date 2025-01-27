#!/bin/bash

USER=$1

if [[ -z "$USER" ]]; then
  echo "Usage: $0 <username>"
  exit 1
fi

cd scripts

ALL_LISTINGS=$(./get-listings.sh)

./get-holdings.sh | grep "^\"$USER\"" | cut -f2 -d',' | tr -d '"' | while read ASSET; do
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

  ./sell.sh $USER $ASSET 1 $SELL_PRICE
done
