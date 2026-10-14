SELECT
    CASE WHEN hvfhs_license_num = 'HV0003' THEN 'Uber' ELSE 'Lyft' END AS operator,
    CASE WHEN pu.LocationID IS NOT NULL OR do_zone.LocationID IS NOT NULL THEN true ELSE false END AS touches_zone,
    COUNT(*) AS trips,
    SUM(CASE WHEN cbd_congestion_fee > 0 THEN 1 ELSE 0 END) AS trips_charged_fee
FROM read_parquet('{raw_file}') t
LEFT JOIN read_csv_auto('{zone_file}') pu ON t.PULocationID = pu.LocationID
LEFT JOIN read_csv_auto('{zone_file}') do_zone ON t.DOLocationID = do_zone.LocationID
WHERE hvfhs_license_num IN ('HV0003', 'HV0005')
  AND CAST(request_datetime AS DATE) BETWEEN DATE '2025-01-06' AND DATE '2025-01-26'
GROUP BY operator, touches_zone
ORDER BY operator, touches_zone
