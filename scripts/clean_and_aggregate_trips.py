"""Audit trip records, infer zone labels, and create small analysis tables."""
from pathlib import Path
from datetime import datetime, timezone
import json
import math
import duckdb
import pandas as pd


TRIP_FIELDS_SQL = """
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
JOIN source_files source ON r.filename = source.filename
"""

AUDITABLE_SQL = """
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
LEFT JOIN zone_lookup do_zone ON t.DOLocationID = do_zone.LocationID
"""

CLEAN_SQL = """
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
  AND known_endpoints = true
"""

ZONE_COUNTS_SQL = """
CREATE OR REPLACE VIEW zone_fee_counts AS
SELECT
    PULocationID AS LocationID,
    COUNT(*) AS pickup_trips,
    COUNT(cbd_congestion_fee) AS fee_observed_trips,
    SUM(CASE WHEN cbd_congestion_fee > 0 THEN 1 ELSE 0 END) AS fee_positive_trips
FROM clean_trips
WHERE request_date BETWEEN DATE '2025-01-05' AND DATE '2025-01-31'
GROUP BY PULocationID
"""

ZONE_PROFILE_SQL = """
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
ORDER BY z.LocationID
"""

LABEL_SQL = """
CREATE OR REPLACE VIEW labeled_trips AS
SELECT
    t.*,
    CASE WHEN pu.LocationID IS NOT NULL OR do_zone.LocationID IS NOT NULL
         THEN true ELSE false END AS touches_zone,
    CASE WHEN valid_distance = true AND trip_miles < 2
         THEN true ELSE false END AS is_short_trip,
    CASE WHEN valid_fare = true AND base_passenger_fare <= {low_fare_threshold}
         THEN true ELSE false END AS is_low_fare_trip
FROM clean_trips t
LEFT JOIN crz_lookup pu ON t.PULocationID = pu.LocationID
LEFT JOIN crz_lookup do_zone ON t.DOLocationID = do_zone.LocationID
"""

METRIC_SQL = """
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
"""

