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
    "Frank:value-investor"
    "Grace:momentum"
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
  declare -A AGENT_PIDS
  for AGENT in "${AGENTS[@]}"; do
    USER=$(echo "$AGENT" | cut -d: -f1)
    STRATEGY=$(echo "$AGENT" | cut -d: -f2)
    (./strategies/"$STRATEGY".sh "$USER") &
    AGENT_PIDS[$!]="$USER:$STRATEGY"
  done
  for PID in "${!AGENT_PIDS[@]}"; do
    if ! wait "$PID"; then
      echo "Warning: ${AGENT_PIDS[$PID]} exited with error"
    fi
  done
  unset AGENT_PIDS

  for AGENT in "${AGENTS[@]}"; do
    USER=$(echo "$AGENT" | cut -d: -f1)
    for ASSET in FOOD OIL WATER; do
      CONSUME=$(( RANDOM % 3 + 1 ))
      curl -s -X POST "$SERVER/consume" \
        -H "Content-Type: application/json" \
        -d "$(jq -n --arg u "$USER" --arg a "$ASSET" --argjson q "$CONSUME" \
          '{user: $u, asset: $a, quantity: $q}')" > /dev/null
    done
  done

  curl -s -X POST "$SERVER/prices/snapshot" \
    -H "Content-Type: application/json" \
    -d "{\"iteration\": $i}" > /dev/null
done

LISTINGS=$(curl -s "$SERVER/listings")
HOLDINGS=$(curl -s "$SERVER/holdings")
USERS=$(curl -s "$SERVER/users")
STRATEGIES=$(for AGENT in "${AGENTS[@]}"; do
  printf '{"name":"%s","strategy":"%s"}' "$(echo "$AGENT" | cut -d: -f1)" "$(echo "$AGENT" | cut -d: -f2)"
done | jq -s '.')

printf "\n=== Final Leaderboard ===\n\n"
printf "%-15s %-15s %10s %10s %10s %10s %12s\n" "USER" "STRATEGY" "BALANCE" "FOOD" "OIL" "WATER" "NET WORTH"
printf "%-15s %-15s %10s %10s %10s %10s %12s\n" "---------------" "---------------" "----------" "----------" "----------" "----------" "------------"

jq -rn \
  --argjson users      "$USERS" \
  --argjson holdings   "$HOLDINGS" \
  --argjson listings   "$LISTINGS" \
  --argjson strategies "$STRATEGIES" \
  '
  ($listings | group_by(.asset) | map({key: .[0].asset, value: (map(.price_per_share) | min)}) | from_entries) as $prices |
  ($strategies | map({key: .name, value: .strategy}) | from_entries) as $strat |
  $users | map(
    . as $user |
    ($holdings | map(select(.name == $user.name)) | group_by(.asset) | map({key: .[0].asset, value: .[0].quantity}) | from_entries) as $h |
    {
      name: $user.name,
      strategy: ($strat[$user.name] // "unknown"),
      balance: $user.balance,
      food:  ($h.FOOD  // 0),
      oil:   ($h.OIL   // 0),
      water: ($h.WATER // 0),
      net_worth: ($user.balance
        + ($h.FOOD  // 0) * ($prices.FOOD  // 0)
        + ($h.OIL   // 0) * ($prices.OIL   // 0)
        + ($h.WATER // 0) * ($prices.WATER // 0))
    }
  ) | sort_by(-.net_worth)[]
  | [.name, .strategy, .balance, .food, .oil, .water, .net_worth] | @tsv
  ' | awk -F'\t' '{printf "%-15s %-15s %10.2f %10d %10d %10d %12.2f\n", $1, $2, $3, $4, $5, $6, $7}'

PRICE_HISTORY=$(curl -s "$SERVER/prices/history")

printf "\n=== Price History ===\n\n"
printf "%-6s %10s %10s %10s\n" "Iter" "FOOD" "OIL" "WATER"
printf "%-6s %10s %10s %10s\n" "------" "----------" "----------" "----------"

echo "$PRICE_HISTORY" | jq -r '
  group_by(.iteration)[] |
  (.[0].iteration) as $i |
  (map(select(.asset == "FOOD"))[0].avg_price  // 0) as $f |
  (map(select(.asset == "OIL"))[0].avg_price   // 0) as $o |
  (map(select(.asset == "WATER"))[0].avg_price // 0) as $w |
  "\($i)\t\($f)\t\($o)\t\($w)"
' | awk -F'\t' '{printf "%-6d %10.2f %10.2f %10.2f\n", $1, $2, $3, $4}'

printf "\nSparklines (▁ = min, █ = max):\n\n"
for ASSET in FOOD OIL WATER; do
  printf "  %-6s " "$ASSET"
  echo "$PRICE_HISTORY" | jq -r --arg a "$ASSET" \
    '[.[] | select(.asset == $a) | .avg_price] | @tsv' | \
  awk '{
    if ($0 == "") { print "(no data)"; exit }
    n = split($0, v, "\t")
    min = max = v[1]+0
    for (i = 2; i <= n; i++) {
      if (v[i]+0 < min) min = v[i]+0
      if (v[i]+0 > max) max = v[i]+0
    }
    split("▁ ▂ ▃ ▄ ▅ ▆ ▇ █", b, " ")
    for (i = 1; i <= n; i++) {
      idx = (max == min) ? 4 : int((v[i]+0 - min) / (max - min) * 7) + 1
      printf "%s", b[idx]
    }
    printf "  min: %.2f  max: %.2f\n", min, max
  }'
done
