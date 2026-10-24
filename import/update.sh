#!/usr/bin/env bash
# Download the latest Indre-et-Loire OSM extract, build the GeoDesk .gol
# from it, verify it, then refresh pv_zones and pv_parkings in PostGIS.
#
# Run:  ./import/update.sh
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd -- "$(dirname -- "$SCRIPT_DIR")"

for cmd in curl gol uv; do
	command -v "$cmd" >/dev/null 2>&1 || { echo "missing command: $cmd" >&2; exit 1; }
done

PBF_URL="https://download.openstreetmap.fr/extracts/europe/france/centre/indre_et_loire-latest.osm.pbf"
PBF="import/indre_et_loire-latest.osm.pbf"
GOL="import/indre_et_loire-latest.gol"

echo "Downloading $PBF_URL ..."
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
curl -fL --retry 3 -o "$tmp" "$PBF_URL"
mv -- "$tmp" "$PBF"

echo "Building $GOL ..."
gol build --yes "$GOL" "$PBF"

echo "Checking $GOL ..."
gol check "$GOL"

echo "Importing zones ..."
uv run import/import_zones.py

echo "Importing parkings ..."
uv run import/import_parkings.py
