#!/bin/bash

LISTING_ID=$1
BUYER=$2
QUANTITY=$3

if [[ -z "$LISTING_ID" || -z "$BUYER" || -z "$QUANTITY" ]]; then
  echo "Usage: $0 <listing_id> <buyer> <quantity>"
  exit 1
fi

curl -s -X POST localhost:8000/buy \
  -H "Content-Type: application/json" \
  -d "{\"listing_id\":$LISTING_ID,\"buyer\":\"$BUYER\",\"quantity\":$QUANTITY}" \
  | jq .
