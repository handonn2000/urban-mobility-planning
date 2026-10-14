"""Marketplace economics, pre-fee check, forecast-band alerts and experiment power."""
from pathlib import Path
from datetime import datetime, timezone
import json
import math
import os
import duckdb
import numpy as np
import pandas as pd


FEE_CHARGED_LYFT_SQL = """
SELECT
    CAST(request_datetime AS DATE) AS request_date,
    COUNT(*) AS lyft_trips_charged_fee,
    SUM(cbd_congestion_fee) AS lyft_fee_usd
FROM read_parquet('{raw_file}')
WHERE hvfhs_license_num = 'HV0005'
  AND cbd_congestion_fee > 0
  AND CAST(request_datetime AS DATE) BETWEEN DATE '2025-01-05' AND DATE '2025-01-31'
GROUP BY CAST(request_datetime AS DATE)
ORDER BY request_date
"""

FEE_CHARGED_BY_LABEL_SQL = """
SELECT
    CASE WHEN hvfhs_license_num = 'HV0003' THEN 'Uber' ELSE 'Lyft' END AS operator,
    CASE WHEN pu.LocationID IS NOT NULL OR do_zone.LocationID IS NOT NULL THEN true ELSE false END AS touches_zone,
    COUNT(*) AS trips,
    SUM(CASE WHEN cbd_congestion_fee > 0 THEN 1 ELSE 0 END) AS trips_charged_fee
FROM read_parquet('{raw_file}') t
LEFT JOIN read_csv_auto('{zone_file}') pu ON t.PULocationID = pu.LocationID
LEFT JOIN read_csv_auto('{zone_file}') do_zone ON t.DOLocationID = do_zone.LocationID
WHERE hvfhs_license_num IN ('HV0003', 'HV0005')
  AND CAST(request_datetime AS DATE) BETWEEN DATE '2025-01-06' AND DATE '2025-01-26'
GROUP BY operator, touches_zone
ORDER BY operator, touches_zone
"""

WINDOWS = {"jan_2024": ("2024-01-08", "2024-01-28"),
           "jan_2025": ("2025-01-06", "2025-01-26"),
           "feb_2025": ("2025-02-03", "2025-02-23")}
COMPARISONS = [("jan_2024", "jan_2025", "Phí: 01/2024 → 01/2025 (cùng thứ, 1 MLK)"),
               ("jan_2025", "feb_2025", "Credit: 01/2025 → 02/2025 (có → hết credit)")]
FEE_START = pd.Timestamp("2025-01-05")
Z_FOR_95_TWO_SIDED = 1.959964
Z_FOR_80_POWER = 0.841621


def segment_label(operator, touches_zone):
    return f"{operator} {'chạm vùng' if touches_zone else 'ngoài vùng'}"


def load_daily(root):
    daily = pd.read_csv(Path(root) / "data/processed/daily_segment.csv", parse_dates=["request_date"])
    daily["touches_zone"] = daily.touches_zone.astype(str).str.lower().eq("true")
    return daily


def load_holidays(root):
    calendar = pd.read_csv(Path(root) / "data/external/holidays.csv", parse_dates=["date"])
    return set(calendar.date)


def window_economics(daily):
    rows = []
    for window, (start, end) in WINDOWS.items():
        data = daily[daily.request_date.between(start, end)]
        groups = [(op, zone, data[(data.operator == op) & (data.touches_zone == zone)])
                  for op in ["Uber", "Lyft"] for zone in [True, False]]
        groups.append(("All", "All", data))
        for op, zone, g in groups:
            trips = int(g.trips.sum())
            econ = int(g.valid_economics_trips.sum())
            fare = float(g.total_base_fare.sum())
            pay = float(g.total_driver_pay.sum())
            avg_fare = fare / econ
            rows.append({"window": window, "start": start, "end": end, "days": g.request_date.nunique(),
                         "operator": op, "touches_zone": zone, "trips": trips,
                         "valid_economics_trips": econ, "base_fare_sum_usd": fare, "driver_pay_sum_usd": pay,
                         "avg_base_fare_usd": avg_fare, "driver_pay_per_trip_usd": pay / econ,
                         "platform_share_proxy": 1 - pay / fare,
                         "platform_retained_per_trip_usd": (fare - pay) / econ,
                         "gmv_proxy_usd": trips * avg_fare})
    return pd.DataFrame(rows)


