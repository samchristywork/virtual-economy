#!/bin/bash

curl -s -X POST localhost:8000/reset \
  -H "Content-Type: application/json" \
  | jq .
