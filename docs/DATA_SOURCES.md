# DRIFTWATCH — DATA SOURCES & ACQUISITION

## Free Public Data (acquire first)

### OpenStreetMap
- URL: https://download.geofabrik.de/asia/india.html
- Files needed:
  delhi-ncr: north-zone extract or full india filtered
  mumbai: west-zone extract
  bengaluru: south-zone extract
  chennai: south-zone extract
  hyderabad: south-zone extract
  kolkata: east-zone extract
- Format: .osm.pbf → process with osmium or osm2pgsql
- Extract: railway lines, metro lines, bus stops, road network, ward boundaries

### Census 2011
- URL: https://censusindia.gov.in/census.website/data/census-tables
- Files needed: Primary Census Abstract, ward-level for all 6 cities
- Key tables: B-Series (workers), H-Series (housing), Primary Abstract

### NSSO Data
- URL: https://mospi.gov.in/web/mospi/download-tables-data
- 78th Round (2020-21): Household Consumer Expenditure Survey
- PLFS 2022-23: Periodic Labour Force Survey
- Key variables: MPCE deciles, occupation codes, travel time to work

### DMRC (Delhi Metro)
- URL: https://www.dmrc.org/contents/view/annual-report
- Download: Annual Reports 2021-22, 2022-23, 2023-24
- Extract: station-wise ridership, peak hour volumes, interchange data

### Indian Railways
- URL: https://indianrailways.gov.in/railwayboard/view_section.jsp
- Annual Statistical Statement: zone-wise suburban ridership
- Also available via data.gov.in search "indian railways ridership"

### Lokniti-CSDS
- URL: https://www.lokniti.org/data-archives
- National Election Study 2024 data (register for academic access)
- Key variables: institutional trust indices, political attitudes

### World Values Survey
- URL: https://www.worldvaluessurvey.org/WVSDocumentationWV7.jsp
- India Wave 7 data (2017-22)
- Key variables: risk tolerance, loss aversion, interpersonal trust

### data.gov.in (Government of India Open Data)
- URL: https://data.gov.in
- Search: "urban transport", "metro ridership", "railway passengers"
- BMTC ridership, MTC Chennai data, TSRTC data available here

## API Integrations

### Overpass API (OpenStreetMap queries)
- URL: https://overpass-api.de
- Use for: real-time city infrastructure queries
- Example query for Delhi metro stations:
  [out:json]; node["railway"="station"]["network"="Delhi Metro"]; out body;

### Google Maps Distance Matrix API
- Free tier: 200 requests/day
- Use for: actual travel time between ward centroids
- Purpose: grounds commute decisions in real travel time

### OpenRouteService (free alternative to Google Maps)
- URL: https://openrouteservice.org
- Free tier: 2,000 requests/day
- Better for bulk ward-to-ward distance matrix computation

## Data Processing Pipeline

Step 1: Download OSM extracts → filter to transport network + ward polygons
Step 2: Download Census 2011 ward tables → join to ward polygons by ward code
Step 3: Download NSSO microdata → compute income decile distributions by city
Step 4: Download transit ridership data → calibrate baseline agent commute rates
Step 5: Download Lokniti data → extract institutional trust values by state
Step 6: Download WVS India Wave 7 → extract risk tolerance / loss aversion params
Step 7: Combine into city profile JSON objects (one per city)
Step 8: Run demographic distribution algorithm to place 100,000 agents across wards

## Data Staleness Mitigation
- Use Census 2011 as structural baseline (ward boundaries, demographic proportions)
- Layer current DMRC/MMRDA/BMRCL ridership data on top (published annually)
- Use Google Maps / ORS for current travel times
- Result: 2011 skeleton with 2024 operational data = accurate enough for simulation
- Disclose this methodology explicitly in technical documentation