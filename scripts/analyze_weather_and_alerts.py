"""Review weather coverage, measure observational ratios, and investigate alerts."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import math
import duckdb
import pandas as pd


WEATHER_FIELDS_SQL = """
CREATE OR REPLACE VIEW weather_trip_fields AS
SELECT
    request_datetime,
    CAST(request_datetime AS DATE) AS request_date,
    date_trunc('hour', request_datetime) AS request_hour,
    hvfhs_license_num,
    PULocationID,
    DOLocationID,
    date_diff('second', request_datetime, pickup_datetime) / 60.0 AS wait_minutes
FROM weather_raw_trips
"""

WEATHER_SAMPLE_SQL = """
CREATE OR REPLACE VIEW weather_sample AS
SELECT *,
    CASE WHEN wait_minutes BETWEEN 0 AND 60 THEN true ELSE false END AS valid_wait
FROM weather_trip_fields
WHERE request_datetime >= TIMESTAMP '{start}'
  AND request_datetime < TIMESTAMP '{end_exclusive}'
  AND hvfhs_license_num IN ('HV0003', 'HV0005')
  AND PULocationID IN (SELECT LocationID FROM known_zones)
  AND DOLocationID IN (SELECT LocationID FROM known_zones)
"""

WEATHER_HOURLY_SQL = """
SELECT request_hour,
    COUNT(*) AS trips,
    SUM(CASE WHEN valid_wait THEN 1 ELSE 0 END) AS valid_wait_trips,
    MEDIAN(CASE WHEN valid_wait THEN wait_minutes END) AS median_wait_minutes
