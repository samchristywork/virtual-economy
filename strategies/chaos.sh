#!/bin/bash

USER=$1

if [[ -z "$USER" ]]; then
  echo "Usage: $0 <username>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

ROLL=$((RANDOM % 10))

if [[ $ROLL -lt 4 ]]; then
  LINE=$(./get-listings.sh | grep -v "\"$USER\"$" | shuf -n1)
  if [[ -z "$LINE" ]]; then
    echo "[$USER] No listings to buy."
    exit 0
  fi

  ID=$(echo "$LINE" | cut -f1 -d',')
  QTY=$(echo "$LINE" | cut -f3 -d',')
  PRICE=$(echo "$LINE" | cut -f4 -d',')

  BALANCE=$(curl -s localhost:8000/users | jq -r ".[] | select(.name == \"$USER\") | .balance")
  MAX_QTY=$(echo "$BALANCE $PRICE" | awk '{print int($1/$2)}')

  if [[ $MAX_QTY -le 0 ]]; then
    echo "[$USER] Can't afford any listing."
    exit 0
  fi

  if [[ $MAX_QTY -lt $QTY ]]; then CAP=$MAX_QTY; else CAP=$QTY; fi
  BUY_QTY=$((RANDOM % CAP + 1))
  ./buy.sh $ID $USER $BUY_QTY

else
  LINE=$(./get-holdings.sh | grep "^\"$USER\"" | shuf -n1)
  if [[ -z "$LINE" ]]; then
    echo "[$USER] Nothing to sell."
    exit 0
  fi

  ASSET=$(echo "$LINE" | cut -f2 -d',' | tr -d '"')
  HOLD_QTY=$(echo "$LINE" | cut -f3 -d',')
  SELL_QTY=$((RANDOM % HOLD_QTY + 1))
  PRICE=$(awk 'BEGIN{srand(); printf "%.2f", 1 + rand() * 19}')

  ./sell.sh $USER $ASSET $SELL_QTY $PRICE
fi
