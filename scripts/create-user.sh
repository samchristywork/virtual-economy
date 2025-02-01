#!/bin/bash

NAME=$1
BALANCE=${2:-1000}

if [[ -z "$NAME" ]]; then
  echo "Usage: $0 <name> [balance]"
  exit 1
fi

curl -s -X POST localhost:8000/users \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg name "$NAME" --argjson balance "$BALANCE" '{name: $name, balance: $balance}')" \
  | jq .
