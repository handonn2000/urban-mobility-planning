
        SELECT request_hour, 
COUNT(*) AS trips,
SUM(CASE WHEN is_short_trip THEN 1 ELSE 0 END) AS short_trips,
SUM(CASE WHEN is_low_fare_trip THEN 1 ELSE 0 END) AS low_fare_trips,
SUM(CASE WHEN valid_wait THEN 1 ELSE 0 END) AS valid_wait_trips,
SUM(CASE WHEN valid_fare THEN 1 ELSE 0 END) AS valid_fare_trips,
SUM(CASE WHEN valid_distance THEN 1 ELSE 0 END) AS valid_distance_trips,
SUM(CASE WHEN valid_driver_pay THEN 1 ELSE 0 END) AS valid_driver_pay_trips,
SUM(CASE WHEN valid_economics THEN 1 ELSE 0 END) AS valid_economics_trips,
SUM(CASE WHEN valid_economics THEN base_passenger_fare END) AS total_base_fare,
SUM(CASE WHEN valid_economics THEN driver_pay END) AS total_driver_pay,
MEDIAN(CASE WHEN valid_wait THEN wait_minutes END) AS median_wait_minutes

        FROM labeled_trips
        GROUP BY request_hour
    ;
