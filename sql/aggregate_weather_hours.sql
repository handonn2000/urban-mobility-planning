SELECT request_hour,
    COUNT(*) AS trips,
    SUM(CASE WHEN valid_wait THEN 1 ELSE 0 END) AS valid_wait_trips,
    MEDIAN(CASE WHEN valid_wait THEN wait_minutes END) AS median_wait_minutes
FROM weather_sample
GROUP BY request_hour
ORDER BY request_hour;
