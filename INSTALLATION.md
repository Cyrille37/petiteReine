# PetiteReine Installation Guide

## Prerequisites

### Software Requirements
- **PHP 8.3** with required extensions:
  - `php-pgsql` (PostgreSQL support)
  - `php-dom` (DOM manipulation)
  - `php-json` (JSON support)
- **PostgreSQL 9+** with **PostGIS 2.0+** extension
- **Python 3.7+** and [uv](https://docs.astral.sh/uv/) for the import scripts (dependencies in `pyproject.toml` are resolved automatically)
- **Web Server** (Apache, Nginx, or built-in PHP server)
- **Optional**: Docker and Docker Compose for containerized setup

### System Requirements
- Minimum 2GB RAM (4GB recommended for large datasets)
- 1GB+ disk space for database
- Internet access for Overpass API queries

## Installation

1. **Docker Setup for Postgis**

   ```bash
   docker exec -it petitereine-sql-1 psql -U postgres -d petitereine -f /path/to/res/DB.sql
   ```

2. **Create database and user**
   ```sql
   CREATE DATABASE petitereine;
   CREATE USER petitereine_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE petitereine TO petitereine_user;
   ```

3. **Import database schema**
   ```bash
   psql -U petitereine_user -d petitereine -f res/DB.sql
   ```

4. **Install PHP dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install php php-pgsql php-xml

   # CentOS/RHEL
   sudo yum install php php-pgsql php-xml
   ```

5. **Configure the application**
   ```bash
   cp conf-example.php conf.php
   # Edit conf.php to match your Docker database settings
   ```

## Configuration

Configuration lives in `conf.php` (copy from [conf-example.php](conf-example.php)). The main options:

* **`MODE_ZONE_FILTER`** — `true` activates the "Communes" selector in the UI (it lists `pv_zones`). `false` disables the feature, and the next `import.php` run flushes `pv_zones`.
* **`$CLIENT_CONF`** — map / UI behaviour:
  * `viewPort`: initial viewport, auto-computed from the parkings in the zones with `visible_default = 1`
  * `popupTimeout`: popup display duration in ms
  * `maxClusterRadius` / `disableClusteringAtZoom`: marker clustering
  * `reservedHeight` / `reservedHeightMobile`: space reserved for the UI panels (max accordion height = map height − reserved height)
  * `isMobile`, `zoneFilter`: auto-detected / mirrored from `MODE_ZONE_FILTER`
* **`$DISTANCE_LEVELS`** + **`DIST_PROJ`** — isochrone thresholds (ascending list of `{dist, colour}`) and the projection where 1 unit ≈ 1 meter (e.g. `27572` = Lambert CC42, central France). Used by the legacy PHP import; the Python import takes these from `conf.ini` (`[parkings]`).
* **`$LOCALES` / `$CURRENT_LOCALE`** — available languages and the one detected from the browser (`fr` → `fr-fr`, otherwise `default` = English).
* **`EDIT_JOSM`** — show an "Edit with JOSM" link on parkings with missing data.

For areas outside France, adjust `DIST_PROJ` to a projection fitting your zone.

## Web Server Setup

### Apache Configuration
```apache
<VirtualHost *:80>
    ServerName petitereine.local
    DocumentRoot /path/to/petitereine
    <Directory /path/to/petitereine>
        AllowOverride All
        Require all granted
    </Directory>
    ErrorLog ${APACHE_LOG_DIR}/error.log
    CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
```

### Nginx Configuration
```nginx
server {
    listen 80;
    server_name petitereine.local;
    root /path/to/petitereine;
    index index.php;

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/var/run/php/php7.4-fpm.sock;
    }
}
```

## First or recurrent Data Import

The import is done by the Python scripts, which read everything locally from `data/france.gol` via GeoDesk (no Overpass call). Run the zones first, then the parkings:

```bash
uv run import/import_zones.py     # pv_zones, from [zones] insee in conf.ini
uv run import/import_parkings.py  # pv_parkings + isochrones + export/parkings.json
```

Both accept `--dry-run` to preview without touching the database, and are idempotent (each run replaces the table contents), so re-running them — e.g. from a cron job — is safe. Example of a daily update at 3 AM:

```bash
# crontab -e
0 3 * * * cd /path/to/petitereine && uv run import/import_zones.py && uv run import/import_parkings.py >> /var/log/petitereine-import.log 2>&1
```

`data/france.gol` is a local OSM snapshot; build it from an OSM PBF:

```bash
gol build france data/france-latest.osm.pbf   # produces data/france.gol
```

Legacy PHP imports, kept for reference: `php import/import.php` (parkings, area from `OSM_ZONE` or bbox in `conf.php`) and `php import/import_zones.php` (single zone).

## Troubleshooting

**Database connection issues:**
- Verify PostgreSQL is running
- Check firewall settings
- Test connection: `psql -h localhost -U your_user -d petitereine`

**PostGIS errors:**
- Ensure PostGIS extension is enabled
- Check version compatibility
- Run: `SELECT PostGIS_version();`

**Overpass API timeouts (legacy PHP import only — the Python import makes no Overpass call):**
- Try alternative Overpass API endpoints
- Reduce import area size
- Increase PHP timeout: `set_time_limit(600);`

**Permission problems:**
- Ensure web server has read access to all files
- Check database user permissions
- Verify PostGIS functions are accessible