SELECT
    CAST(request_datetime AS DATE) AS request_date,
    COUNT(*) AS lyft_trips_charged_fee,
    SUM(cbd_congestion_fee) AS lyft_fee_usd
FROM read_parquet('{raw_file}')
WHERE hvfhs_license_num = 'HV0005'
  AND cbd_congestion_fee > 0
  AND CAST(request_datetime AS DATE) BETWEEN DATE '2025-01-05' AND DATE '2025-01-31'
GROUP BY CAST(request_datetime AS DATE)
ORDER BY request_date
