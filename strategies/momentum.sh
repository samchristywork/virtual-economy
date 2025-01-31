#!/bin/bash

USER=$1

if [[ -z "$USER" ]]; then
  echo "Usage: $0 <username>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

ALL_LISTINGS=$(./get-listings.sh | grep -v "\"$USER\"$")

if [[ -z "$ALL_LISTINGS" ]]; then
  echo "[$USER] No listings available."
  exit 0
fi

# Pick the asset with the most active listings by total volume
TOP_ASSET=$(echo "$ALL_LISTINGS" | awk -F',' '{gsub(/"/, "", $2); asset[$2]+=$3} END {for (a in asset) print asset[a], a}' | sort -rn | head -1 | awk '{print $2}')

if [[ -z "$TOP_ASSET" ]]; then
  echo "[$USER] Could not determine top asset."
  exit 0
fi

echo "[$USER] Targeting most active asset: $TOP_ASSET"

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
done < <(echo "$ALL_LISTINGS" | awk -F',' -v a="\"$TOP_ASSET\"" '$2 == a' | sort -t',' -k4 -n)