def decompose_gmv(economics):
    rows = []
    keys = ["operator", "touches_zone"]
    for before, after, label in COMPARISONS:
        a = economics[economics.window.eq(before)].set_index(keys)
        b = economics[economics.window.eq(after)].set_index(keys)
        for key in a.index:
            trips_change = b.loc[key, "trips"] / a.loc[key, "trips"]
            fare_change = b.loc[key, "avg_base_fare_usd"] / a.loc[key, "avg_base_fare_usd"]
            gmv_change = b.loc[key, "gmv_proxy_usd"] / a.loc[key, "gmv_proxy_usd"]
            log_total = math.log(gmv_change)
            rows.append({"comparison": label, "before": before, "after": after,
                         "operator": key[0], "touches_zone": key[1],
                         "trips_growth": trips_change - 1, "avg_fare_growth": fare_change - 1,
                         "gmv_proxy_growth": gmv_change - 1,
                         "volume_log_points": 100 * math.log(trips_change),
                         "price_log_points": 100 * math.log(fare_change),
                         "volume_share_of_gmv_change": math.log(trips_change) / log_total if abs(log_total) > 1e-12 else np.nan,
                         "driver_pay_per_trip_growth": b.loc[key, "driver_pay_per_trip_usd"] / a.loc[key, "driver_pay_per_trip_usd"] - 1,
                         "platform_share_proxy_change_pp": 100 * (b.loc[key, "platform_share_proxy"] - a.loc[key, "platform_share_proxy"])})
    return pd.DataFrame(rows)


def credit_cost_against_gmv(root, daily, con):
    raw_file = Path(root) / "data/raw/fhvhv_tripdata_2025-01.parquet"
    charged = con.execute(FEE_CHARGED_LYFT_SQL.format(raw_file=raw_file.as_posix())).df()
    charged["request_date"] = pd.to_datetime(charged.request_date)
    rows = []
    for name, (start, end) in [("credit_issuance_full", ("2025-01-05", "2025-01-31")),
                               ("credit_comparison_window", WINDOWS["jan_2025"])]:
        n = int(charged[charged.request_date.between(start, end)].lyft_trips_charged_fee.sum())
        lyft = daily[(daily.operator == "Lyft") & daily.request_date.between(start, end)]
        zone = lyft[lyft.touches_zone]
        lyft_gmv = float(lyft.trips.sum() * lyft.total_base_fare.sum() / lyft.valid_economics_trips.sum())
        zone_gmv = float(zone.trips.sum() * zone.total_base_fare.sum() / zone.valid_economics_trips.sum())
        for redemption in [1.0, 0.5, 0.25]:
            cost = n * 1.5 * redemption
            rows.append({"period": name, "start": start, "end": end,
                         "lyft_trips_charged_fee": n, "lyft_zone_trips": int(zone.trips.sum()),
                         "lyft_trips_all": int(lyft.trips.sum()), "redemption": redemption,
                         "credit_cost_usd": cost, "lyft_zone_gmv_proxy_usd": zone_gmv,
                         "lyft_gmv_proxy_usd": lyft_gmv,
                         "credit_cost_share_of_lyft_zone_gmv": cost / zone_gmv,
                         "credit_cost_share_of_lyft_gmv": cost / lyft_gmv})
    return pd.DataFrame(rows), charged


