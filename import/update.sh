#!/usr/bin/env bash
# Download the latest Indre-et-Loire OSM extract, build the GeoDesk .gol
# from it, verify it, then refresh pv_zones and pv_parkings in PostGIS.
#
# Run:  ./import/update.sh
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd -- "$(dirname -- "$SCRIPT_DIR")"

die() { echo "ERROR: $*" >&2; exit 1; }

for cmd in curl gol uv; do
	command -v "$cmd" >/dev/null 2>&1 || die "missing command: $cmd"
done

PBF_URL="https://download.openstreetmap.fr/extracts/europe/france/centre/indre_et_loire-latest.osm.pbf"
PBF="import/indre_et_loire-latest.osm.pbf"
GOL="import/indre_et_loire-latest.gol"
MIN_SIZE=1048576

echo "Downloading $PBF_URL ..."
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
curl -sfL --retry 3 -o "$tmp" "$PBF_URL" || die "download failed"
[[ -s "$tmp" ]] || die "downloaded file is empty"
size=$(stat -c%s "$tmp")
(( size >= MIN_SIZE )) || die "downloaded file too small (${size}B, expected >= ${MIN_SIZE}B)"
if [[ "$(head -c1 "$tmp")" = "<" ]]; then
	die "downloaded file looks like an HTML error page, not a PBF"
fi
mv -- "$tmp" "$PBF"

echo "Building $GOL ..."
gol build --yes --silent "$GOL" "$PBF" || die "gol build failed"
[[ -s "$GOL" ]] || die "GOL file is empty after build"
size=$(stat -c%s "$GOL")
(( size >= MIN_SIZE )) || die "GOL file too small (${size}B, expected >= ${MIN_SIZE}B)"

echo "Checking $GOL ..."
gol check --silent "$GOL" || die "gol check failed"

echo "Importing zones ..."
uv run import/import_zones.py || die "import_zones.py failed"

echo "Importing parkings ..."
uv run import/import_parkings.py || die "import_parkings.py failed"

echo "Import completed successfully."
