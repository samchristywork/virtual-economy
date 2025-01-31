#!/bin/bash

ITERATIONS=${ITERATIONS:-20}
SERVER=localhost:8000

# Agent assignments as "user:strategy" pairs.
# Override by passing arguments: ./simulate.sh Alice:chaos Bob:flipper
if [[ $# -gt 0 ]]; then
  AGENTS=("$@")
else
  AGENTS=(
    "Alice:chaos"
    "Bob:flipper"
    "Charlie:hoarder"
    "Diana:sniper"
    "Eve:undercut"
  )
fi

if ! curl -s "$SERVER/users" > /dev/null 2>&1; then
  echo "Error: server not reachable at $SERVER"
  exit 1
fi

printf "=== Resetting market ===\n"
scripts/reset.sh > /dev/null

printf "=== Creating users ===\n"
for AGENT in "${AGENTS[@]}"; do
  USER=$(echo "$AGENT" | cut -d: -f1)
  STRATEGY=$(echo "$AGENT" | cut -d: -f2)
  if [[ ! -f "strategies/$STRATEGY.sh" ]]; then
    echo "Error: unknown strategy '$STRATEGY' for user '$USER'"
    exit 1
  fi
  scripts/create-user.sh "$USER" > /dev/null
  printf "  %-12s -> %s\n" "$USER" "$STRATEGY"
done

printf "\n=== Running %d iterations with %d agents ===\n\n" "$ITERATIONS" "${#AGENTS[@]}"

for i in $(seq 1 "$ITERATIONS"); do
  echo "--- Iteration $i/$ITERATIONS ---"
  for AGENT in "${AGENTS[@]}"; do
    USER=$(echo "$AGENT" | cut -d: -f1)
    STRATEGY=$(echo "$AGENT" | cut -d: -f2)
    (./strategies/"$STRATEGY".sh "$USER") &
  done
  wait
done
