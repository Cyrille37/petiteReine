#!/usr/bin/env bash
# Download the latest Indre-et-Loire OSM extract, build the GeoDesk .gol
# from it, verify it, then refresh pv_zones and pv_parkings in PostGIS.
#
# Run:  ./import/update.sh [--silent]
set -euo pipefail

SILENT=0
[[ "${1:-}" = "--silent" ]] && SILENT=1

log() { (( SILENT )) || echo "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd -- "$(dirname -- "$SCRIPT_DIR")"

for cmd in curl gol uv; do
	command -v "$cmd" >/dev/null 2>&1 || die "missing command: $cmd"
done

PBF_URL="https://download.openstreetmap.fr/extracts/europe/france/centre/indre_et_loire-latest.osm.pbf"
PBF="import/indre_et_loire-latest.osm.pbf"
GOL="import/indre_et_loire-latest.gol"
MIN_SIZE=1048576
SILENT_FLAG=""
(( SILENT )) && SILENT_FLAG="--silent"

log "Downloading $PBF_URL ..."
tmp=$(mktemp)
# On exit (success, die() error, or Ctrl+C / kill) remove the temp file plus
# the downloaded PBF and the built GOL, so no stale or partial artifacts are
# left behind. rm -f is a no-op for a file that was never created.
trap 'rm -f -- "$tmp" "$PBF" "$GOL"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
curl -sfL --retry 3 -o "$tmp" "$PBF_URL" || die "download failed"
[[ -s "$tmp" ]] || die "downloaded file is empty"
size=$(stat -c%s "$tmp")
(( size >= MIN_SIZE )) || die "downloaded file too small (${size}B, expected >= ${MIN_SIZE}B)"
if [[ "$(head -c1 "$tmp" | od -An -tx1 | tr -d ' \n')" = "3c" ]]; then
	die "downloaded file looks like an HTML error page, not a PBF"
fi
mv -- "$tmp" "$PBF"

log "Building $GOL ..."
gol build --yes --silent "$GOL" "$PBF" || die "gol build failed"
[[ -s "$GOL" ]] || die "GOL file is empty after build"
size=$(stat -c%s "$GOL")
(( size >= MIN_SIZE )) || die "GOL file too small (${size}B, expected >= ${MIN_SIZE}B)"

log "Checking $GOL ..."
gol check --silent "$GOL" || die "gol check failed"

log "Importing zones ..."
uv run import/import_zones.py $SILENT_FLAG || die "import_zones.py failed"

log "Importing parkings ..."
uv run import/import_parkings.py $SILENT_FLAG || die "import_parkings.py failed"

log "Import completed successfully."
