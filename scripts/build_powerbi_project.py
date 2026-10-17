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
# Only the numbers shown in the report slides (reports/UrbanMobility_Report.pdf) are loaded.

def wet_days(hourly):
    """Days with at least 3 hours of rain (>= 0.5 mm) or snow, the rule used to explain alerts."""
    day = hourly.groupby("request_date").agg(rain_h=("rain_mm", lambda x: int((x >= 0.5).sum())),
                                             snow_h=("snowfall_cm", lambda x: int((x > 0).sum())))
    return day, (day.rain_h + day.snow_h) >= 3


def build_tables(root):
    p = root / "data/processed"
    daily = pd.read_csv(p / "daily_segment.csv", parse_dates=["request_date"])
    holidays = pd.read_csv(root / "data/external/holidays.csv", parse_dates=["date"])
    hourly = pd.read_csv(p / "hourly_city.csv", parse_dates=["request_date"])
    names = dict(zip(holidays.date, holidays.holiday_name))
    segment_label = {s[0]: s[3] for s in SEGMENTS}
    tables = {}

    dates = pd.DataFrame({"Date": pd.date_range("2024-01-01", "2025-02-28")})
    dates["Holiday"] = dates.Date.map(names).fillna("")
    tables["DimDate"] = dates

    tables["DimSegment"] = pd.DataFrame([(s[0], s[3], s[4]) for s in SEGMENTS], columns=["SegmentKey", "Segment", "SortOrder"])
    tables["DimMethod"] = pd.DataFrame([
        ("B1", "Same weekday last week", 1),
        ("B2", "Mean of the last two same weekdays (plan)", 2),
        ("B3", "B2 with the MLK factor on 17 Feb", 3)], columns=["Method", "Description", "SortOrder"])

    daily["SegmentKey"] = [segment_key(o, z) for o, z in zip(daily.operator, daily.touches_zone)]
    tables["FactDaily"] = pd.DataFrame({"Date": daily.request_date, "SegmentKey": daily.SegmentKey, "TripCount": daily.trips})

    # Step 1, fee: zone trips in the matched windows and the expected 2025 level.
    def window(start, end):
        part = daily[daily.request_date.between(start, end)]
        return part.groupby(part.touches_zone.astype(str).str.lower() == "true").trips.sum()

    before, after = window("2024-01-08", "2024-01-28"), window("2025-01-06", "2025-01-26")
    outside_growth = after[False] / before[False] - 1
    expected = before[True] * (1 + outside_growth)
    tables["FactFeeWindow"] = pd.DataFrame({
        "Bar": ["2024 (8-28 Jan)", "Expected 2025", "Actual 2025 (6-26 Jan)"], "BarOrder": [1, 2, 3],
        "ZoneTrips": [int(before[True]), round(expected, 1), int(after[True])]})

    gaps = pd.read_csv(p / "fee_matched_day_gaps.csv", parse_dates=["date_2025"])
    gaps = gaps[gaps.date_2025 <= "2025-01-26"]
    tables["FactFeeGap"] = pd.DataFrame({
        "Date": gaps.date_2025, "Period": (gaps.date_2025 < "2025-01-05").map({True: "Before fee", False: "With fee"}),
        "GapAll": gaps.All_gap.round(6)})

    # Step 2, credit: Lyft share with and after the credit, inside and outside the zone.
    credit = pd.read_csv(p / "lyft_credit_period_comparison.csv")
    tables["FactLyftShare"] = pd.DataFrame({
        "Period": credit.period.map({"credit_issuance": "With credit (6-26 Jan)", "post_issuance": "After credit (3-23 Feb)"}),
        "PeriodOrder": credit.period.map({"credit_issuance": 1, "post_issuance": 2}),
        "ZoneGroup": credit.touches_zone.astype(str).str.lower().map({"true": "Touching the zone", "false": "Outside the zone"}),
        "LyftTrips": credit.lyft_trips, "MarketTrips": credit.market_trips})
    s = credit.assign(zone=credit.touches_zone.astype(str).str.lower() == "true").set_index(["period", "zone"]).lyft_share
    share_gap = (s[("credit_issuance", True)] - s[("post_issuance", True)]) - (s[("credit_issuance", False)] - s[("post_issuance", False)])
    uplift = share_gap / s[("post_issuance", True)]
    extra = 100 * uplift

    # Step 3, weather (summer 2024) and alerts.
    rain = pd.read_csv(p / "rain_factors.csv")
    rain = rain[(rain.study == "summer_2024") & rain.weather_group.isin(["light_rain", "moderate_or_heavy_rain"])]
    tables["FactWeather"] = pd.DataFrame({
        "Weather": rain.weather_group.map({"light_rain": "Light rain (0.5-2 mm/h)", "moderate_or_heavy_rain": "Heavy rain (> 2 mm/h)"}),
        "WeatherOrder": rain.weather_group.map({"light_rain": 1, "moderate_or_heavy_rain": 2}),
        "TripsFactor": rain.trips_factor.round(4), "WaitFactor": rain.wait_factor.round(4)})

    weather, wet = wet_days(hourly)
    alerts = pd.read_csv(p / "forecast_band_alerts.csv", parse_dates=["request_date"])
    alerts = alerts[alerts.outside_band.astype(str).str.lower() == "true"]
    rows = []
    for r in alerts.itertuples(index=False):
        refs = [pd.Timestamp(d) for d in str(r.reference_dates).split(",") if d and d != "nan"]
        reason = ("Holiday" if r.request_date in names
                  else "Rain or snow on a reference day" if any(wet[d] for d in refs) else "Unexplained")
        rows.append({"Date": r.request_date, "Segment": segment_label[segment_key(r.operator, r.touches_zone)],
                     "TripCount": int(r.trips), "Expected": round(float(r.expected_trips)), "Reason": reason,
                     "ReferenceDays": "; ".join(f"{d:%d %b}: rain {weather.rain_h[d]}h, snow {weather.snow_h[d]}h" for d in refs)})
    tables["FactAlertList"] = pd.DataFrame(rows)

    # Step 4, forecast: B1/B2/B3 against actual trips.
    forecast = pd.read_csv(p / "forecast_week.csv", parse_dates=["request_date"])
    forecast["SegmentKey"] = [segment_key(o, z) for o, z in zip(forecast.operator, forecast.touches_zone)]
    actual = tables["FactDaily"].set_index(["Date", "SegmentKey"]).TripCount
    long = forecast.melt(id_vars=["request_date", "SegmentKey"], value_vars=["B1", "B2", "B3"],
                         var_name="Method", value_name="Forecast")
    long["Actual"] = [actual[(d, s)] for d, s in zip(long.request_date, long.SegmentKey)]
    tables["FactForecast"] = long.rename(columns={"request_date": "Date"}).assign(Forecast=lambda d: d.Forecast.round(2))

    pre = pd.read_csv(p / "fee_pre_period_check.csv").set_index("operator")
    watchlist = pd.read_csv(p / "watchlist.csv")
    tables["FactKPI"] = pd.DataFrame([{
        "OutsideGrowth": round(outside_growth, 6),
        "GapBeforeFee": round(pre.loc["All", "pre_fee_gap"], 6), "GapWithFee": round(pre.loc["All", "main_window_gap"], 6),
        "ShareGapPP": round(100 * share_gap, 4), "UpliftProxy": round(uplift, 6),
        "CostPerExtraTrip": round((100 + extra) * 1.5 / extra, 2), "BreakevenUplift": round(1.5 / 4.5, 6),
        "HeavyRainUplift": round(float(rain[rain.weather_group == "moderate_or_heavy_rain"].trips_factor.iloc[0]) - 1, 6),
        "FixedRuleAlerts": len(watchlist)}])
    return tables


