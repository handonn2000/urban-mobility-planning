"""Download public trip/weather sources and inspect input consistency."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
import time

import duckdb
import holidays
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
MONTHS = [("2024-01", "2024-01-01", "2024-01-31"),
          ("2025-01", "2025-01-01", "2025-01-31"),
          ("2025-02", "2025-02-01", "2025-02-28")]
MANIFEST = ROOT / "data/external/source_manifest.json"
REQUIRED = {"request_datetime", "pickup_datetime", "dropoff_datetime", "PULocationID", "DOLocationID",
            "hvfhs_license_num", "trip_miles", "base_passenger_fare", "driver_pay"}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def record(path, url, manifest, **extra):
    manifest[str(path.relative_to(ROOT))] = {
        "url": url, "downloaded_at_utc": utcnow(), "bytes": path.stat().st_size,
        "sha256": digest(path), **extra,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def download(url, path, manifest, params=None):
    key = str(path.relative_to(ROOT))
    if path.exists():
        previous = manifest.get(key)
        if previous and digest(path) == previous["sha256"]:
            print(f"Reuse verified: {key}", flush=True)
            return
        raise RuntimeError(f"Unverified or modified input: {path}. Preserve and inspect it before redownloading.")
    partial = path.with_suffix(path.suffix + ".partial")
    for attempt in range(3):
        try:
            with requests.get(url, params=params, stream=True, timeout=(30, 180)) as response:
                response.raise_for_status()
                length = int(response.headers.get("content-length", 0))
                print(f"Downloading {key}: {length / 1e6:.1f} MB", flush=True)
                size, last = 0, time.monotonic()
                with partial.open("wb") as f:
                    for chunk in response.iter_content(4 * 1024 * 1024):
                        f.write(chunk)
                        size += len(chunk)
                        if time.monotonic() - last >= 15:
                            print(f"  {key}: {size / 1e6:.1f} MB received", flush=True)
                            last = time.monotonic()
                if length and size != length:
                    raise ValueError(f"Incomplete response {size}/{length}")
                if not size:
                    raise ValueError("Empty response")
                if path.suffix == ".parquet":
                    with partial.open("rb") as f:
                        if f.read(4) != b"PAR1":
                            raise ValueError("Invalid Parquet header")
                        f.seek(-4, 2)
                        if f.read(4) != b"PAR1":
                            raise ValueError("Invalid Parquet footer")
                partial.replace(path)
                record(path, response.url, manifest)
                print(f"Saved {key}: {size / 1e6:.1f} MB", flush=True)
                return
        except (requests.RequestException, ValueError) as exc:
            if attempt == 2:
                raise
            print(f"Retry {attempt + 1}: {exc}", flush=True)
            time.sleep(2 * (attempt + 1))


def prepare(manifest):
    for month, start, end in MONTHS:
        download(f"https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_{month}.parquet",
                 ROOT / f"data/raw/fhvhv_tripdata_{month}.parquet", manifest)
    download("https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv",
             ROOT / "data/external/taxi_zone_lookup.csv", manifest)
    frames = []
    for month, start, end in MONTHS:
        path = ROOT / f"data/external/weather_{month}.json"
        download("https://archive-api.open-meteo.com/v1/archive", path, manifest, params={
            "latitude": 40.7812, "longitude": -73.9665, "start_date": start,
            "end_date": end, "hourly": "temperature_2m,rain,snowfall",
            "timezone": "America/New_York", "models": "era5", "temperature_unit": "celsius",
            "precipitation_unit": "mm",
        })
        payload = json.loads(path.read_text())
        if payload.get("timezone") != "America/New_York":
            raise ValueError("Unexpected weather timezone")
        frame = pd.DataFrame(payload["hourly"])
        frame = frame.rename(columns={"time": "request_hour", "temperature_2m": "temperature_c",
                                      "rain": "rain_mm", "snowfall": "snowfall_cm"})
        frames.append(frame)
    pd.concat(frames, ignore_index=True).to_csv(ROOT / "data/external/weather_hourly.csv", index=False)
    calendar = holidays.US(years=[2024, 2025], observed=True)
    pd.DataFrame(sorted(calendar.items()), columns=["date", "holiday_name"]).to_csv(
        ROOT / "data/external/holidays.csv", index=False)
    manifest["derived_sources"] = {
        "weather_hourly.csv": {"inputs": [f"weather_{m}.json" for m, _, _ in MONTHS],
                               "model": "ERA5", "timezone": "America/New_York",
                               "note": "Historical reanalysis; not a forecast known at 16 Feb 2025"},
        "holidays.csv": {"country": "US", "years": [2024, 2025], "observed": True,
                         "holidays_version": importlib.metadata.version("holidays")},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def validate():
    checks, inventory, schemas, fee_frames, timing = [], [], {}, [], []

    def check(name, condition, details):
        checks.append({"check": name, "valid": bool(condition), "details": details})

    versions = {}
    for pkg in ["duckdb", "pandas", "requests", "holidays"]:
        __import__(pkg)
        versions[pkg] = importlib.metadata.version(pkg)
    check("libraries_import", True, versions)
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='2GB'")
    for month, start, end in MONTHS:
        path = ROOT / f"data/raw/fhvhv_tripdata_{month}.parquet"
        schema = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).df()
        names = set(schema["column_name"])
        schemas[month] = schema[["column_name", "column_type"]].to_dict("records")
        n = con.execute("SELECT count(*) FROM read_parquet(?)", [str(path)]).fetchone()[0]
        check(f"schema_{month}", REQUIRED <= names, {"missing": sorted(REQUIRED - names)})
        check(f"rows_{month}", n > 0, {"rows": n})
        if month.startswith("2025"):
            check(f"fee_column_{month}", "cbd_congestion_fee" in names, {})
        fee = "cbd_congestion_fee" if "cbd_congestion_fee" in names else "CAST(NULL AS DOUBLE)"
        frame = con.execute(f"""
          SELECT CAST(request_datetime AS DATE) AS request_date, count(*) AS trips,
                 SUM(CASE WHEN {fee} > 0 THEN 1 ELSE 0 END) AS fee_positive_trips,
                 SUM(CASE WHEN {fee} < 0 THEN 1 ELSE 0 END) AS fee_negative_trips,
                 SUM(CASE WHEN {fee} IS NULL THEN 1 ELSE 0 END) AS fee_null_trips,
                 min({fee}) AS min_fee, max({fee}) AS max_fee
          FROM read_parquet(?) GROUP BY request_date ORDER BY request_date
        """, [str(path)]).df()
        fee_counts = ["fee_positive_trips", "fee_negative_trips", "fee_null_trips"]
        frame[fee_counts] = frame[fee_counts].astype("int64")
        frame.insert(0, "source_month", month)
        fee_frames.append(frame)
        if "cbd_congestion_fee" in names:
            timing_row = con.execute("""
                SELECT SUM(CASE WHEN cbd_congestion_fee>0 AND request_datetime<TIMESTAMP '2025-01-05' THEN 1 ELSE 0 END) AS request_before_start,
                       SUM(CASE WHEN cbd_congestion_fee>0 AND pickup_datetime<TIMESTAMP '2025-01-05' THEN 1 ELSE 0 END) AS pickup_before_start,
                       SUM(CASE WHEN cbd_congestion_fee>0 AND dropoff_datetime<TIMESTAMP '2025-01-05' THEN 1 ELSE 0 END) AS ended_before_start,
                       SUM(CASE WHEN cbd_congestion_fee>0 AND dropoff_datetime IS NULL THEN 1 ELSE 0 END) AS positive_fee_missing_dropoff
                FROM read_parquet(?)
            """, [str(path)]).df()
            timing_row = timing_row.astype("int64")
            timing_row.insert(0, "source_month", month)
            timing.append(timing_row)
        inventory.append({"month": month, "rows": n, "bytes": path.stat().st_size,
                          "columns": len(names), "fee_column_present": "cbd_congestion_fee" in names,
                          "min_request_date": str(frame.request_date.min()),
                          "max_request_date": str(frame.request_date.max())})
        print(f"Validated {month}: {n:,} trips", flush=True)
    fees = pd.concat(fee_frames, ignore_index=True)
    timing_df = pd.concat(timing, ignore_index=True)
    timing_df.to_csv(ROOT / "data/processed/congestion_fee_start_date_checks.csv", index=False)
    before = timing_df.ended_before_start.sum()
    after = fees[fees.request_date >= pd.Timestamp("2025-01-05")].fee_positive_trips.sum()
    check("no_positive_fee_on_trips_ended_before_start", before == 0, {"positive_fee_trips": int(before),
          "time_basis": "dropoff_datetime < 2025-01-05 00:00 New York",
          "note": "Trips spanning midnight may have a fee; 2024 has no fee column"})
    check("positive_fee_has_dropoff", timing_df.positive_fee_missing_dropoff.sum() == 0, {})
    check("positive_fee_after_start", after > 0, {"positive_fee_trips": int(after)})
    fees.to_csv(ROOT / "data/processed/congestion_fee_by_request_date.csv", index=False)
    pd.DataFrame(inventory).to_csv(ROOT / "data/processed/trip_file_inventory.csv", index=False)
    (ROOT / "docs/trip_data_schema.json").write_text(json.dumps(schemas, indent=2) + "\n")
    zones = pd.read_csv(ROOT / "data/external/taxi_zone_lookup.csv")
    check("zone_unique_key", zones.LocationID.notna().all() and zones.LocationID.is_unique,
          {"rows": len(zones)})
    weather = pd.read_csv(ROOT / "data/external/weather_hourly.csv", parse_dates=["request_hour"])
    expected = pd.DatetimeIndex([])
    for _, start, end in MONTHS:
        expected = expected.append(pd.date_range(start, end + " 23:00:00", freq="h"))
    check("weather_exact_hour_grid", len(weather) == 2160 and weather.request_hour.is_unique
          and set(weather.request_hour) == set(expected), {"rows": len(weather), "expected": 2160})
    check("weather_non_null", weather.notna().all().all(), {"nulls": weather.isna().sum().to_dict()})
    check("weather_nonnegative", (weather[["rain_mm", "snowfall_cm"]] >= 0).all().all(), {})
    calendar = pd.read_csv(ROOT / "data/external/holidays.csv")
    required_dates = {"2024-01-15", "2025-01-20", "2025-02-17"}
    check("key_holidays_present", required_dates <= set(calendar.date),
          calendar[calendar.date.isin(required_dates)].to_dict("records"))
    check("holidays_unique", calendar.date.is_unique, {"rows": len(calendar)})
    valid = all(c["valid"] for c in checks)
    report = {"valid": valid, "checked_at_utc": utcnow(),
              "python": sys.version, "checks": checks, "inventory": inventory}
    (ROOT / "docs/source_data_validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    lines = ["# Dữ liệu nguồn - Báo cáo thực hiện", "",
             f"Thời điểm kiểm tra UTC: {report['checked_at_utc']}", "",
             "## Cách đã thực hiện", "",
             "1. Môi trường Python riêng; các thư viện được import thật.",
             "2. Tải nguyên file Parquet/zone và lưu manifest kèm SHA-256.",
             "3. Lấy thời tiết ERA5 theo giờ Central Park, giờ New York; giữ bản JSON API.",
             "4. Xuất lịch lễ Mỹ; DuckDB đọc schema, đếm chuyến và quét phí theo ngày.", "",
             "## Số dòng thực tế", "", "| Tháng | Chuyến | MB | Có cột phí |",
             "|---|---:|---:|---|"]
    for item in inventory:
        lines.append(f"| {item['month']} | {item['rows']:,} | {item['bytes']/1e6:.1f} | {item['fee_column_present']} |")
    lines += ["", f"Tổng chuyến raw: {sum(i['rows'] for i in inventory):,}.",
              f"Thời tiết: {len(weather):,} giờ; zone: {len(zones)} dòng; lịch lễ: {len(calendar)} ngày.",
              "", "## Kết quả kiểm tra", ""]
    for item in checks:
        lines.append(f"- {'Hợp lệ' if item['valid'] else 'Cần kiểm tra'} - {item['check']}: {json.dumps(item['details'], ensure_ascii=False)}")
    lines += ["", "## Giới hạn và bước tiếp", "",
              "Kiểm tra mốc phí dựa trên chuyến đã kết thúc trước 00:00 ngày 05/01. Request/pickup trước mốc không đủ kết luận lỗi nếu chuyến kéo dài qua mốc. Không quan sát được thời điểm đi qua ranh giới thu phí.",
              f"Chuyến có phí nhưng đặt trước mốc: {int(timing_df.request_before_start.sum()):,}; đón trước mốc: {int(timing_df.pickup_before_start.sum()):,}; kết thúc trước mốc: {int(before):,}. Chi tiết: congestion_fee_start_date_checks.csv.",
              "2024 không có cột phí: không sửa raw và không coi NULL là khoản phí đã đo bằng 0.",
              "Số raw gồm mọi hãng/dòng; chưa phải tập sạch Uber/Lyft. Bước làm sạch sẽ audit giờ ngoài tháng, lỗi metric và nhãn vùng.",
              "Thời tiết ERA5 là dữ liệu tái phân tích tại một điểm, không phải đo toàn thành phố hay forecast tại cutoff.",
              "Chưa ước tính tác động phí, credit hoặc dự báo; không dùng số minh họa trong deck.", ""]
    (ROOT / "docs/source_data_report.md").write_text("\n".join(lines))
    con.close()
    if not valid:
        failed = [item["check"] for item in checks if not item["valid"]]
        raise ValueError("Source inconsistencies: " + ", ".join(failed))
    print("Source data prepared. Inventory and diagnostics saved.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    for directory in ["data/raw", "data/external", "data/processed", "docs"]:
        (ROOT / directory).mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mpl-cache"))
    if not args.validate_only:
        prepare(json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {})
    validate()
