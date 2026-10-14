CREATE OR REPLACE VIEW labeled_trips AS
SELECT
    t.*,
    CASE WHEN pu.LocationID IS NOT NULL OR do_zone.LocationID IS NOT NULL
         THEN true ELSE false END AS touches_zone,
    CASE WHEN valid_distance = true AND trip_miles < 2
         THEN true ELSE false END AS is_short_trip,
    CASE WHEN valid_fare = true AND base_passenger_fare <= 11.63
         THEN true ELSE false END AS is_low_fare_trip
FROM clean_trips t
LEFT JOIN crz_lookup pu ON t.PULocationID = pu.LocationID
LEFT JOIN crz_lookup do_zone ON t.DOLocationID = do_zone.LocationID;
