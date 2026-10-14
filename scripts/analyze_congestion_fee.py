"""Estimate relative growth gaps and check alternative zone/weather choices."""
from pathlib import Path
from datetime import datetime, timezone
import json
import math
import os
import duckdb
import pandas as pd


FEE_SAMPLE_SQL = """
CREATE OR REPLACE TEMP VIEW fee_sample AS
SELECT *
FROM clean_trips
WHERE request_date BETWEEN DATE '2024-01-08' AND DATE '2024-01-28'
   OR request_date BETWEEN DATE '2025-01-06' AND DATE '2025-01-26'
"""

FEE_LABEL_SQL = """
CREATE OR REPLACE TEMP VIEW fee_labeled_trips AS
SELECT t.*,
    CASE WHEN pu.LocationID IS NOT NULL OR do_zone.LocationID IS NOT NULL
         THEN true ELSE false END AS touches_zone,
    CASE WHEN valid_distance = true AND trip_miles < 2
         THEN true ELSE false END AS is_short_trip,
    CASE WHEN valid_fare = true AND base_passenger_fare <= {low_fare_threshold}
         THEN true ELSE false END AS is_low_fare_trip
FROM fee_sample t
LEFT JOIN fee_zones pu ON t.PULocationID = pu.LocationID
LEFT JOIN fee_zones do_zone ON t.DOLocationID = do_zone.LocationID
"""

FEE_DAILY_SQL = """
SELECT request_date, operator, touches_zone,
    COUNT(*) AS trips,
    SUM(CASE WHEN is_short_trip THEN 1 ELSE 0 END) AS short_trips,
    SUM(CASE WHEN is_low_fare_trip THEN 1 ELSE 0 END) AS low_fare_trips,
    SUM(CASE WHEN valid_fare THEN 1 ELSE 0 END) AS fare_sample_count,
    SUM(CASE WHEN valid_fare THEN base_passenger_fare END) AS fare_sample_sum,
    SUM(CASE WHEN is_short_trip AND valid_fare THEN 1 ELSE 0 END) AS short_fare_count,
    SUM(CASE WHEN is_short_trip AND valid_fare THEN base_passenger_fare END) AS short_fare_sum,
    SUM(CASE WHEN is_low_fare_trip THEN 1 ELSE 0 END) AS low_fare_count,
    SUM(CASE WHEN is_low_fare_trip THEN base_passenger_fare END) AS low_fare_sum
FROM fee_labeled_trips
GROUP BY request_date, operator, touches_zone
ORDER BY request_date, operator, touches_zone
"""


def describe_fee_windows(root):
    root = Path(root)
    hourly = pd.read_csv(root / "data/processed/hourly_city.csv", parse_dates=["request_date"])
    calendar = pd.read_csv(root / "data/external/holidays.csv", parse_dates=["date"])
    dates = []
    weather_rows = []
    for year, start, end in [(2024, "2024-01-08", "2024-01-28"), (2025, "2025-01-06", "2025-01-26")]:
        for day in pd.date_range(start, end):
            dates.append({"request_date": day, "year": year, "week_index": (day - pd.Timestamp(start)).days // 7,
                          "day_of_week": day.dayofweek, "is_holiday": day in set(calendar.date)})
        data = hourly[hourly.request_date.between(start, end)].copy()
        data["week_index"] = (data.request_date - pd.Timestamp(start)).dt.days // 7
        for week, group in data.groupby("week_index"):
            weather_rows.append({"year": year, "week_index": week,
                                 "start": group.request_date.min(), "end": group.request_date.max(),
                                 "rain_mm": group.rain_mm.sum(), "snowfall_cm": group.snowfall_cm.sum(),
                                 "rain_hours": int((group.rain_mm.gt(0) & group.snowfall_cm.eq(0)).sum()),
                                 "snow_hours": int(group.snowfall_cm.gt(0).sum()),
                                 "holiday_days": int(group.loc[group.is_holiday, "request_date"].nunique())})
    dates = pd.DataFrame(dates)
    weather = pd.DataFrame(weather_rows)
    pair_rain = weather.groupby("week_index").rain_mm.sum().sort_values(ascending=False, kind="stable")
    dropped_week = int(pair_rain.index[0])
    weather["dropped_in_weather_check"] = weather.week_index.eq(dropped_week)
    weather.to_csv(root / "data/processed/fee_comparison_week_weather.csv", index=False)
    dates.to_csv(root / "data/processed/fee_comparison_dates.csv", index=False)
    return dates, weather, dropped_week


