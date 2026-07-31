Static map overlays for the UFO Timeline World Map.

Sources
- Airports: https://d2ad6b4ur7yvpq.cloudfront.net/naturalearth-3.3.0/ne_10m_airports.geojson
- Highways / interstates: https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/USA_Freeway_System/FeatureServer/1/query
- Military bases: https://download.geonames.org/export/dump/allCountries.zip + https://download.geonames.org/export/dump/countryInfo.txt

Notes
- Airports are lightweight Natural Earth point features.
- Highways are simplified ArcGIS interstate lines.
- Military installations are global point records derived from GeoNames and normalized into air / naval / army / other branches.
- Runtime uses points and lines only; no large military land polygons are shipped in the public bundle.
