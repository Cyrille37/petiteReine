# PetiteReine Installation Guide

## Prerequisites

### Software Requirements
- **PHP 7+** with required extensions:
  - `php-pgsql` (PostgreSQL support)
  - `php-dom` (DOM manipulation)
  - `php-json` (JSON support)
- **PostgreSQL 9+** with **PostGIS 2.0+** extension
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

Read [conf-example.php](conf-example.php).

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

## First or recurent Data Import

1. **Basic import**
   ```bash
   php import/import.php
   ```

2. **With zone filtering** (if MODE_ZONE_FILTER=true)
   ```bash
   php import/import_zones.php
   php import/import.php
   ```

## Troubleshooting

**Database connection issues:**
- Verify PostgreSQL is running
- Check firewall settings
- Test connection: `psql -h localhost -U your_user -d petitereine`

**PostGIS errors:**
- Ensure PostGIS extension is enabled
- Check version compatibility
- Run: `SELECT PostGIS_version();`

**Overpass API timeouts:**
- Try alternative Overpass API endpoints
- Reduce import area size
- Increase PHP timeout: `set_time_limit(600);`

**Permission problems:**
- Ensure web server has read access to all files
- Check database user permissions
- Verify PostGIS functions are accessible