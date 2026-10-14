SELECT request_date, operator, touches_zone,
    COUNT(*) AS trips,
    SUM(CASE WHEN is_short_trip THEN 1 ELSE 0 END) AS short_trips,
    SUM(CASE WHEN is_low_fare_trip THEN 1 ELSE 0 END) AS low_fare_trips,
    SUM(CASE WHEN valid_fare THEN 1 ELSE 0 END) AS fare_sample_count,
    SUM(CASE WHEN valid_fare THEN base_passenger_fare END) AS fare_sample_sum,
    SUM(CASE WHEN is_short_trip AND valid_fare THEN 1 ELSE 0 END) AS short_fare_count,
    SUM(CASE WHEN is_short_trip AND valid_fare THEN base_passenger_fare END) AS short_fare_sum,
    SUM(CASE WHEN is_low_fare_trip THEN 1 ELSE 0 END) AS low_fare_count,
    SUM(CASE WHEN is_low_fare_trip THEN base_passenger_fare END) AS low_fare_sum
FROM fee_labeled_trips
GROUP BY request_date, operator, touches_zone
ORDER BY request_date, operator, touches_zone;
