"""Compare observed shares and evaluate explicitly assumed credit economics."""
from pathlib import Path
from datetime import datetime, timezone
import json
import math
import os
import pandas as pd


def summarize_credit_periods(daily, off_start="2025-02-03", off_end="2025-02-23"):
    rows = []
    periods = [("credit_issuance", "2025-01-06", "2025-01-26"), ("post_issuance", off_start, off_end)]
    for period, start, end in periods:
        data = daily[daily.request_date.between(start, end)]
        expected = pd.MultiIndex.from_product([pd.date_range(start, end), ["Uber", "Lyft"], [False, True]],
                                              names=["request_date", "operator", "touches_zone"])
        actual = pd.MultiIndex.from_frame(data[["request_date", "operator", "touches_zone"]])
        if actual.has_duplicates or len(actual) != len(expected) or len(expected.difference(actual)):
            raise ValueError("Credit comparison needs complete unique daily segment coverage.")
        for touches_zone, group in data.groupby("touches_zone"):
            trips = group.groupby("operator").trips.sum()
            paired = group[group.operator.eq("Lyft")]
            row = {"period": period, "start": start, "end": end, "touches_zone": bool(touches_zone),
                   "days": int(group.request_date.nunique()), "holiday_days": int(group.loc[group.is_holiday, "request_date"].nunique()),
                   "lyft_trips": int(trips.loc["Lyft"]), "uber_trips": int(trips.loc["Uber"]),
                   "lyft_valid_economics_trips": int(paired.valid_economics_trips.sum()),
                   "lyft_base_fare_sum": float(paired.total_base_fare.sum()),
                   "lyft_driver_pay_sum": float(paired.total_driver_pay.sum())}
            row["market_trips"] = row["lyft_trips"] + row["uber_trips"]
            row["lyft_share"] = row["lyft_trips"] / row["market_trips"]
            row["reported_fare_pay_gap_proxy"] = (row["lyft_base_fare_sum"] - row["lyft_driver_pay_sum"]) / row["lyft_valid_economics_trips"]
            rows.append(row)
    periods = pd.DataFrame(rows)
    lookup = periods.set_index(["period", "touches_zone"])
    on_zone = lookup.loc[("credit_issuance", True)]
    off_zone = lookup.loc[("post_issuance", True)]
    on_out = lookup.loc[("credit_issuance", False)]
    off_out = lookup.loc[("post_issuance", False)]
    difference = (on_zone.lyft_share - off_zone.lyft_share) - (on_out.lyft_share - off_out.lyft_share)
    counterfactual_share = off_zone.lyft_share + on_out.lyft_share - off_out.lyft_share
    if not 0 < counterfactual_share < 1:
        raise ValueError("Adjusted reference share must be between zero and one.")
    delta = difference * on_zone.market_trips
    summary = {"share_difference": float(difference), "share_difference_percentage_points": float(difference * 100),
               "approx_uplift_vs_post_share": float(difference / off_zone.lyft_share),
               "counterfactual_credit_period_share": float(counterfactual_share),
               "fixed_market_incremental_trip_proxy": float(delta),
               "fixed_market_counterfactual_lyft_trips": float(counterfactual_share * on_zone.market_trips),
               "fixed_market_uplift_proxy": float(difference / counterfactual_share),
               "credit_period_share_in_zone": float(on_zone.lyft_share),
               "post_period_share_in_zone": float(off_zone.lyft_share),
               "credit_period_share_outside": float(on_out.lyft_share),
               "post_period_share_outside": float(off_out.lyft_share),
               "lyft_zone_volume_change_post_vs_credit": float(off_zone.lyft_trips / on_zone.lyft_trips - 1),
               "uber_zone_volume_change_post_vs_credit": float(off_zone.uber_trips / on_zone.uber_trips - 1),
               "market_zone_volume_change_post_vs_credit": float(off_zone.market_trips / on_zone.market_trips - 1),
               "interpretation": "Observed share difference; uplift and trip counts are proxies under fixed-market and unaffected-control assumptions, not causal campaign ROI"}
    return periods, summary