# ---------------------------------------------------------------- semantic model (TMDL)

M_TYPES = {"int64": "Int64.Type", "decimal": "Currency.Type", "double": "type number", "dateTime": "type date", "string": "type text"}


def dtype(series):
    if pd.api.types.is_datetime64_any_dtype(series):
        return "dateTime"
    if pd.api.types.is_integer_dtype(series):
        return "int64"
    if pd.api.types.is_float_dtype(series):
        # Fixed decimal keeps 4 decimal places; ratios need more, e.g. -0.138477 must not round to -0.1385.
        scaled = series.dropna() * 10_000
        return "decimal" if (scaled - scaled.round()).abs().max() < 1e-6 else "double"
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



PCT, SIGNED, NUM, USD = "#,0.0%;-#,0.0%;#,0.0%", "+0.0%;-0.0%;0.0%", "#,0", "\\$#,0.00"

MEASURES = {
    "FactDaily": [("Trips", "SUM(FactDaily[TripCount])", NUM)],
    "FactFeeWindow": [("Zone trips", "SUM(FactFeeWindow[ZoneTrips])", NUM)],
    "FactFeeGap": [("Daily gap", "SUM(FactFeeGap[GapAll])", PCT)],
    "FactLyftShare": [("Lyft share", "DIVIDE(SUM(FactLyftShare[LyftTrips]), SUM(FactLyftShare[MarketTrips]))", PCT)],
    "FactWeather": [
        ("Trips vs dry hours", "SUM(FactWeather[TripsFactor]) - 1", SIGNED),
        ("Wait vs dry hours", "SUM(FactWeather[WaitFactor]) - 1", SIGNED),
    ],
    "FactAlertList": [("Band alerts", "COUNTROWS(FactAlertList)", NUM)],
    "FactForecast": [
        ("Actual trips", 'CALCULATE(SUM(FactForecast[Actual]), DimMethod[Method] = "B2")', NUM),
        ("Plan B2", 'CALCULATE(SUM(FactForecast[Forecast]), DimMethod[Method] = "B2")', NUM),
        ("Plan vs actual", "DIVIDE([Plan B2] - [Actual trips], [Actual trips])", SIGNED),
        ("WAPE", "IF(HASONEVALUE(DimMethod[Method]), DIVIDE(SUMX(FactForecast, ABS(FactForecast[Forecast] - FactForecast[Actual])), SUM(FactForecast[Actual])))", PCT),
        ("Bias", "IF(HASONEVALUE(DimMethod[Method]), DIVIDE(SUMX(FactForecast, FactForecast[Forecast] - FactForecast[Actual]), SUM(FactForecast[Actual])))", SIGNED),
        ("WAPE B2", 'CALCULATE([WAPE], DimMethod[Method] = "B2")', PCT),
    ],
    "FactKPI": [
        ("Outside trip growth", "MAX(FactKPI[OutsideGrowth])", SIGNED),
        ("Gap before fee 2-4 Jan", "MAX(FactKPI[GapBeforeFee])", PCT),
        ("Gap 6-26 Jan", "MAX(FactKPI[GapWithFee])", PCT),
        ("Lyft zone share gap pp", "MAX(FactKPI[ShareGapPP])", "+0.0;-0.0"),
        ("Credit uplift", "MAX(FactKPI[UpliftProxy])", PCT),
        ("Credit cost per extra trip", "MAX(FactKPI[CostPerExtraTrip])", USD),
        ("Break-even uplift", "MAX(FactKPI[BreakevenUplift])", "0%"),
        ("Heavy rain trip uplift", "MAX(FactKPI[HeavyRainUplift])", SIGNED),
        ("Fixed 7% rule alerts", "MAX(FactKPI[FixedRuleAlerts])", NUM),
    ],
}

