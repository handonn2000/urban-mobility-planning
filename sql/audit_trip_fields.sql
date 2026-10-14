CREATE OR REPLACE VIEW auditable_trips AS
SELECT
    t.*,
    CASE WHEN dates.request_date IS NOT NULL THEN true ELSE false END AS in_period,
    CASE
        WHEN pu.LocationID IS NOT NULL AND pu.LocationID <> 264
         AND do_zone.LocationID IS NOT NULL AND do_zone.LocationID <> 264
        THEN true ELSE false
    END AS known_endpoints,
    CASE WHEN wait_minutes BETWEEN 0 AND 60 THEN true ELSE false END AS valid_wait,
    CASE WHEN isfinite(base_passenger_fare) AND base_passenger_fare > 0
         THEN true ELSE false END AS valid_fare,
    CASE WHEN isfinite(driver_pay) AND driver_pay >= 0
         THEN true ELSE false END AS valid_driver_pay,
    CASE WHEN isfinite(trip_miles) AND trip_miles > 0
         THEN true ELSE false END AS valid_distance
FROM trip_fields t
LEFT JOIN analysis_dates dates ON t.request_date = dates.request_date
LEFT JOIN zone_lookup pu ON t.PULocationID = pu.LocationID
LEFT JOIN zone_lookup do_zone ON t.DOLocationID = do_zone.LocationID;
