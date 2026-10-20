#!/usr/bin/env bash
# Sestaví obrazy: cc-bench-base → cc-bench-task-NN (snapshot + pnpm install)
# → cc-bench-NN-<config> (nástroj konfigurace). Kontejnery agentů síť nemají,
# vše se instaluje tady při buildu.
#
# Použití: scripts/build-images.sh [config…]   (výchozí: všechny v configs/)
# Proměnná TASKS: mezerou oddělené úlohy, např. TASKS="05-moje-uloha" (výchozí: všechny v tasks/).
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
build=$root/build
configs=("$@")
if [ ${#configs[@]} -eq 0 ]; then
  for d in "$root"/configs/*/; do configs+=("$(basename "$d")"); done
fi

docker build -q -t cc-bench-base "$root/docker/base" >/dev/null
docker build -q -t cc-bench-gateway "$root/docker/gateway" >/dev/null

task_dirs=()
if [ -n "${TASKS:-}" ]; then
  for t in $TASKS; do task_dirs+=("$root/tasks/$t/"); done
else
  task_dirs=("$root"/tasks/*/)
fi

for task_dir in "${task_dirs[@]}"; do
  task=$(basename "$task_dir")
  nn=${task%%-*}
  snap=$build/snapshots/$task
  if [ ! -d "$snap/.git" ]; then
    rm -rf "$snap"
    "$root/scripts/make-snapshot.sh" "$task_dir" "$snap"
  fi
  dockerfile=$root/docker/task/Dockerfile
  [ -f "$task_dir/task.Dockerfile" ] && dockerfile=$task_dir/task.Dockerfile
  docker build -q -t "cc-bench-task-$nn" -f "$dockerfile" "$snap" >/dev/null
  echo "cc-bench-task-$nn"
  for cfg in "${configs[@]}"; do
    docker build -q -t "cc-bench-$nn-$cfg" --build-arg "TASK_IMAGE=cc-bench-task-$nn" \
      -f "$root/configs/$cfg/Dockerfile" "$root/configs/$cfg" >/dev/null
    echo "cc-bench-$nn-$cfg"
  done
done
