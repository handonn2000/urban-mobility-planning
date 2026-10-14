SELECT count(*) trips,
SUM(CASE WHEN isfinite(trip_miles) AND trip_miles>0 AND trip_miles<2 THEN 1 ELSE 0 END) short_trips,
SUM(CASE WHEN isfinite(base_passenger_fare) AND base_passenger_fare>0 AND base_passenger_fare<=11.63 THEN 1 ELSE 0 END) low_fare_trips,
SUM(CASE WHEN pickup_datetime>=request_datetime AND pickup_datetime<=request_datetime+INTERVAL '60 minutes' THEN 1 ELSE 0 END) valid_wait_trips,
SUM(CASE WHEN isfinite(base_passenger_fare) AND base_passenger_fare>0 AND isfinite(driver_pay) AND driver_pay>=0 THEN CAST(base_passenger_fare AS DECIMAL(18,2)) END) total_base_fare,
SUM(CASE WHEN isfinite(base_passenger_fare) AND base_passenger_fare>0 AND isfinite(driver_pay) AND driver_pay>=0 THEN CAST(driver_pay AS DECIMAL(18,2)) END) total_driver_pay
FROM source_rows WHERE hvfhs_license_num IN ('HV0003','HV0005')
AND strftime(request_datetime,'%Y-%m') IN ('2024-01','2025-01','2025-02')
AND PULocationID IN (SELECT LocationID FROM known_zone_ids)
AND DOLocationID IN (SELECT LocationID FROM known_zone_ids);
