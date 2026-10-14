"""Build a portable PBIP source draft; native Power BI validation is separate."""
from pathlib import Path
import base64
import json
import re
import uuid


SCHEMA_ROOT = "https://developer.microsoft.com/json-schemas/"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def build_powerbi_project(root):
    root = Path(root)
    source = root / "powerbi"
    draft = source / "draft"
    contract = json.loads((source / "data_contract.json").read_text())
    model = {"name": "UrbanMobility", "compatibilityLevel": 1601,
             "model": {"culture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3", "tables": [], "relationships": [],
                       "annotations": [{"name": "EvidenceStatus", "value": "Local source draft; native Desktop refresh and DAX not executed."}]}}
    dimension_keys = {"DimDate": "Date", "DimSegment": "SegmentKey", "DimMethod": "Method", "DimHour": "Hour", "DimFeeOperator": "FeeOperator", "DimTripGroup": "TripGroup", "DimZone": "TouchesZone"}
    by_name = {}
    query_lines = ["# Embedded snapshot Power Query sources", "", "UTF-8 CSV snapshots are embedded in the draft so there is no machine-specific source path. Rebuild after rerunning analysis; native refresh reloads the embedded snapshot, not a live TLC feed.", ""]
    type_map = {"dateTime": "type datetime", "int64": "Int64.Type", "double": "type number", "boolean": "type logical", "string": "type text"}
    for entry in contract:
        name = entry["table"]
        encoded = base64.b64encode((source / entry["csv"]).read_bytes()).decode()
        transforms = ", ".join('{"' + col + '", ' + type_map[kind] + '}' for col, kind in entry["columns"].items())
        expression = ["let", f'    Source = Csv.Document(Binary.FromText("{encoded}", BinaryEncoding.Base64), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
                      '    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),',
                      '    Nullable = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),',
                      f'    Typed = Table.TransformColumnTypes(Nullable, {{{transforms}}}, "en-US")', "in", "    Typed"]
        columns = [{"name": col, "dataType": kind, "sourceColumn": col, "summarizeBy": "none",
                    "isHidden": col == "SegmentKey" and not name.startswith("Dim")} for col, kind in entry["columns"].items()]
        for column in columns:
            if dimension_keys.get(name) == column["name"]:
                column["isKey"] = True
            if column["dataType"] == "dateTime":
                column["formatString"] = "yyyy-MM-dd HH:mm" if column["name"] == "DateTime" else "yyyy-MM-dd"
            if name == "DimDate" and column["name"] == "DayName":
                column["sortByColumn"] = "Weekday"
        table = {"name": name, "columns": columns, "partitions": [{"name": name, "mode": "import", "source": {"type": "m", "expression": expression}}]}
        if name == "DimDate": table["dataCategory"] = "Time"
        model["model"]["tables"].append(table)
        by_name[name] = table
        query_lines += [f"## {name}", "", "```powerquery", *expression, "```", ""]
    measures = []
    for block in (source / "measures.dax").read_text().strip().split("\n\n"):
        name, expression = block.split(":=", 1)
        name = name.strip()
        owner = "FactForecast" if name.startswith("Forecast") else "FactPlan" if name.startswith(("Planned", "Holiday scenario")) else "FactFeeEffect" if name.startswith("Fee") else "FactCreditSummary" if name.startswith(("Credit", "Illustrative")) else "FactWeeklyShare" if name.startswith("Weekly") else "FactWeatherFactors" if name.startswith("Summer") else "FactCityHourly" if name.startswith("City") else "FactAlerts" if name.startswith("Alert") else "FactDaily"
        fmt = "0.00%" if any(x in name.lower() for x in ["wape", "bias", "share", "change", "gap"]) and "pp" not in name else '"$"#,0.00' if "cost" in name.lower() or "fare" in name.lower() else "0.000" if "factor" in name else "0.000" if "pp" in name else "#,0.00" if "wait" in name or "MAE" in name else "#,0"
        measure = {"name": name, "expression": expression.strip().splitlines(), "formatString": fmt,
                   "description": "See report_model_guide.md for grain, denominator, availability and filter semantics."}
        by_name[owner].setdefault("measures", []).append(measure)
        measures.append({"name": name, "table": owner, "format": fmt})
    def relate(fact, column, dimension, key):
        model["model"]["relationships"].append({"name": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{fact}.{column}-{dimension}.{key}")),
                                                "fromTable": fact, "fromColumn": column, "fromCardinality": "many",
                                                "toTable": dimension, "toColumn": key, "toCardinality": "one", "crossFilteringBehavior": "oneDirection", "isActive": True})
    for fact in ["FactDaily", "FactCityHourly", "FactAlerts", "FactPlan", "FactForecast", "FactWeeklyShare"]:
        relate(fact, "Date", "DimDate", "Date")
    for fact in ["FactDaily", "FactAlerts", "FactPlan", "FactForecast"]:
        relate(fact, "SegmentKey", "DimSegment", "SegmentKey")
    relate("FactCityHourly", "Hour", "DimHour", "Hour")
    relate("FactForecast", "Method", "DimMethod", "Method")
    relate("FactFeeEffect", "FeeOperator", "DimFeeOperator", "FeeOperator")
    relate("FactFeeEffect", "TripGroup", "DimTripGroup", "TripGroup")
    relate("FactWeeklyShare", "TouchesZone", "DimZone", "TouchesZone")
    relate("DimSegment", "TouchesZone", "DimZone", "TouchesZone")
    model_dir = draft / "UrbanMobility.SemanticModel"
    report_dir = draft / "UrbanMobility.Report"
    write_json(model_dir / "model.bim", model)
    write_json(model_dir / "definition.pbism", {"$schema": SCHEMA_ROOT + "fabric/item/semanticModel/definitionProperties/1.0.0/schema.json", "version": "1.0"})
    write_json(draft / "UrbanMobility.pbip", {"$schema": SCHEMA_ROOT + "fabric/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0", "artifacts": [{"report": {"path": "UrbanMobility.Report"}}], "settings": {"enableAutoRecovery": True}})
    write_json(report_dir / "definition.pbir", {"$schema": SCHEMA_ROOT + "fabric/item/report/definitionProperties/2.0.0/schema.json", "version": "4.0", "datasetReference": {"byPath": {"path": "../UrbanMobility.SemanticModel"}}})
    definition = report_dir / "definition"
    write_json(definition / "version.json", {"$schema": SCHEMA_ROOT + "fabric/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    write_json(definition / "report.json", {"$schema": SCHEMA_ROOT + "fabric/item/report/definition/report/2.0.0/schema.json", "themeCollection": {}})
    page_names = ["monitoring_weather", "price_credit_plan"]
    write_json(definition / "pages/pages.json", {"$schema": SCHEMA_ROOT + "fabric/item/report/definition/pagesMetadata/1.0.0/schema.json", "pageOrder": page_names, "activePageName": page_names[0]})
    measure_owner = {m["name"]: m["table"] for m in measures}
    visual_spec = []
    def col(table, prop): return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}
    def measure(name): return {"Measure": {"Expression": {"SourceRef": {"Entity": measure_owner[name]}}, "Property": name}}
    def date_filter(start, end):
        comparisons = []
        for kind, value in [(2, start), (4, end)]:
            comparisons.append({"Comparison": {"ComparisonKind": kind, "Left": {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "Date"}}, "Right": {"Literal": {"Value": f"datetime'{value}T00:00:00'"}}}})
        return {"filters": [{"name": "DateWindow", "field": col("DimDate", "Date"), "type": "Advanced",
                             "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "DimDate", "Type": 0}], "Where": [{"Condition": {"And": {"Left": comparisons[0], "Right": comparisons[1]}}}]}}]}
    def visual(page, name, kind, title, position, roles, filters=None):
        state = {}
        for role, fields in roles.items():
            projections = []
            for field in fields:
                body = next(iter(field.values())); entity = body["Expression"]["SourceRef"]["Entity"]
                projections.append({"field": field, "queryRef": f"{entity}.{body['Property']}", "nativeQueryRef": body["Property"]})
            state[role] = {"projections": projections}
        data = {"$schema": SCHEMA_ROOT + "fabric/item/report/definition/visualContainer/2.4.0/schema.json", "name": name,
                "position": dict(zip(["x", "y", "width", "height"], position), z=len(visual_spec), tabOrder=len(visual_spec)),
                "visual": {"visualType": kind, "query": {"queryState": state},
                           "visualContainerObjects": {"title": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}, "text": {"expr": {"Literal": {"Value": "'" + title.replace("'", "''") + "'"}}}}}]}}}
        if filters: data["filterConfig"] = filters
        write_json(definition / f"pages/{page}/visuals/{name}/visual.json", data)
        visual_spec.append({"page": page, "id": name, "type": kind, "title": title, "position": position, "roles": roles})
    for page, title in zip(page_names, ["Monitoring and weather", "Price, credit and plan"]):
        page_data = {"$schema": SCHEMA_ROOT + "fabric/item/report/definition/page/2.0.0/schema.json", "name": page, "displayName": title, "displayOption": "FitToPage", "width": 1280, "height": 720}
        if page == page_names[0]: page_data["filterConfig"] = date_filter("2025-01-06", "2025-01-26")
        write_json(definition / f"pages/{page}/page.json", page_data)
    page = page_names[0]
    for i, name in enumerate(["Trips", "Trips weekday year change", "Lyft share selected zones", "Alert rows"]):
        visual(page, f"kpi_{i}", "card", name, [15 + i*315, 10, 300, 105], {"Values": [measure(name)]})
    visual(page, "segment_slicer", "slicer", "Segment | weather remains city-wide", [15, 120, 450, 65], {"Values": [col("DimSegment", "SegmentLabel")]})
    visual(page, "daily_trips", "lineChart", "Completed trips by segment", [15, 190, 610, 265], {"Category": [col("DimDate", "Date")], "Series": [col("DimSegment", "SegmentLabel")], "Y": [measure("Trips")]})
    visual(page, "city_heatmap", "pivotTable", "City-wide mean trips per weekday / hour", [640, 190, 625, 265], {"Rows": [col("DimDate", "DayName")], "Columns": [col("DimHour", "Hour")], "Values": [measure("City average hourly trips")]})
    visual(page, "alerts", "tableEx", "Alert watchlist | hypotheses and next steps", [15, 470, 905, 235], {"Values": [col("FactAlerts", "Date"), col("DimSegment", "SegmentLabel"), col("FactAlerts", "TripsDeviation"), col("FactAlerts", "WaitDeviation"), col("FactAlerts", "NextStep")]})
    visual(page, "rain_trips", "card", "Summer rain >2mm/h | city trips factor, 35h", [935, 470, 330, 110], {"Values": [measure("Summer heavy rain trips factor")]})
    visual(page, "rain_wait", "card", "Summer rain >2mm/h | wait factor", [935, 595, 330, 110], {"Values": [measure("Summer heavy rain wait factor")]})
    page = page_names[1]
    for i, name in enumerate(["Fee all-trip gap", "Credit share gap pp", "Illustrative credit cost per extra trip", "Planned trips B2"]):
        visual(page, f"decision_kpi_{i}", "card", name, [15+i*315, 10, 300, 105], {"Values": [measure(name)]})
    visual(page, "fee_operator_slicer", "slicer", "Fee operator | fixed matched January window", [15, 120, 450, 65], {"Values": [col("DimFeeOperator", "FeeOperator")]})
    visual(page, "fee_groups", "clusteredBarChart", "Relative zone gap | overlapping groups", [15, 190, 435, 245], {"Category": [col("DimTripGroup", "TripGroup")], "Y": [measure("Fee relative gap")]})
    visual(page, "weekly_share", "lineChart", "Lyft share | full weeks, retrospective", [465, 190, 800, 245], {"Category": [col("DimDate", "Date")], "Series": [col("DimZone", "ZoneLabel")], "Y": [measure("Weekly Lyft share")]})
    visual(page, "forecast_comparison", "lineChart", "17-23 Feb | actual joined after forecast freeze", [15, 455, 835, 250], {"Category": [col("DimDate", "Date")], "Y": [measure("Forecast B1 trips"), measure("Forecast B2 trips"), measure("Forecast B3 trips"), measure("Forecast actual trips")]}, date_filter("2025-02-17", "2025-02-23"))
    visual(page, "forecast_scores", "tableEx", "Backtest | no winner known at cutoff", [865, 455, 400, 250], {"Values": [col("DimMethod", "Method"), measure("Forecast MAE"), measure("Forecast WAPE"), measure("Forecast bias")]})
    write_json(source / "report_visual_spec.json", visual_spec)
    write_json(source / "model_design.json", {"business_purpose": "Understand January served demand and the separately frozen holiday-week plan in thirty seconds.",
                                              "evidence_status": "Local source draft", "tables": contract, "relationships": model["model"]["relationships"],
                                              "measures": measures, "native_powerbi_validated": False,
                                              "security": "Public aggregate source data only; no credentials, RLS roles or external publication configured.",
                                              "refresh": "Embedded immutable snapshot; regenerate from analysis to update. No cloud refresh or credentials configured."})
    (source / "power_query_sources.md").write_text("\n".join(query_lines))
    print(f"Built source draft: {draft / 'UrbanMobility.pbip'}; native refresh/DAX/rendering not executed.")


if __name__ == "__main__":
    build_powerbi_project(Path(__file__).resolve().parents[1])