def estimate_relative_growth(daily, dates, zone_threshold, zone_count, scenario):
    selected = daily.merge(dates, on="request_date", how="inner", validate="many_to_one")
    distribution = dates.groupby(["year", "day_of_week"]).size().unstack("year")
    if not distribution[2024].equals(distribution[2025]):
        raise ValueError("Comparison windows must have matching weekday counts.")
    holidays = dates.groupby("year").is_holiday.sum()
    count_columns = {"all_trips": ("trips", "fare_sample_count", "fare_sample_sum"),
                     "short_trips": ("short_trips", "short_fare_count", "short_fare_sum"),
                     "low_fare_trips": ("low_fare_trips", "low_fare_count", "low_fare_sum")}
    rows = []
    for operator in ["All", "Uber", "Lyft"]:
        data = selected if operator == "All" else selected[selected.operator.eq(operator)]
        for trip_group, (volume, fare_count, fare_sum) in count_columns.items():
            grouped = data.groupby(["year", "touches_zone"])[[volume, fare_count, fare_sum]].sum()
            a = float(grouped.loc[(2024, True), volume])
            b = float(grouped.loc[(2025, True), volume])
            c = float(grouped.loc[(2024, False), volume])
            d = float(grouped.loc[(2025, False), volume])
            if min(a, b, c, d) <= 0:
                raise ValueError("Each comparison cell must have positive volume.")
            zone_growth = b / a - 1
            outside_growth = d / c - 1
            counterfactual = a * d / c
            effect = b / counterfactual - 1
            trip_difference = b - counterfactual
            price_n = float(grouped.loc[(2024, True), fare_count])
            price_sum = float(grouped.loc[(2024, True), fare_sum])
            representative_fare = price_sum / price_n if price_n > 0 else float("nan")
            assumed_price_change = 1.5 / representative_fare if representative_fare > 0 else float("nan")
            elasticity_proxy = effect / assumed_price_change if assumed_price_change > 0 else float("nan")
            rows.append({"zone_threshold": zone_threshold, "zone_count": zone_count, "scenario": scenario,
                         "operator": operator, "trip_group": trip_group,
                         "days_per_year": int(dates.year.eq(2024).sum()),
                         "holiday_days_2024": int(holidays.loc[2024]), "holiday_days_2025": int(holidays.loc[2025]),
                         "holiday_balance_matches": holidays.loc[2024] == holidays.loc[2025],
                         "zone_trips_2024": int(a), "zone_trips_2025": int(b),
                         "outside_trips_2024": int(c), "outside_trips_2025": int(d),
                         "zone_growth": zone_growth, "outside_growth": outside_growth,
                         "growth_gap_percentage_points": 100 * (zone_growth - outside_growth),
                         "relative_growth_gap": effect, "counterfactual_zone_trips_2025": counterfactual,
                         "estimated_trip_difference": trip_difference,
                         "analysis_total_counterfactual_2025": counterfactual + d,
                         "scaled_total_gap": trip_difference / (counterfactual + d),
                         "representative_base_fare_2024": representative_fare,
                         "fare_sample_count_2024": int(price_n), "assumed_fee_usd": 1.5,
                         "assumed_price_increase": assumed_price_change,
                         "naive_elasticity_proxy": elasticity_proxy,
                         "elasticity_interpretation": "Illustrative ratio only; not identified causal price elasticity, especially for Lyft or pooled platforms"})
    return pd.DataFrame(rows)


