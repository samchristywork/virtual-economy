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
  -d "$(jq -n --argjson id "$LISTING_ID" --arg buyer "$BUYER" --argjson qty "$QUANTITY" '{listing_id: $id, buyer: $buyer, quantity: $qty}')" \
  | jq .
