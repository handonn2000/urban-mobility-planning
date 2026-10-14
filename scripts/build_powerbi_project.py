"""Build the Power BI project (PBIP: TMDL semantic model + PBIR report) from the processed tables."""
from pathlib import Path
import base64
import json
import math
import shutil
import sys
import uuid

import pandas as pd

NAME = "UrbanMobility"
NAMESPACE = uuid.UUID("6f1f2d3e-8a51-4c62-9a1e-3b7c0f5d2a10")
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
SEGMENTS = [("Uber_zone", "Uber", "Zone", "Uber zone", 1), ("Uber_outside", "Uber", "Outside", "Uber outside", 2),
            ("Lyft_zone", "Lyft", "Zone", "Lyft zone", 3), ("Lyft_outside", "Lyft", "Outside", "Lyft outside", 4)]


def tag(*parts):
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))


def segment_key(operator, zone):
    zone = str(zone).lower() == "true"
    return f"{operator}_{'zone' if zone else 'outside'}"


# ---------------------------------------------------------------- tables

def build_tables(root):
    p = root / "data/processed"
    daily = pd.read_csv(p / "daily_segment.csv", parse_dates=["request_date"])
    holidays = pd.read_csv(root / "data/external/holidays.csv", parse_dates=["date"])
    hourly = pd.read_csv(p / "hourly_city.csv", parse_dates=["request_date"])
    tables = {}

    dates = pd.DataFrame({"Date": pd.date_range("2024-01-01", "2025-02-28")})
    names = dict(zip(holidays.date, holidays.holiday_name))
    dates["Year"] = dates.Date.dt.year
    dates["MonthNumber"] = dates.Date.dt.month
    dates["Month"] = dates.Date.dt.strftime("%b")
    dates["Weekday"] = dates.Date.dt.dayofweek + 1
    dates["DayName"] = dates.Date.dt.strftime("%a")
    dates["Holiday"] = dates.Date.map(names).fillna("")
    tables["DimDate"] = dates

    tables["DimSegment"] = pd.DataFrame(SEGMENTS, columns=["SegmentKey", "Operator", "ZoneFlag", "Segment", "SortOrder"])
    tables["DimMethod"] = pd.DataFrame([
        ("B1", "Same weekday last week", 1),
        ("B2", "Mean of the last two same weekdays (plan)", 2),
        ("B3", "B2 with the MLK factor on 17 Feb (scenario)", 3)], columns=["Method", "Description", "SortOrder"])

    fact = daily.assign(SegmentKey=[segment_key(o, z) for o, z in zip(daily.operator, daily.touches_zone)])
    tables["FactDaily"] = pd.DataFrame({
        "Date": fact.request_date, "SegmentKey": fact.SegmentKey, "Trips": fact.trips,
        "ShortTrips": fact.short_trips, "LowFareTrips": fact.low_fare_trips,
        "EconomicsTrips": fact.valid_economics_trips, "FareSum": fact.total_base_fare.round(2),
        "DriverPaySum": fact.total_driver_pay.round(2), "MedianWait": fact.median_wait_minutes.round(3)})

    forecast = pd.read_csv(p / "forecast_week.csv", parse_dates=["request_date"])
    forecast["SegmentKey"] = [segment_key(o, z) for o, z in zip(forecast.operator, forecast.touches_zone)]
    actual = tables["FactDaily"].set_index(["Date", "SegmentKey"]).Trips
    long = forecast.melt(id_vars=["request_date", "SegmentKey"], value_vars=["B1", "B2", "B3"],
                         var_name="Method", value_name="Forecast")
    long["Actual"] = [actual[(d, s)] for d, s in zip(long.request_date, long.SegmentKey)]
    tables["FactForecast"] = long.rename(columns={"request_date": "Date"}).assign(Forecast=lambda d: d.Forecast.round(2))

    city = pd.read_csv(p / "forecast_band_city.csv", parse_dates=["request_date"]).dropna(subset=["expected_trips"])
    tables["FactCityForecast"] = pd.DataFrame({
        "Date": city.request_date, "Trips": city.trips, "Expected": city.expected_trips.round(1),
        "BandLower": (city.expected_trips * (city.center_log - city.half_width_log).map(math.exp)).round(1),
        "BandUpper": (city.expected_trips * (city.center_log + city.half_width_log).map(math.exp)).round(1)})

    weather = hourly.groupby("request_date").agg(rain_h=("rain_mm", lambda x: int((x >= 0.5).sum())),
                                                 snow_h=("snowfall_cm", lambda x: int((x > 0).sum())))
    alerts = pd.read_csv(p / "forecast_band_alerts.csv", parse_dates=["request_date"])
    alerts = alerts[alerts.outside_band.astype(str).str.lower() == "true"].copy()

    def describe(day):
        return f"{day:%d %b}: rain {weather.loc[day, 'rain_h']}h, snow {weather.loc[day, 'snow_h']}h"

    rows = []
    for r in alerts.itertuples(index=False):
        refs = [pd.Timestamp(d) for d in str(r.reference_dates).split(",") if d and d != "nan"]
        bad_reference = any(weather.loc[d, "rain_h"] > 0 or weather.loc[d, "snow_h"] > 0 for d in refs)
        reason = ("Holiday" if pd.notna(r.known_event) and str(r.known_event).strip()
                  else "Bad weather on a reference day" if bad_reference else "Unexplained")
        rows.append({"Date": r.request_date, "Segment": dict((s[0], s[3]) for s in SEGMENTS)[segment_key(r.operator, r.touches_zone)],
                     "Trips": int(r.trips), "Expected": round(float(r.expected_trips)), "ZScore": round(float(r.z_score), 2),
                     "Reason": reason, "ReferenceDays": "; ".join(describe(d) for d in refs)})
    tables["FactAlertList"] = pd.DataFrame(rows)

    gaps = pd.read_csv(p / "fee_matched_day_gaps.csv", parse_dates=["date_2025", "date_2024"])
    tables["FactFeeGap"] = pd.DataFrame({
        "Date": gaps.date_2025, "BeforeFee": (gaps.date_2025 < "2025-01-05").astype(int), "GapAll": gaps.All_gap.round(6)})

    effect = pd.read_csv(p / "fee_effect.csv")
    labels = {"all_trips": "All trips", "short_trips": "Short trips (<2 mi)", "low_fare_trips": "Low-fare trips (<=$11.63)"}
    tables["FactFeeEffect"] = pd.DataFrame({
        "Operator": effect.operator, "TripGroup": effect.trip_group.map(labels),
        "TripGroupOrder": effect.trip_group.map({"all_trips": 1, "short_trips": 2, "low_fare_trips": 3}),
        "Gap": effect.relative_growth_gap.round(6)})

    growth = pd.read_csv(p / "gmv_volume_price_decomposition.csv")
    growth = growth[growth.before.eq("jan_2024")]
    growth["Segment"] = [("All trips" if o == "All" else dict((s[0], s[3]) for s in SEGMENTS)[segment_key(o, z)])
                         for o, z in zip(growth.operator, growth.touches_zone)]
    tables["FactGrowth"] = pd.DataFrame({
        "Segment": growth.Segment, "SortOrder": range(1, len(growth) + 1),
        "TripGrowth": growth.trips_growth.round(6), "FareGrowth": growth.avg_fare_growth.round(6),
        "GMVGrowth": growth.gmv_proxy_growth.round(6)})

    share = pd.read_csv(p / "lyft_share_weekly.csv", parse_dates=["week_start"])
    tables["FactWeeklyShare"] = pd.DataFrame({
        "WeekStart": share.week_start,
        "ZoneGroup": share.touches_zone.astype(str).str.lower().map({"true": "Touching the zone", "false": "Outside the zone"}),
        "LyftTrips": share.lyft_trips, "MarketTrips": share.market_trips})

    rain = pd.read_csv(p / "rain_factors.csv")
    rain = rain[~rain.weather_group.isin(["dry", "drizzle"])]
    tables["FactWeather"] = pd.DataFrame({
        "Study": rain.study.str.replace("_", " "),
        "Weather": rain.weather_group.map({"light_rain": "Rain 0.5-2 mm/h", "moderate_or_heavy_rain": "Rain > 2 mm/h", "snow": "Snow"}),
        "Hours": rain.usable_trip_hours, "TripsFactor": rain.trips_factor.round(4), "WaitFactor": rain.wait_factor.round(4),
        "SmallSample": rain.trip_sample_under_20_hours.astype(str).str.lower().map({"true": "Yes", "false": "No"})})

    pre = pd.read_csv(p / "fee_pre_period_check.csv").set_index("operator")
    boot = pd.read_csv(p / "fee_gap_bootstrap.csv")
    boot = boot[(boot.operator == "All") & (boot.method == "day_pairs")].iloc[0]
    credit = pd.read_csv(p / "lyft_credit_share_sensitivity.csv").set_index("comparison")
    cost = pd.read_csv(p / "lyft_credit_cost_vs_gmv.csv")
    cost = cost[(cost.period == "credit_comparison_window") & (cost.redemption == 1.0)].iloc[0]
    yoy = pd.read_csv(p / "gmv_volume_price_decomposition.csv")
    yoy = yoy[(yoy.before == "jan_2024") & (yoy.operator == "All")].iloc[0]
    uplift = credit.loc["planned_three_weeks", "approx_uplift_vs_post_share"]
    extra = 100 * uplift
    watchlist = pd.read_csv(p / "watchlist.csv")
    tables["FactKPI"] = pd.DataFrame([{
        "TripGrowthYoY": round(yoy.trips_growth, 6),
        "GapBeforeFee": round(pre.loc["All", "pre_fee_gap"], 6), "GapWithFee": round(pre.loc["All", "main_window_gap"], 6),
        "GapCILow": round(boot.ci_low_2_5, 6), "GapCIHigh": round(boot.ci_high_97_5, 6),
        "ShareGapPP": round(credit.loc["planned_three_weeks", "share_difference_percentage_points"], 4),
        "UpliftProxy": round(uplift, 6),
        "CostPerExtraTrip": round((100 + extra) * 1.5 / extra, 2),
        "BreakevenBlanket": round(1.5 / 4.5, 6), "BreakevenTargeted": round(0.3 * 1.5 / 4.5, 6),
        "CreditCostShareZoneGMV": round(cost.credit_cost_share_of_lyft_zone_gmv, 6),
        "FixedRuleAlerts": len(watchlist)}])
    return tables