def plot_fee_comparison(root, effect):
    root = Path(root)
    os.environ.setdefault("MPLCONFIGDIR", str(root / ".mpl-cache"))
    (root / "reports").mkdir(exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    sections = [(effect[effect.operator.eq("All")], "Trip groups | Uber + Lyft", "trip_group"),
                (effect[effect.trip_group.eq("all_trips")], "Platforms | All trips", "operator")]
    labels = {"all_trips": "All trips", "short_trips": "Short trips", "low_fare_trips": "Low-fare trips"}
    for ax, (data, title, name) in zip(axes, sections):
        values = data.relative_growth_gap.to_numpy() * 100
        ax.bar(range(len(data)), values, color=["#bf6d36" if v < 0 else "#167f78" for v in values])
        ax.axhline(0, color="#555555", linewidth=1)
        ax.set_xticks(range(len(data)), [labels.get(v, v) for v in data[name]])
        for i, value in enumerate(values):
            ax.text(i, value + (1 if value >= 0 else -1), f"{value:+.1f}%", ha="center",
                    va="bottom" if value >= 0 else "top", fontsize=10)
        ax.set_ylim(min(-5, min(values) - 6), max(5, max(values) + 6))
        ax.set_title(title)
        ax.set_ylabel("Relative growth gap (%)")
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Zone vs outside | Matched January weeks | 95% zone rule", fontsize=13)
    fig.savefig(root / "reports/congestion_fee_comparison.png", dpi=160)
    plt.close(fig)


def analyze_congestion_fee(root):
    root = Path(root).resolve()
    parameters = json.loads((root / "docs/trip_processing_parameters.json").read_text())
    threshold = float(parameters["low_fare_threshold_usd"])
    profile = pd.read_csv(root / "data/processed/zone_fee_profile.csv")
    dates, weather, dropped_week = describe_fee_windows(root)
    database = root / ".analysis-cache/trip_processing.duckdb"
    if not database.exists():
        raise FileNotFoundError("Run the preceding cleaning cells to create the analysis sample.")
    con = duckdb.connect(str(database))
    con.execute("SET threads=4")
    con.execute("SET memory_limit='2GB'")
    con.execute(FEE_SAMPLE_SQL)
    scenarios = []
    daily_frames = []
    for zone_threshold in [.90, .95, .99]:
        zones = profile.loc[profile.fee_rate.ge(zone_threshold), ["LocationID"]]
        if zones.empty or not zones.LocationID.is_unique:
            raise ValueError("Congestion-zone list must be nonempty and unique.")
        con.register("fee_zones", zones)
        label_query = FEE_LABEL_SQL.format(low_fare_threshold=repr(threshold))
        con.execute(label_query)
        daily = con.execute(FEE_DAILY_SQL).df()
        count_columns = ["trips", "short_trips", "low_fare_trips", "fare_sample_count", "short_fare_count", "low_fare_count"]
        daily[count_columns] = daily[count_columns].astype("int64")
        if zone_threshold == .95:
            previous = pd.read_csv(root / "data/processed/daily_segment.csv", parse_dates=["request_date"])
            previous = previous[previous.request_date.isin(dates.request_date)]
            keys = ["request_date", "operator", "touches_zone"]
            pd.testing.assert_frame_equal(daily.set_index(keys)[["trips", "short_trips", "low_fare_trips"]].sort_index(),
                                          previous.set_index(keys)[["trips", "short_trips", "low_fare_trips"]].sort_index(), check_dtype=False)
        daily_frames.append(daily.assign(zone_threshold=zone_threshold, zone_count=len(zones)))
        for scenario, chosen_dates in [("full_window", dates),
                                       ("drop_rainiest_matched_week", dates[dates.week_index.ne(dropped_week)])]:
            scenarios.append(estimate_relative_growth(daily, chosen_dates, zone_threshold, len(zones), scenario))
    con.close()
    sensitivity = pd.concat(scenarios, ignore_index=True)
    effect = sensitivity[sensitivity.zone_threshold.eq(.95) & sensitivity.scenario.eq("full_window")].copy()
    robust_rows = []
    for (operator, group), variants in sensitivity.groupby(["operator", "trip_group"], sort=False):
        base = float(effect[effect.operator.eq(operator) & effect.trip_group.eq(group)].relative_growth_gap.iloc[0])
        values = variants.relative_growth_gap
        same_direction = bool(values.gt(0).all()) if base > 0 else bool(values.lt(0).all()) if base < 0 else bool(values.abs().lt(1e-12).all())
        robust_rows.append({"operator": operator, "trip_group": group, "main_relative_gap": base,
                            "min_relative_gap": values.min(), "max_relative_gap": values.max(),
                            "variants": len(variants), "same_direction": same_direction,
                            "interpretation": "Direction stability only; not proof of causality or parallel trends"})
    robust = pd.DataFrame(robust_rows)
    effect.to_csv(root / "data/processed/fee_effect.csv", index=False)
    sensitivity.to_csv(root / "data/processed/fee_sensitivity.csv", index=False)
    robust.to_csv(root / "data/processed/fee_robustness_summary.csv", index=False)
    pd.concat(daily_frames, ignore_index=True).to_csv(root / "data/processed/fee_daily_counts_by_zone_rule.csv", index=False)
    for name, sql in [("select_fee_comparison_sample.sql", FEE_SAMPLE_SQL),
                      ("label_fee_comparison_trips.sql", label_query), ("aggregate_fee_comparison_days.sql", FEE_DAILY_SQL)]:
        (root / "sql" / name).write_text(sql.strip() + ";\n")
    spot = effect[effect.operator.eq("All") & effect.trip_group.eq("all_trips")].copy()
    r = spot.iloc[0]
    manual_cf = r.zone_trips_2024 * r.outside_trips_2025 / r.outside_trips_2024
    manual_effect = (r.zone_trips_2025 / r.zone_trips_2024) / (r.outside_trips_2025 / r.outside_trips_2024) - 1
    assert math.isclose(manual_cf, r.counterfactual_zone_trips_2025, rel_tol=1e-12)
    assert math.isclose(manual_effect, r.relative_growth_gap, rel_tol=1e-12)
    assert len(effect) == 9 and len(sensitivity) == 54
    assert effect.days_per_year.eq(21).all()
    assert sensitivity[sensitivity.scenario.eq("drop_rainiest_matched_week")].days_per_year.eq(14).all()
    assert sensitivity.holiday_balance_matches.all()
    spot.to_csv(root / "data/processed/fee_effect_spot_check.csv", index=False)
    plot_fee_comparison(root, effect)
    summary = {"completed_at_utc": datetime.now(timezone.utc).isoformat(),
               "reference_window": ["2024-01-08", "2024-01-28"], "comparison_window": ["2025-01-06", "2025-01-26"],
               "main_zone_threshold": .95, "low_fare_threshold_usd": threshold,
               "main_rows": len(effect), "sensitivity_rows": len(sensitivity),
               "rainiest_matched_week_index_removed": dropped_week,
               "weather_rule": "Maximum combined rain_mm in matched week pairs, selected without trip outcomes; remove corresponding seven-day block from each year",
               "all_trips_relative_gap": float(r.relative_growth_gap),
               "all_directions_stable": bool(robust.same_direction.all()),
               "elasticity": "Naive illustrative ratio, not an identified elasticity",
               "identification_limit": "Requires parallel growth absent policy and unaffected controls; neither is established with this short dataset"}
    (root / "docs/congestion_fee_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    write_fee_report(root, effect, robust, weather, spot, summary)
    print(f"Relative-growth comparison completed: {len(effect)} main estimates, {len(sensitivity)} sensitivity estimates.")
    return effect, sensitivity, robust, weather


def write_fee_report(root, effect, robust, weather, spot, summary):
    lines = ["# Phí vùng trung tâm và chênh lệch tăng trưởng", "",
             "## Phạm vi và phương pháp", "",
             "So 08-28/01/2024 với 06-26/01/2025: 21 ngày, cùng thứ, mỗi kỳ có một ngày MLK. Nhãn chạm vùng dùng endpoint; đối chứng là không chạm vùng. Ngưỡng chính 95%, kiểm tra 90%/99%. Mưa mùa hè không tham gia phép tính này.",
             "Counterfactual = chuyến trong vùng 2024 × (chuyến ngoài vùng 2025 / chuyến ngoài vùng 2024). Chênh lệch tương đối = chuyến trong vùng 2025 / counterfactual - 1. Đây là ratio-of-ratios, không phải hiệu hai tỷ lệ tăng trưởng tính bằng điểm phần trăm.",
             "", "## Kết quả chính", "", "| Hãng | Nhóm chuyến | Tăng trưởng chạm vùng | Tăng trưởng ngoài vùng | Chênh lệch tương đối | Chênh lệch chuyến phản thực |", "|---|---|---:|---:|---:|---:|"]
    for r in effect.itertuples(index=False):
        lines.append(f"| {r.operator} | {r.trip_group} | {r.zone_growth:+.2%} | {r.outside_growth:+.2%} | {r.relative_growth_gap:+.2%} | {r.estimated_trip_difference:+,.0f} |")
    r = spot.iloc[0]
    actual_total_growth = (r.zone_trips_2025 + r.outside_trips_2025) / (r.zone_trips_2024 + r.outside_trips_2024) - 1
    lines += ["", "## Tính tay một dòng", "",
              f"Tổng chuyến thực tế trong mẫu tăng {actual_total_growth:+.2%} so với cùng kỳ. Chênh lệch {r.relative_growth_gap:+.2%} dưới đây áp cho nhóm chạm vùng so với nhịp tăng của đối chứng, không phải toàn thị trường giảm từng đó.",
              f"Chạm vùng: {int(r.zone_trips_2024):,} → {int(r.zone_trips_2025):,}; ngoài vùng: {int(r.outside_trips_2024):,} → {int(r.outside_trips_2025):,}.",
              f"Nếu nhóm chạm vùng tăng cùng nhịp đối chứng: {int(r.zone_trips_2024):,} × {int(r.outside_trips_2025):,} / {int(r.outside_trips_2024):,} = {r.counterfactual_zone_trips_2025:,.2f} chuyến.",
              f"Thực tế / phản thực - 1 = {r.relative_growth_gap:.6f}, tức {r.relative_growth_gap:+.2%}. Chênh lệch {r.estimated_trip_difference:+,.2f} chuyến chỉ là ước tính dưới giả định đối chứng, không phải số chuyến mất đã quan sát trực tiếp.",
              "", "## Độ vững", "", "| Hãng | Nhóm | Khoảng chênh lệch qua 6 lựa chọn | Cùng chiều? |", "|---|---|---|---|"]
    for v in robust.itertuples(index=False):
        lines.append(f"| {v.operator} | {v.trip_group} | {v.min_relative_gap:+.2%} đến {v.max_relative_gap:+.2%} | {v.same_direction} |")
    dropped = weather[weather.dropped_in_weather_check]
    lines += ["", "Bỏ cặp tuần có tổng lượng mưa hai năm lớn nhất, cùng bảy thứ ở hai kỳ. Không chỉ bỏ tuần ở một năm. Các phương án đều giữ số ngày lễ bằng nhau trong dữ liệu hiện tại. Khoảng sensitivity không phải khoảng tin cậy thống kê.", ""]
    for v in dropped.itertuples(index=False):
        lines.append(f"- {v.year}: bỏ {v.start:%d/%m}–{v.end:%d/%m}, mưa {v.rain_mm:.1f} mm, tuyết {v.snowfall_cm:.2f} cm.")
    lines += ["", "## Độ nhạy giá: chỉ minh họa", "",
              "Lấy cước cơ bản trung bình dương của nhóm chạm vùng trong kỳ 2024, giả định giá tăng $1,50/cước đó, rồi chia chênh lệch tương đối cho tỷ lệ tăng giá. naive_elasticity_proxy được xuất để hiểu phép tính, không coi là độ nhạy giá nhân quả: cước không gồm mọi phí/thuế, giá động và mix chuyến thay đổi, Lyft có credit tương lai, đối chứng có thể bị ảnh hưởng.",
              "Nhóm giá thấp là nhóm theo ngưỡng cước cố định trong mỗi kỳ, không phải cùng khách hoặc cùng tuyến; cước tăng cũng làm chuyến chuyển ra khỏi nhóm. Chuyến ngắn và giá thấp có thể chồng lấn, không cộng các tác động nhóm.",
              "", "## Đối chiếu nghiên cứu", "",
              "Tóm tắt của Zhang, Sang & Wu (2026) trên Transportation Research Part A báo cáo giảm tổng ride-hailing khoảng 0,5–1,5%, Uber giảm tới 6% và Lyft tăng 2–5% trong kỳ credit; phản ứng tập trung ở chuyến ngắn/giá thấp. Họ dùng thiết kế two-way fixed effects. Nguồn: [tạp chí](https://www.sciencedirect.com/science/article/pii/S0965856426001072), DOI 10.1016/j.tra.2026.104966.",
              "Demo này chỉ đối chiếu tóm tắt công bố, không tái lập mô hình của nghiên cứu. Có điểm tương đồng về hướng khác nhau giữa hai hãng và nhóm giá thấp nhạy hơn, nhưng độ lớn khác rõ. Nhóm chạm vùng và mẫu số của ratio-of-ratios không đồng nhất với tổng ride-hailing nghiên cứu. scaled_total_gap quy đổi sang tổng mẫu phản thực dưới chính giả định demo, vẫn không phải ước lượng tương đương của nghiên cứu.",
              f"Dòng All/all_trips sau quy đổi theo tổng mẫu phản thực là {r.scaled_total_gap:+.2%}; vẫn khác khoảng công bố và không thể coi là so sánh cùng thiết kế.",
              "", "## Giới hạn và cách diễn giải", "",
              "- Cùng chiều qua sensitivity không xác nhận parallel trends. Dữ liệu trước sự kiện ngắn và cách so cùng kỳ không kiểm soát hết thay đổi giữa hai năm.",
              "- Nhóm ngoài vùng có chuyến xuyên vùng chịu phí; dòng kiểm tra fee_label_diagnostics.csv đã cho thấy sai khác nhãn. Đối chứng còn có thể chịu tác động chuyển hãng/chuyển điểm đón.",
              "- Kỳ so có mưa/tuyết khác nhau; chỉ bỏ một cặp tuần chưa kiểm soát đầy đủ thời tiết.",
              "- Lyft credit xảy ra cùng lúc; gộp hai hãng phản ánh nhiều thay đổi, tách Uber vẫn chưa loại cạnh tranh/chuyển hãng.",
              "- Chỉ đo chuyến hoàn thành của tập giữ lại, không đo mọi yêu cầu đặt xe hay booking bị hủy.",
              "- Cách viết phù hợp: nhóm chạm vùng tăng trưởng thấp hơn/cao hơn đối chứng X% trong cửa sổ này. Không viết phí chắc chắn làm mất X% chuyến hoặc dùng proxy elasticity để quyết định tăng giá.", ""]
    (root / "docs/congestion_fee_report.md").write_text("\n".join(lines))


if __name__ == "__main__":
    analyze_congestion_fee(Path(__file__).resolve().parents[1])
