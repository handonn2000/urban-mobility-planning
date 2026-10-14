"""Package reviewable source artifacts, excluding raw data and local runtimes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import zipfile


def package_portfolio(root):
    root = Path(root).resolve()
    output = root / "delivery"
    output.mkdir(exist_ok=True)
    allowed_roots = ["docs", "notebooks", "scripts", "sql", "excel", "reports", "powerbi", "data/external", "data/processed"]
    files = [root / name for name in ["README.md", "AGENTS.md", ".gitignore", "requirements.txt", "requirements.in", "reporting-requirements.txt"]]
    for name in allowed_roots:
        for path in (root / name).rglob("*"):
            if path.is_file() and not any(part.startswith(".") or part == "__pycache__" for part in path.relative_to(root).parts):
                if not path.name.endswith(".inspect.ndjson") and path.suffix not in [".pyc", ".parquet", ".duckdb", ".abf"]:
                    files.append(path)
    files = sorted(set(files))
    archive = output / "urban_mobility_portfolio.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for path in files:
            z.write(path, str(Path("urban-mobility-planning") / path.relative_to(root)))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert not any(any(part in ["raw", "weather_raw", ".venv", ".analysis-cache", ".artifacts", ".git", "__pycache__", ".pbi"] for part in Path(name).parts) for name in z.namelist())
        assert not any(name.endswith(".parquet") for name in z.namelist())
        members = z.namelist()
    result = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "archive": str(archive.relative_to(root)),
              "files": len(files), "bytes": archive.stat().st_size, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "raw_and_runtime_excluded": True, "zip_integrity_checked": True, "native_PBIX_included": any(name.endswith(".pbix") for name in members),
              "published": False, "native_report_status": "Draft; Power BI native validation pending"}
    (output / "portfolio_package_manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    package_portfolio(Path(__file__).resolve().parents[1])