# ---------------------------------------------------------------- semantic model (TMDL)

M_TYPES = {"int64": "Int64.Type", "decimal": "Currency.Type", "dateTime": "type date", "string": "type text"}


def dtype(series):
    if pd.api.types.is_datetime64_any_dtype(series):
        return "dateTime"
    if pd.api.types.is_integer_dtype(series):
        return "int64"
    if pd.api.types.is_float_dtype(series):
        return "decimal"
    return "string"


def partition(name, frame):
    csv = frame.to_csv(index=False, date_format="%Y-%m-%d", lineterminator="\n")
    payload = base64.b64encode(csv.encode("utf-8")).decode("ascii")
    types = ", ".join(f'{{"{c}", {M_TYPES[dtype(frame[c])]}}}' for c in frame.columns)
    lines = ["let",
             f'    Source = Csv.Document(Binary.FromText("{payload}", BinaryEncoding.Base64), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
             "    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
             f'    Typed = Table.TransformColumnTypes(Headers, {{{types}}}, "en-US")',
             "in",
             "    Typed"]
    body = "\n".join("\t\t\t\t" + line for line in lines)
    return f"\tpartition {name} = m\n\t\tmode: import\n\t\tsource =\n{body}\n"


def quote(name):
    return name if name.replace("_", "").isalnum() else "'" + name.replace("'", "''") + "'"


