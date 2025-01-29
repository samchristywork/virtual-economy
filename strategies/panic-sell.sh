#!/bin/bash

SELLER=$1

if [[ -z "$SELLER" ]]; then
  echo "Usage: $0 <seller>"
  exit 1
fi

cd scripts || { echo "scripts/ directory not found"; exit 1; }

./get-holdings.sh | grep "^\"$SELLER\"" | while read LINE; do
  ASSET=$(echo $LINE | cut -f2 -d',' | tr -d '"')
  QTY=$(echo $LINE | cut -f3 -d',')
  ./sell.sh $SELLER $ASSET $QTY 1
done
