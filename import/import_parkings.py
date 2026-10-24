#!/usr/bin/env python3
"""Import bicycle parkings into PostGIS pv_parkings.

Reads the ref:INSEE zone list from conf.ini, fetches the zone boundaries
and the parkings (amenity=bicycle_parking) locally from a GeoDesk .gol
file (no Overpass call), then:

  1. replaces the contents of pv_parkings, assigning each parking its zone
  2. regenerates the isochrone areas in pv_parking_dist_zones
  3. exports the parkings to export/parkings.json
  4. writes a row in pv_import_trace

Prerequisite: pv_zones must be populated (run import/import_zones.py first).

Run:
    uv run import/import_parkings.py
    uv run import/import_parkings.py --dry-run   # query only, no DB
"""

import argparse
import configparser
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import geodesk
import psycopg
from geodesk import Features

REPO_ROOT = Path(__file__).resolve().parent.parent

PARKING_QUERY = "na[amenity=bicycle_parking]"
# OSM type -> obj_id prefix in pv_parkings
OSM_PREFIX = {"node": "n", "way": "w", "relation": "r"}
# Tags copied from OSM into pv_parkings (key -> column)
TAGS = {
    "covered": "covered",
    "bicycle_parking": "parking_type",
    "access": "access",
    "operator": "operator",
}


def load_config():
    cfg_path = REPO_ROOT / "conf.ini"
    if not cfg_path.is_file():
        sys.exit(
            f"Config file not found: {cfg_path}\n"
            "Copy conf.ini.example to conf.ini and fill it in."
        )
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path, encoding="utf-8")

    db = {
        "host": cfg.get("database", "host", fallback="localhost"),
        "port": cfg.getint("database", "port", fallback=5432),
        "dbname": cfg.get("database", "dbname"),
        "user": cfg.get("database", "user"),
        "password": cfg.get("database", "password", fallback=""),
    }

    gol_path = Path(cfg.get("data", "gol"))
    if not gol_path.is_absolute():
        gol_path = REPO_ROOT / gol_path

    raw_insee = cfg.get("zones", "insee", raw=True)
    insee = [c for c in raw_insee.replace(",", " ").split() if c]

    dist_proj = cfg.getint(
        "parkings", "dist_proj", fallback=27572
    )
    raw_levels = cfg.get(
        "parkings", "distance_levels", raw=True, fallback="100,200,400"
    )
    levels = [int(x) for x in raw_levels.replace(",", " ").split() if x]
    levels.sort()

    return db, gol_path, insee, dist_proj, levels


def build_query(insee):
    return f"a[admin_level=8][boundary=administrative][ref:INSEE={','.join(insee)}]"


def parse_capacity(value):
    """Same behaviour as PHP intval(): leading digits, 0 otherwise."""
    if value is None:
        return 0
    m = re.match(r"\s*(\d+)", str(value))
    return int(m.group(1)) if m else 0


def build_parking(feature, timestamp):
    wgs = geodesk.from_mercator(feature.shape)
    if wgs.geom_type != "Point":
        wgs = wgs.centroid

    attrs = {column: "" for column in TAGS.values()}
    for tag, column in TAGS.items():
        value = feature[tag]
        if value is not None:
            attrs[column] = value

    return {
        "obj_id": OSM_PREFIX[feature.osm_type] + str(feature.id),
        "capacity": parse_capacity(feature["capacity"]),
        **attrs,
        "timestamp": timestamp,
        "wkt": wgs.wkt,
    }


def collect_parkings(france, zones, timestamp):
    """All parkings strictly within any of the given zone features."""
    base = france(PARKING_QUERY)
    found = {}
    for zone in zones:
        for p in base.within(zone):
            found.setdefault(p.id, p)
    return [build_parking(p, timestamp) for p in found.values()]