def table_tmdl(name, frame, measures=(), formats=None, hidden=(), sort_by=None, date_table=False):
    formats = formats or {}
    out = [f"table {name}", f"\tlineageTag: {tag(name)}"]
    if date_table:
        out.append("\tdataCategory: Time")
    out.append("")
    for m_name, expression, fmt in measures:
        out.append(f"\tmeasure {quote(m_name)} = {expression}")
        if fmt:
            out.append(f"\t\tformatString: {fmt}")
        out += [f"\t\tlineageTag: {tag(name, 'measure', m_name)}", ""]
    for column in frame.columns:
        kind = dtype(frame[column])
        out.append(f"\tcolumn {quote(column)}")
        out.append(f"\t\tdataType: {kind}")
        if column in KEYS.get(name, ()):
            out.append("\t\tisKey")
        if column in hidden:
            out.append("\t\tisHidden")
            if column not in SORT_TARGETS:
                out.append("\t\tisAvailableInMdx: false")
        fmt = formats.get(column, "yyyy-mm-dd" if kind == "dateTime" else "0" if kind == "int64" else None)
        if fmt:
            out.append(f"\t\tformatString: {fmt}")
        out += [f"\t\tlineageTag: {tag(name, column)}", "\t\tsummarizeBy: none", f"\t\tsourceColumn: {column}"]
        if sort_by and column in sort_by:
            out.append(f"\t\tsortByColumn: {sort_by[column]}")
        out.append("")
        if kind == "dateTime":
            out += ["\t\tannotation UnderlyingDateTimeDataType = Date", ""]
    out.append(partition(name, frame))
    out.append("\tannotation PBI_ResultType = Table\n")
    return "\n".join(out)


PCT, NUM, DEC2, USD = "#,0.0%;-#,0.0%;#,0.0%", "#,0", "0.00", "\\$#,0.00"

