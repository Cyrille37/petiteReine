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

You can read the installation instructions on the wiki: https://github.com/edewaele/petiteReine/wiki

Project versions:
* Current: https://github.com/Cyrille37/petiteReine
* Original: https://github.com/edewaele/petiteReine (no more activity).

## Install

Tested with Php7 and Postgres 9 (Postgis ?).

### Requirements

Php import:
- php-pgsql
- php-dom

### Import

In conf.php set OSM_ZONE with a relation Id to import all ways and nodes with `amenity=bicycle_parking` inside the relation.

When conf has `MODE_ZONE_FILTER=true` :
- php import/import_zones.php
  - create zones for `[admin_level=8][boundary=administrative]`
  - GUI will have a "Communes" control
- php import/import.php

When `MODE_ZONE_FILTER=false`:
- php import/import.php

