#!/bin/bash

curl localhost:8000/listings 2> /dev/null | \
  jq -r '.[] | [.id, .asset, .quantity, .price_per_share] | @csv'