MEASURES = {
    "FactDaily": [
        ("Trips", "SUM(FactDaily[Trips])", NUM),
        ("Average fare", "DIVIDE(SUM(FactDaily[FareSum]), SUM(FactDaily[EconomicsTrips]))", USD),
        ("Platform share", "DIVIDE(SUM(FactDaily[FareSum]) - SUM(FactDaily[DriverPaySum]), SUM(FactDaily[FareSum]))", PCT),
        ("Short trip share", "DIVIDE(SUM(FactDaily[ShortTrips]), [Trips])", PCT),
        ("Low-fare trip share", "DIVIDE(SUM(FactDaily[LowFareTrips]), [Trips])", PCT),
        ("Median wait (one day and segment)", "IF(HASONEVALUE(DimDate[Date]) && HASONEVALUE(DimSegment[SegmentKey]), SELECTEDVALUE(FactDaily[MedianWait]))", "#,0.0"),
        ("Trips same weekday last year", "CALCULATE([Trips], DATEADD(DimDate[Date], -364, DAY))", NUM),
        ("Trips vs last year", "DIVIDE([Trips] - [Trips same weekday last year], [Trips same weekday last year])", PCT),
    ],
    "FactCityForecast": [
        ("City trips", "SUM(FactCityForecast[Trips])", NUM),
        ("City forecast", "SUM(FactCityForecast[Expected])", NUM),
        ("Band lower", "SUM(FactCityForecast[BandLower])", NUM),
        ("Band upper", "SUM(FactCityForecast[BandUpper])", NUM),
    ],
    "FactAlertList": [
        ("Band alerts", "COUNTROWS(FactAlertList)", NUM),
        ("Open alerts", 'CALCULATE(COUNTROWS(FactAlertList), FactAlertList[Reason] = "Unexplained")', NUM),
    ],
    "FactFeeGap": [
        ("Gap before fee", "CALCULATE(AVERAGE(FactFeeGap[GapAll]), FactFeeGap[BeforeFee] = 1)", PCT),
        ("Gap with fee", "CALCULATE(AVERAGE(FactFeeGap[GapAll]), FactFeeGap[BeforeFee] = 0)", PCT),
        ("Window estimate", "IF(NOT ISEMPTY(FactFeeGap) && MAX(DimDate[Date]) >= DATE(2025, 1, 6) && MIN(DimDate[Date]) <= DATE(2025, 1, 26), MAX(FactKPI[GapWithFee]))", PCT),
    ],
    "FactFeeEffect": [("Zone vs outside gap", "AVERAGE(FactFeeEffect[Gap])", PCT)],
    "FactGrowth": [
        ("Trip growth", "SUM(FactGrowth[TripGrowth])", PCT),
        ("Average fare growth", "SUM(FactGrowth[FareGrowth])", PCT),
        ("GMV proxy growth", "SUM(FactGrowth[GMVGrowth])", PCT),
    ],
    "FactWeeklyShare": [("Lyft share", "DIVIDE(SUM(FactWeeklyShare[LyftTrips]), SUM(FactWeeklyShare[MarketTrips]))", PCT)],
    "FactForecast": [
        ("Forecast trips", "IF(HASONEVALUE(DimMethod[Method]), SUM(FactForecast[Forecast]))", NUM),
        ("Actual trips", 'CALCULATE(SUM(FactForecast[Actual]), DimMethod[Method] = "B2")', NUM),
        ("Plan B2", 'CALCULATE(SUM(FactForecast[Forecast]), DimMethod[Method] = "B2")', NUM),
        ("Scenario B3", 'CALCULATE(SUM(FactForecast[Forecast]), DimMethod[Method] = "B3")', NUM),
        ("Last week B1", 'CALCULATE(SUM(FactForecast[Forecast]), DimMethod[Method] = "B1")', NUM),
        ("WAPE", "IF(HASONEVALUE(DimMethod[Method]), DIVIDE(SUMX(FactForecast, ABS(FactForecast[Forecast] - FactForecast[Actual])), SUM(FactForecast[Actual])))", "0.00%"),
        ("Bias", "IF(HASONEVALUE(DimMethod[Method]), DIVIDE(SUMX(FactForecast, FactForecast[Forecast] - FactForecast[Actual]), SUM(FactForecast[Actual])))", "+0.00%;-0.00%;0.00%"),
        ("MAE", "IF(HASONEVALUE(DimMethod[Method]), AVERAGEX(FactForecast, ABS(FactForecast[Forecast] - FactForecast[Actual])))", NUM),
        ("WAPE B2", 'CALCULATE([WAPE], DimMethod[Method] = "B2")', "0.00%"),
    ],
    "FactWeather": [],
    "FactKPI": [
        ("Trip growth YoY", "MAX(FactKPI[TripGrowthYoY])", "+0.0%;-0.0%;0.0%"),
        ("Gap before fee 2-4 Jan", "MAX(FactKPI[GapBeforeFee])", PCT),
        ("Gap 6-26 Jan", "MAX(FactKPI[GapWithFee])", PCT),
        ("Gap 95% CI", 'FORMAT(MAX(FactKPI[GapCILow]), "0.0%") & " to " & FORMAT(MAX(FactKPI[GapCIHigh]), "0.0%")', None),
        ("Lyft zone share gap pp", "MAX(FactKPI[ShareGapPP])", "#,0.0"),
        ("Credit uplift proxy", "MAX(FactKPI[UpliftProxy])", PCT),
        ("Credit cost per extra trip", "MAX(FactKPI[CostPerExtraTrip])", USD),
        ("Break-even uplift blanket", "MAX(FactKPI[BreakevenBlanket])", PCT),
        ("Break-even uplift targeted", "MAX(FactKPI[BreakevenTargeted])", PCT),
        ("Max credit cost share of zone GMV", "MAX(FactKPI[CreditCostShareZoneGMV])", PCT),
        ("Fixed 7% rule alerts", "MAX(FactKPI[FixedRuleAlerts])", NUM),
    ],
}

