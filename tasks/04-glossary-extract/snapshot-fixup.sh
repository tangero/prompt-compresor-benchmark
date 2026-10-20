#!/usr/bin/env bash
# Úloha 04: do snapshotu přidá podkorpus HTML specifikací (Rel-19/20, série 22 a 32,
# 303 specifikací, ~39 MB; veřejné dokumenty 3GPP) na výchozí místo korpusu
# a výstup posledního (chybného) běhu extrakce. Obojí leží v gitignorovaném
# apps/downloader/data/, do commitu snapshotu se nedostane.
#   SOURCE_REPO      klon 3gpp-explorer s lokálním korpusem apps/downloader/data/specs
#   INCIDENT_DIR     výstup scripts/make-incident-04.sh (build/task04-incident)
set -euo pipefail
src=${SOURCE_REPO:-$HOME/GitHub/3gpp-explorer2}/apps/downloader/data/specs
for rel in Rel-19 Rel-20; do
  for series in 22 32; do
    mkdir -p "apps/downloader/data/specs/$rel"
    cp -R "$src/$rel/$series" "apps/downloader/data/specs/$rel/"
  done
done
if [ -n "${INCIDENT_DIR:-}" ] && [ -d "$INCIDENT_DIR" ]; then
  mkdir -p apps/downloader/data/glossary
  cp -R "$INCIDENT_DIR"/. apps/downloader/data/glossary/
fi
