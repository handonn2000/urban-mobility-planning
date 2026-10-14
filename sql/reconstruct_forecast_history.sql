CREATE OR REPLACE TEMP VIEW forecast_source AS
SELECT r.request_datetime, r.dropoff_datetime,
    CAST(r.request_datetime AS DATE) AS request_date,
    CASE WHEN r.hvfhs_license_num = 'HV0003' THEN 'Uber'
         WHEN r.hvfhs_license_num = 'HV0005' THEN 'Lyft' END AS operator,
    CASE WHEN crz_pu.LocationID IS NOT NULL OR crz_do.LocationID IS NOT NULL
         THEN true ELSE false END AS touches_zone
FROM forecast_raw r
JOIN known_zones pu ON r.PULocationID = pu.LocationID
JOIN known_zones do_zone ON r.DOLocationID = do_zone.LocationID
LEFT JOIN forecast_zones crz_pu ON r.PULocationID = crz_pu.LocationID
LEFT JOIN forecast_zones crz_do ON r.DOLocationID = crz_do.LocationID
WHERE r.request_datetime >= TIMESTAMP '2025-01-01'
  AND r.request_datetime < TIMESTAMP '2025-02-17'
  AND r.hvfhs_license_num IN ('HV0003', 'HV0005');
