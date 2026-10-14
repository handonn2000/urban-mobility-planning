"""Freeze a cutoff-safe holiday-week forecast before retrospective scoring."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import duckdb
import pandas as pd


FORECAST_HISTORY_SQL = """
CREATE OR REPLACE TEMP VIEW forecast_source AS
SELECT r.request_datetime, r.dropoff_datetime,
    CAST(r.request_datetime AS DATE) AS request_date,
    CASE WHEN r.hvfhs_license_num = 'HV0003' THEN 'Uber'
         WHEN r.hvfhs_license_num = 'HV0005' THEN 'Lyft' END AS operator,
    CASE WHEN crz_pu.LocationID IS NOT NULL OR crz_do.LocationID IS NOT NULL
         THEN true ELSE false END AS touches_zone
FROM forecast_raw r
JOIN known_zones pu ON r.PULocationID = pu.LocationID
JOIN known_zones do_zone ON r.DOLocationID = do_zone.LocationID
LEFT JOIN forecast_zones crz_pu ON r.PULocationID = crz_pu.LocationID
LEFT JOIN forecast_zones crz_do ON r.DOLocationID = crz_do.LocationID
WHERE r.request_datetime >= TIMESTAMP '2025-01-01'
  AND r.request_datetime < TIMESTAMP '2025-02-17'
  AND r.hvfhs_license_num IN ('HV0003', 'HV0005')
