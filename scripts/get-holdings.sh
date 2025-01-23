#!/bin/bash

curl localhost:8000/holdings 2> /dev/null | \
  jq -r '.[] | [.name, .asset, .quantity] | @csv'
