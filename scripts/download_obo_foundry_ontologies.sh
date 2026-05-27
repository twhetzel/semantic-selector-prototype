#!/usr/bin/env bash
# Download OBO Foundry release OWL files into data/input/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/data/input"
mkdir -p "${OUT}"

declare -A URLS=(
  [mondo.owl]="http://purl.obolibrary.org/obo/mondo.owl"
  [doid.owl]="http://purl.obolibrary.org/obo/doid.owl"
  [hp.owl]="http://purl.obolibrary.org/obo/hp.owl"
  [go.owl]="http://purl.obolibrary.org/obo/go.owl"
  [obi.owl]="http://purl.obolibrary.org/obo/obi.owl"
  [efo.owl]="http://www.ebi.ac.uk/efo/efo.owl"
  [ncit.owl]="http://purl.obolibrary.org/obo/ncit.owl"
)

for file in "${!URLS[@]}"; do
  echo "Downloading ${file} ..."
  curl -fsSL -o "${OUT}/${file}" "${URLS[$file]}"
done

ls -lh "${OUT}"/*.owl