FORMATS = {
    "FactDaily": {"Trips": NUM, "FareSum": NUM, "DriverPaySum": NUM, "MedianWait": "0.0"},
    "FactCityForecast": {"Trips": NUM, "Expected": NUM, "BandLower": NUM, "BandUpper": NUM},
    "FactKPI": {c: PCT for c in ("TripGrowthYoY", "GapBeforeFee", "GapWithFee", "GapCILow", "GapCIHigh",
                                 "UpliftProxy", "BreakevenBlanket", "BreakevenTargeted", "CreditCostShareZoneGMV")}
               | {"ShareGapPP": "0.00", "CostPerExtraTrip": USD, "FixedRuleAlerts": NUM},
    "FactWeeklyShare": {"LyftTrips": NUM, "MarketTrips": NUM},
    "FactAlertList": {"Trips": NUM, "Expected": NUM, "ZScore": "+0.0;-0.0"},
    "FactFeeGap": {"GapAll": PCT},
    "FactFeeEffect": {"Gap": PCT},
    "FactGrowth": {"TripGrowth": PCT, "FareGrowth": PCT, "GMVGrowth": PCT},
    "FactWeather": {"TripsFactor": "0.000", "WaitFactor": "0.000"},
    "FactForecast": {"Forecast": NUM, "Actual": NUM},
}
HIDDEN = {"FactDaily": ["Date", "SegmentKey", "Trips", "ShortTrips", "LowFareTrips", "EconomicsTrips", "FareSum", "DriverPaySum", "MedianWait"],
          "FactForecast": ["Date", "SegmentKey", "Method", "Forecast", "Actual"],
          "FactCityForecast": ["Date", "Trips", "Expected", "BandLower", "BandUpper"],
          "FactFeeGap": ["Date", "BeforeFee", "GapAll"],
          "FactKPI": ["TripGrowthYoY", "GapBeforeFee", "GapWithFee", "GapCILow", "GapCIHigh", "ShareGapPP",
                      "UpliftProxy", "CostPerExtraTrip", "BreakevenBlanket", "BreakevenTargeted",
                      "CreditCostShareZoneGMV", "FixedRuleAlerts"],
          "FactGrowth": ["SortOrder", "TripGrowth", "FareGrowth", "GMVGrowth"],
          "FactWeeklyShare": ["LyftTrips", "MarketTrips"],
          "FactFeeEffect": ["TripGroupOrder", "Gap"],
          "DimSegment": ["SegmentKey", "SortOrder"], "DimMethod": ["SortOrder"]}
KEYS = {"DimDate": ["Date"], "DimSegment": ["SegmentKey"], "DimMethod": ["Method"]}
SORT_TARGETS = {"SortOrder", "TripGroupOrder", "Weekday", "MonthNumber"}
SORT = {"DimDate": {"DayName": "Weekday", "Month": "MonthNumber"}, "DimSegment": {"Segment": "SortOrder"},
        "DimMethod": {"Method": "SortOrder"}, "FactFeeEffect": {"TripGroup": "TripGroupOrder"},
        "FactGrowth": {"Segment": "SortOrder"}}
RELATIONSHIPS = [("FactDaily", "Date", "DimDate", "Date"), ("FactDaily", "SegmentKey", "DimSegment", "SegmentKey"),
                 ("FactForecast", "Date", "DimDate", "Date"), ("FactForecast", "SegmentKey", "DimSegment", "SegmentKey"),
                 ("FactForecast", "Method", "DimMethod", "Method"), ("FactCityForecast", "Date", "DimDate", "Date"),
                 ("FactFeeGap", "Date", "DimDate", "Date")]