def fee_label_coverage(root, con):
    root = Path(root)
    frame = con.execute(FEE_CHARGED_BY_LABEL_SQL.format(
        raw_file=(root / "data/raw/fhvhv_tripdata_2025-01.parquet").as_posix(),
        zone_file=(root / "data/processed/crz_zones.csv").as_posix())).df()
    frame["fee_rate"] = frame.trips_charged_fee / frame.trips
    totals = frame.groupby("operator").trips_charged_fee.transform("sum")
    frame["share_of_operator_fee_trips"] = frame.trips_charged_fee / totals
    return frame


def matched_day_gaps(daily, holidays):
    rows = []
    for day in pd.date_range("2025-01-02", "2025-01-29"):
        prior = day - pd.Timedelta(days=364)
        row = {"date_2025": day, "date_2024": prior, "day_of_week": day.dayofweek,
               "period": "trước phí" if day < FEE_START else "sau phí",
               "holiday_mismatch": (day in holidays) != (prior in holidays),
               "in_main_window": WINDOWS["jan_2025"][0] <= day.strftime("%Y-%m-%d") <= WINDOWS["jan_2025"][1]}
        for op in ["All", "Uber", "Lyft"]:
            sel = daily if op == "All" else daily[daily.operator.eq(op)]
            def total(date, zone):
                return int(sel[(sel.request_date == date) & (sel.touches_zone == zone)].trips.sum())
            z24, z25, o24, o25 = total(prior, True), total(day, True), total(prior, False), total(day, False)
            row.update({f"{op}_zone_2024": z24, f"{op}_zone_2025": z25,
                        f"{op}_outside_2024": o24, f"{op}_outside_2025": o25,
                        f"{op}_gap": (z25 / z24) / (o25 / o24) - 1})
        rows.append(row)
    return pd.DataFrame(rows)


def pooled_gap(frame, op):
    return (frame[f"{op}_zone_2025"].sum() / frame[f"{op}_zone_2024"].sum()) / (
        frame[f"{op}_outside_2025"].sum() / frame[f"{op}_outside_2024"].sum()) - 1


def pre_fee_summary(gaps):
    rows = []
    pre = gaps[gaps.period.eq("trước phí") & ~gaps.holiday_mismatch]
    main = gaps[gaps.in_main_window]
    for op in ["All", "Uber", "Lyft"]:
        rows.append({"operator": op, "pre_fee_days": len(pre),
                     "pre_fee_dates": ",".join(pre.date_2025.dt.strftime("%Y-%m-%d")),
                     "pre_fee_gap": pooled_gap(pre, op), "main_window_days": len(main),
                     "main_window_gap": pooled_gap(main, op),
                     "main_minus_pre_pp": 100 * (pooled_gap(main, op) - pooled_gap(pre, op))})
    return pd.DataFrame(rows)


def bootstrap_gap(gaps, reps=5000, seed=20250105):
    rng = np.random.default_rng(seed)
    main = gaps[gaps.in_main_window].reset_index(drop=True)
    rows = []
    for op in ["All", "Uber", "Lyft"]:
        cols = [f"{op}_zone_2025", f"{op}_zone_2024", f"{op}_outside_2025", f"{op}_outside_2024"]
        values = main[cols].to_numpy(dtype=float)
        by_weekday = [np.flatnonzero(main.day_of_week.to_numpy() == d) for d in range(7)]
        draws_day, draws_strat = [], []
        for _ in range(reps):
            idx = rng.integers(0, len(main), len(main))
            s = values[idx].sum(axis=0)
            draws_day.append((s[0] / s[1]) / (s[2] / s[3]) - 1)
            idx = np.concatenate([rng.choice(g, len(g), replace=True) for g in by_weekday if len(g)])
            s = values[idx].sum(axis=0)
            draws_strat.append((s[0] / s[1]) / (s[2] / s[3]) - 1)
        point = pooled_gap(main, op)
        for method, draws in [("day_pairs", draws_day), ("weekday_stratified", draws_strat)]:
            rows.append({"operator": op, "method": method, "reps": reps, "seed": seed,
                         "point_estimate": point, "ci_low_2_5": float(np.percentile(draws, 2.5)),
                         "ci_high_97_5": float(np.percentile(draws, 97.5)),
                         "interpretation": "Sampling variation across days only; does not cover zone-label, spillover or parallel-trend uncertainty"})
    return pd.DataFrame(rows)