def build_analysis_tables(root):
    root = Path(root).resolve()
    for directory in ["data/processed", "docs", "sql", ".analysis-cache"]:
        (root / directory).mkdir(parents=True, exist_ok=True)
    files = [root / f"data/raw/fhvhv_tripdata_{month}.parquet"
             for month in ["2024-01", "2025-01", "2025-02"]]
    if not all(path.exists() for path in files):
        raise FileNotFoundError("Prepare the three source Parquet files first.")
    zones = pd.read_csv(root / "data/external/taxi_zone_lookup.csv")
    if zones.LocationID.isna().any() or not zones.LocationID.is_unique:
        raise ValueError("Zone lookup must have a unique non-null LocationID.")
    dates = pd.concat([pd.Series(pd.date_range(start, end, freq="D")) for start, end in [
        ("2024-01-01", "2024-01-31"), ("2025-01-01", "2025-02-28")]], ignore_index=True)
    date_frame = pd.DataFrame({"request_date": dates})
    con = duckdb.connect(str(root / ".analysis-cache/trip_processing.duckdb"))
    con.execute("SET threads=4")
    con.execute("SET memory_limit='2GB'")
    spill_dir = str(root / ".analysis-cache/spill").replace("'", "''")
    con.execute(f"SET temp_directory='{spill_dir}'")
    con.read_parquet([str(path) for path in files], union_by_name=True, filename=True).create_view("raw_trips", replace=True)
    con.register("zone_lookup", zones)
    con.register("analysis_dates", date_frame)
    source_files = pd.DataFrame({"filename": [str(path) for path in files],
                                 "source_month": ["2024-01", "2025-01", "2025-02"]})
    con.register("source_files", source_files)
    queries = {"derive_trip_fields.sql": TRIP_FIELDS_SQL, "audit_trip_fields.sql": AUDITABLE_SQL,
               "retain_classifiable_trips.sql": CLEAN_SQL, "count_zone_fees.sql": ZONE_COUNTS_SQL,
               "infer_congestion_zones.sql": ZONE_PROFILE_SQL}
    for name, sql in queries.items():
        (root / "sql" / name).write_text(sql.strip() + ";\n")
    con.execute(TRIP_FIELDS_SQL)
    con.execute(AUDITABLE_SQL)

    audit_rules = [
        ("missing_request_time", "request_datetime IS NULL", "exclude", "Không xác định được ngày phân tích"),
        ("request_outside_source_month", "strftime(request_datetime, '%Y-%m') <> source_month", "flag", "Phân tháng theo request trong toàn bộ phạm vi, không loại chỉ vì khác tháng file"),
        ("request_outside_analysis_period", "NOT in_period", "exclude", "Ngày đặt ngoài 90 ngày đã chọn"),
        ("unsupported_operator", "operator IS NULL", "exclude", "Chỉ phân tích Uber và Lyft"),
        ("unknown_endpoint", "NOT known_endpoints", "exclude", "Không đủ cơ sở gắn nhãn vùng; 264 là Unknown, 265 Outside of NYC được giữ"),
        ("missing_pickup_time", "pickup_datetime IS NULL", "metric_only", "Giữ chuyến; bỏ khỏi mẫu thời gian chờ"),
        ("negative_wait", "wait_minutes < 0", "metric_only", "Giữ chuyến; bỏ khỏi mẫu thời gian chờ"),
        ("wait_over_60_minutes", "wait_minutes > 60", "metric_only", "Giữ chuyến; bỏ khỏi mẫu thời gian chờ"),
        ("invalid_fare", "NOT valid_fare", "metric_only", "Cước phải hữu hạn và >0; không dùng để tính giá, giá thấp hoặc mẫu kinh tế"),
        ("invalid_driver_pay", "NOT valid_driver_pay", "metric_only", "Tiền tài xế phải hữu hạn và >=0; không dùng cho mẫu kinh tế"),
        ("invalid_distance", "NOT valid_distance", "metric_only", "Quãng đường phải hữu hạn và >0; không gắn nhãn chuyến ngắn"),
        ("negative_congestion_fee", "cbd_congestion_fee < 0", "flag", "Giữ chuyến; khoản điều chỉnh không tính là có phí dương"),
        ("missing_congestion_fee", "cbd_congestion_fee IS NULL", "flag", "2024 thiếu cột phí theo schema; không đổi NULL thành 0"),
    ]
    sums = ",\n".join(f"SUM(CASE WHEN {condition} THEN 1 ELSE 0 END) AS {name}" for name, condition, _, _ in audit_rules)
    raw_audit = con.execute(f"SELECT source_month, count(*) raw_trips, {sums} FROM auditable_trips GROUP BY source_month ORDER BY source_month").df()
    records = []
    for _, row in raw_audit.iterrows():
        for name, _, decision, reason in audit_rules:
            records.append({"source_month": row.source_month, "rule": name,
                            "affected_trips": int(row[name]), "raw_trips": int(row.raw_trips),
                            "decision": decision, "reason": reason})
    audit = pd.DataFrame(records)
    audit.to_csv(root / "data/processed/trip_quality_audit.csv", index=False)
    exclusions = con.execute("""
        SELECT source_month, count(*) raw_trips,
            SUM(CASE WHEN NOT in_period THEN 1 ELSE 0 END) excluded_outside_period,
            SUM(CASE WHEN in_period AND operator IS NULL THEN 1 ELSE 0 END) excluded_operator,
            SUM(CASE WHEN in_period AND operator IS NOT NULL AND NOT known_endpoints THEN 1 ELSE 0 END) excluded_unknown_endpoints,
            SUM(CASE WHEN in_period AND operator IS NOT NULL AND known_endpoints THEN 1 ELSE 0 END) retained_trips
        FROM auditable_trips GROUP BY source_month ORDER BY source_month
    """).df()
    exclusions.to_csv(root / "data/processed/trip_exclusion_summary.csv", index=False)
    print("Audit saved. Retaining trips with an in-scope request and known endpoints.", flush=True)
    con.execute(CLEAN_SQL)
    con.execute(ZONE_COUNTS_SQL)
    profile = con.execute(ZONE_PROFILE_SQL).df()
    zone_counts = ["pickup_trips", "fee_observed_trips", "fee_positive_trips"]
    profile[zone_counts] = profile[zone_counts].astype("int64")
    profile.to_csv(root / "data/processed/zone_fee_profile.csv", index=False)
    crz = profile[profile.fee_rate >= .95].copy()
    if crz.empty:
        raise ValueError("No zone meets the congestion-fee threshold; inspect source data.")
    crz.to_csv(root / "data/processed/crz_zones.csv", index=False)
    sensitivity = pd.concat([profile.assign(zone_threshold=threshold, is_zone=profile.fee_rate >= threshold)
                             for threshold in [.90, .95, .99]], ignore_index=True)
    sensitivity.to_csv(root / "data/processed/zone_definition_sensitivity.csv", index=False)
    con.register("crz_lookup", crz)
    threshold_query = """
        SELECT quantile_cont(base_passenger_fare, 0.25)
        FROM clean_trips
        WHERE request_date BETWEEN DATE '2024-01-01' AND DATE '2024-01-31'
          AND valid_fare = true
    """
    threshold = float(con.execute(threshold_query).fetchone()[0])
    label_sql = LABEL_SQL.format(low_fare_threshold=repr(threshold))
    (root / "sql/label_analysis_segments.sql").write_text(label_sql.strip() + ";\n")
    con.execute(label_sql)
    print(f"Zone labels: {len(crz)} zones. Fixed low-fare threshold: ${threshold:.2f}.", flush=True)

    daily_sql = f"""
        SELECT request_date, operator, touches_zone, {METRIC_SQL}
        FROM labeled_trips
        GROUP BY request_date, operator, touches_zone
    """
    hourly_sql = f"""
        SELECT request_hour, {METRIC_SQL}
        FROM labeled_trips
        GROUP BY request_hour
    """
    (root / "sql/aggregate_daily_segments.sql").write_text(daily_sql + ";\n")
    (root / "sql/aggregate_hourly_city.sql").write_text(hourly_sql + ";\n")
    daily_raw = con.execute(daily_sql).df()
    hourly_raw = con.execute(hourly_sql).df()
    
    coverage = con.execute("SELECT request_hour,count(*) source_trips FROM auditable_trips WHERE in_period AND operator IS NOT NULL GROUP BY request_hour").df()
    hour_grid = pd.DataFrame({"request_hour": pd.DatetimeIndex([day + pd.Timedelta(hours=hour) for day in dates for hour in range(24)])})
    hourly = hour_grid.merge(hourly_raw, on="request_hour", how="left", validate="one_to_one")
    hourly = hourly.merge(coverage, on="request_hour", how="left", validate="one_to_one")
    hourly["data_available"] = hourly.source_trips.notna()
    daily_grid = pd.MultiIndex.from_product([pd.DatetimeIndex(dates), ["Uber", "Lyft"], [False, True]],
                                           names=["request_date", "operator", "touches_zone"]).to_frame(index=False)
    daily = daily_grid.merge(daily_raw, on=["request_date", "operator", "touches_zone"], how="left", validate="one_to_one")
    date_coverage = hourly.assign(request_date=hourly.request_hour.dt.normalize()).groupby("request_date").data_available.all()
    daily["data_available"] = daily.request_date.map(date_coverage)
    count_columns = ["trips", "short_trips", "low_fare_trips", "valid_wait_trips", "valid_fare_trips",
                     "valid_distance_trips", "valid_driver_pay_trips", "valid_economics_trips"]
    empty_counts = []
    for table in [daily, hourly]:
        empty = table.trips.isna() & table.data_available
        empty_counts.append(int(empty.sum()))
        table.loc[empty, count_columns + ["total_base_fare", "total_driver_pay"]] = 0
        for name in count_columns:
            table[name] = table[name].astype("Int64")
        
    weather = pd.read_csv(root / "data/external/weather_hourly.csv", parse_dates=["request_hour"])
    calendar = pd.read_csv(root / "data/external/holidays.csv", parse_dates=["date"]).rename(columns={"date": "request_date"})
    if not calendar.request_date.is_unique:
        raise ValueError("Holiday dates must be unique before merging.")
    hourly = hourly.merge(weather, on="request_hour", how="left", validate="one_to_one")
    hourly["request_date"] = hourly.request_hour.dt.normalize()
    daily = daily.merge(calendar, on="request_date", how="left", validate="many_to_one")
    hourly = hourly.merge(calendar, on="request_date", how="left", validate="many_to_one")
    for table in [daily, hourly]:
        table["is_holiday"] = table.holiday_name.notna()
        table["day_of_week"] = table.request_date.dt.dayofweek
    hourly["hour"] = hourly.request_hour.dt.hour
    daily = daily.sort_values(["request_date", "operator", "touches_zone"]).reset_index(drop=True)
    hourly = hourly.sort_values("request_hour").reset_index(drop=True)
    daily.to_csv(root / "data/processed/daily_segment.csv", index=False)
    hourly.to_csv(root / "data/processed/hourly_city.csv", index=False)
    metric_quality = daily.groupby(["request_date", "operator"])[count_columns].sum().reset_index()
    metric_quality["fare_excluded_trips"] = metric_quality.trips - metric_quality.valid_fare_trips
    metric_quality["wait_excluded_trips"] = metric_quality.trips - metric_quality.valid_wait_trips
    metric_quality["fare_excluded_share"] = metric_quality.fare_excluded_trips / metric_quality.trips
    metric_quality["wait_excluded_share"] = metric_quality.wait_excluded_trips / metric_quality.trips
    metric_quality.to_csv(root / "data/processed/metric_quality_by_date.csv", index=False)
    print("Daily and hourly tables saved. Reconciling counts and monetary sums.", flush=True)

    additive = count_columns + ["total_base_fare", "total_driver_pay"]
    clean_totals = con.execute(f"SELECT {METRIC_SQL} FROM labeled_trips").df().iloc[0]
    recon = []
    for name in additive:
        expected = float(clean_totals[name])
        for table_name, table in [("daily_segment", daily), ("hourly_city", hourly)]:
            observed = float(table[name].sum())
            recon.append({"table": table_name, "metric": name, "clean_total": expected,
                          "aggregate_total": observed, "difference": observed - expected,
                          "matches": math.isclose(expected, observed, rel_tol=1e-12, abs_tol=.01 if name.startswith('total_') else 0)})
    recon = pd.DataFrame(recon)
    recon.to_csv(root / "data/processed/aggregation_reconciliation.csv", index=False)
    expected_daily_totals = hourly.groupby("request_date")[additive].sum()
    actual_daily_totals = daily.groupby("request_date")[additive].sum()
    pd.testing.assert_frame_equal(expected_daily_totals[count_columns], actual_daily_totals[count_columns], check_dtype=False)
    for name in ["total_base_fare", "total_driver_pay"]:
        if any(not math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=.01)
               for a, b in zip(expected_daily_totals[name], actual_daily_totals[name])):
            raise ValueError("Daily monetary totals do not reconcile: " + name)
    exclusion_partition = exclusions.raw_trips == exclusions[["excluded_outside_period", "excluded_operator", "excluded_unknown_endpoints", "retained_trips"]].sum(axis=1)
    assert exclusion_partition.all(), "Exclusion reasons must partition the raw universe."
    assert int(clean_totals.trips) == int(exclusions.retained_trips.sum())
    assert len(daily) == 360 and len(hourly) == 2160
    assert daily.data_available.all() and hourly.data_available.all(), "Missing source coverage must not be filled with zero."
    assert recon.matches.all(), "Aggregate totals differ from retained trips."
    assert hourly[["temperature_c", "rain_mm", "snowfall_cm"]].notna().all().all()
    assert not daily.duplicated(["request_date", "operator", "touches_zone"]).any()
    assert not hourly.request_hour.duplicated().any()
    for table in [daily, hourly]:
        assert (table[count_columns[1:]].le(table.trips, axis=0)).all().all()
        assert table.loc[table.valid_wait_trips > 0, "median_wait_minutes"].between(0, 60).all()
    fee_labels = con.execute("""
        SELECT operator,touches_zone,count(*) trips,count(cbd_congestion_fee) fee_observed_trips,
            SUM(CASE WHEN cbd_congestion_fee>0 THEN 1 ELSE 0 END) fee_positive_trips,
            avg(CASE WHEN cbd_congestion_fee>0 THEN 1.0 ELSE 0 END) fee_positive_share
        FROM labeled_trips WHERE request_date BETWEEN DATE '2025-01-05' AND DATE '2025-01-31'
        GROUP BY operator, touches_zone ORDER BY operator, touches_zone
    """).df()
    fee_labels.to_csv(root / "data/processed/fee_label_diagnostics.csv", index=False)
    spot_daily = con.execute(f"SELECT request_date,operator,touches_zone,{METRIC_SQL} FROM labeled_trips WHERE request_date=DATE '2025-01-21' AND operator='Lyft' AND touches_zone GROUP BY request_date, operator, touches_zone").df()
    match = daily[(daily.request_date == pd.Timestamp('2025-01-21')) & (daily.operator == 'Lyft') & daily.touches_zone]
    for name in additive + ["median_wait_minutes"]:
        assert math.isclose(float(spot_daily.iloc[0][name]), float(match.iloc[0][name]), rel_tol=1e-12, abs_tol=.01)
    spot_daily.to_csv(root / "data/processed/daily_segment_spot_check.csv", index=False)
    parameters = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                  "date_basis": "request_datetime, New York local time",
                  "zone_threshold": .95, "zone_count": len(crz),
                  "zone_inference_dates": ["2025-01-05", "2025-01-31"],
                  "low_fare_threshold_usd": threshold,
                  "low_fare_reference": "All retained Jan 2024 trips with finite positive base fare; pooled across operators/zones",
                  "low_fare_definition": "base_passenger_fare <= reference 25th percentile; ties included",
                  "short_trip_definition": "0 < trip_miles < 2",
                  "valid_wait_definition": "0 <= pickup_datetime - request_datetime <= 60 minutes",
                  "monetary_sample": "Both total_base_fare and total_driver_pay use the same valid_economics sample",
                  "outside_nyc_zone": "265 retained as a known outside-zone endpoint; 264 Unknown excluded",
                  "retained_trips": int(clean_totals.trips), "daily_rows": len(daily), "hourly_rows": len(hourly),
                  "empty_daily_segments_filled": empty_counts[0], "empty_hours_filled": empty_counts[1],
                  "source_coverage": "Every expected hour contains in-scope Uber/Lyft requests; this does not prove provider-level completeness",
                  "boundary_limit": "January 2024 cannot include requests picked up in February 2024 because that source month is outside scope; Jan/Feb 2025 requests are reassigned across the available adjacent files"}
    (root / "docs/trip_processing_parameters.json").write_text(json.dumps(parameters, indent=2, ensure_ascii=False) + "\n")
    write_quality_report(root, audit, exclusions, crz, threshold, daily, hourly, fee_labels)
    con.close()
    print(f"Retained {int(clean_totals.trips):,} trips; {len(daily)} daily segments and {len(hourly)} hourly records.", flush=True)
    return daily, hourly


