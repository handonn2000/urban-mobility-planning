CREATE OR REPLACE VIEW weather_trip_fields AS
SELECT
    request_datetime,
    CAST(request_datetime AS DATE) AS request_date,
    date_trunc('hour', request_datetime) AS request_hour,
    hvfhs_license_num,
    PULocationID,
    DOLocationID,
    date_diff('second', request_datetime, pickup_datetime) / 60.0 AS wait_minutes
FROM weather_raw_trips;