FORMATS = {
    "FactDaily": {"TripCount": NUM},
    "FactFeeWindow": {"ZoneTrips": NUM},
    "FactFeeGap": {"GapAll": PCT},
    "FactLyftShare": {"LyftTrips": NUM, "MarketTrips": NUM},
    "FactWeather": {"TripsFactor": "0.000", "WaitFactor": "0.000"},
    "FactAlertList": {"TripCount": NUM, "Expected": NUM},
    "FactForecast": {"Forecast": NUM, "Actual": NUM},
    "FactKPI": {c: PCT for c in ("OutsideGrowth", "GapBeforeFee", "GapWithFee", "UpliftProxy", "BreakevenUplift", "HeavyRainUplift")}
               | {"ShareGapPP": "0.00", "CostPerExtraTrip": USD, "FixedRuleAlerts": NUM},
}
HIDDEN = {"FactDaily": ["Date", "SegmentKey", "TripCount"],
          "FactFeeWindow": ["BarOrder", "ZoneTrips"],
          "FactFeeGap": ["Date", "GapAll"],
          "FactLyftShare": ["PeriodOrder", "LyftTrips", "MarketTrips"],
          "FactWeather": ["WeatherOrder", "TripsFactor", "WaitFactor"],
          "FactForecast": ["Date", "SegmentKey", "Method", "Forecast", "Actual"],
          "FactKPI": ["OutsideGrowth", "GapBeforeFee", "GapWithFee", "ShareGapPP", "UpliftProxy", "CostPerExtraTrip",
                      "BreakevenUplift", "HeavyRainUplift", "FixedRuleAlerts"],
          "DimSegment": ["SegmentKey", "SortOrder"], "DimMethod": ["SortOrder"]}
