SELECT EXTRACT(YEAR FROM request_datetime) AS year,
CASE WHEN PULocationID IN (SELECT LocationID FROM selected_zones)
       OR DOLocationID IN (SELECT LocationID FROM selected_zones)
     THEN true ELSE false END AS touches_zone,
COUNT(*) AS trips
FROM raw_verification
WHERE hvfhs_license_num IN ('HV0003','HV0005')
  AND PULocationID IN (SELECT LocationID FROM known_endpoints)
  AND DOLocationID IN (SELECT LocationID FROM known_endpoints)
  AND (CAST(request_datetime AS DATE) BETWEEN DATE '2024-01-08' AND DATE '2024-01-28'
       OR CAST(request_datetime AS DATE) BETWEEN DATE '2025-01-06' AND DATE '2025-01-26')
GROUP BY year, touches_zone
ORDER BY year, touches_zone;
