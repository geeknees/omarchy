#!/usr/bin/env bash
# Omarchy CI: syntactic and pure-function checks. No privileged device access.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
DIR=$ROOT/install/hardware/apple/macbook81

for file in \
  "$ROOT/install/hardware/apple/fix-macbook81.sh" \
  "$DIR/setup" "$DIR/s3-sleep" "$DIR/initcpio-acpi" "$DIR/bt-reconnect"; do
  bash -n "$file"
done
# A non-MacBook8,1 must be refused before the privileged setup path runs.
model_file=$(mktemp)
trap 'rm -f "$model_file"' EXIT
printf 'MacBook9,1\n' > "$model_file"
if MB81_DMI_PATH="$model_file" bash "$DIR/setup" base >/dev/null 2>&1; then
  echo 'not ok - non-MacBook8,1 was not refused' >&2
  exit 1
fi
python3 "$ROOT/test/macbook81-unit.py"
echo 'ok - MacBook8,1 integration: shell syntax and Python unit tests'
