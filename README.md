PetiteReine (french for bicycle) is a visualisation, data analysis and quality assurance tool for bicycle parkings, using OpenStreetMap data.

Demo online at https://petitereine.openstreetmap.fr/. Thanks to the OpenStreetMap France association for providing the technical facilities.

Features : 
* Data import from OpenStreetMap (local GeoDesk `.gol` file, no Overpass call)
* Easy configuration for a small area (city, county)
* Displaying parkings with several useful attributes (type, capacity, covered or not, access rules)
* Statistics based on user - drawn areas
* Filtering by administrative entities
* Highlighting missing or incorrect data
* Localisation support (English and French are available)

## Documentation

For detailed setup instructions, please refer to:
- [INSTALLATION.md](INSTALLATION.md) - Complete setup guide

Additional information is available on the wiki: https://github.com/edewaele/petiteReine/wiki

Project versions:
* Current: https://github.com/Cyrille37/petiteReine
* Original: https://github.com/edewaele/petiteReine (no more activity).

## Install

Tested with PHP 8.3 (`pdo_pgsql`) and PostgreSQL with PostGIS.

### Requirements

Php import:
- php-pgsql
- php-dom

Python import: [uv](https://docs.astral.sh/uv/) (the dependencies in `pyproject.toml` are resolved automatically).

### Import

One script does the whole update:

```
./import/update.sh
```

It downloads the latest Indre-et-Loire OSM extract, builds and verifies the GeoDesk `.gol` file (`import/indre_et_loire-latest.gol`), then runs the two Python imports — zones first, then parkings. All data is read locally from the `.gol` via [GeoDesk](https://docs.geodesk.com/) (no Overpass call):

- `import/import_zones.py`
  - reads the list of `ref:INSEE` codes from `conf.ini` and imports their `[admin_level=8][boundary=administrative]` boundaries into `pv_zones`
  - GUI will have a "Communes" control
- `import/import_parkings.py`
  - imports all `amenity=bicycle_parking` nodes and polygons within the configured zones into `pv_parkings` (assigns `zone_id`, removes `informal` parkings)
  - regenerates the isochrone areas (`pv_parking_dist_zones`) for each distance threshold in `[parkings] distance_levels`, using the `[parkings] dist_proj` projection
  - exports the parkings to `export/parkings.json` and logs a row in `pv_import_trace`

Both scripts also accept a `--dry-run` flag to query the `.gol` file without touching the database.

**Both scripts are idempotent**: each run replaces the whole table contents (`DELETE` + re-`INSERT` in a single transaction), so re-running them (e.g. from a cron job) is safe and always converges to the latest `.gol` data.

Legacy Overpass imports, kept for reference: `php import/import.php` (parkings, area from `OSM_ZONE` or bbox in `conf.php`) and `php import/import_zones.php` (single zone).

### Configuring the Python import

Copy `conf.ini.example` to `conf.ini` (it is gitignored) and fill in:

- `[database]`: the database credentials
- `[data]`: the path to the `.gol` file
- `[zones] insee`: the list of `ref:INSEE` codes to import (used by both scripts)
- `[parkings]`: the projection (`dist_proj`) and the isochrone distance thresholds (`distance_levels`) for the parking import

### Docker

```
docker compose up -d

docker exec -i petitereine-sql-1 psql -U postgres -d petitereine < res/DB.sql
```

## Usage

The web interface (open `index.php` in a browser) shows the imported parkings on a map. Layers are toggled from the layer control (top-right):

* **Parkings** — all parkings, with attributes (type, capacity, covered, access) in the popups
* **Surrounding areas** — the isochrone areas from `pv_parking_dist_zones` (coloured by distance threshold)
* **Missing or incorrect data** — parkings without a capacity, without a type, or duplicated; an "Edit with JOSM" link is included when `EDIT_JOSM` is enabled
* **Private access** — parkings whose `access` is not public
* **Zone boundaries** — only shown when the zone filter is enabled (below)

A few other things to know:

* **Zone filter** — with `MODE_ZONE_FILTER` enabled in `conf.php` and `pv_zones` populated, a "Communes" selector lets you restrict the display and statistics to a given zone.
* **Statistics on a drawn area** — use the draw control (top-left) to draw a polygon or rectangle; the statistics panel is then computed only for the parkings inside that area.
* **GeoJSON export** — the "About" dialog links to the exported data (`export/parkings.json`).
* **Mobile** — the layout adapts to mobile devices.

The map behaviour (viewport, clustering, popups, reserved heights) is configured through `$CLIENT_CONF` in `conf.php`; see [INSTALLATION.md](INSTALLATION.md) for the full list.