FROM weather_sample
GROUP BY request_hour
ORDER BY request_hour
"""


def read_weather_json(path):
    payload = json.loads(Path(path).read_text())
    if payload.get("timezone") != "America/New_York":
        raise ValueError("Weather must use New York local time.")
    frame = pd.DataFrame(payload["hourly"]).rename(columns={
        "time": "request_hour", "temperature_2m": "temperature_c",
        "rain": "rain_mm", "snowfall": "snowfall_cm"})
    frame["request_hour"] = pd.to_datetime(frame.request_hour)
    if not frame.request_hour.is_unique or frame.isna().any().any():
        raise ValueError("Weather hours must be unique and complete.")
    return frame


def classify_weather(frame):
    frame = frame.sort_values("request_hour").copy()
    frame["weather_group"] = "dry"
    frame.loc[frame.rain_mm.gt(0), "weather_group"] = "drizzle"
    frame.loc[frame.rain_mm.between(.5, 2), "weather_group"] = "light_rain"
    frame.loc[frame.rain_mm.gt(2), "weather_group"] = "moderate_or_heavy_rain"
    frame.loc[frame.snowfall_cm.gt(0), "weather_group"] = "snow"
    wet = frame.rain_mm.gt(0) | frame.snowfall_cm.gt(0)
    gap = frame.request_hour.diff().ne(pd.Timedelta(hours=1))
    starts = wet & (gap | ~wet.shift(fill_value=False))
    frame["weather_event_id"] = starts.cumsum().where(wet).astype("Int64")
    frame["request_date"] = frame.request_hour.dt.normalize()
    frame["month"] = frame.request_hour.dt.month
    frame["year"] = frame.request_hour.dt.year
    frame["day_of_week"] = frame.request_hour.dt.dayofweek
    frame["hour"] = frame.request_hour.dt.hour
    return frame


def review_weather_coverage(root, download):
    root = Path(root)
    manifest_path = root / "data/external/source_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    annual = root / "data/external/weather_2024_full_year.json"
    download("https://archive-api.open-meteo.com/v1/archive", annual, manifest, params={
        "latitude": 40.7812, "longitude": -73.9665, "start_date": "2024-01-01",
        "end_date": "2024-12-31", "hourly": "temperature_2m,rain,snowfall",
        "timezone": "America/New_York", "models": "era5",
        "temperature_unit": "celsius", "precipitation_unit": "mm"})
    weather = classify_weather(read_weather_json(annual))
    holidays_frame = pd.read_csv(root / "data/external/holidays.csv", parse_dates=["date"])
    weather["is_holiday"] = weather.request_date.isin(holidays_frame.date)
    if len(weather) != 8784:
        raise ValueError("Expected a full leap year of hourly weather.")
    monthly_rows = []
    for month, group in weather.groupby("month"):
        usable = group[~group.is_holiday]
        heavy = usable[usable.weather_group.eq("moderate_or_heavy_rain")]
        monthly_rows.append({"month": f"2024-{month:02d}", "total_hours": len(group),
                             "dry_hours": int(usable.weather_group.eq("dry").sum()),
                             "light_rain_hours": int(usable.weather_group.eq("light_rain").sum()),
                             "heavy_rain_hours": len(heavy),
                             "heavy_rain_events": int(heavy.weather_event_id.nunique()),
                             "heavy_rain_days": int(heavy.request_date.nunique()),
                             "snow_hours": int(usable.weather_group.eq("snow").sum())})
    monthly = pd.DataFrame(monthly_rows)
    windows = []
    for start_month in range(1, 11):
        usable = weather[weather.month.between(start_month, start_month + 2) & ~weather.is_holiday]
        heavy = usable[usable.weather_group.eq("moderate_or_heavy_rain")]
        windows.append({"start_month": start_month, "end_month": start_month + 2,
                        "start": f"2024-{start_month:02d}-01",
                        "end": str(pd.Period(f"2024-{start_month + 2:02d}", freq="M").end_time.date()),
                        "heavy_rain_hours": len(heavy),
                        "heavy_rain_events": int(heavy.weather_event_id.nunique()),
                        "heavy_rain_days": int(heavy.request_date.nunique()),
                        "enough_hours": len(heavy) >= 20})
    windows = pd.DataFrame(windows)
    candidates = windows[windows.enough_hours].sort_values(
        ["heavy_rain_events", "heavy_rain_hours", "start_month"], ascending=[False, False, True])
    if candidates.empty:
        raise ValueError("No three-month window meets the weather coverage rule.")
    selected = candidates.iloc[0]
    selection = {"selected_before_trip_analysis": True, "start": selected.start, "end": selected.end,
                 "months": [f"2024-{m:02d}" for m in range(int(selected.start_month), int(selected.end_month) + 1)],
                 "heavy_rain_hours": int(selected.heavy_rain_hours),
                 "heavy_rain_events": int(selected.heavy_rain_events),
                 "selection_rule": "Contiguous three-month windows with >=20 non-holiday heavy-rain hours; maximize distinct wet events, then hours; no trip outcomes used",
                 "event_definition": "Contiguous hours with rain>0 or snowfall>0; heavy hours may belong to the same wet event",
                 "season_limit": "Summer estimates are not directly transferred to February planning"}
    monthly.to_csv(root / "data/processed/weather_coverage_by_month.csv", index=False)
    windows.to_csv(root / "data/processed/weather_window_comparison.csv", index=False)
    (root / "docs/weather_window_selection.json").write_text(json.dumps(selection, indent=2, ensure_ascii=False) + "\n")
    return monthly, windows, selection


def build_weather_study(root, download, selection):
    root = Path(root)
    (root / "data/weather_raw").mkdir(exist_ok=True)
    manifest_path = root / "data/external/source_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    files, weather_frames = [], []
    for month in selection["months"]:
        path = root / f"data/weather_raw/fhvhv_tripdata_{month}.parquet"
        download(f"https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_{month}.parquet", path, manifest)
        weather_path = root / f"data/external/weather_{month}.json"
        end = str(pd.Period(month, freq="M").end_time.date())
        download("https://archive-api.open-meteo.com/v1/archive", weather_path, manifest, params={
            "latitude": 40.7812, "longitude": -73.9665, "start_date": month + "-01", "end_date": end,
            "hourly": "temperature_2m,rain,snowfall", "timezone": "America/New_York",
            "models": "era5", "temperature_unit": "celsius", "precipitation_unit": "mm"})
        files.append(str(path))
        weather_frames.append(read_weather_json(weather_path))
    zones = pd.read_csv(root / "data/external/taxi_zone_lookup.csv")
    known_zones = zones[zones.LocationID.ne(264)][["LocationID"]]
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='2GB'")
    spill = str(root / ".analysis-cache/weather_spill").replace("'", "''")
    con.execute(f"SET temp_directory='{spill}'")
    con.read_parquet(files, union_by_name=True).create_view("weather_raw_trips")
    con.register("known_zones", known_zones)
    con.execute(WEATHER_FIELDS_SQL)
    end_exclusive = str((pd.Timestamp(selection["end"]) + pd.Timedelta(days=1)).date())
    sample_sql = WEATHER_SAMPLE_SQL.format(start=selection["start"], end_exclusive=end_exclusive)
    con.execute(sample_sql)
    hourly = con.execute(WEATHER_HOURLY_SQL).df()
    hourly.valid_wait_trips = hourly.valid_wait_trips.astype("int64")
    weather = pd.concat(weather_frames, ignore_index=True)
    hourly = hourly.merge(weather, on="request_hour", how="outer", validate="one_to_one")
    expected_hours = len(pd.date_range(selection["start"], selection["end"] + " 23:00", freq="h"))
    if len(hourly) != expected_hours or hourly[["trips", "rain_mm", "snowfall_cm"]].isna().any().any():
        raise ValueError("Weather-study hourly coverage is incomplete; do not fill missing sources with zero.")
    con.close()
    hourly = classify_weather(hourly)
    calendar = pd.read_csv(root / "data/external/holidays.csv", parse_dates=["date"])
    hourly["is_holiday"] = hourly.request_date.isin(calendar.date)
    hourly.to_csv(root / "data/processed/weather_study_hourly.csv", index=False)
    for name, sql in [("prepare_weather_trip_fields.sql", WEATHER_FIELDS_SQL),
                      ("select_weather_trip_sample.sql", sample_sql), ("aggregate_weather_hours.sql", WEATHER_HOURLY_SQL)]:
        (root / "sql" / name).write_text(sql.strip() + ";\n")
    return hourly


def calculate_weather_factors(root, summer):
    root = Path(root)
    winter = pd.read_csv(root / "data/processed/hourly_city.csv", parse_dates=["request_hour"])
    winter = classify_weather(winter)
    frames = []
    summaries = []
    for study, data in [("summer_2024", summer), ("winter_2024", winter[winter.year.eq(2024)]),
                        ("winter_2025", winter[winter.year.eq(2025)])]:
        data = data.copy()
        dry = data[data.weather_group.eq("dry") & ~data.is_holiday]
        keys = ["year", "month", "day_of_week", "hour"]
        baselines = dry.groupby(keys).agg(dry_trips=("trips", "median"), dry_wait=("median_wait_minutes", "median"),
                                         dry_hours=("trips", "count"), dry_wait_hours=("median_wait_minutes", "count")).reset_index()
        data = data.merge(baselines, on=keys, how="left", validate="many_to_one")
        eligible = ~data.is_holiday & ~data.weather_group.eq("drizzle")
        data["trips_factor"] = (data.trips / data.dry_trips).where(eligible & data.dry_trips.gt(0))
        data["wait_factor"] = (data.median_wait_minutes / data.dry_wait).where(eligible & data.dry_wait.gt(0))
        data["study"] = study
        frames.append(data)
        for group, hours in data.groupby("weather_group"):
            used = hours[hours.trips_factor.notna()]
            wait_used = hours[hours.wait_factor.notna()]
            wet_used = used[used.weather_group.ne("dry")]
            summaries.append({"study": study, "weather_group": group, "observed_hours": len(hours),
                              "usable_trip_hours": len(used), "usable_wait_hours": len(wait_used),
                              "usable_days": int(used.request_date.nunique()),
                              "wet_events": int(wet_used.weather_event_id.nunique()),
                              "trips_factor": used.trips_factor.median(), "wait_factor": wait_used.wait_factor.median(),
                              "min_dry_reference_hours": used.dry_hours.min(),
                              "trip_sample_under_20_hours": len(used) < 20,
                              "wait_sample_under_20_hours": len(wait_used) < 20,
                              "excluded_holiday_hours": int(hours.is_holiday.sum())})
    ratios = pd.concat(frames, ignore_index=True)
    factors = pd.DataFrame(summaries)
    ratios.to_csv(root / "data/processed/weather_hourly_factors.csv", index=False)
    factors.to_csv(root / "data/processed/rain_factors.csv", index=False)
    spot_candidates = ratios[ratios.study.eq("summer_2024") & ratios.weather_group.eq("moderate_or_heavy_rain") & ratios.trips_factor.notna()]
    if spot_candidates.empty:
        raise ValueError("No matched heavy-rain hour in the chosen study.")
    spot = spot_candidates.head(1).copy()
    r = spot.iloc[0]
    assert math.isclose(r.trips_factor, r.trips / r.dry_trips, rel_tol=1e-12)
    matched = ratios[ratios.study.eq(r.study) & ratios.year.eq(r.year) & ratios.month.eq(r.month)
                     & ratios.day_of_week.eq(r.day_of_week) & ratios.hour.eq(r.hour)
                     & ratios.weather_group.eq("dry") & ~ratios.is_holiday]
    assert math.isclose(r.dry_trips, matched.trips.median(), rel_tol=1e-12)
    assert not ratios.loc[ratios.is_holiday | ratios.weather_group.eq("drizzle"), "trips_factor"].notna().any()
    assert not ratios.loc[ratios.is_holiday | ratios.weather_group.eq("drizzle"), "wait_factor"].notna().any()
    spot.to_csv(root / "data/processed/weather_factor_spot_check.csv", index=False)
    return factors, ratios


def build_demand_watchlist(root):
    root = Path(root)
    daily = pd.read_csv(root / "data/processed/daily_segment.csv", parse_dates=["request_date"])
    hourly = pd.read_csv(root / "data/processed/hourly_city.csv", parse_dates=["request_date"])
    hourly["rain_hour"] = hourly.rain_mm.gt(0) & hourly.snowfall_cm.eq(0)
    hourly["snow_hour"] = hourly.snowfall_cm.gt(0)
    weather = hourly.groupby("request_date").agg(rain_hours=("rain_hour", "sum"), snow_hours=("snow_hour", "sum"),
                                                  rain_mm_total=("rain_mm", "sum"), min_temperature_c=("temperature_c", "min"))
    lookup = daily.set_index(["request_date", "operator", "touches_zone"])
    rows = []
    for r in daily.itertuples(index=False):
        previous_keys = [(r.request_date - pd.Timedelta(days=n), r.operator, r.touches_zone) for n in [7, 14]]
        if all(key in lookup.index for key in previous_keys):
            references = [lookup.loc[key] for key in previous_keys]
            reference_dates = [key[0] for key in previous_keys]
            baseline_method = "previous_two_same_weekdays"
        else:
            key = (r.request_date - pd.Timedelta(days=364), r.operator, r.touches_zone)
            references = [lookup.loc[key]] if key in lookup.index else []
            reference_dates = [key[0]] if references else []
            baseline_method = "same_weekday_previous_year" if references else "unavailable"
        expected_trips = sum(x.trips for x in references) / len(references) if references else float("nan")
        waits = [x.median_wait_minutes for x in references if pd.notna(x.median_wait_minutes)]
        expected_wait = sum(waits) / len(waits) if len(waits) == len(references) and waits else float("nan")
        trips_delta = r.trips / expected_trips - 1 if expected_trips > 0 else float("nan")
        wait_delta = r.median_wait_minutes / expected_wait - 1 if expected_wait > 0 else float("nan")
        w = weather.loc[r.request_date]
        fare_missing = (r.trips - r.valid_fare_trips) / r.trips
        wait_missing = (r.trips - r.valid_wait_trips) / r.trips
        reference_holiday = any(x.is_holiday for x in references)
        triggers = []
        if abs(trips_delta) > .07:
            triggers.append("trips")
        if abs(wait_delta) > .20:
            triggers.append("wait")
        if fare_missing > .05 or wait_missing > .05:
            hypothesis = "metric_sample_quality"
            next_step = "Rà nguồn cước/chờ; giữ volume, không dùng giá thiếu mẫu để gán nguyên nhân."
        elif reference_holiday:
            hypothesis = "holiday_in_baseline"
            next_step = "So lại với ngày thường cùng thứ; baseline có lễ nên không coi chênh lệch là tác động mới."
        elif r.is_holiday:
            hypothesis = "holiday_context"
            next_step = "So cả bốn phân khúc và ngày lễ năm trước; kiểm tra thời tiết trước khi gán nguyên nhân."
        elif w.rain_hours > 0 or w.snow_hours > 0:
            hypothesis = "weather_context"
            next_step = "So giờ khô cùng tháng/thứ/giờ và thời tiết các ngày baseline; chưa suy ra thiếu tài xế."
        else:
            hypothesis = "unexplained_or_market_change"
            next_step = "Rà xu hướng hai hãng/nhãn vùng, giá và dữ liệu nguồn; chưa gán tác động cho phí hoặc credit."
        evidence = (f"Chuyến {trips_delta:+.1%}; chờ {wait_delta:+.1%}; cước không thuộc mẫu {fare_missing:.1%}; "
                    f"mưa {int(w.rain_hours)} giờ, tuyết {int(w.snow_hours)} giờ; "
                    f"lễ hiện tại={r.is_holiday}, lễ trong baseline={reference_holiday}.")
        rows.append({"request_date": r.request_date, "operator": r.operator, "touches_zone": r.touches_zone,
                     "trips": r.trips, "median_wait_minutes": r.median_wait_minutes,
                     "expected_trips": expected_trips, "expected_wait_minutes": expected_wait,
                     "trips_deviation": trips_delta, "wait_deviation": wait_delta, "baseline_method": baseline_method,
                     "baseline_dates": ",".join(str(d.date()) for d in reference_dates),
                     "baseline_contains_holiday": reference_holiday, "is_holiday": r.is_holiday,
                     "rain_hours": int(w.rain_hours), "snow_hours": int(w.snow_hours),
                     "fare_excluded_share": fare_missing, "wait_excluded_share": wait_missing,
                     "alert": bool(triggers), "trigger": ",".join(triggers), "possible_cause": hypothesis,
                     "evidence": evidence, "next_step": next_step, "investigation_status": "needs_follow_up"})
    monitoring = pd.DataFrame(rows)
    alert_mask = monitoring.alert
    cases = []
    for date, operator, touches, finding in [
        ("2025-01-20", "Lyft", False, "Có ngày lễ MLK nhưng biến động không đồng đều giữa hãng/nhãn vùng. Ngày lễ là bối cảnh, chưa đủ giải thích riêng sự giảm của Lyft ngoài vùng."),
        ("2025-01-21", "Lyft", True, "Chuyến tăng đồng thời nhiều cước không thuộc mẫu dương. Đã đối chiếu với raw; giữ volume, không dùng trung bình giá bị mất mẫu để suy ra hiệu quả credit.")]:
        mask = monitoring.request_date.eq(pd.Timestamp(date)) & monitoring.operator.eq(operator) & monitoring.touches_zone.eq(touches) & alert_mask
        if mask.any():
            case = monitoring.loc[mask].iloc[0].to_dict()
            case["finding"] = finding
            case["investigation_status"] = "reviewed_with_limitations"
            cases.append(case)
            monitoring.loc[mask, "investigation_status"] = "reviewed_with_limitations"
    if len(cases) < 2:
        raise ValueError("Expected cases did not trigger; review actual alerts instead of manufacturing evidence.")
    monitoring.to_csv(root / "data/processed/demand_monitoring.csv", index=False)
    watchlist = monitoring[monitoring.alert].copy()
    watchlist.to_csv(root / "data/processed/watchlist.csv", index=False)
    investigations = pd.DataFrame(cases)
    investigations.to_csv(root / "data/processed/alert_investigations.csv", index=False)
    comparisons = monitoring[monitoring.request_date.isin(investigations.request_date)].copy()
    comparisons.to_csv(root / "data/processed/alert_case_comparison.csv", index=False)
    assert monitoring.loc[monitoring.baseline_method.eq("unavailable"), "alert"].eq(False).all()
    for r in monitoring.itertuples(index=False):
        for date in r.baseline_dates.split(","):
            if date:
                assert pd.Timestamp(date) < r.request_date
    return monitoring, watchlist, investigations


def plot_weather_factors(root, factors):
    root = Path(root)
    os.environ.setdefault("MPLCONFIGDIR", str(root / ".mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    data = factors[factors.study.eq("summer_2024") & factors.weather_group.isin(["light_rain", "moderate_or_heavy_rain"])]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    colors = ["#157f78", "#d78335"]
    for ax, metric, title, samples in zip(axes, ["trips_factor", "wait_factor"],
                                        ["Completed trips", "Waiting time"], ["usable_trip_hours", "usable_wait_hours"]):
        for i, r in enumerate(data.itertuples(index=False)):
            value = getattr(r, metric)
            if pd.notna(value):
                ax.bar(i, value, color=colors[i])
                ax.text(i, value + .03, f"{value:.2f}x\nn={getattr(r, samples)} hours", ha="center", fontsize=10)
        ax.axhline(1, color="#555555", linestyle="--", linewidth=1)
        ax.set_xticks(range(len(data)), ["Light rain\n0.5-2 mm/h", "Rain >2 mm/h"])
        ax.set_title(title)
        ax.set_ylabel("Ratio to matched dry hours")
        ax.set_ylim(0, max(1.5, float(data[metric].max()) + .3))
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("NYC Uber + Lyft | Jun-Aug 2024 | Holidays excluded", fontsize=13)
    (root / "reports").mkdir(exist_ok=True)
    fig.savefig(root / "reports/rain_factors.png", dpi=160)
    plt.close(fig)


def analyze_weather_and_alerts(root, download):
    root = Path(root)
    monthly, windows, selection = review_weather_coverage(root, download)
    summer = build_weather_study(root, download, selection)
    factors, ratios = calculate_weather_factors(root, summer)
    monitoring, watchlist, investigations = build_demand_watchlist(root)
    plot_weather_factors(root, factors)
    summary = {"completed_at_utc": datetime.now(timezone.utc).isoformat(), "weather_selection": selection,
               "summer_hourly_rows": len(summer), "summer_completed_trips": int(summer.trips.sum()),
               "baseline": "Dry non-holiday hours within the same year/month/weekday/hour; median trips and hourly median waits",
               "core_monitoring_rows": len(monitoring), "alert_rows": len(watchlist),
               "alert_dates": int(watchlist.request_date.nunique()),
               "missing_baseline_rows": int(monitoring.baseline_method.eq("unavailable").sum()),
               "reviewed_cases": len(investigations), "trips_alert_threshold": .07, "wait_alert_threshold": .20,
               "interpretation": "Descriptive associations, not causal effects; summer factors not transferred directly to February forecasts"}
    (root / "docs/weather_analysis_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    lines = ["# Thời tiết và theo dõi biến động", "",
             "## Chọn khoảng dữ liệu", "",
             f"Rà {8784:,} giờ thời tiết 2024 trước khi phân tích chuyến. Cửa sổ {selection['start']} đến {selection['end']} có {selection['heavy_rain_hours']} giờ mưa >2 mm/giờ thuộc {selection['heavy_rain_events']} đợt ẩm liên tục sau khi bỏ ngày lễ. Chọn theo số đợt, không theo kết quả chuyến.",
             f"Dữ liệu bổ sung chỉ cho mưa: {int(summer.trips.sum()):,} chuyến, {len(summer):,} giờ. Phí/credit/dự báo và watchlist giữ phạm vi ban đầu.",
             "", "## Cách tính", "",
             "Ưu tiên tuyết khi snowfall>0. Khô: rain=0 và không tuyết; mưa nhỏ 0<rain<0,5 bỏ khỏi hệ số; nhẹ 0,5-2; vừa trở lên >2. Mỗi giờ chia cho trung vị giờ khô cùng tháng/năm/thứ/giờ, bỏ lễ ở cả mẫu khô và mẫu thời tiết. Hệ số nhóm là median các tỷ số giờ.",
             "", "## Hệ số quan sát", "", "| Mẫu | Thời tiết | Giờ dùng | Ngày | Đợt | Chuyến | Chờ |", "|---|---|---:|---:|---:|---:|---:|"]
    for r in factors[~factors.weather_group.isin(["dry", "drizzle"])].itertuples(index=False):
        lines.append(f"| {r.study} | {r.weather_group} | {r.usable_trip_hours} | {r.usable_days} | {r.wet_events} | {r.trips_factor:.3f} | {r.wait_factor:.3f} |")
    lines += ["", "Nhóm dưới 20 giờ được đánh dấu ít mẫu trong rain_factors.csv. Số giờ không phải số quan sát độc lập; xem cả số ngày/đợt. Dry reference ít giờ được lưu ở từng dòng, không giấu độ thưa.",
              "", "## Theo dõi và điều tra", "",
              f"{len(monitoring)} dòng ngày/phân khúc; {len(watchlist)} cảnh báo trên {summary['alert_dates']} ngày; {summary['missing_baseline_rows']} dòng thiếu baseline không được gán số 0 hoặc tạo cảnh báo.",
              "Kỳ vọng là trung bình cùng thứ của D-7 và D-14. Thiếu cả bộ hai ngày thì dùng cùng thứ năm trước D-364 khi có; thiếu tiếp thì để NULL. Cảnh báo |lệch chuyến|>7% hoặc |lệch chờ|>20%. Baseline có lễ được ghi riêng.", ""]
    for r in investigations.itertuples(index=False):
        lines += [f"### {r.request_date:%Y-%m-%d} - {r.operator}, chạm vùng={r.touches_zone}", "", r.evidence, "", r.finding, "", "Bước tiếp: " + r.next_step, ""]
    lines += ["## Giới hạn sử dụng", "",
              "- Mưa mùa hè không dùng trực tiếp để điều chỉnh nhu cầu tháng 02. Tuyết được đọc riêng trong mẫu mùa đông.",
              "- Hệ số là liên hệ quan sát với chuyến hoàn thành, không đo toàn bộ booking demand hoặc quan hệ nhân quả.",
              "- Baseline có ít giờ khô, sự kiện đặc biệt và nhiệt độ có thể ảnh hưởng kết quả; chưa có mô hình kiểm soát đầy đủ.",
              "- Chờ tăng không chứng minh tài xế ít đi. Không có số tài xế hoạt động.",
              "- Weather factors dùng toàn bộ cửa sổ hồi cứu. Nếu dùng trong forecast, phải ước tính lại chỉ với dữ liệu có trước cutoff.",
              "- Hai case đã rà với giới hạn; nguyên nhân cuối cùng chưa được chứng minh. Các cảnh báo khác đều có evidence và next_step, không tự ghi đã xử lý xong.", ""]
    (root / "docs/weather_and_alerts_report.md").write_text("\n".join(lines))
    print(f"Weather study completed: {len(summer)} hourly records; {len(watchlist)} alerts; {len(investigations)} reviewed cases.")
    return factors, ratios, monitoring, watchlist, investigations


if __name__ == "__main__":
    from prepare_source_data import download
    analyze_weather_and_alerts(Path(__file__).resolve().parents[1], download)