def credit_economics(base_trips=100, uplift=.03, credit=1.5, margin=6, coverage=1,
                     redemption=1, incremental_credit_fraction=1):
    values = [base_trips, uplift, credit, margin, coverage, redemption, incremental_credit_fraction]
    if not all(math.isfinite(x) for x in values):
        raise ValueError("Economic inputs must be finite.")
    if min(base_trips, uplift, credit, margin) < 0 or not 0 < coverage <= 1 or not 0 <= redemption <= 1 or not 0 <= incremental_credit_fraction <= 1:
        raise ValueError("Invalid economic inputs.")
    effective_credit = credit * redemption
    extra = base_trips * uplift
    issued = base_trips * coverage + extra * incremental_credit_fraction
    redeemed = issued * redemption
    cost = issued * effective_credit
    contribution = extra * margin
    net = contribution - cost
    denominator = margin - incremental_credit_fraction * effective_credit
    if denominator > 0:
        breakeven = coverage * effective_credit / denominator
    elif coverage * effective_credit == 0 and denominator == 0:
        breakeven = 0.0
    else:
        breakeven = None
    return {"base_trips": base_trips, "uplift": uplift, "credit_usd": credit, "margin_usd": margin,
            "coverage": coverage, "redemption": redemption, "incremental_credit_fraction": incremental_credit_fraction,
            "effective_credit_usd": effective_credit, "incremental_trips": extra, "credits_issued": issued,
            "credits_redeemed": redeemed, "credit_cost_usd": cost, "incremental_contribution_usd": contribution,
            "net_incremental_contribution_usd": net, "cost_per_incremental_trip_usd": cost / extra if extra > 0 else None,
            "breakeven_global_uplift": breakeven,
            "breakeven_eligible_uplift": breakeven / coverage if breakeven is not None else None,
            "uplift_denominator": "All base trips; eligible-population threshold divides by baseline-trip coverage"}


