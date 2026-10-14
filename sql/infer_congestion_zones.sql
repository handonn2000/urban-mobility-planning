SELECT
    z.LocationID, z.Borough, z.Zone,
    COALESCE(c.pickup_trips, 0) AS pickup_trips,
    COALESCE(c.fee_observed_trips, 0) AS fee_observed_trips,
    COALESCE(c.fee_positive_trips, 0) AS fee_positive_trips,
    CASE WHEN c.pickup_trips > 0
         THEN 1.0 * c.fee_positive_trips / c.pickup_trips
    END AS fee_rate
FROM zone_lookup z
LEFT JOIN zone_fee_counts c ON z.LocationID = c.LocationID
ORDER BY z.LocationID;
