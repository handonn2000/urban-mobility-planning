"""Prepare reconciled report inputs and local previews without publishing."""
from pathlib import Path
from datetime import datetime, timezone
import json
import math
import os
import pandas as pd


def reporting_segment_key(operator, zone):
    return operator + ("_zone" if zone else "_outside")


def prepare_report_tables(root):
    root = Path(root)
    out = root / "powerbi/data"
    out.mkdir(parents=True, exist_ok=True)
    daily = pd.read_csv(root / "data/processed/daily_segment.csv", parse_dates=["request_date"])
    hourly = pd.read_csv(root / "data/processed/hourly_city.csv", parse_dates=["request_date", "request_hour"])
    alerts = pd.read_csv(root / "data/processed/watchlist.csv", parse_dates=["request_date"])
    forecast = pd.read_csv(root / "data/processed/forecast_evaluation.csv", parse_dates=["request_date"])
    plan = pd.read_csv(root / "data/processed/forecast_week.csv", parse_dates=["request_date"])
    fee = pd.read_csv(root / "data/processed/fee_effect.csv")
    weekly = pd.read_csv(root / "data/processed/lyft_share_weekly.csv", parse_dates=["week_start"])
    weather = pd.read_csv(root / "data/processed/rain_factors.csv")
    credit = json.loads((root / "docs/lyft_credit_analysis.json").read_text())
    holidays = pd.read_csv(root / "data/external/holidays.csv", parse_dates=["date"])
    dates = pd.DataFrame({"Date": pd.date_range("2024-01-01", "2025-02-28")})
    dates["Year"] = dates.Date.dt.year
    dates["Month"] = dates.Date.dt.month
    dates["YearMonth"] = dates.Date.dt.strftime("%Y-%m")
    dates["Weekday"] = dates.Date.dt.dayofweek
    dates["DayName"] = dates.Date.dt.strftime("%a")
    dates["HolidayName"] = dates.Date.map(holidays.set_index("date").holiday_name)
    dates["IsHoliday"] = dates.HolidayName.notna()
    dates["HasTripSource"] = dates.Date.isin(daily.request_date)
    segments = pd.DataFrame([{"SegmentKey": reporting_segment_key(op, zone), "Operator": op,
                              "TouchesZone": zone, "SegmentLabel": f"{op} / {'zone endpoints' if zone else 'outside endpoints'}"}
                             for op in ["Uber", "Lyft"] for zone in [False, True]])
    def segmented(frame):
        result = frame.copy()
        result["SegmentKey"] = [reporting_segment_key(op, zone) for op, zone in zip(result.operator, result.touches_zone)]
        return result
    daily = segmented(daily)
    alerts = segmented(alerts)
    forecast = segmented(forecast)
    plan = segmented(plan)
    facts = {
        "DimDate": dates,
        "DimSegment": segments,
        "DimMethod": pd.DataFrame({"Method": ["B1", "B2", "B3"], "SortOrder": [1, 2, 3]}),
        "DimHour": pd.DataFrame({"Hour": range(24)}),
        "DimFeeOperator": pd.DataFrame({"FeeOperator": ["All", "Uber", "Lyft"]}),
        "DimTripGroup": pd.DataFrame({"TripGroup": ["all_trips", "short_trips", "low_fare_trips"]}),
        "DimZone": pd.DataFrame({"TouchesZone": [False, True], "ZoneLabel": ["Outside endpoints", "Zone endpoints"]}),
        "FactDaily": daily[["request_date", "SegmentKey", "trips", "short_trips", "low_fare_trips", "valid_economics_trips", "total_base_fare", "total_driver_pay", "median_wait_minutes"]].rename(columns={"request_date": "Date", "trips": "Trips", "short_trips": "ShortTrips", "low_fare_trips": "LowFareTrips", "valid_economics_trips": "ValidEconomicsTrips", "total_base_fare": "BaseFareSum", "total_driver_pay": "DriverPaySum", "median_wait_minutes": "MedianWaitMinutes"}),
        "FactCityHourly": hourly[["request_date", "request_hour", "hour", "trips", "median_wait_minutes", "rain_mm", "snowfall_cm", "temperature_c"]].rename(columns={"request_date": "Date", "request_hour": "DateTime", "hour": "Hour", "trips": "Trips", "median_wait_minutes": "MedianWaitMinutes", "rain_mm": "RainMM", "snowfall_cm": "SnowCM", "temperature_c": "TemperatureC"}),
        "FactAlerts": alerts[["request_date", "SegmentKey", "trips_deviation", "wait_deviation", "trigger", "next_step", "investigation_status"]].rename(columns={"request_date": "Date", "trips_deviation": "TripsDeviation", "wait_deviation": "WaitDeviation", "trigger": "Trigger", "next_step": "NextStep", "investigation_status": "Status"}),
        "FactPlan": plan[["request_date", "SegmentKey", "B1", "B2", "B3"]].rename(columns={"request_date": "Date"}),
        "FactFeeEffect": fee[["operator", "trip_group", "relative_growth_gap", "estimated_trip_difference", "scaled_total_gap"]].rename(columns={"operator": "FeeOperator", "trip_group": "TripGroup", "relative_growth_gap": "RelativeGrowthGap", "estimated_trip_difference": "EstimatedTripDifference", "scaled_total_gap": "ScaledTotalGap"}),
        "FactWeeklyShare": weekly[weekly.full_week][["week_start", "touches_zone", "lyft_trips", "market_trips", "lyft_share"]].rename(columns={"week_start": "Date", "touches_zone": "TouchesZone", "lyft_trips": "LyftTrips", "market_trips": "MarketTrips", "lyft_share": "LyftShare"}),
        "FactWeatherFactors": weather[["study", "weather_group", "usable_trip_hours", "usable_days", "wet_events", "trips_factor", "wait_factor", "trip_sample_under_20_hours"]].rename(columns={"study": "Study", "weather_group": "WeatherGroup", "usable_trip_hours": "Hours", "usable_days": "Days", "wet_events": "Events", "trips_factor": "TripsFactor", "wait_factor": "WaitFactor", "trip_sample_under_20_hours": "LowSample"}),
    }
    rows = []
    for method in ["B1", "B2", "B3"]:
        frame = forecast[["request_date", "SegmentKey", "actual_trips", method, f"{method}_absolute_error", f"{method}_error"]].copy()
        frame.columns = ["Date", "SegmentKey", "ActualTrips", "ForecastTrips", "AbsoluteErrorTrips", "SignedErrorTrips"]
        frame["Method"] = method
        rows.append(frame)
    facts["FactForecast"] = pd.concat(rows, ignore_index=True)
    facts["FactCreditSummary"] = pd.DataFrame([{"ShareGapPP": credit["comparison"]["share_difference_percentage_points"],
                                                "UpliftProxy": credit["comparison"]["approx_uplift_vs_post_share"],
                                                "CostPerExtraTrip": credit["default_economics"]["cost_per_incremental_trip_usd"],
                                                "MarginAssumption": 6.0, "RedemptionAssumption": 1.0}])
    contract = []
    for name, frame in facts.items():
        frame.to_csv(out / f"{name}.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")
        types = {}
        for column in frame:
            dtype = frame[column].dtype
            types[column] = "dateTime" if pd.api.types.is_datetime64_any_dtype(dtype) else "boolean" if pd.api.types.is_bool_dtype(dtype) else "int64" if pd.api.types.is_integer_dtype(dtype) else "double" if pd.api.types.is_float_dtype(dtype) else "string"
        contract.append({"table": name, "csv": f"data/{name}.csv", "rows": len(frame), "columns": types})
    (root / "powerbi/data_contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    return facts


def report_kpis(facts, start="2025-01-06", end="2025-01-26", segment_keys=None):
    daily = facts["FactDaily"]
    selected_dates = pd.date_range(start, end)
    selected = daily[daily.Date.isin(selected_dates)]
    if segment_keys is not None:
        selected = selected[selected.SegmentKey.isin(segment_keys)]
    prior = daily[daily.Date.isin(selected_dates - pd.Timedelta(days=364))]
    if segment_keys is not None:
        prior = prior[prior.SegmentKey.isin(segment_keys)]
    prior_total = float(prior.Trips.sum()) if prior.Date.nunique() == len(selected_dates) else None
    zones = facts["DimSegment"].set_index("SegmentKey").TouchesZone
    selected_zones = zones.loc[selected.SegmentKey.unique()].unique()
    market_keys = facts["DimSegment"].loc[facts["DimSegment"].TouchesZone.isin(selected_zones), "SegmentKey"]
    market = daily[daily.Date.isin(selected_dates) & daily.SegmentKey.isin(market_keys)]
    alerts = facts["FactAlerts"][facts["FactAlerts"].Date.isin(selected_dates)]
    if segment_keys is not None:
        alerts = alerts[alerts.SegmentKey.isin(segment_keys)]
    return {"trips": int(selected.Trips.sum()), "prior_trips": prior_total,
            "year_on_year": float(selected.Trips.sum() / prior_total - 1) if prior_total else None,
            "lyft_share": float(market.loc[market.SegmentKey.str.startswith("Lyft"), "Trips"].sum() / market.Trips.sum()) if market.Trips.sum() else None,
            "alert_rows": len(alerts)}


def validate_report_pack(root, facts):
    root = Path(root)
    daily = pd.read_csv(root / "data/processed/daily_segment.csv", parse_dates=["request_date"])
    hourly = pd.read_csv(root / "data/processed/hourly_city.csv")
    scores = pd.read_csv(root / "data/processed/forecast_scores.csv")
    single = report_kpis(facts, "2025-01-21", "2025-01-21", ["Lyft_zone"])
    original = daily[daily.request_date.eq("2025-01-21") & daily.operator.eq("Lyft") & daily.touches_zone].iloc[0]
    forecast = facts["FactForecast"]
    checks = {"continuous_date_dimension": len(facts["DimDate"]) == 425 and facts["DimDate"].Date.is_unique,
              "four_unique_segments": len(facts["DimSegment"]) == 4 and facts["DimSegment"].SegmentKey.is_unique,
              "daily_total_matches_source": int(facts["FactDaily"].Trips.sum()) == int(daily.trips.sum()),
              "city_hour_total_matches_source": int(facts["FactCityHourly"].Trips.sum()) == int(hourly.trips.sum()),
              "single_date_segment_matches": single["trips"] == int(original.trips),
              "all_daily_keys_unique": not facts["FactDaily"].duplicated(["Date", "SegmentKey"]).any(),
              "weather_has_no_segment_key": "SegmentKey" not in facts["FactCityHourly"] and "SegmentKey" not in facts["FactWeatherFactors"],
              "only_full_share_weeks": len(facts["FactWeeklyShare"]) == 14,
              "missing_prior_year_is_unavailable": report_kpis(facts, "2025-02-17", "2025-02-23")["year_on_year"] is None,
              "forecast_keys_unique": len(forecast) == 84 and not forecast.duplicated(["Date", "SegmentKey", "Method"]).any(),
              "plan_has_no_actual": "ActualTrips" not in facts["FactPlan"] and len(facts["FactPlan"]) == 28}
    for method in ["B1", "B2", "B3"]:
        frame = forecast[forecast.Method.eq(method)]
        expected = scores[scores.scope.eq("week") & scores.operator.eq("All") & scores.method.eq(method)].iloc[0]
        checks[f"{method}_WAPE_matches_source"] = math.isclose(frame.AbsoluteErrorTrips.sum() / frame.ActualTrips.sum(), expected.WAPE, rel_tol=1e-10)
    daily_dates = set(facts["DimDate"].Date)
    segments = set(facts["DimSegment"].SegmentKey)
    checks["foreign_keys_match_dimensions"] = all(("Date" not in frame or set(frame.Date).issubset(daily_dates)) and ("SegmentKey" not in frame or set(frame.SegmentKey).issubset(segments)) for frame in facts.values())
    checks["operator_slicer_does_not_change_share_market"] = math.isclose(report_kpis(facts, segment_keys=["Uber_zone"])["lyft_share"], report_kpis(facts, segment_keys=["Lyft_zone"])["lyft_share"], rel_tol=1e-12)
    pd.DataFrame([{"check": "all_retained_trips", "expected": int(daily.trips.sum()), "actual": int(facts["FactDaily"].Trips.sum())},
                  {"check": "2025-01-21_Lyft_zone", "expected": int(original.trips), "actual": single["trips"]}]).to_csv(root / "data/processed/report_reconciliation.csv", index=False)
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "valid": bool(all(checks.values())),
              "checks": {k: bool(v) for k, v in checks.items()}, "default_filters": {"start": "2025-01-06", "end": "2025-01-26"},
              "default_kpis": report_kpis(facts), "native_powerbi_tested": False,
              "evidence": "Local source reconciliation and filter semantics; native DAX and visual interactions require Power BI validation."}
    (root / "docs/reporting_pack_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    if not result["valid"]:
        raise ValueError(f"Report inputs failed reconciliation: {checks}")
    return result


def write_portfolio_memos(root, facts):
    root = Path(root)
    plan = facts["FactPlan"].groupby("Date")[["B2", "B3"]].sum()
    fee = facts["FactFeeEffect"]
    pooled = fee[fee.FeeOperator.eq("All") & fee.TripGroup.eq("all_trips")].iloc[0]
    jan = facts["FactDaily"][facts["FactDaily"].Date.between("2025-01-06", "2025-01-26")]
    zone = jan[jan.SegmentKey.str.endswith("_zone")]
    share = zone.loc[zone.SegmentKey.eq("Lyft_zone"), "Trips"].sum() / zone.Trips.sum()
    memo = ["# January Review and Feb 17-23 Demand Plan", "", "**Decision time: end of 16 February 2025, New York. Historical planning simulation.**", "",
            f"Plan **{plan.B2.sum():,.0f} completed Uber + Lyft trips** for 17-23 February using the two-week same-weekday mean (B2). Treat the MLK adjustment as a holiday scenario, not a proven improvement.", "",
            "## Evidence available at cutoff", "",
            f"In the matched January windows, zone-touching volume was {abs(pooled.RelativeGrowthGap):.2%} below its comparison-based counterfactual. This is an observational relative gap, not an identified causal fee effect. Outside-zone trips can be affected by spillovers and through-zone fees.",
            f"Lyft had {share:.2%} of completed Uber + Lyft zone trips in 6-26 January. Its $1.50 offer was future credit, not cash reimbursement. Redemption and campaign incrementality are unmeasured; the January-February share estimate is excluded because it uses data after this decision time.", "",
            "## Plan and action", "",
            f"Use B2 as the provisional baseline, fixed before evaluation. The B3 holiday scenario totals {plan.B3.sum():,.0f} trips and changes only 17 February. Keep the segment forecasts visible; the four MLK responses differ.",
            "Prepare pickup-time monitoring and rain/snow contingency actions. Summer rain coefficients are not February forecast multipliers. No future observed weather or test-week accuracy is used in this plan.",
            "Design a targeted $1.50 future-credit experiment with 10% randomized holdout, at least 14 issuance days and redemption follow-up. Decide using measured incremental net contribution per assigned user and guardrails. With assumed $6 contribution and full redemption, break-even is 33.33% uplift on eligible baseline trips; a whole-base 10% threshold requires 30% baseline-trip coverage and a compatible denominator.", "",
            "## What remains unknown", "",
            "Completed trips exclude failed/cancelled requests. Driver supply, true margin, redemption, retention and causal incrementality are not observed. This simulation assumes trip records were available at cutoff; public TLC monthly releases are retrospective. B2/B3 scenarios are not prediction intervals.", ""]
    (root / "docs/mobility_planning_memo.md").write_text("\n".join(memo))
    credit = facts["FactCreditSummary"].iloc[0]
    evaluation = facts["FactForecast"]
    review = ["# Retrospective evidence and learning", "", "**Includes trip outcomes through 23 February 2025. Separate from the 16 February planning memo.**", "",
              f"January fee comparison: relative zone gap {pooled.RelativeGrowthGap:+.2%}; observational assumptions remain unverified.",
              f"Credit comparison: adjusted Lyft share gap {credit.ShareGapPP:+.3f} percentage points; uplift proxy {credit.UpliftProxy:.2%}. Under $6 margin and 100% redemption assumptions, expected credit cost per extra trip is ${credit.CostPerExtraTrip:.2f}; this is not observed campaign ROI.", "",
              "| Method | Weekly WAPE | Weekly bias |", "|---|---:|---:|"]
    for method, frame in evaluation.groupby("Method"):
        review.append(f"| {method} | {frame.AbsoluteErrorTrips.sum() / frame.ActualTrips.sum():.2%} | {frame.SignedErrorTrips.sum() / frame.ActualTrips.sum():+.2%} |")
    review += ["", "B2 has the lowest WAPE in this test week. MLK adjustment improves Uber zone endpoints slightly, but worsens the other groups. One test week does not establish an enduring winner.", "",
               "Summer heavy-rain coefficients describe city-wide observed association, not causal demand or driver availability. Use them in the separate weather study; do not apply them to February planning.", ""]
    (root / "docs/mobility_retrospective_review.md").write_text("\n".join(review))
    claims = [{"claim": "planned_week_trips_B2", "value": float(plan.B2.sum()), "source": "data/processed/forecast_week.csv", "selection": "sum B2, 2025-02-17 through 2025-02-23", "known_at_cutoff": True},
              {"claim": "holiday_scenario_week_trips_B3", "value": float(plan.B3.sum()), "source": "data/processed/forecast_week.csv", "selection": "sum B3", "known_at_cutoff": True},
              {"claim": "January_relative_zone_gap", "value": float(pooled.RelativeGrowthGap), "source": "data/processed/fee_effect.csv", "selection": "operator=All, trip_group=all_trips", "known_at_cutoff": True},
              {"claim": "January_Lyft_zone_share", "value": float(share), "source": "data/processed/daily_segment.csv", "selection": "2025-01-06 through 2025-01-26, touches_zone=True", "known_at_cutoff": True},
              {"claim": "credit_cost_per_extra_trip_scenario", "value": float(credit.CostPerExtraTrip), "source": "docs/lyft_credit_analysis.json", "selection": "default_economics.cost_per_incremental_trip_usd; retrospective review only", "known_at_cutoff": False},
              {"claim": "illustrative_eligible_breakeven", "value": 1 / 3, "source": "data/processed/credit_economics_hand_examples.csv", "selection": "targeted example, breakeven_eligible_uplift; assumed economics, independent of observed uplift", "known_at_cutoff": True},
              {"claim": "illustrative_whole_base_breakeven", "value": .1, "source": "data/processed/credit_economics_hand_examples.csv", "selection": "targeted example, breakeven_global_uplift; assumed economics", "known_at_cutoff": True},
              {"claim": "assumed_trip_coverage", "value": .3, "source": "data/processed/credit_economics_hand_examples.csv", "selection": "targeted example, coverage; assumption", "known_at_cutoff": True},
              {"claim": "assumed_contribution_per_trip", "value": 6.0, "source": "data/processed/credit_economics_hand_examples.csv", "selection": "margin_usd; assumption, not observed margin", "known_at_cutoff": True},
              {"claim": "credit_face_value", "value": 1.5, "source": "data/processed/credit_economics_hand_examples.csv", "selection": "credit_usd; program face value", "known_at_cutoff": True},
              {"claim": "proposed_holdout_share", "value": .1, "source": "docs/targeted_credit_experiment_brief.md", "selection": "Eligibility and assignment; proposed design, not executed test", "known_at_cutoff": True},
              {"claim": "proposed_issuance_days_minimum", "value": 14, "source": "docs/targeted_credit_experiment_brief.md", "selection": "Duration and sample; proposed design", "known_at_cutoff": True}]
    pd.DataFrame(claims).to_csv(root / "data/processed/memo_claim_sources.csv", index=False)


def render_report_previews(root, facts):
    root = Path(root)
    os.environ.setdefault("MPLCONFIGDIR", str(root / ".mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    dark, teal, orange, purple = "#18394b", "#217f85", "#c87336", "#7861a2"
    def canvas(title, subtitle):
        fig = plt.figure(figsize=(16, 9), facecolor="#f3f6f8")
        fig.text(.045, .94, title, fontsize=23, fontweight="bold", color=dark)
        fig.text(.045, .905, subtitle, fontsize=11, color="#536571")
        fig.text(.045, .025, "Local report preview from verified CSV | Power BI native rendering and filters pending", fontsize=9, color="#536571")
        return fig
    def card(fig, x, title, value, detail):
        ax = fig.add_axes([x, .745, .21, .12], facecolor="white", zorder=5)
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values(): spine.set_visible(False)
        ax.text(.06, .79, title, transform=ax.transAxes, color="#536571", fontsize=10)
        ax.text(.06, .32, value, transform=ax.transAxes, color=dark, fontsize=22, fontweight="bold")
        ax.text(.06, .07, detail, transform=ax.transAxes, color="#536571", fontsize=8)
    metrics = report_kpis(facts)
    fig = canvas("Demand monitoring and weather", "6-26 January 2025 | All four segments | Matched weekday comparison: 8-28 January 2024")
    for x, title, value, detail in [(.045, "Completed trips", f"{metrics['trips']/1e6:.3f}M", "Observed served demand"), (.285, "Same-weekday change", f"{metrics['year_on_year']:+.2%}", "D-364; all reference days available"), (.525, "Lyft market share", f"{metrics['lyft_share']:.2%}", "Uber + Lyft denominator"), (.765, "Alert rows", str(metrics['alert_rows']), "Date x segment; not unique dates")]:
        card(fig, x, title, value, detail)
    daily = facts["FactDaily"][facts["FactDaily"].Date.between("2025-01-06", "2025-01-26")]
    ax = fig.add_axes([.07, .38, .42, .30], facecolor="white")
    colors = [teal, orange, purple, "#637c9e"]
    for (segment, frame), color in zip(daily.groupby("SegmentKey"), colors):
        ax.plot(frame.Date, frame.Trips/1000, color=color, label=segment.replace("_", " / "))
    ax.set_title("Daily completed trips by segment", loc="left", color=dark)
    ax.set_ylabel("Thousands"); ax.legend(ncol=2, fontsize=8, frameon=False)
    ax.tick_params(axis="x", labelsize=8)
    city = facts["FactCityHourly"][facts["FactCityHourly"].Date.between("2025-01-06", "2025-01-26")].copy()
    city["Weekday"] = city.Date.dt.dayofweek
    heat = city.groupby(["Weekday", "Hour"]).Trips.mean().unstack("Hour")
    ax = fig.add_axes([.57, .40, .35, .25], facecolor="white")
    im = ax.imshow(heat/1000, aspect="auto", cmap="YlGnBu")
    ax.set_yticks(range(7), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.set_xticks(range(0, 24, 3)); ax.set_xlabel("New York hour")
    ax.set_title("City-wide average trips per hour", loc="left", color=dark)
    fig.colorbar(im, ax=ax, fraction=.025, pad=.02, label="Thousands")
    fig.text(.57, .33, "City-wide grain: unaffected by operator / zone slicers", fontsize=9, color="#536571")
    ax = fig.add_axes([.07, .095, .59, .205], facecolor="white"); ax.axis("off")
    ax.set_title("Alerts to investigate | completed review does not establish root cause", loc="left", color=dark, fontsize=11)
    alerts = facts["FactAlerts"][facts["FactAlerts"].Date.between("2025-01-06", "2025-01-26")].copy()
    alerts["Magnitude"] = alerts.TripsDeviation.abs()
    alerts = alerts.sort_values("Magnitude", ascending=False).head(5)
    rows = [[r.Date.strftime("%d Jan"), r.SegmentKey.replace("_", " / "), f"{r.TripsDeviation:+.1%}", f"{r.WaitDeviation:+.1%}", r.Status.replace("_", " ")] for r in alerts.itertuples()]
    table = ax.table(cellText=rows, colLabels=["Date", "Segment", "Trips", "Wait", "Status"], colWidths=[.11, .22, .11, .11, .39], loc="center", cellLoc="left")
    table.auto_set_font_size(False); table.set_fontsize(9); table.scale(1, 1.5)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#edf1f4"); cell.set_facecolor("#e3ebef" if row == 0 else "white")
    rain = facts["FactWeatherFactors"]
    heavy = rain[rain.Study.eq("summer_2024") & rain.WeatherGroup.eq("moderate_or_heavy_rain")].iloc[0]
    fig.text(.715, .28, "Separate summer weather study", color=dark, fontweight="bold", fontsize=12)
    fig.text(.715, .23, f"Heavy rain: trips x{heavy.TripsFactor:.3f}\nWait x{heavy.WaitFactor:.3f} | {int(heavy.Hours)} hours", color=teal, fontsize=13, linespacing=1.5)
    fig.text(.715, .125, "June-August 2024, city-wide association.\nSmall event sample; no causal claim.\nDo not transfer this factor to February.", fontsize=9, color="#536571", linespacing=1.5)
    fig.savefig(root / "reports/demand_monitoring_preview.png", dpi=140)
    plt.close(fig)
    fig = canvas("Price, credit and the holiday-week plan", "Retrospective comparisons and a separately frozen 16 February plan | Observed proxies, not causal campaign ROI")
    fee = facts["FactFeeEffect"]
    all_fee = fee[fee.FeeOperator.eq("All") & fee.TripGroup.eq("all_trips")].iloc[0]
    credit = facts["FactCreditSummary"].iloc[0]
    plan = facts["FactPlan"].groupby("Date")[["B2", "B3"]].sum()
    for x, title, value, detail in [(.045, "Relative zone volume gap", f"{all_fee.RelativeGrowthGap:+.2%}", "Matched January comparison"), (.285, "Adjusted Lyft share gap", f"{credit.ShareGapPP:+.3f} pp", "Jan vs Feb; retrospective"), (.525, "Credit cost / extra trip", f"${credit.CostPerExtraTrip:.2f}", "Assumed $6 margin; 100% redemption"), (.765, "B2 planned week", f"{plan.B2.sum()/1e6:.3f}M", "Frozen cutoff: 16 February")]:
        card(fig, x, title, value, detail)
    ax = fig.add_axes([.08, .39, .23, .29], facecolor="white")
    sample = fee[fee.FeeOperator.eq("All")]
    ax.barh(["All trips", "Short trips", "Low fare"], sample.RelativeGrowthGap*100, color=[teal, orange, purple])
    ax.axvline(0, color="#536571", linewidth=.7); ax.set_xlabel("Relative gap (%)")
    ax.set_title("Fee comparison | pooled operators", fontsize=11, loc="left", color=dark)
    fig.text(.08, .335, "Overlapping trip groups; do not add effects.", fontsize=9, color="#536571")
    ax = fig.add_axes([.40, .40, .52, .27], facecolor="white")
    weekly = facts["FactWeeklyShare"]
    for zone, label, color in [(True, "Zone endpoints", orange), (False, "Outside endpoints", teal)]:
        frame = weekly[weekly.TouchesZone.eq(zone)]
        ax.plot(frame.Date, frame.LyftShare*100, marker="o", color=color, label=label)
    ax.axvspan(pd.Timestamp("2025-01-05"), pd.Timestamp("2025-01-31"), color=orange, alpha=.10)
    ax.set_title("Lyft share | full observed weeks only", loc="left", fontsize=11, color=dark)
    ax.set_ylabel("Percent"); ax.legend(fontsize=8, ncol=2, frameon=False)
    ax.tick_params(axis="x", labelsize=8)
    ax = fig.add_axes([.08, .10, .46, .20], facecolor="white")
    forecast = facts["FactForecast"]
    for method, color, style in [("B1", orange, ":"), ("B2", teal, "--"), ("B3", purple, "-")]:
        frame = forecast[forecast.Method.eq(method)].groupby("Date").ForecastTrips.sum()
        ax.plot(frame.index, frame/1000, color=color, linestyle=style, label=method)
    actual = forecast[forecast.Method.eq("B2")].groupby("Date").ActualTrips.sum()
    ax.plot(actual.index, actual/1000, color="#222222", marker="o", label="Actual")
    ax.set_title("17-23 February | retrospective forecast evaluation", loc="left", fontsize=11, color=dark)
    ax.set_ylabel("Thousands"); ax.legend(ncol=4, fontsize=8, frameon=False)
    ax.set_xticks(actual.index, [d.strftime("%d/%m") for d in actual.index])
    fig.text(.61, .285, "Action and evidence", fontweight="bold", fontsize=12, color=dark)
    wapes = {method: frame.AbsoluteErrorTrips.sum() / frame.ActualTrips.sum() for method, frame in forecast.groupby("Method")}
    result_text = "improve" if wapes["B3"] < wapes["B2"] else "not improve"
    fig.text(.61, .225, f"B2 weekly WAPE {wapes['B2']:.2%}; B3 {wapes['B3']:.2%}, B1 {wapes['B1']:.2%}.\nThe holiday adjustment did {result_text} the pooled result.", fontsize=10, color="#536571", linespacing=1.5)
    fig.text(.61, .145, "Propose a targeted credit experiment with 10% holdout.\nUse net contribution and guardrails; eligible uplift\nbreak-even is 33.33% under the stated assumptions.", fontsize=10, color="#536571", linespacing=1.5)
    fig.savefig(root / "reports/price_credit_plan_preview.png", dpi=140)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7.0, 1.65), layout="constrained")
    ax.bar(plan.index, plan.B2 / 1000, color=[orange] + [teal]*6)
    ax.set_xticks(plan.index, [d.strftime("%d %b") for d in plan.index]); ax.set_ylabel("000 trips", fontsize=9)
    ax.set_title("B2 operating plan | completed trips, cutoff 16 February", loc="left", fontsize=10)
    ax.tick_params(labelsize=8)
    fig.savefig(root / "reports/memo_planned_trips.png", dpi=160)
    plt.close(fig)


def prepare_reporting_pack(root):
    root = Path(root)
    for folder in ["powerbi", "reports", "docs", "data/processed"]:
        (root / folder).mkdir(parents=True, exist_ok=True)
    facts = prepare_report_tables(root)
    verification = validate_report_pack(root, facts)
    write_portfolio_memos(root, facts)
    render_report_previews(root, facts)
    print(f"Prepared {len(facts)} report tables and two local previews; native Power BI validation remains pending.")
    return facts, verification


if __name__ == "__main__":
    prepare_reporting_pack(Path(__file__).resolve().parents[1])