def is_new_year_week(day):
    return day.month == 1 and day.day <= 7


def forecast_band_alerts(daily, holidays, k=2.5, materiality=0.03):
    data = daily.set_index(["request_date", "operator", "touches_zone"]).trips
    rows = []
    for (day, op, zone), actual in data.items():
        refs = []
        for lag in [7, 14, 21, 28, 35]:
            ref = day - pd.Timedelta(days=lag)
            if (ref, op, zone) in data.index and ref not in holidays and not is_new_year_week(ref):
                refs.append(ref)
            if len(refs) == 2:
                break
        expected = float(np.mean([data[(r, op, zone)] for r in refs])) if refs else np.nan
        known = ""
        if day in holidays:
            known = "ngày lễ"
        elif zone is True and day >= FEE_START and refs and min(refs) < FEE_START:
            known = "bắt đầu phí 05/01 (kỳ vọng còn dùng ngày trước phí)"
        rows.append({"request_date": day, "operator": op, "touches_zone": zone, "trips": int(actual),
                     "reference_dates": ",".join(r.strftime("%Y-%m-%d") for r in refs),
                     "reference_count": len(refs), "expected_trips": expected,
                     "log_ratio": math.log(actual / expected) if refs else np.nan,
                     "known_event": known})
    frame = pd.DataFrame(rows)
    frame["band_scale"] = np.where(frame.reference_count.eq(1), math.sqrt(4 / 3), 1.0)
    calib = frame[frame.known_event.eq("") & frame.reference_count.eq(2)]
    bands = []
    for (op, zone), g in calib.groupby(["operator", "touches_zone"]):
        center = float(g.log_ratio.median())
        sd = float((g.log_ratio - center).abs().median()) * 1.4826
        bands.append({"operator": op, "touches_zone": zone, "calibration_days": len(g),
                      "center_log": center, "robust_sd_log": sd, "k": k,
                      "half_width_log": max(k * sd, math.log(1 + materiality)),
                      "old_rule_in_sd_units": math.log(1.07) / sd})
    bands = pd.DataFrame(bands)
    bands["lower_ratio"] = np.exp(bands.center_log - bands.half_width_log)
    bands["upper_ratio"] = np.exp(bands.center_log + bands.half_width_log)
    frame = frame.merge(bands[["operator", "touches_zone", "center_log", "robust_sd_log", "half_width_log",
                               "lower_ratio", "upper_ratio"]], on=["operator", "touches_zone"], how="left")
    frame["half_width_log"] = frame.half_width_log * frame.band_scale
    frame["z_score"] = (frame.log_ratio - frame.center_log) / (frame.robust_sd_log * frame.band_scale)
    frame["outside_band"] = frame.log_ratio.notna() & (frame.log_ratio - frame.center_log).abs().gt(frame.half_width_log)
    frame["alert_status"] = np.select(
        [frame.log_ratio.isna(), frame.outside_band & frame.known_event.ne(""), frame.outside_band],
        ["không đủ kỳ vọng", "lệch, đã có sự kiện giải thích", "cần điều tra"], default="trong dải")
    return frame, bands