def plot_credit_analysis(root, weekly, comparison):
    root = Path(root)
    os.environ.setdefault("MPLCONFIGDIR", str(root / ".mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
    for touches, label, color in [(True, "Zone endpoints", "#d78335"), (False, "Outside endpoints", "#157f78")]:
        data = weekly[weekly.touches_zone.eq(touches)]
        ax.plot(data.week_start, data.lyft_share * 100, marker="o", label=label, color=color)
    ax.axvspan(pd.Timestamp("2025-01-05"), pd.Timestamp("2025-01-31"), color="#d78335", alpha=.10, label="Credit issuance")
    ax.set_title("Lyft weekly share of completed Uber + Lyft trips")
    ax.set_ylabel("Share (%)")
    ax.legend(loc="lower left", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(root / "reports/lyft_share_weekly.png", dpi=160)
    plt.close(fig)


def analyze_lyft_credit(root):
    root = Path(root).resolve()
    for directory in ["data/processed", "docs", "reports"]:
        (root / directory).mkdir(parents=True, exist_ok=True)
    daily = pd.read_csv(root / "data/processed/daily_segment.csv", parse_dates=["request_date"])
    current = daily[daily.request_date.dt.year.eq(2025)].copy()
    current["week_start"] = current.request_date - pd.to_timedelta(current.request_date.dt.dayofweek, unit="D")
    weekly = current.groupby(["week_start", "touches_zone", "operator"]).trips.sum().unstack("operator").reset_index()
    weekly = weekly.rename(columns={"Lyft": "lyft_trips", "Uber": "uber_trips"})
    days = current.groupby(["week_start", "touches_zone"]).request_date.nunique().reset_index(name="days_covered")
    weekly = weekly.merge(days, on=["week_start", "touches_zone"], validate="one_to_one")
    weekly["market_trips"] = weekly.lyft_trips + weekly.uber_trips
    weekly["lyft_share"] = weekly.lyft_trips / weekly.market_trips
    weekly["full_week"] = weekly.days_covered.eq(7)
    weekly.to_csv(root / "data/processed/lyft_share_weekly.csv", index=False)
    periods, summary = summarize_credit_periods(current)
    periods.to_csv(root / "data/processed/lyft_credit_period_comparison.csv", index=False)
    alternatives = []
    for name, start, end in [("planned_three_weeks", "2025-02-03", "2025-02-23"),
                             ("exclude_first_february_week", "2025-02-10", "2025-02-23")]:
        frame, metrics = summarize_credit_periods(current, start, end)
        alternatives.append({"comparison": name, "post_start": start, "post_end": end,
                             "credit_days": 21, "post_days": int(frame[frame.period.eq("post_issuance")].days.iloc[0]), **metrics})
    sensitivity = pd.DataFrame(alternatives)
    sensitivity.to_csv(root / "data/processed/lyft_credit_share_sensitivity.csv", index=False)
    default = credit_economics(uplift=summary["approx_uplift_vs_post_share"])
    scenarios = []
    for margin in [3, 6, 9]:
        for redemption in [.25, .5, .75, 1]:
            for coverage in [1, .3]:
                scenarios.append(credit_economics(uplift=default["uplift"], margin=margin, redemption=redemption, coverage=coverage))
    scenarios = pd.DataFrame(scenarios)
    scenarios.to_csv(root / "data/processed/credit_breakeven_scenarios.csv", index=False)
    hand = credit_economics(uplift=.03)
    assert hand["incremental_trips"] == 3 and hand["credits_issued"] == 103
    assert math.isclose(hand["credit_cost_usd"], 154.5)
    assert math.isclose(hand["cost_per_incremental_trip_usd"], 51.5)
    assert math.isclose(hand["breakeven_global_uplift"], 1 / 3)
    targeted = credit_economics(uplift=.1, coverage=.3)
    assert math.isclose(targeted["net_incremental_contribution_usd"], 0, abs_tol=1e-10)
    assert math.isclose(targeted["breakeven_global_uplift"], .1)
    assert math.isclose(targeted["breakeven_eligible_uplift"], 1 / 3)
    assert credit_economics(redemption=0)["credit_cost_usd"] == 0
    assert credit_economics(uplift=0)["cost_per_incremental_trip_usd"] is None
    assert credit_economics(margin=1)["breakeven_global_uplift"] is None
    hand_rows = pd.DataFrame([{"example": "100_base_3pct_uplift", **hand}, {"example": "targeted_30pct_10pct_global_uplift", **targeted}])
    hand_rows.to_csv(root / "data/processed/credit_economics_hand_examples.csv", index=False)
    validate_credit_outputs(root, daily, weekly, periods, summary, scenarios, hand, targeted)
    assert periods.days.eq(21).all() and periods.holiday_days.eq(1).all()
    assert math.isclose(summary["share_difference"],
                        (summary["credit_period_share_in_zone"] - summary["post_period_share_in_zone"])
                        - (summary["credit_period_share_outside"] - summary["post_period_share_outside"]), rel_tol=1e-12)
    manual_share = periods.iloc[0].lyft_trips / periods.iloc[0].market_trips
    assert math.isclose(manual_share, periods.iloc[0].lyft_share, rel_tol=1e-12)
    payload = {"prepared_at_utc": datetime.now(timezone.utc).isoformat(), "comparison": summary,
               "period_counts": periods.to_dict("records"), "default_economics": default,
               "scenario_rows": len(scenarios), "excel_output": "excel/lyft_credit_breakeven.xlsx",
               "excel_authoring": "Separate presentation artifact; notebook analysis and CSV/JSON outputs do not require this workbook",
               "credit_program": {"face_value_usd": 1.5, "issuance": ["2025-01-05", "2025-01-31"],
                                  "validity": "One week after the initial ride; credit for future Lyft/Citi Bike use",
                                  "source": "https://www.lyft.com/blog/posts/navigating-the-new-nyc-congestion-fee-with-lyft"},
               "economics_limits": "Margin and redemption are assumptions. Cost uses expected redeemed face value, not observed expense. No measured campaign ROI, user retention or total-market incrementality."}
    (root / "docs/lyft_credit_analysis.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    plot_credit_analysis(root, weekly, periods)
    write_credit_report(root, periods, summary, default, sensitivity)
    write_credit_experiment_brief(root)
    print(f"Credit comparison completed: share gap {summary['share_difference_percentage_points']:.2f} pp; illustrative uplift {default['uplift']:.2%}.")
    return weekly, periods, summary, scenarios, sensitivity


def validate_credit_outputs(root, daily, weekly, periods, summary, scenarios, hand, targeted):
    current = daily[daily.request_date.dt.year.eq(2025)].copy()
    current["week_start"] = current.request_date - pd.to_timedelta(current.request_date.dt.dayofweek, unit="D")
    counts = current.groupby(["week_start", "touches_zone", "operator"]).trips.sum().unstack("operator").reset_index()
    joined = weekly.merge(counts, on=["week_start", "touches_zone"], validate="one_to_one")
    on = periods[periods.period.eq("credit_issuance")].set_index("touches_zone")
    off = periods[periods.period.eq("post_issuance")].set_index("touches_zone")
    manual_gap = (on.loc[True, "lyft_trips"] / on.loc[True, "market_trips"]
                  - off.loc[True, "lyft_trips"] / off.loc[True, "market_trips"]
                  - on.loc[False, "lyft_trips"] / on.loc[False, "market_trips"]
                  + off.loc[False, "lyft_trips"] / off.loc[False, "market_trips"])
    checks = {
        "weekly_unique": not weekly.duplicated(["week_start", "touches_zone"]).any(),
        "weekly_counts_match_daily": len(joined) == len(weekly) and joined.lyft_trips.eq(joined.Lyft).all() and joined.uber_trips.eq(joined.Uber).all(),
        "weekly_share_matches_counts": all(math.isclose(row.lyft_share, row.lyft_trips / row.market_trips, rel_tol=1e-12) for row in weekly.itertuples()),
        "matched_periods": len(periods) == 4 and periods.days.eq(21).all() and periods.holiday_days.eq(1).all(),
        "share_gap_matches_counts": math.isclose(manual_gap, summary["share_difference"], rel_tol=1e-12),
        "uplift_denominator_matches": math.isclose(manual_gap / off.loc[True, "lyft_share"], summary["approx_uplift_vs_post_share"], rel_tol=1e-12),
        "hundred_trip_example": math.isclose(hand["credit_cost_usd"], 154.5) and math.isclose(hand["cost_per_incremental_trip_usd"], 51.5),
        "targeted_denominators": math.isclose(targeted["net_incremental_contribution_usd"], 0, abs_tol=1e-10) and math.isclose(targeted["breakeven_global_uplift"], .1) and math.isclose(targeted["breakeven_eligible_uplift"], 1 / 3),
        "scenario_costs_match": len(scenarios) == 24 and all(math.isclose(row.credit_cost_usd, row.base_trips * (row.coverage + row.uplift * row.incremental_credit_fraction) * row.credit_usd * row.redemption, rel_tol=1e-12) for row in scenarios.itertuples()),
        "zero_redemption": credit_economics(redemption=0)["credit_cost_usd"] == 0,
        "zero_uplift": credit_economics(uplift=0)["cost_per_incremental_trip_usd"] is None,
        "insufficient_margin": credit_economics(margin=1)["breakeven_global_uplift"] is None,
    }
    payload = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
               "valid": all(checks.values()), "checks": {key: bool(value) for key, value in checks.items()},
               "weekly_rows": len(weekly), "partial_week_rows": int((~weekly.full_week).sum()),
               "comparison_rows": len(periods), "scenario_rows": len(scenarios)}
    (Path(root) / "docs/lyft_credit_validation.json").write_text(json.dumps(payload, indent=2) + "\n")
    if not payload["valid"]:
        raise ValueError(f"Credit outputs failed reconciliation: {checks}")


def write_credit_report(root, periods, summary, default, sensitivity):
    lines = ["# Lyft credit: thị phần và kinh tế theo kịch bản", "",
             "## So sánh quan sát", "",
             "06-26/01/2025 so với 03-23/02/2025: cùng ba tuần, cùng thứ và một lễ thứ Hai. Credit phát trong 05-31/01 và dùng cho chuyến tương lai/Citi Bike trong tuần kế tiếp; giai đoạn đầu tháng 02 có thể còn credit. Ngoài vùng cũng có thể hưởng credit.",
             "", "| Kỳ | Nhãn vùng | Lyft | Uber | Thị phần Lyft |", "|---|---|---:|---:|---:|"]
    for r in periods.itertuples(index=False):
        lines.append(f"| {r.period} | {r.touches_zone} | {r.lyft_trips:,} | {r.uber_trips:,} | {r.lyft_share:.2%} |")
    lines += ["", f"Chênh lệch của thay đổi thị phần = {summary['share_difference_percentage_points']:+.3f} điểm phần trăm. Quy đổi xấp xỉ theo deck, chia cho thị phần Lyft trong vùng giai đoạn sau: {summary['approx_uplift_vs_post_share']:.2%}.",
              f"Nếu giữ quy mô thị trường tháng 01 cố định và điều chỉnh mức share phản thực bằng thay đổi ngoài vùng, proxy là {summary['fixed_market_incremental_trip_proxy']:,.0f} chuyến, uplift trên chính mẫu phản thực {summary['fixed_market_uplift_proxy']:.2%}. Hai tỷ lệ khác mẫu số; không coi là hai ước lượng nhân quả độc lập.",
              f"Từ kỳ January sang February, volume trong vùng: Lyft {summary['lyft_zone_volume_change_post_vs_credit']:+.2%}, Uber {summary['uber_zone_volume_change_post_vs_credit']:+.2%}, tổng {summary['market_zone_volume_change_post_vs_credit']:+.2%}. Lyft không giảm volume tuyệt đối dù share giảm; chưa kết luận toàn bộ chênh lệch là lấy chuyến từ Uber hay tạo nhu cầu mới.",
              "", "## Bỏ tuần đầu tháng 02", ""]
    for r in sensitivity.itertuples(index=False):
        lines.append(f"- {r.comparison}: {r.share_difference_percentage_points:+.3f} pp; uplift xấp xỉ {r.approx_uplift_vs_post_share:.2%}; {r.credit_days} ngày kỳ credit so {r.post_days} ngày kỳ sau.")
    lines += ["", "Phép kiểm tra 10-23/02 giảm lo ngại carryover nhưng có hai tuần so ba tuần, khác thành phần thứ/lễ; chỉ là độ vững tham khảo, không dùng volume thô để suy ra tăng giảm nhân quả.",
              "", "## Mô hình kinh tế", "",
              "N: chuyến nền; u: uplift trên toàn bộ N; s: phần chuyến nền nhận credit; a: phần chuyến tăng thêm nhận credit; c: mệnh giá; r: tỷ lệ sử dụng; m: contribution margin giả định mỗi chuyến tăng thêm.",
              "Credit cost=N×(s+a×u)×c×r. Contribution thêm=N×u×m. Chênh lệch=N×[u×(m−a×c×r)−s×c×r]. Hòa vốn toàn mẫu u*=s×c×r/(m−a×c×r), nếu mẫu số dương. Hòa vốn riêng nhóm đủ điều kiện=u*/s khi incrementals nằm trong nhóm đó.",
              f"Mặc định N=100, c=$1,50, m=$6 (giả định), r=100%, s=100%, a=100%, u={default['uplift']:.2%}: cost/extra trip=${default['cost_per_incremental_trip_usd']:.2f}; net contribution=${default['net_incremental_contribution_usd']:.2f}/100 chuyến nền. Đây không phải ROI thực tế.",
              "m=$6 không lấy trực tiếp từ cước trừ driver pay. TLC không có đủ chi phí nền tảng. Credit cost là mệnh giá kỳ vọng được dùng, chưa có redemption/cost thực tế và chưa tính lợi ích tương lai hay Citi Bike.",
              "", "## Hai ví dụ cần tự giải thích", "",
              "100 chuyến nền, u=3%, hoàn toàn bộ và dùng hết: 103 credit ×$1,50=$154,50; 3 chuyến thêm đem $18 contribution; cost/extra=$51,50. Hòa vốn=33,33%.",
              "Chỉ trợ giá 30% chuyến nền, r=100%, a=100%: hòa vốn=10% toàn mẫu, tương đương 33,33% trên nhóm đủ điều kiện. Không dùng ngưỡng 10% cho KPI uplift đo riêng nhóm eligible. Đổi targeting phải ước tính lại uplift, không giả định đáp ứng giữ nguyên.",
              "", "## Sản phẩm và giới hạn", "",
              "Excel riêng có nguồn counts, công thức thị phần, input chỉnh được và sensitivity hòa vốn. Notebook tự chứa các phép tính và xuất CSV/JSON; không cần Excel hay builder để chạy trên Colab.",
              "Không có customer ID, credit redemption, retention hoặc lợi nhuận đóng góp trong dữ liệu công khai. Khác mùa/thời tiết, cạnh tranh và nhóm đối chứng hưởng credit làm giả định DiD chưa được kiểm chứng. Kết quả dùng để thiết kế thử nghiệm, không phê duyệt chi phí chiến dịch thật.",
              "Nguồn credit: [Lyft](https://www.lyft.com/blog/posts/navigating-the-new-nyc-congestion-fee-with-lyft). Nguồn volume: daily_segment.csv từ NYC TLC, quy tắc trong trip_data_quality.md.", ""]
    (root / "docs/lyft_credit_report.md").write_text("\n".join(lines))


def write_credit_experiment_brief(root):
    text = """# Campaign brief - Targeted congestion credit test

**Hypothesis.** Offering a $1.50 future-ride credit to eligible users with a pre-test history of short, low-fare zone trips increases contribution at lower organic-trip subsidy cost than blanket issuance.

**Eligibility and assignment.** Define eligibility from the preceding 28 days before assignment; do not classify users from post-treatment fares or trips. Randomly assign 90% of eligible users to treatment and 10% to holdout. Keep assignment stable per user. The public TLC data has no user IDs, so this is a proposed design, not an executed test or generated targeting list. Trip coverage s=30% is an assumption to validate, not 30% of users.

**Primary metric.** Zone trips per assigned eligible user, including zero-trip users, analyzed by intention to treat. Uplift is (treatment rate/control rate)-1 on the eligible-user denominator. Also measure all Lyft trips per user to detect displacement outside the zone. Do not compare eligible-user uplift directly with a whole-market 10% threshold.

**Economics and guardrails.** Measure actual credit issued/redeemed and contribution using approved internal cost definitions. Primary economic outcome: incremental contribution per assigned user after redeemed-credit cost. Guardrails: waiting time, cancellation rate and contribution per trip. Marketplace spillovers may affect the holdout; random assignment reduces confounding but does not remove every interference assumption. Margin/redemption/cancellation metrics require internal platform data.

**Duration and sample.** At least 14 issuance days for two of every weekday, plus a redemption follow-up covering the seven-day credit validity and issuance timing. Final duration and user count come from a power calculation using pre-test variance and a prespecified minimum detectable effect; public aggregate TLC data cannot supply a defensible sample-size calculation.

**Decision.** Before launch, agree sample size, guardrail limits, contribution definition and a fixed analysis date. Expand only if the confidence interval for incremental net contribution supports a positive effect and guardrails remain within agreed limits; otherwise do not expand and stop or redesign the campaign. Under m=$6, c=$1.50, redemption=100%, and all extra trips credited, the illustrative break-even is 33.33% eligible uplift. If eligible baseline trips are 30% of all baseline trips, that equals 10% whole-base uplift. Recompute the threshold from measured margin/redemption; do not treat either number as an unconditional launch rule.

This brief is a design deliverable. No live campaign, customer messaging or account changes were made.
"""
    (Path(root) / "docs/targeted_credit_experiment_brief.md").write_text(text)


if __name__ == "__main__":
    analyze_lyft_credit(Path(__file__).resolve().parents[1])
