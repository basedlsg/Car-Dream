#!/bin/bash
set -euo pipefail

# Download OSM data (example: Berlin)
wget https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf

# Convert OSM data to XODR format (optional)
# Requires osm2xodr: https://github.com/JHMeusener/osm2xodr
# osm2xodr berlin-latest.osm.pbf -o berlin.xodr

echo "OSM data downloaded successfully."