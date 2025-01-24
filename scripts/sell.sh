#!/bin/bash

SELLER=$1
ASSET=$2
QUANTITY=$3
PRICE=$4

if [[ -z "$SELLER" || -z "$ASSET" || -z "$QUANTITY" || -z "$PRICE" ]]; then
  echo "Usage: $0 <seller> <asset> <quantity> <price_per_share>"
  exit 1
fi

curl -s -X POST localhost:8000/listings \
  -H "Content-Type: application/json" \
  -d "{\"seller\":\"$SELLER\",\"asset\":\"$ASSET\",\"quantity\":$QUANTITY,\"price_per_share\":$PRICE}" \
  | jq .
