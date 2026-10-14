CREATE OR REPLACE TABLE clean_trips AS
SELECT
    source_month, request_datetime, pickup_datetime, request_date, request_hour,
    operator, PULocationID, DOLocationID, trip_miles, base_passenger_fare,
    driver_pay, cbd_congestion_fee, wait_minutes, valid_wait, valid_fare,
    valid_driver_pay, valid_distance,
    valid_fare AND valid_driver_pay AS valid_economics
FROM auditable_trips
WHERE in_period = true
  AND operator IS NOT NULL
  AND known_endpoints = true;