def write_semantic_model(folder, tables):
    definition = folder / "definition"
    (definition / "tables").mkdir(parents=True)
    (folder / "definition.pbism").write_text(json.dumps({
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2) + "\n")
    (definition / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1601\n\n")
    order = list(tables)
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
             "annotation PBI_QueryOrder = " + json.dumps(order, separators=(",", ":")), "",
             "annotation PBI_ProTooling = [\"DevMode\"]", ""]
    model += [f"ref table {name}" for name in order]
    (definition / "model.tmdl").write_text("\n".join(model) + "\n\n")
    for name, frame in tables.items():
        text = table_tmdl(name, frame, MEASURES.get(name, []), FORMATS.get(name), HIDDEN.get(name, ()),
                          SORT.get(name), date_table=name == "DimDate")
        (definition / "tables" / f"{name}.tmdl").write_text(text)
    rel = []
    for f_table, f_col, t_table, t_col in RELATIONSHIPS:
        rel += [f"relationship {tag('rel', f_table, f_col, t_table)}",
                f"\tfromColumn: {f_table}.{f_col}", f"\ttoColumn: {t_table}.{t_col}", ""]
    (definition / "relationships.tmdl").write_text("\n".join(rel) + "\n")


# ---------------------------------------------------------------- report (PBIR)

def lit(value):
    return {"expr": {"Literal": {"Value": value}}}


def text_lit(text):
    return lit("'" + text.replace("'", "''") + "'")


def column(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def measure(entity, prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def projection(field, active=False):
    inner = next(iter(field.values()))
    prop = inner["Property"]
    item = {"field": field, "queryRef": f"{inner['Expression']['SourceRef']['Entity']}.{prop}", "nativeQueryRef": prop}
    if active:
        item["active"] = True
    return item


class Page:
    def __init__(self, name, display, filters=None):
        self.name, self.display, self.filters, self.visuals = name, display, filters, []

    def add(self, name, x, y, w, h, visual):
        z = 1000 * (len(self.visuals) + 1)
        self.visuals.append({"$schema": f"{SCHEMA}/item/report/definition/visualContainer/2.8.0/schema.json",
                             "name": name, "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
                             "visual": visual})


def container_objects(title, alt):
    objects = {"general": [{"properties": {"altText": text_lit(alt)}}]}
    objects["title"] = [{"properties": {"show": lit("true" if title else "false"), "text": text_lit(title or "")}}]
    return objects


def chart(kind, roles, title, alt, sort=None):
    query = {"queryState": {role: {"projections": items} for role, items in roles.items()}}
    if sort:
        query["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": True}
    return {"visualType": kind, "query": query, "visualContainerObjects": container_objects(title, alt),
            "drillFilterOtherVisuals": True}


def card(title, entity, prop, alt=None):
    visual = chart("cardVisual", {"Data": [projection(measure(entity, prop))]}, title, alt or title)
    visual["objects"] = {"label": [{"properties": {"show": lit("false")}, "selector": {"id": "default"}}]}
    return visual


def textbox(paragraphs, alt):
    built = []
    for paragraph in paragraphs:
        runs = []
        for run in (paragraph if isinstance(paragraph, list) else [paragraph]):
            if isinstance(run, tuple):
                text, style = run
                runs.append({"value": text, "textStyle": style})
            else:
                runs.append({"value": run})
        built.append({"textRuns": runs})
    return {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": built}}]},
            "visualContainerObjects": container_objects(None, alt), "drillFilterOtherVisuals": True}


def slicer(entity, prop, title):
    visual = chart("slicer", {"Values": [projection(column(entity, prop), active=True)]}, title, f"Slicer to filter the page by {title.lower()}")
    visual["objects"] = {"data": [{"properties": {"mode": text_lit("Dropdown")}}]}
    return visual


def year_filter(year):
    return {"filters": [{"name": "year_filter", "field": column("DimDate", "Year"), "type": "Categorical",
                         "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "DimDate", "Type": 0}],
                                    "Where": [{"Condition": {"In": {
                                        "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "Year"}}],
                                        "Values": [[{"Literal": {"Value": f"{year}L"}}]]}}}]}}]}


BOLD = {"fontWeight": "bold"}
HEADER = {"fontWeight": "bold", "fontSize": "16pt"}


def header(page, title, subtitle, width=1240):
    page.add("header", 20, 8, width, 56, textbox([[(title, HEADER)], subtitle], "Page title and reading guide"))


def build_pages():
    pages = []

    p = Page("summary", "Summary")
    header(p, "NYC ride-hailing demand planning",
           "Decision date 16 Feb 2025. Completed Uber and Lyft trips, Jan 2024 and Jan-Feb 2025 (NYC TLC).")
    cards = [("Completed trips analysed", "FactDaily", "Trips"), ("Trip growth, matched Jan windows", "FactKPI", "Trip growth YoY"),
             ("Holiday-week plan (B2)", "FactForecast", "Plan B2"), ("Backtest WAPE, B2", "FactForecast", "WAPE B2"),
             ("Zone vs outside gap, 2-4 Jan (no fee)", "FactKPI", "Gap before fee 2-4 Jan"),
             ("Zone vs outside gap, 6-26 Jan", "FactKPI", "Gap 6-26 Jan"),
             ("Credit cost per extra trip ($6 contribution)", "FactKPI", "Credit cost per extra trip"),
             ("Alerts with the forecast band", "FactAlertList", "Band alerts")]
    for i, (title, entity, prop) in enumerate(cards):
        p.add(f"kpi_{i + 1}", 20 + (i % 4) * 312, 76 + (i // 4) * 122, 296, 110, card(title, entity, prop))
    p.add("findings", 20, 330, 800, 380, textbox([
        [("What happened in January", BOLD)],
        "Demand grew through volume: trips +2.0% year on year, average base fare +0.7%.",
        "Zone-touching trips grew 9.5% slower than outside trips, but the gap was already -13.8% on 2-4 January, before the fee. "
        "This comparison cannot attribute the gap to the $1.50 fee.",
        "Inside the zone Uber's average fare rose 9.2% while Lyft's fell 5.8%, a competing explanation for the shift between platforms.",
        "Lyft's zone share rose 1.6 pp while its credit ran (uplift proxy about 6%). At a $6 contribution each extra trip cost about $26 in credit.",
        "Heavy rain (> 2 mm/h) lifts trips about 8% and median wait about 1%.",
        "A fixed 7% alert rule fires on 118 of 360 segment-days; a forecast band fires on 9, and 7 of those are explained."],
        "Key findings"))
    p.add("recommendations", 840, 330, 420, 380, textbox([
        [("Recommendations", BOLD)],
        "Plan 4.87 M trips for 17-23 Feb with B2 and keep B3 as the holiday scenario.",
        "Replace blanket credit with a targeted test and a 10% randomized holdout.",
        "Move daily monitoring to the forecast band and skip bad-weather reference days.",
        "Add Nov-Dec 2023 and 2024 before quoting any fee effect.",
        "Treat rain as an operations trigger, not a demand multiplier."], "Recommendations"))
    pages.append(p)

    p = Page("monitoring", "Demand monitoring", year_filter(2025))
    header(p, "Demand monitoring, Jan-Feb 2025", "Year filter is set to 2025 in the filter pane; change it to 2024 to see January 2024.", 1000)
    p.add("segment_slicer", 1040, 14, 220, 52, slicer("DimSegment", "Segment", "Segment"))
    p.add("daily_trips", 20, 72, 760, 300, chart("lineChart", {
        "Category": [projection(column("DimDate", "Date"), active=True)],
        "Y": [projection(measure("FactDaily", "Trips"))],
        "Series": [projection(column("DimSegment", "Segment"))]},
        "Completed trips per day by segment", "Line chart of daily completed trips for the four segments"))
    for i, (title, prop) in enumerate([("Completed trips", "Trips"), ("Average base fare", "Average fare"),
                                       ("Platform share (1 - driver pay / fare)", "Platform share")]):
        p.add(f"monitor_kpi_{i + 1}", 800, 72 + i * 102, 460, 94, card(title, "FactDaily", prop))
    p.add("city_band", 20, 382, 760, 330, chart("lineChart", {
        "Category": [projection(column("DimDate", "Date"), active=True)],
        "Y": [projection(measure("FactCityForecast", m)) for m in ("City trips", "City forecast", "Band lower", "Band upper")]},
        "City trips vs two-week forecast and alert band (2.5 robust SD)",
        "Line chart of city-wide trips against the forecast and its alert band"))
    p.add("alerts", 800, 382, 460, 180, chart("tableEx", {"Values": [projection(column("FactAlertList", c)) for c in
                                                                     ("Date", "Segment", "ZScore", "Reason", "ReferenceDays")]},
        "Band alerts (Jan 2024 and Jan-Feb 2025)", "Table of the nine segment-days outside the forecast band"))
    p.add("weather", 800, 570, 460, 142, chart("tableEx", {"Values": [projection(column("FactWeather", c)) for c in
                                                                      ("Study", "Weather", "Hours", "TripsFactor", "WaitFactor", "SmallSample")]},
        "Weather factors vs matched dry hours", "Table of trip and wait ratios by weather group"))
    pages.append(p)

    p = Page("fee_credit", "Fee and credit")
    header(p, "Congestion fee and Lyft credit",
           "The zone vs outside gap existed before the fee started on 5 Jan, so it is not a fee effect. Comparisons are observational.")
    p.add("fee_gap_daily", 20, 72, 620, 300, chart("lineChart", {
        "Category": [projection(column("DimDate", "Date"), active=True)],
        "Y": [projection(measure("FactFeeGap", m)) for m in ("Gap before fee", "Gap with fee", "Window estimate")]},
        "Daily zone vs outside gap, 2025 vs same weekday 2024", "Line chart of the daily gap before and after the fee start"))
    for i, (title, prop) in enumerate([("Gap 2-4 Jan (no fee yet)", "Gap before fee 2-4 Jan"),
                                       ("Gap 6-26 Jan", "Gap 6-26 Jan"), ("95% bootstrap interval", "Gap 95% CI")]):
        p.add(f"fee_kpi_{i + 1}", 660 + i * 204, 72, 196, 96, card(title, "FactKPI", prop))
    p.add("fee_groups", 660, 176, 600, 196, chart("clusteredBarChart", {
        "Category": [projection(column("FactFeeEffect", "TripGroup"), active=True)],
        "Series": [projection(column("FactFeeEffect", "Operator"))],
        "Y": [projection(measure("FactFeeEffect", "Zone vs outside gap"))]},
        "Zone vs outside gap by trip group, 6-26 Jan 2025 vs 8-28 Jan 2024",
        "Bar chart of the relative gap by operator and trip group"))
    p.add("growth", 20, 382, 620, 330, chart("clusteredBarChart", {
        "Category": [projection(column("FactGrowth", "Segment"), active=True)],
        "Y": [projection(measure("FactGrowth", m)) for m in ("Trip growth", "Average fare growth")]},
        "Year-on-year growth: trips vs average fare", "Bar chart splitting year-on-year growth into volume and price"))
    p.add("lyft_share", 660, 382, 600, 220, chart("lineChart", {
        "Category": [projection(column("FactWeeklyShare", "WeekStart"), active=True)],
        "Y": [projection(measure("FactWeeklyShare", "Lyft share"))],
        "Series": [projection(column("FactWeeklyShare", "ZoneGroup"))]},
        "Lyft weekly share (credit issued 5-31 Jan; first and last weeks partial)",
        "Line chart of Lyft weekly share inside and outside the zone"))
    for i, (title, prop) in enumerate([("Lyft zone share gap (pp)", "Lyft zone share gap pp"),
                                       ("Credit uplift proxy", "Credit uplift proxy"),
                                       ("Break-even, blanket credit", "Break-even uplift blanket")]):
        p.add(f"credit_kpi_{i + 1}", 660 + i * 204, 612, 196, 100, card(title, "FactKPI", prop))
    pages.append(p)

    p = Page("forecast", "Holiday-week plan")
    header(p, "Holiday-week plan, 17-23 Feb 2025",
           "History ends at 16 Feb and counts only trips completed by then. B2 was chosen before the test week.", 1000)
    p.add("forecast_segment", 1040, 14, 220, 52, slicer("DimSegment", "Segment", "Segment"))
    p.add("plan_by_day", 20, 72, 620, 300, chart("clusteredColumnChart", {
        "Category": [projection(column("DimDate", "Date"), active=True)],
        "Y": [projection(measure("FactForecast", "Plan B2"))]},
        "Planned completed trips per day (B2)", "Column chart of planned trips per day"))
    p.add("forecast_vs_actual", 660, 72, 600, 300, chart("lineChart", {
        "Category": [projection(column("DimDate", "Date"), active=True)],
        "Y": [projection(measure("FactForecast", m)) for m in ("Actual trips", "Plan B2", "Scenario B3", "Last week B1")]},
        "Backtest: actual trips vs the three baselines", "Line chart comparing actual trips with B1, B2 and B3"))
    p.add("scores", 20, 382, 620, 160, chart("tableEx", {"Values": [
        projection(column("DimMethod", "Method")), projection(column("DimMethod", "Description")),
        projection(measure("FactForecast", "WAPE")), projection(measure("FactForecast", "Bias")),
        projection(measure("FactForecast", "MAE"))]},
        "Backtest accuracy (WAPE = sum of absolute errors / sum of actuals)", "Table of WAPE, bias and MAE by method"))
    for i, (title, prop) in enumerate([("Plan B2, week", "Plan B2"), ("Holiday scenario B3, week", "Scenario B3"),
                                       ("Actual trips, week", "Actual trips")]):
        p.add(f"forecast_kpi_{i + 1}", 660 + i * 204, 382, 196, 100, card(title, "FactForecast", prop))
    p.add("forecast_reading", 20, 552, 1240, 160, textbox([
        [("Reading", BOLD)],
        "B2 had the lowest error over the week (WAPE 3.48%) and on Presidents' Day itself (1.41%).",
        "The MLK factor (B3) made 17 Feb worse in three of four segments: Presidents' Day did not behave like MLK.",
        "The largest miss is Uber zone trips on Sunday 23 Feb (about 171k planned, 147k actual); its reference day 16 Feb had 17 hours of rain."],
        "Forecast reading"))
    pages.append(p)
    return pages


def write_report(folder, pages):
    definition = folder / "definition"
    (definition / "pages").mkdir(parents=True)
    (folder / "definition.pbir").write_text(json.dumps({
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json", "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2) + "\n")
    (definition / "version.json").write_text(json.dumps({
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2) + "\n")
    (definition / "report.json").write_text(json.dumps({
        "$schema": f"{SCHEMA}/item/report/definition/report/3.2.0/schema.json", "themeCollection": {}}, indent=2) + "\n")
    (definition / "pages/pages.json").write_text(json.dumps({
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name}, indent=2) + "\n")
    for page in pages:
        folder_page = definition / "pages" / page.name
        (folder_page / "visuals").mkdir(parents=True)
        body = {"$schema": f"{SCHEMA}/item/report/definition/page/2.1.0/schema.json", "name": page.name,
                "displayName": page.display, "displayOption": "FitToPage", "height": 720, "width": 1280}
        if page.filters:
            body["filterConfig"] = page.filters
        (folder_page / "page.json").write_text(json.dumps(body, indent=2) + "\n")
        for visual in page.visuals:
            (folder_page / "visuals" / visual["name"]).mkdir()
            (folder_page / "visuals" / visual["name"] / "visual.json").write_text(json.dumps(visual, indent=2) + "\n")


def build(root):
    root = Path(root)
    out = root / "powerbi"
    for item in [f"{NAME}.pbip", f"{NAME}.SemanticModel", f"{NAME}.Report", "data"]:
        target = out / item
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    out.mkdir(exist_ok=True)
    tables = build_tables(root)
    (out / "data").mkdir()
    for name, frame in tables.items():
        frame.to_csv(out / "data" / f"{name}.csv", index=False, date_format="%Y-%m-%d")
    write_semantic_model(out / f"{NAME}.SemanticModel", tables)
    write_report(out / f"{NAME}.Report", build_pages())
    (out / f"{NAME}.pbip").write_text(json.dumps({
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}}, indent=2) + "\n")
    print(f"Wrote {out / (NAME + '.pbip')}: {len(tables)} tables, {sum(len(v) for v in MEASURES.values())} measures.")
    return tables


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
