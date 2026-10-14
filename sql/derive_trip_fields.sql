CREATE OR REPLACE VIEW trip_fields AS
SELECT
    source.source_month,
    r.request_datetime,
    r.pickup_datetime,
    r.PULocationID,
    r.DOLocationID,
    r.trip_miles,
    r.base_passenger_fare,
    r.driver_pay,
    r.cbd_congestion_fee,
    CAST(r.request_datetime AS DATE) AS request_date,
    date_trunc('hour', r.request_datetime) AS request_hour,
    CASE
        WHEN r.hvfhs_license_num = 'HV0003' THEN 'Uber'
        WHEN r.hvfhs_license_num = 'HV0005' THEN 'Lyft'
    END AS operator,
    date_diff('second', r.request_datetime, r.pickup_datetime) / 60.0 AS wait_minutes
FROM raw_trips r
JOIN source_files source ON r.filename = source.filename;