def write_quality_report(root, audit, exclusions, crz, threshold, daily, hourly, fee_labels):
    lines = ["# Làm sạch và tổng hợp chuyến", "",
             "## Cách thực hiện", "",
             "1. Audit raw bằng SQL, đếm từng quy tắc riêng. Một chuyến có thể vi phạm nhiều quy tắc; không cộng các dòng audit để suy ra tổng bị loại.",
             "2. Chọn ngày request trong 90 ngày nghiên cứu trên cả ba file; không loại chỉ vì request khác tháng nguồn. Chỉ giữ Uber/Lyft và hai endpoint xác định. Zone 265 Outside of NYC được giữ; 264 Unknown bị loại khỏi tập phân tích chung.",
             "3. Giữ chuyến có giá/chờ/quãng đường lỗi để đếm; chỉ bỏ metric tương ứng. Hai tổng cước và tiền tài xế cùng dùng mẫu kinh tế hợp lệ.",
             "4. Suy ra vùng từ tỷ lệ phí dương trên toàn bộ chuyến đón 05-31/01/2025 của tập giữ lại. Ngưỡng chính 95%; lưu nhãn 90% và 99% để kiểm tra độ vững sau này. Không coi NULL phí là số đo 0.",
             "5. Ngưỡng giá thấp lấy một lần từ cước dương hợp lệ 01/2024; phân vị 25% và dùng <= để bao gồm giá trùng ngưỡng. Chuyến ngắn: 0<dặm<2.",
             "6. Gộp ngày × hãng × nhãn vùng và giờ toàn thành phố; lấp lưới theo coverage, nối thời tiết/lễ với kiểm tra cardinality.",
             "7. Đối chiếu từng metric cộng được với tập giữ lại và giữa hai bảng cho từng ngày; kiểm tra riêng một phân khúc 21/01/2025.", "",
             "## Quy mô sau xử lý", "", "| Tháng file | Raw | Ngoài thời kỳ | Hãng khác | Endpoint không rõ | Giữ lại |",
             "|---|---:|---:|---:|---:|---:|"]
    for r in exclusions.itertuples(index=False):
        lines.append(f"| {r.source_month} | {r.raw_trips:,} | {r.excluded_outside_period:,} | {r.excluded_operator:,} | {r.excluded_unknown_endpoints:,} | {r.retained_trips:,} |")
    lines += ["", f"Tổng giữ lại: {int(exclusions.retained_trips.sum()):,} chuyến. Vùng thu phí: {len(crz)} zone. Ngưỡng giá thấp: ${threshold:.2f}.",
              f"Bảng ngày: {len(daily)} dòng. Bảng giờ: {len(hourly)} dòng. Median chờ dùng quan sát hợp lệ, không lấy trung bình median giữa các nhóm.",
              "", "## Quy tắc audit và quyết định", "", "| Quy tắc | Dòng ảnh hưởng trên raw | Quyết định | Lý do |", "|---|---:|---|---|"]
    for rule, group in audit.groupby("rule", sort=False):
        first = group.iloc[0]
        lines.append(f"| {rule} | {int(group.affected_trips.sum()):,} | {first.decision} | {first.reason} |")
    lines += ["", "## Nhãn vùng và phí thực tế", "", "| Hãng | Chạm vùng | Chuyến | Có phí dương | Tỷ lệ |", "|---|---|---:|---:|---:|"]
    for r in fee_labels.itertuples(index=False):
        lines.append(f"| {r.operator} | {r.touches_zone} | {r.trips:,} | {r.fee_positive_trips:,} | {r.fee_positive_share:.2%} |")
    lines += ["", "## Giới hạn", "",
              "- Cước bằng 0 có thể là điều chỉnh/khuyến mãi hoặc vấn đề báo cáo; chưa biết nguyên nhân. Không xóa chuyến, nhưng trung bình giá chỉ phản ánh mẫu cước dương. metric_quality_by_date.csv cho biết mức mất mẫu theo ngày/hãng.",
              "- Nhãn endpoint không nhận biết chuyến xuyên vùng. Nhóm ngoài vùng vẫn có thể chịu phí; bảng diagnostics lượng hóa sai khác này.",
              "- Bỏ endpoint không rõ làm thay đổi phạm vi so với raw. Các tổng và tỷ lệ trong phân tích chỉ đại diện tập đã giữ lại.",
              "- Tháng 01/2024 thiếu các chuyến request cuối tháng nhưng pickup trong tháng 02/2024. Đầu/cuối phạm vi có sai khác biên; không giả lập dữ liệu chưa tải.",
              "- Mỗi giờ có dòng nguồn không chứng minh nhà cung cấp đã báo cáo đầy đủ mọi chuyến. data_available chỉ phản ánh coverage quan sát.",
              "- Không có trip ID tin cậy để suy ra hai dòng giống nhau là một chuyến. Không tự deduplicate bằng giờ/zone/giá vì có thể xóa chuyến thật.",
              "- Chênh lệch cước và driver pay là proxy, không phải lợi nhuận đóng góp hoặc take rate kế toán đã xác minh.", ""]
    fare_quality = daily.groupby(["request_date", "operator"])[["trips", "valid_fare_trips"]].sum().reset_index()
    fare_quality["excluded_fare_trips"] = fare_quality.trips - fare_quality.valid_fare_trips
    worst = fare_quality.sort_values("excluded_fare_trips", ascending=False).iloc[0]
    lines += ["## Quan sát cần điều tra tiếp", "",
              f"Ngày {worst.request_date:%Y-%m-%d}, {worst.operator}: {int(worst.excluded_fare_trips):,}/{int(worst.trips):,} chuyến không thuộc mẫu cước dương hợp lệ ({worst.excluded_fare_trips / worst.trips:.2%}). Đây là hiện tượng dữ liệu cần điều tra, chưa có bằng chứng để gán nguyên nhân cho credit hay chính sách phí.", ""]
    (root / "docs/trip_data_quality.md").write_text("\n".join(lines))


if __name__ == "__main__":
    build_analysis_tables(Path(__file__).resolve().parents[1])
