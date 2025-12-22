# PetiteReine Usage Guide

## Getting Started

### Accessing the Application
1. Open your web browser
2. Navigate to your configured URL (e.g., http://localhost or http://petitereine.local)
3. The map should automatically load showing bicycle parking locations

### Basic Navigation
- **Pan**: Click and drag the map
- **Zoom**: Use mouse wheel, +/-, or zoom controls
- **Full screen**: Click the full-screen button in top-right corner
- **Layer selection**: Use the layer control in top-right corner

## Data Import and Management

### Import Methods

**Relation-based Import:**
```bash
# Set your OSM relation ID in conf.php
define('IMPORT_FROM_RELATION', true);
define('OSM_ZONE', 123456); // Your relation ID

# Run import
php import/import.php
```

**Bounding Box Import:**
```bash
# Configure bounding box in conf.php
define('IMPORT_FROM_RELATION', false);
define('BBOX_NORTH', 46.64118);
define('BBOX_SOUTH', 46.51351);
define('BBOX_WEST', 0.208053);
define('BBOX_EAST', 0.483398);

# Run import
php import/import.php
```

### Zone Management

**Enable Zone Filtering:**
```php
// In conf.php
define('MODE_ZONE_FILTER', true);
```

**Import Administrative Zones:**
```bash
php import/import_zones.php
php import/import.php
```

**Zone Configuration:**
- Zones are stored in `pv_zones` table
- Each zone has:
  - `zone_id`: Unique identifier
  - `label`: Display name
  - `osm_id`: OSM relation ID
  - `active`: Whether zone is active
  - `visible_default`: Whether shown by default
  - `geom`: Boundary geometry

### Scheduled Updates

**Cron Job Example:**
```bash
# Edit crontab
crontab -e

# Add daily update at 3 AM
0 3 * * * /usr/bin/php /path/to/petitereine/import/import.php >> /var/log/petitereine-import.log 2>&1
```

## Configuration Options

### Map Configuration
```php
// In conf.php
$CLIENT_CONF = array(
    'popupTimeout' => 2000,          // Popup display duration (ms)
    'maxClusterRadius' => 70,        // Marker clustering radius
    'disableClusteringAtZoom' => 18, // Zoom level to disable clustering
    'reservedHeight' => 150,         // Space reserved for UI elements
    'reservedHeightMobile' => 100    // Space on mobile devices
);
```

### Distance Calculation
```php
// In conf.php
define('DIST_PROJ',27572);
$DISTANCE_LEVELS = array(
    array('dist' => 100, 'colour' => 'green'),    // 0-100m: green
    array('dist' => 200, 'colour' => 'yellow'),   // 100-200m: yellow
    array('dist' => 400, 'colour' => 'orange')   // 200-400m: orange
);
```

### Localization
```php
// In conf.php
$LOCALES = array(
    'fr' => 'fr-fr',    // French
    'default' => 'default' // English (fallback)
);
```

## Using the Web Interface

### Map Controls
- **Base Layers**: Switch between different map styles
- **Parking Layers**: Toggle different parking categories
- **Zone Filter**: Filter by administrative zones (if enabled)
- **Statistics Panel**: View parking statistics
- **About Dialog**: Access application information

### Data Analysis Features
- **Statistics by Zone**: View parking counts and capacity
- **Coverage Analysis**: Visualize areas within distance thresholds
- **Data Quality**: Identify missing or incomplete information
- **Export**: Download data as GeoJSON

### Mobile Interface
- Automatically detects mobile devices
- Simplified layout for smaller screens
- Touch-friendly controls
- Optimized space usage

## Advanced Configuration

### Custom Projections
```php
// For regions outside France, adjust the projection
define('DIST_PROJ', 3857); // Web Mercator (EPSG:3857) for global use
```

### Overpass API Configuration
```php
define('OAPI_URL', "https://overpass-api.de/api/interpreter");
```

### Performance Optimization
```php
// For large datasets, adjust clustering
$CLIENT_CONF = array(
    'maxClusterRadius' => 100,        // Larger radius for more clustering
    'disableClusteringAtZoom' => 16   // Disable clustering earlier
);
```

## Troubleshooting Common Issues

**No Parkings Displayed:**
- Verify data import completed successfully
- Check database connection in conf.php
- Ensure zone filtering is properly configured
- Verify Overpass API query returned results

**Slow Performance:**
- Reduce import area size
- Optimize PostGIS queries
- Increase clustering radius
- Use simpler base maps

**Missing Data:**
- Check Overpass API timeout settings
- Verify OSM relation ID is correct
- Ensure bounding box coordinates are valid
- Test with smaller areas first

**Mobile Display Issues:**
- Clear browser cache
- Check mobile detection settings
- Test with different devices
- Verify responsive CSS is loading