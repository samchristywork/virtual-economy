#!/bin/bash

USER=$1

if [[ -n "$USER" ]]; then
  curl -s "localhost:8000/transactions?user=$USER" | jq .
else
  curl -s localhost:8000/transactions | jq .
fi
