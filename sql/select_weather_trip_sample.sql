CREATE OR REPLACE VIEW weather_sample AS
SELECT *,
    CASE WHEN wait_minutes BETWEEN 0 AND 60 THEN true ELSE false END AS valid_wait
FROM weather_trip_fields
WHERE request_datetime >= TIMESTAMP '2024-06-01'
  AND request_datetime < TIMESTAMP '2024-09-01'
  AND hvfhs_license_num IN ('HV0003', 'HV0005')
  AND PULocationID IN (SELECT LocationID FROM known_zones)
  AND DOLocationID IN (SELECT LocationID FROM known_zones);
