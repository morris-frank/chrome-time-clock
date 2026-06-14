"""Infer approximate workday start/end from Chrome browser history."""

import argparse
import csv
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from zoneinfo import ZoneInfo

# Chrome/WebKit epoch: microseconds since 1601-01-01 00:00 UTC
CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)

INTERNAL_SCHEMES = ("chrome://", "chrome-extension://", "about:", "file://")

DEFAULT_TIMEZONE = "Europe/Amsterdam"
DEFAULT_GAP_MINUTES = 60
DEFAULT_PROFILE = "Default"
DEFAULT_OUT_DIR = "./chrome_workhours_export"

WARN_MIN_VISITS_PER_DAY = 5
WARN_MAX_SPAN_HOURS = 16
WARN_EARLIEST_HOUR = 5
WARN_LATEST_HOUR_MINUTE = (23, 30)


def resolve_history_path(browser: str, profile: str, history_db: Optional[Union[str, Path]]) -> Path:
    """Resolve the path to the browser history database based on OS and browser."""
    if history_db:
        return Path(history_db).expanduser()

    home = Path.home()
    browser_lower = browser.lower()

    if sys.platform == "darwin":  # macOS
        roots = {
            "chrome": home / "Library/Application Support/Google/Chrome",
            "chromium": home / "Library/Application Support/Chromium",
            "brave": home / "Library/Application Support/BraveSoftware/Brave-Browser",
        }
    elif sys.platform == "win32":  # Windows
        local_app_data = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
        roots = {
            "chrome": local_app_data / "Google/Chrome/User Data",
            "chromium": local_app_data / "Chromium/User Data",
            "brave": local_app_data / "BraveSoftware/Brave-Browser/User Data",
        }
    else:  # Linux / other Unix
        roots = {
            "chrome": home / ".config/google-chrome",
            "chromium": home / ".config/chromium",
            "brave": home / ".config/BraveSoftware/Brave-Browser",
        }

    root = roots.get(browser_lower)
    if root is None:
        raise ValueError(
            f"Unknown browser '{browser}' on platform '{sys.platform}'. "
            f"Supported browsers: chrome, chromium, brave. Or use --history-db for a custom path."
        )
    return root / profile / "History"


def copy_history_db(src: Path) -> Path:
    """Copy the history database to a temporary location to avoid locking issues."""
    if not src.exists():
        raise FileNotFoundError(f"History DB not found: {src}")
    tmp_dir = Path(tempfile.mkdtemp())
    tmp_file = tmp_dir / "History"
    shutil.copy2(src, tmp_file)
    return tmp_file


def read_visits(db_path: Path) -> List[Dict[str, Any]]:
    """Read visit records from the SQLite history database."""
    # Use read-only mode to prevent database modification
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.execute(
            """
            SELECT
                visits.id        AS visit_id,
                visits.visit_time,
                urls.url,
                urls.title
            FROM visits
            JOIN urls ON urls.id = visits.url
            WHERE visits.visit_time > 0
            ORDER BY visits.visit_time ASC
            """
        )
        rows = [
            {"visit_id": r[0], "visit_time": r[1], "url": r[2], "title": r[3] or ""}
            for r in cur.fetchall()
        ]
    finally:
        con.close()
    return rows


def chrome_time_to_datetime(value: int) -> datetime:
    """Convert Chrome WebKit microsecond timestamp to timezone-aware datetime."""
    return CHROME_EPOCH + timedelta(microseconds=value)


def convert_times(visits: List[Dict[str, Any]], tz: ZoneInfo) -> List[Dict[str, Any]]:
    """Convert raw timestamps to local datetimes and dates."""
    out = []
    for v in visits:
        dt_utc = chrome_time_to_datetime(v["visit_time"])
        dt_local = dt_utc.astimezone(tz)
        out.append({**v, "timestamp_local": dt_local, "date_local": dt_local.date()})
    return out