KEYS = {"DimDate": ["Date"], "DimSegment": ["SegmentKey"], "DimMethod": ["Method"]}
SORT_TARGETS = {"SortOrder", "BarOrder", "PeriodOrder", "WeatherOrder"}
SORT = {"DimSegment": {"Segment": "SortOrder"},
        "DimMethod": {"Method": "SortOrder"}, "FactFeeWindow": {"Bar": "BarOrder"},
        "FactLyftShare": {"Period": "PeriodOrder"}, "FactWeather": {"Weather": "WeatherOrder"}}
RELATIONSHIPS = [("FactDaily", "Date", "DimDate", "Date"), ("FactDaily", "SegmentKey", "DimSegment", "SegmentKey"),
                 ("FactForecast", "Date", "DimDate", "Date"), ("FactForecast", "SegmentKey", "DimSegment", "SegmentKey"),
                 ("FactForecast", "Method", "DimMethod", "Method"), ("FactFeeGap", "Date", "DimDate", "Date")]


def check_unique_names(tables):
    """Power BI requires measure names to be unique across all columns and measures of the model."""
    columns = {c.lower() for frame in tables.values() for c in frame.columns}
    measures = [m[0].lower() for items in MEASURES.values() for m in items]
    clashes = sorted({m for m in measures if m in columns} | {m for m in measures if measures.count(m) > 1})
    if clashes:
        raise ValueError(f"Measure names clash with columns or other measures: {clashes}")


def write_semantic_model(folder, tables):
    check_unique_names(tables)
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


EXACT, MILLIONS = "1D", "1000000D"


def card(title, entity, prop, alt=None, units=None, decimals=None):
    """units: None keeps Power BI's auto display units; EXACT shows the full number; MILLIONS shows e.g. 40.37M."""
    visual = chart("cardVisual", {"Data": [projection(measure(entity, prop))]}, title, alt or title)
    visual["objects"] = {"label": [{"properties": {"show": lit("false")}, "selector": {"id": "default"}}]}
    value = {}
    if units:
        value["labelDisplayUnits"] = lit(units)
    if decimals is not None:
        value["labelPrecision"] = lit(f"{decimals}L")
    if value:
        visual["objects"]["value"] = [{"properties": value, "selector": {"id": "default"}}]
    return visual


def no_totals(visual):
    visual["objects"] = {"total": [{"properties": {"totals": lit("false")}}]}
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
    visual = chart("slicer", {"Values": [projection(column(entity, prop), active=True)]}, None, f"Slicer to filter the page by {title.lower()}")
    visual["objects"] = {"data": [{"properties": {"mode": text_lit("Dropdown")}}]}
    return visual



BOLD = {"fontWeight": "bold"}
HEADER = {"fontWeight": "bold", "fontSize": "16pt"}


def header(page, title, subtitle, width=1240):
    page.add("header", 20, 4, width, 66, textbox([[(title, HEADER)], subtitle], "Page title and reading guide"))