def add_weather_context(root, frame):
    hourly = pd.read_csv(Path(root) / "data/processed/hourly_city.csv", parse_dates=["request_date"])
    day = hourly.groupby("request_date").agg(rain_hours=("rain_mm", lambda x: int((x >= 0.5).sum())),
                                             snow_hours=("snowfall_cm", lambda x: int((x > 0).sum())))
    def describe(dates):
        parts = []
        for d in [pd.Timestamp(x) for x in dates if x]:
            r = day.loc[d] if d in day.index else None
            parts.append(f"{d:%d/%m}: mưa {r.rain_hours}h, tuyết {r.snow_hours}h" if r is not None else f"{d:%d/%m}: n/a")
        return "; ".join(parts)
    frame = frame.copy()
    frame["weather_target"] = frame.request_date.map(lambda d: describe([d.strftime("%Y-%m-%d")]))
    frame["weather_references"] = frame.reference_dates.fillna("").map(lambda x: describe(x.split(",")))
    return frame


def band_sensitivity(frame):
    rows = []
    usable = frame[frame.log_ratio.notna()]
    for k in [2.0, 2.5, 3.0]:
        out = (usable.z_score.abs() > k) & ((usable.log_ratio - usable.center_log).abs() > math.log(1.03))
        rows.append({"k": k, "expected_false_alarm_rate_if_normal": math.erfc(k / math.sqrt(2)),
                     "days_with_expectation": len(usable), "outside_band": int(out.sum()),
                     "explained_by_known_event": int((out & usable.known_event.ne("")).sum()),
                     "needs_investigation": int((out & usable.known_event.eq("")).sum())})
    return pd.DataFrame(rows)


def city_band_series(daily, holidays, k=2.5, materiality=0.03):
    city = daily.groupby("request_date", as_index=False).trips.sum()
    city["operator"], city["touches_zone"] = "City", "All"
    return forecast_band_alerts(city, holidays, k, materiality)


def old_vs_new_alerts(root, new_alerts):
    old = pd.read_csv(Path(root) / "data/processed/watchlist.csv")
    old["request_date"] = pd.to_datetime(old.request_date)
    rows = []
    for month, label in [("2024-01", "01/2024"), ("2025-01", "01/2025"), ("2025-02", "02/2025")]:
        o = old[old.request_date.dt.strftime("%Y-%m").eq(month) & old.alert.astype(str).str.lower().eq("true")]
        n = new_alerts[new_alerts.request_date.dt.strftime("%Y-%m").eq(month)]
        rows.append({"month": label, "old_rule_alerts": len(o),
                     "old_rule_needs_follow_up": int(o.investigation_status.eq("needs_follow_up").sum()),
                     "band_outside": int(n.outside_band.sum()),
                     "band_explained_by_known_event": int(n.alert_status.eq("lệch, đã có sự kiện giải thích").sum()),
                     "band_needs_investigation": int(n.alert_status.eq("cần điều tra").sum()),
                     "band_no_expectation": int(n.alert_status.eq("không đủ kỳ vọng").sum())})
    return pd.DataFrame(rows)


def mde_relative(sd_log, n_treat, n_control, design_effect=1.0):
    return (Z_FOR_95_TWO_SIDED + Z_FOR_80_POWER) * sd_log * math.sqrt(design_effect * (1 / n_treat + 1 / n_control))


def switchback_power(root, holidays):
    hourly = pd.read_csv(Path(root) / "data/processed/hourly_city.csv", parse_dates=["request_hour", "request_date"])
    data = hourly[(hourly.request_date >= "2025-01-06") & ~hourly.request_date.isin(holidays)].copy()
    data["month"] = data.request_date.dt.month
    rows = []
    rain_rate = float(((data.rain_mm >= 0.5) & data.snowfall_cm.eq(0)).mean())
    for metric in ["trips", "median_wait_minutes"]:
        data["log_value"] = np.log(data[metric])
        data["resid"] = data.log_value - data.groupby(["month", "day_of_week", "hour"]).log_value.transform("median")
        for block in [1, 2]:
            series = data.sort_values("request_hour").copy()
            series["block"] = (series.request_hour - series.request_hour.min()).dt.total_seconds() // (3600 * block)
            blocks = series.groupby("block").resid.mean()
            sd = float(blocks.std(ddof=1))
            rho = float(blocks.autocorr(lag=1))
            de = (1 + max(rho, 0)) / (1 - max(rho, 0))
            for days, scope in [(14, "mọi giờ"), (28, "mọi giờ"), (14, "chỉ giờ mưa ≥0,5 mm"), (56, "chỉ giờ mưa ≥0,5 mm")]:
                slices = days * 24 // block if scope == "mọi giờ" else max(int(round(days * 24 * rain_rate / block)), 2)
                rows.append({"metric": metric, "block_hours": block, "test_days": days, "scope": scope,
                             "slices": slices, "sd_log_per_slice": sd, "lag1_autocorrelation": rho,
                             "design_effect": de, "winter_2025_rain_hour_share": rain_rate,
                             "mde_relative": mde_relative(sd, slices / 2, slices / 2, de)})
    return pd.DataFrame(rows)