def filter_visits(
    visits: List[Dict[str, Any]],
    ignore_schemes: Tuple[str, ...] = INTERNAL_SCHEMES,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Filter out internal browser schemes and restrict to date range."""
    out = []
    for v in visits:
        url = v["url"]
        if any(url.startswith(s) for s in ignore_schemes):
            continue
        d = v["date_local"]
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        out.append(v)
    return out


def compute_blocks(day_visits: List[Dict[str, Any]], gap_minutes: int) -> List[Dict[str, Any]]:
    """Cluster visits into active blocks separated by inactivity gaps."""
    if not day_visits:
        return []
    threshold = timedelta(minutes=gap_minutes)
    blocks = []
    block_start = day_visits[0]["timestamp_local"]
    block_end = day_visits[0]["timestamp_local"]
    block_count = 1

    for v in day_visits[1:]:
        ts = v["timestamp_local"]
        if ts - block_end <= threshold:
            block_end = ts
            block_count += 1
        else:
            blocks.append({"start": block_start, "end": block_end, "n_visits": block_count})
            block_start = ts
            block_end = ts
            block_count = 1

    blocks.append({"start": block_start, "end": block_end, "n_visits": block_count})
    return blocks


def group_daily(
    visits: List[Dict[str, Any]], gap_minutes: int
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Group visits by day and compute daily summaries and block intervals."""
    by_day: Dict[date, List[Dict[str, Any]]] = {}
    for v in visits:
        by_day.setdefault(v["date_local"], []).append(v)

    daily_rows = []
    block_rows = []

    for d in sorted(by_day):
        day_visits = sorted(by_day[d], key=lambda x: x["timestamp_local"])
        blocks = compute_blocks(day_visits, gap_minutes)

        first_seen = day_visits[0]["timestamp_local"]
        last_seen = day_visits[-1]["timestamp_local"]
        gross_span = (last_seen - first_seen).total_seconds() / 3600

        active_secs = sum(
            (b["end"] - b["start"]).total_seconds() for b in blocks
        )
        active_hours = active_secs / 3600

        daily_rows.append(
            {
                "date": d.isoformat(),
                "first_seen": first_seen.strftime("%H:%M"),
                "last_seen": last_seen.strftime("%H:%M"),
                "gross_span_hours": round(gross_span, 2),
                "active_block_hours": round(active_hours, 2),
                "n_blocks": len(blocks),
                "n_visits": len(day_visits),
                "_first_dt": first_seen,
                "_last_dt": last_seen,
            }
        )

        for b in blocks:
            dur = (b["end"] - b["start"]).total_seconds() / 3600
            block_rows.append(
                {
                    "date": d.isoformat(),
                    "block_start": b["start"].strftime("%H:%M"),
                    "block_end": b["end"].strftime("%H:%M"),
                    "duration_hours": round(dur, 2),
                    "n_visits": b["n_visits"],
                }
            )

    return daily_rows, block_rows


def write_csv(rows: List[Dict[str, Any]], path: Path, fieldnames: List[str]) -> None:
    """Write rows to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(daily_rows: List[Dict[str, Any]], path: Path) -> None:
    """Write daily summaries to a Markdown table file."""
    lines = [
        "# Chrome Work Hours Summary",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| Date | First | Last | Gross h | Active h | Blocks | Visits |",
        "|------|-------|------|---------|----------|--------|--------|",
    ]
    for r in daily_rows:
        lines.append(
            f"| {r['date']} | {r['first_seen']} | {r['last_seen']} "
            f"| {r['gross_span_hours']:.2f} | {r['active_block_hours']:.2f} "
            f"| {r['n_blocks']} | {r['n_visits']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def emit_warnings(daily_rows: List[Dict[str, Any]]) -> List[str]:
    """Check daily rows for potential anomalies and return a list of warning strings."""
    warn_late_h, warn_late_m = WARN_LATEST_HOUR_MINUTE
    warnings = []
    for r in daily_rows:
        d_str = r["date"]
        if r["n_visits"] < WARN_MIN_VISITS_PER_DAY:
            warnings.append(f"WARN {d_str}: only {r['n_visits']} visits (< {WARN_MIN_VISITS_PER_DAY})")
        if r["gross_span_hours"] > WARN_MAX_SPAN_HOURS:
            warnings.append(f"WARN {d_str}: gross span {r['gross_span_hours']:.1f} h > {WARN_MAX_SPAN_HOURS} h")
        first_h = r["_first_dt"].hour
        if first_h < WARN_EARLIEST_HOUR:
            warnings.append(f"WARN {d_str}: first visit at {r['first_seen']} (before 0{WARN_EARLIEST_HOUR}:00)")
        last_dt = r["_last_dt"]
        if (last_dt.hour, last_dt.minute) > (warn_late_h, warn_late_m):
            warnings.append(f"WARN {d_str}: last visit at {r['last_seen']} (after {warn_late_h}:{warn_late_m:02d})")
    return warnings


def extract_workhours(
    browser: str = "chrome",
    profile: str = DEFAULT_PROFILE,
    history_db: Optional[Union[str, Path]] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    timezone_str: str = DEFAULT_TIMEZONE,
    gap_minutes: int = DEFAULT_GAP_MINUTES,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """
    Programmatic API to extract work hours from browser history.
    
    Returns:
        Tuple of (daily_rows, block_rows, warnings)
    """
    tz = ZoneInfo(timezone_str)
    src = resolve_history_path(browser, profile, history_db)
    tmp_db = copy_history_db(src)

    try:
        raw = read_visits(tmp_db)
        converted = convert_times(raw, tz)
        filtered = filter_visits(converted, date_from=date_from, date_to=date_to)
        
        if not filtered:
            return [], [], []

        daily_rows, block_rows = group_daily(filtered, gap_minutes)
        warnings = emit_warnings(daily_rows)
        return daily_rows, block_rows, warnings
    finally:
        try:
            shutil.rmtree(tmp_db.parent, ignore_errors=True)
        except OSError:
            pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Infer workday start/end from Chrome browser history."
    )
    p.add_argument("--profile", default=DEFAULT_PROFILE, help="Chrome profile name (default: Default)")
    p.add_argument("--browser", default="chrome", choices=["chrome", "chromium", "brave"])
    p.add_argument("--history-db", default=None, help="Direct path to History SQLite file")
    p.add_argument("--from", dest="date_from", default=None, help="Start date YYYY-MM-DD (inclusive)")
    p.add_argument("--to", dest="date_to", default=None, help="End date YYYY-MM-DD (inclusive)")
    p.add_argument("--timezone", default=DEFAULT_TIMEZONE, help="IANA timezone (default: Europe/Amsterdam)")
    p.add_argument("--gap-minutes", type=int, default=DEFAULT_GAP_MINUTES, help="Inactivity gap threshold in minutes")
    p.add_argument("--out", default=DEFAULT_OUT_DIR, help="Output directory")
    p.add_argument("--markdown", action="store_true", help="Also write daily_summary.md")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    date_from = (
        datetime.strptime(args.date_from, "%Y-%m-%d").date() if args.date_from else None
    )
    date_to = (
        datetime.strptime(args.date_to, "%Y-%m-%d").date() if args.date_to else None
    )

    try:
        daily_rows, block_rows, warnings = extract_workhours(
            browser=args.browser,
            profile=args.profile,
            history_db=args.history_db,
            date_from=date_from,
            date_to=date_to,
            timezone_str=args.timezone,
            gap_minutes=args.gap_minutes,
        )
        
        if not daily_rows:
            print("No visits found after filtering. Nothing to do.")
            return

        print(f"Days summarised: {len(daily_rows)}")
        for w in warnings:
            print(f"  {w}")

        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)

        daily_path = out_dir / "daily_summary.csv"
        blocks_path = out_dir / "blocks.csv"

        write_csv(
            daily_rows,
            daily_path,
            ["date", "first_seen", "last_seen", "gross_span_hours", "active_block_hours", "n_blocks", "n_visits"],
        )
        write_csv(
            block_rows,
            blocks_path,
            ["date", "block_start", "block_end", "duration_hours", "n_visits"],
        )

        if args.markdown:
            md_path = out_dir / "daily_summary.md"
            write_markdown(daily_rows, md_path)
            print(f"Markdown written to:  {md_path}")

        print(f"Output written to: {out_dir.resolve()}")
        print(f"  {daily_path.name}: {len(daily_rows)} days")
        print(f"  {blocks_path.name}: {len(block_rows)} blocks")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
