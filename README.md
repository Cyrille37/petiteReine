PetiteReine (french for bicycle) is a visualisation, data analysis and quality assurance tool for bicycle parkings, using OpenStreetMap data.

Demo online at https://petitereine.openstreetmap.fr/. Thanks to the OpenStreetMap France association for providing the technical facilities.

Features : 
* Data import with Overpass API
* Easy configuration for a small area (city, county)
* Displaying parkings with several useful attributes (type, capacity, covered or not, access rules)
* Statictics based on user - drawn areas
* Filtering by administrative entities
* Highlighting missing or incorrect data
* Localisation support (English and French are available)

## Documentation

For detailed installation and usage instructions, please refer to:
- [INSTALLATION.md](INSTALLATION.md) - Complete setup guide
- [USAGE.md](USAGE.md) - Usage instructions and configuration

Additional information is available on the wiki: https://github.com/edewaele/petiteReine/wiki

Project versions:
* Current: https://github.com/Cyrille37/petiteReine
* Original: https://github.com/edewaele/petiteReine (no more activity).

## Install

Tested with Php7 and Postgres 9 (Postgis ?).

### Requirements

Php import:
- php-pgsql
- php-dom

Python import: [uv](https://docs.astral.sh/uv/) (the dependencies in `pyproject.toml` are resolved automatically).

### Import

The Python import reads everything locally from `data/france.gol` via [GeoDesk](https://docs.geodesk.com/) (no Overpass call). Run the zones first, then the parkings:

- `uv run import/import_zones.py`
  - reads the list of `ref:INSEE` codes from `conf.ini` and imports their `[admin_level=8][boundary=administrative]` boundaries into `pv_zones`
  - GUI will have a "Communes" control
- `uv run import/import_parkings.py`
  - imports all `amenity=bicycle_parking` nodes and polygons within the configured zones into `pv_parkings` (assigns `zone_id`, removes `informal` parkings)
  - regenerates the isochrone areas (`pv_parking_dist_zones`) for each distance threshold in `[parkings] distance_levels`, using the `[parkings] dist_proj` projection
  - exports the parkings to `export/parkings.json` and logs a row in `pv_import_trace`

Both scripts accept a `--dry-run` flag to query the `.gol` file without touching the database.

Legacy Overpass imports, kept for reference: `php import/import.php` (parkings, area from `OSM_ZONE` or bbox in `conf.php`) and `php import/import_zones.php` (single zone).

### Configuring the Python import

Copy `conf.ini.example` to `conf.ini` (it is gitignored) and fill in:

- `[database]`: the database credentials
- `[data]`: the path to the `france.gol` file
- `[zones] insee`: the list of `ref:INSEE` codes to import (used by both scripts)
- `[parkings]`: the projection (`dist_proj`) and the isochrone distance thresholds (`distance_levels`) for the parking import

### Docker

```
docker compse up -d

docker exec -i petitereine-sql-1 psql -U postgres -d petitereine < res/DB.sql
```