def user_holdout_power():
    rows = []
    for users in [50_000, 200_000, 500_000]:
        for cv in [1.5, 2.5]:
            for cuped_r2 in [0.0, 0.3, 0.5]:
                sd = cv * math.sqrt(1 - cuped_r2)
                rows.append({"eligible_users": users, "treatment_share": .9, "trips_per_user_cv": cv,
                             "cuped_variance_reduction": cuped_r2,
                             "mde_relative": mde_relative(sd, users * .9, users * .1),
                             "assumption": "Giả định minh họa; TLC không có ID khách. Thay bằng phương sai thật trước khi chạy."})
    return pd.DataFrame(rows)


def srm_check(treatment_users, control_users, expected_treatment_share=.9):
    total = treatment_users + control_users
    exp_t, exp_c = total * expected_treatment_share, total * (1 - expected_treatment_share)
    chi2 = (treatment_users - exp_t) ** 2 / exp_t + (control_users - exp_c) ** 2 / exp_c
    p_value = math.erfc(math.sqrt(chi2 / 2))
    return {"treatment_users": treatment_users, "control_users": control_users, "chi_square": chi2,
            "p_value": p_value, "srm_flag": p_value < 0.001}


def plot_extensions(root, gaps, boot, decomposition, city):
    root = Path(root)
    os.environ.setdefault("MPLCONFIGDIR", str(root / ".mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, muted, grid = "#1f2933", "#6b7280", "#e5e7eb"
    orange, teal = "#d78335", "#157f78"

    fig, ax = plt.subplots(figsize=(9.5, 4.2), layout="constrained")
    ax.axvspan(gaps.date_2025.min() - pd.Timedelta(hours=12), FEE_START - pd.Timedelta(hours=12), color=grid, alpha=.7)
    ax.axhline(0, color=muted, lw=1)
    ok = gaps[~gaps.holiday_mismatch]
    bad = gaps[gaps.holiday_mismatch]
    ax.plot(gaps.date_2025, gaps.All_gap * 100, color=teal, lw=2)
    ax.scatter(ok.date_2025, ok.All_gap * 100, s=26, color=teal, zorder=3, edgecolor="white", linewidth=1.5)
    ax.scatter(bad.date_2025, bad.All_gap * 100, s=34, facecolor="white", edgecolor=teal, linewidth=1.8, zorder=3)
    b = boot[(boot.operator == "All") & (boot.method == "day_pairs")].iloc[0]
    start, end = pd.Timestamp(WINDOWS["jan_2025"][0]), pd.Timestamp(WINDOWS["jan_2025"][1])
    ax.fill_between([start, end], b.ci_low_2_5 * 100, b.ci_high_97_5 * 100, color=orange, alpha=.18, lw=0)
    ax.plot([start, end], [b.point_estimate * 100] * 2, color=orange, lw=2)
    ax.text(.99, .04, f"Orange: window 06–26/01 = {b.point_estimate:.1%}\n95% bootstrap over days: {b.ci_low_2_5:.1%} to {b.ci_high_97_5:.1%}",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5, color=ink)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax.text(gaps.date_2025.min(), ax.get_ylim()[1], " before fee", va="top", fontsize=8.5, color=muted)
    ax.set_title("Zone vs outside growth gap by matched day (2025 vs same weekday 2024)", loc="left", fontsize=11, color=ink)
    ax.set_ylabel("Relative gap (%)", color=muted)
    ax.grid(axis="y", color=grid, lw=.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=muted)
    ax.text(1, -0.14, "Hollow marker: holiday on one side only (MLK mismatch)", transform=ax.transAxes, ha="right", fontsize=8, color=muted)
    fig.savefig(root / "reports/fee_pre_period_check.png", dpi=160)
    plt.close(fig)

    seg = decomposition[decomposition.operator.ne("All")].copy()
    seg["label"] = [segment_label(o, z == True).replace("chạm vùng", "zone").replace("ngoài vùng", "outside") for o, z in zip(seg.operator, seg.touches_zone)]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True, sharex=True, layout="constrained")
    for ax, (label, g) in zip(axes, seg.groupby("comparison", sort=False)):
        y = np.arange(len(g))
        ax.barh(y - .19, g.volume_log_points, height=.36, color=teal, label="Trips (volume)")
        ax.barh(y + .19, g.price_log_points, height=.36, color=orange, label="Avg base fare (price)")
        ax.set_yticks(y, g.label)
        ax.axvline(0, color=muted, lw=1)
        ax.set_title("Fee: Jan 2024 → Jan 2025" if "Phí" in label else "Credit: Jan 2025 → Feb 2025", loc="left", fontsize=10.5, color=ink)
        ax.grid(axis="x", color=grid, lw=.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(colors=muted)
        ax.set_xlabel("Contribution to GMV proxy change (log points)", color=muted, fontsize=9)
    axes[0].invert_yaxis()
    axes[1].legend(loc="lower right", fontsize=8.5, frameon=False)
    fig.savefig(root / "reports/gmv_volume_price_decomposition.png", dpi=160)
    plt.close(fig)

    import matplotlib.dates as mdates
    c = city.dropna(subset=["log_ratio"])
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True, layout="constrained")
    for ax, (year, g) in zip(axes, c.groupby(c.request_date.dt.year)):
        lo = (np.exp(g.center_log - g.half_width_log) - 1) * 100
        hi = (np.exp(g.center_log + g.half_width_log) - 1) * 100
        ax.fill_between(g.request_date, lo, hi, color=grid, alpha=.9, lw=0, step="mid")
        ax.axhline(0, color=muted, lw=1)
        ax.plot(g.request_date, (np.exp(g.log_ratio) - 1) * 100, color=teal, lw=2, marker="o", ms=3.5)
        flag = g[g.outside_band]
        ax.scatter(flag.request_date, (np.exp(flag.log_ratio) - 1) * 100, s=46, color=orange, zorder=3, edgecolor="white", linewidth=1.5)
        for _, r in flag.iterrows():
            ax.annotate(r.request_date.strftime("%d/%m"), (r.request_date, (math.exp(r.log_ratio) - 1) * 100),
                        textcoords="offset points", xytext=(5, 2), fontsize=8, color=ink)
        ax.set_title(f"{year}", loc="left", fontsize=10.5, color=ink)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        ax.grid(axis="y", color=grid, lw=.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(colors=muted)
    axes[0].set_ylabel("City trips vs forecast (%)", color=muted)
    fig.suptitle("City trips vs two-week same-weekday forecast; grey = alert band (2.5 robust SD)", x=.01, ha="left", fontsize=11, color=ink)
    fig.savefig(root / "reports/forecast_band_alerts.png", dpi=160)
    plt.close(fig)


def analyze_marketplace_extensions(root):
    root = Path(root)
    processed = root / "data/processed"
    (root / "sql").mkdir(exist_ok=True)
    (root / "sql/count_lyft_fee_charged_trips.sql").write_text(FEE_CHARGED_LYFT_SQL.strip() + "\n")
    (root / "sql/count_fee_charged_trips_by_zone_label.sql").write_text(FEE_CHARGED_BY_LABEL_SQL.strip() + "\n")
    daily = load_daily(root)
    holidays = load_holidays(root)
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'")

    economics = window_economics(daily)
    decomposition = decompose_gmv(economics)
    credit_cost, charged = credit_cost_against_gmv(root, daily, con)
    label_coverage = fee_label_coverage(root, con)
    gaps = matched_day_gaps(daily, holidays)
    pre = pre_fee_summary(gaps)
    boot = bootstrap_gap(gaps)
    alerts, bands = forecast_band_alerts(daily, holidays)
    city, city_bands = city_band_series(daily, holidays)
    alerts = add_weather_context(root, alerts)
    comparison = old_vs_new_alerts(root, alerts)
    sensitivity = band_sensitivity(alerts)
    switchback = switchback_power(root, holidays)
    holdout = user_holdout_power()
    srm_examples = pd.DataFrame([srm_check(180_000, 20_000), srm_check(179_200, 20_800)])

    outputs = {"marketplace_economics_windows": economics, "gmv_volume_price_decomposition": decomposition,
               "lyft_credit_cost_vs_gmv": credit_cost, "lyft_fee_charged_trips_daily": charged,
               "fee_label_coverage": label_coverage, "forecast_band_sensitivity": sensitivity,
               "fee_matched_day_gaps": gaps, "fee_pre_period_check": pre, "fee_gap_bootstrap": boot,
               "forecast_band_alerts": alerts, "forecast_band_parameters": pd.concat([bands, city_bands]),
               "forecast_band_city": city, "alert_rule_comparison": comparison,
               "experiment_power_switchback": switchback, "experiment_power_user_holdout": holdout,
               "experiment_srm_examples": srm_examples}
    for name, frame in outputs.items():
        frame.to_csv(processed / f"{name}.csv", index=False)
    plot_extensions(root, gaps, boot, decomposition, city)

    main = gaps[gaps.in_main_window]
    fee_effect = pd.read_csv(processed / "fee_effect.csv")
    reference = fee_effect[(fee_effect.zone_threshold == .95) & (fee_effect.scenario == "full_window")
                           & (fee_effect.operator == "All") & (fee_effect.trip_group == "all_trips")].relative_growth_gap.iloc[0]
    jan25 = economics[(economics.window == "jan_2025") & (economics.operator == "All")].iloc[0]
    checks = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "matched_day_window_equals_fee_effect": bool(abs(pooled_gap(main, "All") - reference) < 1e-12),
        "main_window_days": int(len(main)),
        "economics_all_trips_equals_segment_sum": bool(
            economics[(economics.window == "jan_2025") & (economics.operator != "All")].trips.sum() == jan25.trips),
        "decomposition_logs_add_up": bool(np.allclose(
            decomposition.volume_log_points + decomposition.price_log_points,
            100 * np.log1p(decomposition.gmv_proxy_growth))),
        "alert_rows": int(len(alerts)), "alert_rows_expected": 360,
        "credit_window_charged_trips": int(credit_cost.lyft_trips_charged_fee.iloc[-1]),
        "fee_charged_trips_labeled_outside_share": {op: float(g[~g.touches_zone].share_of_operator_fee_trips.sum())
                                                    for op, g in label_coverage.groupby("operator")},
        "bootstrap_point_matches_fee_effect": bool(abs(boot.point_estimate.iloc[0] - reference) < 1e-12),
    }
    (root / "docs/marketplace_extensions_validation.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False) + "\n")
    return outputs, checks


if __name__ == "__main__":
    outputs, checks = analyze_marketplace_extensions(Path(__file__).resolve().parents[1])
    print(json.dumps(checks, indent=2, ensure_ascii=False))
