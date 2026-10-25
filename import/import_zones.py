#!/usr/bin/env python3
"""Import administrative zones (communes) into PostGIS pv_zones.

Reads a list of ref:INSEE codes from conf.ini, fetches their boundaries
locally from a GeoDesk .gol file, and inserts each one as a MultiPolygon
into the pv_zones table. Replaces the single-zone Overpass import
(import/import_zones.php).

Run:
    uv run import/import_zones.py
    uv run import/import_zones.py --dry-run   # query + build geoms, no DB
"""

import argparse
import configparser
import sys
from pathlib import Path

import psycopg
import geodesk
from geodesk import Features
from shapely.ops import unary_union

REPO_ROOT = Path(__file__).resolve().parent.parent


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
        "client_encoding": "UTF8",
    }

    gol_path = Path(cfg.get("data", "gol"))
    if not gol_path.is_absolute():
        gol_path = REPO_ROOT / gol_path

    raw_insee = cfg.get("zones", "insee", raw=True)
    insee = [c for c in raw_insee.replace(",", " ").split() if c]

    return db, gol_path, insee


ZONE_QUERY = "a[admin_level=8][boundary=administrative][ref:INSEE={code}]"


def collect_zones(france, insee):
    """Return ({code: (label, osm_id, wgs84_geom)}, [missing codes]).

    One query per INSEE code: the multi-value form [ref:INSEE=a,b] is
    unreliable across geodesk versions (2.2.5 matches nothing), so each
    code is queried individually to stay version-independent.
    """
    zones = {}
    for code in insee:
        feats = france(ZONE_QUERY.format(code=code))
        if feats.count == 0:
            continue
        first = next(iter(feats))
        geom = unary_union([geodesk.from_mercator(f.shape) for f in feats])
        zones[code] = (first["name"] or code, int(first.id), geom)

    missing = [c for c in insee if c not in zones]
    return zones, missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="query and build geometries, but do not touch the database",
    )
    args = parser.parse_args()

    db, gol_path, insee = load_config()
    if not insee:
        sys.exit("No ref:INSEE codes configured in conf.ini [zones] insee")
    if not gol_path.is_file():
        sys.exit(f"GeoDesk file not found: {gol_path}")

    print(f"Loading {gol_path} ...")
    france = Features(str(gol_path))

    print(f"Querying {len(insee)} INSEE code(s): {', '.join(insee)}")
    zones, missing = collect_zones(france, insee)
    print(f"Found {len(zones)} zone(s).")
    for code in missing:
        print(f"  WARNING: no area for INSEE {code}")

    for code, (label, osm_id, geom) in sorted(zones.items()):
        parts = len(geom.geoms) if geom.geom_type == "MultiPolygon" else 1
        print(f"  {code}  {label}  (R{osm_id})  {geom.geom_type}  {parts} part(s)")

    if args.dry_run:
        print("Dry run: no database changes made.")
        return

    with psycopg.connect(**db) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DELETE FROM pv_zones")
                sql = (
                    "INSERT INTO pv_zones (zone_id, label, osm_id, active, visible_default, geom) "
                    "VALUES (%s, %s, %s, 1, 1, ST_Multi(ST_GeomFromText(%s, 4326)))"
                )
                for code, (label, osm_id, geom) in sorted(zones.items()):
                    cur.execute(sql, (code, label, osm_id, geom.wkt))

    print(f"Inserted {len(zones)} zone(s) into pv_zones.")


if __name__ == "__main__":
    main()
