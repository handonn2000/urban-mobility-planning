CREATE OR REPLACE VIEW zone_fee_counts AS
SELECT
    PULocationID AS LocationID,
    COUNT(*) AS pickup_trips,
    COUNT(cbd_congestion_fee) AS fee_observed_trips,
    SUM(CASE WHEN cbd_congestion_fee > 0 THEN 1 ELSE 0 END) AS fee_positive_trips
FROM clean_trips
WHERE request_date BETWEEN DATE '2025-01-05' AND DATE '2025-01-31'
GROUP BY PULocationID;