def build_pages():
    pages = []

    p = Page("summary", "Summary")
    header(p, "How many trips does New York need in the Presidents' Day week?",
           "Plan made on 16 Feb 2025 for 17-23 Feb. Completed Uber and Lyft trips, Jan 2024 and Jan-Feb 2025 (NYC TLC).")
    cards = [("Completed trips analysed", "FactDaily", "Trips", EXACT),
             ("Zone vs outside gap before the fee (2-4 Jan)", "FactKPI", "Gap before fee 2-4 Jan", None),
             ("Credit cost per extra Lyft trip", "FactKPI", "Credit cost per extra trip", None),
             ("Heavy rain: trips vs dry hours", "FactKPI", "Heavy rain trip uplift", None),
             ("Alerts, fixed ±7% rule", "FactKPI", "Fixed 7% rule alerts", None),
             ("Alerts, segment band", "FactAlertList", "Band alerts", None),
             ("Plan B2, 17-23 Feb", "FactForecast", "Plan B2", EXACT),
             ("Forecast error (WAPE, B2)", "FactForecast", "WAPE B2", None)]
    for i, (title, entity, prop, units) in enumerate(cards):
        p.add(f"kpi_{i + 1}", 20 + (i % 4) * 312, 76 + (i // 4) * 122, 296, 110, card(title, entity, prop, units=units))
    p.add("findings", 20, 330, 800, 380, textbox([
        [("Results", BOLD)],
        "Fee: zone trips came in 9.5% below the expected level, but the gap was already -13.8% before the fee. Not proven.",
        "Credit: Lyft's zone share rose 1.6 points (about 6% more trips), at $25.88 per extra trip against a ~$6 margin.",
        "Rain: heavy rain lifts trips 7.7%; waiting time barely changes.",
        "Alerts: 118 with a fixed ±7% rule, 9 with a band per segment; 7 of the 9 are explained.",
        "Forecast: plan 4.87 M trips; actual 4.82 M; WAPE 3.5%."], "Results"))
    p.add("recommendations", 840, 330, 420, 380, textbox([
        [("Recommendations at 16 Feb", BOLD)],
        "1. Plan 4.87 M trips with B2. Watch the 17 Feb holiday and keep a plan for rain or snow.",
        "2. Do not give the credit to everyone: test on selected riders with a 10% holdout for at least 14 days.",
        "3. Switch to the segment band for alerts; get Nov-Dec 2024 data before measuring the fee again."], "Recommendations"))
    pages.append(p)

    p = Page("fee_credit", "Fee and credit")
    header(p, "Step 1-2: congestion fee and Lyft credit",
           "Both are measured against a comparison group: trips outside the zone. Observational, not an experiment.")
    p.add("fee_window", 20, 72, 400, 300, chart("clusteredColumnChart", {
        "Category": [projection(column("FactFeeWindow", "Bar"), active=True)],
        "Y": [projection(measure("FactFeeWindow", "Zone trips"))]},
        "Zone trips in 21 days vs the expected level", "Column chart of zone trips in 2024, expected 2025 and actual 2025"))
    p.add("fee_gap_daily", 440, 72, 620, 300, chart("clusteredColumnChart", {
        "Category": [projection(column("DimDate", "Date"), active=True)],
        "Series": [projection(column("FactFeeGap", "Period"))],
        "Y": [projection(measure("FactFeeGap", "Daily gap"))]},
        "Daily zone vs outside gap, 2025 vs same weekday 2024 (fee from 5 Jan)",
        "Column chart of the daily gap before and after the fee start"))
    for i, (title, prop) in enumerate([("Outside zone growth", "Outside trip growth"), ("Gap 6-26 Jan", "Gap 6-26 Jan"),
                                       ("Gap 2-4 Jan (no fee yet)", "Gap before fee 2-4 Jan")]):
        p.add(f"fee_kpi_{i + 1}", 1080, 72 + i * 102, 180, 94, card(title, "FactKPI", prop))
    p.add("lyft_share", 20, 382, 620, 330, chart("clusteredColumnChart", {
        "Category": [projection(column("FactLyftShare", "ZoneGroup"), active=True)],
        "Series": [projection(column("FactLyftShare", "Period"))],
        "Y": [projection(measure("FactLyftShare", "Lyft share"))]},
        "Lyft share of Uber + Lyft trips, with and after the credit",
        "Column chart of Lyft share inside and outside the zone in the two periods"))
    for i, (title, prop) in enumerate([("Lyft zone share gain (pp)", "Lyft zone share gap pp"),
                                       ("Extra Lyft zone trips", "Credit uplift"),
                                       ("Cost per extra trip ($6 margin)", "Credit cost per extra trip"),
                                       ("Break-even: extra trips needed", "Break-even uplift")]):
        p.add(f"credit_kpi_{i + 1}", 660 + (i % 2) * 304, 382 + (i // 2) * 120, 296, 110, card(title, "FactKPI", prop))
    p.add("credit_note", 660, 622, 600, 90, textbox([
        "Cost = 106.15 trips x $1.50 credit / 6.15 extra trips. Assumes a $6 margin and every credit used; "
        "if only half are used it is still about $12.9 per extra trip."], "Credit cost note"))
    pages.append(p)

    p = Page("weather_alerts", "Weather and alerts")
    header(p, "Step 3: rain and daily alerts",
           "Rain: each rain hour vs dry hours of the same month, weekday and hour, summer 2024. Alerts: 4 segments x 90 days.")
    p.add("rain", 20, 72, 620, 300, chart("clusteredBarChart", {
        "Category": [projection(column("FactWeather", "Weather"), active=True)],
        "Y": [projection(measure("FactWeather", m)) for m in ("Trips vs dry hours", "Wait vs dry hours")]},
        "Trips and waiting time vs dry hours (summer 2024: 35 heavy-rain hours, 14 events)",
        "Bar chart of the change in trips and wait time in light and heavy rain"))
    p.add("fixed_alerts", 660, 72, 296, 110, card("Alerts, fixed ±7% rule", "FactKPI", "Fixed 7% rule alerts"))
    p.add("band_alerts", 964, 72, 296, 110, card("Alerts, band of 2.5 x segment SD", "FactAlertList", "Band alerts"))
    p.add("alert_reasons", 660, 192, 600, 180, chart("clusteredBarChart", {
        "Category": [projection(column("FactAlertList", "Reason"), active=True)],
        "Y": [projection(measure("FactAlertList", "Band alerts"))]},
        "Why the 9 band alerts happened", "Bar chart of band alerts by reason"))
    p.add("alerts", 20, 382, 1240, 330, chart("tableEx", {"Values": [projection(column("FactAlertList", c)) for c in
                                                                    ("Date", "Segment", "TripCount", "Expected", "Reason", "ReferenceDays")]},
        "Band alerts and the weather on their reference days", "Table of the nine segment-days outside the band"))
    pages.append(p)

    p = Page("forecast", "Holiday-week plan")
    header(p, "Step 4: plan for 17-23 Feb 2025",
           "History ends at 16 Feb and counts only trips completed by then. B2 was chosen before the week was scored.", 1000)
    p.add("forecast_segment", 1040, 14, 220, 52, slicer("DimSegment", "Segment", "Segment"))
    p.add("plan_vs_actual", 20, 72, 820, 330, chart("clusteredColumnChart", {
        "Category": [projection(column("DimDate", "Date"), active=True)],
        "Y": [projection(measure("FactForecast", m)) for m in ("Actual trips", "Plan B2")]},
        "Actual trips vs plan B2 per day", "Column chart comparing actual trips with plan B2 per day"))
    for i, (title, prop) in enumerate([("Plan B2, week", "Plan B2"), ("Actual trips, week", "Actual trips"),
                                       ("Plan vs actual", "Plan vs actual")]):
        p.add(f"forecast_kpi_{i + 1}", 860, 72 + i * 112, 400, 104,
              card(title, "FactForecast", prop, units=EXACT if prop != "Plan vs actual" else None))
    p.add("scores", 20, 412, 620, 150, no_totals(chart("tableEx", {"Values": [
        projection(column("DimMethod", "Method")), projection(column("DimMethod", "Description")),
        projection(measure("FactForecast", "WAPE")), projection(measure("FactForecast", "Bias"))]},
        "Forecast error by method (WAPE = sum of absolute errors / actual trips, 28 cells)", "Table of WAPE and bias by method")))
    p.add("daily_gap", 660, 412, 600, 150, no_totals(chart("tableEx", {"Values": [
        projection(column("DimDate", "Date")), projection(measure("FactForecast", "Actual trips")),
        projection(measure("FactForecast", "Plan B2")), projection(measure("FactForecast", "Plan vs actual"))]},
        "Plan vs actual by day", "Table of actual trips, plan and difference by day")))
    p.add("forecast_reading", 20, 572, 1240, 140, textbox([
        [("Reading", BOLD)],
        "B2 missed by 3.5% (WAPE), better than last week alone (B1, 4.4%). The plan was 1.1% above actual.",
        "The largest miss is Sunday 23 Feb (+4.5%): both reference days, 9 and 16 Feb, had rain or snow, while 23 Feb was dry."],
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