"""


def prepare_forecast_history(root):
    root = Path(root)
    cutoff = pd.Timestamp("2025-02-16")
    end_exclusive = pd.Timestamp("2025-02-17")
    daily = pd.read_csv(root / "data/processed/daily_segment.csv", parse_dates=["request_date"])
    expected = daily[daily.request_date.between("2025-01-01", cutoff)].copy()
    keys = ["request_date", "operator", "touches_zone"]
    grid = pd.MultiIndex.from_product([pd.date_range("2025-01-01", cutoff), ["Uber", "Lyft"], [False, True]], names=keys)
    actual_keys = pd.MultiIndex.from_frame(expected[keys])
    if actual_keys.has_duplicates or len(grid.difference(actual_keys)) or len(expected) != len(grid) or not expected.data_available.all():
        raise ValueError("Forecast history needs complete observed source coverage.")
    parameters = json.loads((root / "docs/trip_processing_parameters.json").read_text())
    if max(pd.Timestamp(x) for x in parameters["zone_inference_dates"]) > cutoff:
        raise ValueError("Forecast zone calibration extends beyond cutoff.")
    zones = pd.read_csv(root / "data/external/taxi_zone_lookup.csv")
    calendar = pd.read_csv(root / "data/external/holidays.csv", parse_dates=["date"])
    if not {pd.Timestamp("2025-01-20"), pd.Timestamp("2025-02-17")}.issubset(set(calendar.date)):
        raise ValueError("The planned MLK and Presidents' Day dates are missing from the holiday calendar.")
    crz = pd.read_csv(root / "data/processed/crz_zones.csv")
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='2GB'")
    con.execute("SET temp_directory='" + str(root / ".analysis-cache/forecast_spill").replace("'", "''") + "'")
    files = [str(root / f"data/raw/fhvhv_tripdata_{month}.parquet") for month in ["2025-01", "2025-02"]]
    con.read_parquet(files, union_by_name=True).create_view("forecast_raw")
    con.register("known_zones", zones.loc[zones.LocationID.ne(264), ["LocationID"]])
    con.register("forecast_zones", crz[["LocationID"]])
    con.execute(FORECAST_HISTORY_SQL)
    history = con.execute("""
        SELECT request_date, operator, touches_zone, COUNT(*) AS trips
        FROM forecast_source
        WHERE dropoff_datetime < TIMESTAMP '2025-02-17'
        GROUP BY request_date, operator, touches_zone
        ORDER BY request_date, operator, touches_zone
    """).df()
    deferred = con.execute("""
        SELECT request_date, operator, touches_zone,
            SUM(CASE WHEN dropoff_datetime >= TIMESTAMP '2025-02-17' THEN 1 ELSE 0 END) AS completed_after_cutoff,
            SUM(CASE WHEN dropoff_datetime IS NULL THEN 1 ELSE 0 END) AS completion_time_missing
        FROM forecast_source
        GROUP BY request_date, operator, touches_zone
    """).df()
    latest = con.execute("""
        SELECT MAX(request_datetime) AS latest_request, MAX(dropoff_datetime) AS latest_completion
        FROM forecast_source WHERE dropoff_datetime < TIMESTAMP '2025-02-17'
    """).df().iloc[0]
    con.close()
    history = expected[keys].merge(history, on=keys, how="left", validate="one_to_one")
    history["trips"] = history.trips.fillna(0).astype("int64")
    history["cutoff_date"] = cutoff
    reconciliation = expected[keys + ["trips"]].rename(columns={"trips": "final_retrospective_trips"}).merge(
        history[keys + ["trips"]].rename(columns={"trips": "known_completed_trips"}), on=keys, validate="one_to_one").merge(deferred, on=keys, validate="one_to_one")
    reconciliation["difference"] = reconciliation.final_retrospective_trips - reconciliation.known_completed_trips
    if not reconciliation.difference.eq(reconciliation.completed_after_cutoff + reconciliation.completion_time_missing).all():
        raise ValueError("Cutoff reconstruction does not reconcile with final daily counts.")
    if pd.Timestamp(latest.latest_request) >= end_exclusive or pd.Timestamp(latest.latest_completion) >= end_exclusive:
        raise ValueError("History contains a request or completion after cutoff.")
    history.to_csv(root / "data/processed/forecast_history.csv", index=False)
    reconciliation.to_csv(root / "data/processed/forecast_cutoff_reconciliation.csv", index=False)
    provenance = {"cutoff_date": "2025-02-16", "cutoff_timezone": "America/New_York",
                  "end_exclusive": "2025-02-17T00:00:00", "latest_request": str(latest.latest_request),
                  "latest_completion": str(latest.latest_completion), "history_rows": len(history),
                  "zone_calibration_dates": parameters["zone_inference_dates"],
                  "known_calendar_dates": ["2025-01-20", "2025-02-17"],
                  "calendar_note": "Scheduled holiday dates can be known before cutoff; they are not future trip or weather observations.",
                  "completed_after_cutoff_excluded": int(reconciliation.completed_after_cutoff.sum()),
                  "completion_time_missing_excluded": int(reconciliation.completion_time_missing.sum()),
                  "availability_assumption": "Historical simulation assumes trip records and the static zone lookup are accessible at cutoff. TLC monthly releases are retrospective, not a live feed.",
                  "unused_inputs": ["credit uplift", "weather factors", "future weather observations", "backtest scores", "fare thresholds"]}
    (root / "docs/forecast_input_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    (root / "sql/reconstruct_forecast_history.sql").write_text(FORECAST_HISTORY_SQL.strip() + ";\n")
    return history, provenance


def build_holiday_forecasts(history):
    cutoff = pd.Timestamp("2025-02-16")
    history = history[history.request_date.le(cutoff)].copy()
    keys = ["request_date", "operator", "touches_zone"]
    if history.duplicated(keys).any() or history.trips.isna().any() or (history.trips < 0).any():
        raise ValueError("Forecast history must have unique keys and nonnegative observed trips.")
    counts = history.set_index(keys).trips
    rows, factors, lineage = [], [], []
    for operator in ["Uber", "Lyft"]:
        for touches in [False, True]:
            def observed(date):
                key = (pd.Timestamp(date), operator, touches)
                if key not in counts.index:
                    raise ValueError(f"Missing forecast reference: {key}")
                return float(counts.loc[key])
            mlk, before, after = [observed(date) for date in ["2025-01-20", "2025-01-13", "2025-01-27"]]
            reference = (before + after) / 2
            if reference <= 0:
                raise ValueError("Holiday factor requires a positive reference volume.")
            factor = mlk / reference
            factors.append({"operator": operator, "touches_zone": touches, "holiday_date": "2025-01-20",
                            "reference_before": "2025-01-13", "reference_after": "2025-01-27",
                            "holiday_trips": mlk, "before_trips": before, "after_trips": after,
                            "reference_trips": reference, "holiday_factor": factor, "cutoff_date": "2025-02-16"})
            for date in pd.date_range("2025-02-17", "2025-02-23"):
                d7, d14 = date - pd.Timedelta(days=7), date - pd.Timedelta(days=14)
                b1 = observed(d7)
                b2 = (b1 + observed(d14)) / 2
                applied = factor if date == pd.Timestamp("2025-02-17") else 1.0
                rows.append({"request_date": date, "operator": operator, "touches_zone": touches,
                             "cutoff_date": cutoff, "is_target_holiday": date == pd.Timestamp("2025-02-17"),
                             "d7_date": d7, "d14_date": d14, "B1": b1, "B2": b2, "B3": b2 * applied,
                             "applied_holiday_factor": applied, "planning_method": "B2"})
                for source, role in [(d7, "D-7"), (d14, "D-14")]:
                    lineage.append({"forecast_date": date, "operator": operator, "touches_zone": touches,
                                    "source_date": source, "role": role})
                if date == pd.Timestamp("2025-02-17"):
                    for source, role in [("2025-01-13", "MLK reference before"), ("2025-01-20", "MLK holiday"), ("2025-01-27", "MLK reference after")]:
                        lineage.append({"forecast_date": date, "operator": operator, "touches_zone": touches,
                                        "source_date": pd.Timestamp(source), "role": role})
    forecast = pd.DataFrame(rows).sort_values(keys).reset_index(drop=True)
    return forecast, pd.DataFrame(factors), pd.DataFrame(lineage)


def forecast_metrics(actual, prediction):
    errors = prediction - actual
    denominator = float(actual.sum())
    return {"observations": len(actual), "actual_trips": denominator, "forecast_trips": float(prediction.sum()),
            "absolute_error_trips": float(errors.abs().sum()), "signed_error_trips": float(errors.sum()),
            "MAE": float(errors.abs().mean()), "WAPE": float(errors.abs().sum() / denominator) if denominator > 0 else None,
            "bias": float(errors.sum() / denominator) if denominator > 0 else None}


def score_holiday_forecasts(forecast, daily):
    keys = ["request_date", "operator", "touches_zone"]
    actual = daily[daily.request_date.between("2025-02-17", "2025-02-23")].copy()
    if actual.duplicated(keys).any() or not actual.data_available.all():
        raise ValueError("Backtest actuals have duplicate keys or missing coverage.")
    evaluation = forecast.merge(actual[keys + ["trips"]].rename(columns={"trips": "actual_trips"}),
                                on=keys, how="left", validate="one_to_one")
    if len(evaluation) != 28 or evaluation.actual_trips.isna().any():
        raise ValueError("Backtest needs all 28 actual observations.")
    records = []
    for scope in ["week", "holiday", "ordinary_days"]:
        subset = evaluation if scope == "week" else evaluation[evaluation.is_target_holiday.eq(scope == "holiday")]
        groups = [("All", "All", subset)] + [(op, str(bool(zone)), frame) for (op, zone), frame in subset.groupby(["operator", "touches_zone"])]
        for operator, zone, frame in groups:
            for method in ["B1", "B2", "B3"]:
                records.append({"scope": scope, "operator": operator, "touches_zone": zone, "method": method,
                                **forecast_metrics(frame.actual_trips, frame[method])})
    scores = pd.DataFrame(records)
    for method in ["B1", "B2", "B3"]:
        evaluation[f"{method}_error"] = evaluation[method] - evaluation.actual_trips
        evaluation[f"{method}_absolute_error"] = evaluation[f"{method}_error"].abs()
    return evaluation, scores


def write_cutoff_planning_memo(root, forecast, factors):
    totals = forecast.groupby("request_date")[["B1", "B2", "B3"]].sum()
    lines = ["# Holiday-week operating plan", "", "**Information cutoff: end of 16 February 2025, New York time.**", "",
             "Forecast completed Uber + Lyft trips for 17-23 February, split by operator and zone endpoints. This is a historical planning simulation, assuming cutoff trip records are accessible; TLC monthly releases are not a live feed.", "",
             "## Planning choice", "", "Use B2, the mean of the two preceding same-weekday observations, as the provisional planning baseline. This choice is fixed before test actuals are joined: averaging reduces reliance on a single unusual day. It has not been shown to win the upcoming test week.", "",
             "B3 is a holiday scenario for 17 February only: apply each segment's MLK factor from 20 January versus the mean of 13 and 27 January. One MLK observation does not establish Presidents' Day behavior; keep B2 and B3 visible to show this assumption's effect. B1 is the reference based on the preceding week.", "",
             "| Date | B2 planning trips | B3 holiday scenario |", "|---|---:|---:|"]
    for date, row in totals.iterrows():
        lines.append(f"| {date:%Y-%m-%d} | {row.B2:,.0f} | {row.B3:,.0f} |")
    lines += ["", f"B2 total: {totals.B2.sum():,.0f} completed trips. B3 scenario total: {totals.B3.sum():,.0f}. Fractional forecasts are retained for scoring; table display is rounded.",
              "", "## Operations and limits", "",
              "Review staffing readiness and pickup waiting times around the holiday, without converting trip forecasts into a driver count. If a weather forecast becomes available, prepare rain/snow contingency actions; future observed weather and summer rain factors are excluded from these forecasts. B2/B3 differences are scenarios, not a statistical prediction interval.",
              "", "Zone membership is calibrated on 5-31 January, before cutoff. History excludes trips completed after cutoff or lacking a completion time. No February credit uplift, test actuals, or retrospective weather coefficients enter this memo. Refresh with newly available observations during operations and evaluate accuracy in a separate retrospective report.", ""]
    (Path(root) / "docs/holiday_week_planning_memo.md").write_text("\n".join(lines))


def plot_holiday_forecasts(root, evaluation):
    root = Path(root)
    os.environ.setdefault("MPLCONFIGDIR", str(root / ".mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), layout="constrained")
    for ax, ((operator, zone), frame) in zip(axes.flat, evaluation.groupby(["operator", "touches_zone"])):
        ax.plot(frame.request_date, frame.actual_trips / 1000, color="#222222", marker="o", linewidth=2, label="Actual")
        for method, color, style in [("B1", "#9b6a38", ":"), ("B2", "#197f8c", "--"), ("B3", "#7257a5", "-")]:
            ax.plot(frame.request_date, frame[method] / 1000, color=color, linestyle=style, marker=".", label=method)
        ax.set_title(f"{operator} | {'Zone endpoints' if zone else 'Outside endpoints'}")
        ax.set_ylabel("Completed trips (thousands)")
        ax.set_xticks(frame.request_date, [date.strftime("%d/%m") for date in frame.request_date])
        ax.spines[["top", "right"]].set_visible(False)
    axes[0, 0].legend(ncol=4, fontsize=9)
    fig.suptitle("Holiday-week retrospective: 17-23 February 2025\nForecast information cutoff: 16 February; B3 differs from B2 only on 17 February", fontsize=12)
    fig.savefig(root / "reports/holiday_week_forecast.png", dpi=160)
    plt.close(fig)


def write_forecast_report(root, scores, factors, provenance, winner):
    total = scores[(scores.operator == "All") & (scores.scope == "week")]
    holiday = scores[(scores.operator == "All") & (scores.scope == "holiday")]
    lines = ["# Dự báo tuần có lễ: kết quả hồi cứu", "", "Dự báo 17-23/02/2025, cutoff hết 16/02 theo giờ New York. B2 được chọn trước làm baseline kế hoạch; B3 là kịch bản lễ. Phương án thắng dưới đây chỉ được biết sau tuần kiểm thử.", "",
             "## Ba cách dự báo", "", "B1=D-7. B2=trung bình D-7 và D-14. B3=B2×hệ số MLK riêng ngày 17/02; sáu ngày còn lại bằng B2. Hệ số riêng từng hãng/nhãn vùng = chuyến 20/01 chia trung bình 13/01 và 27/01. Không thêm machine learning hoặc chỉnh hệ số theo test.", "",
             "## Điểm toàn tuần", "", "| Cách | MAE (chuyến/ô ngày × phân khúc) | WAPE | Bias |", "|---|---:|---:|---:|"]
    for row in total.itertuples():
        lines.append(f"| {row.method} | {row.MAE:,.2f} | {row.WAPE:.2%} | {row.bias:+.2%} |")
    lines += ["", f"Phương án có WAPE thấp nhất hồi cứu: **{winner}**. Đây là kết luận của một tuần kiểm thử, không phải quyết định đã biết tại cutoff hoặc bằng chứng tổng quát cho mọi tuần có lễ.",
              "", "## Riêng ngày lễ", "", "| Cách | MAE (chuyến/phân khúc) | WAPE | Bias |", "|---|---:|---:|---:|"]
    for row in holiday.itertuples():
        lines.append(f"| {row.method} | {row.MAE:,.2f} | {row.WAPE:.2%} | {row.bias:+.2%} |")
    lines += ["", "Bảng điểm đầy đủ gồm toàn tuần, ngày lễ, ngày thường và từng phân khúc. WAPE toàn mẫu = tổng sai số tuyệt đối của 28 ô / tổng actual, không phải trung bình WAPE các phân khúc. Bias dương là dự báo cao, âm là dự báo thấp.",
              "", "## Đọc kết quả theo phân khúc", "", "| Hãng | Chạm vùng | WAPE B1 | WAPE B2 | WAPE B3 |", "|---|---|---:|---:|---:|"]
    segment_week = scores[(scores.operator != "All") & (scores.scope == "week")]
    for (operator, zone), frame in segment_week.groupby(["operator", "touches_zone"]):
        values = frame.set_index("method").WAPE
        lines.append(f"| {operator} | {zone} | {values.B1:.2%} | {values.B2:.2%} | {values.B3:.2%} |")
    b2_wape = total.set_index("method").loc["B2", "WAPE"]
    b3_wape = total.set_index("method").loc["B3", "WAPE"]
    lines += ["", f"Chênh lệch WAPE B3 trừ B2 là {(b3_wape - b2_wape) * 100:+.3f} điểm %. Toàn bộ khác biệt dự báo nằm ở 17/02. Hệ số MLK gồm cả nhóm tăng và giảm, không giả định mọi phân khúc giảm trong ngày lễ. Đọc bảng phân khúc trước khi quyết định dùng hệ số chung; kết quả một tuần chưa đủ xác nhận mô hình tốt nhất ổn định.",
              "", "## Hệ số MLK", "", "| Hãng | Chạm vùng | Chuyến MLK | Reference trung bình | Hệ số |", "|---|---|---:|---:|---:|"]
    for row in factors.itertuples():
        lines.append(f"| {row.operator} | {row.touches_zone} | {row.holiday_trips:,.0f} | {row.reference_trips:,.1f} | {row.holiday_factor:.4f} |")
    lines += ["", "## Cutoff và giới hạn", "",
              f"History chỉ giữ request từ 01/01 tới 16/02 và dropoff trước 00:00 ngày 17/02. Loại {provenance['completed_after_cutoff_excluded']:,} chuyến hoàn thành sau cutoff, {provenance['completion_time_missing_excluded']:,} chuyến thiếu thời điểm hoàn thành. Đối chiếu các chênh lệch với bảng ngày hồi cứu riêng, không sửa bảng ngày hoặc raw.",
              "Forecast và memo được ghi xuống đĩa trước khi ghép actual; hash forecast được kiểm tra sau scoring. Các tham số dùng tháng 01, không dùng kết quả credit tới 23/02 hoặc thời tiết thực tế tương lai. Bộ kiểm tra còn thay đổi mọi volume sau cutoff để xác nhận dự báo giữ nguyên.",
              "Đây là mô phỏng lịch sử với giả định dữ liệu chuyến đã có ở cutoff; TLC công bố theo tháng sau kỳ dữ liệu, không cung cấp feed dự báo realtime. Ngày lễ khác nhau, thời tiết, xu hướng và sự kiện đặc biệt có thể làm MLK không đại diện cho Presidents' Day. B2/B3 không tạo khoảng tin cậy. Chỉ đo nhu cầu được phục vụ, không đo booking bị hủy hoặc số tài xế.",
              "", "Memo kế hoạch tại cutoff: holiday_week_planning_memo.md. Đầu ra: forecast_week.csv, forecast_evaluation.csv, forecast_scores.csv, forecast_holiday_factors.csv, forecast_source_dates.csv và biểu đồ holiday_week_forecast.png.", ""]
    (Path(root) / "docs/holiday_week_forecast_report.md").write_text("\n".join(lines))


def validate_holiday_forecast(root, history, forecast, factors, lineage, evaluation, scores, provenance, frozen_hash):
    root = Path(root)
    keys = ["request_date", "operator", "touches_zone"]
    sample = evaluation.iloc[0]
    count = history.set_index(keys).trips
    d7 = float(count.loc[(sample.d7_date, sample.operator, sample.touches_zone)])
    d14 = float(count.loc[(sample.d14_date, sample.operator, sample.touches_zone)])
    h, before, after = [float(count.loc[(pd.Timestamp(date), sample.operator, sample.touches_zone)]) for date in ["2025-01-20", "2025-01-13", "2025-01-27"]]
    hand_b3 = (d7 + d14) / 2 * h / ((before + after) / 2)
    total = scores[(scores.operator == "All") & (scores.scope == "week") & (scores.method == "B3")].iloc[0]
    absolute = sum(abs(row.B3 - row.actual_trips) for row in evaluation.itertuples())
    actual_total = sum(row.actual_trips for row in evaluation.itertuples())
    signed = sum(row.B3 - row.actual_trips for row in evaluation.itertuples())
    noisy_future = pd.DataFrame([{"request_date": date, "operator": op, "touches_zone": zone, "trips": 999999999} for date in pd.date_range("2025-02-17", "2025-02-28") for op in ["Uber", "Lyft"] for zone in [False, True]])
    unchanged, _, _ = build_holiday_forecasts(pd.concat([history, noisy_future], ignore_index=True))
    missing_rejected = False
    try:
        build_holiday_forecasts(history[~((history.request_date == pd.Timestamp("2025-02-03")) & history.operator.eq("Uber") & ~history.touches_zone)])
    except ValueError:
        missing_rejected = True
    checks = {
        "twenty_eight_unique_keys": len(forecast) == 28 and not forecast.duplicated(keys).any(),
        "reference_dates_before_cutoff": lineage.source_date.le(pd.Timestamp("2025-02-16")).all(),
        "history_completed_before_cutoff": pd.Timestamp(provenance["latest_completion"]) < pd.Timestamp("2025-02-17"),
        "zone_calibration_before_cutoff": max(pd.Timestamp(x) for x in provenance["zone_calibration_dates"]) <= pd.Timestamp("2025-02-16"),
        "four_holiday_factors": len(factors) == 4 and not factors.duplicated(["operator", "touches_zone"]).any(),
        "six_ordinary_days_equal": forecast.loc[~forecast.is_target_holiday, "B2"].equals(forecast.loc[~forecast.is_target_holiday, "B3"]),
        "hand_forecast_matches": math.isclose(sample.B1, d7) and math.isclose(sample.B2, (d7 + d14) / 2) and math.isclose(sample.B3, hand_b3),
        "hand_MAE_matches": math.isclose(total.MAE, absolute / 28),
        "pooled_WAPE_matches": math.isclose(total.WAPE, absolute / actual_total),
        "pooled_bias_matches": math.isclose(total.bias, signed / actual_total, abs_tol=1e-12),
        "future_volume_cannot_change_forecast": forecast.equals(unchanged),
        "missing_reference_rejected": missing_rejected,
        "forecast_file_unchanged_after_scoring": hashlib.sha256((root / "data/processed/forecast_week.csv").read_bytes()).hexdigest() == frozen_hash,
        "scores_cover_scopes_and_segments": len(scores) == 45,
        "zero_actual_denominator_unavailable": forecast_metrics(pd.Series([0.]), pd.Series([1.]))["WAPE"] is None,
    }
    spot = {"request_date": str(sample.request_date.date()), "operator": sample.operator, "touches_zone": bool(sample.touches_zone),
            "D7_trips": d7, "D14_trips": d14, "MLK_trips": h, "MLK_before_trips": before, "MLK_after_trips": after,
            "B1": sample.B1, "B2": sample.B2, "B3": sample.B3, "hand_B3": hand_b3, "actual_trips": int(sample.actual_trips),
            "pooled_B3_absolute_error": absolute, "pooled_actual_trips": actual_total, "pooled_B3_signed_error": signed,
            "hand_MAE": absolute / 28, "hand_WAPE": absolute / actual_total, "hand_bias": signed / actual_total}
    pd.DataFrame([spot]).to_csv(root / "data/processed/forecast_spot_check.csv", index=False)
    payload = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "valid": bool(all(checks.values())),
               "checks": {key: bool(value) for key, value in checks.items()}, "forecast_rows": len(forecast), "score_rows": len(scores)}
    (root / "docs/holiday_week_forecast_validation.json").write_text(json.dumps(payload, indent=2) + "\n")
    if not payload["valid"]:
        raise ValueError(f"Forecast reconciliation failed: {checks}")


def forecast_holiday_week(root):
    root = Path(root)
    for folder in ["data/processed", "docs", "sql", "reports", ".analysis-cache"]:
        (root / folder).mkdir(parents=True, exist_ok=True)
    history, provenance = prepare_forecast_history(root)
    forecast, factors, lineage = build_holiday_forecasts(history)
    forecast.to_csv(root / "data/processed/forecast_week.csv", index=False)
    factors.to_csv(root / "data/processed/forecast_holiday_factors.csv", index=False)
    lineage.to_csv(root / "data/processed/forecast_source_dates.csv", index=False)
    write_cutoff_planning_memo(root, forecast, factors)
    frozen_hash = hashlib.sha256((root / "data/processed/forecast_week.csv").read_bytes()).hexdigest()
    daily = pd.read_csv(root / "data/processed/daily_segment.csv", parse_dates=["request_date"])
    evaluation, scores = score_holiday_forecasts(forecast, daily)
    evaluation.to_csv(root / "data/processed/forecast_evaluation.csv", index=False)
    scores.to_csv(root / "data/processed/forecast_scores.csv", index=False)
    all_week = scores[(scores.operator == "All") & (scores.scope == "week")]
    winner = all_week.sort_values(["WAPE", "method"]).iloc[0].method
    validate_holiday_forecast(root, history, forecast, factors, lineage, evaluation, scores, provenance, frozen_hash)
    plot_holiday_forecasts(root, evaluation)
    write_forecast_report(root, scores, factors, provenance, winner)
    summary = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "cutoff_date": "2025-02-16",
               "target_window": ["2025-02-17", "2025-02-23"], "planning_method_at_cutoff": "B2",
               "planning_reason": "Prespecified same-weekday two-week mean; MLK transfer retained as a scenario, not selected using test scores.",
               "retrospective_lowest_WAPE_method": winner, "week_scores": all_week.to_dict("records"),
               "forecast_sha256_before_actual_join": frozen_hash, "forecast_frozen_before_actual_join": True,
               "parameters_use_future_actuals": False, "weather_adjustment_used": False,
               "availability_assumption": provenance["availability_assumption"]}
    (root / "docs/holiday_week_forecast_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Forecast frozen: {len(forecast)} rows. Planning method B2; retrospective lowest WAPE: {winner}.")
    return forecast, evaluation, scores, factors, history


if __name__ == "__main__":
    forecast_holiday_week(Path(__file__).resolve().parents[1])