def import_parkings(conn, parkings):
    """Replace pv_parkings contents and assign zone ids."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pv_parkings")
            cur.executemany(
                "INSERT INTO pv_parkings "
                "(obj_id, capacity, covered, parking_type, access, the_geom, timestamp, operator) "
                "VALUES (%s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s)",
                [
                    (
                        p["obj_id"], p["capacity"], p["covered"],
                        p["parking_type"], p["access"], p["wkt"],
                        p["timestamp"], p["operator"],
                    )
                    for p in parkings
                ],
            )
            cur.execute(
                "UPDATE pv_parkings SET zone_id = rel.zone_id "
                "FROM (SELECT Z.zone_id, p.obj_id "
                "      FROM pv_zones Z, pv_parkings p "
                "      WHERE Z.zone_id != 'default' "
                "        AND ST_Contains(Z.geom, p.the_geom)) rel "
                "WHERE pv_parkings.obj_id = rel.obj_id"
            )
            cur.execute(
                "DELETE FROM pv_parkings WHERE parking_type = 'informal'"
            )


def build_isochrones(conn, dist_proj, levels):
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE pv_parking_dist_zones")
            for dist in levels:
                cur.execute(
                    "INSERT INTO pv_parking_dist_zones "
                    "SELECT zone_id, %s, the_geom FROM ("
                    "  SELECT zone_id, ST_Multi(ST_Intersection("
                    "    Z.geom, "
                    "    (SELECT ST_Transform(ST_Union(ST_Buffer("
                    "      ST_Transform(the_geom, %s), %s)), 4326) "
                    "     FROM pv_parkings WHERE access <> 'private'))"
                    "  ) AS the_geom "
                    "  FROM pv_zones Z"
                    ") sr WHERE ST_GeometryType(the_geom) = 'ST_MultiPolygon'",
                    (dist, dist_proj, dist),
                )


def export_geojson(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT obj_id, capacity, covered, parking_type, access, operator, "
        "       zone_id, ST_AsGeoJSON(the_geom) "
        "FROM pv_parkings ORDER BY obj_id"
    )
    collection = {"type": "FeatureCollection", "features": []}
    for row in cur:
        collection["features"].append({
            "type": "Feature",
            "geometry": json.loads(row[7]),
            "properties": {
                "osm_id": row[0],
                "capacity": row[1],
                "covered": row[2],
                "bicycle_parking": row[3],
                "access": row[4],
                "operator": row[5],
                "zone_id": row[6],
            },
        })
    out = REPO_ROOT / "export" / "parkings.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(collection), encoding="utf-8")
    return len(collection["features"])


def write_trace(conn, status, start, zone_count):
    with conn.cursor() as cur:
        stats = {}
        if status:
            cur.execute(
                "SELECT count(*), coalesce(sum(capacity), 0) FROM pv_parkings"
            )
            count, total = cur.fetchone()
            cur.execute(
                "SELECT count(*) FROM pv_parkings WHERE capacity = 0"
            )
            no_capacity = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM pv_parkings WHERE parking_type = ''"
            )
            no_type = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM pv_parkings "
                "WHERE parking_type = '' OR capacity = 0"
            )
            problem = cur.fetchone()[0]
            stats = dict(
                number_parking=count,
                total_capacity=total,
                number_nocapacity=no_capacity,
                number_notype=no_type,
                number_problem=problem,
            )
        else:
            stats = dict(
                number_parking=0,
                total_capacity=0,
                number_nocapacity=0,
                number_notype=0,
                number_problem=0,
            )
        cur.execute(
            "INSERT INTO pv_import_trace "
            "(trace_id, status, startdt, duration, area, number_parking, "
            " total_capacity, number_nocapacity, number_notype, number_problem) "
            "SELECT coalesce(max(trace_id), 0) + 1, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s FROM pv_import_trace",
            (
                status,
                datetime.fromtimestamp(start).isoformat(),
                int(time.time() - start),
                zone_count,
                stats["number_parking"],
                stats["total_capacity"],
                stats["number_nocapacity"],
                stats["number_notype"],
                stats["number_problem"],
            ),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="query parkings from the .gol file, but do not touch the database",
    )
    args = parser.parse_args()

    start = time.time()
    db, gol_path, insee, dist_proj, levels = load_config()
    if not insee:
        sys.exit("No ref:INSEE codes configured in conf.ini [zones] insee")
    if not gol_path.is_file():
        sys.exit(f"GeoDesk file not found: {gol_path}")

    print(f"Loading {gol_path} ...")
    france = Features(str(gol_path))

    zone_query = build_query(insee)
    print(f"Zones: {zone_query}")
    zones = list(france(zone_query))
    if not zones:
        sys.exit("No zones found for the configured ref:INSEE codes.")
    for zone in zones:
        print(f"  {zone['ref:INSEE']}  {zone['name']}  (R{zone.id})")

    print(f"Parkings: {PARKING_QUERY} within {len(zones)} zone(s)")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parkings = collect_parkings(france, zones, timestamp)
    print(f"Found {len(parkings)} parking(s).")

    if args.dry_run:
        for p in parkings[:20]:
            print(f"  {p['obj_id']}  cap={p['capacity']}  "
                  f"type={p['parking_type'] or '-'}  {p['wkt']}")
        if len(parkings) > 20:
            print(f"  ... and {len(parkings) - 20} more")
        print("Dry run: no database changes made.")
        return

    status = False
    with psycopg.connect(**db) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT zone_id FROM pv_zones WHERE zone_id != 'default'"
            )
            db_zones = {row[0] for row in cur}
        missing = [c for c in insee if c not in db_zones]
        if missing:
            sys.exit(
                f"pv_zones is missing: {', '.join(missing)}.\n"
                "Run import/import_zones.py first."
            )

        if parkings:
            import_parkings(conn, parkings)
            build_isochrones(conn, dist_proj, levels)
            exported = export_geojson(conn)
            print(f"Inserted {len(parkings)} parking(s), "
                  f"regenerated isochrones ({', '.join(map(str, levels))} m), "
                  f"exported {exported} feature(s) to export/parkings.json.")
            status = True
        else:
            print("No parkings found: database left unchanged.")

        write_trace(conn, status, start, len(zones))

    print("Done.")


if __name__ == "__main__":
    main()
