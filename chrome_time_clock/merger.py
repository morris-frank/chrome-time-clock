"""Merge multiple blocks.csv files, collapsing overlapping intervals."""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union


def parse_dt(d: str, t: str) -> datetime:
    """Parse date and time strings into a datetime object."""
    return datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")


def load_blocks(paths: List[Path]) -> List[Dict[str, Any]]:
    """Load block records from a list of CSV files."""
    rows = []
    for p in paths:
        with open(p, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append({
                    "date": row["date"],
                    "start": parse_dt(row["date"], row["block_start"]),
                    "end":   parse_dt(row["date"], row["block_end"]),
                    "n_visits": int(row["n_visits"]),
                })
    return rows


def merge_intervals(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort and merge overlapping or adjacent block intervals."""
    if not rows:
        return []

    rows.sort(key=lambda r: (r["date"], r["start"]))
    merged = []
    cur = dict(rows[0])

    for r in rows[1:]:
        # extend if overlapping or immediately adjacent (same minute)
        if r["date"] == cur["date"] and r["start"] <= cur["end"]:
            cur["end"] = max(cur["end"], r["end"])
            cur["n_visits"] += r["n_visits"]
        else:
            merged.append(cur)
            cur = dict(r)

    merged.append(cur)
    return merged


def write_blocks(rows: List[Dict[str, Any]], path: Path) -> None:
    """Write merged blocks to a CSV file."""
    fieldnames = ["date", "block_start", "block_end", "duration_hours", "n_visits"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            dur = (r["end"] - r["start"]).total_seconds() / 3600
            w.writerow({
                "date": r["date"],
                "block_start": r["start"].strftime("%H:%M"),
                "block_end":   r["end"].strftime("%H:%M"),
                "duration_hours": round(dur, 2),
                "n_visits": r["n_visits"],
            })


def write_daily(rows: List[Dict[str, Any]], path: Path) -> None:
    """Derive and write daily summaries from merged blocks to a CSV file."""
    by_day: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_day.setdefault(r["date"], []).append(r)

    fieldnames = ["date", "first_seen", "last_seen", "gross_span_hours",
                  "active_block_hours", "n_blocks", "n_visits"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for d in sorted(by_day):
            day = by_day[d]
            first = min(r["start"] for r in day)
            last  = max(r["end"]   for r in day)
            gross = (last - first).total_seconds() / 3600
            active = sum((r["end"] - r["start"]).total_seconds() for r in day) / 3600
            w.writerow({
                "date": d,
                "first_seen": first.strftime("%H:%M"),
                "last_seen":  last.strftime("%H:%M"),
                "gross_span_hours":  round(gross, 2),
                "active_block_hours": round(active, 2),
                "n_blocks": len(day),
                "n_visits": sum(r["n_visits"] for r in day),
            })


def merge_blocks(
    files: List[Union[str, Path]],
    out_blocks: Union[str, Path] = "merged_blocks.csv",
    out_daily: Union[str, Path] = "merged_daily.csv",
) -> None:
    """
    Programmatic API to merge multiple blocks.csv files and write outputs.
    """
    paths = [Path(f) for f in files]
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Files not found: {', '.join(str(m) for m in missing)}")

    rows = load_blocks(paths)
    merged = merge_intervals(rows)

    write_blocks(merged, Path(out_blocks))
    write_daily(merged, Path(out_daily))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Merge blocks.csv files, collapsing overlapping time intervals."
    )
    p.add_argument("files", nargs="+", help="blocks.csv files to merge")
    p.add_argument("--out-blocks", default="merged_blocks.csv")
    p.add_argument("--out-daily",  default="merged_daily.csv",
                   help="Derive a daily summary from merged blocks")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    try:
        merge_blocks(
            files=args.files,
            out_blocks=args.out_blocks,
            out_daily=args.out_daily,
        )
        print(f"Successfully merged {len(args.files)} file(s).")
        print(f"Written: {args.out_blocks}")
        print(f"Written: {args.out_daily}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
